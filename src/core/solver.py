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
    Custom callback for the OR-Tools solver to print intermediate search progress.
    """

    def __init__(self, start_time):
        """
        Initialize the solution printer.

        Args:
            start_time (float): The timestamp when the solver started.
        """
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__start_time = start_time
        self.__solution_count = 0

    def on_solution_callback(self):
        """
        Handle the event when a new feasible solution is found.

        Calculates elapsed time and prints the current objective value
        to standard output.
        """
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
    Construct and solve the CP-SAT model for group balancing.

    The problem is modeled as follows:
    1.  **Variables**: Boolean assignments for each (person, group) pair.
    2.  **Constraints**:
        - Each person assigned to exactly one group.
        - Group sizes must be balanced (difference <= 1).
        - (Optional) 'Star' participants distributed evenly.
    3.  **Objective**:
        - Minimize the sum of absolute deviations of group sums from their
          theoretical target sums.

    Args:
        participants (list[dict]): List of participant dictionaries containing
                                   name and score data.
        num_groups (int): The target number of groups to create.
        respect_stars (bool): If True, enforces even distribution of participants
                              whose names end with the advantage character.

    Returns:
        tuple: A tuple containing:
            - list[dict]: A list of group dictionaries describing the solution.
                          Returns empty list if no solution is found.
            - bool: True if a feasible or optimal solution was found, else False.

    Raises:
        ValueError: If num_groups is less than 1.
    """
    if num_groups < 1:
        raise ValueError("num_groups must be at least 1")

    model = cp_model.CpModel()

    # --- 1. Data Preparation ---
    # CP-SAT requires integer inputs. Scale scores to preserve precision.
    num_people = len(participants)
    scores = [
        int(round(float(p[config.COL_SCORE]) * config.SCALE_FACTOR))
        for p in participants
    ]
    total_score = sum(scores)

    # Identify indices of 'Star' participants for constraint application
    stars = [
        i
        for i, p in enumerate(participants)
        if str(p[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR)
    ]

    # --- 2. Group Size Calculation ---
    # Calculate required group sizes to ensure count balance (difference <= 1).
    base_size = num_people // num_groups
    remainder = num_people % num_groups

    # Map each group index to its specific target size.
    # Groups 0 to remainder-1 get base_size + 1.
    group_sizes_map = {}
    for g in range(num_groups):
        if g < remainder:
            group_sizes_map[g] = base_size + 1
        else:
            group_sizes_map[g] = base_size

    # --- 3. Decision Variables ---
    # x[i, g] is a boolean variable: 1 if person i is in group g, else 0.
    x = {}
    for i in range(num_people):
        for g in range(num_groups):
            x[(i, g)] = model.NewBoolVar(f"assign_p{i}_g{g}")

    # --- 4. Constraints ---

    # Constraint: Each participant must be assigned to exactly one group.
    for i in range(num_people):
        model.Add(sum(x[(i, g)] for g in range(num_groups)) == 1)

    # Constraint: Each group must contain the exact number of participants calculated earlier.
    for g in range(num_groups):
        model.Add(sum(x[(i, g)] for i in range(num_people)) == group_sizes_map[g])

    # Constraint: Distribute 'Star' participants evenly across groups if requested.
    if respect_stars and stars:
        # Calculate maximum allowed stars per group to enforce distribution.
        max_stars_per_group = math.ceil(len(stars) / num_groups)
        for g in range(num_groups):
            model.Add(sum(x[(i, g)] for i in stars) <= max_stars_per_group)

    # --- 5. Objective Function ---
    # Objective: Minimize deviation from ideal average score.
    # Formula derived to avoid floating point arithmetic:
    # Minimize |(GroupSum * NumPeople) - (TotalScore * GroupSize)|

    abs_diffs = []

    # Define upper bound for domain variables to prevent overflow.
    max_domain_val = total_score * num_people

    for g in range(num_groups):
        # Variable representing the sum of scores in group g
        g_sum = model.NewIntVar(0, total_score, f"sum_group_{g}")
        model.Add(g_sum == sum(x[(i, g)] * scores[i] for i in range(num_people)))

        # Calculate target value scaled by total people
        target_val = total_score * group_sizes_map[g]

        # Calculate actual value scaled by number of people
        actual_val = model.NewIntVar(0, max_domain_val, f"actual_val_{g}")
        model.Add(actual_val == g_sum * num_people)

        # Calculate signed difference
        diff = model.NewIntVar(-max_domain_val, max_domain_val, f"diff_{g}")
        model.Add(diff == actual_val - target_val)

        # Calculate absolute difference
        abs_diff = model.NewIntVar(0, max_domain_val, f"abs_diff_{g}")
        model.AddAbsEquality(abs_diff, diff)

        abs_diffs.append(abs_diff)

    model.Minimize(sum(abs_diffs))

    # --- 6. Solver Execution ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = config.SOLVER_TIMEOUT
    solver.parameters.num_search_workers = config.SOLVER_NUM_WORKERS

    printer = SolutionPrinter(time.time())
    status = solver.Solve(model, printer)

    print("")  # Output formatting

    # --- 7. Result Reconstruction ---
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result_groups = []
        for g in range(num_groups):
            group_data = {"id": g + 1, "members": [], "current_sum": 0.0, "avg": 0.0}
            result_groups.append(group_data)

        # Map solver variables back to participant data
        for i in range(num_people):
            for g in range(num_groups):
                if solver.Value(x[(i, g)]) == 1:
                    result_groups[g]["members"].append(participants[i])

        # Calculate final floating point statistics for display
        for g in result_groups:
            g_sum = sum(float(m[config.COL_SCORE]) for m in g["members"])
            count = len(g["members"])
            g["current_sum"] = g_sum
            g["avg"] = g_sum / count if count > 0 else 0.0

        return result_groups, True
    else:
        return [], False
