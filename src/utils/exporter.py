"""Excel export utility.

This module formats the results into a side-by-side 'Matrix View' structure
and includes summary statistics in the generated Excel file for multiple dimensions.
"""

import io
from typing import Any

import pandas as pd

from src.utils import group_helpers


def _get_excel_column_name(n: int) -> str:
    """Converts a 0-indexed column number to an Excel column name.

    Args:
        n (int): The 0-indexed column position.

    Returns:
        str: The corresponding Excel column label (e.g., A, B, ..., Z, AA, ...).
    """
    res = ""
    while n >= 0:
        res = chr(n % 26 + 65) + res
        n = n // 26 - 1
    return res


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

    groups = group_helpers.aggregate_groups(
        df_results,
        col_group,
        score_cols,
        col_name,
    )

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sheet_name = "Balanced_Groups"

        if not groups:
            pd.DataFrame().to_excel(writer, sheet_name=sheet_name)
        else:
            rows: list[dict[str, Any]] = []

            # Dynamically compute enough header columns for 2 groups + gaps + stats
            num_cols_per_group = 1 + len(score_cols)
            required_count = max(
                50,
                (num_cols_per_group * 2) + 5 + (len(score_cols) * 3),
            )
            headers = [_get_excel_column_name(i) for i in range(required_count)]

            g1_cols = [headers[i] for i in range(num_cols_per_group)]
            gap_col = headers[len(g1_cols)]
            g2_cols = [
                headers[i] for i in range(len(g1_cols) + 1, len(g1_cols) * 2 + 1)
            ]

            for i in range(0, len(groups), 2):
                g1 = groups[i]
                g2 = groups[i + 1] if (i + 1) < len(groups) else None

                row_header: dict[str, Any] = {}
                row_header[g1_cols[0]] = f"GROUP {g1['id']}"
                for idx, col in enumerate(score_cols):
                    row_header[g1_cols[idx + 1]] = (
                        f"AVG {col}: {g1['averages'][col]:.2f}"
                    )
                row_header[gap_col] = ""

                if g2:
                    row_header[g2_cols[0]] = f"GROUP {g2['id']}"
                    for idx, col in enumerate(score_cols):
                        row_header[g2_cols[idx + 1]] = (
                            f"AVG {col}: {g2['averages'][col]:.2f}"
                        )
                else:
                    for c in g2_cols:
                        row_header[c] = ""
                rows.append(row_header)

                row_sub: dict[str, Any] = {}
                row_sub[g1_cols[0]] = "Name"
                for idx, col in enumerate(score_cols):
                    row_sub[g1_cols[idx + 1]] = col
                row_sub[gap_col] = ""

                if g2:
                    row_sub[g2_cols[0]] = "Name"
                    for idx, col in enumerate(score_cols):
                        row_sub[g2_cols[idx + 1]] = col
                else:
                    for c in g2_cols:
                        row_sub[c] = ""
                rows.append(row_sub)

                len1 = len(g1["members"])
                len2 = len(g2["members"]) if g2 else 0
                max_len = max(len1, len2)

                for k in range(max_len):
                    m1 = g1["members"][k] if k < len1 else None
                    m2 = g2["members"][k] if g2 and k < len2 else None

                    row_data: dict[str, Any] = {}
                    row_data[g1_cols[0]] = m1[col_name] if m1 else ""
                    for idx, col in enumerate(score_cols):
                        row_data[g1_cols[idx + 1]] = m1[col] if m1 else ""
                    row_data[gap_col] = ""

                    if g2:
                        row_data[g2_cols[0]] = m2[col_name] if m2 else ""
                        for idx, col in enumerate(score_cols):
                            row_data[g2_cols[idx + 1]] = m2[col] if m2 else ""
                    else:
                        for c in g2_cols:
                            row_data[c] = ""

                    rows.append(row_data)

                rows.append({})

            pd.DataFrame(rows).to_excel(
                writer,
                sheet_name=sheet_name,
                index=False,
                header=False,
                startcol=0,
            )

            # Accurate dataset-wide global statistics for each dimension
            stats_start_col = len(g1_cols) * 2 + 2

            for col_idx, col in enumerate(score_cols):
                if col in df_results.columns:
                    col_data = pd.to_numeric(df_results[col], errors="coerce").dropna()
                    if not col_data.empty:
                        stats = [
                            {f"{col} Stat": "Lowest", "Val": f"{col_data.min():.3f}"},
                            {f"{col} Stat": "Highest", "Val": f"{col_data.max():.3f}"},
                            {
                                f"{col} Stat": "Global Avg",
                                "Val": f"{col_data.mean():.3f}",
                            },
                            {
                                f"{col} Stat": "StdDev",
                                "Val": f"{col_data.std(ddof=0):.4f}",
                            },
                        ]
                        pd.DataFrame(stats).to_excel(
                            writer,
                            sheet_name=sheet_name,
                            index=False,
                            startcol=stats_start_col + (col_idx * 3),
                        )

    return output.getvalue()
