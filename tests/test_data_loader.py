"""Unit tests for the data loader module."""

import os
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from src.core import config, data_loader


@pytest.fixture
def mock_file(tmp_path: Path) -> str:
    """Fixture to create a temporary CSV file.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.

    Returns:
        str: Path to the created file.
    """
    f = tmp_path / "test.csv"
    df = pd.DataFrame({"Name": ["A"], "Score1": [10]})
    df.to_csv(f, index=False)
    return str(f)


def test_validate_file_path_invalid_root(tmp_path: Path) -> None:
    """Test path validation outside project root.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    # Create a file outside the project root (in temp dir)
    outside_file = tmp_path / "outside.csv"
    outside_file.touch()

    # Mock project root to something else
    with patch("pathlib.Path.cwd", return_value=Path("/dev/null")):
        # We need to bypass the is_testing check to exercise the relative_to logic
        with patch("src.core.data_loader.sys.modules", {}):
            with patch.dict(os.environ, {"PYTEST_CURRENT_TEST": ""}):
                with pytest.raises(ValueError, match="Access denied"):
                    data_loader.validate_file_path(str(outside_file))


def test_validate_file_path_type_error(tmp_path: Path) -> None:
    """Test path validation exception when commonpath fails with non-ValueError.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    test_file = tmp_path / "test.csv"
    test_file.touch()

    # Mock Path.relative_to to raise TypeError
    with patch("pathlib.Path.relative_to", side_effect=TypeError("Bad type")):
        # Bypass is_testing
        with patch("src.core.data_loader.sys.modules", {}):
            with patch.dict(os.environ, {"PYTEST_CURRENT_TEST": ""}):
                with pytest.raises(ValueError, match="Access denied"):
                    data_loader.validate_file_path(str(test_file))


def test_validate_file_path_exists(mock_file: str) -> None:
    """Test path validation for existing file.

    Args:
        mock_file (str): Fixture providing path to a valid file.
    """
    path = data_loader.validate_file_path(mock_file)
    assert Path(path).is_absolute()


def test_validate_file_path_limit(tmp_path: Path) -> None:
    """Test file size limit validation.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    large_file = tmp_path / "boundary.csv"
    size_bytes = int(config.MAX_FILE_SIZE_MB * 1024 * 1024)
    with large_file.open("wb") as f:
        f.seek(size_bytes - 1)
        f.write(b"0")

    assert data_loader.validate_file_path(str(large_file)) is not None

    with large_file.open("ab") as f:
        f.write(b"1")

    with pytest.raises(ValueError, match=r"File size .* exceeds"):
        data_loader.validate_file_path(str(large_file))


def test_validate_file_path_missing(tmp_path: Path) -> None:
    """Test validation for non-existent file.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    missing = str(tmp_path / "non_existent.csv")
    with pytest.raises(FileNotFoundError):
        data_loader.validate_file_path(missing)


def test_load_data_none() -> None:
    """Verify load_data returns None for empty input."""
    assert data_loader.load_data("") is None


def test_load_data_invalid_format(tmp_path: Path) -> None:
    """Verify load_data returns None for unsupported extensions.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    f = tmp_path / "test.txt"
    with f.open("w") as fw:
        fw.write("test")
    assert data_loader.load_data(str(f)) is None


def test_load_data_empty_df(tmp_path: Path) -> None:
    """Verify load_data returns empty list for empty files.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    f = tmp_path / "empty.csv"
    pd.DataFrame().to_csv(f)
    assert data_loader.load_data(str(f)) is None


def test_load_data_missing_columns(tmp_path: Path) -> None:
    """Verify load_data returns None when required columns are missing.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    f = tmp_path / "bad.csv"
    pd.DataFrame({"Wrong": [1]}).to_csv(f, index=False)
    assert data_loader.load_data(str(f)) is None


def test_load_data_success(mock_file: str) -> None:
    """Verify successful data loading.

    Args:
        mock_file (str): Fixture providing path to a valid file.
    """
    data = data_loader.load_data(mock_file)
    assert data is not None
    assert len(data) == 1
    assert data[0][config.COL_NAME] == "A"
