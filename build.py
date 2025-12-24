import PyInstaller.__main__
import os
import shutil


def build_executable():
    """
    Builds the Group Balancer executable using PyInstaller.
    """
    print("🚀 Starting Build Process...")

    # Define the PyInstaller arguments
    args = [
        "group_balancer.py",  # Main script
        "--name=GroupBalancer",  # Name of the executable
        "--onefile",  # Bundle everything into a single file
        "--clean",  # Clean PyInstaller cache
        "--noconfirm",  # Do not confirm overwrite
        # Data & Imports
        # OR-Tools often needs hidden imports specified if PyInstaller misses them
        "--hidden-import=ortools",
        "--hidden-import=pandas",
        # Exclude unnecessary heavy modules to save space (optional)
        "--exclude-module=matplotlib",
        "--exclude-module=tkinter",
        # Console window is needed for user input/output
        "--console",
    ]

    # Run PyInstaller
    PyInstaller.__main__.run(args)

    print("\n✅ Build Complete!")
    print(f"Executable is located in: {os.path.abspath('dist')}")


if __name__ == "__main__":
    # Ensure we are in the script's directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Clean previous builds
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")

    build_executable()
