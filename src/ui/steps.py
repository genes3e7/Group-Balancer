"""UI Rendering Logic for individual steps.

Handles the multi-dimensional weight inputs, advanced mode topologies, and
displays solver results. Decoupled from core business logic via DataService.
"""

import time

import pandas as pd
import streamlit as st

from src.core import config
from src.core.models import ConflictPriority, OptimizationMode
from src.core.services import DataService, OptimizationService
from src.ui import results_renderer, session_manager
from src.utils import exporter


def _load_uploaded_file() -> None:
    """Callback to handle file uploads and clean data via DataService."""
    uploaded = st.session_state.u_file
    if uploaded is not None:
        try:
            if uploaded.name.endswith(".csv"):
                df_new = pd.read_csv(uploaded)
            else:
                df_new = pd.read_excel(uploaded)

            # Use Service layer for cleaning
            df_clean = DataService.clean_participants_df(df_new)
            score_cols = DataService.get_score_columns(df_clean)

            if config.COL_NAME in df_clean.columns and score_cols:
                st.session_state.manual_df = df_clean
                st.toast(f"✅ Imported {len(df_clean)} rows!", icon="📂")
            else:
                st.error("File missing required columns: Name and Score*")
        except Exception as e:
            st.error(f"Error reading file: {e}")


def render_step_1() -> None:
    """Renders Data Entry step."""
    st.header("Step 1: Data Entry")

    with st.expander("📂 Import from Excel/CSV (Optional)", expanded=True):
        st.file_uploader(
            "Select file",
            type=["xlsx", "csv"],
            key="u_file",
            on_change=_load_uploaded_file,
        )

    st.subheader("Edit Participants")

    # Ensure default columns exist in session state
    for col in [config.COL_GROUPER, config.COL_SEPARATOR]:
        if col not in st.session_state.manual_df.columns:
            st.session_state.manual_df[col] = ""

    if st.button("➕ Add Score Column"):
        current_scores = DataService.get_score_columns(st.session_state.manual_df)
        new_name = f"{config.SCORE_PREFIX}{len(current_scores) + 1}"
        st.session_state.manual_df[new_name] = 0.0
        st.rerun()

    edited_df = st.data_editor(
        st.session_state.manual_df,
        num_rows="dynamic",
        width="stretch",
        key="editor_input",
    )

    if st.button("Next: Configure", type="primary"):
        if edited_df is not None and not edited_df.empty:
            clean_df = DataService.clean_participants_df(edited_df)
            score_cols = DataService.get_score_columns(clean_df)

            if not score_cols:
                st.error("At least one score column is required.")
            else:
                st.session_state.participants_df = clean_df
                st.session_state.manual_df = clean_df.copy()
                st.session_state.score_cols = score_cols
                session_manager.go_to_step(2)
        else:
            st.warning("Please add participants.")


def render_step_2() -> None:
    """Renders Configuration step."""
    st.header("Step 2: Configuration")
    df = st.session_state.get("participants_df")
    if df is None or df.empty:
        st.warning("No data found.")
        if st.button("⬅ Back"):
            session_manager.go_to_step(1)
        st.stop()

    total_p = len(df)
    score_cols = st.session_state.get("score_cols", [])

    c1, c2 = st.columns(2)
    num_groups = int(c1.number_input("Groups", 1, total_p, 2))
    c2.info(f"Total Participants: {total_p}")

    st.subheader("Group Capacities")
    group_capacities = []
    base, rem = divmod(total_p, num_groups)
    cols = st.columns(num_groups)
    for i in range(num_groups):
        default = base + (1 if i < rem else 0)
        cap = int(
            cols[i % len(cols)].number_input(
                f"G{i + 1}", 0, total_p, default, key=f"cap_{i}"
            )
        )
        group_capacities.append(cap)

    cap_valid = sum(group_capacities) == total_p
    if not cap_valid:
        st.error(f"Capacity mismatch: {sum(group_capacities)} != {total_p}")

    with st.expander("⚙️ Advanced Solver Controls", expanded=True):
        opt_mode = st.radio("Mode", ["Simple", "Advanced"], index=1)
        priority = st.radio("Priority", ["Groupers", "Separators"], index=0)

    st.subheader("Objective Weighting")
    score_weights = {
        col: st.number_input(f"Weight: {col}", 0.0, 10.0, 1.0, 0.1, key=f"w_{col}")
        for col in score_cols
    }

    timeout = int(
        st.slider(
            "Timeout (s)",
            config.UI_TIMEOUT_MIN,
            config.UI_TIMEOUT_MAX,
            config.UI_TIMEOUT_DEFAULT,
        )
    )

    st.divider()
    c_back, c_go = st.columns([1, 5])
    if c_back.button("⬅ Back"):
        session_manager.go_to_step(1)

    if c_go.button("🚀 Generate", type="primary", disabled=not cap_valid):
        st.session_state.num_groups_target = num_groups
        st.session_state.group_capacities = group_capacities

        status_box = st.empty()

        # Use Service layer for optimization
        result_df, metrics = OptimizationService.run(
            df,
            group_capacities,
            score_weights,
            OptimizationMode(opt_mode),
            ConflictPriority(priority),
            timeout,
            status_box=status_box,
        )

        if result_df is not None:
            st.session_state.results_df = result_df
            st.session_state.interactive_df = result_df.copy()
            st.session_state.solver_status = metrics["status"]
            st.session_state.solver_elapsed = metrics["elapsed"]
            time.sleep(0.5)
            session_manager.go_to_step(3)


def render_step_3() -> None:
    """Renders Results step."""
    if st.button("⬅ Back"):
        session_manager.go_to_step(2)
    st.header("Step 3: Results")

    status_name = st.session_state.get("solver_status")
    elapsed = st.session_state.get("solver_elapsed", 0.0)

    if status_name == "OPTIMAL":
        st.success(f"🎯 Optimal Solution found in {elapsed:.2f}s")
    else:
        st.warning(f"⏳ Best solution found in {elapsed:.2f}s (Status: {status_name})")

    if "interactive_df" not in st.session_state:
        st.error("No results found.")
        return

    view = st.radio("View", ["Table", "Cards"], horizontal=True)
    score_cols = st.session_state.get("score_cols", [])

    if view == "Table":
        _render_table_view(score_cols)
    else:
        results_renderer.render_group_cards(st.session_state.interactive_df, score_cols)

    st.divider()
    _render_footer_actions(score_cols)


def _render_table_view(score_cols: list[str]) -> None:
    """Renders result table.

    Args:
        score_cols: List of score columns to display.
    """
    editor_configs = {
        config.COL_GROUP: st.column_config.NumberColumn(
            "Group",
            min_value=1,
            format="%d",
        ),
        config.COL_NAME: st.column_config.TextColumn(disabled=True),
    }
    for col in score_cols:
        editor_configs[col] = st.column_config.NumberColumn(disabled=True)

    edited_df = st.data_editor(
        st.session_state.interactive_df,
        column_config=editor_configs,
        hide_index=True,
        width="stretch",
    )
    if not edited_df.equals(st.session_state.interactive_df):
        st.session_state.interactive_df = edited_df
        st.rerun()


def _render_footer_actions(score_cols: list[str]) -> None:
    """Footer buttons.

    Args:
        score_cols: List of score columns to include in export.
    """
    excel_data = exporter.generate_excel_bytes(
        st.session_state.interactive_df,
        config.COL_GROUP,
        score_cols,
        config.COL_NAME,
    )
    st.download_button(
        "📥 Download Excel",
        excel_data,
        config.OUTPUT_FILENAME,
        type="primary",
    )

    if st.button("🔄 Start Over"):
        st.session_state.clear()
        st.rerun()
