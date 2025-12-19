"""
Advanced Group Balancer Application.

This script distributes participants into balanced groups based on scores.
It uses Google OR-Tools (Constraint Programming) to find mathematically
optimal solutions that minimize the standard deviation of group averages.

Usage:
    python group_balancer.py
"""

import multiprocessing
import time
import numpy as np
from modules import config, data_loader, output_manager, solver


def run_solver_interface(participants: list[dict], n_groups: int):
    """
    Runs the solver for both 'Constrained' and 'Unconstrained' scenarios.
    Compares the results and saves the optimal outcomes.

    Args:
        participants (list[dict]): List of participant data.
        n_groups (int): The target number of groups.
    """
    print("--- Advanced Group Balancer (OR-Tools Engine) ---")
    print("NOTE: Using Constraint Programming for exact mathematical optimization.")

    results = {}

    # --- Scenario 1: With Star Constraints ---
    print(f"\nSolving Scenario: {config.SHEET_WITH_CONSTRAINT}...")
    t0 = time.time()
    groups_c, found_c = solver.solve_with_ortools(
        participants, n_groups, respect_stars=True
    )
    dt_c = time.time() - t0

    std_c = 99999.0
    if found_c:
        avgs_c = [g['avg'] for g in groups_c]
        std_c = np.std(avgs_c)
        print(f"  > Finished in {dt_c:.2f}s. StdDev: {std_c:.4f}")
        results[config.SHEET_WITH_CONSTRAINT] = groups_c
    else:
        print("  > No solution found within time limit.")

    # --- Scenario 2: No Constraints ---
    print(f"\nSolving Scenario: {config.SHEET_WITHOUT_CONSTRAINT}...")
    t0 = time.time()
    groups_u, found_u = solver.solve_with_ortools(
        participants, n_groups, respect_stars=False
    )
    dt_u = time.time() - t0

    if found_u:
        avgs_u = [g['avg'] for g in groups_u]
        std_u = np.std(avgs_u)
        print(f"  > Finished in {dt_u:.2f}s. StdDev: {std_u:.4f}")

        # Champion Logic:
        # Sometimes the 'Constrained' logic inadvertently finds a better
        # mathematical topology for size distribution than the 'Unconstrained'
        # search path within the time limit. If Constrained is strictly better, use it.
        if found_c and (std_c < std_u - 0.0001):
            print("  > Champion Wins! (Constrained result promoted to Unconstrained slot)")
            results[config.SHEET_WITHOUT_CONSTRAINT] = groups_c
        else:
            results[config.SHEET_WITHOUT_CONSTRAINT] = groups_u
    else:
        print("  > No solution found within time limit.")

    # --- Output ---
    output_manager.save_results(results)


def main():
    """Main execution function."""
    # Good practice for cross-platform multiprocessing compatibility
    multiprocessing.freeze_support()

    # 1. Load Data
    filepath = data_loader.get_file_path_from_user()
    participants = data_loader.load_data(filepath)
    if not participants:
        return

    # 2. Get User Input
    try:
        n_groups_str = input("Enter number of groups: ").strip()
        if not n_groups_str.isdigit():
            print("Error: Please enter a valid integer.")
            return
        
        n_groups = int(n_groups_str)
        
        if n_groups <= 0:
            print("Error: Number of groups must be positive.")
            return
        if n_groups > len(participants):
            print("Error: Cannot have more groups than participants.")
            return

    except Exception as e:
        print(f"Error reading input: {e}")
        return

    # 3. Run Logic
    run_solver_interface(participants, n_groups)


if __name__ == "__main__":
    main()
