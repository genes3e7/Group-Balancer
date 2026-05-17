"""
Build script to package the Group Balancer application into a standalone executable.

Uses PyInstaller to bundle the Streamlit app and core logic into a single file
or directory structure depending on the target distribution.

Enhanced with 'Tree Shaking' logic to exclude unused dependencies and minimize
the final bundle size and build time.
"""

import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import ClassVar

from packaging.requirements import Requirement


class TreeShaker:
    """Analyzes imports and environment to identify modules for exclusion.

    Identifies candidates for the PyInstaller --exclude-module flag by
    scanning project source code and comparing against installed packages.
    """

    # Static list of heavy or irrelevant libraries that should always be excluded
    # if not explicitly imported by the project.
    BANNED_BLOAT: ClassVar[frozenset[str]] = frozenset(
        {
            "tkinter",
            "tcl",
            "matplotlib",
            "scipy",
            "IPython",
            "ipykernel",
            "notebook",
            "jedi",
            "parso",
            "PIL",
            "pydeck",
            "bokeh",
            "plotly",
            "PyQt5",
            "PySide2",
            "sqlite3",
            "distutils",
            "setuptools",
            "wheel",
        }
    )

    # Packages known to be used by dev tools or testing but not the app itself.
    DEV_PACKAGES: ClassVar[frozenset[str]] = frozenset(
        {
            "pytest",
            "pytest-cov",
            "pytest-xdist",
            "coverage",
            "vulture",
            "interrogate",
            "ruff",
            "pymarkdownlnt",
            "pyinstaller",
            "pefile",
            "altgraph",
            "gitpython",
            "gitdb",
            "smmap",
        }
    )

    # Critical runtime dependencies that must never be excluded.
    PROTECTED: ClassVar[frozenset[str]] = frozenset(
        {"streamlit", "pandas", "numpy", "ortools", "openpyxl"}
    )

    def __init__(self, project_root: str) -> None:
        self.root = Path(project_root)
        self.import_re = re.compile(r"^(?:import|from)\s+([a-zA-Z0-9_]+)")

    def find_all_imports(self) -> set[str]:
        """Scans project source code for top-level module imports.

        Returns:
            set[str]: Unique top-level module names imported in the project.
        """
        found = set()
        # Scan src/ and top-level entry points
        scan_targets = [self.root / "src", self.root / "app.py"]

        for target in scan_targets:
            if target.is_file():
                found.update(self._scan_file(target))
            elif target.is_dir():
                for py_file in target.rglob("*.py"):
                    found.update(self._scan_file(py_file))
        return found

    def _scan_file(self, path: Path) -> set[str]:
        """Extracts top-level module names from a single Python file.

        Args:
            path (Path): Path to the Python file.

        Returns:
            set[str]: Module names extracted from import statements.
        """
        imports = set()
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    match = self.import_re.match(line.strip())
                    if match:
                        imports.add(match.group(1))
        except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
            print(f"⚠️ Warning: Failed to scan {path}: {e}")
        return imports

    def generate_exclusion_list(self) -> list[str]:
        """Identifies modules that are not required for production.

        Calculates the delta between installed packages and project imports,
        filtering through protected and banned lists.

        Returns:
            list[str]: Sorted list of module names for PyInstaller exclusion.
        """
        imported = {i.lower() for i in self.find_all_imports()}

        # Deterministic Baseline: Parse declared dependencies from pyproject.toml
        pyproject_path = self.root / "pyproject.toml"
        try:
            with open(pyproject_path, "rb") as f:
                pyproject = tomllib.load(f)

            project = pyproject.get("project", {})
            # Main dependencies
            deps = set()
            for req in project.get("dependencies", []):
                try:
                    deps.add(Requirement(req).name.lower())
                except Exception as e:
                    print(f"⚠️ Warning: Skipping invalid dependency '{req}': {e}")

            # Optional (dev) dependencies
            optional = pyproject.get("project", {}).get("optional-dependencies", {})
            for group in optional.values():
                for req in group:
                    try:
                        deps.add(Requirement(req).name.lower())
                    except Exception as e:
                        print(
                            f"⚠️ Warning: Skipping invalid dev dependency '{req}': {e}"
                        )
        except (FileNotFoundError, PermissionError) as e:
            print(f"⚠️ Warning: Failed to parse pyproject.toml: {e}")
            deps = set()

        # Calculate delta: declared but not imported (candidates for exclusion)
        dynamic_delta = (deps - imported) - {p.lower() for p in self.PROTECTED}

        excludes = set()

        # Step 1: Explicit Banned Bloat (if not used)
        for mod in self.BANNED_BLOAT:
            if mod.lower() not in imported:
                excludes.add(mod)

        # Step 2: Explicit Development Packages (if not in PROTECTED)
        excludes.update(self.DEV_PACKAGES - self.PROTECTED)

        # Step 3: Dynamic Delta (packages declared in pyproject but not used)
        excludes.update(dynamic_delta)

        # Step 4: Absolute Protection
        excludes -= self.PROTECTED

        return sorted(excludes)


def build_executable():
    """Execute the PyInstaller build process with tree-shaken exclusions.

    1. Cleans previous build artifacts.
    2. Runs 'Tree Shaker' to identify exclusions.
    3. Executes PyInstaller with minimal dependency set.
    """
    pyinstaller_bin = shutil.which("pyinstaller")
    if not pyinstaller_bin:
        print("\n❌ Error: PyInstaller not found in PATH.")
        sys.exit(1)

    project_root = os.path.abspath(os.path.dirname(__file__))
    shaker = TreeShaker(project_root)

    build_dir = os.path.join(project_root, "build")
    dist_dir = os.path.join(project_root, "dist")

    # Clean old artifacts
    dirs_to_clean = [build_dir, dist_dir]
    for d in dirs_to_clean:
        if os.path.exists(d):
            shutil.rmtree(d)

    spec_path = os.path.join(project_root, "GroupBalancer.spec")
    if os.path.exists(spec_path):
        os.remove(spec_path)

    # Tree Shaking
    print("🌳 Detecting unused dependencies (Tree Shaking)...")
    excludes = shaker.generate_exclusion_list()
    print(f"📉 Excluding {len(excludes)} modules to shrink bundle...")

    # PyInstaller Command
    app_path = os.path.join(project_root, "app.py")
    src_path = os.path.join(project_root, "src")
    launcher_path = os.path.join(project_root, "streamlit_launcher.py")

    cmd = [
        pyinstaller_bin,
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name",
        "GroupBalancer",
        "--specpath",
        build_dir,
        "--clean",  # Ensure fresh analysis
        "--noupx",  # Speed up build and prevent extraction slowdown
    ]

    # Add exclusions
    for mod in excludes:
        cmd.extend(["--exclude-module", mod])

    # Data inclusions
    cmd.extend(
        [
            "--add-data",
            f"{app_path}{os.pathsep}.",
            "--add-data",
            f"{src_path}{os.pathsep}src",
            launcher_path,
        ]
    )

    try:
        os.makedirs(build_dir, exist_ok=True)
        print(f"Running optimized command (Excludes: {len(excludes)} modules)")
        subprocess.run(cmd, check=True)
        print(f"\n✅ Build Complete! Check: {dist_dir}")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build Failed: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("\n❌ Error: PyInstaller not found. Please install it.")
        sys.exit(1)


if __name__ == "__main__":
    build_executable()
