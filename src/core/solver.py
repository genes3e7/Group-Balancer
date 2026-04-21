"""
Core optimization logic using Google OR-Tools.

This module defines the Constraint Programming (CP) model used to partition
participants into balanced groups using Simple/Advanced modes and Pigeonhole constraints.
"""

import math
import sys
import time
from ortools.sat.python import cp_model
from src.core import config


class SolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Callback to print intermediate solutions found by the solver."""

    def __init__(self, start_time: float):
        """
        Initializes the printer.

        Args:
            start_time (float): Timestamp when solving started.
        """
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__start_time = start_time
        self.__solution_count = 0
        self.__last_print_time = 0.0

    def on_solution_callback(self) -> None:
        """Called by the solver when a new valid solution is found."""
        self.__solution_count += 1
        current_time = time.time()

        if current_time - self.__last_print_time >= 0.1:
            obj = self.ObjectiveValue()
            elapsed = current_time - self.__start_time
            sys.stdout.write(
                f"\r  > Solutions Evaluated: {self.__solution_count} | "
                f"Objective: {obj} | Time: {elapsed:.2f}s\033[K"
            )
            sys.stdout.flush()
            self.__last_print_time = current_time


def build_partition_model(
    participants: list[dict],
    group_capacities: list[int],
    respect_stars: bool,
    score_columns: list[str],
    score_weights: dict[str, float],
    opt_mode: str = "Advanced",
    conflict_priority: str = "Groupers",
) -> tuple[cp_model.CpModel, dict, int, int]:
    """
    Constructs the Constraint Programming model for the group balancer.

    Args:
        participants (list[dict]): List of participant data.
        group_capacities (list[int]): Exact capacity requirements for each group.
        respect_stars (bool): Whether to enforce even distribution of 'star' players.
        score_columns (list[str]): The continuous score dimensions to balance.
        score_weights (dict[str, float]): Scalar multipliers for each score dimension.
        opt_mode (str): 'Simple' (pre-aggregated) or 'Advanced' (multi-dimensional).
        conflict_priority (str): 'Groupers' or 'Separators' resolution logic.

    Returns:
        tuple: (model, x_vars, num_people, num_groups)

    Raises:
        ValueError: If capacities are invalid or mathematically contradictory.
    """
    if not group_capacities or any(cap < 0 for cap in group_capacities):
        raise ValueError("group_capacities must be valid non-negative requirements.")

    num_people = len(participants)
    num_groups = len(group_capacities)

    if sum(group_capacities) != num_people:
        raise ValueError("Sum of group capacities must equal total participants.")

    model = cp_model.CpModel()

    # --- 1. Variable Initialization ---
    x = {}
    for i in range(num_people):
        for g in range(num_groups):
            x[(i, g)] = model.NewBoolVar(f"assign_p{i}_g{g}")
        model.AddExactlyOne([x[(i, g)] for g in range(num_groups)])

    for g in range(num_groups):
        model.Add(sum(x[(i, g)] for i in range(num_people)) == group_capacities[g])

    # --- 2. Star Constraints ---
    stars = [
        i
        for i, p in enumerate(participants)
        if str(p.get(config.COL_NAME, "")).endswith(config.ADVANTAGE_CHAR)
    ]
    if respect_stars and stars and num_people > 0:
        for g in range(num_groups):
            expected = len(stars) * group_capacities[g] / num_people
            model.Add(sum(x[(i, g)] for i in stars) <= math.ceil(expected))
            model.Add(sum(x[(i, g)] for i in stars) >= math.floor(expected))

    # --- 3. Tag Parsing & Conflict Resolution ---
    grouper_sets = {}
    separator_sets = {}
    for i, p in enumerate(participants):
        g_tags = [
            t.strip()
            for t in str(p.get(config.COL_GROUPER, "")).split(",")
            if t.strip()
        ]
        s_tags = [
            t.strip()
            for t in str(p.get(config.COL_SEPARATOR, "")).split(",")
            if t.strip()
        ]
        for tag in g_tags:
            grouper_sets.setdefault(tag, set()).add(i)
        for tag in s_tags:
            separator_sets.setdefault(tag, set()).add(i)

    if conflict_priority.startswith("Groupers"):
        for s_tag, s_set in separator_sets.items():
            for g_tag, g_set in grouper_sets.items():
                overlap = s_set.intersection(g_set)
                if len(overlap) > 1:
                    s_set.difference_update(overlap)
    else:
        for g_tag, g_set in list(grouper_sets.items()):
            for s_tag, s_set in separator_sets.items():
                overlap = g_set.intersection(s_set)
                if len(overlap) > 1:
                    g_set.difference_update(overlap)

    # --- 4. Pigeonhole Spread (Separators) ---
    for s_tag, s_set in separator_sets.items():
        if not s_set:
            continue
        limit = math.ceil(len(s_set) / num_groups)
        for g in range(num_groups):
            model.Add(sum(x[(i, g)] for i in s_set) <= limit)

    # --- 5. Fractional Cohesion (Groupers) ---
    cohesion_penalties = []
    base_cohesion_penalty = 10**9  # Massive penalty to override soft scoring
    for g_tag, g_set in grouper_sets.items():
        if len(g_set) <= 1:
            continue
        for g in range(num_groups):
            used = model.NewBoolVar(f"used_{g_tag}_{g}")
            model.AddMaxEquality(used, [x[(i, g)] for i in g_set])
            # Tie-breaker: Prioritize fitting into smaller groups to preserve big groups
            capacity_penalty = group_capacities[g] * 1000
            cohesion_penalties.append(used * (base_cohesion_penalty + capacity_penalty))

    # --- 6. Scoring Mode Evaluation ---
    abs_diffs = []
    active_score_cols = (
        ["_SIMPLE_TOTAL_"] if opt_mode.startswith("Simple") else score_columns
    )

    for col_idx, col in enumerate(active_score_cols):
        if col == "_SIMPLE_TOTAL_":
            scores = [
                int(
                    round(
                        sum(
                            float(p.get(c, 0)) * score_weights.get(c, 1.0)
                            for c in score_columns
                        )
                        * config.SCALE_FACTOR
                    )
                )
                for p in participants
            ]
            weight_m = 100
        else:
            scores = [
                int(round(float(p.get(col, 0)) * config.SCALE_FACTOR))
                for p in participants
            ]
            weight_m = int(round(score_weights.get(col, 1.0) * 100))

        total_score = sum(scores)
        min_sum = sum(s for s in scores if s < 0)
        max_sum = sum(s for s in scores if s > 0)

        if min_sum == 0 and max_sum == 0:
            continue

        g_sums = [
            model.NewIntVar(min_sum, max_sum, f"g_sum_{col}_{g}")
            for g in range(num_groups)
        ]

        # Symmetry breaking
        if col_idx == 0:
            for g1 in range(num_groups):
                for g2 in range(g1 + 1, num_groups):
                    if group_capacities[g1] == group_capacities[g2]:
                        model.Add(g_sums[g1] <= g_sums[g2])

        diff_bound = max(1, (max_sum - min_sum) * num_people * 2)

        for g in range(num_groups):
            model.Add(
                g_sums[g] == sum(x[(i, g)] * scores[i] for i in range(num_people))
            )

            target_val = total_score * group_capacities[g]
            actual_val = model.NewIntVar(
                min_sum * num_people, max_sum * num_people, f"act_{col}_{g}"
            )
            model.Add(actual_val == g_sums[g] * num_people)

            diff = model.NewIntVar(-diff_bound, diff_bound, f"diff_{col}_{g}")
            model.Add(diff == actual_val - target_val)

            abs_diff = model.NewIntVar(0, diff_bound, f"abs_{col}_{g}")
            model.AddAbsEquality(abs_diff, diff)

            w_diff = model.NewIntVar(0, diff_bound * 10000, f"w_diff_{col}_{g}")
            model.Add(w_diff == abs_diff * weight_m)
            abs_diffs.append(w_diff)

    model.Minimize(sum(abs_diffs) + sum(cohesion_penalties))

    return model, x, num_people, num_groups


def solve_with_ortools(
    participants: list[dict],
    group_capacities: list[int],
    respect_stars: bool,
    score_columns: list[str],
    score_weights: dict[str, float],
    opt_mode: str = "Advanced",
    conflict_priority: str = "Groupers",
) -> tuple[list[dict], bool]:
    """
    Main orchestration function to execute the solver and format the groupings.

    Args:
        participants (list[dict]): Participant dictionaries.
        group_capacities (list[int]): Exact size constraints per group.
        respect_stars (bool): Maintain uniform star distribution.
        score_columns (list[str]): Columns to balance.
        score_weights (dict[str, float]): Impact weight logic.
        opt_mode (str): Optimization topology selection.
        conflict_priority (str): Collision resolution mechanism.

    Returns:
        tuple[list[dict], bool]: Resolved groupings and success flag.
    """
    model, x, num_people, num_groups = build_partition_model(
        participants,
        group_capacities,
        respect_stars,
        score_columns,
        score_weights,
        opt_mode,
        conflict_priority,
    )

    solver_inst = cp_model.CpSolver()
    solver_inst.parameters.max_time_in_seconds = config.SOLVER_TIMEOUT
    solver_inst.parameters.num_search_workers = config.SOLVER_NUM_WORKERS

    status = solver_inst.Solve(model, SolutionPrinter(time.time()))
    print("")

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result_groups = [{"id": g + 1, "members": []} for g in range(num_groups)]
        for i in range(num_people):
            for g in range(num_groups):
                if solver_inst.Value(x[(i, g)]) == 1:
                    result_groups[g]["members"].append(participants[i])
        return result_groups, True

    return [], False
