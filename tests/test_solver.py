"""
Unit tests for the solver module.
"""

import pytest
from src.core import solver, config


def make_participants(count, score=100, star_indices=None):
    if star_indices is None:
        star_indices = []
    data = []
    for i in range(count):
        name = f"P{i}"
        if i in star_indices:
            name += config.ADVANTAGE_CHAR
        data.append({config.COL_NAME: name, config.COL_SCORE: score})
    return data


def test_solver_basic_split():
    participants = make_participants(10, score=100)
    groups, success = solver.solve_with_ortools(
        participants, num_groups=2, respect_stars=False
    )
    assert success is True
    assert len(groups) == 2
    assert groups[0]["avg"] == 100.0


def test_solver_empty_input():
    # Case: 0 participants, 0 groups -> Invalid
    with pytest.raises(ValueError):
        solver.solve_with_ortools([], num_groups=0, respect_stars=True)
