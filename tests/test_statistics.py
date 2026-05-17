"""Unit tests for the balancing statistics module."""

import pandas as pd
import pytest

from src.utils import group_helpers

# Expected Values for Verification
WANT_GLOBAL_AVG = 15.0
WANT_COUNT_2 = 2


def test_calculate_balancing_stats_basic() -> None:
    """Verify statistics for a simple 2-group balanced case."""
    score_cols = ["Score1"]
    groups = [
        {"id": 1, "averages": {"Score1": 10.0}, "count": WANT_COUNT_2},
        {"id": 2, "averages": {"Score1": 20.0}, "count": WANT_COUNT_2},
    ]

    stats = group_helpers.calculate_balancing_stats(groups, score_cols)

    assert len(stats) == 1
    assert stats[0]["Score Dimension"] == "Score1"
    # Result should be avg(10, 20) = 15.0
    # Standard deviation: sqrt(((10-15)**2 + (20-15)**2) / (2-1)) = sqrt(50)
    assert stats[0]["Global Avg"] == WANT_GLOBAL_AVG
    assert stats[0]["Avg Std Dev (Balance)"] == pytest.approx(
        pd.Series([10.0, 20.0]).std(ddof=1)
    )


def test_calculate_balancing_stats_exclude_unassigned() -> None:
    """Verify that group ID -1 is excluded from statistical calculations."""
    score_cols = ["Score1"]
    groups = [
        {"id": 1, "averages": {"Score1": 10.0}, "count": WANT_COUNT_2},
        {"id": 2, "averages": {"Score1": 20.0}, "count": WANT_COUNT_2},
        {"id": -1, "averages": {"Score1": 100.0}, "count": 1},  # Should be ignored
    ]

    stats = group_helpers.calculate_balancing_stats(groups, score_cols)

    # Weighted Global Avg = (10*2 + 20*2) / (2+2) = 60/4 = 15.0
    # Std Dev of [10, 20] should match
    assert stats[0]["Global Avg"] == WANT_GLOBAL_AVG
    expected_std = pd.Series([10.0, 20.0]).std(ddof=1)
    assert stats[0]["Avg Std Dev (Balance)"] == pytest.approx(expected_std)


def test_statistical_parity_between_ui_paths() -> None:
    """Verify that sample std dev (ddof=1) matches pandas default."""
    data = [10.0, 20.0, 30.0]
    series = pd.Series(data)

    score_cols = ["S"]
    groups = [
        {"id": i, "averages": {"S": val}, "count": 1} for i, val in enumerate(data)
    ]

    stats = group_helpers.calculate_balancing_stats(groups, score_cols)
    assert stats[0]["Avg Std Dev (Balance)"] == pytest.approx(series.std(ddof=1))
