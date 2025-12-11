# group_balancer.py
import multiprocessing
import time
import numpy as np
from modules import config, data_loader, output_manager, solver

def run_solver_interface(participants, n_groups):
    print("--- Advanced Group Balancer (OR-Tools Engine) ---")
    print("NOTE: Using Constraint Programming for exact mathematical optimization.")
    
    results = {}
    
    # 1. Constrained
    print(f"\nSolving Scenario: {config.SHEET_WITH_CONSTRAINT}...")
    t0 = time.time()
    # We allow more time for constrained as it's harder, but usually finishes fast
    groups_c, found_c = solver.solve_with_ortools(participants, n_groups, respect_stars=True, time_limit_seconds=300)
    dt_c = time.time() - t0
    
    if found_c:
        avgs = [g['avg'] for g in groups_c]
        std_c = np.std(avgs)
        print(f"  > Finished in {dt_c:.2f}s. StdDev: {std_c:.4f}")
        results[config.SHEET_WITH_CONSTRAINT] = groups_c
    else:
        print("  > No solution found within time limit.")
        std_c = 99999

    # 2. Unconstrained
    print(f"\nSolving Scenario: {config.SHEET_WITHOUT_CONSTRAINT}...")
    t0 = time.time()
    groups_u, found_u = solver.solve_with_ortools(participants, n_groups, respect_stars=False, time_limit_seconds=300)
    dt_u = time.time() - t0
    
    if found_u:
        avgs = [g['avg'] for g in groups_u]
        std_u = np.std(avgs)
        print(f"  > Finished in {dt_u:.2f}s. StdDev: {std_u:.4f}")
        
        if std_c < std_u - 0.0001:
            print("  > Champion Wins! (Constrained was better)")
            results[config.SHEET_WITHOUT_CONSTRAINT] = groups_c
        else:
            results[config.SHEET_WITHOUT_CONSTRAINT] = groups_u

    # 3. Output
    output_manager.save_results(results)

def main():
    multiprocessing.freeze_support()
    
    filepath = data_loader.get_file_path_from_user()
    participants = data_loader.load_data(filepath)
    if not participants: return

    try:
        n_groups = int(input("Enter number of groups: "))
        if n_groups < 1: return
    except: return

    run_solver_interface(participants, n_groups)

if __name__ == "__main__":
    main()
