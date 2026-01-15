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
import pandas as pd
import numpy as np

# Updated Imports for src/ structure
from src.core import config, data_loader, solver
from src.utils import exporter


def _convert_to_df(groups: list) -> pd.DataFrame:
    """Converts list-of-dicts group structure to a flat DataFrame."""
    rows = []
    for g in groups:
        for m in g["members"]:
            rows.append(
                {
                    config.COL_NAME: m[config.COL_NAME],
                    config.COL_SCORE: m[config.COL_SCORE],
                    config.COL_GROUP: g["id"],
                }
            )
    return pd.DataFrame(rows)


def print_cli_summary(groups: list, label: str):
    """Prints a statistical summary to the console."""
    print(f"\n--- {label} ---")
    scores = [g["avg"] for g in groups]
    for g in sorted(groups, key=lambda x: x["id"]):
        star_count = sum(
            1
            for m in g["members"]
            if str(m[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR)
        )
        print(
            f"Grp {g['id']} | Count: {len(g['members'])} | Stars: {star_count} | Avg: {g['avg']:.2f}"
        )

    if scores:
        print(f"StdDev: {np.std(scores):.4f}")


def save_results_to_disk(results: dict):
    """Saves the results dictionary to an Excel file using the new Exporter."""
    print(f"\nSaving to {config.OUTPUT_FILENAME}...")

    champion_groups = results.get(config.SHEET_WITHOUT_CONSTRAINT) or results.get(
        config.SHEET_WITH_CONSTRAINT
    )

    if not champion_groups:
        print("No results to save.")
        return

    # Convert to DataFrame for the Exporter
    df_results = _convert_to_df(champion_groups)

    # Generate Bytes
    excel_bytes = exporter.generate_excel_bytes(
        df_results, config.COL_GROUP, config.COL_SCORE, config.COL_NAME
    )

    # Write to Disk
    try:
        with open(config.OUTPUT_FILENAME, "wb") as f:
            f.write(excel_bytes)
        print("✅ Success! File saved.")
    except PermissionError:
        print(
            f"❌ Error: Permission denied. Close '{config.OUTPUT_FILENAME}' and try again."
        )
    except Exception as e:
        print(f"❌ Error saving file: {e}")


def run_solver_interface(participants: list[dict], n_groups: int):
    print("--- Advanced Group Balancer (OR-Tools Engine) ---")
    results = {}

    # --- Scenario 1: With Star Constraints ---
    print("\nSolving Scenario: With Constraints...")
    t0 = time.time()
    groups_c, found_c = solver.solve_with_ortools(
        participants, n_groups, respect_stars=True
    )
    dt_c = time.time() - t0

    std_c = 99999.0
    if found_c:
        print(f"  > Finished in {dt_c:.2f}s")
        print_cli_summary(groups_c, "Constrained Results")
        std_c = np.std([g["avg"] for g in groups_c])
        results[config.SHEET_WITH_CONSTRAINT] = groups_c
    else:
        print(f"  > No solution found (Time: {dt_c:.2f}s).")

    # --- Scenario 2: No Constraints ---
    print("\nSolving Scenario: No Constraints...")
    t0 = time.time()
    groups_u, found_u = solver.solve_with_ortools(
        participants, n_groups, respect_stars=False
    )
    dt_u = time.time() - t0

    if found_u:
        print(f"  > Finished in {dt_u:.2f}s")
        std_u = np.std([g["avg"] for g in groups_u])

        # Champion Logic
        if found_c and (std_c < std_u - 0.0001):
            print("\n🏆 Champion Wins! (Constrained result is mathematically superior)")
            results[config.SHEET_WITHOUT_CONSTRAINT] = groups_c
            print_cli_summary(groups_c, "Final Selection")
        else:
            print_cli_summary(groups_u, "Final Selection")
            results[config.SHEET_WITHOUT_CONSTRAINT] = groups_u
    else:
        print(f"  > No solution found (Time: {dt_u:.2f}s).")

    save_results_to_disk(results)


def main():
    multiprocessing.freeze_support()

    filepath = data_loader.get_file_path_from_user()
    participants = data_loader.load_data(filepath)
    if not participants:
        return

    try:
        n_str = input("Enter number of groups: ").strip()
        if not n_str.isdigit() or int(n_str) < 1:
            print("Invalid number.")
            return
        n_groups = int(n_str)
        if n_groups > len(participants):
            print("Error: More groups than participants.")
            return
    except Exception as e:
        print(f"Input Error: {e}")
        return

    run_solver_interface(participants, n_groups)


if __name__ == "__main__":
    main()
