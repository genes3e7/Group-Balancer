"""Group Balancer: Local Pre-CI Script."""

import argparse
import concurrent.futures
import glob
import os
import shutil
import subprocess
import sys


class PreCIPipeline:
    """Orchestrates the local and CI validation checks for the project."""

    STATUS_MAP = {
        True: "✅ PASS",
        False: "❌ FAIL",
        "SKIPPED": "⏭️  SKIP",
    }

    def __init__(self, min_ver: str = "3.10", max_ver: str = "3.14"):
        """Initializes the PreCIPipeline with Python version bounds."""
        self._results = []
        self.is_ci = os.environ.get("CI", "").lower() in ("true", "1", "yes")
        self.min_ver = min_ver
        self.max_ver = max_ver

    def record_result(self, description: str, passed: bool | str) -> None:
        """Records the outcome of a specific step for the final summary."""
        self._results.append((description, passed))

    def run_command(
        self, command: list[str], description: str, fail_fast: bool = False
    ) -> bool:
        """Executes a single shell command and prints the status."""
        print(f"\n>>> [Step: {description}]")
        try:
            subprocess.run(command, check=True)
            print(f"✅ {description} completed successfully.")
            self.record_result(description, True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"\n❌ FATAL: '{description}' failed with exit code {e.returncode}")
            self.record_result(description, False)
            if fail_fast:
                sys.exit(e.returncode)
            return False

    def run_commands_parallel(self, tasks: list[tuple[list[str], str]]) -> bool:
        """Executes multiple shell commands concurrently and captures output."""
        print("\n>>> [Parallel Execution] Starting concurrent checks...")
        success_overall = True

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_desc = {
                executor.submit(
                    subprocess.run, cmd, capture_output=True, text=True
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
                        self.record_result(desc, True)
                    else:
                        print(
                            f"❌ FATAL: '{desc}' failed with exit code "
                            f"{result.returncode}"
                        )
                        self.record_result(desc, False)
                        success_overall = False
                except Exception as exc:
                    print(f"\n❌ FATAL: '{desc}' generated an exception: {exc}")
                    self.record_result(desc, False)
                    success_overall = False

        return success_overall

    def print_summary(self, title: str = "📋 PRE-CI SUMMARY") -> bool:
        """Prints a summary of all executed checks and returns overall success."""
        print("\n" + "=" * 60)
        print(title)
        print("=" * 60)
        all_passed = True
        for desc, passed in self._results:
            status = self.STATUS_MAP.get(passed, "❓ UNKNOWN")
            print(f"{status} - {desc}")
            if passed is not True:
                all_passed = False
        print("=" * 60)
        return all_passed

    def cleanup(self) -> None:
        """Removes temporary cache directories and artifacts."""
        if self.is_ci:
            print(
                "\n>>> [Cleanup] Skipped: CI environment detected "
                "(preserving artifacts)."
            )
            return

        print("\n>>> [Cleanup] Removing build artifacts and caches...")
        folders = [
            ".coverage",
            ".ruff_cache",
            ".pytest_cache",
            "dist",
            "build",
            "__pycache__",
        ]
        folders.extend(glob.glob("*.egg-info"))

        for folder in folders:
            if os.path.exists(folder):
                if os.path.isdir(folder):
                    shutil.rmtree(folder, ignore_errors=True)
                else:
                    os.remove(folder)

    def execute(self) -> None:
        """Main execution path for the Pre-CI suite."""
        print("\n" + "=" * 60)
        mode = "CI PIPELINE" if self.is_ci else "LOCAL PRE-CI"
        print(f"🚀 GROUP BALANCER {mode} GATE")
        print("=" * 60)

        self.run_command(
            ["uv", "sync", "--all-extras", "--frozen"],
            "Syncing Project Environment",
        )

        self.run_command(
            [
                "uv",
                "run",
                "python",
                "tools/update_readme.py",
                self.min_ver,
                self.max_ver,
            ],
            "Updating README structure",
        )

        # Formatting runs unconditionally.
        self.run_command(["uv", "run", "ruff", "check", ".", "--fix"], "Ruff Linting")
        self.run_command(["uv", "run", "ruff", "format", "."], "Ruff Formatting")

        parallel_tasks = [
            (
                ["uv", "run", "vulture", "src/", "--min-confidence", "80"],
                "Dead Code Analysis (Vulture)",
            ),
            (["uv", "run", "interrogate", "."], "Docstring Coverage Enforcement"),
        ]

        # Pytest executes in the test-matrix. Prevent redundant compute in CI.
        if not self.is_ci:
            parallel_tasks.append(
                (["uv", "run", "pytest"], "Unit Tests & Coverage Enforcement")
            )

        self.run_commands_parallel(parallel_tasks)

        if self.print_summary():
            self.run_command(
                ["uv", "run", "python", "build.py"], "Verifying Build Integrity"
            )
        else:
            self.record_result("Verifying Build Integrity", "SKIPPED")

        self.cleanup()

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
