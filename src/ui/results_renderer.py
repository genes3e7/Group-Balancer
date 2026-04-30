"""Results Rendering Logic.

This module provides functions to display the final grouping results and
statistics for each group in a grid layout across multiple score dimensions,
including categorical constraint tags.
"""

import pandas as pd
import streamlit as st

from src.core import config
from src.utils import group_helpers


def render_global_stats(df: pd.DataFrame, score_cols: list[str]) -> None:
    """Renders a summary table of global balancing KPIs.

    The global average is a participant-weighted average across all groups.
    The reported dispersion is the standard deviation computed across the
    group averages. Lower standard deviation indicates better balance.

    Args:
        df: The DataFrame containing group assignments.
        score_cols: The list of score columns to calculate statistics for.
    """
    if df is None or df.empty:
        return

    st.subheader("📊 Global Balancing KPIs")
    groups = group_helpers.aggregate_groups(
        df, config.COL_GROUP, score_cols, config.COL_NAME
    )

    stats_data = group_helpers.calculate_balancing_stats(groups, score_cols)

    stats_df = pd.DataFrame(stats_data)
    st.dataframe(
        stats_df,
        hide_index=True,
        width="stretch",
        column_config={
            "Global Avg": st.column_config.NumberColumn(
                format="%.2f",
                help="Participant-weighted global average for this dimension.",
            ),
            "Avg Std Dev (Balance)": st.column_config.NumberColumn(
                format="%.4f",
                help="Standard deviation between group averages. Lower is better.",
            ),
        },
    )


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
        c1, c2 = st.columns([3, 1])
        c1.markdown(f"### 👥 Group {group['id']}")
        c2.metric("Size", len(group["members"]))

        with st.expander("📊 Group Summary", expanded=True):
            m_cols = st.columns(len(score_cols))
            for j, col in enumerate(score_cols):
                with m_cols[j]:
                    avg = group["averages"].get(col, 0)
                    st.metric(label=f"Avg {col}", value=f"{avg:.1f}")

        if group["members"]:
            disp_df = pd.DataFrame(group["members"])
            display_columns = [config.COL_NAME, config.COL_GROUP]

            # Add tags if they exist and are not empty
            for col in [config.COL_GROUPER, config.COL_SEPARATOR]:
                if col in disp_df.columns and not disp_df[col].eq("").all():
                    display_columns.append(col)

            display_columns.extend(score_cols)

            max_groups = st.session_state.get("num_groups_target", 10)
            col_configs = {
                config.COL_GROUP: st.column_config.NumberColumn(
                    "Group", min_value=1, max_value=max_groups, format="%d"
                ),
                config.COL_NAME: st.column_config.TextColumn(disabled=True),
            }
            for col in [config.COL_GROUPER, config.COL_SEPARATOR]:
                col_configs[col] = st.column_config.TextColumn(disabled=True)
            for col in score_cols:
                col_configs[col] = st.column_config.NumberColumn(
                    format="%.2f", disabled=True
                )

            edited_df = st.data_editor(
                disp_df[display_columns],
                width="stretch",
                column_config=col_configs,
                key=f"editor_group_{group['id']}",
            )

            if not edited_df.equals(disp_df[display_columns]):
                # A group reassignment happened
                interactive_df = st.session_state.interactive_df
                for local_idx, row in edited_df.iterrows():
                    orig_idx = disp_df.at[local_idx, "_original_index"]
                    new_grp = row[config.COL_GROUP]
                    if interactive_df.at[orig_idx, config.COL_GROUP] != new_grp:
                        interactive_df.at[orig_idx, config.COL_GROUP] = new_grp
                st.session_state.interactive_df = interactive_df
                st.rerun()
        else:
            st.caption("No members assigned.")
