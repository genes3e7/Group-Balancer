"""Group Balancer: Local Pre-CI Script."""

import argparse
import concurrent.futures
import os
import pathlib
import shutil
import subprocess
import sys


class PreCIPipeline:
    """Orchestrates the local and CI validation checks for the project.

    Attributes:
        STATUS_MAP (dict): Maps boolean or string outcomes to visual status labels.
        _results (list): Internal log of (description, status) tuples for all steps.
        is_ci (bool): True if executing within a remote CI environment.
        min_ver (str): Minimum supported Python version for README updates.
        max_ver (str): Maximum supported Python version for README updates.
    """

    STATUS_MAP = {
        True: "✅ PASS",
        False: "❌ FAIL",
        "SKIPPED": "⏭️  SKIP",
    }

    def __init__(self, min_ver: str = "3.10", max_ver: str = "3.14") -> None:
        """Initializes the PreCIPipeline with Python version bounds.

        Args:
            min_ver (str): Minimum supported Python version. Defaults to "3.10".
            max_ver (str): Maximum supported Python version. Defaults to "3.14".
        """
        self._results = []
        self.is_ci = os.environ.get("CI", "").lower() in ("true", "1", "yes")
        self.min_ver = min_ver
        self.max_ver = max_ver

    def record_result(
        self,
        description: str,
        passed: bool | str,
        outputs: dict[str, str] | None = None,
    ) -> None:
        """Records the outcome of a specific step for the final summary.

        Args:
            description (str): A brief description of the step.
            passed (bool | str): True/False for success/failure, or "SKIPPED".
            outputs (dict[str, str] | None): Optional dict with 'stdout' and 'stderr'.
        """
        self._results.append((description, passed, outputs))

    def run_command(
        self, command: list[str], description: str, fail_fast: bool = False
    ) -> bool:
        """Executes a single shell command and prints the status.

        Args:
            command (list[str]): The command to run as a list of strings.
            description (str): A brief description of the step for logging.
            fail_fast (bool): If True, exits the script immediately on failure.

        Returns:
            bool: True if the command succeeded (exit code 0), False otherwise.
        """
        print(f"\n>>> [Step: {description}]")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
                env=env,
            )

            # Stream stdout/stderr back since we captured it successfully
            if result.stdout:
                sys.stdout.write(result.stdout)
            if result.stderr:
                sys.stderr.write(result.stderr)

            print(f"✅ {description} completed successfully.")
            self.record_result(description, True)
            return True

        except subprocess.CalledProcessError as e:
            print(f"\n❌ FATAL: '{description}' failed with exit code {e.returncode}")
            if e.stdout:
                print("--- STDOUT ---")
                sys.stdout.write(e.stdout)
            if e.stderr:
                print("--- STDERR ---")
                sys.stderr.write(e.stderr)

            # Attach captured outputs to the failure record
            self.record_result(
                description, False, {"stdout": e.stdout, "stderr": e.stderr}
            )
            if fail_fast:
                sys.exit(e.returncode)
            return False
        except (subprocess.SubprocessError, OSError) as e:
            print(f"\n❌ FATAL: '{description}' generated an exception: {e}")
            self.record_result(description, False, {"stdout": str(e), "stderr": ""})
            if fail_fast:
                sys.exit(1)
            return False

    def run_commands_parallel(self, tasks: list[tuple[list[str], str]]) -> bool:
        """Executes multiple shell commands concurrently and captures output.

        This method leverages a ThreadPoolExecutor to run independent checks
        (like linting, testing, and dead-code analysis) in parallel to optimize
        execution speed.

        Args:
            tasks (list[tuple[list[str], str]]): A list of (command, description)
                tuples to be executed concurrently.

        Returns:
            bool: True if all parallel tasks succeeded, False if any failed.
        """
        print("\n>>> [Parallel Execution] Starting concurrent checks...")
        success_overall = True
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_desc = {
                executor.submit(
                    subprocess.run,
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    env=env,
                ): desc
                for cmd, desc in tasks
            }

            for future in concurrent.futures.as_completed(future_to_desc):
                desc = future_to_desc[future]
                try:
                    result = future.result()
                    print(f"\n--- Output from {desc} ---")
                    if result.stdout:
                        print(result.stdout.strip())
                    if result.stderr:
                        print(result.stderr.strip())

                    if result.returncode == 0:
                        print(f"✅ {desc} completed successfully.")
                        self.record_result(
                            desc,
                            True,
                            {"stdout": result.stdout, "stderr": result.stderr},
                        )
                    else:
                        print(
                            f"❌ FATAL: '{desc}' failed with exit code "
                            f"{result.returncode}"
                        )
                        self.record_result(
                            desc,
                            False,
                            {"stdout": result.stdout, "stderr": result.stderr},
                        )
                        success_overall = False
                except (subprocess.SubprocessError, OSError) as exc:
                    print(f"\n❌ FATAL: '{desc}' generated an exception: {exc}")
                    self.record_result(desc, False, {"stdout": str(exc), "stderr": ""})
                    success_overall = False

        return success_overall

    def all_passed(self) -> bool:
        """Predicate to check if every recorded result is a strict PASS.

        Returns:
            bool: True iff every result is exactly True.
        """
        return all(passed is True for _, passed, _ in self._results)

    def print_summary(self, title: str = "📋 PRE-CI SUMMARY") -> bool:
        """Prints a summary of all executed checks.

        Args:
            title (str): The header title for the summary block.

        Returns:
            bool: True if all checks passed, False if any failed.
        """
        print("\n" + "=" * 60)
        print(title)
        print("=" * 60)
        for desc, passed, _ in self._results:
            status = self.STATUS_MAP.get(passed, "❓ UNKNOWN")
            print(f"{status} - {desc}")
        print("=" * 60)
        return self.all_passed()

    def cleanup(self) -> None:
        """Removes temporary cache directories and artifacts recursively.

        Explicitly skips hidden directories and virtual environments.
        """
        if self.is_ci:
            print(
                "\n>>> [Cleanup] Skipped: CI environment detected "
                "(preserving artifacts)."
            )
            return

        print("\n>>> [Cleanup] Removing build artifacts and caches...")

        # Define base folders to remove if they exist at root
        base_targets = [".coverage", "dist", "build", ".ruff_cache", ".pytest_cache"]
        for target_name in base_targets:
            target = pathlib.Path(target_name)
            if target.exists():
                self._remove_path(target)

        # Recursively find __pycache__ and *.egg-info, skipping venvs and hidden dirs
        venv_names = {".venv", "venv", "env"}
        for root, dirs, _files in os.walk("."):
            # Skip hidden directories and venvs
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in venv_names]

            for d in dirs:
                if d == "__pycache__" or d.endswith(".egg-info"):
                    path = pathlib.Path(root) / d
                    self._remove_path(path)

    def _remove_path(self, path: pathlib.Path) -> None:
        """Helper to remove a directory or file."""
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        except OSError as e:
            print(f"⚠️ Warning: Could not remove {path}: {e}")

    def execute(self) -> None:
        """Main execution path for the Pre-CI suite."""
        print("\n" + "=" * 60)
        mode = "CI PIPELINE" if self.is_ci else "LOCAL PRE-CI"
        print(f"🚀 GROUP BALANCER {mode} GATE")
        print("=" * 60)

        # 1. Sync Dependencies (Fail-fast as subsequent steps depend on it)
        self.run_command(
            ["uv", "sync", "--all-extras", "--frozen"],
            "Syncing Project Environment",
            fail_fast=True,
        )

        # 2. Update README
        self.run_command(
            [
                "uv",
                "run",
                "--no-sync",
                "python",
                "tools/update_readme.py",
                self.min_ver,
                self.max_ver,
            ],
            "Updating README structure",
        )

        # 3. Formatting and Linting (Run unconditionally so CI can push diffs)
        self.run_command(
            ["uv", "run", "--no-sync", "ruff", "check", ".", "--fix"], "Ruff Linting"
        )
        self.run_command(
            ["uv", "run", "--no-sync", "ruff", "format", "."], "Ruff Formatting"
        )

        # 4. Parallel Checks (Vulture, Interrogate, Pytest)
        # Use --no-sync to avoid lock contention during parallel uv run calls
        parallel_tasks = [
            (
                ["uv", "run", "--no-sync", "vulture", "src/", "--min-confidence", "80"],
                "Dead Code Analysis (Vulture)",
            ),
            (
                ["uv", "run", "--no-sync", "interrogate", "."],
                "Docstring Coverage Enforcement",
            ),
        ]

        # Pytest executes in the remote test-matrix job. Prevent redundancy in CI.
        if not self.is_ci:
            parallel_tasks.append(
                (
                    ["uv", "run", "--no-sync", "pytest"],
                    "Unit Tests & Coverage Enforcement",
                )
            )

        self.run_commands_parallel(parallel_tasks)

        # 5. Build Verification Gate
        if self.all_passed():
            self.run_command(
                ["uv", "run", "--no-sync", "python", "build.py"],
                "Verifying Build Integrity",
            )
        else:
            self.record_result("Verifying Build Integrity", "SKIPPED")

        self.cleanup()

        # 6. Final Report
        if self.print_summary(title="📋 FINAL PRE-CI SUMMARY"):
            print("\n✨ ALL CHECKS PASSED.\n")
        else:
            print("\n❌ Pipeline failed. See logs above.\n")
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Group Balancer Pre-CI Gate")
    parser.add_argument(
        "min_ver", nargs="?", default="3.10", help="Minimum supported Python version"
    )
    parser.add_argument(
        "max_ver", nargs="?", default="3.14", help="Maximum supported Python version"
    )
    args = parser.parse_args()

    pipeline = PreCIPipeline(args.min_ver, args.max_ver)
    pipeline.execute()
