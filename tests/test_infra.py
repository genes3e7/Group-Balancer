"""Infrastructure tests for root-level scripts."""

import os
from unittest.mock import MagicMock, patch

import app
import build


def test_build_executable_cleanup() -> None:
    """Test that build_executable cleans up old directories."""
    with (
        patch("os.path.exists", return_value=True),
        patch("shutil.rmtree") as mock_rm,
        patch("os.remove") as mock_remove,
        patch("subprocess.run"),
    ):
        build.build_executable()

        # Verify cleanup of build and dist
        assert mock_rm.call_count >= 2
        # Verify cleanup of spec
        assert mock_remove.called


def test_build_executable_success() -> None:
    """Test successful execution of PyInstaller command."""
    with (
        patch("os.path.exists", return_value=False),
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
        assert len(add_data_indices) == 2

        # Check source paths (the item immediately following --add-data)
        add_data_sources = [cmd[i + 1].split(os.pathsep)[0] for i in add_data_indices]
        assert any("app.py" in s for s in add_data_sources)
        assert any("src" in s for s in add_data_sources)

        # Verify the main entry point is present
        assert any("streamlit_launcher.py" in s for s in cmd)


def test_app_importable() -> None:
    """Check that app.py can be imported."""
    assert app.__name__ == "app"
