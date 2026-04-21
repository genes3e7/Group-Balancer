"""
Interface for running the solver within a Streamlit environment.

Provides thread-safe context handling to ensure solver status updates
can render live to the UI during deep search execution.
"""

import threading
import time
from typing import Any
import pandas as pd
from ortools.sat.python import cp_model
from src.core import config, solver

try:
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
except ImportError:
    try:
        from streamlit.scriptrunner import add_script_run_ctx, get_script_run_ctx
    except ImportError:

        def add_script_run_ctx(t: Any, c: Any = None) -> None:
            pass

        def get_script_run_ctx() -> Any:
            return None


class StreamlitSolverCallback(cp_model.CpSolverSolutionCallback):
    """Custom OR-Tools callback to pipe logs to Streamlit."""

    def __init__(self, status_placeholder: Any):
        """
        Args:
            status_placeholder: A Streamlit placeholder element.
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

            self.status_placeholder.markdown(
                f"""
                **Solver Status:** 🏃 Running (Optimizing & Proving)...  
                Solutions Found: `{self.solution_count}`  
                Current Weighted Deviation: `{obj}`  
                Time Elapsed: `{elapsed:.2f}s`
                """
            )
            self.last_update_time = current_time


def run_optimization(
    participants: list[dict],
    group_capacities: list[int],
    status_box: Any,
    timeout_limit: int,
    score_columns: list[str],
    score_weights: dict[str, float],
    opt_mode: str,
    conflict_priority: str,
) -> tuple[pd.DataFrame | None, int | None, float]:
    """
    Runs the optimization and surfaces results as a DataFrame safely.

    Args:
        participants (list[dict]): Participant dictionaries.
        group_capacities (list[int]): Exact capacity requirements.
        status_box: Streamlit placeholder for updates.
        timeout_limit (int): Solver max limit in seconds.
        score_columns (list[str]): Dimensions to balance.
        score_weights (dict[str, float]): Impact weight mapping.
        opt_mode (str): Optimization topology mode.
        conflict_priority (str): Tag collision strategy.

    Returns:
        tuple: (Assigned DataFrame or None, Status Code, Elapsed Time)
    """
    model, x, num_people, num_groups = solver.build_partition_model(
        participants,
        group_capacities,
        True,
        score_columns,
        score_weights,
        opt_mode,
        conflict_priority,
    )

    solver_inst = cp_model.CpSolver()
    solver_inst.parameters.max_time_in_seconds = timeout_limit
    solver_inst.parameters.num_search_workers = config.SOLVER_NUM_WORKERS

    cb = StreamlitSolverCallback(status_box)
    status = solver_inst.Solve(model, cb)

    if cb.ctx:
        add_script_run_ctx(threading.current_thread(), cb.ctx)
    elapsed = time.time() - cb.start_time

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        status_label = "Optimal" if status == cp_model.OPTIMAL else "Feasible (Timeout)"
        status_box.markdown(
            f"""
            **Solver Status:** ✅ Complete ({status_label})  
            Solutions Evaluated: `{cb.solution_count}`  
            Final Cost Objective: `{solver_inst.ObjectiveValue()}`  
            Total Time: `{elapsed:.2f}s`
            """
        )

        df = pd.DataFrame(participants)
        df[config.COL_GROUP] = 0
        for i in range(num_people):
            for g in range(num_groups):
                if solver_inst.Value(x[(i, g)]):
                    df.at[i, config.COL_GROUP] = g + 1
        return df, status, elapsed

    else:
        status_label = (
            "Infeasible" if status == cp_model.INFEASIBLE else "Unknown/Error"
        )
        status_box.markdown(
            f"""
            **Solver Status:** ❌ Failed ({status_label})  
            Solutions Evaluated: `{cb.solution_count}`  
            Total Time: `{elapsed:.2f}s`
            """
        )
        return None, status, elapsed
