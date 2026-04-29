"""
Service layer for Group Balancer business logic.

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


class DataService:
    """Service for cleaning and extracting structured data from DataFrames."""

    @staticmethod
    def clean_participants_df(df: pd.DataFrame) -> pd.DataFrame:
        """
        Cleans and sanitizes a raw participant DataFrame.

        Trims whitespace from headers, coerces scores to numeric, and ensures
        categorical tag columns exist with proper string types.

        Args:
            df (pd.DataFrame): The raw input DataFrame.

        Returns:
            pd.DataFrame: A sanitized copy of the input data.
        """
        clean_df = df.copy()
        clean_df.columns = clean_df.columns.astype(str).str.strip()

        # Required Name column - fillna before astype(str) to avoid "nan" string
        if config.COL_NAME not in clean_df.columns:
            clean_df[config.COL_NAME] = ""
        else:
            clean_df[config.COL_NAME] = (
                clean_df[config.COL_NAME].fillna("").astype(str).str.strip()
            )

        # Categorical constraints
        for col in [config.COL_GROUPER, config.COL_SEPARATOR]:
            if col not in clean_df.columns:
                clean_df[col] = ""
            else:
                clean_df[col] = clean_df[col].fillna("").astype(str).str.strip()

        # Score dimensions
        score_cols = DataService.get_score_columns(clean_df)
        for col in score_cols:
            clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce").fillna(0.0)

        return clean_df

    @staticmethod
    def get_score_columns(df: pd.DataFrame) -> list[str]:
        """
        Identifies all score-based columns based on prefix.

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
        opt_mode: OptimizationMode,
        conflict_priority: ConflictPriority,
        timeout_seconds: int,
        status_box=None,
        previous_results: pd.DataFrame | None = None,
        strict_groupers: bool = False,
    ) -> tuple[pd.DataFrame | None, dict]:
        """
        Runs the group balancing optimization.

        Converts raw DataFrame data into strongly-typed Participant models
        and executes the OR-Tools solver interface.

        Args:
            participants_df (pd.DataFrame): Sanitized participant data.
            group_capacities (list[int]): Desired size for each group.
            score_weights (dict): Weight mapping for each score dimension.
            opt_mode (OptimizationMode): Simple or Advanced balancing mode.
            conflict_priority (ConflictPriority): Resolution for tag collisions.
            timeout_seconds (int): Max search time in seconds.
            status_box: Optional Streamlit placeholder for live updates.
            previous_results: Optional DataFrame containing previous assignments
                for solution hinting (warm start).
            strict_groupers: If True, cohesion tags are hard constraints.

        Returns:
            tuple: (Results DataFrame or None, Metrics dictionary)
        """
        if not group_capacities:
            raise ValueError("Group capacities cannot be empty.")

        # Convert to models
        participants = [
            Participant(
                name=str(row.get(config.COL_NAME, "")),
                scores={
                    str(k): float(v)
                    for k, v in row.items()
                    if str(k).startswith(config.SCORE_PREFIX)
                },
                groupers=str(row.get(config.COL_GROUPER, "")),
                separators=str(row.get(config.COL_SEPARATOR, "")),
                original_index=i,
            )
            for i, row in enumerate(participants_df.to_dict("records"))
        ]

        hints = None
        if previous_results is not None and not previous_results.empty:
            # Validate snapshot against fingerprints to prevent stale hints
            if (
                config.COL_GROUP in previous_results.columns
                and "participant_fingerprint" in previous_results.columns
            ):
                current_fingerprints = sorted([p.fingerprint for p in participants])
                prev_fingerprints = sorted(
                    previous_results["participant_fingerprint"].astype(str).unique()
                )

                if current_fingerprints == prev_fingerprints:
                    hints = dict(
                        zip(
                            previous_results["participant_fingerprint"],
                            previous_results[config.COL_GROUP],
                            strict=False,
                        )
                    )
                else:
                    logger.info("Ignoring stale warm-start hints (mismatch)")
            # Fallback to original_index for backward compatibility
            elif (
                config.COL_GROUP in previous_results.columns
                and "_original_index" in previous_results.columns
            ):
                current_indices = sorted([p.original_index for p in participants])
                prev_indices = sorted(previous_results["_original_index"].unique())

                if current_indices == prev_indices:
                    hints = dict(
                        zip(
                            previous_results["_original_index"],
                            previous_results[config.COL_GROUP],
                            strict=False,
                        )
                    )
                else:
                    logger.info("Ignoring stale warm-start hints (indices mismatch).")

        cfg = SolverConfig(
            num_groups=len(group_capacities),
            group_capacities=group_capacities,
            score_weights=score_weights,
            opt_mode=opt_mode,
            conflict_priority=conflict_priority,
            timeout_seconds=timeout_seconds,
            hints=hints,
            strict_groupers=strict_groupers,
        )

        try:
            return solver_interface.run_optimization(
                participants, cfg, status_box=status_box
            )
        except Exception as e:
            metrics = {"status": "ERROR", "error": str(e), "elapsed": 0.0}
            return None, metrics
