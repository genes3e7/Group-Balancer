"""Module for rendering optimization results in the Streamlit UI.

Provides high-level functions for displaying group-based statistics,
interactive member cards, and data editor views.
"""

import pandas as pd
import streamlit as st

from src.core import config
from src.utils import group_helpers


def render_global_stats(df: pd.DataFrame, score_cols: list[str]) -> None:
    """Renders high-level summary metrics for the entire partitioning.

    Args:
        df (pd.DataFrame): The participant result data.
        score_cols (list[str]): List of score columns to calculate stats for.
    """
    if df is None or df.empty:
        st.warning("No participant data found.")
        return

    st.subheader("Balancing Summary")
    groups = group_helpers.aggregate_groups(
        df, config.COL_GROUP, score_cols, config.COL_NAME
    )
    stats_data = group_helpers.calculate_balancing_stats(groups, score_cols)

    cols = st.columns(len(score_cols))
    for i, col in enumerate(score_cols):
        with cols[i]:
            std_val = stats_data[i]["Avg Std Dev (Balance)"]
            st.metric(f"{col} Std Dev", f"{std_val:.4f}")

    # Hidden detailed statistics table
    with st.expander("📊 Detailed Dimension Statistics", expanded=False):
        st.dataframe(pd.DataFrame(stats_data), hide_index=True, width="stretch")


def render_group_cards(df: pd.DataFrame, score_cols: list[str]) -> None:
    """Renders groups as a grid of interactive cards.

    Args:
        df (pd.DataFrame): The participant result data.
        score_cols (list[str]): List of score columns to display.
    """
    if df is None or df.empty:
        st.warning("No groups to display.")
        return

    groups = group_helpers.aggregate_groups(
        df, config.COL_GROUP, score_cols, config.COL_NAME
    )

    # Grid parameters
    num_cols = 3
    num_groups = len(groups)
    num_rows = (num_groups + num_cols - 1) // num_cols

    for r in range(num_rows):
        cols = st.columns(num_cols)
        for c in range(num_cols):
            idx = r * num_cols + c
            if idx < num_groups:
                with cols[c]:
                    _render_single_card(groups[idx], score_cols)


def _render_single_card(group: dict, score_cols: list[str]) -> None:
    """Renders an individual group container with member details.

    Args:
        group (dict): Group record from aggregator.
        score_cols (list[str]): Scores to display in member table.
    """
    with st.container(border=True):
        st.markdown(f"#### Group {group['id']}")

        # Mini-metrics for group averages
        cols = st.columns(len(score_cols))
        for i, col in enumerate(score_cols):
            avg = group["averages"][col]
            cols[i].metric(col, f"{avg:.1f}")

        # Member list using a data editor for potential manual tweaks
        members_df = pd.DataFrame(group["members"])
        if not members_df.empty:
            display_columns = [config.COL_NAME, config.COL_GROUP] + score_cols

            max_groups = st.session_state.get("num_groups_target", 10)
            col_configs = {
                config.COL_GROUP: st.column_config.NumberColumn(
                    "Group", min_value=1, max_value=max_groups, format="%d"
                ),
                config.COL_NAME: st.column_config.TextColumn(disabled=True),
            }
            for col in [config.COL_GROUPER, config.COL_SEPARATOR]:
                if col in members_df.columns:
                    display_columns.append(col)
                    col_configs[col] = st.column_config.TextColumn(disabled=True)

            for col in score_cols:
                col_configs[col] = st.column_config.NumberColumn(disabled=True)

            edited_df = st.data_editor(
                members_df[display_columns],
                column_config=col_configs,
                hide_index=True,
                width="stretch",
                key=f"editor_g{group['id']}",
            )

            # Sync manual edits back to the global interactive DataFrame
            if not edited_df.equals(members_df[display_columns]):
                # Determine who changed groups
                for idx, row in edited_df.iterrows():
                    orig_row = members_df.iloc[idx]
                    if row[config.COL_GROUP] != orig_row[config.COL_GROUP]:
                        p_idx = orig_row["_original_index"]

                        # Find and update in the session-wide dataframe
                        st.session_state.interactive_df.at[p_idx, config.COL_GROUP] = (
                            row[config.COL_GROUP]
                        )

                st.rerun()
        else:
            st.caption("No members assigned.")
