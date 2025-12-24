"""
Unit tests for data_loader module.
"""

from unittest.mock import patch
import pandas as pd
from modules import data_loader, config


@patch("builtins.input")
@patch("os.path.exists")
def test_get_file_path_sanitization(mock_exists, mock_input):
    """Test that input paths are cleaned of quotes and PowerShell artifacts."""
    mock_exists.return_value = True

    # Test case 1: Windows path with quotes
    mock_input.side_effect = ['"C:\\Users\\Test\\file.xlsx"']
    path = data_loader.get_file_path_from_user()
    assert path.endswith("file.xlsx")
    assert '"' not in path

    # Test case 2: PowerShell drag-and-drop (& 'path')
    # We reset the mock to handle the second call
    mock_input.side_effect = ["& 'data.csv'"]
    path = data_loader.get_file_path_from_user()

    # The actual code returns an absolute path.
    # We check if it ends with the expected filename.
    assert path.endswith("data.csv")
    assert "&" not in path
    assert "'" not in path


@patch("pandas.read_excel")
@patch("pandas.read_csv")
def test_load_data_valid(mock_csv, mock_excel):
    """Test loading valid data."""
    # Setup mock DF
    mock_df = pd.DataFrame(
        {config.COL_NAME: ["Alice", "Bob"], config.COL_SCORE: [10, 20]}
    )
    mock_excel.return_value = mock_df

    data = data_loader.load_data("test.xlsx")
    assert len(data) == 2
    assert data[0][config.COL_NAME] == "Alice"
    assert data[0][config.COL_SCORE] == 10


def test_load_data_invalid_columns():
    """Test error when columns are missing."""
    with patch("pandas.read_csv") as mock_read:
        mock_read.return_value = pd.DataFrame({"WrongName": ["A"], "Score": [1]})
        data = data_loader.load_data("test.csv")
        assert data is None


def test_load_data_empty():
    """Test error when file is empty."""
    with patch("pandas.read_csv") as mock_read:
        mock_read.return_value = pd.DataFrame(
            columns=[config.COL_NAME, config.COL_SCORE]
        )
        data = data_loader.load_data("test.csv")
        assert data is None
