"""Unit tests to enforce and lock in the lexicographic bit-slicing scaling logic.

Ensures that the priority tiers (Separators > Groupers > Fairness > Balance)
are strictly respected and cannot be regressed by future changes.
"""

from ortools.sat.python import cp_model

from src.core import config, solver
from src.core.models import ConflictPriority, OptimizationMode, SolverConfig


def test_tier1_sep_over_tier2_group():
    """Verify Tier 1 (Separators) strictly outweighs Tier 2 (Groupers).

    Scenario:
    - 4 participants, 2 groups (Capacities: 2, 2).
    - P0 and P1 share a Separator tag 'S'.
    - P0 and P1 share a Grouper tag 'G'.
    - Limit for 'S' in any group is ceil(2 * 2 / 4) = 1.
    - If Sep ($10^12$) > Group ($10^9$), P0 and P1 MUST be separated.
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
            config.COL_SEPARATOR: "S",
        },
        {
            config.COL_NAME: "P2",
            "Score1": 10,
            config.COL_GROUPER: "",
            config.COL_SEPARATOR: "",
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
        opt_mode=OptimizationMode.ADVANCED,
        conflict_priority=ConflictPriority.GROUPERS,
        timeout_seconds=5,
    )

    results, status, _ = solver.solve_with_ortools(participants, cfg)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    p0_group = next(r[config.COL_GROUP] for r in results if r[config.COL_NAME] == "P0")
    p1_group = next(r[config.COL_GROUP] for r in results if r[config.COL_NAME] == "P1")

    # Must be separated as Sep penalty ($10^12$) > Grouper penalty ($10^9$)
    assert p0_group != p1_group


def test_tier2_group_over_tier3_fairness():
    """Verify Tier 2 (Groupers) strictly outweighs Tier 3 (Max-Min Fairness).

    Scenario:
    - 4 participants, 2 groups (Capacities: 2, 2).
    - P0 and P1 share a Grouper tag 'G'.
    - Scores are designed so placing P0 and P1 together causes a Max-Min imbalance.
    - If Group ($10^9$) > Fairness ($10^7$), P0 and P1 MUST be together.
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
        opt_mode=OptimizationMode.ADVANCED,
        conflict_priority=ConflictPriority.GROUPERS,
        timeout_seconds=5,
    )

    results, status, _ = solver.solve_with_ortools(participants, cfg)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    p0_group = next(r[config.COL_GROUP] for r in results if r[config.COL_NAME] == "P0")
    p1_group = next(r[config.COL_GROUP] for r in results if r[config.COL_NAME] == "P1")

    # They MUST be together because Grouper penalty ($10^9$) > Fairness imbalance
    assert p0_group == p1_group


def test_norm_multiplier_precision():
    """Verify that 0.001 precision (1000 * N) is active.

    Ensures that small score differences are preserved after normalization.
    """
    # Use 10 participants to increase the norm_multiplier magnitude (10,000)
    participants_raw = []
    for i in range(10):
        # 1.000 vs 1.002 to avoid round-to-even collisions at 0.5 boundaries
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
