"""Functional tests to verify absolute solver determinism and balancing quality."""

import pandas as pd
import pytest
from src.core import config
from src.core.models import ConflictPriority, OptimizationMode
from src.core.services import OptimizationService

@pytest.fixture
def sample_data():
    """15 participants, 2 groups, with identical scores to test symmetry."""
    data = {
        config.COL_NAME: [f"Person {i}" for i in range(15)],
        "Score1": [10, 10, 10, 20, 20, 20, 30, 30, 30, 40, 40, 40, 50, 50, 50],
        "Score2": [10, 10, 10, 20, 20, 20, 30, 30, 30, 40, 40, 40, 50, 50, 50],
        config.COL_GROUPER: [""] * 15,
        config.COL_SEPARATOR: [""] * 15,
    }
    return pd.DataFrame(data)

def test_cold_start_determinism(sample_data):
    """Verifies that multiple cold starts yield identical assignments.

    Ensures that for a fixed random seed and single search worker, the CP-SAT
    solver reaches the exact same solution across independent runs.

    Args:
        sample_data: Fixture providing a DataFrame of participants with
            identical Score1 and Score2 values to test symmetry.
    """
    group_capacities = [8, 7]
    score_weights = {"Score1": 1.0, "Score2": 1.0}
    
    res1, metrics1 = OptimizationService.run(
        sample_data, group_capacities, score_weights,
        OptimizationMode.ADVANCED, ConflictPriority.GROUPERS, 10
    )
    assert metrics1["status"] == "OPTIMAL"
    
    res2, metrics2 = OptimizationService.run(
        sample_data, group_capacities, score_weights,
        OptimizationMode.ADVANCED, ConflictPriority.GROUPERS, 10
    )
    assert metrics2["status"] == "OPTIMAL"
    
    # Assert identical assignments
    try:
        pd.testing.assert_series_equal(res1[config.COL_GROUP], res2[config.COL_GROUP])
    except AssertionError:
        print("\nDIAGNOSTIC: Cold starts yielded different assignments!")
        print(f"Assignments 1: {res1[config.COL_GROUP].tolist()}")
        print(f"Assignments 2: {res2[config.COL_GROUP].tolist()}")
        raise


def test_weight_toggle_determinism(sample_data):
    """Verifies that toggling weights back and forth yields the same result.

    Replicates a common user workflow where weights are changed and then
    restored (1:0 -> 0:1 -> 1:0). It ensures that warm-start metadata
    restoration prevents solution drift and ensures identical optima.

    Args:
        sample_data: Fixture providing a DataFrame of participants.
    """
    group_capacities = [8, 7]
    
    res_a, _ = OptimizationService.run(
        sample_data, group_capacities, {"Score1": 1.0, "Score2": 0.0},
        OptimizationMode.ADVANCED, ConflictPriority.GROUPERS, 10
    )
    
    res_b, _ = OptimizationService.run(
        sample_data, group_capacities, {"Score1": 0.0, "Score2": 1.0},
        OptimizationMode.ADVANCED, ConflictPriority.GROUPERS, 10,
        previous_results=res_a
    )
    
    res_c, _ = OptimizationService.run(
        sample_data, group_capacities, {"Score1": 1.0, "Score2": 0.0},
        OptimizationMode.ADVANCED, ConflictPriority.GROUPERS, 10,
        previous_results=res_b
    )
    
    pd.testing.assert_series_equal(res_a[config.COL_GROUP], res_c[config.COL_GROUP])


def test_balancing_quality_magnitude_insensitive():
    """Verifies that small-magnitude scores are balanced correctly.

    Tests the fairness of multi-dimensional balancing when raw numeric ranges
    differ significantly (e.g., Score1: 10..50, Score2: 0.1..0.5). It ensures
    that user weights are the primary driver of priority, not raw magnitude.
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
        df, group_capacities, {"Score1": 0.0, "Score2": 1.0},
        OptimizationMode.ADVANCED, ConflictPriority.GROUPERS, 10
    )
    assert metrics["status"] == "OPTIMAL"
    
    group_avgs = res.groupby(config.COL_GROUP)["Score2"].mean()
    assert group_avgs.std(ddof=1) == 0.0
