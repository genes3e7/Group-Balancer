"""launcher to allow PyInstaller to run Streamlit correctly."""

import os
import sys

import streamlit.web.cli


def main():
    """Launcher entry point for PyInstaller bundle."""
    # Determine the root directory of the bundle
    bundle_root = getattr(sys, "_MEIPASS", os.path.dirname(__file__))

    # Configure Streamlit arguments
    # We want to run: streamlit run app.py --server.headless=true
    sys.argv = [
        "streamlit",
        "run",
        os.path.join(bundle_root, "app.py"),
        "--server.headless=true",
    ]

    # Invoke Streamlit's CLI
    sys.exit(streamlit.web.cli.main())


if __name__ == "__main__":
    main()
