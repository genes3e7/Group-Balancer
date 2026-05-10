"""Functional tests to verify solver determinism and balancing quality.

Ensures that the CP-SAT solver provides consistent balancing quality
across independent runs and correctly handles balancing regardless of
score magnitude.
"""

import pandas as pd
import pytest

from src.core import config
from src.core.models import ConflictPriority
from src.core.services import OptimizationService


@pytest.fixture
def sample_data():
    """Provides a dataset of 16 participants for symmetry testing.

    Score2 is explicitly different from Score1 to verify weight invalidation.

    Returns:
        pd.DataFrame: Symmetric participant data.
    """
    data = {
        config.COL_NAME: [f"Person {i}" for i in range(16)],
        "Score1": [10, 10, 10, 10, 20, 20, 20, 20, 30, 30, 30, 30, 40, 40, 40, 40],
        "Score2": [40, 40, 30, 30, 20, 20, 10, 10, 40, 40, 30, 30, 20, 20, 10, 10],
        config.COL_GROUPER: [""] * 16,
        config.COL_SEPARATOR: [""] * 16,
    }
    return pd.DataFrame(data)


def test_cold_start_determinism(sample_data):
    """Verifies that multiple independent runs yield identical quality.

    Note: In Race Mode (interleave_search=False), bit-for-bit assignment
    identity is not guaranteed if multiple symmetric optima exist, but
    balancing quality (Standard Deviation) must remain identical.

    Args:
        sample_data (pd.DataFrame): Fixture providing participant data.
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

    for col in ["Score1", "Score2"]:
        std1 = res1.groupby(config.COL_GROUP)[col].mean().std(ddof=1)
        std2 = res2.groupby(config.COL_GROUP)[col].mean().std(ddof=1)
        assert abs(std1 - std2) < 1e-9


def test_warm_start_determinism(sample_data):
    """Verifies that iterative solving is stable across runs with hints.

    Args:
        sample_data (pd.DataFrame): Fixture providing participant data.
    """
    group_capacities = [8, 8]
    weights = {"Score1": 0.0, "Score2": 1.0}

    res_a, _ = OptimizationService.run(
        sample_data,
        group_capacities,
        {"Score1": 1.0, "Score2": 0.0},
        ConflictPriority.GROUPERS,
        10,
    )

    # Initial target solve
    res_b, _ = OptimizationService.run(
        sample_data,
        group_capacities,
        weights,
        ConflictPriority.GROUPERS,
        10,
        previous_results=res_a,
    )

    # Re-solve with same weights to verify hint stability
    res_c, _ = OptimizationService.run(
        sample_data,
        group_capacities,
        weights,
        ConflictPriority.GROUPERS,
        10,
        previous_results=res_b,
    )

    for col in ["Score1", "Score2"]:
        std_b = res_b.groupby(config.COL_GROUP)[col].mean().std(ddof=1)
        std_c = res_c.groupby(config.COL_GROUP)[col].mean().std(ddof=1)
        assert abs(std_b - std_c) < 1e-9


def test_balancing_quality_magnitude_insensitive():
    """Verifies balancing quality is driven by weights, not score magnitude."""
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
