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
    Participant,
    SolverConfig,
)
from src.core.solver import apply_solver_tuning

try:
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
except ImportError:
    try:
        from streamlit.scriptrunner import add_script_run_ctx, get_script_run_ctx
    except ImportError:  # pragma: no cover

        def add_script_run_ctx(_: object, c: object = None) -> None:
            """Fallback for add_script_run_ctx."""

        def get_script_run_ctx() -> Any:  # noqa: ANN401
            """Fallback for get_script_run_ctx."""
            return None


# UI-only normalization factor to scale large objective values for display
_DISPLAY_OBJECTIVE_DIVISOR_FACTOR = 100

# Performance Tuning
UPDATE_INTERVAL_SECONDS = 0.25


class StreamlitSolverCallback(cp_model.CpSolverSolutionCallback):
    """Custom OR-Tools callback to pipe logs to Streamlit."""

    def __init__(self, status_placeholder: Any, num_people: int) -> None:  # noqa: ANN401
        """Initializes the callback with a Streamlit status placeholder.

        Args:
            status_placeholder: A Streamlit placeholder object to update.
            num_people (int): Total count of participants for scaling metrics.
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
        Streamlit status placeholder with a progress summary.
        """
        self.solution_count += 1
        current_time = time.time()

        if current_time - self.last_update_time >= UPDATE_INTERVAL_SECONDS:
            if self.ctx:
                add_script_run_ctx(threading.current_thread(), self.ctx)

            obj = self.ObjectiveValue()
            elapsed = max(0.01, current_time - self.start_time)

            # Scale down to human readable units
            display_obj = obj / (
                config.SCALE_FACTOR
                * self.num_people
                * _DISPLAY_OBJECTIVE_DIVISOR_FACTOR
            )

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
    status_box: Any = None,  # noqa: ANN401
) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """Runs the optimization using Participant models and SolverConfig.

    Orchestrates the entire solver lifecycle and updates the UI via the
    provided status_box placeholder.

    Args:
        participants (list[Participant]): List of strongly-typed models.
        cfg (SolverConfig): The solver configuration parameters.
        status_box (Any): Optional Streamlit placeholder for updates.

    Returns:
        tuple[pd.DataFrame | None, dict[str, Any]]: Results and metrics.
    """
    if status_box:
        status_box.info("Solver Status: ⏳ Initializing...")

    start_time = time.time()
    builder = solver.ConstraintBuilder(participants, cfg)
    builder.build_variables()

    groupers, separators = solver.TagProcessor.process_participants(
        participants,
        cfg.conflict_priority,
    )
    builder.add_separator_penalties(separators)

    strategy = solver.AdvancedScoring()
    builder.add_scoring_objectives(strategy)
    builder.add_cohesion_penalties(groupers)
    builder.add_participant_symmetry_breaking()
    builder.add_solution_hints()
    builder.add_branching_strategy()

    model = builder.get_model()

    solver_inst = cp_model.CpSolver()
    apply_solver_tuning(solver_inst, cfg)

    cb = StreamlitSolverCallback(status_box, len(participants))
    status = solver_inst.Solve(model, cb)

    if cb.ctx:
        add_script_run_ctx(threading.current_thread(), cb.ctx)
    elapsed = time.time() - start_time

    status_name = solver_inst.StatusName(status)
    error_msg = _get_solver_error_msg(status, status_name)

    metrics = {
        "status": status_name,
        "elapsed": elapsed,
        "raw_status": status,
        "error": error_msg,
    }

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        if status_box:
            _render_success_status(
                status_box, status_name, elapsed, solver_inst, len(participants)
            )

        results = _build_results_list(participants, cfg, builder, solver_inst)
        result_df = pd.DataFrame(results)
        _attach_metadata(result_df, cfg)
        return result_df, metrics

    if status_box:
        _render_failure_status(status_box, status_name, error_msg)
    return None, metrics


def _get_solver_error_msg(status: int, status_name: str) -> str | None:
    """Derives a user-friendly error message from solver status."""
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    if status_name == "MODEL_INVALID":
        return (
            "The solver model is invalid. This often happens due to "
            "numerical overflows from extremely large weights or "
            "conflicting constraints."
        )
    if status_name == "INFEASIBLE":
        return (
            "No solution exists that satisfies all hard constraints "
            "(capacities and separator tags)."
        )
    return f"Solver stopped with status: {status_name}"


def _render_success_status(
    status_box: Any,  # noqa: ANN401
    status_name: str,
    elapsed: float,
    solver_inst: Any,  # noqa: ANN401
    num_p: int,
) -> None:
    """Renders success metrics to the status box."""
    if not status_box:
        return

    with (
        status_box,
        st.status(f"✅ Optimization Complete ({status_name})", expanded=False),
    ):
        st.write(f"Computation time: {elapsed:.2f}s")
        display_obj = solver_inst.ObjectiveValue() / (
            config.SCALE_FACTOR * num_p * _DISPLAY_OBJECTIVE_DIVISOR_FACTOR
        )
        st.write(f"Final weighted objective: {display_obj:.4f}")


def _render_failure_status(
    status_box: Any,  # noqa: ANN401
    status_name: str,
    error_msg: str | None,
) -> None:
    """Renders failure messages to the status box."""
    if not status_box:
        return

    with (
        status_box,
        st.status(f"❌ Optimization Failed ({status_name})", state="error"),
    ):
        if error_msg:
            st.error(error_msg)
        else:
            st.write(f"Solver stopped with status: {status_name}")


def _build_results_list(
    participants: list[Participant],
    cfg: SolverConfig,
    builder: Any,  # noqa: ANN401
    solver_inst: Any,  # noqa: ANN401
) -> list[dict]:
    """Constructs the raw results list from solver assignments."""
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
            "participant_fingerprint": p.fingerprint,
        }
        p_dict.update(p.scores)
        results.append(p_dict)
    return results


def _attach_metadata(df: pd.DataFrame, cfg: SolverConfig) -> None:
    """Attaches solver configuration metadata to the result DataFrame."""
    df.attrs["score_weights"] = dict(cfg.score_weights)
    df.attrs["conflict_priority"] = cfg.conflict_priority
    df.attrs["group_capacities"] = list(cfg.group_capacities)
    df.attrs["grouper_weight"] = cfg.grouper_weight
    df.attrs["separator_weight"] = cfg.separator_weight
