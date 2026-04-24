"""Group Balancer: Local Pre-CI Script.

This module provides a unified interface for running local pre-commit checks
including environment synchronization, linting, formatting, dead code analysis,
docstring coverage, unit testing, README updates, and build verification.

Example:
    $ uv run tools/pre_ci.py
"""

import os
import shutil
import subprocess
import sys


def run_command(command, description):
    """Executes a shell command and prints the status.

    Args:
        command (list[str]): The command to run as a list of strings.
        description (str): A brief description of the step for logging.

    Raises:
        SystemExit: If the command fails (returns a non-zero exit code).
    """
    print(f"\n>>> [Step: {description}]")
    try:
        subprocess.run(command, check=True)
        print(f"✅ {description} completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ FATAL: '{description}' failed with exit code {e.returncode}")
        sys.exit(e.returncode)


def cleanup():
    """Removes temporary cache directories and artifacts."""
    print("\n>>> [Cleanup] Removing build artifacts and caches...")
    folders = [".coverage", ".ruff_cache", ".pytest_cache", "dist", "build"]
    for folder in folders:
        if os.path.exists(folder):
            if os.path.isdir(folder):
                shutil.rmtree(folder, ignore_errors=True)
            else:
                os.remove(folder)


def main():
    """Main execution path for the Pre-CI suite."""
    print("\n" + "=" * 60)
    print("🚀 GROUP BALANCER PRE-CI GATE")
    print("=" * 60)

    # 1. Sync Dependencies
    run_command(
        ["uv", "sync", "--all-extras", "--frozen"], "Syncing Project Environment"
    )

    # 2. Ruff Linting
    run_command(["uv", "run", "ruff", "check", ".", "--fix"], "Ruff Linting")

    # 3. Ruff Formatting
    run_command(["uv", "run", "ruff", "format", "."], "Ruff Formatting")

    # 4. Vulture (Dead Code Analysis)
    run_command(
        ["uv", "run", "vulture", "src/", "--min-confidence", "80"],
        "Dead Code Analysis (Vulture)",
    )

    # 5. Interrogate (Docstring Coverage)
    run_command(["uv", "run", "interrogate", "."], "Docstring Coverage Enforcement")

    # 6. Pytest (Tests and Coverage)
    run_command(["uv", "run", "pytest"], "Unit Tests & Coverage Enforcement")

    # 7. Update README
    run_command(
        ["uv", "run", "python", "tools/update_readme.py", "3.10", "3.14"],
        "Updating README structure",
    )

    # 8. Verify Build
    run_command(["uv", "run", "python", "build.py"], "Verifying Build Integrity")

    # Cleanup
    cleanup()

    print("\n" + "=" * 60)
    print("✨ ALL CHECKS PASSED: The codebase is healthy and ready for commit.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
