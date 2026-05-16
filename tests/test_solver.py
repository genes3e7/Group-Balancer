"""Unit tests for the solver module.

Ensures that partition logic, constraint satisfaction, objective weighting,
and search determinism behave correctly in the high-precision CP-SAT engine.
"""

from unittest.mock import patch

import pandas as pd
import pytest
from ortools.sat.python import cp_model

from src.core import config, solver
from src.core.models import (
    ConflictPriority,
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
    """Helper to generate mock participant data.

    Args:
        count (int): Number of participants to create.
        score (float): Default score for each participant.
        groupers (list[str] | None): Optional list of grouper tags.
        separators (list[str] | None): Optional list of separator tags.

    Returns:
        list[dict]: List of participant dictionaries.
    """
    if groupers is None:
        groupers = [""] * count
    if separators is None:
        separators = [""] * count

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
    priority: ConflictPriority = ConflictPriority.GROUPERS,
) -> SolverConfig:
    """Helper to create SolverConfig.

    Args:
        num_groups (int): Number of groups.
        capacities (list[int]): Group capacities.
        weights (dict[str, float] | None): Optional score weights.
        priority (ConflictPriority): Conflict priority.

    Returns:
        SolverConfig: The constructed configuration.
    """
    if weights is None:
        weights = {SCORE_COL: 1.0}
    return SolverConfig(
        num_groups=num_groups,
        group_capacities=capacities,
        score_weights=weights,
        conflict_priority=priority,
        timeout_seconds=10,
    )


def test_solver_basic_split() -> None:
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


def test_solver_unequal_sizes() -> None:
    """Test splitting into different sizes."""
    participants = make_participants(10)
    cfg = get_solver_config(3, [4, 3, 3])
    results, _, _ = solver.solve_with_ortools(participants, cfg)

    group_counts = {}
    for p in results:
        gid = p[config.COL_GROUP]
        group_counts[gid] = group_counts.get(gid, 0) + 1

    assert sorted(group_counts.values()) == [3, 3, 4]


def test_solver_multi_dimensional_weighted() -> None:
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

    for gid in [1, 2]:
        members = [p for p in results if p[config.COL_GROUP] == gid]
        assert sum(m[SCORE_COL] for m in members) == 110


def test_solver_pigeonhole_separator() -> None:
    """Test separator spread via proportional limits."""
    p = make_participants(4, separators=["A", "A", "A", ""])
    cfg = get_solver_config(2, [2, 2], priority=ConflictPriority.SEPARATORS)
    results, _, _ = solver.solve_with_ortools(p, cfg)

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


def test_solver_fractional_cohesion() -> None:
    """Test grouper cohesion."""
    p = make_participants(6, groupers=["T", "T", "T", "", "", ""])
    cfg = get_solver_config(2, [3, 3])
    results, _, _ = solver.solve_with_ortools(p, cfg)

    t_groups = {p[config.COL_GROUP] for p in results if "T" in p[config.COL_GROUPER]}
    assert len(t_groups) == 1


def test_solver_conflict_resolution() -> None:
    """Test priority resolution between groupers and separators."""
    p = make_participants(4, groupers=["X", "X", "", ""], separators=["X", "X", "", ""])

    cfg_g = get_solver_config(2, [2, 2], priority=ConflictPriority.GROUPERS)
    res_g, _, _ = solver.solve_with_ortools(p, cfg_g)
    gids_g = {p[config.COL_GROUP] for p in res_g if "X" in p[config.COL_GROUPER]}
    assert len(gids_g) == 1

    cfg_s = get_solver_config(2, [2, 2], priority=ConflictPriority.SEPARATORS)
    res_s, _, _ = solver.solve_with_ortools(p, cfg_s)
    gids_s = {p[config.COL_GROUP] for p in res_s if "X" in p[config.COL_SEPARATOR]}
    assert len(gids_s) == 2


def test_solver_rounding_extreme() -> None:
    """Cover edge cases in solver.py rounding."""
    participants = [Participant(name="P1", scores={"S1": 10.0})]
    cfg = SolverConfig(
        num_groups=1, group_capacities=[1], score_weights={"S1": 0.00000000001}
    )
    from src.core.solver import AdvancedScoring

    strategy = AdvancedScoring()
    vectors = strategy.get_score_vectors(participants, cfg)
    assert vectors[0][2] == 1


def test_circular_conflict_edge() -> None:
    """Test solver behavior with contradictory constraints."""
    from src.core.solver_interface import run_optimization

    participants = [
        Participant(name="A", scores={"S": 10}, groupers="X", separators="Z"),
        Participant(name="B", scores={"S": 10}, groupers="X", separators=""),
        Participant(name="C", scores={"S": 10}, groupers="Y", separators="X"),
    ]

    solver_config = SolverConfig(
        num_groups=2,
        group_capacities=[2, 1],
        score_weights={"S": 1.0},
        conflict_priority=ConflictPriority.GROUPERS,
    )

    df, metrics = run_optimization(participants, solver_config)
    assert df is not None
    assert len(df) == 3
    assert metrics["status"] in ["OPTIMAL", "FEASIBLE"]


def test_solver_zero_sum_weighted_error() -> None:
    """Verify ValueError is raised if a weighted dimension has zero absolute sum."""
    col = f"{config.SCORE_PREFIX}1"
    cfg = get_solver_config(1, [1], weights={col: 1.0})
    with pytest.raises(ValueError, match="has weight but sum is 0"):
        solver.solve_with_ortools([{"Name": "P1", col: 0.0}], cfg)


def test_solver_tie_breaker_pressure() -> None:
    """Verify the tie-breaker ensures canonical ordering for symmetric optima.

    This test validates that the tie-breaker term in get_model:
    sum(g * original_index * x_ig) forces P1 (original_index=1) into group 1
    and P0 (original_index=0) into group 2, because the solver minimizes the
    objective. P0 has the lower index, so the solver prefers assigning it to
    the group with the higher index (group 2) to minimize g*index.
    """
    p = [
        {"Name": "P0", "Score1": 10, "Separators": "A"},
        {"Name": "P1", "Score1": 10, "Separators": "B"},
    ]
    cfg = get_solver_config(2, [1, 1])
    results, _, _ = solver.solve_with_ortools(p, cfg)

    p0 = next(r for r in results if r[config.COL_NAME] == "P0")
    assert p0[config.COL_GROUP] == 2


def test_solver_quantization_preservation() -> None:
    """Verify variance preservation for tight distributions with large N."""
    participants = []
    for i in range(100):
        s = 3.51 if i < 50 else 3.49
        participants.append({"Name": f"P{i}", "Score1": s})

    cfg = get_solver_config(2, [50, 50])
    results, status, _ = solver.solve_with_ortools(participants, cfg)

    assert status == cp_model.OPTIMAL

    df = pd.DataFrame(results)
    for gid in [1, 2]:
        group = df[df[config.COL_GROUP] == gid]
        assert abs(group[SCORE_COL].mean() - 3.5) < 0.01


def test_solver_soft_groupers() -> None:
    """Verify soft grouper cohesion penalties are added."""
    p = make_participants(4, groupers=["T", "T", " ", " "])
    cfg = get_solver_config(2, [2, 2])
    results, status, _ = solver.solve_with_ortools(p, cfg)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    t_groups = {p[config.COL_GROUP] for p in results if "T" in p[config.COL_GROUPER]}
    assert len(t_groups) == 1


def test_solver_soft_groupers_clamping() -> None:
    """Trigger the cohesion penalty clamping logic with a safe but high weight."""
    p = make_participants(4, groupers=["T", "T", "", ""])
    cfg = SolverConfig(
        num_groups=2,
        group_capacities=[2, 2],
        score_weights={SCORE_COL: 1.0},
        grouper_weight=1_000,
    )
    results, status, _ = solver.solve_with_ortools(p, cfg)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    t_groups = {r[config.COL_GROUP] for r in results if "T" in r[config.COL_GROUPER]}
    assert len(t_groups) == 1


def test_solver_clean_helpers() -> None:
    """Cover _clean_tag_cell and _clean_score_cell edge cases."""
    from src.core.solver import _clean_score_cell, _clean_tag_cell

    assert _clean_tag_cell(None) == ""
    assert _clean_tag_cell(pd.NA) == ""
    assert _clean_tag_cell("ABC") == "ABC"

    assert _clean_score_cell(None) == 0.0
    assert _clean_score_cell(" ") == 0.0
    assert _clean_score_cell("not a float") == 0.0
    assert _clean_score_cell(12.5) == 12.5
    assert _clean_score_cell([]) == 0.0
    assert _clean_score_cell(float("nan")) == 0.0
    assert _clean_score_cell(float("inf")) == 0.0


def test_solver_multi_dimension_symmetry_breaking() -> None:
    """Ensure group symmetry breaking only applies to the first canonical dimension.

    Scenario 1: S1=10/10, S2=10/20. S1 is canonical (alphabetical).
    Symmetry breaking on S1 is non-binding (g1_S1 <= g2_S1 is always 10 <= 10).
    The tie-breaker favors P1 in G2 (lowest index in highest group).
    If S2 symmetry was binding, P2 (higher S2) would forced into G2.

    Scenario 2: Mirror swap. S1=10/20, S2=10/10. S1 is still canonical.
    Symmetry breaking on S1 is now binding (g1_S1 <= g2_S1 -> G1 must have P1).
    """
    # Case 1
    participants = [
        {"Name": "P1", "Score1": 10, "Score2": 10},
        {"Name": "P2", "Score1": 10, "Score2": 20},
    ]
    cfg = get_solver_config(2, [1, 1], weights={"Score1": 1.0, "Score2": 1.0})
    results, status, _ = solver.solve_with_ortools(participants, cfg)
    assert status == cp_model.OPTIMAL
    p1 = next(r for r in results if r[config.COL_NAME] == "P1")
    # P1 pushed to G2 by tie-breaker because S1 symmetry is not binding
    assert p1[config.COL_GROUP] == 2

    # Case 2: Mirror swap. S1 is now binding.
    p_mirror = [
        {"Name": "P1", "Score1": 10, "Score2": 10},
        {"Name": "P2", "Score1": 20, "Score2": 10},
    ]
    res_m, status_m, _ = solver.solve_with_ortools(p_mirror, cfg)
    assert status_m == cp_model.OPTIMAL
    p1_m = next(r for r in res_m if r[config.COL_NAME] == "P1")
    # P1 MUST be in G1 because G1_S1 <= G2_S1 (10 <= 20)
    assert p1_m[config.COL_GROUP] == 1


def test_solver_hint_range_warning() -> None:
    """Verify that out-of-range warm-start hints trigger a warning log."""
    p = [Participant(name="P1", scores={"S1": 10}, original_index=0)]
    cfg = SolverConfig(
        num_groups=1,
        group_capacities=[1],
        score_weights={"S1": 1.0},
        hints_by_index={0: 99},
    )
    builder = solver.ConstraintBuilder(p, cfg)
    with patch("src.core.solver.logger.warning") as mock_log:
        builder.add_solution_hints()
        assert mock_log.called


def test_solver_identity_buckets_complex() -> None:
    """Exercise the symmetry-aware hint mapping logic with duplicate candidates.

    Construction:
    - P1 and P2 are identical (Name, Scores, Tags).
    - Hints assign P1 to Group 1 and P2 to Group 2.
    - The loop must consume these hints in canonical order.
    """
    p = [
        Participant(name="Identical", scores={"S1": 10}, original_index=0),
        Participant(name="Identical", scores={"S1": 10}, original_index=1),
    ]
    cfg = SolverConfig(
        num_groups=2,
        group_capacities=[1, 1],
        score_weights={"S1": 1.0},
        hints_by_index={0: 1, 1: 2},
    )
    builder = solver.ConstraintBuilder(p, cfg)
    builder.build_variables()

    # Capture AddHint calls via monkeypatching the model
    with patch.object(builder.model, "AddHint") as mock_add_hint:
        builder.add_solution_hints()
        # Verify that hints were consumed for both participants in the zip loop
        assert mock_add_hint.call_count == 2
        # Check first hint: p0 in g0 (int(1)-1)
        mock_add_hint.assert_any_call(builder.x[(0, 0)], 1)
        # Check second hint: p1 in g1 (int(2)-1)
        mock_add_hint.assert_any_call(builder.x[(1, 1)], 1)


def test_solver_strict_grouping_enforcement() -> None:
    """Verify that strict grouping forces participants together."""
    cfg = SolverConfig(
        num_groups=2,
        group_capacities=[1, 1],  # Max capacity 1, but strict group of 2 needed
        score_weights={"Score1": 1.0},
        strict_grouping=True,
    )
    # This should be INFEASIBLE because they MUST be together (size 2)
    # but max capacity is 1.
    _, status, _ = solver.solve_with_ortools(
        [
            {"Name": "P1", "Score1": 10, config.COL_GROUPER: "G"},
            {"Name": "P2", "Score1": 10, config.COL_GROUPER: "G"},
        ],
        cfg,
    )
    assert status == cp_model.INFEASIBLE


def test_solver_hint_out_of_range() -> None:
    """Verify logger warning when a hint is out of the valid group range."""
    p = [Participant(name="P1", scores={"S1": 10}, original_index=0)]
    # Hint for group 999 in a 2-group config
    cfg = SolverConfig(
        num_groups=2,
        group_capacities=[1, 1],
        score_weights={"S1": 1.0},
        hints_by_index={0: 999},
    )
    builder = solver.ConstraintBuilder(p, cfg)
    builder.build_variables()
    with patch("src.core.solver.logger.warning") as mock_log:
        builder.add_solution_hints()
        mock_log.assert_any_call(
            "Warm-start hint out of range for Participant#%d: %s", 0, 999
        )


def test_solver_status_unknown_coverage() -> None:
    """Cover the branch where solver returns an unexpected status."""
    cfg = SolverConfig(
        num_groups=1, group_capacities=[1], score_weights={"Score1": 1.0}
    )
    with patch(
        "ortools.sat.python.cp_model.CpSolver.Solve", return_value=cp_model.UNKNOWN
    ):
        _, status, _ = solver.solve_with_ortools([{"Name": "P1", "Score1": 10}], cfg)
        assert status == cp_model.UNKNOWN


def test_solver_aggregate_objective_error() -> None:
    """Verify ValueError is raised if the bound exceeds 64-bit limits."""
    p = [Participant(name="P1", scores={"Score1": 10}, original_index=0)]
    cfg = SolverConfig(
        num_groups=1, group_capacities=[1], score_weights={"Score1": 1.0}
    )
    builder = solver.ConstraintBuilder(p, cfg)
    builder.build_variables()

    # Artificially blow the objective bound
    builder.objective_bounds = [2**63]
    with pytest.raises(ValueError, match="exceeds CP-SAT safety bound"):
        builder.get_model()
