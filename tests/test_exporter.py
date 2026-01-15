"""
Unit tests for the exporter utility.
"""

import pandas as pd
import io
from src.utils import exporter
from src.core import config


def test_generate_excel_bytes():
    """Test that Excel generation returns bytes and includes Assignments sheet."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A", "B"],
            config.COL_SCORE: [10, 20],
            config.COL_GROUP: [1, 2],
        }
    )

    output = exporter.generate_excel_bytes(
        df, config.COL_GROUP, config.COL_SCORE, config.COL_NAME
    )

    assert isinstance(output, bytes)
    assert len(output) > 0

    with io.BytesIO(output) as f:
        df_out = pd.read_excel(f, sheet_name="Assignments")
        assert len(df_out) == 2
        assert config.COL_GROUP in df_out.columns


def test_generate_excel_matrix_view():
    """Test that the Matrix_View sheet is created and contains data."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A", "B"],
            config.COL_SCORE: [10, 20],
            config.COL_GROUP: [1, 2],
        }
    )

    output = exporter.generate_excel_bytes(
        df, config.COL_GROUP, config.COL_SCORE, config.COL_NAME
    )

    with io.BytesIO(output) as f:
        # Read Matrix_View without headers to check raw content
        df_matrix = pd.read_excel(f, sheet_name="Matrix_View", header=None)
        # Should contain strings like "GROUP 1" and "GROUP 2"
        content = df_matrix.to_string()
        assert "GROUP 1" in content
        assert "GROUP 2" in content


def test_generate_excel_odd_groups():
    """Test that odd number of groups renders correctly (last group alone)."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A", "B", "C"],
            config.COL_SCORE: [10, 20, 30],
            config.COL_GROUP: [1, 2, 3],
        }
    )

    output = exporter.generate_excel_bytes(
        df, config.COL_GROUP, config.COL_SCORE, config.COL_NAME
    )

    with io.BytesIO(output) as f:
        df_matrix = pd.read_excel(f, sheet_name="Matrix_View", header=None)
        content = df_matrix.to_string()
        assert "GROUP 1" in content
        assert "GROUP 2" in content
        assert "GROUP 3" in content


def test_generate_excel_empty():
    """Test behavior with empty input."""
    df = pd.DataFrame(columns=[config.COL_NAME, config.COL_SCORE, config.COL_GROUP])

    output = exporter.generate_excel_bytes(
        df, config.COL_GROUP, config.COL_SCORE, config.COL_NAME
    )

    with io.BytesIO(output) as f:
        # Assignments sheet should exist but be empty
        df_out = pd.read_excel(f, sheet_name="Assignments")
        assert df_out.empty
