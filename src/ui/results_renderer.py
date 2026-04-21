"""
Visualization logic for displaying results.

This module handles the 'Card View' rendering of groups, showing detailed
statistics for each group in a grid layout across multiple score dimensions,
including categorical constraint tags.
"""

import streamlit as st
import pandas as pd
from src.core import config
from src.utils import group_helpers


def render_group_cards(df: pd.DataFrame, score_cols: list[str]) -> None:
    """
    Renders groups in a grid layout (cards).

    Args:
        df (pd.DataFrame): The DataFrame containing group assignments.
        score_cols (list[str]): The dimensions of scores to be rendered in the view.
    """
    if df is None or df.empty:
        st.warning("No groups to display.")
        return

    groups = group_helpers.aggregate_groups(
        df, config.COL_GROUP, score_cols, config.COL_NAME
    )

    for i in range(0, len(groups), 2):
        g1 = groups[i]
        g2 = groups[i + 1] if (i + 1) < len(groups) else None

        c1, c2 = st.columns(2)

        with c1:
            _render_single_card(g1, score_cols)

        with c2:
            if g2:
                _render_single_card(g2, score_cols)

        st.markdown("---")


def _render_single_card(group: dict, score_cols: list[str]) -> None:
    """
    Helper to render a single group card with metrics for all score dimensions
    and a table containing members and their constraint tags.

    Args:
        group (dict): Dictionary containing group metadata and members.
        score_cols (list[str]): List of score dimensions to show averages for.
    """
    with st.container(border=True):
        st.markdown(f"### Group {group['id']}")

        # Header metrics: Count + dynamic average for every score column provided
        num_metrics = 1 + len(score_cols)
        cols = st.columns(num_metrics)

        cols[0].metric("Count", group["count"])

        for i, col in enumerate(score_cols):
            avg_val = group["averages"].get(col, 0.0)
            cols[i + 1].metric(f"Avg {col}", f"{avg_val:.2f}")

        st.divider()

        disp_df = pd.DataFrame(group["members"])
        if not disp_df.empty:
            # Dynamically build display columns based on available data
            display_columns = [config.COL_NAME]

            # Add constraint columns if they exist in the member data
            if config.COL_GROUPER in disp_df.columns:
                display_columns.append(config.COL_GROUPER)
            if config.COL_SEPARATOR in disp_df.columns:
                display_columns.append(config.COL_SEPARATOR)

            # Append all score columns
            display_columns.extend(score_cols)

            # Ensure score columns are formatted consistently with the metrics
            col_configs = {
                col: st.column_config.NumberColumn(format="%.2f") for col in score_cols
            }

            st.dataframe(
                disp_df[display_columns],
                hide_index=True,
                width="stretch",
                column_config=col_configs,
            )
        else:
            st.caption("No members assigned.")
