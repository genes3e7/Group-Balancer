import threading
import time
import math
import pandas as pd
from ortools.sat.python import cp_model
from src.core import config

# Robust import for Streamlit Context
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
    """Updates Streamlit UI in real-time during solving."""

    def __init__(self, status_placeholder):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.status_placeholder = status_placeholder
        self.solution_count = 0
        self.start_time = time.time()
        # Capture the context of the main Streamlit thread
        self.ctx = get_script_run_ctx()

    def on_solution_callback(self):
        # Attach the captured context to the current thread (OR-Tools worker)
        if self.ctx:
            add_script_run_ctx(threading.current_thread(), self.ctx)

        self.solution_count += 1
        current_time = time.time()
        obj = self.ObjectiveValue()
        elapsed = current_time - self.start_time

        # Update the UI placeholder
        self.status_placeholder.markdown(
            f"""
            **Solver Status:** 🏃 Running...  
            Solutions Found: `{self.solution_count}`  
            Current Deviation Score: `{obj}`  
            Time Elapsed: `{elapsed:.2f}s`
            """
        )


def run_optimization(participants, num_groups, status_box):
    """
    Executes the solver with the Streamlit callback.
    """
    model = cp_model.CpModel()

    # --- Data Prep ---
    col_score = config.COL_SCORE
    col_name = config.COL_NAME
    scale_factor = config.SCALE_FACTOR
    col_group = config.COL_GROUP

    num_people = len(participants)
    # Convert scores to integers for CP-SAT
    scores = [int(round(float(p[col_score]) * scale_factor)) for p in participants]
    total_score = sum(scores)

    # Identify Stars
    stars = [
        i
        for i, p in enumerate(participants)
        if str(p[col_name]).endswith(config.ADVANTAGE_CHAR)
    ]

    # --- Group Sizes ---
    base_size = num_people // num_groups
    remainder = num_people % num_groups
    group_sizes = {
        g: (base_size + 1 if g < remainder else base_size) for g in range(num_groups)
    }

    # --- Variables ---
    x = {}
    for i in range(num_people):
        for g in range(num_groups):
            x[(i, g)] = model.NewBoolVar(f"x_{i}_{g}")

    # --- Constraints ---
    # 1. Every person in exactly one group
    for i in range(num_people):
        model.Add(sum(x[(i, g)] for g in range(num_groups)) == 1)

    # 2. Group sizes match targets
    for g in range(num_groups):
        model.Add(sum(x[(i, g)] for i in range(num_people)) == group_sizes[g])

    # 3. Star Separation
    if stars:
        max_stars = math.ceil(len(stars) / num_groups)
        min_stars = len(stars) // num_groups
        for g in range(num_groups):
            model.Add(sum(x[(i, g)] for i in stars) <= max_stars)
            model.Add(sum(x[(i, g)] for i in stars) >= min_stars)

    # --- Objective ---
    abs_diffs = []
    max_domain = total_score * num_people
    for g in range(num_groups):
        g_sum = model.NewIntVar(0, total_score, f"g_sum_{g}")
        model.Add(g_sum == sum(x[(i, g)] * scores[i] for i in range(num_people)))

        target = total_score * group_sizes[g]
        actual = model.NewIntVar(0, max_domain, f"act_{g}")
        model.Add(actual == g_sum * num_people)

        diff = model.NewIntVar(-max_domain, max_domain, f"diff_{g}")
        model.Add(diff == actual - target)

        abs_diff = model.NewIntVar(0, max_domain, f"abs_{g}")
        model.AddAbsEquality(abs_diff, diff)
        abs_diffs.append(abs_diff)

    model.Minimize(sum(abs_diffs))

    # --- Solve ---
    solver_inst = cp_model.CpSolver()
    solver_inst.parameters.max_time_in_seconds = config.SOLVER_TIMEOUT
    solver_inst.parameters.num_search_workers = config.SOLVER_NUM_WORKERS

    cb = StreamlitSolverCallback(status_box)
    status = solver_inst.Solve(model, cb)

    # --- Reconstruct ---
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        df = pd.DataFrame(participants)
        df[col_group] = 0
        for i in range(num_people):
            for g in range(num_groups):
                if solver_inst.Value(x[(i, g)]):
                    df.at[i, col_group] = g + 1
        return df
    return None
