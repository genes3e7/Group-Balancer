"""Unit tests for the exporter utility."""

import io

import pandas as pd

from src.core import config
from src.utils import exporter

SCORE_COL = f"{config.SCORE_PREFIX}1"


def test_generate_excel_bytes():
    """Test that excel generation returns non-empty bytes."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["Alice", "Bob"],
            config.COL_GROUP: [1, 2],
            SCORE_COL: [10, 20],
        },
    )
    score_cols = [SCORE_COL]

    excel_bytes = exporter.generate_excel_bytes(
        df,
        config.COL_GROUP,
        score_cols,
        config.COL_NAME,
    )

    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 0

    # Optional: Verify it's a valid Excel file
    with io.BytesIO(excel_bytes) as f:
        xl = pd.ExcelFile(f)
        assert "Balanced_Groups" in xl.sheet_names
        df_out = pd.read_excel(f, sheet_name="Balanced_Groups")
        # Verify it has some data.
        assert not df_out.empty


def test_generate_excel_bytes_empty():
    """Test behavior with empty dataframe."""
    df = pd.DataFrame()
    excel_bytes = exporter.generate_excel_bytes(
        df,
        config.COL_GROUP,
        [],
        config.COL_NAME,
    )

    # Should still return valid empty template bytes
    assert isinstance(excel_bytes, bytes)
    with io.BytesIO(excel_bytes) as f:
        xl = pd.ExcelFile(f)
        assert "Balanced_Groups" in xl.sheet_names
        df_out = xl.parse("Balanced_Groups")
        assert df_out.empty


def test_generate_excel_bytes_multiple_members():
    """Test aggregation with more members per group."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A", "B", "C", "D"],
            config.COL_GROUP: [1, 1, 2, 2],
            SCORE_COL: [10, 20, 30, 40],
        },
    )
    score_cols = [SCORE_COL]
    excel_bytes = exporter.generate_excel_bytes(
        df,
        config.COL_GROUP,
        score_cols,
        config.COL_NAME,
    )
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 0
    with io.BytesIO(excel_bytes) as f:
        sheet = pd.read_excel(f, sheet_name="Balanced_Groups", header=None)
    values = set(sheet.stack().astype(str))
    assert {"GROUP 1", "GROUP 2", "A", "B", "C", "D"}.issubset(values)


def test_generate_excel_bytes_odd_groups():
    """Test with odd number of groups to cover g2 is None branches."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A", "B"],
            config.COL_GROUP: [1, 1],
            SCORE_COL: [10, 20],
        },
    )
    score_cols = [SCORE_COL]
    excel_bytes = exporter.generate_excel_bytes(
        df,
        config.COL_GROUP,
        score_cols,
        config.COL_NAME,
    )
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 0
    with io.BytesIO(excel_bytes) as f:
        sheet = pd.read_excel(f, sheet_name="Balanced_Groups", header=None)
    values = set(sheet.stack().astype(str))
    assert "GROUP 1" in values
    assert "GROUP 2" not in values


def test_exporter_no_groups_edge():
    """Cover 'if not groups' branch in exporter."""
    df = pd.DataFrame()
    res = exporter.generate_excel_bytes(df, "Group", ["S1"], "Name")
    assert isinstance(res, bytes)
    assert len(res) > 0
    with io.BytesIO(res) as f:
        xl = pd.ExcelFile(f)
        assert "Balanced_Groups" in xl.sheet_names
        assert xl.parse("Balanced_Groups").empty
