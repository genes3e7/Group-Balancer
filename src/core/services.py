"""Service layer for data processing and optimization orchestration.

Decouples business logic from the UI and state management.
"""

from typing import Any, Protocol

import pandas as pd

from src.core import config
from src.core.models import (
    ConflictPriority,
    OptimizationMode,
    Participant,
    SolverConfig,
)
from src.core.solver_interface import run_optimization


class IDataService(Protocol):
    """Interface for data operations."""

    @staticmethod
    def clean_participants_df(df: pd.DataFrame) -> pd.DataFrame:
        """Cleans and normalizes the participants dataframe.

        Args:
            df: Input dataframe.

        Returns:
            pd.DataFrame: Cleaned dataframe.
        """
        ...

    @staticmethod
    def get_score_columns(df: pd.DataFrame) -> list[str]:
        """Returns list of score columns in the dataframe.

        Args:
            df: Input dataframe.

        Returns:
            list[str]: List of column names.
        """
        ...


class DataService(IDataService):
    """Handles data transformation and validation."""

    @staticmethod
    def clean_participants_df(df: pd.DataFrame) -> pd.DataFrame:
        """Cleans and normalizes the participants dataframe.

        Moves logic out of src/ui/steps.py.

        Args:
            df: Input dataframe.

        Returns:
            pd.DataFrame: Cleaned dataframe.
        """
        clean_df = df.copy()

        # Ensure Name column exists and is string
        if config.COL_NAME not in clean_df.columns:
            clean_df[config.COL_NAME] = ""
        clean_df[config.COL_NAME] = clean_df[config.COL_NAME].astype(str).str.strip()

        # Identify score columns
        score_cols = [
            c for c in clean_df.columns if str(c).startswith(config.SCORE_PREFIX)
        ]

        # Coerce scores to numeric
        for col in score_cols:
            clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce").fillna(0.0)

        # Coerce constraints to string
        for col in [config.COL_GROUPER, config.COL_SEPARATOR]:
            if col not in clean_df.columns:
                clean_df[col] = ""
            clean_df[col] = clean_df[col].fillna("").astype(str)

        return clean_df

    @staticmethod
    def get_score_columns(df: pd.DataFrame) -> list[str]:
        """Returns list of score columns in the dataframe.

        Args:
            df: Input dataframe.

        Returns:
            list[str]: List of column names.
        """
        return [c for c in df.columns if str(c).startswith(config.SCORE_PREFIX)]


class OptimizationService:
    """Orchestrates the optimization process."""

    @staticmethod
    def run(
        participants_df: pd.DataFrame,
        group_capacities: list[int],
        score_weights: dict[str, float],
        opt_mode: OptimizationMode,
        conflict_priority: ConflictPriority,
        timeout_seconds: int,
        **kwargs: Any,
    ) -> tuple[pd.DataFrame | None, dict[str, Any]]:
        """Runs the solver and returns results as a DataFrame.

        Decoupled from Streamlit's st.session_state, but allows passthrough
        of UI components like status_box via kwargs.

        Args:
            participants_df: Dataframe of participants.
            group_capacities: List of capacities for each group.
            score_weights: Weights for each score dimension.
            opt_mode: Optimization mode (Simple or Advanced).
            conflict_priority: Priority for tag collisions.
            timeout_seconds: Solver timeout.
            **kwargs: Additional parameters passed to the solver interface.

        Returns:
            tuple: (Results dataframe or None, Status dictionary).
        """
        cfg = SolverConfig(
            num_groups=len(group_capacities),
            group_capacities=group_capacities,
            score_weights=score_weights,
            opt_mode=opt_mode,
            conflict_priority=conflict_priority,
            timeout_seconds=timeout_seconds,
            num_workers=config.SOLVER_NUM_WORKERS,
        )

        records = participants_df.to_dict("records")
        participants = [
            Participant(
                name=r.get(config.COL_NAME, "Unknown"),
                scores={
                    k: float(v)
                    for k, v in r.items()
                    if k.startswith(config.SCORE_PREFIX)
                },
                groupers=str(r.get(config.COL_GROUPER, "")),
                separators=str(r.get(config.COL_SEPARATOR, "")),
            )
            for r in records
        ]

        return run_optimization(participants, cfg, **kwargs)
