"""Group Balancer: Local Pre-CI Script."""

import argparse
import concurrent.futures
import os
import pathlib
import shutil
import subprocess
import sys
from typing import ClassVar


class PreCIPipeline:
    """Orchestrates the local and CI validation checks for the project.

    Attributes:
        STATUS_MAP (dict): Maps boolean or string outcomes to visual status labels.
        _results (list): Internal log of (description, status, outputs) tuples.
        is_ci (bool): True if executing within a remote CI environment.
        min_ver (str): Minimum supported Python version for README updates.
        max_ver (str): Maximum supported Python version for README updates.
    """

    STATUS_MAP: ClassVar[dict[bool | str, str]] = {
        True: "✅ PASS",
        False: "❌ FAIL",
        "SKIPPED": "⏭️  SKIP",
    }

    def __init__(self, min_ver: str = "3.10", max_ver: str = "3.14") -> None:
        """Initializes the PreCIPipeline with Python version bounds.

        Args:
            min_ver: The minimum supported Python version string (e.g. "3.10").
            max_ver: The maximum supported Python version string (e.g. "3.14").
        """
        self._results: list[tuple[str, bool | str, dict[str, str] | None]] = []
        self.is_ci = os.environ.get("CI", "").lower() in ("true", "1", "yes")
        self.min_ver = min_ver
        self.max_ver = max_ver

    def record_result(
        self,
        description: str,
        passed: bool | str,
        outputs: dict[str, str] | None = None,
    ) -> None:
        """Records the outcome of a specific pipeline step.

        Args:
            description: Human-readable label for the step being recorded.
            passed: ``True`` on success, ``False`` on failure, or ``"SKIPPED"``
                when a step is intentionally bypassed.
            outputs: Optional dict with 'stdout' and 'stderr' captured content.

        Returns:
            None
        """
        self._results.append((description, passed, outputs))

    def run_command(
        self, command: list[str], description: str, fail_fast: bool = False
    ) -> bool:
        """Executes a single shell command and records its pass/fail status.

        Args:
            command: The command and its arguments as a list of strings,
                e.g. ``["uv", "run", "ruff", "check", "."]``.
            description: Human-readable label printed before and after execution.
            fail_fast: When ``True``, calls ``sys.exit`` immediately on non-zero
                return code instead of returning ``False``.

        Returns:
            ``True`` if the command exits with code 0, ``False`` otherwise.
        """
        print(f"\n>>> [Step: {description}]", flush=True)
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            result = subprocess.run(  # noqa: S603
                command,
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
                env=env,
            )

            # Stream stdout/stderr back since we captured it successfully
            if result.stdout:
                print(result.stdout, end="", file=sys.stdout, flush=True)
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr, flush=True)

            print(f"✅ {description} completed successfully.", flush=True)
            self.record_result(
                description, True, {"stdout": result.stdout, "stderr": result.stderr}
            )
            return True

        except subprocess.CalledProcessError as e:
            print(
                f"\n❌ FATAL: '{description}' failed with exit code {e.returncode}",
                flush=True,
            )
            if e.stdout:
                print("--- STDOUT ---", flush=True)
                print(e.stdout, end="", file=sys.stdout, flush=True)
            if e.stderr:
                print("--- STDERR ---", flush=True)
                print(e.stderr, end="", file=sys.stderr, flush=True)

            # Attach captured outputs to the failure record
            self.record_result(
                description, False, {"stdout": e.stdout, "stderr": e.stderr}
            )
            if fail_fast:
                sys.exit(e.returncode)
            return False
        except (subprocess.SubprocessError, OSError) as e:
            print(f"\n❌ FATAL: '{description}' error: {e}", flush=True)
            self.record_result(description, False, {"stdout": "", "stderr": str(e)})

            if fail_fast:
                sys.exit(1)
            return False

    def run_commands_parallel(self, tasks: list[tuple[list[str], str]]) -> bool:
        """Executes multiple shell commands concurrently via a thread pool.

        Each task is submitted to a ``ThreadPoolExecutor``. stdout/stderr from
        every subprocess is captured and printed after all futures complete.
        Failures are aggregated; no individual failure short-circuits the others.

        Args:
            tasks: A list of ``(command, description)`` tuples where ``command``
                is a list of strings (as in ``run_command``) and ``description``
                is the human-readable step label.

        Returns:
            ``True`` if every task exits with code 0, ``False`` if any task fails.
        """
        print("\n>>> [Parallel Execution] Starting concurrent checks...", flush=True)
        success_overall = True
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_desc = {
                executor.submit(
                    subprocess.run,  # noqa: S603
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
                    print(f"\n--- Output from {desc} ---", flush=True)
                    if result.stdout:
                        print(result.stdout.strip(), flush=True)
                    if result.stderr:
                        print(result.stderr.strip(), flush=True)

                    if result.returncode == 0:
                        print(f"✅ {desc} completed successfully.", flush=True)
                        self.record_result(
                            desc,
                            True,
                            {"stdout": result.stdout, "stderr": result.stderr},
                        )
                    else:
                        print(
                            f"❌ FATAL: '{desc}' failed with exit code "
                            f"{result.returncode}",
                            flush=True,
                        )
                        self.record_result(
                            desc,
                            False,
                            {"stdout": result.stdout, "stderr": result.stderr},
                        )
                        success_overall = False
                except (subprocess.SubprocessError, OSError) as exc:
                    print(
                        f"\n❌ FATAL: '{desc}' generated an exception: {exc}",
                        flush=True,
                    )
                    self.record_result(desc, False, {"stdout": "", "stderr": str(exc)})
                    success_overall = False

        return success_overall

    def all_passed(self) -> bool:
        """Predicate to check if every recorded result is a strict PASS.

        Returns:
            bool: True iff every result is exactly True.
        """
        return all(passed is True for _, passed, _ in self._results)

    def print_summary(self, title: str = "📋 PRE-CI SUMMARY") -> bool:
        """Prints a formatted table of all recorded step results.

        Args:
            title: The heading printed above the summary table.

        Returns:
            ``True`` if there are no explicit ``False`` results (i.e., ``True``
            and ``"SKIPPED"`` entries are treated as non-failures);
            ``False`` otherwise.
        """
        print("\n" + "=" * 60, flush=True)
        print(title, flush=True)
        print("=" * 60, flush=True)

        all_passed = True
        for description, passed, _ in self._results:
            status_label = self.STATUS_MAP.get(passed, "❓ UNKNOWN")
            print(f"{status_label.ljust(10)} | {description}", flush=True)
            if passed is False:
                all_passed = False

        print("=" * 60, flush=True)
        return all_passed

    def cleanup(self) -> None:
        """Removes build artifacts and caches from the local workspace.

        Args:
            None

        Returns:
            None
        """
        print("\n>>> [Cleanup] Purging caches and build artifacts...", flush=True)
        root = pathlib.Path(".")

        # Standard top-level targets that we want to remove explicitly
        base_targets = [
            "build",
            "dist",
            ".ruff_cache",
            ".pytest_cache",
            ".coverage",
            "python_version_*.txt",
            "artifacts",
        ]

        # Dynamically find nested artifacts, explicitly skipping venvs and hidden dirs
        venv_names = {"venv", ".venv", "env"}
        if os.environ.get("VIRTUAL_ENV"):
            venv_names.add(pathlib.Path(os.environ["VIRTUAL_ENV"]).name)

        folders = []
        for base in base_targets:
            folders.extend(root.glob(base))

        for dirpath, dirnames, _filenames in os.walk(root):
            path = pathlib.Path(dirpath)

            # Skip common environment and hidden directories
            if path.name in venv_names or path.name.startswith("."):
                dirnames[:] = []  # Don't recurse into these
                continue

            # Identify and prune artifacts in the current (non-skipped) directory
            for d in list(dirnames):
                if d == "__pycache__" or d.endswith(".egg-info"):
                    folders.append(path / d)
                    dirnames.remove(d)

        for target in sorted(set(folders)):
            self._remove_path(target)

    def _remove_path(self, path: pathlib.Path) -> None:
        """Removes a file or directory, suppressing errors.

        Args:
            path: The path to the file or directory to remove.

        Returns:
            None
        """
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
        except OSError as e:
            print(f"⚠️ Warning: Could not remove {path}: {e}", flush=True)

    def execute(self) -> None:
        """Runs the full Pre-CI gate sequence and exits non-zero on failure.

        Execution order: environment sync → README update → Ruff lint/format →
        parallel (Vulture + Interrogate [+ Pytest if not CI]) → summary →
        optional build verification → cleanup → final summary.

        Args:
            None

        Returns:
            None
        """
        print("\n" + "=" * 60, flush=True)
        mode = "CI PIPELINE" if self.is_ci else "LOCAL PRE-CI"
        print(f"🚀 GROUP BALANCER {mode} GATE", flush=True)
        print("=" * 60, flush=True)

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
            print("\n✨ ALL CHECKS PASSED.\n", flush=True)
        else:
            print("\n❌ Pipeline failed. See logs above.\n", flush=True)
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
