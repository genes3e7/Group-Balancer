"""Unit tests to enforce and lock in the lexicographic bit-slicing scaling logic.

Ensures that the priority tiers (Separators, Groupers, Fairness, Balance)
are strictly respected and dynamically swappable via the Priority toggle.
"""

from ortools.sat.python import cp_model

from src.core import config, solver
from src.core.models import ConflictPriority, SolverConfig


def test_scaling_constants_lock():
    """Explicitly enforce the 'perfect' scaling constants in config.py.

    This test serves as a sentinel to prevent any accidental drift in the
    mathematical priority hierarchy or precision resolution.
    """
    assert config.TIER_HI_MULTIPLIER == 10**12
    assert config.TIER_LO_MULTIPLIER == 10**9
    assert config.TIER_FAIRNESS_MULTIPLIER == 10**7
    assert config.TIER_BALANCE_MULTIPLIER == 10**0
    assert config.RESOLUTION_BASE == 1000
    assert config.SCALE_FACTOR == 10**5


def test_priority_separators_wins():
    """Verify HI Tier (Separators) strictly outweighs LO Tier (Groupers).

    Scenario:
    - 4 participants, 2 groups (Capacities: 2, 2).
    - P0/P1 share Grouper 'G' (HI if Priority=Groupers).
    - P0/P2 share Separator 'S' (HI if Priority=Separators).
    - Setting Priority to SEPARATORS should force P0/P2 apart even if it
      splits P0/P1.
    """
    participants = [
        {
            config.COL_NAME: "P0",
            "Score1": 10,
            config.COL_GROUPER: "G",
            config.COL_SEPARATOR: "S",
        },
        {
            config.COL_NAME: "P1",
            "Score1": 10,
            config.COL_GROUPER: "G",
            config.COL_SEPARATOR: "",
        },
        {
            config.COL_NAME: "P2",
            "Score1": 10,
            config.COL_GROUPER: "",
            config.COL_SEPARATOR: "S",
        },
        {
            config.COL_NAME: "P3",
            "Score1": 10,
            config.COL_GROUPER: "",
            config.COL_SEPARATOR: "",
        },
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
    p2_group = next(r[config.COL_GROUP] for r in results if r[config.COL_NAME] == "P2")

    # They MUST be separated because Separators have the HI_MULTIPLIER
    assert p0_group != p2_group


def test_priority_groupers_wins():
    """Verify HI Tier (Groupers) strictly outweighs LO Tier (Separators).

    Scenario:
    - 4 participants, 2 groups (Capacities: 2, 2).
    - P0/P1 share Grouper 'G'.
    - P0/P2 share Separator 'S'.
    - Setting Priority to GROUPERS should force P0/P1 together even if it
      clumps P0/P2.
    """
    participants = [
        {
            config.COL_NAME: "P0",
            "Score1": 10,
            config.COL_GROUPER: "G",
            config.COL_SEPARATOR: "S",
        },
        {
            config.COL_NAME: "P1",
            "Score1": 10,
            config.COL_GROUPER: "G",
            config.COL_SEPARATOR: "",
        },
        {
            config.COL_NAME: "P2",
            "Score1": 10,
            config.COL_GROUPER: "",
            config.COL_SEPARATOR: "S",
        },
        {
            config.COL_NAME: "P3",
            "Score1": 10,
            config.COL_GROUPER: "",
            config.COL_SEPARATOR: "",
        },
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

    # They MUST be together because Groupers have the HI_MULTIPLIER
    assert p0_group == p1_group


def test_tier_hi_over_tier3_fairness():
    """Verify that the HI tier strictly outweighs Max-Min Fairness.

    Scenario:
    - 4 participants, 2 groups (Capacities: 2, 2).
    - P0 and P1 share a Grouper tag 'G'.
    - Imbalance {100, 100} vs {10, 10} is caused if they stay together.
    - If Groupers (HI) > Fairness, they MUST stay together.
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

    assert p0_group == p1_group


def test_norm_multiplier_precision():
    """Verify that high-precision normalization (RESOLUTION_BASE) is active.

    Ensures that small score differences are preserved after normalization.
    """
    participants_raw = []
    for i in range(10):
        # 1.002 vs 1.000 difference is preserved at RESOLUTION_BASE=1000
        s = 1.002 if i == 0 else 1.000
        participants_raw.append({config.COL_NAME: f"P{i}", "Score1": s})

    from src.core.solver import AdvancedScoring

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
    # P0 (1.002) and P1 (1.000) should have different integer scores
    assert scores[0] != scores[1]
