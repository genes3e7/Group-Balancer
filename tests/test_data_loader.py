"""Unit tests for the data loader module."""

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
    with (
        patch("pathlib.Path.cwd", return_value=Path("/dev/null")),
        pytest.raises(ValueError, match="Access denied"),
    ):
        data_loader.validate_file_path(str(outside_file))


def test_validate_file_path_type_error(tmp_path: Path) -> None:
    """Test path validation exception when resolve fails with RuntimeError.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    test_file = tmp_path / "test.csv"
    test_file.touch()

    # Mock Path.resolve to raise RuntimeError
    with (
        patch("pathlib.Path.resolve", side_effect=RuntimeError("Bad path")),
        pytest.raises(ValueError, match="Invalid path configuration"),
    ):
        data_loader.validate_file_path(str(test_file))


def test_validate_file_path_oserror() -> None:
    """Cover OSError branch in validate_file_path."""
    with patch("pathlib.Path.resolve", side_effect=OSError("Disk error")):
        with pytest.raises(ValueError, match="Invalid path configuration"):
            data_loader.validate_file_path("test.csv")


def test_validate_file_path_exists(mock_file: str) -> None:
    """Test path validation for existing file.

    Args:
        mock_file (str): Fixture providing path to a valid file.
    """
    # Use allow_out_of_tree because mock_file is in system temp dir
    path = data_loader.validate_file_path(mock_file, allow_out_of_tree=True)
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

    # Use allow_out_of_tree
    assert (
        data_loader.validate_file_path(str(large_file), allow_out_of_tree=True)
        is not None
    )

    with large_file.open("ab") as f:
        f.write(b"1")

    with pytest.raises(ValueError, match=r"File size .* exceeds"):
        data_loader.validate_file_path(str(large_file), allow_out_of_tree=True)


def test_validate_file_path_missing(tmp_path: Path) -> None:
    """Test validation for non-existent file.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    missing = str(tmp_path / "non_existent.csv")
    with pytest.raises(FileNotFoundError):
        data_loader.validate_file_path(missing, allow_out_of_tree=True)


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
    assert data_loader.load_data(str(f), allow_out_of_tree=True) is None


def test_load_data_empty_df(tmp_path: Path) -> None:
    """Verify load_data returns empty list for empty files.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    f = tmp_path / "empty.csv"
    pd.DataFrame().to_csv(f)
    assert data_loader.load_data(str(f), allow_out_of_tree=True) is None


def test_load_data_missing_columns(tmp_path: Path) -> None:
    """Verify load_data returns None when required columns are missing.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
    """
    f = tmp_path / "bad.csv"
    pd.DataFrame({"Wrong": [1]}).to_csv(f, index=False)
    assert data_loader.load_data(str(f), allow_out_of_tree=True) is None


def test_load_data_success(mock_file: str) -> None:
    """Verify successful data loading.

    Args:
        mock_file (str): Fixture providing path to a valid file.
    """
    data = data_loader.load_data(mock_file, allow_out_of_tree=True)
    assert data is not None
    assert len(data) == 1
    assert data[0][config.COL_NAME] == "A"


def test_data_loader_process_service_unsupported() -> None:
    """Cover unsupported file format log."""
    with patch("src.core.data_loader.logger.error") as mock_log:
        res = data_loader._read_raw_file("test.txt")
        assert res is None
        assert mock_log.called


def test_data_loader_read_raw_xls(tmp_path: Path) -> None:
    """Cover old Excel format branch."""
    f = tmp_path / "test.xls"
    f.touch()
    with patch("pandas.read_excel", return_value=pd.DataFrame()):
        data_loader._read_raw_file(str(f))


def test_data_loader_process_data_limit() -> None:
    """Cover participant limit log."""
    df = pd.DataFrame({"A": range(config.MAX_PARTICIPANTS + 1)})
    with patch("src.core.data_loader.logger.error") as mock_log:
        res = data_loader._process_data_service(df, "test.csv")
        assert res is None
        assert mock_log.called


def test_data_loader_missing_required_cols() -> None:
    """Cover missing required columns branch."""
    df = pd.DataFrame({"Wrong": [1]})
    with patch("src.core.data_loader.logger.error") as mock_log:
        res = data_loader._process_data_service(df, "test.csv")
        assert res is None
        assert mock_log.called


def test_data_loader_empty_records() -> None:
    """Cover empty records branch."""
    df = pd.DataFrame({config.COL_NAME: [], "Score1": []})
    with patch("src.core.data_loader.logger.warning") as mock_log:
        res = data_loader._process_data_service(df, "test.csv")
        assert res is None
        assert mock_log.called
