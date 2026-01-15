"""
Visualization logic for displaying results.

This module handles the 'Card View' rendering of groups, showing detailed
statistics for each group in a grid layout.
"""

import streamlit as st
import pandas as pd
from src.core import config
from src.utils import group_helpers


def render_group_cards(df: pd.DataFrame) -> None:
    """
    Renders groups in a grid layout (cards).

    Args:
        df (pd.DataFrame): The DataFrame containing group assignments.
    """
    if df is None or df.empty:
        st.warning("No groups to display.")
        return

    # Use shared helper to get structured data
    groups = group_helpers.aggregate_groups(
        df, config.COL_GROUP, config.COL_SCORE, config.COL_NAME
    )

    for i in range(0, len(groups), 2):
        g1 = groups[i]
        g2 = groups[i + 1] if (i + 1) < len(groups) else None

        c1, c2 = st.columns(2)

        with c1:
            _render_single_card(g1)

        with c2:
            if g2:
                _render_single_card(g2)

        st.markdown("---")


def _render_single_card(group: dict) -> None:
    """
    Helper to render a single group card.

    Args:
        group (dict): Dictionary containing group metadata and members.
    """
    with st.container(border=True):
        st.markdown(f"### Group {group['id']}")
        cols = st.columns([1, 1, 1])
        cols[0].metric("Count", group["count"])
        cols[1].metric("Avg", f"{group['avg']:.2f}")
        cols[2].metric("Stars", group["stars"])

        st.divider()

        disp_df = pd.DataFrame(group["members"])
        if not disp_df.empty:
            st.dataframe(
                disp_df[[config.COL_NAME, config.COL_SCORE]],
                hide_index=True,
                width="stretch",
                column_config={
                    config.COL_SCORE: st.column_config.NumberColumn(format="%.0f")
                },
            )
        else:
            st.caption("No members assigned.")
