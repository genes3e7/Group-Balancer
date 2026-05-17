"""Group Balancer: Local Pre-CI Script."""

import argparse
import concurrent.futures
import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import ClassVar

DEFAULT_MIN_PY = "3.11"
DEFAULT_MAX_PY = "3.14"


class PreCIPipeline:
    """Orchestrates the local and CI validation checks for the project.

    Attributes:
        STATUS_MAP (dict): Maps boolean or string outcomes to visual status labels.
        _results (list): Internal log of (description, passed) tuples.
        is_ci (bool): True if executing within a remote CI environment.
        min_ver (str): Minimum supported Python version for README updates.
        max_ver (str): Maximum supported Python version for README updates.
    """

    STATUS_MAP: ClassVar[dict[bool | str, str]] = {
        True: "✅ PASS",
        False: "❌ FAIL",
        "SKIPPED": "⏭️  SKIP",
    }

    def __init__(
        self, min_ver: str = DEFAULT_MIN_PY, max_ver: str = DEFAULT_MAX_PY
    ) -> None:
        """Initializes the PreCIPipeline with Python version bounds.

        Args:
            min_ver: The minimum supported Python version string (e.g. "3.11").
            max_ver: The maximum supported Python version string (e.g. "3.14").
        """
        self._results: list[tuple[str, bool | str]] = []
        self.is_ci = os.environ.get("CI", "").lower() in ("true", "1", "yes")
        self.min_ver = min_ver
        self.max_ver = max_ver

    def record_result(
        self,
        description: str,
        passed: bool | str,
    ) -> None:
        """Records the outcome of a specific pipeline step.

        Args:
            description: Human-readable label for the step being recorded.
            passed: ``True`` on success, ``False`` on failure, or ``"SKIPPED"``
                when a step is intentionally bypassed.
        """
        self._results.append((description, passed))

    def run_command(
        self, command: list[str], description: str, fail_fast: bool = False
    ) -> bool:
        """Executes a single shell command and records its pass/fail status.

        Args:
            command: The command and its arguments as a list of strings.
            description: Human-readable label printed before and after execution.
            fail_fast: When ``True``, calls ``sys.exit`` immediately on failure.

        Returns:
            ``True`` if the command exits with code 0, ``False`` otherwise.
        """
        print(f"\n>>> [Step: {description}]", flush=True)
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            # capture_output=False (default) streams directly to our stdout/stderr
            subprocess.run(  # noqa: S603
                command,
                check=True,
                env=env,
            )
        except (
            subprocess.CalledProcessError,
            subprocess.SubprocessError,
            OSError,
        ) as e:
            ret_code = getattr(e, "returncode", 1)
            print(
                f"\n❌ FATAL: '{description}' failed with code {ret_code}: {e}",
                flush=True,
            )
            self.record_result(description, False)
            if fail_fast:
                sys.exit(ret_code)
            return False
        else:
            print(f"✅ {description} completed successfully.", flush=True)
            self.record_result(description, True)
            return True

    def run_commands_parallel(self, tasks: list[tuple[list[str], str]]) -> bool:
        """Executes multiple shell commands concurrently via a thread pool.

        Args:
            tasks: A list of ``(command, description)`` tuples.

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
                success_overall &= self._process_parallel_result(future, desc)

        return success_overall

    def _process_parallel_result(
        self, future: concurrent.futures.Future, desc: str
    ) -> bool:
        """Helper to process and log a single parallel command result."""
        try:
            result = future.result()
            print(f"\n--- Output from {desc} ---", flush=True)
            if result.stdout:
                print(result.stdout.strip(), flush=True)
            if result.stderr:
                print(result.stderr.strip(), flush=True)

            if result.returncode != 0:
                ret = result.returncode
                print(f"❌ FATAL: '{desc}' failed with code {ret}", flush=True)
                self.record_result(desc, False)
                return False
        except (subprocess.SubprocessError, OSError) as exc:
            print(f"\n❌ FATAL: '{desc}' generated an exception: {exc}", flush=True)
            self.record_result(desc, False)
            return False
        else:
            print(f"✅ {desc} completed successfully.", flush=True)
            self.record_result(desc, True)
            return True

    def all_passed(self) -> bool:
        """Predicate to check if every recorded result is a strict PASS.

        Returns:
            bool: True iff every result is exactly True.
        """
        return all(passed is True for _, passed in self._results)

    def print_summary(self, title: str = "📋 PRE-CI SUMMARY") -> bool:
        """Prints a formatted table of all recorded step results.

        Args:
            title: The heading printed above the summary table.

        Returns:
            ``True`` if there are no explicit ``False`` results.
        """
        print("\n" + "=" * 60, flush=True)
        print(title, flush=True)
        print("=" * 60, flush=True)

        no_failures = True
        for description, passed in self._results:
            status_label = self.STATUS_MAP.get(passed, "❓ UNKNOWN")
            print(f"{status_label.ljust(10)} | {description}", flush=True)
            if passed is False:
                no_failures = False

        print("=" * 60, flush=True)
        return no_failures

    def cleanup(self) -> None:
        """Removes build artifacts and caches from the local workspace."""
        print("\n>>> [Cleanup] Purging caches and build artifacts...", flush=True)
        root = pathlib.Path()
        self._cleanup_standard_targets(root)
        self._cleanup_nested_pycache(root)

    def _cleanup_standard_targets(self, root: pathlib.Path) -> None:
        """Internal helper to remove top-level artifacts."""
        base_targets = [
            "build",
            "dist",
            ".ruff_cache",
            ".pytest_cache",
            ".coverage",
            "python_version_*.txt",
            "artifacts",
        ]
        for pattern in base_targets:
            for path in root.glob(pattern):
                self._remove_path(path)

    def _cleanup_nested_pycache(self, root: pathlib.Path) -> None:
        """Recursively finds and removes __pycache__ and egg-info."""
        for dirpath, dirnames, _ in os.walk(root):
            path = pathlib.Path(dirpath)
            # Prune descent into venvs
            if ".venv" in dirnames:
                dirnames.remove(".venv")
            if "venv" in dirnames:
                dirnames.remove("venv")

            for d in list(dirnames):
                if d == "__pycache__" or d.endswith(".egg-info"):
                    self._remove_path(path / d)
                    dirnames.remove(d)

    def _remove_path(self, path: pathlib.Path) -> None:
        """Removes a file or directory, suppressing errors."""
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
        except OSError as e:
            print(f"⚠️ Warning: Could not remove {path}: {e}", flush=True)

    def execute(self) -> None:
        """Runs the full Pre-CI gate sequence and exits non-zero on failure."""
        try:
            self._phase_prepare()
            self._phase_static_analysis()
            self._phase_unit_tests()
            self._phase_style_and_lint()
            self._phase_build()

        finally:
            self.cleanup()
            self._report_final()

    def _phase_prepare(self) -> None:
        """Environment preparation phase."""
        print("\n" + "=" * 60, flush=True)
        mode = "CI PIPELINE" if self.is_ci else "LOCAL PRE-CI"
        print(f"🚀 GROUP BALANCER {mode} GATE", flush=True)
        print("=" * 60, flush=True)

        uv_path = shutil.which("uv")
        if not uv_path:
            print("\n❌ FATAL: 'uv' executable not found in PATH.", flush=True)
            sys.exit(1)

        self.run_command(
            [uv_path, "sync", "--all-extras", "--frozen"],
            "Syncing Project Environment",
            fail_fast=True,
        )

        # 2. Update README
        print("\n>>> [Step: Updating README structure]", flush=True)
        env = os.environ.copy()
        res = subprocess.run(  # noqa: S603
            [
                uv_path,
                "run",
                "--no-sync",
                "python",
                "tools/update_readme.py",
                self.min_ver,
                self.max_ver,
            ],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            env=env,
        )
        if res.stdout:
            print(res.stdout.strip(), flush=True)
        if res.stderr:
            print(res.stderr.strip(), flush=True)

        if res.returncode != 0 or re.search(
            r"^ERROR:|^CRITICAL:", res.stdout + res.stderr, re.MULTILINE
        ):
            print("\n❌ FATAL: 'Updating README structure' failed.", flush=True)
            self.record_result("Updating README structure", False)
            sys.exit(1)

        print("✅ Updating README structure completed successfully.", flush=True)
        self.record_result("Updating README structure", True)

    def _phase_static_analysis(self) -> None:
        """Parallel static analysis phase."""
        uv_path = shutil.which("uv")
        parallel_tasks = [
            (
                [
                    uv_path,
                    "run",
                    "--no-sync",
                    "vulture",
                    "src/",
                    "--min-confidence",
                    "80",
                ],
                "Dead Code Analysis (Vulture)",
            ),
        ]
        success_parallel = self.run_commands_parallel(parallel_tasks)
        if not success_parallel:
            print("\n❌ FATAL: Parallel checks failed. Aborting.", flush=True)
            sys.exit(1)

    def _phase_unit_tests(self) -> None:
        """Functional testing phase."""
        if not self.is_ci:
            uv_path = shutil.which("uv")
            self.run_command(
                [
                    uv_path,
                    "run",
                    "--no-sync",
                    "pytest",
                    "-v",
                    "--cov=src",
                    "--cov-report=term-missing",
                    "--cov-fail-under=95",
                ],
                "Unit Tests & Coverage Enforcement",
                fail_fast=True,
            )

    def _phase_style_and_lint(self) -> None:
        """Linting and formatting phase."""
        uv_path = shutil.which("uv")
        if self.is_ci:
            self.run_command(
                [uv_path, "run", "--no-sync", "ruff", "check", "."],
                "Ruff Linting",
                fail_fast=True,
            )
            self.run_command(
                [uv_path, "run", "--no-sync", "ruff", "format", "--check", "."],
                "Ruff Formatting",
                fail_fast=True,
            )
            self.run_command(
                [uv_path, "run", "--no-sync", "pymarkdown", "scan", "."],
                "Markdown Linting",
                fail_fast=True,
            )
        else:
            self.run_command(
                [uv_path, "run", "--no-sync", "pymarkdown", "scan", "."],
                "Markdown Linting",
                fail_fast=True,
            )
            if self.all_passed():
                self.run_command(
                    [uv_path, "run", "--no-sync", "ruff", "check", ".", "--fix"],
                    "Ruff Linting",
                    fail_fast=True,
                )
                self.run_command(
                    [uv_path, "run", "--no-sync", "ruff", "format", "."],
                    "Ruff Formatting",
                    fail_fast=True,
                )

    def _phase_build(self) -> None:
        """Build integrity phase."""
        if self.all_passed():
            uv_path = shutil.which("uv")
            self.run_command(
                [uv_path, "run", "--no-sync", "python", "build.py"],
                "Verifying Build Integrity",
                fail_fast=True,
            )

    def _report_final(self) -> None:
        """Final reporting and exit."""
        if self.print_summary(title="📋 FINAL PRE-CI SUMMARY"):
            print("\n✨ ALL CHECKS PASSED.\n", flush=True)
        else:
            print("\n❌ Pipeline failed. See logs above.\n", flush=True)
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Group Balancer Pre-CI Gate")
    parser.add_argument(
        "min_ver",
        nargs="?",
        default=None,
        help="Minimum supported Python version",
    )
    parser.add_argument(
        "max_ver",
        nargs="?",
        default=None,
        help="Maximum supported Python version",
    )
    args = parser.parse_args()

    # Regex for semantic-ish versions like 3.11 or 3.14-dev
    _ver_re = re.compile(r"^\d+\.\d+(?:-[a-zA-Z0-9]+)?$")

    def _validate(label: str, val: str | None, fallback: str) -> str:
        if val is None:
            return fallback
        if not _ver_re.match(val):
            print(
                f"❌ FATAL: {label}={val!r} is not a valid version "
                f"(expected e.g. '3.11' or '3.14-dev').",
                flush=True,
            )
            sys.exit(2)
        return val

    validated_min = _validate("min_ver", args.min_ver, DEFAULT_MIN_PY)
    validated_max = _validate("max_ver", args.max_ver, DEFAULT_MAX_PY)

    def _ver_tuple(v: str) -> tuple[int, int]:
        """Parses a version string into a (major, minor) integer tuple."""
        # Handles 3.11 and 3.14-dev
        parts = v.split("-", 1)[0].split(".")
        return int(parts[0]), int(parts[1])

    if _ver_tuple(validated_min) > _ver_tuple(validated_max):
        print(
            f"❌ FATAL: min_ver={validated_min!r} > max_ver={validated_max!r} "
            "is an invalid range.",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)

    pipeline = PreCIPipeline(validated_min, validated_max)
    pipeline.execute()
