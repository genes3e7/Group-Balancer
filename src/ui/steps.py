"""UI Rendering Logic for individual steps.

Handles the multi-dimensional weight inputs, advanced mode topologies, and
displays solver results. Decoupled from core business logic via DataService.
"""

import hashlib
import json
import pathlib
import time
from typing import Any

import pandas as pd
import streamlit as st

from src import logger
from src.core import config
from src.core.models import ConflictPriority
from src.core.services import DataService, OptimizationService
from src.ui import results_renderer, session_manager
from src.utils import exporter, group_helpers


def _generate_cache_key(
    df: pd.DataFrame,
    group_capacities: list[int],
    score_weights: dict[str, float],
    priority: ConflictPriority,
) -> str:
    """Generates a composite MD5 hash of the data and configuration.

    Args:
        df (pd.DataFrame): The current participant dataset.
        group_capacities (list[int]): Desired group sizes.
        score_weights (dict[str, float]): Weight mapping for scores.
        priority (ConflictPriority): Constraint priority setting.

    Returns:
        str: A unique hex string for this specific state.
    """
    # Hash the data (content and structure) deterministically by row
    data_hashes = pd.util.hash_pandas_object(df, index=True)
    data_blob = data_hashes.to_numpy().tobytes()

    # Serialize config deterministically
    config_payload = {
        "capacities": list(group_capacities),
        "weights": sorted(score_weights.items()),
        "priority": priority.value,
    }
    config_json = json.dumps(config_payload, sort_keys=True)

    # Combine into final key
    raw = f"{config_json}".encode() + data_blob
    return hashlib.md5(raw, usedforsecurity=False).hexdigest()


def _process_uploaded_file(uploaded: Any) -> tuple[bool, str]:  # noqa: ANN401
    """Processes the uploaded file and updates session state manual data.

    Args:
        uploaded: The uploaded file object.

    Returns:
        tuple[bool, str]: Success flag and content-based signature.
    """
    if uploaded is None:
        return False, ""
    try:
        suffix = pathlib.Path(uploaded.name).suffix.lower().lstrip(".")
        df_new = pd.read_csv(uploaded) if suffix == "csv" else pd.read_excel(uploaded)

        df_new.columns = df_new.columns.astype(str).str.strip()
        score_cols_raw = DataService.get_score_columns(df_new)
        if config.COL_NAME in df_new.columns and score_cols_raw:
            df_clean = DataService.clean_participants_df(df_new)
            st.session_state.manual_df = df_clean
            st.toast(f"✅ Imported {len(df_clean)} rows!", icon="📂")
            return (
                True,
                str(pd.util.hash_pandas_object(df_clean, index=True).sum()),
            )

        st.error("File missing required columns: Name and Score*")
    except (pd.errors.ParserError, UnicodeDecodeError) as e:
        logger.exception("Data processing failed")
        st.error(f"Error reading file: {e}")
    except Exception:  # noqa: BLE001 # pragma: no cover
        logger.exception("Unexpected error during file upload")
        st.error("Unexpected error reading file. Check logs for details.")

    return False, ""


def render_step_1() -> None:
    """Renders Data Entry step."""
    st.header("Step 1: Data Entry")

    _render_file_importer()

    st.subheader("Edit Participants")

    for col in [config.COL_GROUPER, config.COL_SEPARATOR]:
        if col not in st.session_state.manual_df.columns:
            st.session_state.manual_df[col] = ""

    if st.button("+ Add Score Column"):
        _add_new_score_column()

    edited_df = st.data_editor(
        st.session_state.manual_df,
        num_rows="dynamic",
        width="stretch",
        key="editor_input",
    )

    if st.button("Next: Configure", type="primary"):
        _handle_step_1_navigation(edited_df)


def _render_file_importer() -> None:
    """Renders the file uploader and handles file processing logic."""
    with st.expander("📂 Import from Excel/CSV (Optional)", expanded=True):
        uploaded = st.file_uploader(
            "Select file",
            type=["xlsx", "csv"],
            key="u_file",
        )
        if uploaded:
            # Use hash of raw bytes to detect edits even with same name/size
            bytes_sig = hashlib.md5(
                uploaded.getvalue(), usedforsecurity=False
            ).hexdigest()

            # Gate on content signature to ensure we handle same-name edits correctly
            if st.session_state.get("last_file_processed_meta") != bytes_sig or (
                st.session_state.get("last_file_content_sig") is None
            ):
                success, content_sig = _process_uploaded_file(uploaded)
                if success:
                    st.session_state.last_file_processed_meta = bytes_sig
                    st.session_state.last_file_content_sig = content_sig


def _add_new_score_column() -> None:
    """Logic to find and add the next incremental ScoreN column."""
    current_cols = st.session_state.manual_df.columns
    n = 1
    while f"{config.SCORE_PREFIX}{n}" in current_cols:
        n += 1
    new_name = f"{config.SCORE_PREFIX}{n}"
    st.session_state.manual_df[new_name] = 0.0
    st.rerun()


def _handle_step_1_navigation(edited_df: pd.DataFrame | None) -> None:
    """Validates data and transitions to Step 2."""
    if edited_df is not None and not edited_df.empty:
        clean_df = DataService.clean_participants_df(edited_df)
        score_cols = DataService.get_score_columns(clean_df)

        if not score_cols:
            st.error("At least one score column is required.")
        else:
            st.session_state.participants_df = clean_df
            st.session_state.manual_df = clean_df.copy()
            st.session_state.score_cols = score_cols
            session_manager.go_to_step(config.STEP_CONFIGURE)
    else:
        st.warning("Please add participants.")


def render_step_2() -> None:
    """Renders Step 2: Configuration.

    Handles group count, capacity allocation, objective weighting, and
    solver execution.
    """
    st.header("Step 2: Configuration")
    df = st.session_state.get("participants_df")
    if df is None or df.empty:
        _handle_missing_data_step_2()
        return

    total_p = len(df)
    score_cols = st.session_state.get("score_cols", [])

    # 1. Group Count Input
    num_groups = _render_group_count_input(total_p)

    # 2. Capacity Inputs
    group_capacities = _render_capacity_inputs(total_p, num_groups)
    cap_valid = sum(group_capacities) == total_p
    if not cap_valid:
        st.error(f"Capacity mismatch: {sum(group_capacities)} != {total_p}")

    # 3. Solver Controls (Priority and Weights)
    priority, score_weights = _render_solver_controls(score_cols)

    # 4. Timeout Slider
    timeout = _render_timeout_slider()

    st.divider()
    # 5. Navigation and Execution
    _render_step_2_footer(
        df,
        group_capacities,
        score_weights,
        priority,
        timeout,
        {"cap_valid": cap_valid, "num_groups": num_groups},
    )


def _handle_missing_data_step_2() -> None:
    """Renders warning and back button when data is missing in Step 2."""
    st.warning("No data found.")
    if st.button("⬅ Back"):
        session_manager.go_to_step(config.STEP_DATA_ENTRY)
    st.stop()


def _render_group_count_input(total_p: int) -> int:
    """Renders the number_input for group count with defensive clamping."""
    min_allowed = min(config.MIN_PARTICIPANTS_FOR_BALANCING, total_p)
    try:
        raw_val = st.session_state.get("groups_input", min_allowed)
        curr_val = int(raw_val)
    except (ValueError, TypeError):
        curr_val = min_allowed

    st.session_state["groups_input"] = max(1, min(curr_val, total_p))

    c1, _c2 = st.columns(2)
    num_groups = int(
        c1.number_input(
            "Groups",
            min_value=1,
            max_value=total_p,
            key="groups_input",
        )
    )
    st.info(f"Total Participants: {total_p}")
    return num_groups


def _render_capacity_inputs(total_p: int, num_groups: int) -> list[int]:
    """Renders numeric inputs for each group capacity."""
    st.subheader("Group Capacities")
    group_capacities = []
    base, rem = divmod(total_p, num_groups)
    cols = st.columns(num_groups)

    for i in range(num_groups):
        default = base + (1 if i < rem else 0)
        key = f"cap_{num_groups}_{i}"

        # Defensive state clamping
        try:
            val = int(st.session_state.get(key, default))
        except (ValueError, TypeError):
            val = default
        st.session_state[key] = max(0, min(val, total_p))

        cap = int(cols[i % len(cols)].number_input(f"G{i + 1}", 0, total_p, key=key))
        group_capacities.append(cap)
    return group_capacities


def _render_solver_controls(
    score_cols: list[str],
) -> tuple[ConflictPriority, dict[str, float]]:
    """Renders priority radio and weight numeric inputs."""
    st.subheader("Solver Controls")
    priority_options = {
        "groupers": ConflictPriority.GROUPERS,
        "separators": ConflictPriority.SEPARATORS,
    }

    priority_key = st.radio(
        "Priority",
        list(priority_options.keys()),
        index=0,
        key="conflict_priority",
        format_func=lambda k: priority_options[k].value,
        help="Determines which constraint type takes precedence in the hierarchy.",
    )

    st.subheader("Objective Weighting")
    score_weights = {
        col: st.number_input(
            f"Weight: {col}", 0.0, 10.0, config.DEFAULT_UI_WEIGHT, 0.1, key=f"w_{col}"
        )
        for col in score_cols
    }
    return priority_options[priority_key], score_weights


def _render_timeout_slider() -> int:
    """Renders the slider for solver timeout."""
    return int(
        st.slider(
            "Timeout (s)",
            config.UI_TIMEOUT_MIN,
            config.UI_TIMEOUT_MAX,
            config.UI_TIMEOUT_DEFAULT,
            key="timeout_slider",
        )
    )


def _render_step_2_footer(  # noqa: PLR0913
    df: pd.DataFrame,
    group_capacities: list[int],
    score_weights: dict[str, float],
    priority: ConflictPriority,
    timeout: int,
    meta: dict[str, Any],
) -> None:
    """Renders the footer buttons and handles optimization execution logic."""
    cap_valid = meta["cap_valid"]
    num_groups = meta["num_groups"]

    c_back, c_go = st.columns([1, 5])
    if c_back.button("⬅ Back"):
        session_manager.go_to_step(config.STEP_DATA_ENTRY)

    if c_go.button("🚀 Generate", type="primary", disabled=not cap_valid):
        st.session_state.num_groups_target = num_groups
        st.session_state.group_capacities = group_capacities

        status_box = st.empty()

        # Cache and Warm-Start resolution
        cache_key = _generate_cache_key(df, group_capacities, score_weights, priority)
        prev_results = _resolve_best_hints(df, cache_key, priority)

        result_df, metrics = OptimizationService.run(
            df,
            group_capacities,
            score_weights,
            priority,
            timeout,
            grouper_weight=config.DEFAULT_GROUPER_WEIGHT,
            separator_weight=config.DEFAULT_SEPARATOR_WEIGHT,
            interleave_search=False,
            status_box=status_box,
            previous_results=prev_results,
        )

        _handle_optimization_result(result_df, metrics, cache_key)


def _resolve_best_hints(
    df: pd.DataFrame, cache_key: str, priority: ConflictPriority
) -> pd.DataFrame | None:
    """Determines the best available previous results for warm-starting."""
    # 1. Check current interactive state
    interactive_df = st.session_state.get("interactive_df")
    results_df = st.session_state.get("results_df")

    if interactive_df is not None and results_df is not None:
        interactive_key = _generate_cache_key(
            df,
            results_df.attrs.get("group_capacities", []),
            results_df.attrs.get("score_weights", {}),
            results_df.attrs.get("conflict_priority", priority),
        )
        if interactive_key == cache_key:
            prev = interactive_df.copy(deep=True)
            for col in ["_original_index", "participant_fingerprint"]:
                if col in results_df.columns:
                    prev[col] = results_df[col]
            prev.attrs = dict(results_df.attrs)
            return prev

    # 2. Check LRU Cache
    if cache_key in st.session_state.warm_start_cache:
        prev = st.session_state.warm_start_cache[cache_key].copy(deep=True)
        st.session_state.warm_start_cache.move_to_end(cache_key)
        return prev

    # 3. Fallback to raw results
    return results_df


def _handle_optimization_result(
    result_df: pd.DataFrame | None, metrics: dict, cache_key: str
) -> None:
    """Updates session state and navigates based on solver outcome."""
    if result_df is not None:
        st.session_state.warm_start_cache[cache_key] = result_df.copy()
        if len(st.session_state.warm_start_cache) > config.MAX_WARM_CACHE_SIZE:
            st.session_state.warm_start_cache.popitem(last=False)

        st.session_state.results_df = result_df
        st.session_state.interactive_df = result_df.copy()
        st.session_state.solver_status = metrics["status"]
        st.session_state.solver_elapsed = metrics["elapsed"]
        st.session_state.solver_error = None
        time.sleep(0.5)
    else:
        st.session_state.results_df = None
        st.session_state.interactive_df = None
        st.session_state.solver_status = metrics["status"]
        st.session_state.solver_elapsed = metrics["elapsed"]
        st.session_state.solver_error = metrics.get("error")

    session_manager.go_to_step(config.STEP_RESULTS)


def render_step_3() -> None:
    """Renders Results step."""
    if st.button("⬅ Back"):
        session_manager.go_to_step(config.STEP_CONFIGURE)
    st.header("Step 3: Results")

    status_name = st.session_state.get("solver_status")
    elapsed = st.session_state.get("solver_elapsed", 0.0)
    error_msg = st.session_state.get("solver_error")

    if error_msg:
        st.error(f"❌ {error_msg}")
        st.info(
            "💡 **Tips to resolve:**\n"
            "- Check for conflicting Separator tags.\n"
            "- Ensure group capacities emerge from sufficient total "
            "participant count.\n"
            "- Try increasing the timeout."
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
        score_cols (list[str]): List of score columns to display.
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
            "_original_index": None,
            "participant_fingerprint": None,
        }
        for col in score_cols:
            editor_configs[col] = st.column_config.NumberColumn(disabled=True)

        edited_df = st.data_editor(
            st.session_state.interactive_df,
            column_config=editor_configs,
            hide_index=True,
            width="stretch",
            key="results_editor_table",
        )
        if not edited_df.equals(st.session_state.interactive_df):
            st.session_state.interactive_df = edited_df
            st.rerun()

    with stats_col:
        st.subheader("Live Stats")
        groups_cfg = group_helpers.GroupingConfig(
            config.COL_GROUP,
            score_cols,
            config.COL_NAME,
        )
        groups = group_helpers.aggregate_groups(
            st.session_state.interactive_df,
            groups_cfg,
        )
        stats_data = group_helpers.calculate_balancing_stats(groups, score_cols)
        stats_lookup = {s["Score Dimension"]: s for s in stats_data}

        for col in score_cols:
            st.markdown(f"**{col} Stats**")
            gdf = (
                st.session_state.interactive_df.groupby(config.COL_GROUP)[col]
                .agg(["count", "mean", "sum"])
                .reset_index()
            )
            gdf.columns = ["Group", "Count", "Avg", "Sum"]

            std_val = stats_lookup[col]["Avg Std Dev (Balance)"]

            st.metric(f"{col} Std Dev", f"{std_val:.4f}")
            st.dataframe(
                gdf.style.format({"Avg": "{:.2f}", "Sum": "{:.2f}"}), hide_index=True
            )


@st.cache_data(show_spinner=False)
def _build_excel_bytes(
    df_key: tuple[str, int, tuple[str, ...]],
    _df: pd.DataFrame,
    score_cols: tuple[str, ...],
) -> bytes:
    """Memoized Excel generation to avoid redundant recomputes.

    Args:
        df_key (tuple): Tuple of hash hex, length, and columns for cache keying.
        _df (pd.DataFrame): The result dataframe to export.
        score_cols (tuple): Tuple of score columns to include.

    Returns:
        bytes: The generated Excel file as a byte stream.
    """
    _ = df_key
    return exporter.generate_excel_bytes(
        _df, config.COL_GROUP, list(score_cols), config.COL_NAME
    )


def _render_footer_actions(score_cols: list[str]) -> None:
    """Footer buttons.

    Args:
        score_cols (list[str]): List of score columns to include in export.
    """
    df = st.session_state.interactive_df
    export_df = df.drop(
        columns=["_original_index", "participant_fingerprint"], errors="ignore"
    )

    row_hashes = pd.util.hash_pandas_object(export_df, index=True)
    df_key = (
        hashlib.md5(row_hashes.to_numpy().tobytes(), usedforsecurity=False).hexdigest(),
        len(export_df),
        tuple(map(str, export_df.columns)),
    )
    excel_data = _build_excel_bytes(df_key, export_df, tuple(score_cols))
    st.download_button(
        "📥 Download Excel",
        excel_data,
        config.OUTPUT_FILENAME,
        type="primary",
    )

    if st.button("🔄 Start Over"):
        # Selective reset: Preserve the memoization cache but clear all project data
        for key in list(st.session_state.keys()):
            if key not in config.RESET_PRESERVE_KEYS:
                del st.session_state[key]
        st.rerun()
