import pandas as pd
import numpy as np
import io


def generate_excel_bytes(df_results, col_group, col_score, col_name):
    """
    Generates an Excel file in-memory matching the 'Main Branch' format:
    - Side-by-side Group Matrix (Columns A-E)
    - Statistics Table (Starts at Column G)

    Args:
        df_results (pd.DataFrame): The dataframe containing participant data.
        col_group (str): Column name for Group ID.
        col_score (str): Column name for Score.
        col_name (str): Column name for Participant Name.

    Returns:
        bytes: The Excel file content.
    """
    output = io.BytesIO()

    # 1. Reconstruct group structure from DataFrame
    groups = []
    if not df_results.empty:
        unique_groups = sorted(df_results[col_group].unique())
        for g_id in unique_groups:
            # Get members for this group
            members = df_results[df_results[col_group] == g_id].to_dict("records")
            if members:
                scores = [float(m[col_score]) for m in members]
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
            # Handle empty case
            pd.DataFrame().to_excel(writer, sheet_name=sheet_name)
        else:
            # --- 2. Prepare Main Grid Data (Side-by-Side) ---
            rows = []
            for i in range(0, len(groups), 2):
                g1 = groups[i]
                # Check if a right-side pair exists
                g2 = groups[i + 1] if (i + 1) < len(groups) else None

                # Header Row
                row_header = {
                    "A": f"GROUP {g1['id']}",
                    "B": f"AVG: {g1['avg']:.2f}",
                    "C": "",  # Spacer column
                    "D": f"GROUP {g2['id']}" if g2 else "",
                    "E": f"AVG: {g2['avg']:.2f}" if g2 else "",
                }
                rows.append(row_header)

                # Sub-header Row
                row_sub = {
                    "A": "Name",
                    "B": "Score",
                    "C": "",
                    "D": "Name" if g2 else "",
                    "E": "Score" if g2 else "",
                }
                rows.append(row_sub)

                # Member Rows
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

                # Empty row between group blocks
                rows.append({})

            # Write Main Grid to Excel (starting at col A / index 0)
            pd.DataFrame(rows).to_excel(
                writer, sheet_name=sheet_name, index=False, header=False, startcol=0
            )

            # --- 3. Calculate & Write Statistics (Column G) ---
            avgs = [g["avg"] for g in groups]
            if avgs:
                stats = [
                    {"Stat": "Lowest", "Val": f"{min(avgs):.3f}"},
                    {"Stat": "Highest", "Val": f"{max(avgs):.3f}"},
                    {"Stat": "Global Avg", "Val": f"{np.mean(avgs):.3f}"},
                    {"Stat": "StdDev", "Val": f"{np.std(avgs):.4f}"},
                ]
                # Write stats table starting at column G (index 6)
                pd.DataFrame(stats).to_excel(
                    writer, sheet_name=sheet_name, index=False, startcol=6
                )

    return output.getvalue()
