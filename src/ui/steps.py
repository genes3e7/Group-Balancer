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
            ext = uploaded.name.split(".")[-1].lower()
            if ext == "csv":
                df_new = pd.read_csv(uploaded)
            else:
                df_new = pd.read_excel(uploaded)

            # Validate raw upload before cleaning
            # Normalize headers consistent with DataService.clean_participants_df
            df_new.columns = df_new.columns.astype(str).str.strip()
            score_cols_raw = DataService.get_score_columns(df_new)
            if config.COL_NAME in df_new.columns and score_cols_raw:
                # Use Service layer for cleaning
                df_clean = DataService.clean_participants_df(df_new)
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
        current_cols = st.session_state.manual_df.columns
        n = 1
        while f"{config.SCORE_PREFIX}{n}" in current_cols:
            n += 1
        new_name = f"{config.SCORE_PREFIX}{n}"
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
    """Renders Step 2: Configuration.

    Handles group count, capacity allocation, objective weighting, and
    solver mode selection. Validates that capacities sum to total participants.
    """
    st.header("Step 2: Configuration")
    df = st.session_state.get("participants_df")
    if df is None or df.empty:
        st.warning("No data found.")
        if st.button("⬅ Back"):
            session_manager.go_to_step(1)
        st.stop()

    total_p = len(df)
    score_cols = st.session_state.get("score_cols", [])

    # Initialize or clamp stale groups_input if total_p shrank
    if "groups_input" not in st.session_state:
        st.session_state["groups_input"] = min(2, total_p)
    elif isinstance(st.session_state.get("groups_input"), (int, float)):
        st.session_state["groups_input"] = min(
            int(st.session_state["groups_input"]), total_p
        )

    c1, c2 = st.columns(2)
    num_groups = int(
        c1.number_input(
            "Groups",
            min_value=1,
            max_value=total_p,
            value=st.session_state["groups_input"],
            key="groups_input",
        )
    )
    c2.info(f"Total Participants: {total_p}")

    st.subheader("Group Capacities")
    group_capacities = []
    base, rem = divmod(total_p, num_groups)
    cols = st.columns(num_groups)
    for i in range(num_groups):
        default = base + (1 if i < rem else 0)
        # Use num_groups in key to force reset on count change
        cap = int(
            cols[i % len(cols)].number_input(
                f"G{i + 1}", 0, total_p, default, key=f"cap_{num_groups}_{i}"
            )
        )
        group_capacities.append(cap)

    cap_valid = sum(group_capacities) == total_p
    if not cap_valid:
        st.error(f"Capacity mismatch: {sum(group_capacities)} != {total_p}")

    with st.expander("⚙️ Advanced Solver Controls", expanded=True):
        mode_options = {
            "simple": OptimizationMode.SIMPLE,
            "advanced": OptimizationMode.ADVANCED,
        }
        priority_options = {
            "groupers": ConflictPriority.GROUPERS,
            "separators": ConflictPriority.SEPARATORS,
        }

        opt_mode_key = st.radio(
            "Mode",
            list(mode_options.keys()),
            index=1,
            key="optimization_mode",
            format_func=lambda k: mode_options[k].value,
        )
        priority_key = st.radio(
            "Priority",
            list(priority_options.keys()),
            index=0,
            key="conflict_priority",
            format_func=lambda k: priority_options[k].value,
        )

        st.checkbox(
            "Strict Grouping (Hard Constraints)",
            value=False,
            key="strict_grouping_toggle",
            help="Force all members with the same tag into one group. "
            "May lead to infeasibility if tags are too large.",
        )

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
            key="timeout_slider",
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
            mode_options[opt_mode_key],
            priority_options[priority_key],
            timeout,
            status_box=status_box,
            previous_results=st.session_state.get("results_df"),
            strict_groupers=st.session_state.get("strict_grouping_toggle", False),
        )

        if result_df is not None:
            st.session_state.results_df = result_df
            st.session_state.interactive_df = result_df.copy()
            st.session_state.solver_status = metrics["status"]
            st.session_state.solver_elapsed = metrics["elapsed"]
            st.session_state.solver_error = None
            time.sleep(0.5)
            session_manager.go_to_step(3)
        else:
            # Surface error state in results view
            # Clear stale results so KPIs/cards don't show old data
            st.session_state.results_df = None
            st.session_state.interactive_df = None
            st.session_state.solver_status = metrics["status"]
            st.session_state.solver_elapsed = metrics["elapsed"]
            st.session_state.solver_error = metrics.get("error")
            session_manager.go_to_step(3)


def render_step_3() -> None:
    """Renders Results step."""
    if st.button("⬅ Back"):
        session_manager.go_to_step(2)
    st.header("Step 3: Results")

    status_name = st.session_state.get("solver_status")
    elapsed = st.session_state.get("solver_elapsed", 0.0)
    error_msg = st.session_state.get("solver_error")

    if error_msg:
        st.error(f"❌ {error_msg}")
        st.info(
            "💡 **Tips to resolve:**\n"
            "- Check for conflicting Separator tags.\n"
            "- Ensure group capacities are large enough for the number of tags.\n"
            "- Try increasing the timeout or using 'Simple' mode."
        )
        return

    if st.session_state.get("interactive_df") is None:
        st.error("No results found.")
        return

    if status_name == "OPTIMAL":
        st.success(f"🎯 Optimal Solution found in {elapsed:.2f}s")
    elif status_name == "FEASIBLE":
        st.warning(f"⏳ Best solution found in {elapsed:.2f}s (Status: {status_name})")
    else:
        st.warning(f"⏳ Solver stopped in {elapsed:.2f}s (Status: {status_name})")

    score_cols = st.session_state.get("score_cols", [])
    results_renderer.render_global_stats(st.session_state.interactive_df, score_cols)

    view = st.radio("View", ["Table", "Cards"], horizontal=True, key="view_toggle")

    if view == "Table":
        _render_table_view(score_cols)
    else:
        results_renderer.render_group_cards(st.session_state.interactive_df, score_cols)

    st.divider()
    _render_footer_actions(score_cols)


def _render_table_view(score_cols: list[str]) -> None:
    """Renders result table with live statistics.

    Args:
        score_cols: List of score columns to display.
    """
    stats_col, editor_col = st.columns([1, 3])
    with editor_col:
        st.subheader("Edit Assignments")
        editor_configs = {
            config.COL_GROUP: st.column_config.NumberColumn(
                "Group",
                min_value=1,
                max_value=st.session_state.get("num_groups_target", 10),
                format="%d",
            ),
            config.COL_NAME: st.column_config.TextColumn(disabled=True),
            config.COL_GROUPER: st.column_config.TextColumn(disabled=True),
            config.COL_SEPARATOR: st.column_config.TextColumn(disabled=True),
        }
        for col in score_cols:
            editor_configs[col] = st.column_config.NumberColumn(disabled=True)

        df_for_editor = st.session_state.interactive_df.drop(
            columns=["_original_index", "participant_fingerprint"], errors="ignore"
        )
        edited_df = st.data_editor(
            df_for_editor,
            column_config=editor_configs,
            hide_index=True,
            width="stretch",
            key="results_editor_table",
        )
        if not edited_df.equals(df_for_editor):
            if "_original_index" in st.session_state.interactive_df.columns:
                orig_index = st.session_state.interactive_df["_original_index"]
                edited_df["_original_index"] = orig_index
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
            st.dataframe(
                gdf.style.format({"Avg": "{:.2f}", "Sum": "{:.2f}"}), hide_index=True
            )


@st.cache_data(show_spinner=False)
def _build_excel_bytes(
    df_key: tuple[int, int, tuple[str, ...]],
    _df: pd.DataFrame,
    score_cols: tuple[str, ...],
) -> bytes:
    """Memoized Excel generation to avoid redundant recomputes.

    Args:
        df_key: Tuple of hash sum, length, and columns for cache keying.
        _df: The result dataframe to export (excluded from cache hashing).
        score_cols: Tuple of score columns to include.

    Returns:
        bytes: The generated Excel file as a byte stream.
    """
    # Use key explicitly to satisfy Vulture and reinforce cache keying intent
    _ = df_key
    return exporter.generate_excel_bytes(
        _df, config.COL_GROUP, list(score_cols), config.COL_NAME
    )


def _render_footer_actions(score_cols: list[str]) -> None:
    """Footer buttons.

    Args:
        score_cols: List of score columns to include in export.
    """
    df = st.session_state.interactive_df
    row_hashes = pd.util.hash_pandas_object(df, index=True)
    df_key = (
        int(row_hashes.sum()),
        len(df),
        tuple(map(str, df.columns)),
    )
    excel_data = _build_excel_bytes(df_key, df, tuple(score_cols))
    st.download_button(
        "📥 Download Excel",
        excel_data,
        config.OUTPUT_FILENAME,
        type="primary",
    )

    if st.button("🔄 Start Over"):
        st.session_state.clear()
        st.rerun()
