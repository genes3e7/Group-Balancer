"""Unit tests for the solver module.

Updated to match the professional standards refactor (models and result formats).
"""

from unittest.mock import patch

import pytest
from ortools.sat.python import cp_model

from src.core import config, solver
from src.core.models import (
    ConflictPriority,
    OptimizationMode,
    Participant,
    SolverConfig,
)

SCORE_COL = f"{config.SCORE_PREFIX}1"


def make_participants(
    count: int,
    score: float = 100.0,
    groupers: list[str] | None = None,
    separators: list[str] | None = None,
) -> list[dict]:
    """Helper to generate mock participant data."""
    if groupers is None:
        groupers = [""] * count
    if separators is None:
        separators = [""] * count

    # Ensure lists match count
    groupers = (groupers + [""] * count)[:count]
    separators = (separators + [""] * count)[:count]

    data = []
    for i in range(count):
        data.append(
            {
                config.COL_NAME: f"P{i}",
                SCORE_COL: score,
                config.COL_GROUPER: groupers[i],
                config.COL_SEPARATOR: separators[i],
            },
        )
    return data


def get_solver_config(
    num_groups: int,
    capacities: list[int],
    weights: dict[str, float] | None = None,
    mode: OptimizationMode = OptimizationMode.ADVANCED,
    priority: ConflictPriority = ConflictPriority.GROUPERS,
) -> SolverConfig:
    """Helper to create SolverConfig."""
    if weights is None:
        weights = {SCORE_COL: 1.0}
    return SolverConfig(
        num_groups=num_groups,
        group_capacities=capacities,
        score_weights=weights,
        opt_mode=mode,
        conflict_priority=priority,
        timeout_seconds=10,
    )


def test_solver_basic_split():
    """Test standard even partitioning."""
    participants = make_participants(10)
    cfg = get_solver_config(2, [5, 5])
    results, _, _ = solver.solve_with_ortools(participants, cfg)

    assert len(results) == 10
    group_counts = {}
    for p in results:
        gid = p[config.COL_GROUP]
        group_counts[gid] = group_counts.get(gid, 0) + 1

    assert group_counts == {1: 5, 2: 5}


def test_solver_unequal_sizes():
    """Test splitting into different sizes."""
    participants = make_participants(10)
    cfg = get_solver_config(3, [4, 3, 3])
    results, _, _ = solver.solve_with_ortools(participants, cfg)

    group_counts = {}
    for p in results:
        gid = p[config.COL_GROUP]
        group_counts[gid] = group_counts.get(gid, 0) + 1

    assert sorted(group_counts.values()) == [3, 3, 4]


def test_solver_multi_dimensional_weighted():
    """Test multi-objective weighting."""
    s2 = f"{config.SCORE_PREFIX}2"
    participants = [
        {config.COL_NAME: "P1", SCORE_COL: 100, s2: 10},
        {config.COL_NAME: "P2", SCORE_COL: 10, s2: 100},
        {config.COL_NAME: "P3", SCORE_COL: 100, s2: 10},
        {config.COL_NAME: "P4", SCORE_COL: 10, s2: 100},
    ]
    cfg = get_solver_config(2, [2, 2], weights={SCORE_COL: 1.0, s2: 0.0})
    results, status, _ = solver.solve_with_ortools(participants, cfg)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert len(results) == 4

    # Check that each group has one 100 and one 10 for Score1
    for gid in [1, 2]:
        members = [p for p in results if p[config.COL_GROUP] == gid]
        assert sum(m[SCORE_COL] for m in members) == 110


def test_solver_pigeonhole_separator():
    """Test separator spread.

    With 4 participants (3 'A' tags) and 2 groups of size 2,
    the proportional limit ceil(3 * 2 / 4) = 2 should be enforced.
    """
    p = make_participants(4, separators=["A", "A", "A", ""])
    cfg = get_solver_config(2, [2, 2])
    results, _, _ = solver.solve_with_ortools(p, cfg)

    # 3 'A's spread over 2 groups: limit 2
    g1_sep = sum(
        1
        for p in results
        if p[config.COL_GROUP] == 1 and "A" in p[config.COL_SEPARATOR]
    )
    g2_sep = sum(
        1
        for p in results
        if p[config.COL_GROUP] == 2 and "A" in p[config.COL_SEPARATOR]
    )
    assert g1_sep <= 2
    assert g2_sep <= 2
    assert g1_sep + g2_sep == 3
    assert g1_sep >= 1


def test_solver_fractional_cohesion():
    """Test grouper cohesion."""
    p = make_participants(6, groupers=["T", "T", "T", "", "", ""])
    cfg = get_solver_config(2, [3, 3])
    results, _, _ = solver.solve_with_ortools(p, cfg)

    # Check if T's are together
    t_groups = {p[config.COL_GROUP] for p in results if "T" in p[config.COL_GROUPER]}
    assert len(t_groups) == 1


def test_solver_conflict_resolution():
    """Test priority resolution."""
    p = make_participants(4, groupers=["X", "X", "", ""], separators=["X", "X", "", ""])

    # Priority: Groupers -> Together
    cfg_g = get_solver_config(2, [2, 2], priority=ConflictPriority.GROUPERS)
    res_g, _, _ = solver.solve_with_ortools(p, cfg_g)
    gids_g = {p[config.COL_GROUP] for p in res_g if "X" in p[config.COL_GROUPER]}
    assert len(gids_g) == 1

    # Priority: Separators -> Apart
    cfg_s = get_solver_config(2, [2, 2], priority=ConflictPriority.SEPARATORS)
    res_s, _, _ = solver.solve_with_ortools(p, cfg_s)
    gids_s = {p[config.COL_GROUP] for p in res_s if "X" in p[config.COL_SEPARATOR]}
    assert len(gids_s) == 2


def test_solver_rounding_extreme():
    """Cover edge cases in solver.py rounding."""
    participants = [Participant(name="P1", scores={"S1": 10.0})]
    cfg = SolverConfig(
        num_groups=1, group_capacities=[1], score_weights={"S1": 0.00000000001}
    )
    from src.core.solver import AdvancedScoring

    strategy = AdvancedScoring()
    vectors = strategy.get_score_vectors(participants, cfg)
    assert vectors[0][2] == 1


def test_circular_conflict_edge():
    """Test solver behavior with circular or contradictory constraints."""
    from src.core.solver_interface import run_optimization

    # A groupers B, B groupers C, C separators A
    participants = [
        Participant(name="A", scores={"S": 10}, groupers="X", separators="Z"),
        Participant(name="B", scores={"S": 10}, groupers="X", separators=""),
        Participant(name="C", scores={"S": 10}, groupers="Y", separators="X"),
    ]

    solver_config = SolverConfig(
        num_groups=2,
        group_capacities=[2, 1],
        score_weights={"S": 1.0},
        opt_mode=OptimizationMode.SIMPLE,
        conflict_priority=ConflictPriority.GROUPERS,
    )

    df, metrics = run_optimization(participants, solver_config)
    assert df is not None
    assert len(df) == 3
    assert metrics["status"] in ["OPTIMAL", "FEASIBLE"]


def test_scoring_strategy_pass():
    """Cover the abstract pass in ScoringStrategy (line 112)."""
    from src.core.solver import ScoringStrategy

    with patch.multiple(ScoringStrategy, __abstractmethods__=frozenset()):
        strategy = ScoringStrategy()
        strategy.get_score_vectors([], None)


def test_solver_extreme_value_error():
    """Cover line 250 ValueError."""
    participants = [Participant(name="P1", scores={"S1": 1.0})]
    # A huge weight so weight_m > 2**60
    # weight_m is weight * 100, so weight > 2**60 / 100
    huge_weight = (2**61) / 100.0
    with patch("src.core.models.SolverConfig.__post_init__"):
        cfg = SolverConfig(
            num_groups=1, group_capacities=[1], score_weights={"S1": huge_weight}
        )
    from src.core.solver import AdvancedScoring, ConstraintBuilder

    strategy = AdvancedScoring()
    builder = ConstraintBuilder(participants, cfg)
    builder.build_variables()
    with pytest.raises(ValueError, match="too extreme even after scaling"):
        builder.add_scoring_objectives(strategy)


def test_solver_objective_generation_edge():
    """Cover lines 230 (min_sum==0, max_sum==0), 234-244, and 250."""
    participants = [Participant(name="P1", scores={"S1": 1e12, "S2": 0.0})]
    cfg = SolverConfig(
        num_groups=2, group_capacities=[1, 1], score_weights={"S1": 1.0, "S2": 1.0}
    )
    from src.core.solver import AdvancedScoring, ConstraintBuilder

    strategy = AdvancedScoring()
    builder = ConstraintBuilder(participants, cfg)
    builder.build_variables()
    with patch("src.core.solver.logger.warning") as mock_warn:
        builder.add_scoring_objectives(strategy)
        mock_warn.assert_called()
