"""
Build script to package the Group Balancer application into a standalone executable.

Uses PyInstaller to bundle the Streamlit app and core logic into a single file
or directory structure depending on the target distribution.
"""

import os
import shutil
import subprocess
import sys


def build_executable():
    """Orchestrates the build process.

    1. Cleans previous build artifacts.
    2. Executes PyInstaller with specific hooks for Streamlit.
    3. Verifies output.
    """
    print("🚀 Starting Build Process...")

    # Clean old artifacts
    dirs_to_clean = ["build", "dist"]
    for d in dirs_to_clean:
        if os.path.exists(d):
            shutil.rmtree(d)

    # Clean legacy spec files from root
    if os.path.exists("GroupBalancer.spec"):
        os.remove("GroupBalancer.spec")

    # Clean internal src caches
    if os.path.exists("src"):
        for root, dirs, _ in os.walk("src"):
            if "__pycache__" in dirs:
                shutil.rmtree(os.path.join(root, "__pycache__"))

    # Define PyInstaller Command
    # We bundle 'app.py' which launches the Streamlit UI.
    # --noconfirm: Overwrite existing
    # --onedir: Create a distribution folder
    # --windowed: Disable the console window
    # --specpath: Place spec file in build dir
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name",
        "GroupBalancer",
        "--specpath",
        "build",
        "app.py",
    ]

    try:
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
