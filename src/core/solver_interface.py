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
        self.ctx = get_script_run_ctx()

    def on_solution_callback(self):
        """
        Executed whenever a solution is found. Updates the UI with progress.
        """
        if self.ctx:
            add_script_run_ctx(threading.current_thread(), self.ctx)

        self.solution_count += 1
        current_time = time.time()
        obj = self.ObjectiveValue()
        elapsed = current_time - self.start_time

        self.status_placeholder.markdown(
            f"""
            **Solver Status:** 🏃 Running...  
            Solutions Found: `{self.solution_count}`  
            Current Deviation Score: `{obj}`  
            Time Elapsed: `{elapsed:.2f}s`
            """
        )


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
        model.Add(sum(x[(i, g)] for g in range(num_groups)) == 1)

    for g in range(num_groups):
        model.Add(sum(x[(i, g)] for i in range(num_people)) == group_capacities[g])

    if stars:
        max_stars = math.ceil(len(stars) / num_groups)
        min_stars = len(stars) // num_groups
        for g in range(num_groups):
            upper_g = min(max_stars, group_capacities[g])
            lower_g = min(min_stars, group_capacities[g])
            model.Add(sum(x[(i, g)] for i in stars) <= upper_g)
            model.Add(sum(x[(i, g)] for i in stars) >= lower_g)

    abs_diffs = []
    max_domain = total_score * num_people
    for g in range(num_groups):
        g_sum = model.NewIntVar(0, total_score, f"g_sum_{g}")
        model.Add(g_sum == sum(x[(i, g)] * scores[i] for i in range(num_people)))

        target = total_score * group_capacities[g]
        actual = model.NewIntVar(0, max_domain, f"act_{g}")
        model.Add(actual == g_sum * num_people)

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

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        df = pd.DataFrame(participants)
        df[col_group] = 0
        for i in range(num_people):
            for g in range(num_groups):
                if solver_inst.Value(x[(i, g)]):
                    df.at[i, col_group] = g + 1
        return df
    return None
