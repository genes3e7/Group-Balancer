"""
Unit tests for data_loader module.
"""

from unittest.mock import patch
import pandas as pd
from src.core import data_loader, config


@patch("builtins.input")
@patch("os.path.exists")
def test_get_file_path_sanitization(mock_exists, mock_input):
    """Test that input paths are cleaned."""
    mock_exists.return_value = True

    # Test 1
    mock_input.side_effect = ['"C:\\Users\\Test\\file.xlsx"']
    path = data_loader.get_file_path_from_user()
    assert path.endswith("file.xlsx")
    assert '"' not in path

    # Test 2
    mock_input.side_effect = ["& 'data.csv'"]
    path = data_loader.get_file_path_from_user()
    assert path.endswith("data.csv")
    assert "&" not in path


@patch("src.core.data_loader.pd.read_excel")
@patch("src.core.data_loader.pd.read_csv")
def test_load_data_valid(mock_csv, mock_excel):
    """Test loading valid data."""
    mock_df = pd.DataFrame({config.COL_NAME: ["Alice"], config.COL_SCORE: [10]})
    mock_excel.return_value = mock_df

    data = data_loader.load_data("test.xlsx")
    assert len(data) == 1
    assert data[0][config.COL_NAME] == "Alice"


def test_load_data_invalid_columns():
    """Test error when Name column is missing."""
    with patch("src.core.data_loader.pd.read_csv") as mock_read:
        mock_read.return_value = pd.DataFrame({"Wrong": ["A"], "Score": [1]})
        data = data_loader.load_data("test.csv")
        assert data is None


def test_load_data_missing_score_column():
    """Test error when Score column is missing."""
    with patch("src.core.data_loader.pd.read_csv") as mock_read:
        mock_read.return_value = pd.DataFrame({"Name": ["Alice"], "Wrong": [1]})
        data = data_loader.load_data("test.csv")
        assert data is None
