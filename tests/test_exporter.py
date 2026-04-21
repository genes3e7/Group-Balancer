"""
Unit tests for the exporter utility.
"""

import pandas as pd
import io
from src.utils import exporter
from src.core import config

SCORE_COL = f"{config.SCORE_PREFIX}1"


def test_generate_excel_bytes():
    """Test that Excel generation returns bytes and contains the expected sheet."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A", "B"],
            SCORE_COL: [10, 20],
            config.COL_GROUP: [1, 2],
        }
    )

    output = exporter.generate_excel_bytes(
        df, config.COL_GROUP, [SCORE_COL], config.COL_NAME
    )

    assert isinstance(output, bytes)
    assert len(output) > 0

    with io.BytesIO(output) as f:
        # Read the file to ensure it's valid Excel
        xl = pd.ExcelFile(f)
        assert "Balanced_Groups" in xl.sheet_names


def test_generate_excel_matrix_content():
    """Test that the sheet contains the Matrix View structure."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A", "B"],
            SCORE_COL: [10, 20],
            config.COL_GROUP: [1, 2],
        }
    )

    output = exporter.generate_excel_bytes(
        df, config.COL_GROUP, [SCORE_COL], config.COL_NAME
    )

    with io.BytesIO(output) as f:
        # Read without headers to check raw strings
        df_out = pd.read_excel(f, sheet_name="Balanced_Groups", header=None)
        content = df_out.to_string()

        # Verify Matrix headers exist
        assert "GROUP 1" in content
        assert "GROUP 2" in content
        # Verify names exist
        assert "A" in content
        assert "B" in content


def test_generate_excel_odd_groups():
    """Test that odd number of groups renders correctly (last group alone)."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A", "B", "C"],
            SCORE_COL: [10, 20, 30],
            config.COL_GROUP: [1, 2, 3],
        }
    )

    output = exporter.generate_excel_bytes(
        df, config.COL_GROUP, [SCORE_COL], config.COL_NAME
    )

    with io.BytesIO(output) as f:
        df_out = pd.read_excel(f, sheet_name="Balanced_Groups", header=None)
        content = df_out.to_string()
        assert "GROUP 1" in content
        assert "GROUP 2" in content
        assert "GROUP 3" in content


def test_generate_excel_empty():
    """Test behavior with empty input."""
    df = pd.DataFrame(columns=[config.COL_NAME, SCORE_COL, config.COL_GROUP])

    output = exporter.generate_excel_bytes(
        df, config.COL_GROUP, [SCORE_COL], config.COL_NAME
    )

    with io.BytesIO(output) as f:
        # Should contain the sheet but it should be largely empty
        xl = pd.ExcelFile(f)
        assert "Balanced_Groups" in xl.sheet_names
        # Re-use xl object to parse, avoiding EOF error
        df_out = xl.parse("Balanced_Groups")
        assert df_out.empty
