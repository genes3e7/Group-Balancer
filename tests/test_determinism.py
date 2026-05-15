"""Functional tests to verify solver determinism and balancing quality.

Ensures that the CP-SAT solver provides consistent balancing quality
across independent runs and correctly handles balancing regardless of
score magnitude. Implements dual-layer validation for both bit-for-bit
identity (Interleaved) and production quality (Race Mode).
"""

import pandas as pd
import pytest

from src.core import config
from src.core.models import ConflictPriority
from src.core.services import OptimizationService


@pytest.fixture
def sample_data() -> pd.DataFrame:
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


def test_strict_identity_determinism(sample_data: pd.DataFrame) -> None:
    """Verifies bit-for-bit identity when search interleaving is enabled.

    This Level 1 test proves the mathematical model is stable and the
    tie-breaker logic defines a unique canonical global optimum.

    Args:
        sample_data (pd.DataFrame): Fixture providing participant data.
    """
    group_capacities = [8, 8]
    score_weights = {"Score1": 1.0, "Score2": 1.0}

    # Run 1: Interleaved
    res1, metrics1 = OptimizationService.run(
        sample_data,
        group_capacities,
        score_weights,
        ConflictPriority.GROUPERS,
        10,
        interleave_search=True,
    )
    assert metrics1["status"] == "OPTIMAL"

    # Run 2: Interleaved
    res2, metrics2 = OptimizationService.run(
        sample_data,
        group_capacities,
        score_weights,
        ConflictPriority.GROUPERS,
        10,
        interleave_search=True,
    )
    assert metrics2["status"] == "OPTIMAL"

    # Canonicalize and compare exact assignments
    def canonicalize(df: pd.DataFrame) -> pd.DataFrame:
        df = df.sort_values(config.COL_NAME).reset_index(drop=True)
        # Flip group IDs so Group 1 is always the one containing 'Person 0'
        g0 = df.loc[df[config.COL_NAME] == "Person 0", config.COL_GROUP].iloc[0]
        remap = {g0: 1, (2 if g0 == 1 else 1): 2}
        df[config.COL_GROUP] = df[config.COL_GROUP].map(remap)
        return df

    pd.testing.assert_series_equal(
        canonicalize(res1)[config.COL_GROUP],
        canonicalize(res2)[config.COL_GROUP],
    )


def test_race_mode_quality_stability(sample_data: pd.DataFrame) -> None:
    """Verifies that high-speed Race Mode still yields identical balance quality.

    This Level 2 test represents the production configuration. While workers
    may 'race' and return symmetric assignments, the resulting Standard
    Deviations must remain identical.

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
        interleave_search=False,
    )

    res2, metrics2 = OptimizationService.run(
        sample_data,
        group_capacities,
        score_weights,
        ConflictPriority.GROUPERS,
        10,
        interleave_search=False,
    )

    assert metrics1["status"] == metrics2["status"] == "OPTIMAL"

    # Quality metrics (Std Dev) must match even if assignments are shuffled
    for col in ["Score1", "Score2"]:
        std1 = res1.groupby(config.COL_GROUP)[col].mean().std(ddof=1)
        std2 = res2.groupby(config.COL_GROUP)[col].mean().std(ddof=1)
        assert std1 == pytest.approx(std2, abs=1e-9)


def test_warm_start_determinism(sample_data: pd.DataFrame) -> None:
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
        assert std_b == pytest.approx(std_c, abs=1e-9)


def test_balancing_quality_magnitude_insensitive() -> None:
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
    assert group_avgs.std(ddof=1) == pytest.approx(0.0, abs=1e-9)
