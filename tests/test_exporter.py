"""Unit tests for the Excel exporter module."""

import io

import pandas as pd
import pytest

from src.core import config
from src.utils import exporter


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Fixture providing a typical optimized result set."""
    return pd.DataFrame(
        [
            {config.COL_NAME: "A", config.COL_GROUP: 1, "Score1": 10},
            {config.COL_NAME: "B", config.COL_GROUP: 1, "Score1": 20},
            {config.COL_NAME: "C", config.COL_GROUP: 2, "Score1": 30},
            {config.COL_NAME: "D", config.COL_GROUP: 2, "Score1": 40},
        ],
    )


def test_generate_excel_bytes_valid(sample_df: pd.DataFrame) -> None:
    """Verify standard Excel generation with valid data."""
    excel_bytes = exporter.generate_excel_bytes(
        sample_df, config.COL_GROUP, ["Score1"], config.COL_NAME
    )

    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 0

    # Verify content via pandas
    with io.BytesIO(excel_bytes) as f:
        sheet = pd.read_excel(f, sheet_name="Balanced_Groups", header=None)

    # Convert to set of all cell strings to check for markers
    values = {str(val) for val in sheet.to_numpy().flatten()}
    assert {"GROUP 1", "GROUP 2", "A", "B", "C", "D"}.issubset(values)


def test_generate_excel_bytes_empty() -> None:
    """Verify behavior with empty input."""
    df = pd.DataFrame()
    excel_bytes = exporter.generate_excel_bytes(
        df, config.COL_GROUP, ["Score1"], config.COL_NAME
    )
    assert isinstance(excel_bytes, bytes)

    # Empty result should still produce a valid (but essentially empty) sheet
    with io.BytesIO(excel_bytes) as f:
        sheet = pd.read_excel(f, sheet_name="Balanced_Groups")
    assert sheet.empty


def test_matrix_layout_alignment() -> None:
    """Verify the interleaved 2-column matrix layout logic."""
    df = pd.DataFrame(
        [
            {config.COL_NAME: "A", config.COL_GROUP: 1, "Score1": 10},
            {config.COL_NAME: "C", config.COL_GROUP: 2, "Score1": 30},
        ],
    )
    excel_bytes = exporter.generate_excel_bytes(
        df, config.COL_GROUP, ["Score1"], config.COL_NAME
    )

    with io.BytesIO(excel_bytes) as f:
        # Load with header=None so we can see the literal content of all cells
        sheet = pd.read_excel(f, sheet_name="Balanced_Groups", header=None)

    # G1 should be on the left, G2 on the right
    # Because to_excel writes headers by default, row 0 is "A", "B", "C"...
    # "GROUP 1" and "GROUP 2" should be in the same row (row 1)
    # Check all rows just in case of header shifts
    all_rows = [row.tolist() for row in sheet.to_numpy()]
    header_row_found = False
    for row in all_rows:
        row_strs = [str(s) for s in row]
        if any("GROUP 1" in s for s in row_strs) and any(
            "GROUP 2" in s for s in row_strs
        ):
            header_row_found = True
            break

    assert header_row_found


def test_generate_excel_bytes_odd_groups() -> None:
    """Verify that odd number of groups are handled (last group is single).."""
    df = pd.DataFrame(
        [
            {config.COL_NAME: "A", config.COL_GROUP: 1, "Score1": 10},
        ],
    )
    excel_bytes = exporter.generate_excel_bytes(
        df, config.COL_GROUP, ["Score1"], config.COL_NAME
    )

    with io.BytesIO(excel_bytes) as f:
        sheet = pd.read_excel(f, sheet_name="Balanced_Groups", header=None)
    values = {str(val) for val in sheet.to_numpy().flatten()}
    assert "GROUP 1" in values
    assert "GROUP 2" not in values
