"""
Command-Line Interface (CLI) Entry Point.

Allows the Group Balancer to be run in "headless" mode without the
Streamlit UI. This is useful for batch processing or testing logic.
"""

from src.core import data_loader, solver, config


def main():
    """
    Main function for the CLI.
    Orchestrates data loading, solving, and printing results to the console.
    """
    print("=== Group Balancer CLI ===")

    filepath = data_loader.get_file_path_from_user()
    if not filepath:
        return

    participants = data_loader.load_data(filepath)
    if not participants:
        return

    print(f"Loaded {len(participants)} participants.")

    while True:
        try:
            num_groups_str = input("Enter number of groups: ").strip()
            num_groups = int(num_groups_str)
            if num_groups > 0:
                break
            print("Please enter a positive integer.")
        except ValueError:
            print("Invalid number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            return

    print("\nSolving...")
    result, success = solver.solve_with_ortools(
        participants, num_groups, respect_stars=True
    )

    if success:
        print("\n=== Optimal Grouping Found ===")
        for g in result:
            print(f"\nGroup {g['id']} (Avg: {g['avg']:.2f}, Sum: {g['current_sum']}):")
            for m in g["members"]:
                print(f" - {m[config.COL_NAME]} ({m[config.COL_SCORE]})")
    else:
        print("\nFailed to find a feasible solution.")


if __name__ == "__main__":
    main()
