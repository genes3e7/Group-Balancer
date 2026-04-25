"""Unit tests for data_loader module.

Hardened with security and error handling checks.
"""

import os
from pathlib import Path
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


@pytest.fixture(autouse=True)
def mock_project_root(tmp_path):
    """Mocks getcwd to use tmp_path as project root."""
    with patch("os.getcwd", return_value=str(tmp_path)):
        yield


def test_validate_file_path_security_violation():
    """Test that paths outside project root are rejected."""
    outside_path = (
        "/etc/passwd" if os.name != "nt" else "C:/Windows/system32/config/SAM"
    )
    with pytest.raises(ValueError, match="Access denied"):
        data_loader.validate_file_path(outside_path)


def test_validate_file_path_type_error():
    """Test path validation exception when commonpath fails with non-ValueError."""
    with patch("os.path.commonpath", side_effect=TypeError("Bad type")):
        with pytest.raises(ValueError, match="Invalid path configuration"):
            data_loader.validate_file_path("test.csv")


def test_validate_file_path_exists(mock_file):
    """Test path validation for existing file."""
    path = data_loader.validate_file_path(mock_file)
    assert os.path.isabs(path)


def test_validate_file_path_boundary(tmp_path):
    """Test the exact boundary of MAX_FILE_SIZE_MB."""
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


def test_validate_file_path_missing(tmp_path):
    """Test path validation for missing file."""
    missing = os.path.join(str(tmp_path), "non_existent.csv")
    with pytest.raises(FileNotFoundError):
        data_loader.validate_file_path(missing)


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


def test_load_data_valid_path_obj(mock_file):
    """Test loading valid data from pathlib.Path object."""
    data = data_loader.load_data(Path(mock_file))
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
        mock_read.return_value = pd.DataFrame(
            {
                config.COL_NAME: [f"P{i}" for i in range(config.MAX_PARTICIPANTS + 1)],
                f"{config.SCORE_PREFIX}1": [10] * (config.MAX_PARTICIPANTS + 1),
            },
        )
        data = data_loader.load_data(mock_file)
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
    mock_input.side_effect = [
        "",
        "& test.csv",
        "&test.csv",
        "& 'test.csv'",
        '""test.csv""',
    ]
    mock_val.return_value = "C:/abs/test.csv"

    # All these should be sanitized to "test.csv" before calling validator
    for _ in range(4):
        path = data_loader.get_file_path_from_user()
        assert path == "C:/abs/test.csv"
        mock_val.assert_called_with("test.csv")


@patch("builtins.input")
@patch("src.core.data_loader.validate_file_path")
def test_get_file_path_from_user_value_error(mock_val, mock_input):
    """Test ValueError loop in CLI file path input."""
    # Raise ValueError first time, then KeyboardInterrupt to break loop
    mock_input.side_effect = ["bad.csv", "exit"]
    mock_val.side_effect = [ValueError("Bad path"), "C:/good.csv"]
    path = data_loader.get_file_path_from_user()
    assert path == "C:/good.csv"


@patch("builtins.input")
@patch("src.core.data_loader.validate_file_path")
def test_get_file_path_from_user_fnf_error(mock_val, mock_input):
    """Test FileNotFoundError loop in CLI file path input."""
    mock_input.side_effect = ["bad.csv", "exit"]
    mock_val.side_effect = [FileNotFoundError("Not found"), "C:/good.csv"]
    path = data_loader.get_file_path_from_user()
    assert path == "C:/good.csv"


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


def test_load_data_coerce(tmp_path):
    """Coerce non-numeric score values to 0.0."""
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
    assert data[0][f"{config.SCORE_PREFIX}1"] == 0.0
    assert data[0][config.COL_GROUPER] == ""
    assert data[0][config.COL_SEPARATOR] == ""


def test_load_data_empty_records_empty_dataframe(tmp_path):
    """Return None when the file contains only a header row."""
    f = tmp_path / "test.csv"
    pd.DataFrame(columns=[config.COL_NAME, f"{config.SCORE_PREFIX}1"]).to_csv(
        f,
        index=False,
    )
    with patch("src.core.data_loader.validate_file_path", return_value=str(f)):
        data = data_loader.load_data(str(f))
    assert data is None
