"""
Interface for running the solver within a Streamlit environment.

This module provides thread-safe context handling to ensure that solver
updates can be rendered to the Streamlit UI during execution.
"""

import threading
import time
import pandas as pd
from ortools.sat.python import cp_model
from src.core import config, solver

try:
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
except ImportError:
    try:
        from streamlit.scriptrunner import add_script_run_ctx, get_script_run_ctx
    except ImportError:

        def add_script_run_ctx(t, c=None):
            pass

        def get_script_run_ctx():
            return None


class StreamlitSolverCallback(cp_model.CpSolverSolutionCallback):
    """
    A custom OR-Tools callback that updates a Streamlit UI element.
    """

    def __init__(self, status_placeholder):
        """
        Args:
            status_placeholder: A Streamlit placeholder element to render updates.
        """
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.status_placeholder = status_placeholder
        self.solution_count = 0
        self.start_time = time.time()
        self.last_update_time = 0
        self.ctx = get_script_run_ctx()

    def on_solution_callback(self):
        """
        Executed whenever a solution is found. Updates the UI with progress.
        """
        self.solution_count += 1
        current_time = time.time()

        # Throttle UI renders to max ~4 updates per second
        if current_time - self.last_update_time >= 0.25:
            if self.ctx:
                add_script_run_ctx(threading.current_thread(), self.ctx)

            obj = self.ObjectiveValue()
            elapsed = current_time - self.start_time

            self.status_placeholder.markdown(
                f"""
                **Solver Status:** 🏃 Running (Optimizing & Proving)...  
                Solutions Found: `{self.solution_count}`  
                Current Deviation Score: `{obj}`  
                Time Elapsed: `{elapsed:.2f}s`
                """
            )
            self.last_update_time = current_time


def run_optimization(
    participants: list[dict],
    group_capacities: list[int],
    status_box,
    timeout_limit: int,
) -> tuple[pd.DataFrame | None, int | None, float]:
    """
    Runs the optimization process and returns the result as a DataFrame along with the status and elapsed time.

    Args:
        participants (list[dict]): List of participant dictionaries.
        group_capacities (list[int]): Exact capacity requirements for each group.
        status_box: Streamlit placeholder for status updates.
        timeout_limit (int): Maximum solver runtime in seconds.

    Returns:
        tuple: (DataFrame of assignments or None, CP Solver Status Code, Elapsed Time in seconds)
    """
    model, x, num_people, num_groups = solver.build_partition_model(
        participants, group_capacities, respect_stars=True
    )

    solver_inst = cp_model.CpSolver()
    solver_inst.parameters.max_time_in_seconds = timeout_limit
    solver_inst.parameters.num_search_workers = config.SOLVER_NUM_WORKERS

    cb = StreamlitSolverCallback(status_box)
    status = solver_inst.Solve(model, cb)

    # Force final render context
    if cb.ctx:
        add_script_run_ctx(threading.current_thread(), cb.ctx)
    elapsed = time.time() - cb.start_time

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        status_label = "Optimal" if status == cp_model.OPTIMAL else "Feasible (Timeout)"
        status_box.markdown(
            f"""
            **Solver Status:** ✅ Complete ({status_label})  
            Solutions Evaluated: `{cb.solution_count}`  
            Final Deviation Score: `{solver_inst.ObjectiveValue()}`  
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
