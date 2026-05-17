"""Build script to package the Group Balancer application into a standalone executable.

Uses PyInstaller to bundle the Streamlit app and core logic into a single file
or directory structure depending on the target distribution.

Enhanced with 'Tree Shaking' logic to exclude unused dependencies and minimize
the final bundle size and build time.
"""

import importlib.metadata
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
    scanning project source code and comparing against all installed packages
    in the current environment.
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
        {"streamlit", "pandas", "numpy", "ortools", "openpyxl", "src"}
    )

    def __init__(self, project_root: str) -> None:
        """Initializes the TreeShaker with the project root path.

        Args:
            project_root (str): The absolute path to the project root.
        """
        self.root = Path(project_root)
        # Regex updated to allow leading whitespace for lazy imports
        self.import_re = re.compile(r"^\s*(?:import|from)\s+([a-zA-Z0-9_]+)")

    def find_all_imports(self) -> set[str]:
        """Scans project source code for top-level module imports.

        Returns:
            set[str]: Unique top-level module names imported in the project.
        """
        found = set()
        # Scan src/, app.py, and all top-level entry points
        scan_targets = [
            self.root / "src",
            self.root / "app.py",
            self.root / "group_balancer.py",
            self.root / "streamlit_launcher.py",
        ]

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
            with path.open(encoding="utf-8") as f:
                for line in f:
                    match = self.import_re.match(line)
                    if match:
                        imports.add(match.group(1))
        except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
            print(f"⚠️ Warning: Failed to scan {path}: {e}")
        return imports

    def generate_exclusion_list(self) -> list[str]:
        """Identifies modules that are not required for production.

        Calculates the delta between all installed packages and project imports,
        ensuring indirect bloat is captured.

        Returns:
            list[str]: Sorted list of module names for PyInstaller exclusion.
        """
        imported = {i.lower() for i in self.find_all_imports()}

        # Aggressive Environmental Baseline:
        # Detect ALL packages in the current venv. If it's installed but not
        # explicitly imported (and not protected), exclude it.
        try:
            installed = {
                pkg.metadata["Name"].lower()
                for pkg in importlib.metadata.distributions()
            }
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ Warning: Failed to detect environment packages: {e}")
            installed = set()

        # Calculate delta: installed in environment but not used by code
        dynamic_excludes = (installed - imported) - {p.lower() for p in self.PROTECTED}

        excludes = set()

        # Step 1: Explicit Banned Bloat (Guaranteed removal of heavy-hitters)
        excludes.update(self.BANNED_BLOAT)

        # Step 2: Explicit Development Packages
        excludes.update(self.DEV_PACKAGES)

        # Step 3: Dynamic Environmental Excludes (transitive and unused packages)
        excludes.update(dynamic_excludes)

        # Step 4: Absolute Protection Guard
        # Ensure we never accidentally exclude a module that we actually import
        # or that is vital for the runtime.
        excludes = {e for e in excludes if e.lower() not in imported}
        excludes -= self.PROTECTED

        return sorted(excludes)


def build_executable() -> None:
    """Execute the PyInstaller build process with tree-shaken exclusions.

    1. Cleans previous build artifacts.
    2. Runs 'Tree Shaker' to identify exclusions.
    3. Executes PyInstaller with minimal dependency set.
    """
    pyinstaller_bin = shutil.which("pyinstaller")
    if not pyinstaller_bin:
        print("\n❌ Error: PyInstaller not found in PATH.")
        sys.exit(1)

    project_root = Path(__file__).parent.resolve()
    shaker = TreeShaker(str(project_root))

    build_dir = project_root / "build"
    dist_dir = project_root / "dist"

    # Clean old artifacts
    dirs_to_clean = [build_dir, dist_dir]
    for d in dirs_to_clean:
        if d.exists():
            shutil.rmtree(d)

    spec_path = project_root / "GroupBalancer.spec"
    if spec_path.exists():
        spec_path.unlink()

    # Tree Shaking
    print("🌳 Detecting unused dependencies (Tree Shaking)...")
    excludes = shaker.generate_exclusion_list()
    print(f"📉 Excluding {len(excludes)} modules to shrink bundle...")

    # PyInstaller Command
    app_path = project_root / "app.py"
    src_path = project_root / "src"
    launcher_path = project_root / "streamlit_launcher.py"

    cmd = [
        pyinstaller_bin,
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name",
        "GroupBalancer",
        "--specpath",
        str(build_dir),
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
            str(launcher_path),
        ]
    )

    try:
        build_dir.mkdir(parents=True, exist_ok=True)
        print(f"Running optimized command (Excludes: {len(excludes)} modules)")
        subprocess.run(cmd, check=True)  # noqa: S603
        print(f"\n✅ Build Complete! Check: {dist_dir}")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build Failed: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("\n❌ Error: PyInstaller not found. Please install it.")
        sys.exit(1)


if __name__ == "__main__":
    build_executable()
