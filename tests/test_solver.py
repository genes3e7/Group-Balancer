"""
Unit tests for the solver module.
"""
import pytest
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
    groups, success = solver.solve_with_ortools(participants, num_groups=2, respect_stars=False)
    
    assert success is True
    assert len(groups) == 2
    assert len(groups[0]['members']) == 5
    assert len(groups[1]['members']) == 5
    assert groups[0]['avg'] == 100.0
    assert groups[1]['avg'] == 100.0

def test_solver_unequal_sizes():
    """Test splitting 10 people into 3 groups (4, 3, 3)."""
    participants = make_participants(10, score=10)
    groups, success = solver.solve_with_ortools(participants, num_groups=3, respect_stars=False)
    
    assert success is True
    sizes = sorted([len(g['members']) for g in groups])
    assert sizes == [3, 3, 4]

def test_solver_star_constraints():
    """Test that stars are distributed evenly."""
    # 4 stars, 6 normals -> 2 groups. Should be 2 stars per group.
    participants = make_participants(10, score=50, star_indices=[0, 1, 2, 3])
    groups, success = solver.solve_with_ortools(participants, num_groups=2, respect_stars=True)
    
    assert success is True
    for g in groups:
        # Use endswith to match solver logic strictly
        stars = sum(1 for m in g['members'] if str(m[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR))
        assert stars == 2

def test_solver_impossible_stars():
    """
    Test behavior when stars CANNOT be perfectly even (e.g. 3 stars, 2 groups).
    Solver should still work, distributing 2 and 1.
    """
    participants = make_participants(5, score=10, star_indices=[0, 1, 2]) # 3 stars
    groups, success = solver.solve_with_ortools(participants, num_groups=2, respect_stars=True)
    
    assert success is True
    # Use endswith to match solver logic strictly
    star_counts = sorted([sum(1 for m in g['members'] if str(m[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR)) for g in groups])
    assert star_counts == [1, 2]

def test_solver_single_group():
    """Test trivial case of 1 group."""
    participants = make_participants(5)
    groups, success = solver.solve_with_ortools(participants, num_groups=1, respect_stars=True)
    
    assert success is True
    assert len(groups) == 1
    assert len(groups[0]['members']) == 5

def test_solver_empty_input():
    """Test empty input handling."""
    # Case 1: 0 participants, 0 groups -> Should be valid (empty result)
    # Note: CP-SAT might error on 0 variables or constraints if not careful, 
    # but logically 0 people into 0 groups is empty set.
    # The solver code calculates base_size = num_people // num_groups.
    # If num_groups is 0, this raises ZeroDivisionError.
    # We should expect the solver (or wrapper) to handle this, or we catch the error.
    # Given the solver implementation, let's assume num_groups > 0 is required for the math.
    
    # Case 2: 0 participants, 1 group -> Valid, result is 1 group with 0 members
    groups, success = solver.solve_with_ortools([], num_groups=1, respect_stars=True)
    assert success is True
    assert len(groups) == 1
    assert len(groups[0]['members']) == 0
    
    # Case 3: 0 participants, 0 groups -> Expect ZeroDivisionError or similar if not guarded
    # The main script guards against n_groups < 1.
    # If we call solver directly:
    with pytest.raises(ZeroDivisionError):
        solver.solve_with_ortools([], num_groups=0, respect_stars=True)
