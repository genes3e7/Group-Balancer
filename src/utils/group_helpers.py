"""
Helper utilities for group data aggregation.

This module provides shared logic for processing dataframe results into
structured group dictionaries used by the UI and Exporter across multiple dimensions.
"""

import pandas as pd
from src.core import config


def aggregate_groups(
    df: pd.DataFrame, col_group: str, score_cols: list[str], col_name: str
) -> list[dict]:
    """
    Aggregates a DataFrame of results into a list of group metadata dictionaries.

    Args:
        df (pd.DataFrame): The DataFrame containing group assignments.
        col_group (str): Column name for Group ID.
        score_cols (list[str]): List of score dimensions to aggregate.
        col_name (str): Column name for Participant Name.

    Returns:
        list[dict]: A list of dictionaries, where each dict represents a group
        and contains keys: 'id', 'members', 'count', 'stars', 'averages', 'sums'.
    """
    groups = []
    if df is None or df.empty:
        return groups

    if col_group not in df.columns:
        return groups

    unique_groups = sorted(df[col_group].unique())

    for g_id in unique_groups:
        members = df[df[col_group] == g_id].to_dict("records")
        count = len(members)
        stars = 0
        averages = {}
        sums = {}

        for m in members:
            val = str(m[col_name])
            if val.endswith(config.ADVANTAGE_CHAR):
                stars += 1

        for col in score_cols:
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
                "stars": stars,
                "averages": averages,
                "sums": sums,
            }
        )

    return groups
