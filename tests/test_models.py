"""Unit tests for the data models module."""

import pytest

from src.core import config
from src.core.models import Participant, SolverConfig


def test_participant_name_sanitization() -> None:
    """Verify that participant names are coerced to strings."""
    p = Participant(name=123, scores={"S1": 10.0})
    assert p.name == "123"


def test_solver_config_invalid_num_groups() -> None:
    """Verify validation of group counts."""
    with pytest.raises(ValueError, match="Number of groups must be positive"):
        SolverConfig(num_groups=0, group_capacities=[], score_weights={"S1": 1.0})

    with pytest.raises(ValueError, match="Number of groups exceeds limit"):
        SolverConfig(
            num_groups=config.MAX_GROUPS + 1,
            group_capacities=[1] * (config.MAX_GROUPS + 1),
            score_weights={"S1": 1.0},
        )


def test_solver_config_invalid_total_capacity() -> None:
    """Verify validation of aggregate participant capacity."""
    with pytest.raises(ValueError, match="Total capacity must be positive"):
        SolverConfig(num_groups=1, group_capacities=[0], score_weights={"S1": 1.0})

    with pytest.raises(ValueError, match=r"Total participants .* exceeds limit"):
        SolverConfig(
            num_groups=1,
            group_capacities=[config.MAX_PARTICIPANTS + 1],
            score_weights={"S1": 1.0},
        )


def test_solver_config_mismatched_capacities_length() -> None:
    """Verify that capacities list must align with num_groups."""
    with pytest.raises(ValueError, match="length must match num_groups"):
        SolverConfig(num_groups=2, group_capacities=[1], score_weights={"S1": 1.0})


def test_solver_config_negative_capacities() -> None:
    """Verify that individual group capacities cannot be negative."""
    # When sum(group_capacities) <= 0, we get "Total capacity must be positive."
    with pytest.raises(ValueError, match="Total capacity must be positive"):
        SolverConfig(num_groups=1, group_capacities=[-1], score_weights={"S1": 1.0})

    # When sum > 0 but some are negative
    with pytest.raises(ValueError, match="Group capacities cannot be negative"):
        SolverConfig(num_groups=2, group_capacities=[2, -1], score_weights={"S1": 1.0})


def test_solver_config_validation_errors() -> None:
    """Verify validation for score weights and constraint weights."""
    # 1. No weights
    with pytest.raises(ValueError, match="At least one score weight"):
        SolverConfig(num_groups=1, group_capacities=[1], score_weights={})

    # 2. Infinite weights
    with pytest.raises(ValueError, match="must be a finite number"):
        SolverConfig(
            num_groups=1, group_capacities=[1], score_weights={"S": float("inf")}
        )

    # 3. Negative weights
    with pytest.raises(ValueError, match="cannot be negative"):
        SolverConfig(num_groups=1, group_capacities=[1], score_weights={"S": -1.0})

    # 4. Zero weights only
    with pytest.raises(ValueError, match="At least one score weight must be positive"):
        SolverConfig(num_groups=1, group_capacities=[1], score_weights={"S": 0.0})

    # 5. Non-finite constraint weights
    with pytest.raises(ValueError, match="must be a finite number"):
        SolverConfig(
            num_groups=1,
            group_capacities=[1],
            score_weights={"S": 1.0},
            grouper_weight=float("nan"),
        )

    # 6. Negative constraint weights
    with pytest.raises(ValueError, match="cannot be negative"):
        SolverConfig(
            num_groups=1,
            group_capacities=[1],
            score_weights={"S": 1.0},
            separator_weight=-1,
        )

    # 7. Out of bound constraint weights
    with pytest.raises(ValueError, match="exceeds safe limit"):
        SolverConfig(
            num_groups=1,
            group_capacities=[1],
            score_weights={"S": 1.0},
            grouper_weight=config.MAX_WEIGHT_LIMIT + 1,
        )
