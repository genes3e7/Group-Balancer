import streamlit as st
import pandas as pd
import time
from src.core import config, solver_interface
from src.ui import components, results_renderer
from src.utils import exporter

# Initialize Page
components.setup_page()

# Initialize Session State
if "step" not in st.session_state:
    st.session_state.update({"step": 1, "participants_df": None, "results_df": None})

# Initialize the 'working' dataframe for the editor if it doesn't exist
if "manual_df" not in st.session_state:
    st.session_state.manual_df = pd.DataFrame(
        {
            config.COL_NAME: ["Player 1", "Player 2*", "Player 3"],
            config.COL_SCORE: [80, 95, 60],
        }
    )

# Render Progress & Description
components.render_page_header(st.session_state.step)


def go_to_step(step):
    st.session_state.step = step
    st.rerun()


# --- Callback for File Upload ---
def load_uploaded_file():
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
                # Update the session state used by the editor
                st.session_state.manual_df = df_new
                st.toast(f"✅ Imported {len(df_new)} rows from file!", icon="📂")
            else:
                st.error(
                    f"File missing required columns: {config.COL_NAME}, {config.COL_SCORE}"
                )
        except Exception as e:
            st.error(f"Error reading file: {e}")


# ==========================================
# STEP 1: IMPORT & EDIT DATA
# ==========================================
if st.session_state.step == 1:
    st.header("Step 1: Data Entry")

    # 1. File Uploader (Importer)
    with st.expander("📂 Import from Excel/CSV (Optional)", expanded=True):
        st.caption("Uploading a file will overwrite the table below.")
        st.file_uploader(
            "Select file to import",
            type=["xlsx", "csv"],
            key="u_file",
            on_change=load_uploaded_file,
        )

    # 2. The Data Editor (Source of Truth)
    st.subheader("Edit Participants")
    st.caption("Verify your data below. You can manually add rows or edit values.")

    edited_df = st.data_editor(
        st.session_state.manual_df,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_input",  # Unique key to prevent state conflicts
    )

    # 3. Validation & Navigation
    if st.button("Next: Configure", type="primary"):
        if edited_df is not None and not edited_df.empty:
            # Ensure columns exist (in case user deleted them manually)
            if (
                config.COL_NAME not in edited_df.columns
                or config.COL_SCORE not in edited_df.columns
            ):
                st.error(
                    f"Table must contain columns: '{config.COL_NAME}' and '{config.COL_SCORE}'"
                )
            else:
                # Clean Data types before proceeding
                clean_df = edited_df.copy()
                clean_df[config.COL_NAME] = clean_df[config.COL_NAME].astype(str)

                # Handle Score Coercion with Warning
                clean_df[config.COL_SCORE] = pd.to_numeric(
                    clean_df[config.COL_SCORE], errors="coerce"
                )

                # Check for NaNs (invalid scores)
                coerced_count = clean_df[config.COL_SCORE].isna().sum()
                clean_df[config.COL_SCORE] = clean_df[config.COL_SCORE].fillna(0)

                if coerced_count > 0:
                    st.warning(
                        f"⚠️ {coerced_count} invalid score(s) were set to 0. Please check your input."
                    )

                st.session_state.participants_df = clean_df
                go_to_step(2)
        else:
            st.warning("Please add at least one participant.")

# ==========================================
# STEP 2: CONFIG & GENERATE
# ==========================================
elif st.session_state.step == 2:
    st.header("Step 2: Configuration")
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
        go_to_step(1)

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
            # Fix: Reset interactive view to match new results immediately
            st.session_state.interactive_df = result_df.copy()

            status_box.success("Optimization Complete!")
            time.sleep(0.5)
            go_to_step(3)
        else:
            status_box.error("No solution found. Try reducing constraints.")

# ==========================================
# STEP 3: RESULTS
# ==========================================
elif st.session_state.step == 3:
    # --- Top Navigation ---
    col_top_back, col_top_title = st.columns([1, 6])
    if col_top_back.button("⬅ Back to Config"):
        go_to_step(2)
    with col_top_title:
        st.header("Step 3: Results")

    if "interactive_df" not in st.session_state:
        st.session_state.interactive_df = st.session_state.results_df.copy()

    # View Toggle
    view_mode = st.radio(
        "Display Mode:",
        ["📝 Editor (Table)", "🃏 Group Cards (Visual)"],
        horizontal=True,
    )

    st.divider()

    # --- Main Content ---
    if st.session_state.interactive_df is None or st.session_state.interactive_df.empty:
        st.error("No results to display. Please go back and regenerate.")
    else:
        if view_mode == "📝 Editor (Table)":
            stats_col, editor_col = st.columns([1, 3])

            with editor_col:
                st.subheader("Edit Assignments")
                edited_df = st.data_editor(
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
                    use_container_width=True,
                )
                st.session_state.interactive_df = edited_df

            with stats_col:
                st.subheader("Live Stats")
                gdf = (
                    edited_df.groupby(config.COL_GROUP)[config.COL_SCORE]
                    .agg(["count", "mean", "sum"])
                    .reset_index()
                )
                gdf.columns = ["Group", "Count", "Avg", "Sum"]
                st.metric("Std Dev", f"{gdf['Avg'].std():.4f}")
                st.dataframe(gdf.style.format({"Avg": "{:.2f}"}), hide_index=True)

        else:
            # Card View
            results_renderer.render_group_cards(st.session_state.interactive_df)

    st.divider()

    # --- Footer Actions ---
    c_dl, c_reset = st.columns([1, 1])

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
