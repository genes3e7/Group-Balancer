import pytest
from modules import solver, config

def test_solver_basic_split():
    """
    Test that the solver correctly splits participants into equal groups.
    """
    # Setup: 10 people with identical scores
    participants = [{'Name': f'P{i}', 'Score': 100} for i in range(10)]
    n_groups = 2
    
    groups, success = solver.solve_with_ortools(participants, n_groups, respect_stars=False)
    
    assert success is True
    assert len(groups) == 2
    assert len(groups[0]['members']) == 5
    assert len(groups[1]['members']) == 5
    assert groups[0]['avg'] == 100.0

def test_solver_unequal_groups():
    """
    Test 10 people into 3 groups (4, 3, 3).
    """
    participants = [{'Name': f'P{i}', 'Score': 10} for i in range(10)]
    n_groups = 3
    
    groups, success = solver.solve_with_ortools(participants, n_groups, respect_stars=False)
    
    assert success is True
    # Verify sizes: one group of 4, two groups of 3
    sizes = sorted([len(g['members']) for g in groups])
    assert sizes == [3, 3, 4]

def test_solver_star_constraint():
    """
    Test that stars are distributed evenly.
    """
    # 4 Stars, 6 Normals -> Total 10. 2 Groups.
    # Each group should get 2 Stars.
    stars = [{'Name': f'Star{i}*', 'Score': 100} for i in range(4)]
    normals = [{'Name': f'Norm{i}', 'Score': 10} for i in range(6)]
    participants = stars + normals
    
    groups, success = solver.solve_with_ortools(participants, num_groups=2, respect_stars=True)
    
    assert success is True
    for g in groups:
        star_count = sum(1 for m in g['members'] if '*' in m['Name'])
        assert star_count == 2
