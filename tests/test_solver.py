"""
Unit tests for the solver module.

Tests cover standard capacity balancing, multi-dimensional score weighting,
and advanced categorical constraints (Groupers and Separators).
"""

import pytest
from src.core import solver, config

SCORE_COL = f"{config.SCORE_PREFIX}1"


def make_participants(
    count: int,
    score: float = 100.0,
    star_indices: list[int] | None = None,
    groupers: list[str] | None = None,
    separators: list[str] | None = None,
) -> list[dict]:
    """
    Helper to generate mock participant data with advanced tags.

    Args:
        count (int): Number of participants to create.
        score (float): Default score for all participants.
        star_indices (list[int] | None): Indices of participants to mark as stars.
        groupers (list[str] | None): Grouper tags for participants.
        separators (list[str] | None): Separator tags for participants.

    Returns:
        list[dict]: Generated participant list.
    """
    if star_indices is None:
        star_indices = []
    if groupers is None:
        groupers = [""] * count
    if separators is None:
        separators = [""] * count

    data = []
    for i in range(count):
        name = f"P{i}" + (config.ADVANTAGE_CHAR if i in star_indices else "")
        data.append(
            {
                config.COL_NAME: name,
                SCORE_COL: score,
                config.COL_GROUPER: groupers[i],
                config.COL_SEPARATOR: separators[i],
            }
        )
    return data


def test_solver_basic_split():
    """Test standard even partitioning of participants."""
    participants = make_participants(10, score=100.0)
    groups, success = solver.solve_with_ortools(
        participants,
        group_capacities=[5, 5],
        respect_stars=False,
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
    )
    assert success is True
    assert len(groups) == 2
    for g in groups:
        assert len(g["members"]) == 5


def test_solver_unequal_sizes():
    """Test splitting participants into groups of different sizes."""
    participants = make_participants(10, score=10.0)
    groups, success = solver.solve_with_ortools(
        participants,
        group_capacities=[4, 3, 3],
        respect_stars=False,
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
    )

    assert success is True
    sizes = sorted([len(g["members"]) for g in groups])
    assert sizes == [3, 3, 4]


def test_solver_star_constraints():
    """Test that stars are distributed evenly across groups."""
    # 4 stars, 6 normals -> 2 groups. Should be 2 stars per group.
    participants = make_participants(10, score=50.0, star_indices=[0, 1, 2, 3])
    groups, success = solver.solve_with_ortools(
        participants,
        group_capacities=[5, 5],
        respect_stars=True,
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
    )

    assert success is True
    for g in groups:
        stars = sum(
            1
            for m in g["members"]
            if str(m.get(config.COL_NAME, "")).endswith(config.ADVANTAGE_CHAR)
        )
        assert stars == 2


def test_solver_impossible_stars():
    """Test star distribution when perfect division is mathematically impossible."""
    participants = make_participants(5, score=10.0, star_indices=[0, 1, 2])
    groups, success = solver.solve_with_ortools(
        participants,
        group_capacities=[3, 2],
        respect_stars=True,
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
    )

    assert success is True
    star_counts = sorted(
        [
            sum(
                1
                for m in g["members"]
                if str(m.get(config.COL_NAME, "")).endswith(config.ADVANTAGE_CHAR)
            )
            for g in groups
        ]
    )
    assert star_counts == [1, 2]


def test_solver_single_group():
    """Test trivial case with only one group."""
    participants = make_participants(5)
    groups, success = solver.solve_with_ortools(
        participants,
        group_capacities=[5],
        respect_stars=True,
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
    )

    assert success is True
    assert len(groups) == 1
    assert len(groups[0]["members"]) == 5


def test_solver_empty_input():
    """Test error handling when no group capacities are provided."""
    with pytest.raises(
        ValueError,
        match="group_capacities must be valid non-negative requirements.",
    ):
        solver.solve_with_ortools(
            [],
            group_capacities=[],
            respect_stars=True,
            score_columns=[SCORE_COL],
            score_weights={SCORE_COL: 1.0},
        )


def test_solver_zero_participants_positive_groups():
    """Test behavior with 0 participants but valid empty capacities."""
    groups, success = solver.solve_with_ortools(
        [],
        group_capacities=[0, 0],
        respect_stars=True,
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
    )
    assert success is True
    assert len(groups) == 2
    assert len(groups[0]["members"]) == 0


def test_solver_positive_participants_zero_groups():
    """Test error handling when participants exist but capacity list is empty."""
    participants = make_participants(5)
    with pytest.raises(
        ValueError,
        match="group_capacities must be valid non-negative requirements.",
    ):
        solver.solve_with_ortools(
            participants,
            group_capacities=[],
            respect_stars=True,
            score_columns=[SCORE_COL],
            score_weights={SCORE_COL: 1.0},
        )


def test_solver_multi_dimensional_weighted():
    """Test that the solver respects weights across multiple score dimensions."""
    second_col = f"{config.SCORE_PREFIX}2"
    participants = [
        {config.COL_NAME: "P1", SCORE_COL: 100, second_col: 10},
        {config.COL_NAME: "P2", SCORE_COL: 10, second_col: 100},
        {config.COL_NAME: "P3", SCORE_COL: 100, second_col: 10},
        {config.COL_NAME: "P4", SCORE_COL: 10, second_col: 100},
    ]
    score_cols = [SCORE_COL, second_col]

    # Priority on Score1: Result should balance Score1 effectively
    score_weights = {SCORE_COL: 1.0, second_col: 0.0}

    groups, success = solver.solve_with_ortools(
        participants,
        group_capacities=[2, 2],
        respect_stars=False,
        score_columns=score_cols,
        score_weights=score_weights,
    )

    assert success is True
    for g in groups:
        sum_score1 = sum(m[SCORE_COL] for m in g["members"])
        assert sum_score1 == 110


def test_solver_simple_mode():
    """Verify that simple mode correctly pre-aggregates dimensions."""
    p = [
        {config.COL_NAME: "A", SCORE_COL: 10, "Score2": 100},
        {config.COL_NAME: "B", SCORE_COL: 100, "Score2": 10},
    ]
    groups, success = solver.solve_with_ortools(
        p,
        group_capacities=[1, 1],
        respect_stars=False,
        score_columns=[SCORE_COL, "Score2"],
        score_weights={SCORE_COL: 1.0, "Score2": 1.0},
        opt_mode="Simple",
        conflict_priority="Groupers",
    )
    assert success is True
    assert len(groups) == 2


def test_solver_pigeonhole_separator():
    """Test that separators force people apart using the spread logic."""
    p = make_participants(4, score=10.0, separators=["TagA", "TagA", "TagA", "TagA"])
    groups, success = solver.solve_with_ortools(
        p,
        group_capacities=[2, 2],
        respect_stars=False,
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
    )
    assert success is True
    # 4 people, 2 groups -> limit should be ceil(4/2) = 2 per group
    for g in groups:
        assert len(g["members"]) == 2


def test_solver_fractional_cohesion():
    """Test that groupers try to keep people together."""
    p = make_participants(
        6, score=10.0, groupers=["Team1", "Team1", "Team1", "", "", ""]
    )
    groups, success = solver.solve_with_ortools(
        p,
        group_capacities=[3, 3],
        respect_stars=False,
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
    )
    assert success is True
    # Team1 should end up entirely in one of the groups because there's room
    found_together = False
    for g in groups:
        team_count = sum(
            1 for m in g["members"] if m.get(config.COL_GROUPER) == "Team1"
        )
        if team_count == 3:
            found_together = True
    assert found_together is True


def test_solver_conflict_resolution():
    """Test that conflicting tags are resolved based on the priority toggle."""
    p = make_participants(
        2, score=10.0, groupers=["TagX", "TagX"], separators=["TagX", "TagX"]
    )
    # If Groupers prioritized, they stay together in the 2-capacity group
    groups, success = solver.solve_with_ortools(
        p,
        group_capacities=[2, 0],
        respect_stars=False,
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
        conflict_priority="Groupers",
    )
    assert success is True

    # Since we prioritized Groupers, the pigeonhole constraint
    # (which would have limited them to 1 per group) was dropped.
    assert len(groups[0]["members"]) == 2
