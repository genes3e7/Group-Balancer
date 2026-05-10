"""Unit tests for the lexicographic bit-slicing scaling logic.

Ensures that priority tiers (Separators, Groupers, Fairness, Balance) are
strictly respected and correctly toggled via the Priority settings.
"""

from ortools.sat.python import cp_model

from src.core import config, solver
from src.core.models import ConflictPriority, SolverConfig
from src.core.solver import AdvancedScoring


def test_scaling_constants_lock():
    """Explicitly enforce mathematical priority hierarchy constants.

    Serves as a sentinel to prevent drift in bit-sliced multipliers or
    precision resolution.
    """
    assert config.TIER_HI_MULTIPLIER == 10**12
    assert config.TIER_LO_MULTIPLIER == 10**9
    assert config.TIER_FAIRNESS_MULTIPLIER == 10**7
    assert config.TIER_BALANCE_MULTIPLIER == 10**0
    assert config.RESOLUTION_BASE == 1000
    assert config.SCALE_FACTOR == 10**5


def test_priority_separators_wins():
    """Verify HI Tier (Separators) strictly outweighs LO Tier (Groupers).

    Conflict scenario:
    - P0 and P1 share a Separator tag 'S' (Want them apart).
    - P2 and P3 share a Grouper tag 'G' (Want them together).
    If Separators win, the solver must prioritize splitting P0/P1 even
    if it potentially compromises other constraints.
    """
    participants = [
        {config.COL_NAME: "P0", "Score1": 10, config.COL_SEPARATOR: "S"},
        {config.COL_NAME: "P1", "Score1": 10, config.COL_SEPARATOR: "S"},
        {config.COL_NAME: "P2", "Score1": 10, config.COL_GROUPER: "G"},
        {config.COL_NAME: "P3", "Score1": 10, config.COL_GROUPER: "G"},
    ]

    cfg = SolverConfig(
        num_groups=2,
        group_capacities=[2, 2],
        score_weights={"Score1": 1.0},
        conflict_priority=ConflictPriority.SEPARATORS,
        timeout_seconds=5,
    )

    results, status, _ = solver.solve_with_ortools(participants, cfg)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    p0_group = next(r[config.COL_GROUP] for r in results if r[config.COL_NAME] == "P0")
    p1_group = next(r[config.COL_GROUP] for r in results if r[config.COL_NAME] == "P1")

    # Separators priority wins -> P0 and P1 are split
    assert p0_group != p1_group


def test_priority_groupers_wins():
    """Verify HI Tier (Groupers) strictly outweighs LO Tier (Separators).

    Conflict scenario:
    - P0 and P1 share a Separator tag 'S' (Want them apart).
    - P2 and P3 share a Grouper tag 'G' (Want them together).
    If Groupers win, keeping P2/P3 together takes precedence.
    """
    participants = [
        {config.COL_NAME: "P0", "Score1": 10, config.COL_SEPARATOR: "S"},
        {config.COL_NAME: "P1", "Score1": 10, config.COL_SEPARATOR: "S"},
        {config.COL_NAME: "P2", "Score1": 10, config.COL_GROUPER: "G"},
        {config.COL_NAME: "P3", "Score1": 10, config.COL_GROUPER: "G"},
    ]

    cfg = SolverConfig(
        num_groups=2,
        group_capacities=[2, 2],
        score_weights={"Score1": 1.0},
        conflict_priority=ConflictPriority.GROUPERS,
        timeout_seconds=5,
    )

    results, status, _ = solver.solve_with_ortools(participants, cfg)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    p0_group = next(r[config.COL_GROUP] for r in results if r[config.COL_NAME] == "P0")
    p1_group = next(r[config.COL_GROUP] for r in results if r[config.COL_NAME] == "P1")

    # Groupers priority wins -> P0 and P1 are kept together
    assert p0_group == p1_group


def test_tier_hi_over_tier3_fairness():
    """Verify that the HI tier strictly outweighs Max-Min Fairness.

    Conflict scenario:
    - P0 and P1 share a Grouper tag 'G' (Want them together).
    - Scores: P0=100, P1=100, P2=10, P3=10.
    - Fairness wants [P0, P2] and [P1, P3] (Sums 110 vs 110).
    - Grouper HI wants [P0, P1] and [P2, P3] (Sums 200 vs 20).
    Under default multipliers, HI wins and they stay together.
    """
    participants = [
        {config.COL_NAME: "P0", "Score1": 100, config.COL_GROUPER: "G"},
        {config.COL_NAME: "P1", "Score1": 100, config.COL_GROUPER: "G"},
        {config.COL_NAME: "P2", "Score1": 10, config.COL_GROUPER: ""},
        {config.COL_NAME: "P3", "Score1": 10, config.COL_GROUPER: ""},
    ]

    cfg = SolverConfig(
        num_groups=2,
        group_capacities=[2, 2],
        score_weights={"Score1": 1.0},
        conflict_priority=ConflictPriority.GROUPERS,
        timeout_seconds=5,
    )

    results, status, _ = solver.solve_with_ortools(participants, cfg)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    p0_group = next(r[config.COL_GROUP] for r in results if r[config.COL_NAME] == "P0")
    p1_group = next(r[config.COL_GROUP] for r in results if r[config.COL_NAME] == "P1")

    # HI tier wins -> P0 and P1 are kept together despite fairness cost
    assert p0_group == p1_group

    # Case 2: Reduce HI multiplier significantly to force Fairness to win
    # Note: We patch the solver module where the multipliers are consumed
    from unittest.mock import patch

    with patch("src.core.solver.config.TIER_HI_MULTIPLIER", 1):
        results2, status2, _ = solver.solve_with_ortools(participants, cfg)
        assert status2 in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        p0_g2 = next(
            r[config.COL_GROUP] for r in results2 if r[config.COL_NAME] == "P0"
        )
        p1_g2 = next(
            r[config.COL_GROUP] for r in results2 if r[config.COL_NAME] == "P1"
        )
        # Now Fairness wins -> P0 and P1 are split

        assert p0_g2 != p1_g2


def test_norm_multiplier_precision():
    """Verify that high-precision normalization is active and functional."""
    participants_raw = []
    for i in range(10):
        s = 1.002 if i == 0 else 1.000
        participants_raw.append({config.COL_NAME: f"P{i}", "Score1": s})

    cfg = SolverConfig(
        num_groups=2, group_capacities=[5, 5], score_weights={"Score1": 1.0}
    )

    participants = [
        solver.Participant(
            name=p[config.COL_NAME], scores={"Score1": p["Score1"]}, original_index=i
        )
        for i, p in enumerate(participants_raw)
    ]

    strategy = AdvancedScoring()
    vectors = strategy.get_score_vectors(participants, cfg)

    scores = vectors[0][1]
    assert abs(scores[0] - scores[1]) >= 1
    assert abs(scores[0] - scores[1]) / max(scores) >= 0.001
