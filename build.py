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
from pathlib import Path
from typing import ClassVar


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
        """Scans project source code for top-level module imports."""
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
        """Extracts top-level module names from a single Python file."""
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
        """Computes the final list of modules to exclude from the bundle."""
        imported = {i.lower() for i in self.find_all_imports()}

        # Logic: Exclude if BANNED_BLOAT OR is DEV_PACKAGES.
        # Dynamic exclusion is disabled to protect indirect dependencies.
        excludes = set()

        # 1. Add all dev packages, ensuring they aren't in PROTECTED
        for dev in self.DEV_PACKAGES:
            if dev not in self.PROTECTED:
                excludes.add(dev)

        # 2. Add bloat if not used and not in PROTECTED
        for bloat in self.BANNED_BLOAT:
            if bloat.lower() not in imported and bloat not in self.PROTECTED:
                excludes.add(bloat)

        return sorted(excludes)


def build_executable():
    """Orchestrates the optimized build process.

    1. Cleans previous build artifacts.
    2. Runs 'Tree Shaker' to identify exclusions.
    3. Executes PyInstaller with minimal dependency set.
    """
    print("🚀 Starting Optimized Build Process...")

    project_root = os.path.abspath(os.path.dirname(__file__))
    shaker = TreeShaker(project_root)

    # Clean old artifacts
    dirs_to_clean = ["build", "dist"]
    for d in dirs_to_clean:
        full_path = os.path.join(project_root, d)
        if os.path.exists(full_path):
            shutil.rmtree(full_path)

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
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name",
        "GroupBalancer",
        "--specpath",
        "build",
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
        os.makedirs("build", exist_ok=True)
        print(f"Running optimized command (Excludes: {len(excludes)} modules)")
        subprocess.run(cmd, check=True)
        print(f"\n✅ Build Complete! Check: {os.path.abspath('dist')}")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build Failed: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("\n❌ Error: PyInstaller not found. Please install it.")
        sys.exit(1)


if __name__ == "__main__":
    build_executable()
