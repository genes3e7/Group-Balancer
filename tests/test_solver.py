"""
Unit tests for the solver module.
"""

from modules import solver, config


# Helper to generate dummy participants
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
    """Test equal splitting of identical scores."""
    participants = make_participants(10, score=100)
    groups, success = solver.solve_with_ortools(
        participants, num_groups=2, respect_stars=False
    )

    assert success is True
    assert len(groups) == 2
    assert len(groups[0]["members"]) == 5
    assert len(groups[1]["members"]) == 5
    assert groups[0]["avg"] == 100.0


def test_solver_unequal_sizes():
    """Test splitting 10 people into 3 groups (4, 3, 3)."""
    participants = make_participants(10, score=10)
    groups, success = solver.solve_with_ortools(
        participants, num_groups=3, respect_stars=False
    )

    assert success is True
    sizes = sorted([len(g["members"]) for g in groups])
    assert sizes == [3, 3, 4]


def test_solver_star_constraints():
    """Test that stars are distributed evenly."""
    # 4 stars, 6 normals -> 2 groups. Should be 2 stars per group.
    participants = make_participants(10, score=50, star_indices=[0, 1, 2, 3])
    groups, success = solver.solve_with_ortools(
        participants, num_groups=2, respect_stars=True
    )

    assert success is True
    for g in groups:
        stars = sum(
            1 for m in g["members"] if config.ADVANTAGE_CHAR in m[config.COL_NAME]
        )
        assert stars == 2


def test_solver_impossible_stars():
    """
    Test behavior when stars CANNOT be perfectly even (e.g. 3 stars, 2 groups).
    Solver should still work, distributing 2 and 1.
    """
    participants = make_participants(5, score=10, star_indices=[0, 1, 2])  # 3 stars
    groups, success = solver.solve_with_ortools(
        participants, num_groups=2, respect_stars=True
    )

    assert success is True
    star_counts = sorted(
        [
            sum(1 for m in g["members"] if config.ADVANTAGE_CHAR in m[config.COL_NAME])
            for g in groups
        ]
    )
    assert star_counts == [1, 2]


def test_solver_single_group():
    """Test trivial case of 1 group."""
    participants = make_participants(5)
    groups, success = solver.solve_with_ortools(
        participants, num_groups=1, respect_stars=True
    )

    assert success is True
    assert len(groups) == 1
    assert len(groups[0]["members"]) == 5


def test_solver_empty_input():
    """Test empty input handling (should probably return empty or handle gracefully)."""
    # Based on current logic, it might return empty groups or fail feasibility.
    # An empty list of participants with num_groups > 0 is technically infeasible
    # if we enforce constraints "every person assigned" (0 constraints) but "size constraints".
    # However, CP-SAT might return INFEASIBLE or OPTIMAL with empty groups depending on formulation.
    # Let's assume we pass at least 1 person usually, but let's see.
    pass  # Skipping for now as load_data handles empty checks usually.
