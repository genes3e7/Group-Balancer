"""CLI entry point for the Group Balancer.

Provides a terminal interface for loading data and running the optimization
engine directly without the Streamlit UI.
"""

import logging
import sys

from src import logger
from src.core import config, data_loader, solver
from src.core.models import ConflictPriority, SolverConfig

# Configure global logger for the CLI
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def main() -> None:
    """Main CLI execution loop."""
    logger.info("Starting Group Balancer CLI...")

    filepath = data_loader.get_file_path_from_user()
    participants = data_loader.load_data(filepath)

    if not participants:
        logger.error("Failed to load participants.")
        sys.exit(1)

    num_people = len(participants)
    score_cols = [c for c in participants[0] if str(c).startswith(config.SCORE_PREFIX)]

    logger.info(
        "Found %d participants and %d score dimensions.",
        num_people,
        len(score_cols),
    )

    try:
        num_groups_in = input("Enter number of groups: ")
        timeout_in = input("Enter max search time (seconds, default 60): ") or "60"

        num_groups = int(num_groups_in)
        timeout = int(timeout_in)

        if num_groups <= 0:
            logger.error("Number of groups must be a positive integer.")
            sys.exit(1)
        if timeout <= 0:
            logger.error("Timeout must be a positive integer.")
            sys.exit(1)

    except ValueError:
        logger.error("Invalid input. Numeric values required.")
        sys.exit(1)

    # Basic equal capacity distribution
    base, rem = divmod(num_people, num_groups)
    capacities = [base + (1 if i < rem else 0) for i in range(num_groups)]

    cfg = SolverConfig(
        num_groups=num_groups,
        group_capacities=capacities,
        score_weights=dict.fromkeys(score_cols, 1.0),
        conflict_priority=ConflictPriority.GROUPERS,
        timeout_seconds=timeout,
        interleave_search=True,  # CLI uses interleaved search for determinism
    )

    logger.info("Solving optimization model...")
    results, _status, elapsed = solver.solve_with_ortools(participants, cfg)

    if results:
        logger.info(
            "Optimization successful! (Time: %.2fs)",
            elapsed,
        )
        # Display summary
        for gid in range(1, num_groups + 1):
            members = [r for r in results if r[config.COL_GROUP] == gid]
            names = ", ".join(m[config.COL_NAME] for m in members)
            logger.info("Group %d (%d members): %s", gid, len(members), names)
    else:
        logger.error("Solver failed to find a solution.")


if __name__ == "__main__":
    main()
