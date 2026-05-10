"""Infrastructure tests for root-level scripts."""

from unittest.mock import MagicMock, patch

import app
import build


def test_build_executable_cleanup():
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


def test_build_executable_success():
    """Test successful execution of PyInstaller command."""
    with (
        patch("os.path.exists", return_value=False),
        patch("subprocess.run") as mock_run,
    ):
        # First call: uv pip list (Tree Shaker)
        # Second call: pyinstaller
        mock_run.side_effect = [
            MagicMock(stdout="Package Version\n---\npkg1 1.0\n", returncode=0),
            MagicMock(returncode=0),
        ]

        build.build_executable()

        # Verify pyinstaller was called
        assert mock_run.call_count == 2
        last_call_args = mock_run.call_args[0][0]
        assert "pyinstaller" in last_call_args
        assert "--exclude-module" in last_call_args


def test_app_importable():
    """Check that app.py can be imported."""
    assert app.__name__ == "app"
