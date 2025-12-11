# modules/output_manager.py
import pandas as pd
import numpy as np
from modules import config

"""
Module: Output Manager
Responsibility: Formatting results into Excel files and printing CLI summaries.
"""

def save_results(final_results):
    """
    Saves the dictionary of group results to an Excel file with multiple sheets.
    Also prints a summary table to the console.
    
    Args:
        final_results (dict): {SheetName: List of Group Dicts}
    """
    print(f"\nSaving to {config.OUTPUT_FILENAME}...")
    
    try:
        with pd.ExcelWriter(config.OUTPUT_FILENAME, engine='openpyxl') as writer:
            for sheet_name, groups in final_results.items():
                
                # --- 1. Prepare Data for Excel Grid ---
                # Sort by Group ID for consistent display
                s_groups = sorted(groups, key=lambda x: x['id'])
                rows = []
                
                # Display groups in pairs (Left Column, Right Column) for readability
                for i in range(0, len(s_groups), 2):
                    g1 = s_groups[i]
                    g2 = s_groups[i+1] if i+1 < len(s_groups) else None
                    
                    # Header Row
                    rows.append({
                        'A': f"GROUP {g1['id']}", 'B': f"AVG: {g1['avg']:.2f}", 'C': '', 
                        'D': f"GROUP {g2['id']}" if g2 else "", 'E': f"AVG: {g2['avg']:.2f}" if g2 else ""
                    })
                    # Sub-header Row
                    rows.append({'A': 'Name', 'B': 'Score', 'D': 'Name' if g2 else '', 'E': 'Score' if g2 else ''})
                    
                    # Member Rows
                    max_len = max(len(g1['members']), len(g2['members']) if g2 else 0)
                    for k in range(max_len):
                        m1 = g1['members'][k] if k < len(g1['members']) else None
                        m2 = g2['members'][k] if g2 and k < len(g2['members']) else None
                        
                        rows.append({
                            'A': m1[config.COL_NAME] if m1 else "", 
                            'B': m1[config.COL_SCORE] if m1 else "",
                            'D': m2[config.COL_NAME] if m2 else "", 
                            'E': m2[config.COL_SCORE] if m2 else ""
                        })
                    # Spacer Row
                    rows.append({})
                
                # Write Grid to Sheet
                pd.DataFrame(rows).to_excel(writer, sheet_name=sheet_name, index=False, header=False, startcol=0)
                
                # --- 2. Calculate Statistics ---
                avgs = [g['avg'] for g in groups]
                stats = [
                    {'Stat': 'Lowest', 'Val': f"{min(avgs):.3f}"},
                    {'Stat': 'Highest', 'Val': f"{max(avgs):.3f}"},
                    {'Stat': 'Global Avg', 'Val': f"{np.mean(avgs):.3f}"},
                    {'Stat': 'StdDev', 'Val': f"{np.std(avgs):.4f}"}
                ]
                
                # Write Stats to Sheet (Column G)
                pd.DataFrame(stats).to_excel(writer, sheet_name=sheet_name, index=False, startcol=6)
                
                # --- 3. CLI Summary Output ---
                print(f"\n--- {sheet_name} ---")
                for g in s_groups:
                    # Count stars for verification
                    star_count = sum(1 for m in g['members'] if str(m[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR))
                    print(f"Grp {g['id']} | Count: {len(g['members'])} | Stars: {star_count} | Avg: {g['avg']:.3f}")
                print(f"StdDev: {np.std(avgs):.4f}")

        print("\nSuccess! File saved.")
        
    except Exception as e:
        print(f"Error saving Excel file: {e}")
        print("Tip: Ensure the file is not currently open in Excel.")
