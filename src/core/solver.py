"""
Solver Module.

This module encapsulates the Constraint Programming logic used to solve the
group partitioning problem. It utilizes Google OR-Tools' CP-SAT solver to
find mathematically optimal distributions based on defined constraints.
"""

import math
import sys
import time
from ortools.sat.python import cp_model
from src.core import config


class SolutionPrinter(cp_model.CpSolverSolutionCallback):
    """
    Custom callback for the OR-Tools solver to print intermediate progress.
    """

    def __init__(self, start_time):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__start_time = start_time
        self.__solution_count = 0

    def on_solution_callback(self):
        """Called whenever a new solution is found."""
        current_time = time.time()
        obj = self.ObjectiveValue()
        self.__solution_count += 1
        elapsed = current_time - self.__start_time
        # \033[K clears the line from cursor to end
        sys.stdout.write(
            f"\r  > Found solution #{self.__solution_count} | "
            f"Objective (Deviation): {obj} | Time: {elapsed:.2f}s\033[K"
        )
        sys.stdout.flush()


def solve_with_ortools(
    participants: list[dict], num_groups: int, respect_stars: bool
) -> tuple[list[dict], bool]:
    """
    Constructs and solves the CP-SAT model for group balancing.

    The problem is modeled as follows:
    1.  **Variables**: Boolean assignments for each (person, group) pair.
    2.  **Constraints**:
        - Each person assigned to exactly one group.
        - Group sizes must be balanced (diff <= 1).
        - (Optional) 'Star' participants distributed evenly.
    3.  **Objective**:
        - Minimize the sum of absolute deviations of group sums from their
          theoretical target sums (scaled by group size).

    Args:
        participants (list[dict]): List of participant data.
        num_groups (int): Target number of groups.
        respect_stars (bool): Whether to enforce star separation constraints.

    Returns:
        tuple: (List of group dictionaries, Boolean success flag).
               Returns ([], False) if no solution is found.
    """
    if num_groups < 1:
        raise ValueError("num_groups must be at least 1")

    model = cp_model.CpModel()

    # --- 1. Data Preparation (Integer Scaling) ---
    # CP-SAT requires integers. We scale floats to preserve precision.
    num_people = len(participants)
    scores = [
        int(round(float(p[config.COL_SCORE]) * config.SCALE_FACTOR))
        for p in participants
    ]
    total_score = sum(scores)

    # Identify indices of 'Star' participants
    stars = [
        i
        for i, p in enumerate(participants)
        if str(p[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR)
    ]

    # --- 2. Group Size Pre-calculation ---
    # Determine the required sizes for groups to be balanced within 1.
    # Example: 10 people, 3 groups -> sizes [4, 3, 3]
    base_size = num_people // num_groups
    remainder = num_people % num_groups

    # Map group index to its required size to break symmetry and set exact targets
    group_sizes_map = {}
    for g in range(num_groups):
        if g < remainder:
            group_sizes_map[g] = base_size + 1
        else:
            group_sizes_map[g] = base_size

    # --- 3. Decision Variables ---
    # x[i, g] is 1 if person i is in group g, else 0
    x = {}
    for i in range(num_people):
        for g in range(num_groups):
            x[(i, g)] = model.NewBoolVar(f"assign_p{i}_g{g}")

    # --- 4. Constraints ---

    # Constraint A: Every person must be in exactly one group
    for i in range(num_people):
        model.Add(sum(x[(i, g)] for g in range(num_groups)) == 1)

    # Constraint B: Groups must match the pre-calculated sizes
    for g in range(num_groups):
        model.Add(sum(x[(i, g)] for i in range(num_people)) == group_sizes_map[g])

    # Constraint C: Star Separation (Optional)
    if respect_stars and stars:
        # Ceiling division to determine max stars per group
        max_stars_per_group = math.ceil(len(stars) / num_groups)
        for g in range(num_groups):
            model.Add(sum(x[(i, g)] for i in stars) <= max_stars_per_group)

    # --- 5. Objective Function ---
    # Minimize deviation from the ideal average.
    # To avoid floating point logic in the solver:
    # Ideal: GroupSum / GroupSize == TotalScore / NumPeople
    # Cross-multiply: GroupSum * NumPeople == TotalScore * GroupSize
    # Minimize: |(GroupSum * NumPeople) - (TotalScore * GroupSize)|

    abs_diffs = []

    # Upper bound for domain variable (Total Score * Num People)
    # This prevents overflow in constraint definition
    max_domain_val = total_score * num_people

    for g in range(num_groups):
        # Variable for the sum of scores in group g
        g_sum = model.NewIntVar(0, total_score, f"sum_group_{g}")
        model.Add(g_sum == sum(x[(i, g)] * scores[i] for i in range(num_people)))

        # Target value for this group size (TotalScore * GroupSize)
        target_val = total_score * group_sizes_map[g]

        # Actual value scaled (GroupSum * NumPeople)
        actual_val = model.NewIntVar(0, max_domain_val, f"actual_val_{g}")
        model.Add(actual_val == g_sum * num_people)

        # Difference variable (can be negative)
        diff = model.NewIntVar(-max_domain_val, max_domain_val, f"diff_{g}")
        model.Add(diff == actual_val - target_val)

        # Absolute difference variable (must be positive)
        abs_diff = model.NewIntVar(0, max_domain_val, f"abs_diff_{g}")
        model.AddAbsEquality(abs_diff, diff)

        abs_diffs.append(abs_diff)

    model.Minimize(sum(abs_diffs))

    # --- 6. Solve ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = config.SOLVER_TIMEOUT
    solver.parameters.num_search_workers = config.SOLVER_NUM_WORKERS

    # Use callback to show progress
    printer = SolutionPrinter(time.time())
    status = solver.Solve(model, printer)

    print("")  # Newline after progress output

    # --- 7. Reconstruct Results ---
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result_groups = []
        for g in range(num_groups):
            group_data = {"id": g + 1, "members": [], "current_sum": 0.0, "avg": 0.0}
            result_groups.append(group_data)

        for i in range(num_people):
            for g in range(num_groups):
                if solver.Value(x[(i, g)]) == 1:
                    result_groups[g]["members"].append(participants[i])

        # Recalculate float stats for final output
        for g in result_groups:
            # Use original float scores for display accuracy
            g_sum = sum(float(m[config.COL_SCORE]) for m in g["members"])
            count = len(g["members"])
            g["current_sum"] = g_sum
            g["avg"] = g_sum / count if count > 0 else 0.0

        return result_groups, True
    else:
        return [], False
