"""Functional tests to verify absolute solver determinism and balancing quality."""

import pandas as pd
import pytest

from src.core import config
from src.core.models import ConflictPriority
from src.core.services import OptimizationService


@pytest.fixture
def sample_data():
    """16 participants, 2 groups, with identical scores to test symmetry.

    Returns:
        pd.DataFrame: Sample participant data.
    """
    data = {
        config.COL_NAME: [f"Person {i}" for i in range(16)],
        "Score1": [10, 10, 10, 10, 20, 20, 20, 20, 30, 30, 30, 30, 40, 40, 40, 40],
        "Score2": [10, 10, 10, 10, 20, 20, 20, 20, 30, 30, 30, 30, 40, 40, 40, 40],
        config.COL_GROUPER: [""] * 16,
        config.COL_SEPARATOR: [""] * 16,
    }
    return pd.DataFrame(data)


def test_cold_start_determinism(sample_data):
    """Verifies that multiple cold starts yield identical assignments.

    Ensures that for a fixed random seed and single search worker, the CP-SAT
    solver reaches the exact same solution across independent runs.

    Args:
        sample_data (pd.DataFrame): Fixture providing symmetric participant data.
    """
    group_capacities = [8, 8]
    score_weights = {"Score1": 1.0, "Score2": 1.0}

    res1, metrics1 = OptimizationService.run(
        sample_data,
        group_capacities,
        score_weights,
        ConflictPriority.GROUPERS,
        10,
    )
    assert metrics1["status"] == "OPTIMAL"

    res2, metrics2 = OptimizationService.run(
        sample_data,
        group_capacities,
        score_weights,
        ConflictPriority.GROUPERS,
        10,
    )
    assert metrics2["status"] == "OPTIMAL"

    # Assert identical group assignment per participant
    pd.testing.assert_series_equal(res1[config.COL_GROUP], res2[config.COL_GROUP])


def test_weight_toggle_determinism(sample_data):
    """Verifies that toggling weights back and forth yields the same result.

    Ensures that warm-start metadata restoration prevents solution drift.

    Args:
        sample_data (pd.DataFrame): Fixture providing participant data.
    """
    group_capacities = [8, 8]

    res_a, _ = OptimizationService.run(
        sample_data,
        group_capacities,
        {"Score1": 1.0, "Score2": 0.0},
        ConflictPriority.GROUPERS,
        10,
    )

    res_b, _ = OptimizationService.run(
        sample_data,
        group_capacities,
        {"Score1": 0.0, "Score2": 1.0},
        ConflictPriority.GROUPERS,
        10,
        previous_results=res_a,
    )

    res_c, _ = OptimizationService.run(
        sample_data,
        group_capacities,
        {"Score1": 1.0, "Score2": 0.0},
        ConflictPriority.GROUPERS,
        10,
        previous_results=res_b,
    )

    pd.testing.assert_series_equal(res_a[config.COL_GROUP], res_c[config.COL_GROUP])


def test_balancing_quality_magnitude_insensitive():
    """Verifies that small-magnitude scores are balanced correctly.

    Ensures that user weights are the primary driver of priority, not raw magnitude.
    """
    data = {
        config.COL_NAME: [f"P{i}" for i in range(4)],
        "Score1": [10, 10, 50, 50],
        "Score2": [0.1, 0.5, 0.1, 0.5],
        config.COL_GROUPER: [""] * 4,
        config.COL_SEPARATOR: [""] * 4,
    }
    df = pd.DataFrame(data)
    group_capacities = [2, 2]

    res, metrics = OptimizationService.run(
        df,
        group_capacities,
        {"Score1": 0.0, "Score2": 1.0},
        ConflictPriority.GROUPERS,
        10,
    )
    assert metrics["status"] == "OPTIMAL"

    group_avgs = res.groupby(config.COL_GROUP)["Score2"].mean()
    assert group_avgs.std(ddof=1) == 0.0
