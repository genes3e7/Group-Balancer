"""
Command-Line Interface (CLI) Entry Point.

Allows the Group Balancer to be run in "headless" mode without the
Streamlit UI. This is useful for batch processing or testing logic.
"""

from src.core import data_loader, solver, config


def main() -> None:
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

    num_people = len(participants)
    print(f"Loaded {num_people} participants.")

    score_cols_set = set()
    for p in participants:
        for k in p.keys():
            if str(k).startswith(config.SCORE_PREFIX):
                score_cols_set.add(k)

    score_cols = sorted(list(score_cols_set))
    if not score_cols:
        print("Fatal Error: No score columns detected by parser.")
        return

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

    base_size = num_people // num_groups
    remainder = num_people % num_groups
    group_capacities = [
        base_size + 1 if i < remainder else base_size for i in range(num_groups)
    ]

    # Give uniform equal weights in the CLI by default
    score_weights = {col: 1.0 for col in score_cols}

    print(f"\nBalancing across {len(score_cols)} dimensions: {score_cols}")
    print("Solving...")
    result, success = solver.solve_with_ortools(
        participants, group_capacities, score_cols, score_weights
    )

    if success:
        print("\n=== Optimal Grouping Found ===")
        for g in result:
            print(f"\nGroup {g['id']}:")
            for m in g["members"]:
                scores_str = ", ".join(
                    [f"{col}: {m.get(col, 0)}" for col in score_cols]
                )
                print(f" - {m.get(config.COL_NAME, 'Unknown')} ({scores_str})")
    else:
        print("\nFailed to find a feasible solution.")


if __name__ == "__main__":
    main()
