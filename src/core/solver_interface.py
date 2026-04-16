"""
Interface for running the solver within a Streamlit environment.

This module provides thread-safe context handling to ensure that solver
updates can be rendered to the Streamlit UI during execution.
"""

import threading
import time
import math
import pandas as pd
from ortools.sat.python import cp_model
from src.core import config

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
    participants: list[dict], group_capacities: list[int], status_box
) -> pd.DataFrame | None:
    """
    Runs the optimization process and returns the result as a DataFrame.

    Args:
        participants (list[dict]): List of participant dictionaries.
        group_capacities (list[int]): Exact capacity requirements for each group.
        status_box: Streamlit placeholder for status updates.

    Returns:
        pd.DataFrame | None: A DataFrame with assigned groups, or None if no solution.
    """
    if not group_capacities:
        raise ValueError(
            "group_capacities must contain at least one capacity requirement."
        )

    if any(cap < 0 for cap in group_capacities):
        raise ValueError("group_capacities must not contain negative values.")

    model = cp_model.CpModel()

    col_score = config.COL_SCORE
    col_name = config.COL_NAME
    scale_factor = config.SCALE_FACTOR
    col_group = config.COL_GROUP

    num_people = len(participants)
    num_groups = len(group_capacities)

    if sum(group_capacities) != num_people:
        raise ValueError("Sum of group capacities must equal total participants.")

    scores = [int(round(float(p[col_score]) * scale_factor)) for p in participants]
    total_score = sum(scores)

    stars = [
        i
        for i, p in enumerate(participants)
        if str(p[col_name]).endswith(config.ADVANTAGE_CHAR)
    ]

    x = {}
    for i in range(num_people):
        for g in range(num_groups):
            x[(i, g)] = model.NewBoolVar(f"x_{i}_{g}")

    for i in range(num_people):
        model.AddExactlyOne([x[(i, g)] for g in range(num_groups)])

    for g in range(num_groups):
        model.Add(sum(x[(i, g)] for i in range(num_people)) == group_capacities[g])

    if stars and num_people > 0:
        for g in range(num_groups):
            expected = len(stars) * group_capacities[g] / num_people
            upper_g = min(group_capacities[g], math.ceil(expected))
            lower_g = min(group_capacities[g], math.floor(expected))
            model.Add(sum(x[(i, g)] for i in stars) <= upper_g)
            model.Add(sum(x[(i, g)] for i in stars) >= lower_g)

    abs_diffs = []
    max_domain = total_score * num_people

    # Define g_sums upfront so they can be used for symmetry breaking
    g_sums = [model.NewIntVar(0, total_score, f"g_sum_{g}") for g in range(num_groups)]

    # --- SYMMETRY BREAKING ---
    # Force identically sized groups to be ordered by their score sum.
    # This prevents the solver from redundantly evaluating mirrored configurations.
    for g1 in range(num_groups):
        for g2 in range(g1 + 1, num_groups):
            if group_capacities[g1] == group_capacities[g2]:
                model.Add(g_sums[g1] <= g_sums[g2])

    for g in range(num_groups):
        model.Add(g_sums[g] == sum(x[(i, g)] * scores[i] for i in range(num_people)))

        target = total_score * group_capacities[g]
        actual = model.NewIntVar(0, max_domain, f"act_{g}")
        model.Add(actual == g_sums[g] * num_people)

        diff = model.NewIntVar(-max_domain, max_domain, f"diff_{g}")
        model.Add(diff == actual - target)

        abs_diff = model.NewIntVar(0, max_domain, f"abs_{g}")
        model.AddAbsEquality(abs_diff, diff)
        abs_diffs.append(abs_diff)

    model.Minimize(sum(abs_diffs))

    solver_inst = cp_model.CpSolver()
    solver_inst.parameters.max_time_in_seconds = config.SOLVER_TIMEOUT
    solver_inst.parameters.num_search_workers = config.SOLVER_NUM_WORKERS

    cb = StreamlitSolverCallback(status_box)
    status = solver_inst.Solve(model, cb)

    # Force final render
    if cb.ctx:
        add_script_run_ctx(threading.current_thread(), cb.ctx)
    elapsed = time.time() - cb.start_time
    status_box.markdown(
        f"""
        **Solver Status:** ✅ Complete  
        Solutions Evaluated: `{cb.solution_count}`  
        Final Deviation Score: `{solver_inst.ObjectiveValue()}`  
        Total Time: `{elapsed:.2f}s`
        """
    )

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        df = pd.DataFrame(participants)
        df[col_group] = 0
        for i in range(num_people):
            for g in range(num_groups):
                if solver_inst.Value(x[(i, g)]):
                    df.at[i, col_group] = g + 1
        return df
    return None
