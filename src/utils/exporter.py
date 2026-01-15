import pandas as pd
import io


def generate_excel_bytes(df_results, col_group, col_score, col_name):
    """
    Generates an Excel file in-memory with two sheets:
    1. Assignments: Flat list of results.
    2. Matrix_View: Side-by-side comparison of groups.

    Returns:
        bytes: The Excel file content.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Sheet 1: Flat List
        df_results.to_excel(writer, sheet_name="Assignments", index=False)

        # Sheet 2: Matrix View (Side by Side)
        groups = []
        unique_groups = sorted(df_results[col_group].unique())
        for g_id in unique_groups:
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

        rows = []
        # Redundant sort removed (groups are already sorted via unique_groups loop)

        # Create pairs of groups for side-by-side view
        for i in range(0, len(groups), 2):
            g1 = groups[i]
            g2 = groups[i + 1] if i + 1 < len(groups) else None

            # Header Row
            rows.append(
                {
                    "A": f"GROUP {g1['id']}",
                    "B": f"AVG: {g1['avg']:.2f}",
                    "C": "",
                    "D": f"GROUP {g2['id']}" if g2 else "",
                    "E": f"AVG: {g2['avg']:.2f}" if g2 else "",
                }
            )
            # Column Names
            rows.append(
                {
                    "A": "Name",
                    "B": "Score",
                    "C": "",
                    "D": "Name" if g2 else "",
                    "E": "Score" if g2 else "",
                }
            )

            # Member Rows
            len1 = len(g1["members"])
            len2 = len(g2["members"]) if g2 else 0
            for k in range(max(len1, len2)):
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
            rows.append({})  # Spacer

        if rows:
            pd.DataFrame(rows).to_excel(
                writer, sheet_name="Matrix_View", index=False, header=False
            )

    return output.getvalue()
