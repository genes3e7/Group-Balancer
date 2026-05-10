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
        patch.object(build.shutil, "which", return_value="uv"),
        patch.object(build.subprocess, "run") as mock_run,
    ):
        # Only call: pyinstaller
        mock_run.return_value = MagicMock(returncode=0)

        build.build_executable()

        # Verify pyinstaller was invoked with the optimized build contract
        assert mock_run.call_count == 1
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "pyinstaller"

        for flag in ("--clean", "--noupx", "--noconfirm", "--onedir", "--windowed"):
            assert flag in cmd, f"Missing required flag: {flag}"

        # Critical bundled artifacts must be present in --add-data
        joined_cmd = " ".join(cmd)
        assert "app.py" in joined_cmd
        assert "src" in joined_cmd
        assert "streamlit_launcher.py" in joined_cmd


def test_app_importable():
    """Check that app.py can be imported."""
    assert app.__name__ == "app"
