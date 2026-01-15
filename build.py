import PyInstaller.__main__
import os
import shutil


def build_executable():
    print("🚀 Starting Build Process...")

    args = [
        "group_balancer.py",
        "--name=GroupBalancer",
        "--onefile",
        "--clean",
        "--noconfirm",
        "--hidden-import=ortools",
        "--hidden-import=pandas",
        # Ensure src packages are found
        "--paths=.",
        "--exclude-module=matplotlib",
        "--exclude-module=tkinter",
        "--console",
    ]

    PyInstaller.__main__.run(args)
    print(f"\n✅ Build Complete! Check: {os.path.abspath('dist')}")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Clean previous builds and cache
    for folder in ["build", "dist", "__pycache__"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)

    # Clean internal src caches
    if os.path.exists("src"):
        for root, dirs, files in os.walk("src"):
            if "__pycache__" in dirs:
                shutil.rmtree(os.path.join(root, "__pycache__"))

    build_executable()
