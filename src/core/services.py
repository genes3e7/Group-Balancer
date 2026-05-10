"""Service layer for Group Balancer business logic.

This module provides high-level services for data processing and optimization,
decoupling the UI from core internal logic and OR-Tools dependencies.
"""

import pandas as pd

from src import logger
from src.core import config, solver_interface
from src.core.models import (
    ConflictPriority,
    OptimizationMode,
    Participant,
    SolverConfig,
)


def _resolve_warm_start_hints(
    participants: list[Participant],
    previous_results: pd.DataFrame,
    score_weights: dict[str, float],
    conflict_priority: ConflictPriority,
    group_capacities: list[int],
) -> tuple[dict[str, int] | None, dict[int, int] | None]:
    """Validates and constructs hint mappings from a previous result snapshot.

    Args:
        participants (list[Participant]): Current participant models.
        previous_results (pd.DataFrame): Result snapshot from a prior run.
        score_weights (dict[str, float]): Current optimization weights.
        conflict_priority (ConflictPriority): Current priority setting.
        group_capacities (list[int]): Current capacity configuration.

    Returns:
        tuple[dict | None, dict | None]: Hints by fingerprint and by index.
    """
    hints_fp = None
    hints_idx = None

    # Snapshot validation: Hints are only safe if the high-level configuration matches.
    config_match = (
        previous_results.attrs.get("score_weights") == score_weights
        and previous_results.attrs.get("conflict_priority") == conflict_priority
        and previous_results.attrs.get("group_capacities") == group_capacities
    )

    if not config_match:
        logger.info("Ignoring stale warm-start hints (config change).")
        return None, None

    # Dataset validation: Snapshots are only safe if the personnel multiset matches.
    if (
        config.COL_GROUP in previous_results.columns
        and "participant_fingerprint" in previous_results.columns
    ):
        current_f = sorted(p.fingerprint for p in participants)
        prev_f = sorted(
            previous_results["participant_fingerprint"].astype(str).tolist()
        )

        if current_f != prev_f:
            logger.info("Ignoring stale warm-start hints (mismatch)")
            return None, None

        # Build identity-based mappings
        fp_series = previous_results["participant_fingerprint"].astype(str)

        # Only use fingerprint hints if they are globally unique
        # to prevent identical participants from colliding in the search tree.
        if not fp_series.duplicated().any():
            hints_fp = dict(
                zip(
                    fp_series,
                    previous_results[config.COL_GROUP],
                    strict=False,
                )
            )
        else:
            logger.info("Ignoring stale hints (duplicate profiles).")

        # Always try to build index-based hints as a secondary layer
        if "_original_index" in previous_results.columns:
            mask = previous_results["_original_index"].notna()
            valid_rows = previous_results[mask]
            hints_idx = dict(
                zip(
                    valid_rows["_original_index"].astype(int),
                    valid_rows[config.COL_GROUP],
                    strict=False,
                )
            )
    elif (
        config.COL_GROUP in previous_results.columns
        and "_original_index" in previous_results.columns
    ):
        # Legacy fallback for results missing fingerprints
        current_indices = sorted(
            [p.original_index for p in participants if p.original_index is not None]
        )
        prev_indices = sorted(previous_results["_original_index"].dropna().unique())

        if current_indices == prev_indices:
            mask = previous_results["_original_index"].notna()
            valid_rows = previous_results[mask]
            hints_idx = dict(
                zip(
                    valid_rows["_original_index"].astype(int),
                    valid_rows[config.COL_GROUP],
                    strict=False,
                )
            )
        else:
            logger.info("Ignoring stale hints (indices mismatch).")

    return hints_fp, hints_idx


class DataService:
    """Service for cleaning and extracting structured data from DataFrames."""

    @staticmethod
    def clean_participants_df(df: pd.DataFrame) -> pd.DataFrame:
        """Cleans and sanitizes a raw participant DataFrame.

        Trims whitespace from headers, coerces scores to numeric, and ensures
        categorical tag columns exist with proper string types.

        Args:
            df (pd.DataFrame): The raw input DataFrame.

        Returns:
            pd.DataFrame: A sanitized copy of the input data.
        """
        clean_df = df.copy()
        clean_df.columns = clean_df.columns.astype(str).str.strip()

        if config.COL_NAME not in clean_df.columns:
            clean_df[config.COL_NAME] = ""
        else:
            clean_df[config.COL_NAME] = (
                clean_df[config.COL_NAME].fillna("").astype(str).str.strip()
            )

        for col in [config.COL_GROUPER, config.COL_SEPARATOR]:
            if col not in clean_df.columns:
                clean_df[col] = ""
            else:
                clean_df[col] = clean_df[col].fillna("").astype(str).str.strip()

        score_cols = DataService.get_score_columns(clean_df)
        for col in score_cols:
            clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce").fillna(0.0)

        return clean_df

    @staticmethod
    def get_score_columns(df: pd.DataFrame) -> list[str]:
        """Identifies all score-based columns based on prefix.

        Args:
            df (pd.DataFrame): The DataFrame to inspect.

        Returns:
            list[str]: Sorted list of detected score column names.
        """
        cols = [str(c) for c in df.columns if str(c).startswith(config.SCORE_PREFIX)]
        return sorted(cols)


class OptimizationService:
    """Service for orchestrating the CP-SAT solver process."""

    @staticmethod
    def run(
        participants_df: pd.DataFrame,
        group_capacities: list[int],
        score_weights: dict[str, float],
        conflict_priority: ConflictPriority,
        timeout_seconds: int,
        *,
        status_box=None,
        previous_results: pd.DataFrame | None = None,
    ) -> tuple[pd.DataFrame | None, dict]:
        """Runs the group balancing optimization.

        Converts raw DataFrame data into strongly-typed Participant models
        and executes the OR-Tools solver interface.

        Args:
            participants_df (pd.DataFrame): Sanitized participant data.
            group_capacities (list[int]): Desired size for each group.
            score_weights (dict[str, float]): Weight mapping for each score.
            conflict_priority (ConflictPriority): Resolution for tag collisions.
            timeout_seconds (int): Max search time in seconds.
            status_box: Optional Streamlit placeholder for live updates.
            previous_results (pd.DataFrame | None): Optional previous assignments.

        Returns:
            tuple[pd.DataFrame | None, dict]: Results DataFrame and metrics.

        Raises:
            ValueError: If input data or capacities are invalid.
        """
        if participants_df is None:
            raise ValueError("Participants DataFrame cannot be None.")

        if not group_capacities:
            raise ValueError("Group capacities cannot be empty.")

        try:
            participants = []
            for i, row in enumerate(participants_df.to_dict("records")):
                # Robust index extraction
                raw_idx = row.get("_original_index")
                orig_idx = int(raw_idx) if pd.notna(raw_idx) else i

                participants.append(
                    Participant(
                        name=str(row.get(config.COL_NAME, "")),
                        scores={
                            str(k): float(v)
                            for k, v in row.items()
                            if str(k).startswith(config.SCORE_PREFIX)
                        },
                        groupers=str(row.get(config.COL_GROUPER, "")),
                        separators=str(row.get(config.COL_SEPARATOR, "")),
                        original_index=orig_idx,
                    )
                )

            hints_fp, hints_idx = None, None
            if previous_results is not None and not previous_results.empty:
                hints_fp, hints_idx = _resolve_warm_start_hints(
                    participants,
                    previous_results,
                    score_weights,
                    conflict_priority,
                    group_capacities,
                )

            cfg = SolverConfig(
                num_groups=len(group_capacities),
                group_capacities=group_capacities,
                score_weights=score_weights,
                opt_mode=OptimizationMode.ADVANCED,
                conflict_priority=conflict_priority,
                timeout_seconds=timeout_seconds,
                hints_by_fingerprint=hints_fp,
                hints_by_index=hints_idx,
            )

            return solver_interface.run_optimization(
                participants, cfg, status_box=status_box
            )
        except (ValueError, KeyError) as e:
            logger.error("OptimizationService validation failed: %s", e)
            metrics = {"status": "ERROR", "error": str(e), "elapsed": 0.0}
            return None, metrics
        except Exception:
            logger.exception("OptimizationService.run failed unexpectedly")
            raise
