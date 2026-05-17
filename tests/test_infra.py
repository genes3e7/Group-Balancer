"""Infrastructure tests for root-level scripts."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import app
import build

# Expected Counts for Verification
EXPECTED_RM_COUNT = 2
EXPECTED_DATA_ARGS = 2


def test_build_executable_cleanup() -> None:
    """Test that build_executable cleans up old directories."""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("shutil.rmtree") as mock_rm,
        patch("pathlib.Path.unlink") as mock_remove,
        patch("shutil.which", return_value="/usr/bin/pyinstaller"),
        patch("subprocess.run"),
    ):
        build.build_executable()

        # Verify cleanup of build and dist
        assert mock_rm.call_count >= EXPECTED_RM_COUNT
        # Verify cleanup of spec
        assert mock_remove.called


def test_build_executable_success() -> None:
    """Test successful execution of PyInstaller command."""
    with (
        patch("pathlib.Path.exists", return_value=False),
        patch.object(build.shutil, "which", return_value="uv"),
        patch.object(build.subprocess, "run") as mock_run,
    ):
        # Only call: pyinstaller
        mock_run.return_value = MagicMock(returncode=0)

        build.build_executable()

        # Verify the resolved binary was used
        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "uv"
        for flag in ("--clean", "--noupx", "--noconfirm", "--onedir", "--windowed"):
            assert flag in cmd, f"Missing required flag: {flag}"

        # Critical bundled artifacts must be present in --add-data
        # Format: --add-data src:dest
        add_data_indices = [i for i, item in enumerate(cmd) if item == "--add-data"]
        assert len(add_data_indices) == EXPECTED_DATA_ARGS

        # Check source paths (the item immediately following --add-data)
        # Handle both ';' (Windows) and ':' (Linux) separators
        add_data_sources = []
        for i in add_data_indices:
            arg = cmd[i + 1]
            source = arg.split(os.pathsep)[0]
            add_data_sources.append(source)

        assert any("app.py" in s for s in add_data_sources)
        assert any("src" in s for s in add_data_sources)

        # Verify the main entry point is present via exact basename check
        entrypoint = [token for token in cmd if not token.startswith("-")][-1]
        assert Path(entrypoint).name == "streamlit_launcher.py"


def test_app_importable() -> None:
    """Check that app.py can be imported."""
    assert app.__name__ == "app"
