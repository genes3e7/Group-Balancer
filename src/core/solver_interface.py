"""Interface for running the solver within a Streamlit environment.

Provides thread-safe context handling to ensure solver status updates
can render live to the UI during deep search execution.
"""

import threading
import time
from typing import Any

import pandas as pd
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

        def add_script_run_ctx(t: Any, c: Any = None) -> None:
            """Fallback for add_script_run_ctx if streamlit is not installed.

            Args:
                t: Thread object.
                c: Context object.
            """

        def get_script_run_ctx() -> Any:
            """Fallback for get_script_run_ctx if streamlit is not installed.

            Returns:
                Any: Always None.
            """
            return None


class StreamlitSolverCallback(cp_model.CpSolverSolutionCallback):
    """Custom OR-Tools callback to pipe logs to Streamlit."""

    def __init__(self, status_placeholder: Any) -> None:
        """Initializes the callback with a Streamlit status placeholder.

        Args:
            status_placeholder: A Streamlit placeholder object to update.
        """
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.status_placeholder = status_placeholder
        self.solution_count = 0
        self.start_time = time.time()
        self.last_update_time = 0.0
        self.ctx = get_script_run_ctx()

    def on_solution_callback(self) -> None:
        """Update UI with live progress variables."""
        self.solution_count += 1
        current_time = time.time()

        if current_time - self.last_update_time >= 0.25:
            if self.ctx:
                add_script_run_ctx(threading.current_thread(), self.ctx)

            obj = self.ObjectiveValue()
            elapsed = current_time - self.start_time

            if self.status_placeholder:
                self.status_placeholder.markdown(
                    f"**Solver Status:** 🏃 Running (Optimizing & Proving)... \n"
                    f"Solutions Found: `{self.solution_count}` \n"
                    f"Current Weighted Deviation: `{obj}` \n"
                    f"Time Elapsed: `{elapsed:.2f}s`",
                )
            self.last_update_time = current_time


def run_optimization(
    participants: list[Participant],
    cfg: SolverConfig,
    status_box: Any = None,
) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """Runs the optimization using Participant models and SolverConfig.

    Args:
        participants: List of participants.
        cfg: Solver configuration.
        status_box: Streamlit status placeholder.

    Returns:
        tuple: (Results dataframe or None, Status metrics dictionary).
    """
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

    cb = StreamlitSolverCallback(status_box)
    status = solver_inst.Solve(model, cb)

    if cb.ctx:
        add_script_run_ctx(threading.current_thread(), cb.ctx)
    elapsed = time.time() - start_time

    status_name = solver_inst.StatusName(status)
    metrics = {"status": status_name, "elapsed": elapsed, "raw_status": status}

    # 3. Results
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        if status_box:
            status_msg = (
                f"**Solver Status:** ✅ Complete ({status_name}) | "
                f"Time: `{elapsed:.2f}s`"
            )
            status_box.markdown(status_msg)

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
            }
            p_dict.update(p.scores)
            results.append(p_dict)

        return pd.DataFrame(results), metrics

    if status_box:
        status_box.error(f"Solver Status: ❌ Failed (Status: {status_name})")
    return None, metrics
