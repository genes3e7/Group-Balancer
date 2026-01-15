import streamlit as st
import pandas as pd
from src.core import config


def render_group_cards(df):
    """
    Renders groups in a grid layout (cards).
    """
    if df is None or df.empty:
        st.warning("No groups to display.")
        return

    # 1. Prepare Data
    groups = []
    unique_groups = sorted(df[config.COL_GROUP].unique())

    for g_id in unique_groups:
        members = df[df[config.COL_GROUP] == g_id].to_dict("records")
        scores = [float(m[config.COL_SCORE]) for m in members]

        # Safely count stars
        stars = 0
        for m in members:
            val = str(m[config.COL_NAME])
            if val.endswith(config.ADVANTAGE_CHAR):
                stars += 1

        groups.append(
            {
                "id": g_id,
                "members": members,
                "count": len(members),
                "avg": sum(scores) / len(scores) if scores else 0,
                "stars": stars,
            }
        )

    # 2. Render Grid (2 Groups per Row)
    for i in range(0, len(groups), 2):
        g1 = groups[i]
        g2 = groups[i + 1] if (i + 1) < len(groups) else None

        c1, c2 = st.columns(2)

        # Render Left Group
        with c1:
            _render_single_card(g1)

        # Render Right Group (if exists)
        with c2:
            if g2:
                _render_single_card(g2)

        st.markdown("---")


def _render_single_card(group):
    """Helper to render one group card."""
    with st.container(border=True):
        # Header Stats
        st.markdown(f"### Group {group['id']}")
        cols = st.columns([1, 1, 1])
        cols[0].metric("Count", group["count"])
        cols[1].metric("Avg", f"{group['avg']:.2f}")
        cols[2].metric("Stars", group["stars"])

        st.divider()

        # Members List
        disp_df = pd.DataFrame(group["members"])
        if not disp_df.empty:
            st.dataframe(
                disp_df[[config.COL_NAME, config.COL_SCORE]],
                hide_index=True,
                use_container_width=True,
                column_config={
                    config.COL_SCORE: st.column_config.NumberColumn(format="%.0f")
                },
            )
        else:
            st.caption("No members assigned.")
