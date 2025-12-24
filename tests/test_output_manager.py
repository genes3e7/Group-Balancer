"""
Unit tests for output_manager.
"""

from unittest.mock import patch, MagicMock
from modules import output_manager, config


@patch("modules.output_manager.pd.ExcelWriter")
def test_save_results(mock_writer):
    """Test that save_results calls ExcelWriter correctly."""
    # Mock context manager
    mock_context = MagicMock()
    mock_writer.return_value.__enter__.return_value = mock_context

    test_results = {
        "Sheet1": [
            {
                "id": 1,
                "members": [{"Name": "A", "Score": 10}],
                "avg": 10.0,
                "current_sum": 10,
            },
            {
                "id": 2,
                "members": [{"Name": "B", "Score": 20}],
                "avg": 20.0,
                "current_sum": 20,
            },
        ]
    }

    output_manager.save_results(test_results)

    # Verify writer was called with correct arguments
    mock_writer.assert_called_once_with(config.OUTPUT_FILENAME, engine="openpyxl")
