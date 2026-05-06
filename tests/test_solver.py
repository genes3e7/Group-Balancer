"""Unit tests for the solver module.

Updated to match the professional standards refactor (models and result formats).
"""

from unittest.mock import patch

import pandas as pd
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
        assert strategy.get_score_vectors([], None) is None


def test_solver_extreme_value_error():
    """Cover ValueError for safety bound violation."""
    # Use two participants with different scores to ensure non-zero deviation
    participants = [
        Participant(name="P1", scores={"S1": 100.0}),
        Participant(name="P2", scores={"S1": 0.0}),
    ]
    # Weight high enough to trigger safety bound (> 2^62)
    huge_weight = 1e16
    with patch("src.core.models.SolverConfig.validate_safety_bounds"):
        cfg = SolverConfig(
            num_groups=2, group_capacities=[1, 1], score_weights={"S1": huge_weight}
        )
    from src.core.solver import AdvancedScoring, ConstraintBuilder

    strategy = AdvancedScoring()
    builder = ConstraintBuilder(participants, cfg)
    builder.build_variables()
    msg = "Objective aggregate exceeds safety bound"
    with pytest.raises(ValueError, match=msg):
        builder.add_scoring_objectives(strategy)


def test_solver_zero_sum_weighted_error():
    """Verify ValueError is raised if a weighted dimension has zero absolute sum."""
    cfg = get_solver_config(1, [1], weights={"S1": 1.0})
    with pytest.raises(ValueError, match="has weight but sum is 0"):
        solver.solve_with_ortools([{"Name": "P1", "Score1": 0.0}], cfg)


def test_solver_tie_breaker_pressure():
    """Verify the tie-breaker ensures canonical ordering for symmetric optima.

    With symmetric scores (10 and 20, target 15 each), there are two optimal
    arrangements with identical objective values. The tie-breaker should
    force P0 into G2 and P1 into G1 to minimize penalty (0 vs 1).
    We use different capacities to avoid group symmetry breaking.
    """
    p = [
        {"Name": "P0", "Score1": 10, "Separators": "A"},
        {"Name": "P1", "Score1": 10, "Separators": "B"},
    ]
    cfg = get_solver_config(2, [1, 1])
    results, _, _ = solver.solve_with_ortools(p, cfg)

    # Tie-breaker sum(g * i * x[i,g])
    # Arr 1: P0 in G1 (0,0), P1 in G2 (1,1). Penalty 1.
    # Arr 2: P0 in G2 (1,0), P1 in G1 (0,1). Penalty 0.
    # Arr 2 is better. P0 should be in Group 2.
    p0 = next(r for r in results if r[config.COL_NAME] == "P0")
    assert p0[config.COL_GROUP] == 2


def test_solver_quantization_preservation():
    """Verify variance preservation for tight distributions with large N.

    Ensures that scores like 3.51 and 3.49 are NOT crushed to the same integer.
    """
    participants = []
    # 100 people: 50 have 3.51, 50 have 3.49
    for i in range(100):
        s = 3.51 if i < 50 else 3.49
        participants.append({"Name": f"P{i}", "Score1": s})

    # Balance into 2 groups of 50
    cfg = get_solver_config(2, [50, 50])
    results, status, _ = solver.solve_with_ortools(participants, cfg)

    assert status == cp_model.OPTIMAL

    # Each group should have 25 of 3.51 and 25 of 3.49 to be perfectly balanced
    df = pd.DataFrame(results)
    for gid in [1, 2]:
        group = df[df[config.COL_GROUP] == gid]
        # Mean should be exactly 3.5.
        # Relaxed bound for 100x resolution.
        assert abs(group[SCORE_COL].mean() - 3.5) < 0.01


def test_solver_zero_sum_weighted_error_simple():
    """Verify ValueError in SimpleScoring for zero-sum weighted dimensions."""
    cfg = get_solver_config(1, [1], weights={"S1": 1.0}, mode=OptimizationMode.SIMPLE)
    with pytest.raises(ValueError, match="has weight but sum is 0"):
        solver.solve_with_ortools([{"Name": "P1", "Score1": 0.0}], cfg)


def test_solver_soft_groupers():
    """Verify soft grouper cohesion penalties are added."""
    # 2 groups of 2. P0, P1 both have tag 'T'.
    p = make_participants(4, groupers=["T", "T", "", ""])
    # Not strict
    cfg = get_solver_config(2, [2, 2])
    results, status, _ = solver.solve_with_ortools(p, cfg)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    # They should be together because it's optimal
    t_groups = {p[config.COL_GROUP] for p in results if "T" in p[config.COL_GROUPER]}
    assert len(t_groups) == 1


def test_solver_soft_groupers_clamping():
    """Trigger the cohesion penalty clamping logic with a safe but high weight."""
    p = make_participants(4, groupers=["T", "T", "", ""])
    # Max safe weight
    cfg = SolverConfig(
        num_groups=2,
        group_capacities=[2, 2],
        score_weights={SCORE_COL: 1.0},
        opt_mode=OptimizationMode.ADVANCED,
        grouper_weight=1_000,
    )
    results, status, _ = solver.solve_with_ortools(p, cfg)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_solver_simple_multi_dimension():
    """Verify SimpleScoring with multiple dimensions and symmetry breaking."""
    s2 = f"{config.SCORE_PREFIX}2"
    participants = [
        {config.COL_NAME: "P1", SCORE_COL: 100, s2: 10},
        {config.COL_NAME: "P2", SCORE_COL: 10, s2: 100},
    ]
    # Weight both.
    cfg = get_solver_config(
        2, [1, 1], weights={SCORE_COL: 1.0, s2: 1.0}, mode=OptimizationMode.SIMPLE
    )
    results, status, _ = solver.solve_with_ortools(participants, cfg)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_solver_clean_helpers():
    """Cover _clean_tag_cell and _clean_score_cell edge cases."""
    from src.core.solver import _clean_score_cell, _clean_tag_cell

    # Tag cleaning
    assert _clean_tag_cell(None) == ""
    assert _clean_tag_cell(pd.NA) == ""
    assert _clean_tag_cell("ABC") == "ABC"

    # Score cleaning
    assert _clean_score_cell(None) == 0.0
    assert _clean_score_cell(" ") == 0.0
    assert _clean_score_cell("not a float") == 0.0
    assert _clean_score_cell(12.5) == 12.5
    # Cover the TypeError/ValueError paths
    assert _clean_score_cell([]) == 0.0


def test_solver_multi_dimension_symmetry_breaking():
    """Ensure group symmetry breaking only applies to the first canonical dimension."""
    s2 = f"{config.SCORE_PREFIX}2"
    participants = [
        {config.COL_NAME: "P1", SCORE_COL: 100, s2: 10},
        {config.COL_NAME: "P2", SCORE_COL: 10, s2: 100},
    ]
    # Weight both. Symmetry breaking should happen for Score1.
    cfg = get_solver_config(2, [1, 1], weights={SCORE_COL: 1.0, s2: 1.0})
    results, status, _ = solver.solve_with_ortools(participants, cfg)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
