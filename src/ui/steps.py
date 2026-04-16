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
from ortools.sat.python import cp_model
from src.core import config, solver_interface
from src.ui import results_renderer, session_manager
from src.utils import exporter


def _load_uploaded_file() -> None:
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
            score_cols = [
                c for c in df_new.columns if str(c).startswith(config.SCORE_PREFIX)
            ]

            if config.COL_NAME in df_new.columns and score_cols:
                st.session_state.manual_df = df_new
                st.toast(f"✅ Imported {len(df_new)} rows from file!", icon="📂")
            else:
                st.error(
                    f"File missing required columns. Requires '{config.COL_NAME}' and at least one starting with '{config.SCORE_PREFIX}'."
                )
        except Exception as e:
            st.error(f"Error reading file: {e}")


def render_step_1() -> None:
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
            score_cols = [
                c for c in edited_df.columns if str(c).startswith(config.SCORE_PREFIX)
            ]

            if config.COL_NAME not in edited_df.columns or not score_cols:
                st.error(
                    f"Table must contain '{config.COL_NAME}' and at least one column starting with '{config.SCORE_PREFIX}'."
                )
            else:
                clean_df = edited_df.copy()
                clean_df[config.COL_NAME] = clean_df[config.COL_NAME].astype(str)

                empty_names = clean_df[config.COL_NAME].str.strip().eq("").sum()
                if empty_names > 0:
                    st.warning(
                        f"⚠️ {empty_names} row(s) with empty names will be included."
                    )

                for col in score_cols:
                    clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce")
                    coerced_count = clean_df[col].isna().sum()
                    clean_df[col] = clean_df[col].fillna(0)

                    if coerced_count > 0:
                        st.warning(
                            f"⚠️ {coerced_count} invalid scores in {col} were set to 0. Please check your input."
                        )

                st.session_state.participants_df = clean_df
                st.session_state.manual_df = clean_df.copy()
                st.session_state.score_cols = score_cols
                session_manager.go_to_step(2)
        else:
            st.warning("Please add at least one participant.")


def render_step_2() -> None:
    """
    Renders the Configuration step (Step 2).
    Allows user to select the number of groups, define custom capacities, multi-score weights, and launch the solver.
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
    total_participants = len(df)
    score_cols = st.session_state.get("score_cols", [])

    c1, c2 = st.columns(2)
    with c1:
        num_groups = st.number_input(
            "Number of Groups",
            min_value=1,
            max_value=max(1, total_participants),
            value=2,
        )
    with c2:
        st.info(f"Total Participants: {total_participants}")
        st.caption(
            f"Note: Names ending in '{config.ADVANTAGE_CHAR}' are treated as Star players."
        )

    st.subheader("Group Capacities")
    st.caption(
        "Adjust the size of each group. The total must equal the participant count."
    )

    for key in list(st.session_state.keys()):
        if key.startswith("cap_"):
            try:
                idx = int(key.split("_")[1])
                if idx >= num_groups:
                    del st.session_state[key]
            except ValueError:
                pass

    capacity_cols = st.columns(num_groups)
    group_capacities = []

    base_size = total_participants // num_groups
    remainder = total_participants % num_groups

    for i in range(num_groups):
        default_cap = base_size + 1 if i < remainder else base_size
        with capacity_cols[i % len(capacity_cols)]:
            cap = st.number_input(
                f"Group {i + 1}",
                min_value=0,
                max_value=total_participants,
                value=default_cap,
                key=f"cap_{i}",
            )
            group_capacities.append(cap)

    total_cap = sum(group_capacities)
    cap_valid = total_cap == total_participants

    if not cap_valid:
        st.error(
            f"Validation Error: Total capacity ({total_cap}) does not match participants ({total_participants})."
        )
    else:
        st.success("Validation Success: Capacities match total participants.")

    st.subheader("Score Multi-Objective Weighting")
    st.caption("Adjust the relative importance of balancing each score dimension.")

    score_weights = {}
    if not score_cols:
        st.warning("No score columns detected. Please verify your data entry.")
    else:
        weight_cols = st.columns(len(score_cols))
        for i, col in enumerate(score_cols):
            with weight_cols[i]:
                score_weights[col] = st.number_input(
                    f"Weight: {col}", min_value=0.0, max_value=10.0, value=1.0, step=0.1
                )

    st.subheader("Solver Configuration")
    timeout_limit = st.slider(
        "Max Calculation Time (Seconds)",
        min_value=config.UI_TIMEOUT_MIN,
        max_value=config.UI_TIMEOUT_MAX,
        value=config.UI_TIMEOUT_DEFAULT,
        help=f"Higher limits allow finding better groupings but take longer. A hard cap is enforced at {config.SOLVER_TIMEOUT}s.",
    )

    st.divider()
    c_back, c_go = st.columns([1, 5])
    if c_back.button("⬅ Back"):
        session_manager.go_to_step(1)

    if c_go.button("🚀 Generate Groupings", type="primary", disabled=not cap_valid):
        st.session_state.num_groups_target = num_groups
        st.session_state.group_capacities = group_capacities
        status_box = st.empty()
        solver_error = False

        with st.spinner("Initializing solver engine..."):
            try:
                result_df, solver_status, elapsed_time = (
                    solver_interface.run_optimization(
                        st.session_state.participants_df.to_dict("records"),
                        st.session_state.group_capacities,
                        status_box,
                        timeout_limit,
                        score_cols,
                        score_weights,
                    )
                )
            except Exception as e:
                status_box.error(f"Solver encountered an error: {e}")
                result_df = None
                solver_status = None
                solver_error = True

        if result_df is not None:
            st.session_state.results_df = result_df
            st.session_state.interactive_df = result_df.copy()
            st.session_state.solver_status = solver_status
            st.session_state.solver_elapsed = elapsed_time
            time.sleep(0.5)
            session_manager.go_to_step(3)
        else:
            if not solver_error:
                status_box.error(
                    "No valid solution could be found. Try adjusting constraints."
                )


def render_step_3() -> None:
    """
    Renders the Results step (Step 3).
    Displays the result matrix, live statistics, and export buttons.
    """
    col_top_back, col_top_title = st.columns([1, 6])
    if col_top_back.button("⬅ Back to Config"):
        session_manager.go_to_step(2)
    with col_top_title:
        st.header("Step 3: Results")

    solver_status = st.session_state.get("solver_status")
    elapsed = st.session_state.get("solver_elapsed", 0.0)
    score_cols = st.session_state.get("score_cols", [])

    if solver_status == cp_model.FEASIBLE:
        st.warning(
            f"⏱️ **Timeout Reached:** Displaying the best grouping found within the {elapsed:.2f}s limit. A mathematically optimal solution could not be proven in time.",
            icon="⏳",
        )
    elif solver_status == cp_model.OPTIMAL:
        st.success(
            f"🎯 **Optimal Solution Proven:** This grouping has the lowest possible mathematical deviation for the given constraints. (Proven in {elapsed:.2f}s)",
            icon="✅",
        )

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
            _render_table_view(score_cols)
        else:
            results_renderer.render_group_cards(
                st.session_state.interactive_df, score_cols
            )

    st.divider()
    _render_footer_actions(has_data, score_cols)


def _render_table_view(score_cols: list[str]) -> None:
    """
    Renders the editable table view for results.
    Handles 'Update & Rerun' logic to ensure immediate stat updates.

    Args:
        score_cols (list[str]): List of score dimensions present in the dataframe.
    """
    stats_col, editor_col = st.columns([1, 3])
    with editor_col:
        st.subheader("Edit Assignments")

        max_groups = st.session_state.get("num_groups_target", 10)

        editor_configs = {
            config.COL_GROUP: st.column_config.NumberColumn(
                "Group ID",
                min_value=1,
                max_value=max_groups,
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
            key="results_editor",
        )

        if not edited_df.equals(st.session_state.interactive_df):
            st.session_state.interactive_df = edited_df
            st.rerun()

    with stats_col:
        st.subheader("Live Stats")

        for col in score_cols:
            st.markdown(f"**{col} Stats**")
            gdf = (
                st.session_state.interactive_df.groupby(config.COL_GROUP)[col]
                .agg(["count", "mean", "sum"])
                .reset_index()
            )
            gdf.columns = ["Group", "Count", "Avg", "Sum"]

            std_val = gdf["Avg"].std()
            if pd.isna(std_val):
                std_val = 0.0

            st.metric(f"{col} Std Dev", f"{std_val:.4f}")
            st.dataframe(gdf.style.format({"Avg": "{:.2f}"}), hide_index=True)


def _render_footer_actions(has_data: bool, score_cols: list[str]) -> None:
    """
    Renders the footer actions (Download Excel, Start Over).

    Args:
        has_data (bool): Whether data exists to allow download.
        score_cols (list[str]): List of score dimensions to structure export.
    """
    c_dl, c_reset = st.columns([1, 1])
    if has_data:
        excel_data = exporter.generate_excel_bytes(
            st.session_state.interactive_df,
            config.COL_GROUP,
            score_cols,
            config.COL_NAME,
        )
        c_dl.download_button(
            "📥 Download Excel",
            excel_data,
            config.OUTPUT_FILENAME,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )

    with c_reset:
        if st.button("🔄 Start Over"):
            st.session_state.confirm_reset = True
            st.rerun()

        if st.session_state.get("confirm_reset"):
            st.warning("Are you sure? This will clear all data.")
            col_yes, col_no = st.columns(2)
            if col_yes.button("Yes, clear"):
                st.session_state.clear()
                st.rerun()
            if col_no.button("Cancel"):
                st.session_state.confirm_reset = False
                st.rerun()
