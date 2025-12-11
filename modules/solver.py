# modules/solver.py
from ortools.sat.python import cp_model
import math
import time
import sys
import pandas as pd
from modules import config

class SolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Callback to print intermediate solutions."""
    def __init__(self, start_time):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__start_time = start_time
        self.__solution_count = 0

    def on_solution_callback(self):
        current_time = time.time()
        obj = self.ObjectiveValue()
        self.__solution_count += 1
        # Clear line and print status
        sys.stdout.write(f"\r  > Found solution #{self.__solution_count} | Objective (Deviation): {obj} | Time: {current_time - self.__start_time:.2f}s")
        sys.stdout.flush()

def solve_with_ortools(participants, num_groups, respect_stars, time_limit_seconds=180):
    model = cp_model.CpModel()

    # --- 1. DATA PREP (HIGH PRECISION) ---
    # Scale to integers. 
    # Using 100,000 allows us to respect up to 5 decimal places.
    SCALE = 100000 
    
    num_people = len(participants)
    # Use round() for better accuracy than int() truncation
    scores = [int(round(float(p[config.COL_SCORE]) * SCALE)) for p in participants]
    total_score = sum(scores)
    
    stars = []
    for i, p in enumerate(participants):
        if str(p[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR):
            stars.append(i)

    # Determine Sizes
    base_size = num_people // num_groups
    remainder = num_people % num_groups
    
    # Explicitly assign target sizes to group indices
    # This breaks symmetry and allows precise target calculation
    group_sizes_map = {}
    for g in range(num_groups):
        if g < remainder:
            group_sizes_map[g] = base_size + 1
        else:
            group_sizes_map[g] = base_size

    # --- 2. VARIABLES ---
    # x[i, g] = 1 if person i is in group g
    x = {}
    for i in range(num_people):
        for g in range(num_groups):
            x[(i, g)] = model.NewBoolVar(f'x_{i}_{g}')

    # --- 3. CONSTRAINTS ---

    # A. Each person belongs to exactly one group
    for i in range(num_people):
        model.Add(sum(x[(i, g)] for g in range(num_groups)) == 1)

    # B. Explicit Group Sizes
    for g in range(num_groups):
        model.Add(sum(x[(i, g)] for i in range(num_people)) == group_sizes_map[g])

    # C. Star Constraints
    if respect_stars and stars:
        max_stars_per_group = math.ceil(len(stars) / num_groups)
        for g in range(num_groups):
            model.Add(sum(x[(i, g)] for i in stars) <= max_stars_per_group)

    # --- 4. OBJECTIVE: BALANCE AVERAGES ---
    # We minimize the deviation of (GroupSum * TotalPeople) vs (TotalScore * GroupSize)
    # This comparison avoids division and maintains integer precision
    
    abs_diffs = []
    
    for g in range(num_groups):
        # Upper bound for sum is Total Score
        g_sum = model.NewIntVar(0, total_score, f'sum_{g}')
        model.Add(g_sum == sum(x[(i, g)] * scores[i] for i in range(num_people)))
        
        # Target scaled by N (TotalScore * GroupSize)
        target_scaled = total_score * group_sizes_map[g]
        
        # Actual scaled sum (GroupSum * TotalPeople)
        actual_scaled = model.NewIntVar(0, total_score * num_people, f'act_sc_{g}')
        model.Add(actual_scaled == g_sum * num_people)
        
        # Difference
        # Range can be negative, so we set bounds +/- total potential value
        diff = model.NewIntVar(-total_score * num_people, total_score * num_people, f'diff_{g}')
        model.Add(diff == actual_scaled - target_scaled)
        
        # Absolute Difference
        abs_diff = model.NewIntVar(0, total_score * num_people, f'abs_diff_{g}')
        model.AddAbsEquality(abs_diff, diff)
        abs_diffs.append(abs_diff)

    model.Minimize(sum(abs_diffs))

    # --- 5. SOLVE ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    # 8 workers is standard for modern multi-core CPUs
    solver.parameters.num_search_workers = 8 
    
    # Callback for progress
    printer = SolutionPrinter(time.time())
    status = solver.Solve(model, printer)
    
    print("") # Newline after progress bar

    # --- 6. RECONSTRUCT ---
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result_groups = [{'id': g+1, 'members': [], 'current_sum': 0} for g in range(num_groups)]
        
        for i in range(num_people):
            for g in range(num_groups):
                if solver.Value(x[(i, g)]) == 1:
                    result_groups[g]['members'].append(participants[i])
        
        # Calculate final stats
        for g in result_groups:
            g['current_sum'] = sum(float(m[config.COL_SCORE]) for m in g['members'])
            count = len(g['members'])
            g['avg'] = g['current_sum'] / count if count > 0 else 0
            
        return result_groups, True
    else:
        return [], False
