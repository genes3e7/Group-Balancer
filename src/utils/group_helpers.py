"""Helper utilities for group data aggregation.

This module provides shared logic for processing dataframe results into
structured group dictionaries used by the UI and Exporter across multiple dimensions.
"""

from dataclasses import dataclass
from typing import Any, TypedDict

import pandas as pd


class GroupMetadata(TypedDict):
    """Strongly-typed metadata for an optimized group."""

    id: int
    members: list[dict[str, Any]]
    count: int
    averages: dict[str, float]
    sums: dict[str, float]


@dataclass(frozen=True)
class GroupingConfig:
    """Configuration for group aggregation."""

    col_group: str
    score_cols: list[str]
    _col_name: str


def aggregate_groups(
    df: pd.DataFrame,
    cfg: GroupingConfig,
) -> list[GroupMetadata]:
    """Aggregates a DataFrame of results into a list of group metadata dictionaries.

    Args:
        df (pd.DataFrame): The DataFrame containing group assignments.
        cfg (GroupingConfig): Configuration for aggregation.

    Returns:
        list[GroupMetadata]: A list of group metadata objects.

    Raises:
        KeyError: If required columns are missing from the DataFrame.
    """
    groups: list[GroupMetadata] = []
    if df is None or df.empty:
        return groups

    if cfg.col_group not in df.columns:
        msg = f"Column '{cfg.col_group}' missing from results."
        raise KeyError(msg)

    unique_groups = sorted(df[cfg.col_group].unique())

    for g_id in unique_groups:
        group_df = df[df[cfg.col_group] == g_id].copy()
        if "_original_index" not in group_df.columns:
            group_df["_original_index"] = group_df.index
        members = group_df.to_dict("records")
        count = len(members)
        averages = {}
        sums = {}

        for col in cfg.score_cols:
            if col not in group_df.columns:
                msg = f"Score column '{col}' missing from results."
                raise KeyError(msg)

            col_scores = []
            for m in members:
                try:
                    col_scores.append(float(m.get(col, 0.0)))
                except (ValueError, TypeError):
                    col_scores.append(0.0)

            dim_sum = sum(col_scores)
            sums[col] = dim_sum
            averages[col] = dim_sum / count if count > 0 else 0.0

        groups.append(
            {
                "id": g_id,
                "members": members,
                "count": count,
                "averages": averages,
                "sums": sums,
            },
        )

    return groups


def calculate_balancing_stats(
    groups: list[GroupMetadata], score_cols: list[str]
) -> list[dict[str, Any]]:
    """Calculates global averages and standard deviations of group averages.

    Args:
        groups (list[GroupMetadata]): List of group metadata from aggregate_groups.
        score_cols (list[str]): List of score dimensions to process.

    Returns:
        list[dict[str, Any]]: List of dictionaries containing 'Score Dimension',
            'Global Avg', and 'Avg Std Dev (Balance)'.
    """  # Exclude unassigned participants (Group -1) from balancing metrics
    valid_groups = [g for g in groups if g["id"] != -1]

    stats_data = []
    total_p = sum(g["count"] for g in valid_groups)

    for col in score_cols:
        group_avgs = [g["averages"].get(col, 0.0) for g in valid_groups]
        series = pd.Series(group_avgs)

        # Participant-weighted global average
        group_contribs = [
            g["averages"].get(col, 0.0) * g["count"] for g in valid_groups
        ]
        weighted_avg = sum(group_contribs) / total_p if total_p > 0 else 0.0

        # Standard deviation of the group averages (Sample Std Dev, ddof=1)
        # This measures how balanced the groups are relative to each other.
        std_dev = float(series.std(ddof=1)) if len(group_avgs) > 1 else 0.0

        stats_data.append(
            {
                "Score Dimension": col,
                "Global Avg": weighted_avg,
                "Avg Std Dev (Balance)": std_dev,
            }
        )

    return stats_data
