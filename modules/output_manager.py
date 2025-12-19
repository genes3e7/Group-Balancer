"""
Output Manager Module.

This module handles:
1. Formatting group data into presentation-ready structures.
2. Calculating statistical summaries (Std Dev, Min/Max).
3. Writing data to Excel files with multiple sheets.
4. Printing summaries to the command line.
"""

import pandas as pd
import numpy as np
from modules import config


def save_results(final_results: dict[str, list]):
    """
    Saves the results to an Excel file and prints a CLI summary.

    Args:
        final_results (dict): A dictionary where keys are sheet names and
                              values are lists of group dictionaries.
    """
    print(f"\nSaving to {config.OUTPUT_FILENAME}...")

    try:
        with pd.ExcelWriter(config.OUTPUT_FILENAME, engine='openpyxl') as writer:
            for sheet_name, groups in final_results.items():
                if not groups:
                    continue

                # --- 1. Prepare Main Grid Data ---
                s_groups = sorted(groups, key=lambda x: x['id'])
                rows = []

                # Format groups side-by-side in pairs (Left Group, Right Group)
                for i in range(0, len(s_groups), 2):
                    g1 = s_groups[i]
                    # Check if a right-side pair exists
                    g2 = s_groups[i+1] if (i + 1) < len(s_groups) else None

                    # Header Row
                    row_header = {
                        'A': f"GROUP {g1['id']}",
                        'B': f"AVG: {g1['avg']:.2f}",
                        'C': '',  # Spacer column
                        'D': f"GROUP {g2['id']}" if g2 else "",
                        'E': f"AVG: {g2['avg']:.2f}" if g2 else ""
                    }
                    rows.append(row_header)

                    # Sub-header Row
                    row_sub = {
                        'A': 'Name', 'B': 'Score', 'C': '',
                        'D': 'Name' if g2 else '', 'E': 'Score' if g2 else ''
                    }
                    rows.append(row_sub)

                    # Member Rows
                    len1 = len(g1['members'])
                    len2 = len(g2['members']) if g2 else 0
                    max_len = max(len1, len2)

                    for k in range(max_len):
                        m1 = g1['members'][k] if k < len1 else None
                        m2 = g2['members'][k] if g2 and k < len2 else None

                        rows.append({
                            'A': m1[config.COL_NAME] if m1 else "",
                            'B': m1[config.COL_SCORE] if m1 else "",
                            'C': "",
                            'D': m2[config.COL_NAME] if m2 else "",
                            'E': m2[config.COL_SCORE] if m2 else ""
                        })
                    
                    # Empty row between group blocks
                    rows.append({})

                # Write main grid to Excel
                df_grid = pd.DataFrame(rows)
                df_grid.to_excel(writer, sheet_name=sheet_name, index=False, header=False, startcol=0)

                # --- 2. Calculate Statistics ---
                avgs = [g['avg'] for g in groups]
                stats = []
                if avgs:
                    stats = [
                        {'Stat': 'Lowest', 'Val': f"{min(avgs):.3f}"},
                        {'Stat': 'Highest', 'Val': f"{max(avgs):.3f}"},
                        {'Stat': 'Global Avg', 'Val': f"{np.mean(avgs):.3f}"},
                        {'Stat': 'StdDev', 'Val': f"{np.std(avgs):.4f}"}
                    ]

                # Write stats table to Excel (starting at column G/index 6)
                df_stats = pd.DataFrame(stats)
                df_stats.to_excel(writer, sheet_name=sheet_name, index=False, startcol=6)

                # --- 3. CLI Summary ---
                print(f"\n--- {sheet_name} ---")
                for g in s_groups:
                    # Count 'Stars' for verification
                    star_count = sum(
                        1 for m in g['members']
                        if str(m[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR)
                    )
                    print(
                        f"Grp {g['id']} | "
                        f"Count: {len(g['members'])} | "
                        f"Stars: {star_count} | "
                        f"Avg: {g['avg']:.3f}"
                    )
                if avgs:
                    print(f"StdDev: {np.std(avgs):.4f}")

        print("\nSuccess! File saved.")

    except PermissionError:
        print(f"Error: Permission denied. Please close '{config.OUTPUT_FILENAME}' and try again.")
    except Exception as e:
        print(f"Error saving results: {e}")
