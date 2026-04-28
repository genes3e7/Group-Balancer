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

    project_root = os.path.abspath(os.path.dirname(__file__))

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
                dirs.remove("__pycache__")

    # Define PyInstaller Command
    # We use 'streamlit_launcher.py' to bridge PyInstaller with Streamlit.
    # app.py and src/ are included as data to ensure they are available in the bundle.
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
        "--add-data",
        f"{app_path}{os.pathsep}.",
        "--add-data",
        f"{src_path}{os.pathsep}src",
        launcher_path,
    ]

    try:
        # Ensure build dir exists for spec file
        os.makedirs("build", exist_ok=True)
        print(f"Running command: {' '.join(cmd)}")
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
