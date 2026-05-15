"""Unit tests for the data_loader module.

Hardened with security and error handling checks.
"""

import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.core import config, data_loader


@pytest.fixture
def mock_file(tmp_path: Path) -> str:
    """Creates a small mock CSV file for testing.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.

    Returns:
        str: Absolute path to the generated CSV file.
    """
    f = tmp_path / "test.csv"
    df = pd.DataFrame({config.COL_NAME: ["Alice"], f"{config.SCORE_PREFIX}1": [10]})
    df.to_csv(f, index=False)
    return str(f)


@pytest.fixture(autouse=True)
def mock_project_root(tmp_path: Path) -> Generator[None, None, None]:
    """Mocks getcwd to use tmp_path as project root for isolation.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.

    Yields:
        None
    """
    with patch("os.getcwd", return_value=str(tmp_path)):
        yield


def test_validate_file_path_security_violation() -> None:
    """Test that paths outside project root are rejected."""
    outside_path = (
        "/etc/passwd" if os.name != "nt" else "C:/Windows/system32/config/SAM"
    )
    with pytest.raises(ValueError, match="Access denied"):
        data_loader.validate_file_path(outside_path)


def test_validate_file_path_type_error() -> None:
    """Test path validation exception when commonpath fails with non-ValueError."""
    with patch("os.path.commonpath", side_effect=TypeError("Bad type")):
        with pytest.raises(ValueError, match="Invalid path configuration"):
            data_loader.validate_file_path("test.csv")


def test_validate_file_path_exists(mock_file: str) -> None:
    """Test path validation for existing file.

    Args:
        mock_file (str): Path to the mock CSV file.
    """
    path = data_loader.validate_file_path(mock_file)
    assert os.path.isabs(path)


def test_validate_file_path_boundary(tmp_path: Path) -> None:
    """Test the exact boundary of MAX_FILE_SIZE_MB.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    large_file = tmp_path / "boundary.csv"
    size_bytes = int(config.MAX_FILE_SIZE_MB * 1024 * 1024)
    with open(large_file, "wb") as f:
        f.seek(size_bytes - 1)
        f.write(b"0")

    assert data_loader.validate_file_path(str(large_file)) is not None

    with open(large_file, "ab") as f:
        f.write(b"1")

    with pytest.raises(ValueError, match="exceeds"):
        data_loader.validate_file_path(str(large_file))


def test_validate_file_path_missing(tmp_path: Path) -> None:
    """Test path validation for missing file.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    missing = os.path.join(str(tmp_path), "non_existent.csv")
    with pytest.raises(FileNotFoundError):
        data_loader.validate_file_path(missing)


def test_validate_file_path_not_a_file(tmp_path: Path) -> None:
    """Test path validation for a directory instead of a file.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    with pytest.raises(ValueError, match="Path is not a file"):
        data_loader.validate_file_path(str(tmp_path))


def test_validate_file_path_size_limit(mock_file: str) -> None:
    """Test file size limit enforcement.

    Args:
        mock_file (str): Path to the mock CSV file.
    """
    with patch("os.path.getsize") as mock_size:
        mock_size.return_value = (config.MAX_FILE_SIZE_MB + 1) * 1024 * 1024
        with pytest.raises(ValueError, match="exceeds"):
            data_loader.validate_file_path(mock_file)


def test_load_data_valid(mock_file: str) -> None:
    """Test loading valid data from real file.

    Args:
        mock_file (str): Path to the mock CSV file.
    """
    data = data_loader.load_data(mock_file)
    assert data is not None
    assert len(data) == 1
    assert data[0][config.COL_NAME] == "Alice"


def test_load_data_valid_path_obj(mock_file: str) -> None:
    """Test loading valid data from pathlib.Path object.

    Args:
        mock_file (str): Path to the mock CSV file.
    """
    data = data_loader.load_data(Path(mock_file))
    assert data is not None
    assert len(data) == 1
    assert data[0][config.COL_NAME] == "Alice"


def test_load_data_valid_excel(tmp_path: Path) -> None:
    """Test loading valid data from excel file.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    f = tmp_path / "test.xlsx"
    df = pd.DataFrame({config.COL_NAME: ["Bob"], f"{config.SCORE_PREFIX}1": [20]})
    df.to_excel(f, index=False)
    data = data_loader.load_data(str(f))
    assert data is not None
    assert len(data) == 1
    assert data[0][config.COL_NAME] == "Bob"


def test_load_data_unsupported(tmp_path: Path) -> None:
    """Test loading unsupported extension.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    f = tmp_path / "test.txt"
    with open(f, "w") as fw:
        fw.write("test")
    assert data_loader.load_data(str(f)) is None


def test_load_data_participant_limit(mock_file: str) -> None:
    """Test participant count limit.

    Args:
        mock_file (str): Path to the mock CSV file.
    """
    with patch("pandas.read_csv") as mock_read:
        mock_read.return_value = pd.DataFrame(
            {
                config.COL_NAME: [f"P{i}" for i in range(config.MAX_PARTICIPANTS + 1)],
                f"{config.SCORE_PREFIX}1": [10] * (config.MAX_PARTICIPANTS + 1),
            },
        )
        data = data_loader.load_data(mock_file)
        assert data is None


def test_load_data_missing_constraint_cols(tmp_path: Path) -> None:
    """Test that missing constraint cols are gracefully filled.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    f = tmp_path / "noconstraints.csv"
    pd.DataFrame({config.COL_NAME: ["A"], f"{config.SCORE_PREFIX}1": [10]}).to_csv(
        f,
        index=False,
    )
    data = data_loader.load_data(str(f))
    assert data is not None
    assert data[0][config.COL_GROUPER] == ""
    assert data[0][config.COL_SEPARATOR] == ""


@patch("builtins.input")
@patch("src.core.data_loader.validate_file_path")
def test_get_file_path_from_user_success(
    mock_val: MagicMock, mock_input: MagicMock
) -> None:
    """Test successful CLI file path input with artifacts.

    Args:
        mock_val (MagicMock): Mock for validate_file_path.
        mock_input (MagicMock): Mock for builtins.input.
    """
    mock_input.side_effect = [
        "",
        "& test.csv",
        "&test.csv",
        "& 'test.csv'",
        '""test.csv""',
        "test.csv",
    ]
    mock_val.return_value = "C:/abs/test.csv"

    for _ in range(5):
        path = data_loader.get_file_path_from_user()
        assert path == "C:/abs/test.csv"
        mock_val.assert_called_with("test.csv")


@patch("builtins.input")
@patch("src.core.data_loader.validate_file_path")
def test_get_file_path_from_user_value_error(
    mock_val: MagicMock, mock_input: MagicMock
) -> None:
    """Test ValueError loop in CLI file path input.

    Args:
        mock_val (MagicMock): Mock for validate_file_path.
        mock_input (MagicMock): Mock for builtins.input.
    """
    mock_input.side_effect = ["bad.csv", "exit"]
    mock_val.side_effect = [ValueError("Bad path"), "C:/good.csv"]
    path = data_loader.get_file_path_from_user()
    assert path == "C:/good.csv"


@patch("builtins.input")
@patch("src.core.data_loader.validate_file_path")
def test_get_file_path_from_user_fnf_error(
    mock_val: MagicMock, mock_input: MagicMock
) -> None:
    """Test FileNotFoundError loop in CLI file path input.

    Args:
        mock_val (MagicMock): Mock for validate_file_path.
        mock_input (MagicMock): Mock for builtins.input.
    """
    mock_input.side_effect = ["bad.csv", "exit"]
    mock_val.side_effect = [FileNotFoundError("Not found"), "C:/good.csv"]
    path = data_loader.get_file_path_from_user()
    assert path == "C:/good.csv"


@patch("builtins.input")
def test_get_file_path_from_user_generic_error(mock_input: MagicMock) -> None:
    """Test general Exception loop in CLI file path input.

    Args:
        mock_input (MagicMock): Mock for builtins.input.
    """
    mock_input.side_effect = [Exception("Test Exception"), KeyboardInterrupt]
    with pytest.raises(SystemExit):
        data_loader.get_file_path_from_user()


def test_load_data_none() -> None:
    """Test load_data with None path."""
    assert data_loader.load_data(None) is None


def test_load_data_permission_error(mock_file: str) -> None:
    """Test permission error handling.

    Args:
        mock_file (str): Path to the mock CSV file.
    """
    with patch("pandas.read_csv", side_effect=PermissionError):
        assert data_loader.load_data(mock_file) is None


def test_load_data_generic_exception(mock_file: str) -> None:
    """Test generic exception handling.

    Args:
        mock_file (str): Path to the mock CSV file.
    """
    with patch("pandas.read_csv", side_effect=Exception):
        assert data_loader.load_data(mock_file) is None


def test_load_data_coerce(tmp_path: Path) -> None:
    """Coerce non-numeric score values to 0.0.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    f = tmp_path / "test.csv"
    pd.DataFrame(
        {
            config.COL_NAME: ["Alice"],
            f"{config.SCORE_PREFIX}1": ["not a number"],
            config.COL_GROUPER: [None],
            config.COL_SEPARATOR: [None],
        }
    ).to_csv(f, index=False)
    with patch("src.core.data_loader.validate_file_path", return_value=str(f)):
        data = data_loader.load_data(str(f))
    assert data is not None
    assert data[0][f"{config.SCORE_PREFIX}1"] == 0.0
    assert data[0][config.COL_GROUPER] == ""
    assert data[0][config.COL_SEPARATOR] == ""


def test_load_data_empty_records_empty_dataframe(tmp_path: Path) -> None:
    """Return None when the file contains only a header row.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    f = tmp_path / "test.csv"
    pd.DataFrame(columns=[config.COL_NAME, f"{config.SCORE_PREFIX}1"]).to_csv(
        f,
        index=False,
    )
    with patch("src.core.data_loader.validate_file_path", return_value=str(f)):
        data = data_loader.load_data(str(f))
    assert data is None
