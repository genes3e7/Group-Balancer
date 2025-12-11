# group_balancer.py
import multiprocessing
import time
import numpy as np
from modules import config, data_loader, output_manager, solver

"""
Application Entry Point.
Orchestrates data loading, solving, and output generation.
"""

def run_solver_interface(participants, n_groups):
    """
    Runs the solver for both Constrained and Unconstrained scenarios.
    """
    print("--- Advanced Group Balancer (OR-Tools Engine) ---")
    print("NOTE: Using Constraint Programming for exact mathematical optimization.")
    
    results = {}
    
    # --- SCENARIO 1: With Star Constraints ---
    print(f"\nSolving Scenario: {config.SHEET_WITH_CONSTRAINT}...")
    t0 = time.time()
    
    groups_c, found_c = solver.solve_with_ortools(participants, n_groups, respect_stars=True)
    dt_c = time.time() - t0
    
    if found_c:
        avgs = [g['avg'] for g in groups_c]
        std_c = np.std(avgs)
        print(f"  > Finished in {dt_c:.2f}s. StdDev: {std_c:.4f}")
        results[config.SHEET_WITH_CONSTRAINT] = groups_c
    else:
        print("  > No solution found within time limit.")
        std_c = 99999.0

    # --- SCENARIO 2: No Constraints ---
    print(f"\nSolving Scenario: {config.SHEET_WITHOUT_CONSTRAINT}...")
    t0 = time.time()
    
    groups_u, found_u = solver.solve_with_ortools(participants, n_groups, respect_stars=False)
    dt_u = time.time() - t0
    
    if found_u:
        avgs = [g['avg'] for g in groups_u]
        std_u = np.std(avgs)
        print(f"  > Finished in {dt_u:.2f}s. StdDev: {std_u:.4f}")
        
        # Champion Logic:
        # Even if Unconstrained search found a result, if the Constrained result
        # happens to be better (due to solver search path or timing), use it.
        # This guarantees the Unconstrained output is always the mathematical best available.
        if std_c < std_u - 0.0001:
            print("  > Champion Wins! (Constrained result promoted to Unconstrained slot)")
            results[config.SHEET_WITHOUT_CONSTRAINT] = groups_c
        else:
            results[config.SHEET_WITHOUT_CONSTRAINT] = groups_u

    # --- OUTPUT ---
    output_manager.save_results(results)

def main():
    # Freeze support is good practice for cross-platform multiprocessing,
    # even if OR-Tools handles threading internally.
    multiprocessing.freeze_support()
    
    # 1. Load Data
    filepath = data_loader.get_file_path_from_user()
    participants = data_loader.load_data(filepath)
    if not participants: return

    # 2. Get Settings
    try:
        n_groups = int(input("Enter number of groups: "))
        if n_groups < 1: 
            print("Error: Groups must be > 0")
            return
        if n_groups > len(participants):
            print("Error: More groups than participants.")
            return
    except ValueError:
        print("Error: Invalid number.")
        return

    # 3. Run
    run_solver_interface(participants, n_groups)

if __name__ == "__main__":
    main()
