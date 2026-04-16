"""
Core optimization logic using Google OR-Tools.

This module defines the Constraint Programming (CP) model used to partition
participants into balanced groups based on their scores and 'star' status.
"""

import math
import sys
import time
from ortools.sat.python import cp_model
from src.core import config


class SolutionPrinter(cp_model.CpSolverSolutionCallback):
    """
    Callback to print intermediate solutions found by the solver.
    """

    def __init__(self, start_time):
        """
        Initializes the printer.

        Args:
            start_time (float): Timestamp when solving started.
        """
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__start_time = start_time
        self.__solution_count = 0
        self.__last_print_time = 0

    def on_solution_callback(self):
        """
        Called by the solver when a new valid solution is found.
        Prints the objective value and elapsed time.
        """
        self.__solution_count += 1
        current_time = time.time()

        # Throttle CLI prints
        if current_time - self.__last_print_time >= 0.1:
            obj = self.ObjectiveValue()
            elapsed = current_time - self.__start_time
            sys.stdout.write(
                f"\r  > Solutions Evaluated: {self.__solution_count} | "
                f"Objective (Deviation): {obj} | Time: {elapsed:.2f}s\033[K"
            )
            sys.stdout.flush()
            self.__last_print_time = current_time


def solve_with_ortools(
    participants: list[dict], group_capacities: list[int], respect_stars: bool
) -> tuple[list[dict], bool]:
    """
    Solves the group partitioning problem.

    Minimizes the sum of absolute deviations of group scores from the global average.
    Enforces exact group capacities and optionally distributes 'star' players evenly.

    Args:
        participants (list[dict]): List of participant data.
        group_capacities (list[int]): Exact capacity requirements for each group.
        respect_stars (bool): Whether to enforce even distribution of 'star' players.

    Returns:
        tuple[list[dict], bool]: A tuple containing the resulting group structure
        and a success boolean.
    """
    if not group_capacities:
        raise ValueError(
            "group_capacities must contain at least one capacity requirement."
        )

    if any(cap < 0 for cap in group_capacities):
        raise ValueError("group_capacities must not contain negative values.")

    model = cp_model.CpModel()

    num_people = len(participants)
    num_groups = len(group_capacities)

    if sum(group_capacities) != num_people:
        raise ValueError(
            "Sum of group capacities must equal the total number of participants."
        )

    scores = [
        int(round(float(p[config.COL_SCORE]) * config.SCALE_FACTOR))
        for p in participants
    ]
    total_score = sum(scores)

    stars = [
        i
        for i, p in enumerate(participants)
        if str(p[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR)
    ]

    x = {}
    for i in range(num_people):
        for g in range(num_groups):
            x[(i, g)] = model.NewBoolVar(f"assign_p{i}_g{g}")

    for i in range(num_people):
        model.AddExactlyOne([x[(i, g)] for g in range(num_groups)])

    for g in range(num_groups):
        model.Add(sum(x[(i, g)] for i in range(num_people)) == group_capacities[g])

    if respect_stars and stars and num_people > 0:
        for g in range(num_groups):
            expected = len(stars) * group_capacities[g] / num_people
            upper_g = min(group_capacities[g], math.ceil(expected))
            lower_g = min(group_capacities[g], math.floor(expected))
            model.Add(sum(x[(i, g)] for i in stars) <= upper_g)
            model.Add(sum(x[(i, g)] for i in stars) >= lower_g)

    abs_diffs = []
    max_domain_val = total_score * num_people

    g_sums = [model.NewIntVar(0, total_score, f"g_sum_{g}") for g in range(num_groups)]

    # --- SYMMETRY BREAKING ---
    for g1 in range(num_groups):
        for g2 in range(g1 + 1, num_groups):
            if group_capacities[g1] == group_capacities[g2]:
                model.Add(g_sums[g1] <= g_sums[g2])

    for g in range(num_groups):
        model.Add(g_sums[g] == sum(x[(i, g)] * scores[i] for i in range(num_people)))

        target_val = total_score * group_capacities[g]
        actual_val = model.NewIntVar(0, max_domain_val, f"actual_val_{g}")
        model.Add(actual_val == g_sums[g] * num_people)

        diff = model.NewIntVar(-max_domain_val, max_domain_val, f"diff_{g}")
        model.Add(diff == actual_val - target_val)

        abs_diff = model.NewIntVar(0, max_domain_val, f"abs_diff_{g}")
        model.AddAbsEquality(abs_diff, diff)

        abs_diffs.append(abs_diff)

    model.Minimize(sum(abs_diffs))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = config.SOLVER_TIMEOUT
    solver.parameters.num_search_workers = config.SOLVER_NUM_WORKERS

    printer = SolutionPrinter(time.time())
    status = solver.Solve(model, printer)

    print("")

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result_groups = []
        for g in range(num_groups):
            group_data = {"id": g + 1, "members": [], "current_sum": 0.0, "avg": 0.0}
            result_groups.append(group_data)

        for i in range(num_people):
            for g in range(num_groups):
                if solver.Value(x[(i, g)]) == 1:
                    result_groups[g]["members"].append(participants[i])

        for g in result_groups:
            g_sum = sum(float(m[config.COL_SCORE]) for m in g["members"])
            count = len(g["members"])
            g["current_sum"] = g_sum
            g["avg"] = g_sum / count if count > 0 else 0.0

        return result_groups, True
    else:
        return [], False
