"""Results Rendering Logic.

This module provides functions to display the final grouping results and
statistics for each group in a grid layout across multiple score dimensions,
including categorical constraint tags.
"""

import pandas as pd
import streamlit as st

from src.core import config
from src.utils import group_helpers


def render_group_cards(df: pd.DataFrame, score_cols: list[str]) -> None:
    """Renders groups in a grid layout (cards).

    Args:
        df: The DataFrame containing group assignments.
        score_cols: The dimensions of scores to be rendered in the view.
    """
    if df is None or df.empty:
        st.warning("No groups to display.")
        return

    groups = group_helpers.aggregate_groups(
        df, config.COL_GROUP, score_cols, config.COL_NAME
    )

    # Use columns for a grid-like layout
    num_cols = 2
    cols = st.columns(num_cols)

    for i, group in enumerate(groups):
        with cols[i % num_cols]:
            _render_single_card(group, score_cols)


def _render_single_card(group: dict, score_cols: list[str]) -> None:
    """Helper to render a single group card.

    Args:
        group: Dictionary containing group metadata and members.
        score_cols: List of score dimensions to show averages for.
    """
    with st.container(border=True):
        st.markdown(f"### Group {group['id']}")

        # Show key averages/sums as metrics
        m_cols = st.columns(len(score_cols))
        for j, col in enumerate(score_cols):
            with m_cols[j]:
                avg = group["averages"].get(col, 0)
                st.metric(label=f"Avg {col}", value=f"{avg:.2f}")

        st.markdown("**Members:**")
        if group["members"]:
            disp_df = pd.DataFrame(group["members"])

            # Clean display for categorical tags
            display_columns = [config.COL_NAME]
            if config.COL_GROUPER in disp_df.columns:
                display_columns.append(config.COL_GROUPER)
            if config.COL_SEPARATOR in disp_df.columns:
                display_columns.append(config.COL_SEPARATOR)

            # Append all score columns
            display_columns.extend(score_cols)

            # Ensure score columns are formatted consistently
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
