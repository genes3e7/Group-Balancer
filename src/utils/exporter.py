"""
Excel export utility.

This module formats the results into a side-by-side 'Matrix View' structure
and includes summary statistics in the generated Excel file.
"""

import pandas as pd
import numpy as np
import io


def generate_excel_bytes(
    df_results: pd.DataFrame, col_group: str, col_score: str, col_name: str
) -> bytes:
    """
    Generates an Excel file in-memory matching the 'Main Branch' format.

    Structure:
    - Side-by-side Group Matrix (Columns A-E for pairs)
    - Statistics Table (Starts at Column G)

    Args:
        df_results (pd.DataFrame): The dataframe containing participant data.
        col_group (str): Column name for Group ID.
        col_score (str): Column name for Score.
        col_name (str): Column name for Participant Name.

    Returns:
        bytes: The Excel file content as bytes.
    """
    output = io.BytesIO()

    groups = []
    if not df_results.empty:
        unique_groups = sorted(df_results[col_group].unique())
        for g_id in unique_groups:
            members = df_results[df_results[col_group] == g_id].to_dict("records")
            if members:
                scores = []
                for m in members:
                    try:
                        scores.append(float(m[col_score]))
                    except (ValueError, TypeError):
                        scores.append(0.0)

                groups.append(
                    {
                        "id": g_id,
                        "members": members,
                        "avg": sum(scores) / len(scores) if scores else 0,
                    }
                )

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sheet_name = "Balanced_Groups"

        if not groups:
            pd.DataFrame().to_excel(writer, sheet_name=sheet_name)
        else:
            rows = []
            for i in range(0, len(groups), 2):
                g1 = groups[i]
                g2 = groups[i + 1] if (i + 1) < len(groups) else None

                row_header = {
                    "A": f"GROUP {g1['id']}",
                    "B": f"AVG: {g1['avg']:.2f}",
                    "C": "",
                    "D": f"GROUP {g2['id']}" if g2 else "",
                    "E": f"AVG: {g2['avg']:.2f}" if g2 else "",
                }
                rows.append(row_header)

                row_sub = {
                    "A": "Name",
                    "B": "Score",
                    "C": "",
                    "D": "Name" if g2 else "",
                    "E": "Score" if g2 else "",
                }
                rows.append(row_sub)

                len1 = len(g1["members"])
                len2 = len(g2["members"]) if g2 else 0
                max_len = max(len1, len2)

                for k in range(max_len):
                    m1 = g1["members"][k] if k < len1 else None
                    m2 = g2["members"][k] if g2 and k < len2 else None

                    rows.append(
                        {
                            "A": m1[col_name] if m1 else "",
                            "B": m1[col_score] if m1 else "",
                            "C": "",
                            "D": m2[col_name] if m2 else "",
                            "E": m2[col_score] if m2 else "",
                        }
                    )

                rows.append({})

            pd.DataFrame(rows).to_excel(
                writer, sheet_name=sheet_name, index=False, header=False, startcol=0
            )

            avgs = [g["avg"] for g in groups]
            if avgs:
                stats = [
                    {"Stat": "Lowest", "Val": f"{min(avgs):.3f}"},
                    {"Stat": "Highest", "Val": f"{max(avgs):.3f}"},
                    {"Stat": "Global Avg", "Val": f"{np.mean(avgs):.3f}"},
                    {"Stat": "StdDev", "Val": f"{np.std(avgs):.4f}"},
                ]
                pd.DataFrame(stats).to_excel(
                    writer, sheet_name=sheet_name, index=False, startcol=6
                )

    return output.getvalue()
