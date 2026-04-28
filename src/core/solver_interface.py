"""Interface for running the solver within a Streamlit environment.

Provides thread-safe context handling to ensure solver status updates
can render live to the UI during deep search execution.
"""

import threading
import time
from typing import Any

import pandas as pd
import streamlit as st
from ortools.sat.python import cp_model

from src.core import config, solver
from src.core.models import (
    OptimizationMode,
    Participant,
    SolverConfig,
)

try:
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
except ImportError:
    try:
        from streamlit.scriptrunner import add_script_run_ctx, get_script_run_ctx
    except ImportError:

        def add_script_run_ctx(_: Any, c: Any = None) -> None:
            """Fallback for add_script_run_ctx if streamlit is not installed."""

        def get_script_run_ctx() -> Any:
            """Fallback for get_script_run_ctx if streamlit is not installed."""
            return None


class StreamlitSolverCallback(cp_model.CpSolverSolutionCallback):
    """Custom OR-Tools callback to pipe logs to Streamlit."""

    def __init__(self, status_placeholder: Any, num_people: int) -> None:
        """Initializes the callback with a Streamlit status placeholder.

        Args:
            status_placeholder: A Streamlit placeholder object to update.
            num_people: Total count of participants for scaling metrics.
        """
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.status_placeholder = status_placeholder
        self.num_people = max(1, num_people)
        self.solution_count = 0
        self.start_time = time.time()
        self.last_update_time = 0.0
        self.ctx = get_script_run_ctx()

    def on_solution_callback(self) -> None:
        """Update UI with live progress variables.

        Calculates elapsed time and current objective value, then updates the
        Streamlit status placeholder with a progress summary including solution
        count and weighted deviation.
        """
        self.solution_count += 1
        current_time = time.time()

        if current_time - self.last_update_time >= 0.25:
            if self.ctx:
                add_script_run_ctx(threading.current_thread(), self.ctx)

            obj = self.ObjectiveValue()
            elapsed = max(0.01, current_time - self.start_time)

            # Scale down to human readable units (Weighted Average Absolute Error)
            display_obj = obj / (config.SCALE_FACTOR * self.num_people * 100)

            if self.status_placeholder:
                with self.status_placeholder.container():
                    st.markdown("### ⚙️ Optimization Progress")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Solutions", self.solution_count)
                    m2.metric("Weighted Objective", f"{display_obj:.4f}")
                    m3.metric("Time", f"{elapsed:.1f}s")
            self.last_update_time = current_time


def run_optimization(
    participants: list[Participant],
    cfg: SolverConfig,
    status_box: Any = None,
) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """Runs the optimization using Participant models and SolverConfig.

    Orchestrates the entire solver lifecycle: model building, constraint
    addition, scoring strategy execution, and the final solve process.
    Updates the UI via the provided status_box placeholder.

    Args:
        participants: List of strongly-typed Participant models.
        cfg: The solver configuration parameters.
        status_box: Optional Streamlit placeholder for live progress updates.

    Returns:
        A tuple of (results_df, metrics_dict). results_df is None if the
        solver fails to find any feasible solution.
    """
    if status_box:
        status_box.info("Solver Status: ⏳ Initializing...")

    start_time = time.time()
    # 1. Build Model using Builder
    builder = solver.ConstraintBuilder(participants, cfg)
    builder.build_variables()

    groupers, separators = solver.TagProcessor.process_participants(
        participants,
        cfg.conflict_priority,
    )
    builder.add_pigeonhole_constraints(separators)

    strategy = (
        solver.AdvancedScoring()
        if cfg.opt_mode == OptimizationMode.ADVANCED
        else solver.SimpleScoring()
    )
    builder.add_scoring_objectives(strategy)
    builder.add_cohesion_penalties(groupers)

    model = builder.get_model()

    # 2. Solve with Callback
    solver_inst = cp_model.CpSolver()
    solver_inst.parameters.max_time_in_seconds = float(cfg.timeout_seconds)
    solver_inst.parameters.num_search_workers = cfg.num_workers

    cb = StreamlitSolverCallback(status_box, len(participants))
    status = solver_inst.Solve(model, cb)

    if cb.ctx:
        add_script_run_ctx(threading.current_thread(), cb.ctx)
    elapsed = time.time() - start_time

    status_name = solver_inst.StatusName(status)
    error_msg = None
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        if status_name == "MODEL_INVALID":
            error_msg = (
                "The solver model is invalid. This often happens due to "
                "numerical overflows from extremely large weights or "
                "conflicting constraints."
            )
        elif status_name == "INFEASIBLE":
            error_msg = (
                "No solution exists that satisfies all hard constraints "
                "(capacities and separator tags)."
            )
        else:
            error_msg = f"Solver stopped with status: {status_name}"

    metrics = {
        "status": status_name,
        "elapsed": elapsed,
        "raw_status": status,
        "error": error_msg,
    }

    # 3. Results
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        if status_box:
            with status_box:
                with st.status(
                    f"✅ Optimization Complete ({status_name})", expanded=False
                ):
                    st.write(f"Computation time: {elapsed:.2f}s")
                    display_obj = solver_inst.ObjectiveValue() / (
                        config.SCALE_FACTOR * len(participants) * 100
                    )
                    st.write(f"Final weighted objective: {display_obj:.4f}")

        results = []
        for i, p in enumerate(participants):
            assigned_group = -1
            for g in range(cfg.num_groups):
                if solver_inst.Value(builder.x[(i, g)]) == 1:
                    assigned_group = g + 1
                    break

            p_dict = {
                config.COL_NAME: p.name,
                config.COL_GROUP: assigned_group,
                config.COL_GROUPER: p.groupers,
                config.COL_SEPARATOR: p.separators,
                "_original_index": p.original_index,
            }
            p_dict.update(p.scores)
            results.append(p_dict)

        return pd.DataFrame(results), metrics

    if status_box:
        with status_box:
            with st.status(f"❌ Optimization Failed ({status_name})", state="error"):
                if error_msg:
                    st.error(error_msg)
                else:
                    st.write(f"Solver stopped with status: {status_name}")
    return None, metrics
