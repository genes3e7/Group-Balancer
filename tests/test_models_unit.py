"""Unit tests for data models validation."""

import pytest

from src.core.models import (
    Participant,
    SolverConfig,
)


def test_participant_name_sanitization():
    """Test that name is coerced to string."""
    p = Participant(name=123, scores={})
    assert p.name == "123"


def test_solver_config_invalid_num_groups():
    """Test validator for num_groups."""
    with pytest.raises(ValueError, match="Number of groups must be positive"):
        SolverConfig(num_groups=0, group_capacities=[], score_weights={})


def test_solver_config_invalid_total_capacity():
    """Test validator for total capacity."""
    with pytest.raises(ValueError, match="Total capacity must be positive"):
        SolverConfig(num_groups=1, group_capacities=[0], score_weights={})


def test_solver_config_mismatched_capacities_length():
    """Test validator for capacity list length."""
    with pytest.raises(
        ValueError,
        match="Group capacities list length must match num_groups",
    ):
        SolverConfig(num_groups=2, group_capacities=[1], score_weights={})


def test_solver_config_negative_capacities():
    """Test validator for negative capacities."""
    # sum([-1, 2]) = 1 > 0, so total capacity check passes, triggers negative check
    with pytest.raises(ValueError, match="Group capacities cannot be negative"):
        SolverConfig(num_groups=2, group_capacities=[-1, 2], score_weights={})
