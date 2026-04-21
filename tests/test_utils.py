"""Unit tests for the utility helpers."""

import pandas as pd

from src.core import config
from src.utils import group_helpers


def test_aggregate_groups_empty():
    """Test that empty or None DataFrames return empty list."""
    assert group_helpers.aggregate_groups(None, "Group", [], "Name") == []
    assert group_helpers.aggregate_groups(pd.DataFrame(), "Group", [], "Name") == []


def test_aggregate_groups_missing_column():
    """Test behavior when the group column is missing."""
    df = pd.DataFrame({"Name": ["Alice"], "Score": [10]})
    assert group_helpers.aggregate_groups(df, "Wrong", ["Score"], "Name") == []


def test_aggregate_groups_valid():
    """Test standard aggregation."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A", "B", "C"],
            config.COL_GROUP: [1, 1, 2],
            "Score1": [10, 20, 30],
        },
    )
    groups = group_helpers.aggregate_groups(
        df,
        config.COL_GROUP,
        ["Score1"],
        config.COL_NAME,
    )

    assert len(groups) == 2
    assert groups[0]["id"] == 1
    assert groups[0]["count"] == 2
    assert groups[0]["averages"]["Score1"] == 15.0
    assert groups[0]["sums"]["Score1"] == 30.0

    assert groups[1]["id"] == 2
    assert groups[1]["count"] == 1
    assert groups[1]["averages"]["Score1"] == 30.0


def test_aggregate_groups_invalid_score_types():
    """Test that non-numeric scores are handled."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A", "B"],
            config.COL_GROUP: [1, 1],
            "Score1": ["invalid", 10],
        },
    )
    groups = group_helpers.aggregate_groups(
        df,
        config.COL_GROUP,
        ["Score1"],
        config.COL_NAME,
    )
    # "invalid" becomes 0.0, so sum is 10.0, avg is 5.0
    assert groups[0]["averages"]["Score1"] == 5.0
