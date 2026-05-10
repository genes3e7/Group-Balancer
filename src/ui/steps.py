"""UI Rendering Logic for individual steps.

Handles the multi-dimensional weight inputs, advanced mode topologies, and
displays solver results. Decoupled from core business logic via DataService.
"""

import hashlib
import json
import pathlib
import time

import pandas as pd
import streamlit as st

from src import logger
from src.core import config
from src.core.models import ConflictPriority
from src.core.services import DataService, OptimizationService
from src.ui import results_renderer, session_manager
from src.utils import exporter, group_helpers

# Keys that should not be deleted when the user clicks 'Start Over'
_RESET_PRESERVE_KEYS = frozenset({"warm_start_cache"})


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
    # Hash the data (content and structure)
    data_hash = pd.util.hash_pandas_object(df, index=True).sum()

    # Serialize config deterministically
    config_payload = {
        "capacities": list(group_capacities),
        "weights": sorted(score_weights.items()),
        "priority": priority.value,
    }
    config_json = json.dumps(config_payload, sort_keys=True)

    # Combine into final key
    raw = f"{data_hash}_{config_json}"
    return hashlib.md5(raw.encode("utf-8"), usedforsecurity=False).hexdigest()


def _process_uploaded_file(uploaded) -> tuple[bool, str]:
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
        if suffix == "csv":
            df_new = pd.read_csv(uploaded)
        else:
            df_new = pd.read_excel(uploaded)

        df_new.columns = df_new.columns.astype(str).str.strip()
        score_cols_raw = DataService.get_score_columns(df_new)
        if config.COL_NAME in df_new.columns and score_cols_raw:
            df_clean = DataService.clean_participants_df(df_new)
            st.session_state.manual_df = df_clean
            st.toast(f"✅ Imported {len(df_clean)} rows!", icon="📂")
            # Generate content signature
            sig = str(pd.util.hash_pandas_object(df_clean, index=True).sum())
            return True, sig

        st.error("File missing required columns: Name and Score*")
        return False, ""
    except (pd.errors.ParserError, UnicodeDecodeError) as e:
        logger.exception("Data processing failed")
        st.error(f"Error reading file: {e}")
        return False, ""
    except Exception:
        logger.exception("Unexpected error during file upload")
        raise


def render_step_1() -> None:
    """Renders Data Entry step."""
    st.header("Step 1: Data Entry")

    with st.expander("📂 Import from Excel/CSV (Optional)", expanded=True):
        uploaded = st.file_uploader(
            "Select file",
            type=["xlsx", "csv"],
            key="u_file",
        )
        if uploaded:
            # Use content-based signature to detect edits even with same name/size
            meta_sig = f"{uploaded.name}_{uploaded.size}"
            # Gate on content signature to ensure we handle same-name edits correctly
            if st.session_state.get("last_file_processed_meta") != meta_sig or (
                st.session_state.get("last_file_content_sig") is None
            ):
                success, content_sig = _process_uploaded_file(uploaded)
                if success:
                    st.session_state.last_file_processed_meta = meta_sig
                    st.session_state.last_file_content_sig = content_sig

    st.subheader("Edit Participants")

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
    solver mode selection.
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
        key = f"cap_{num_groups}_{i}"

        # Defensive state clamping to prevent out-of-bounds rendering
        if key in st.session_state:
            st.session_state[key] = max(0, min(int(st.session_state[key]), total_p))
        else:
            st.session_state[key] = default

        cap = int(cols[i % len(cols)].number_input(f"G{i + 1}", 0, total_p, key=key))
        group_capacities.append(cap)

    cap_valid = sum(group_capacities) == total_p
    if not cap_valid:
        st.error(f"Capacity mismatch: {sum(group_capacities)} != {total_p}")

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

        # Cache Logic: Generate key and lookup
        cache_key = _generate_cache_key(
            df, group_capacities, score_weights, priority_options[priority_key]
        )

        # Determine best-effort previous results
        if cache_key in st.session_state.warm_start_cache:
            prev_results = st.session_state.warm_start_cache[cache_key]
            st.session_state.warm_start_cache.move_to_end(cache_key)
        else:
            prev_results = st.session_state.get("interactive_df")
            cached_results = st.session_state.get("results_df")

            if prev_results is not None and cached_results is not None:
                prev_results = prev_results.copy()
                for col in ["_original_index", "participant_fingerprint"]:
                    if col in cached_results.columns:
                        prev_results[col] = cached_results[col]
                prev_results.attrs = dict(cached_results.attrs)
            elif prev_results is None:
                prev_results = cached_results

        result_df, metrics = OptimizationService.run(
            df,
            group_capacities,
            score_weights,
            priority_options[priority_key],
            timeout,
            status_box=status_box,
            previous_results=prev_results,
        )

        if result_df is not None:
            st.session_state.warm_start_cache[cache_key] = result_df.copy()
            if len(st.session_state.warm_start_cache) > 50:
                st.session_state.warm_start_cache.popitem(last=False)

            st.session_state.results_df = result_df
            st.session_state.interactive_df = result_df.copy()
            st.session_state.solver_status = metrics["status"]
            st.session_state.solver_elapsed = metrics["elapsed"]
            st.session_state.solver_error = None
            time.sleep(0.5)
            session_manager.go_to_step(3)
        else:
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
        groups = group_helpers.aggregate_groups(
            st.session_state.interactive_df,
            config.COL_GROUP,
            score_cols,
            config.COL_NAME,
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
    df_key: tuple[int, int, tuple[str, ...]],
    _df: pd.DataFrame,
    score_cols: tuple[str, ...],
) -> bytes:
    """Memoized Excel generation to avoid redundant recomputes.

    Args:
        df_key (tuple): Tuple of hash sum, length, and columns for cache keying.
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
        int(row_hashes.sum()),
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
            if key not in _RESET_PRESERVE_KEYS:
                del st.session_state[key]
        st.rerun()
