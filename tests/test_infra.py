"""Infrastructure tests for root-level scripts."""

from unittest.mock import patch

import app
import build


def test_build_executable_cleanup():
    """Test that build_executable cleans up old directories."""
    with (
        patch("os.path.exists", return_value=True),
        patch("shutil.rmtree") as mock_rm,
        patch("subprocess.run"),
    ):
        build.build_executable()

        # Verify cleanup of build and dist
        assert mock_rm.call_count >= 2


def test_build_executable_success():
    """Test successful execution of PyInstaller command."""
    with (
        patch("os.path.exists", return_value=False),
        patch("subprocess.run") as mock_run,
    ):
        build.build_executable()

        # Verify pyinstaller was called
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "pyinstaller" in args
        assert "app.py" in args


def test_app_importable():
    """Check that app.py can be imported."""
    assert app.__name__ == "app"
