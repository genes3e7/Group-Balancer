"""Excel export utilities for optimization results.

This module provides functions to generate downloadable Excel workbooks
formatted for high readability and analysis.
"""

import io
from typing import Any

import pandas as pd

from src.core import config
from src.utils import group_helpers


def _get_excel_column_name(n: int) -> str:
    """Converts a zero-based index to an Excel column label (A, B, ..., AA, AB...)."""
    name = ""
    n_idx = n
    while n_idx >= 0:
        name = chr(n_idx % 26 + 65) + name
        n_idx = n_idx // 26 - 1
    return name


def generate_excel_bytes(
    df_results: pd.DataFrame,
    col_group: str,
    score_cols: list[str],
    col_name: str,
) -> bytes:
    """Generates an Excel file in-memory matching the 'Matrix View' format.

    Dynamically sizes column headers and data to accommodate N score dimensions.

    Args:
        df_results (pd.DataFrame): The dataframe containing participant data.
        col_group (str): Column name for Group ID.
        score_cols (list[str]): List of all score dimensions.
        col_name (str): Column name for Participant Name.

    Returns:
        bytes: The Excel file content as bytes.
    """
    output = io.BytesIO()

    cfg = group_helpers.GroupingConfig(
        col_group,
        score_cols,
        col_name,
    )
    groups = group_helpers.aggregate_groups(
        df_results,
        cfg,
    )

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sheet_name = "Balanced_Groups"

        if not groups:
            pd.DataFrame().to_excel(writer, sheet_name=sheet_name)
        else:
            rows = _build_matrix_rows(groups, score_cols)
            pd.DataFrame(rows).to_excel(writer, index=False, sheet_name=sheet_name)

    return output.getvalue()


def _build_matrix_rows(
    groups: list[dict],
    score_cols: list[str],
) -> list[dict[str, Any]]:
    """Internal helper to construct the interleaved group matrix rows."""
    rows: list[dict[str, Any]] = []

    # Dynamically compute enough header columns for 2 groups + gaps + stats
    num_cols_per_group = config.COLS_PER_GROUP_BASE + len(score_cols)
    required_count = max(
        config.MIN_HEADER_COUNT,
        (num_cols_per_group * 2) + config.STATS_COLUMN_OFFSET + (len(score_cols) * 3),
    )
    headers = [_get_excel_column_name(i) for i in range(required_count)]

    g1_cols = [headers[i] for i in range(num_cols_per_group)]
    gap_col = headers[len(g1_cols)]
    g2_cols = [headers[i] for i in range(len(g1_cols) + 1, len(g1_cols) * 2 + 1)]

    for i in range(0, len(groups), 2):
        g1 = groups[i]
        g2 = groups[i + 1] if (i + 1) < len(groups) else None

        row_header = _build_row_header(g1, g2, g1_cols, g2_cols, gap_col, score_cols)
        rows.append(row_header)

        # Interleave members
        max_m = max(len(g1["members"]), len(g2["members"]) if g2 else 0)
        for m_idx in range(max_m):
            row_m: dict[str, Any] = {}
            _fill_member_data(row_m, g1, m_idx, g1_cols, score_cols)
            row_m[gap_col] = ""
            _fill_member_data(row_m, g2, m_idx, g2_cols, score_cols)
            rows.append(row_m)

        # Gap between group pairs
        rows.append(dict.fromkeys(headers, ""))

    return rows


def _build_row_header(  # noqa: PLR0913
    g1: dict,
    g2: dict | None,
    g1_cols: list[str],
    g2_cols: list[str],
    gap_col: str,
    score_cols: list[str],
) -> dict[str, Any]:
    """Constructs the bold header row for a pair of groups."""
    row_header: dict[str, Any] = {}
    row_header[g1_cols[0]] = f"GROUP {g1['id']}"
    for idx, col in enumerate(score_cols):
        row_header[g1_cols[idx + 1]] = (
            f"AVG {col}: {g1['averages'][col]:.{config.STATS_PRECISION}f}"
        )
    row_header[gap_col] = ""

    if g2:
        row_header[g2_cols[0]] = f"GROUP {g2['id']}"
        for idx, col in enumerate(score_cols):
            row_header[g2_cols[idx + 1]] = (
                f"AVG {col}: {g2['averages'][col]:.{config.STATS_PRECISION}f}"
            )
    else:
        for c in g2_cols:
            row_header[c] = ""
    return row_header


def _fill_member_data(
    row: dict,
    group: dict | None,
    m_idx: int,
    cols: list[str],
    score_cols: list[str],
) -> None:
    """Populates a row dictionary with member name and scores."""
    if group and m_idx < len(group["members"]):
        m = group["members"][m_idx]
        row[cols[0]] = m[config.COL_NAME]
        for s_idx, s_col in enumerate(score_cols):
            row[cols[s_idx + 1]] = m[s_col]
    else:
        for c in cols:
            row[c] = ""
