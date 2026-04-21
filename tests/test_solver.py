"""Unit tests for the solver module.

Updated to match the professional standards refactor (models and result formats).
"""

from src.core import config, solver
from src.core.models import ConflictPriority, OptimizationMode, SolverConfig

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
    weights: dict = None,
    mode=OptimizationMode.ADVANCED,
    priority=ConflictPriority.GROUPERS,
):
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
    results, _, _ = solver.solve_with_ortools(participants, cfg)

    # Check that each group has one 100 and one 10 for Score1
    for gid in [1, 2]:
        members = [p for p in results if p[config.COL_GROUP] == gid]
        assert sum(m[SCORE_COL] for m in members) == 110


def test_solver_pigeonhole_separator():
    """Test separator spread."""
    p = make_participants(4, separators=["A", "A", "A", ""])
    cfg = get_solver_config(2, [3, 1])
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
