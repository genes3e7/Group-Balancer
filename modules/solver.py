# modules/solver.py
from ortools.sat.python import cp_model
import math
import time
import sys
from modules import config

"""
Module: Solver
Responsibility: Defines and solves the Constraint Programming model using Google OR-Tools.
"""

class SolutionPrinter(cp_model.CpSolverSolutionCallback):
    """
    Custom Callback for the OR-Tools solver.
    Prints status updates to the console whenever a better solution is found.
    """
    def __init__(self, start_time):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__start_time = start_time
        self.__solution_count = 0

    def on_solution_callback(self):
        current_time = time.time()
        obj = self.ObjectiveValue()
        self.__solution_count += 1
        # \033[K clears the line to prevent visual artifacts
        sys.stdout.write(f"\r  > Found solution #{self.__solution_count} | Objective (Deviation): {obj} | Time: {current_time - self.__start_time:.2f}s\033[K")
        sys.stdout.flush()

def solve_with_ortools(participants, num_groups, respect_stars):
    """
    Constructs and solves the mathematical model for group balancing.
    
    Strategy:
        1. Scale scores to integers (x100,000) to maintain high precision without floating-point errors.
        2. Pre-calculate group sizes to break symmetry and define exact targets.
        3. Define constraints: One person per group, specific group sizes, star limits.
        4. Minimize the sum of absolute differences between Actual Group Sum and Target Group Sum.
    
    Args:
        participants (list): List of dicts containing Name and Score.
        num_groups (int): Desired number of groups.
        respect_stars (bool): If True, enforces star separation constraints.
        
    Returns:
        tuple: (List of groups with members, Boolean indicating success)
    """
    model = cp_model.CpModel()

    # --- 1. DATA PREPARATION (Integer Scaling) ---
    
    # We multiply scores by 100,000 to keep 5 decimal places of precision 
    # while working with Integers (required by CP-SAT).
    SCALE = 100000 
    
    num_people = len(participants)
    
    # Convert scores to scaled integers
    scores = [int(round(float(p[config.COL_SCORE]) * SCALE)) for p in participants]
    total_score = sum(scores)
    
    # Identify indices of "Star" participants
    stars = []
    for i, p in enumerate(participants):
        if str(p[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR):
            stars.append(i)

    # --- 2. GROUP SIZE CALCULATION ---
    
    # Example: 26 people / 6 groups = 4 remainder 2.
    # Result: 2 groups of 5, 4 groups of 4.
    base_size = num_people // num_groups
    remainder = num_people % num_groups
    
    # We explicitly map which group index gets which size.
    # This helps the solver converge faster by removing "Symmetry" 
    # (ambiguity about which group is which).
    group_sizes_map = {}
    for g in range(num_groups):
        if g < remainder:
            group_sizes_map[g] = base_size + 1
        else:
            group_sizes_map[g] = base_size

    # --- 3. DECISION VARIABLES ---
    
    # x[i, g] is a boolean: 1 if person i is in group g, 0 otherwise.
    x = {}
    for i in range(num_people):
        for g in range(num_groups):
            x[(i, g)] = model.NewBoolVar(f'assignment_p{i}_g{g}')

    # --- 4. HARD CONSTRAINTS ---

    # Constraint A: Every person must be assigned to exactly one group.
    for i in range(num_people):
        model.Add(sum(x[(i, g)] for g in range(num_groups)) == 1)

    # Constraint B: Groups must match the pre-calculated sizes exactly.
    for g in range(num_groups):
        model.Add(sum(x[(i, g)] for i in range(num_people)) == group_sizes_map[g])

    # Constraint C: Star Separation (If enabled).
    if respect_stars and stars:
        # Calculate maximum allowed stars per group (ceiling division)
        max_stars_per_group = math.ceil(len(stars) / num_groups)
        for g in range(num_groups):
            model.Add(sum(x[(i, g)] for i in stars) <= max_stars_per_group)

    # --- 5. OBJECTIVE FUNCTION (Balancing) ---
    
    # The Goal: Make every group's average score as close to the Global Average as possible.
    # Math derivation to keep it Integer-based:
    #   Ideally: GroupSum / GroupSize == TotalScore / NumPeople
    #   Cross-multiply: GroupSum * NumPeople == TotalScore * GroupSize
    #   Minimize: | (GroupSum * NumPeople) - (TotalScore * GroupSize) |
    
    abs_diffs = []
    
    for g in range(num_groups):
        # Variable representing the sum of scores in this group
        g_sum = model.NewIntVar(0, total_score, f'sum_group_{g}')
        model.Add(g_sum == sum(x[(i, g)] * scores[i] for i in range(num_people)))
        
        # Calculate the mathematical target for this specific group size
        target_scaled = total_score * group_sizes_map[g]
        
        # Calculate the actual value scaled up to match dimensions
        actual_scaled = model.NewIntVar(0, total_score * num_people, f'actual_scaled_{g}')
        model.Add(actual_scaled == g_sum * num_people)
        
        # Calculate the deviation (can be positive or negative)
        # Bounds: +/- Max possible score
        diff = model.NewIntVar(-total_score * num_people, total_score * num_people, f'diff_{g}')
        model.Add(diff == actual_scaled - target_scaled)
        
        # Convert deviation to Absolute Value
        abs_diff = model.NewIntVar(0, total_score * num_people, f'abs_diff_{g}')
        model.AddAbsEquality(abs_diff, diff)
        
        abs_diffs.append(abs_diff)

    # Minimize the total absolute deviation across all groups
    model.Minimize(sum(abs_diffs))

    # --- 6. EXECUTION ---
    
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = config.SOLVER_TIMEOUT
    # Use 8 workers for parallel search (speeds up proving optimality)
    solver.parameters.num_search_workers = 8 
    
    printer = SolutionPrinter(time.time())
    status = solver.Solve(model, printer)
    
    print("") # Newline for clean output

    # --- 7. RESULT RECONSTRUCTION ---
    
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result_groups = [{'id': g+1, 'members': [], 'current_sum': 0} for g in range(num_groups)]
        
        # Map boolean variables back to data structures
        for i in range(num_people):
            for g in range(num_groups):
                if solver.Value(x[(i, g)]) == 1:
                    result_groups[g]['members'].append(participants[i])
        
        # Calculate final floating-point stats for display
        for g in result_groups:
            g['current_sum'] = sum(float(m[config.COL_SCORE]) for m in g['members'])
            count = len(g['members'])
            g['avg'] = g['current_sum'] / count if count > 0 else 0
            
        return result_groups, True
    else:
        return [], False
