"""
Unit tests for the exporter utility.
"""

import pandas as pd
import io
from src.utils import exporter
from src.core import config


def test_generate_excel_bytes():
    """Test that Excel generation returns bytes."""

    # Mock Data
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A", "B"],
            config.COL_SCORE: [10, 20],
            config.COL_GROUP: [1, 2],
        }
    )

    # Call function
    output = exporter.generate_excel_bytes(
        df, config.COL_GROUP, config.COL_SCORE, config.COL_NAME
    )

    # Assert output is bytes
    assert isinstance(output, bytes)
    assert len(output) > 0

    # Verify we can read it back as Excel
    with io.BytesIO(output) as f:
        df_out = pd.read_excel(f, sheet_name="Assignments")
        assert len(df_out) == 2
        assert config.COL_GROUP in df_out.columns
