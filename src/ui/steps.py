import streamlit as st
import pandas as pd
import time
from src.core import config, solver_interface
from src.ui import results_renderer, session_manager
from src.utils import exporter


# --- Helper Callbacks ---
def _load_uploaded_file():
    """Reads the uploaded file and updates the manual_df session state."""
    uploaded = st.session_state.u_file
    if uploaded is not None:
        try:
            if uploaded.name.endswith(".csv"):
                df_new = pd.read_csv(uploaded)
            else:
                df_new = pd.read_excel(uploaded)

            # Clean columns
            df_new.columns = df_new.columns.str.strip()

            # Basic Validation
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
    Callback for Step 3.
    Updates interactive_df from the unique 'results_editor' key.
    """
    if "results_editor" in st.session_state:
        st.session_state.interactive_df = st.session_state["results_editor"]


# ==========================================
# STEP 1: IMPORT & EDIT DATA
# ==========================================
def render_step_1():
    st.header("Step 1: Data Entry")

    # 1. File Uploader (Importer)
    with st.expander("📂 Import from Excel/CSV (Optional)", expanded=True):
        st.caption("Uploading a file will overwrite the table below.")
        st.file_uploader(
            "Select file to import",
            type=["xlsx", "csv"],
            key="u_file",
            on_change=_load_uploaded_file,
        )

    # 2. The Data Editor (Source of Truth)
    st.subheader("Edit Participants")
    st.caption("Verify your data below. You can manually add rows or edit values.")

    edited_df = st.data_editor(
        st.session_state.manual_df,
        num_rows="dynamic",
        width="stretch",
        key="editor_input",  # Unique key for Step 1
    )

    # 3. Validation & Navigation
    if st.button("Next: Configure", type="primary"):
        if edited_df is not None and not edited_df.empty:
            # Ensure columns exist
            if (
                config.COL_NAME not in edited_df.columns
                or config.COL_SCORE not in edited_df.columns
            ):
                st.error(
                    f"Table must contain columns: '{config.COL_NAME}' and '{config.COL_SCORE}'"
                )
            else:
                # Clean Data
                clean_df = edited_df.copy()
                clean_df[config.COL_NAME] = clean_df[config.COL_NAME].astype(str)
                clean_df[config.COL_SCORE] = pd.to_numeric(
                    clean_df[config.COL_SCORE], errors="coerce"
                )

                # Check for invalid scores
                coerced_count = clean_df[config.COL_SCORE].isna().sum()
                clean_df[config.COL_SCORE] = clean_df[config.COL_SCORE].fillna(0)

                if coerced_count > 0:
                    st.warning(
                        f"⚠️ {coerced_count} invalid score(s) were set to 0. Please check your input."
                    )

                st.session_state.participants_df = clean_df
                session_manager.go_to_step(2)
        else:
            st.warning("Please add at least one participant.")


# ==========================================
# STEP 2: CONFIG & GENERATE
# ==========================================
def render_step_2():
    st.header("Step 2: Configuration")

    # Guard: Ensure data exists
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


# ==========================================
# STEP 3: RESULTS
# ==========================================
def render_step_3():
    # Top Navigation
    col_top_back, col_top_title = st.columns([1, 6])
    if col_top_back.button("⬅ Back to Config"):
        session_manager.go_to_step(2)
    with col_top_title:
        st.header("Step 3: Results")

    # Initialize interactive state if missing
    if "interactive_df" not in st.session_state:
        st.session_state.interactive_df = (
            st.session_state.results_df.copy()
            if st.session_state.results_df is not None
            else None
        )

    # [CRITICAL FIX] Data Corruption Guard
    # If interactive_df became a dict (due to key collision bug), repair it immediately.
    if not isinstance(st.session_state.interactive_df, pd.DataFrame):
        st.session_state.interactive_df = st.session_state.results_df.copy()

    # View Toggle
    view_mode = st.radio(
        "Display Mode:",
        ["📝 Editor (Table)", "🃏 Group Cards (Visual)"],
        horizontal=True,
    )
    st.divider()

    # Main Content
    has_data = (
        st.session_state.interactive_df is not None
        and not st.session_state.interactive_df.empty
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
    stats_col, editor_col = st.columns([1, 3])
    with editor_col:
        st.subheader("Edit Assignments")

        # FIX: Use a unique key ("results_editor") to prevent conflict with Step 1
        st.data_editor(
            st.session_state.interactive_df,
            column_config={
                config.COL_GROUP: st.column_config.NumberColumn(
                    "Group ID",
                    min_value=1,
                    max_value=st.session_state.num_groups_target,
                    format="%d",
                ),
                config.COL_SCORE: st.column_config.NumberColumn(disabled=True),
                config.COL_NAME: st.column_config.TextColumn(disabled=True),
            },
            hide_index=True,
            width="stretch",
            key="results_editor",  # <--- UNIQUE KEY
            on_change=_update_results_state,  # <--- SYNC CALLBACK
        )

    with stats_col:
        st.subheader("Live Stats")
        # Use session_state directly to reflect instant updates
        gdf = (
            st.session_state.interactive_df.groupby(config.COL_GROUP)[config.COL_SCORE]
            .agg(["count", "mean", "sum"])
            .reset_index()
        )
        gdf.columns = ["Group", "Count", "Avg", "Sum"]
        st.metric("Std Dev", f"{gdf['Avg'].std():.4f}")
        st.dataframe(gdf.style.format({"Avg": "{:.2f}"}), hide_index=True)


def _render_footer_actions(has_data):
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
            "balanced_groups.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )

    if c_reset.button("🔄 Start Over"):
        st.session_state.clear()
        st.rerun()
