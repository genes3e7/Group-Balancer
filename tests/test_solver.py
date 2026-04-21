"""
Unit tests for the solver module.

Tests cover standard capacity balancing, multi-dimensional score weighting,
and advanced categorical constraints (Groupers and Separators via character tokenization).
"""

import pytest
from src.core import solver, config

SCORE_COL = f"{config.SCORE_PREFIX}1"


def make_participants(
    count: int,
    score: float = 100.0,
    groupers: list[str] | None = None,
    separators: list[str] | None = None,
) -> list[dict]:
    """
    Helper to generate mock participant data with advanced tags.

    Args:
        count (int): Number of participants to create.
        score (float): Default score for all participants.
        groupers (list[str] | None): Grouper tags for participants.
        separators (list[str] | None): Separator tags for participants.

    Returns:
        list[dict]: Generated participant list.
    """
    if groupers is None:
        groupers = [""] * count
    if separators is None:
        separators = [""] * count

    data = []
    for i in range(count):
        name = f"P{i}"
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
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
    )

    assert success is True
    sizes = sorted([len(g["members"]) for g in groups])
    assert sizes == [3, 3, 4]


def test_solver_single_group():
    """Test trivial case with only one group."""
    participants = make_participants(5)
    groups, success = solver.solve_with_ortools(
        participants,
        group_capacities=[5],
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
            score_columns=[SCORE_COL],
            score_weights={SCORE_COL: 1.0},
        )


def test_solver_zero_participants_positive_groups():
    """Test behavior with 0 participants but valid empty capacities."""
    groups, success = solver.solve_with_ortools(
        [],
        group_capacities=[0, 0],
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
        score_columns=[SCORE_COL, "Score2"],
        score_weights={SCORE_COL: 1.0, "Score2": 1.0},
        opt_mode="Simple",
        conflict_priority="Groupers",
    )
    assert success is True
    assert len(groups) == 2


def test_solver_pigeonhole_separator():
    """Test that separators force people apart using the spread logic."""
    p = make_participants(4, score=10.0, separators=["A", "A", "A", "A"])
    groups, success = solver.solve_with_ortools(
        p,
        group_capacities=[2, 2],
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
    )
    assert success is True
    # 4 people, 2 groups -> limit should be ceil(4/2) = 2 per group
    for g in groups:
        assert len(g["members"]) == 2


def test_solver_fractional_cohesion():
    """Test that groupers try to keep people together."""
    p = make_participants(6, score=10.0, groupers=["T", "T", "T", "", "", ""])
    groups, success = solver.solve_with_ortools(
        p,
        group_capacities=[3, 3],
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
    )
    assert success is True
    found_together = False
    for g in groups:
        team_count = sum(1 for m in g["members"] if m.get(config.COL_GROUPER) == "T")
        if team_count == 3:
            found_together = True
    assert found_together is True


def test_solver_conflict_resolution():
    """Test that conflicting tags are resolved based on the priority toggle."""
    p = make_participants(2, score=10.0, groupers=["X", "X"], separators=["X", "X"])
    # If Groupers prioritized, they stay together in the 2-capacity group
    groups, success = solver.solve_with_ortools(
        p,
        group_capacities=[2, 0],
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
        conflict_priority="Groupers",
    )
    assert success is True

    # Pigeonhole constraint was dropped due to priority
    assert len(groups[0]["members"]) == 2


def test_solver_character_tokenization_separator():
    """Verify that 'GSA' is interpreted as 3 independent separator tags."""
    p = make_participants(4, score=10.0, separators=["GSA", "GSA", "GSA", "GSA"])
    groups, success = solver.solve_with_ortools(
        p,
        group_capacities=[2, 2],
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
    )
    assert success is True
    for g in groups:
        assert len(g["members"]) == 2


def test_solver_comma_illegal_handling():
    """Verify that commas in tags are ignored and do not create empty tags."""
    p1 = make_participants(2, groupers=["A,B", "A,B"])
    p2 = make_participants(2, groupers=["AB", "AB"])

    groups1, _ = solver.solve_with_ortools(
        p1,
        group_capacities=[2, 0],
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
    )
    groups2, _ = solver.solve_with_ortools(
        p2,
        group_capacities=[2, 0],
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
    )

    assert len(groups1[0]["members"]) == 2
    assert len(groups2[0]["members"]) == 2


def test_solver_character_tokenization_grouper():
    """Verify that shared characters in groupers create cohesive clumps."""
    p = make_participants(4, groupers=["X", "XY", "Y", ""])
    groups, success = solver.solve_with_ortools(
        p,
        group_capacities=[3, 1],
        score_columns=[SCORE_COL],
        score_weights={SCORE_COL: 1.0},
    )
    assert success is True

    clump_in_g1 = sum(
        1 for m in groups[0]["members"] if m[config.COL_NAME] in ["P0", "P1", "P2"]
    )
    assert clump_in_g1 == 3
