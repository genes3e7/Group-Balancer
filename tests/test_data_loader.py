"""Unit tests for data_loader module.

Hardened with security and error handling checks.
"""

import os
from unittest.mock import patch

import pandas as pd
import pytest

from src.core import config, data_loader


@pytest.fixture
def mock_file(tmp_path):
    """Creates a small mock CSV file."""
    f = tmp_path / "test.csv"
    df = pd.DataFrame({config.COL_NAME: ["Alice"], f"{config.SCORE_PREFIX}1": [10]})
    df.to_csv(f, index=False)
    return str(f)


def test_validate_file_path_exists(mock_file):
    """Test path validation for existing file."""
    path = data_loader.validate_file_path(mock_file)
    assert os.path.isabs(path)


def test_validate_file_path_boundary(tmp_path):
    """Test the exact boundary of MAX_FILE_SIZE_MB."""
    large_file = tmp_path / "boundary.csv"
    # Create file exactly at the limit
    size_bytes = int(config.MAX_FILE_SIZE_MB * 1024 * 1024)
    with open(large_file, "wb") as f:
        f.seek(size_bytes - 1)
        f.write(b"0")

    assert data_loader.validate_file_path(str(large_file)) is not None

    # Just over the limit
    with open(large_file, "ab") as f:
        f.write(b"1")

    with pytest.raises(ValueError, match="exceeds"):
        data_loader.validate_file_path(str(large_file))


def test_validate_file_path_missing():
    """Test path validation for missing file."""
    with pytest.raises(FileNotFoundError):
        data_loader.validate_file_path("non_existent.csv")


def test_validate_file_path_not_a_file(tmp_path):
    """Test path validation for a directory instead of a file."""
    with pytest.raises(ValueError, match="Path is not a file"):
        data_loader.validate_file_path(str(tmp_path))


def test_validate_file_path_size_limit(mock_file):
    """Test file size limit enforcement."""
    with patch("os.path.getsize") as mock_size:
        mock_size.return_value = (config.MAX_FILE_SIZE_MB + 1) * 1024 * 1024
        with pytest.raises(ValueError, match="exceeds"):
            data_loader.validate_file_path(mock_file)


def test_load_data_valid(mock_file):
    """Test loading valid data from real file."""
    data = data_loader.load_data(mock_file)
    assert len(data) == 1
    assert data[0][config.COL_NAME] == "Alice"


def test_load_data_valid_excel(tmp_path):
    """Test loading valid data from excel file."""
    f = tmp_path / "test.xlsx"
    df = pd.DataFrame({config.COL_NAME: ["Bob"], f"{config.SCORE_PREFIX}1": [20]})
    df.to_excel(f, index=False)
    data = data_loader.load_data(str(f))
    assert len(data) == 1
    assert data[0][config.COL_NAME] == "Bob"


def test_load_data_unsupported(tmp_path):
    """Test loading unsupported extension."""
    f = tmp_path / "test.txt"
    with open(f, "w") as fw:
        fw.write("test")
    assert data_loader.load_data(str(f)) is None


def test_load_data_participant_limit(mock_file):
    """Test participant count limit."""
    with patch("pandas.read_csv") as mock_read:
        # Create a df with too many participants
        mock_read.return_value = pd.DataFrame(
            {
                config.COL_NAME: [f"P{i}" for i in range(config.MAX_PARTICIPANTS + 1)],
                f"{config.SCORE_PREFIX}1": [10] * (config.MAX_PARTICIPANTS + 1),
            },
        )
        data = data_loader.load_data(mock_file)
        assert data is None


def test_load_data_empty_records(tmp_path):
    """Test empty records handling."""
    f = tmp_path / "empty.csv"
    pd.DataFrame(columns=[config.COL_NAME, f"{config.SCORE_PREFIX}1"]).to_csv(
        f,
        index=False,
    )
    data = data_loader.load_data(str(f))
    assert data is None


def test_load_data_missing_constraint_cols(tmp_path):
    """Test that missing constraint cols are gracefully filled."""
    f = tmp_path / "noconstraints.csv"
    pd.DataFrame({config.COL_NAME: ["A"], f"{config.SCORE_PREFIX}1": [10]}).to_csv(
        f,
        index=False,
    )
    data = data_loader.load_data(str(f))
    assert data[0][config.COL_GROUPER] == ""
    assert data[0][config.COL_SEPARATOR] == ""


@patch("builtins.input")
@patch("src.core.data_loader.validate_file_path")
def test_get_file_path_from_user_success(mock_val, mock_input):
    """Test successful CLI file path input with artifacts."""
    # Test skipping empty inputs and handling shell prefixes
    mock_input.side_effect = ["", "& test.csv", "& 'test.csv'", '""test.csv""']
    mock_val.side_effect = ["C:/abs/test.csv", "C:/abs/test.csv", "C:/abs/test.csv"]

    path1 = data_loader.get_file_path_from_user()
    path2 = data_loader.get_file_path_from_user()
    path3 = data_loader.get_file_path_from_user()
    assert path1 == "C:/abs/test.csv"
    assert path2 == "C:/abs/test.csv"
    assert path3 == "C:/abs/test.csv"


@patch("builtins.input")
def test_get_file_path_from_user_value_error(mock_input):
    """Test ValueError loop in CLI file path input."""
    # Should catch error, print, and loop again
    mock_input.side_effect = ["bad.csv", KeyboardInterrupt]
    with pytest.raises(SystemExit):
        data_loader.get_file_path_from_user()


@patch("builtins.input")
def test_get_file_path_from_user_generic_error(mock_input):
    """Test general Exception loop in CLI file path input."""
    # Should catch error, print, and loop again
    mock_input.side_effect = [Exception("Test Exception"), KeyboardInterrupt]
    with pytest.raises(SystemExit):
        data_loader.get_file_path_from_user()


def test_load_data_none():
    """Test load_data with None path."""
    assert data_loader.load_data(None) is None


def test_load_data_permission_error(mock_file):
    """Test permission error handling."""
    with patch("pandas.read_csv", side_effect=PermissionError):
        assert data_loader.load_data(mock_file) is None


def test_load_data_generic_exception(mock_file):
    """Test generic exception handling."""
    with patch("pandas.read_csv", side_effect=Exception):
        assert data_loader.load_data(mock_file) is None
