"""CLI Entry Point for the Group Balancer.

Provides a terminal-based interface for running the optimization.
"""

import sys

from src import logger
from src.core import config, data_loader, solver
from src.core.models import ConflictPriority, OptimizationMode, SolverConfig


def main():
    """Main CLI execution loop."""
    logger.info("Starting Group Balancer CLI...")
    print("\n=== Group Balancer CLI ===")

    filepath = data_loader.get_file_path_from_user()
    participants = data_loader.load_data(filepath)

    if not participants:
        logger.error("Failed to load data. Exiting.")
        sys.exit(1)

    num_people = len(participants)
    score_cols = [
        c for c in participants[0].keys() if c.startswith(config.SCORE_PREFIX)
    ]

    if not score_cols:
        logger.error("No score columns detected in input data.")
        sys.exit(1)

    print(f"\nFound {num_people} participants and {len(score_cols)} score dimensions.")

    try:
        num_groups = int(input(f"Enter number of groups (1-{num_people}) [2]: ") or "2")
    except ValueError:
        logger.error("Invalid number of groups. Exiting.")
        sys.exit(1)

    # Simple even capacity split for CLI
    base, rem = divmod(num_people, num_groups)
    capacities = [base + (1 if i < rem else 0) for i in range(num_groups)]

    cfg = SolverConfig(
        num_groups=num_groups,
        group_capacities=capacities,
        score_weights={c: 1.0 for c in score_cols},
        opt_mode=OptimizationMode.ADVANCED,
        conflict_priority=ConflictPriority.GROUPERS,
        timeout_seconds=config.SOLVER_TIMEOUT,
    )

    print("\nSolving optimization model...")
    results, status, elapsed = solver.solve_with_ortools(participants, cfg)

    if results:
        print(f"\n✅ Success! Found grouping in {elapsed:.2f}s.")
        print("=== Results Summary ===")
        for g_id in range(1, num_groups + 1):
            members = [p for p in results if p[config.COL_GROUP] == g_id]
            print(f"\nGroup {g_id} ({len(members)} members):")
            for m in members:
                scores_str = ", ".join([f"{k}:{m[k]}" for k in score_cols])
                print(f" - {m[config.COL_NAME]} ({scores_str})")
    else:
        print("\n❌ Failed to find a valid solution.")


if __name__ == "__main__":
    main()
