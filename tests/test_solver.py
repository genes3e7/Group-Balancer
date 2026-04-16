"""
Unit tests for the solver module.
"""

import pytest
from src.core import solver, config

SCORE_COL = f"{config.SCORE_PREFIX}1"


def make_participants(count, score=100, star_indices=None):
    if star_indices is None:
        star_indices = []
    data = []
    for i in range(count):
        name = f"P{i}"
        if i in star_indices:
            name += config.ADVANTAGE_CHAR
        data.append({config.COL_NAME: name, SCORE_COL: score})
    return data


def test_solver_basic_split():
    participants = make_participants(10, score=100)
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
    """Test splitting 10 people into 3 groups (4, 3, 3)."""
    participants = make_participants(10, score=10)
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
    """Test that stars are distributed evenly."""
    # 4 stars, 6 normals -> 2 groups. Should be 2 stars per group.
    participants = make_participants(10, score=50, star_indices=[0, 1, 2, 3])
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
            if str(m[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR)
        )
        assert stars == 2


def test_solver_impossible_stars():
    """
    Test behavior when stars CANNOT be perfectly even (e.g. 3 stars, 2 groups).
    Solver should still work, distributing 2 and 1.
    """
    participants = make_participants(5, score=10, star_indices=[0, 1, 2])  # 3 stars
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
                if str(m[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR)
            )
            for g in groups
        ]
    )
    assert star_counts == [1, 2]


def test_solver_single_group():
    """Test trivial case of 1 group."""
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
    # Case: 0 participants, 0 capacities -> Invalid
    with pytest.raises(
        ValueError,
        match="group_capacities must contain at least one capacity requirement.",
    ):
        solver.solve_with_ortools(
            [],
            group_capacities=[],
            respect_stars=True,
            score_columns=[SCORE_COL],
            score_weights={SCORE_COL: 1.0},
        )


def test_solver_zero_participants_positive_groups():
    """Test behavior with 0 participants but valid capacities matching 0 sum."""
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
    """Test error when participants exist but no capacities provided."""
    participants = make_participants(5)
    with pytest.raises(
        ValueError,
        match="group_capacities must contain at least one capacity requirement.",
    ):
        solver.solve_with_ortools(
            participants,
            group_capacities=[],
            respect_stars=True,
            score_columns=[SCORE_COL],
            score_weights={SCORE_COL: 1.0},
        )
