"""
UI Rendering Logic for individual steps.

This module contains the specific layout and interaction logic for:
- Step 1: Data Entry & Import
- Step 2: Configuration & Solver Launch
- Step 3: Results Display & Export
"""

import streamlit as st
import pandas as pd
import time
from src.core import config, solver_interface
from src.ui import results_renderer, session_manager
from src.utils import exporter


def _load_uploaded_file():
    """
    Callback to handle file uploads.
    Reads the file and updates 'manual_df' in session state.
    """
    uploaded = st.session_state.u_file
    if uploaded is not None:
        try:
            if uploaded.name.endswith(".csv"):
                df_new = pd.read_csv(uploaded)
            else:
                df_new = pd.read_excel(uploaded)

            df_new.columns = df_new.columns.str.strip()

            if config.COL_NAME in df_new.columns and config.COL_SCORE in df_new.columns:
                st.session_state.manual_df = df_new
                st.toast(f"✅ Imported {len(df_new)} rows from file!", icon="📂")
            else:
                st.error(
                    f"File missing required columns: {config.COL_NAME}, {config.COL_SCORE}"
                )
        except Exception as e:
            st.error(f"Error reading file: {e}")


def _update_results_state():
    """
    Callback for Step 3 editor changes.
    Syncs the interactive editor state with the main session state.
    """
    if "results_editor" in st.session_state:
        new_value = st.session_state["results_editor"]
        if isinstance(new_value, pd.DataFrame):
            st.session_state.interactive_df = new_value


def render_step_1():
    """
    Renders the Data Entry step (Step 1).
    Displays the file importer and the editable data table.
    """
    st.header("Step 1: Data Entry")

    with st.expander("📂 Import from Excel/CSV (Optional)", expanded=True):
        st.caption("Uploading a file will overwrite the table below.")
        st.file_uploader(
            "Select file to import",
            type=["xlsx", "csv"],
            key="u_file",
            on_change=_load_uploaded_file,
        )

    st.subheader("Edit Participants")
    st.caption("Verify your data below. You can manually add rows or edit values.")

    edited_df = st.data_editor(
        st.session_state.manual_df,
        num_rows="dynamic",
        width="stretch",
        key="editor_input",
    )

    if st.button("Next: Configure", type="primary"):
        if edited_df is not None and not edited_df.empty:
            if (
                config.COL_NAME not in edited_df.columns
                or config.COL_SCORE not in edited_df.columns
            ):
                st.error(
                    f"Table must contain columns: '{config.COL_NAME}' and '{config.COL_SCORE}'"
                )
            else:
                clean_df = edited_df.copy()
                clean_df[config.COL_NAME] = clean_df[config.COL_NAME].astype(str)

                # Check for empty names
                empty_names = clean_df[config.COL_NAME].str.strip().eq("").sum()
                if empty_names > 0:
                    st.warning(
                        f"⚠️ {empty_names} row(s) with empty names will be included."
                    )

                clean_df[config.COL_SCORE] = pd.to_numeric(
                    clean_df[config.COL_SCORE], errors="coerce"
                )

                coerced_count = clean_df[config.COL_SCORE].isna().sum()
                clean_df[config.COL_SCORE] = clean_df[config.COL_SCORE].fillna(0)

                if coerced_count > 0:
                    st.warning(
                        f"⚠️ {coerced_count} invalid score(s) were set to 0. Please check your input."
                    )

                st.session_state.participants_df = clean_df
                st.session_state.manual_df = clean_df.copy()
                session_manager.go_to_step(2)
        else:
            st.warning("Please add at least one participant.")


def render_step_2():
    """
    Renders the Configuration step (Step 2).
    Allows user to select the number of groups and launch the solver.
    """
    st.header("Step 2: Configuration")

    if (
        st.session_state.participants_df is None
        or st.session_state.participants_df.empty
    ):
        st.warning("No participant data found. Please go back to Step 1.")
        if st.button("⬅ Back to Data Entry"):
            session_manager.go_to_step(1)
        st.stop()

    df = st.session_state.participants_df

    c1, c2 = st.columns(2)
    with c1:
        num_groups = st.number_input(
            "Groups", min_value=1, max_value=max(1, len(df)), value=2
        )
    with c2:
        st.info(f"Participants: {len(df)}")
        st.caption(
            f"Note: Names ending in '{config.ADVANTAGE_CHAR}' are treated as Star players."
        )

    c_back, c_go = st.columns([1, 5])
    if c_back.button("⬅ Back"):
        session_manager.go_to_step(1)

    if c_go.button("🚀 Generate Groupings", type="primary"):
        st.session_state.num_groups_target = num_groups
        status_box = st.empty()

        with st.spinner("Initializing solver engine..."):
            result_df = solver_interface.run_optimization(
                st.session_state.participants_df.to_dict("records"),
                st.session_state.num_groups_target,
                status_box,
            )

        if result_df is not None:
            st.session_state.results_df = result_df
            st.session_state.interactive_df = result_df.copy()
            status_box.success("Optimization Complete!")
            time.sleep(0.5)
            session_manager.go_to_step(3)
        else:
            status_box.error("No solution found. Try reducing constraints.")


def render_step_3():
    """
    Renders the Results step (Step 3).
    Displays the result matrix, live statistics, and export buttons.
    """
    col_top_back, col_top_title = st.columns([1, 6])
    if col_top_back.button("⬅ Back to Config"):
        session_manager.go_to_step(2)
    with col_top_title:
        st.header("Step 3: Results")

    if "interactive_df" not in st.session_state:
        st.session_state.interactive_df = (
            st.session_state.results_df.copy()
            if st.session_state.results_df is not None
            else None
        )

    if not isinstance(st.session_state.get("interactive_df"), pd.DataFrame):
        if isinstance(st.session_state.get("results_df"), pd.DataFrame):
            st.session_state.interactive_df = st.session_state.results_df.copy()
        else:
            st.session_state.interactive_df = pd.DataFrame()

    view_mode = st.radio(
        "Display Mode:",
        ["📝 Editor (Table)", "🃏 Group Cards (Visual)"],
        horizontal=True,
    )
    st.divider()

    interactive_df = st.session_state.interactive_df
    has_data = (
        interactive_df is not None
        and isinstance(interactive_df, pd.DataFrame)
        and not interactive_df.empty
    )

    if not has_data:
        st.error("No results to display. Please go back and regenerate.")
    else:
        if view_mode == "📝 Editor (Table)":
            _render_table_view()
        else:
            results_renderer.render_group_cards(st.session_state.interactive_df)

    st.divider()
    _render_footer_actions(has_data)


def _render_table_view():
    """
    Renders the editable table view for results.
    Handles 'Update & Rerun' logic to ensure immediate stat updates.
    """
    stats_col, editor_col = st.columns([1, 3])
    with editor_col:
        st.subheader("Edit Assignments")

        max_groups = st.session_state.get("num_groups_target", 10)

        edited_df = st.data_editor(
            st.session_state.interactive_df,
            column_config={
                config.COL_GROUP: st.column_config.NumberColumn(
                    "Group ID",
                    min_value=1,
                    max_value=max_groups,
                    format="%d",
                ),
                config.COL_SCORE: st.column_config.NumberColumn(disabled=True),
                config.COL_NAME: st.column_config.TextColumn(disabled=True),
            },
            hide_index=True,
            width="stretch",
            key="results_editor",
        )

        if not edited_df.equals(st.session_state.interactive_df):
            st.session_state.interactive_df = edited_df
            st.rerun()

    with stats_col:
        st.subheader("Live Stats")
        gdf = (
            st.session_state.interactive_df.groupby(config.COL_GROUP)[config.COL_SCORE]
            .agg(["count", "mean", "sum"])
            .reset_index()
        )
        gdf.columns = ["Group", "Count", "Avg", "Sum"]

        std_val = gdf["Avg"].std()
        if pd.isna(std_val):
            std_val = 0.0

        st.metric("Std Dev", f"{std_val:.4f}")
        st.dataframe(gdf.style.format({"Avg": "{:.2f}"}), hide_index=True)


def _render_footer_actions(has_data: bool):
    """
    Renders the footer actions (Download Excel, Start Over).

    Args:
        has_data (bool): Whether data exists to allow download.
    """
    c_dl, c_reset = st.columns([1, 1])
    if has_data:
        excel_data = exporter.generate_excel_bytes(
            st.session_state.interactive_df,
            config.COL_GROUP,
            config.COL_SCORE,
            config.COL_NAME,
        )
        c_dl.download_button(
            "📥 Download Excel",
            excel_data,
            config.OUTPUT_FILENAME,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )

    if c_reset.button("🔄 Start Over"):
        st.session_state.clear()
        st.rerun()
