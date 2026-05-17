"""Launcher entry point for PyInstaller bundle.

This script ensures Streamlit can be launched as a standalone process
from within the PyInstaller compressed environment.
"""

import os
import sys
from pathlib import Path

import streamlit.web.cli as stcli


def main() -> None:
    """Launcher entry point for PyInstaller bundle."""
    # Determine the root directory of the bundle
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)).resolve()

    # Configure Streamlit arguments
    sys.argv = [
        "streamlit",
        "run",
        str(bundle_root / "app.py"),
        "--server.headless=true",
    ]

    # Explicitly set the environment variable for headless mode
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"

    # Launch Streamlit
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
