"""Unit tests for statistical calculation logic."""

import numpy as np
import pandas as pd

from src.core import config
from src.utils import group_helpers


def test_calculate_balancing_stats_basic():
    """Test standard deviation of group averages (ddof=1)."""
    # 2 groups, averages 10 and 20
    groups = [
        {"id": 1, "count": 1, "averages": {"S1": 10.0}},
        {"id": 2, "count": 1, "averages": {"S1": 20.0}},
    ]
    score_cols = ["S1"]

    stats = group_helpers.calculate_balancing_stats(groups, score_cols)

    # Expected: avg(10, 20) = 15.0
    # Expected std: sqrt(((10-15)**2 + (20-15)**2) / (2-1)) = sqrt(50) ≈ 7.0711
    assert stats[0]["Global Avg"] == 15.0
    assert np.isclose(
        stats[0]["Avg Std Dev (Balance)"], pd.Series([10.0, 20.0]).std(ddof=1)
    )
    assert stats[0]["Avg Std Dev (Balance)"] > 7.07


def test_calculate_balancing_stats_exclude_unassigned():
    """Test that Group -1 is ignored in statistical calculations."""
    groups = [
        {"id": 1, "count": 2, "averages": {"S1": 10.0}},
        {"id": 2, "count": 2, "averages": {"S1": 20.0}},
        {"id": -1, "count": 50, "averages": {"S1": 1000.0}},  # Should be ignored
    ]
    score_cols = ["S1"]

    stats = group_helpers.calculate_balancing_stats(groups, score_cols)

    # If Group -1 is ignored:
    # Weighted Global Avg = (10*2 + 20*2) / (2+2) = 60/4 = 15.0
    # Std Dev of [10, 20] ≈ 7.0711
    assert stats[0]["Global Avg"] == 15.0
    assert (
        stats[0]["Avg Std Dev (Balance)"] < 10.0
    )  # Definitely didn't include the 1000.0


def test_statistical_parity_between_ui_paths():
    """Ensure helper matches manual pandas aggregation results."""
    df = pd.DataFrame(
        {
            config.COL_GROUP: [1, 1, 2, 2],
            "S1": [10.0, 10.0, 20.0, 20.0],
            config.COL_NAME: ["A", "B", "C", "D"],
        }
    )
    score_cols = ["S1"]

    # Path 1: Group Helpers (KPI Path)
    groups = group_helpers.aggregate_groups(
        df, config.COL_GROUP, score_cols, config.COL_NAME
    )
    stats_helper = group_helpers.calculate_balancing_stats(groups, score_cols)

    # Path 2: Manual Pandas GroupBy (Live Stats Path)
    gdf = df.groupby(config.COL_GROUP)["S1"].mean()
    stats_pandas = gdf.std(ddof=1)

    assert np.isclose(stats_helper[0]["Avg Std Dev (Balance)"], stats_pandas)
