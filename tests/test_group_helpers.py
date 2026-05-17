"""Unit tests for group helper utilities and statistics."""

import pandas as pd
import pytest

from src.core import config
from src.utils import group_helpers

# Expected Values for Verification
WANT_LEN_2 = 2
WANT_ID_1 = 1
WANT_COUNT_2 = 2
WANT_AVG_15 = 15.0
WANT_SUM_30 = 30.0
WANT_ID_2 = 2
WANT_COUNT_1 = 1
WANT_AVG_30 = 30.0
WANT_SUM_30_ID2 = 30.0
WANT_AVG_5 = 5.0


def test_aggregate_groups_empty() -> None:
    """Verify that aggregate_groups handles empty DataFrames gracefully."""
    cfg = group_helpers.GroupingConfig("G", [], "N")
    assert group_helpers.aggregate_groups(pd.DataFrame(), cfg) == []
    assert group_helpers.aggregate_groups(None, cfg) == []


def test_aggregate_groups_missing_column() -> None:
    """Verify that aggregate_groups raises KeyError on missing columns."""
    df = pd.DataFrame({"X": [1]})
    cfg = group_helpers.GroupingConfig("Group", ["S1"], "Name")
    with pytest.raises(KeyError):
        group_helpers.aggregate_groups(df, cfg)


def test_aggregate_groups_valid() -> None:
    """Verify standard aggregation of participants into groups."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A", "B", "C"],
            config.COL_GROUP: [1, 1, 2],
            "Score1": [10.0, 20.0, 30.0],
        }
    )

    cfg = group_helpers.GroupingConfig(config.COL_GROUP, ["Score1"], config.COL_NAME)
    groups = group_helpers.aggregate_groups(df, cfg)

    assert len(groups) == WANT_LEN_2
    assert groups[0]["id"] == WANT_ID_1
    assert groups[0]["count"] == WANT_COUNT_2
    assert groups[0]["averages"]["Score1"] == WANT_AVG_15
    assert groups[0]["sums"]["Score1"] == WANT_SUM_30

    assert groups[1]["id"] == WANT_ID_2
    assert groups[1]["count"] == WANT_COUNT_1
    assert groups[1]["averages"]["Score1"] == WANT_AVG_30
    assert groups[1]["sums"]["Score1"] == WANT_SUM_30_ID2


def test_aggregate_groups_invalid_score_types() -> None:
    """Verify that non-numeric score dimensions are coerced to 0.0."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A", "B"],
            config.COL_GROUP: [1, 1],
            "Score1": [10.0, "invalid"],
        }
    )

    cfg = group_helpers.GroupingConfig(config.COL_GROUP, ["Score1"], config.COL_NAME)
    groups = group_helpers.aggregate_groups(df, cfg)
    # "invalid" becomes 0.0, so sum is 10.0, avg is 5.0
    assert groups[0]["averages"]["Score1"] == WANT_AVG_5


def test_calculate_balancing_stats_basic() -> None:
    """Verify standard calculation of group standard deviation."""
    groups = [
        {"id": 1, "averages": {"S1": 10.0}, "count": 1},
        {"id": 2, "averages": {"S1": 20.0}, "count": 1},
    ]
    # mean of [10, 20] is 15. std dev with ddof=1 is sqrt((25 + 25) / 1) = sqrt(50) = 7.071
    stats = group_helpers.calculate_balancing_stats(groups, ["S1"])
    assert stats[0]["Score Dimension"] == "S1"
    assert round(stats[0]["Avg Std Dev (Balance)"], 3) == 7.071


def test_calculate_balancing_stats_exclude_unassigned() -> None:
    """Verify that unassigned participants (Group -1) are excluded from stats."""
    groups = [
        {"id": 1, "averages": {"S1": 10.0}, "count": 1},
        {"id": -1, "averages": {"S1": 100.0}, "count": 1},
    ]
    stats = group_helpers.calculate_balancing_stats(groups, ["S1"])
    # std dev of one group is 0.0 per group_helpers.py:125
    assert stats[0]["Avg Std Dev (Balance)"] == 0.0


def test_statistical_parity_between_ui_paths() -> None:
    """Verify consistency between group averages and calculate_balancing_stats."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["P1", "P2", "P3", "P4"],
            config.COL_GROUP: [1, 1, 2, 2],
            "Score1": [10, 30, 20, 20],
        }
    )
    cfg = group_helpers.GroupingConfig(config.COL_GROUP, ["Score1"], config.COL_NAME)
    groups = group_helpers.aggregate_groups(df, cfg)

    # G1 avg: 20, G2 avg: 20. Std dev: 0.0
    stats = group_helpers.calculate_balancing_stats(groups, ["Score1"])
    assert stats[0]["Avg Std Dev (Balance)"] == 0.0
