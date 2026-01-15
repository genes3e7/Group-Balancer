"""
Helper utilities for group data aggregation.

This module provides shared logic for processing dataframe results into
structured group dictionaries used by the UI and Exporter.
"""

import pandas as pd
from src.core import config


def aggregate_groups(
    df: pd.DataFrame, col_group: str, col_score: str, col_name: str
) -> list[dict]:
    """
    Aggregates a DataFrame of results into a list of group metadata dictionaries.

    Args:
        df (pd.DataFrame): The DataFrame containing group assignments.
        col_group (str): Column name for Group ID.
        col_score (str): Column name for Score.
        col_name (str): Column name for Participant Name.

    Returns:
        list[dict]: A list of dictionaries, where each dict represents a group
        and contains keys: 'id', 'members', 'count', 'avg', 'stars'.
    """
    groups = []
    if df is None or df.empty:
        return groups

    unique_groups = sorted(df[col_group].unique())

    for g_id in unique_groups:
        # Convert DataFrame rows to list of dicts
        members = df[df[col_group] == g_id].to_dict("records")

        scores = []
        stars = 0

        for m in members:
            # Safely parse scores
            try:
                scores.append(float(m[col_score]))
            except (ValueError, TypeError):
                scores.append(0.0)

            # Count stars
            val = str(m[col_name])
            if val.endswith(config.ADVANTAGE_CHAR):
                stars += 1

        count = len(members)
        avg = sum(scores) / count if count > 0 else 0.0

        groups.append(
            {
                "id": g_id,
                "members": members,
                "count": count,
                "avg": avg,
                "stars": stars,
            }
        )

    return groups
