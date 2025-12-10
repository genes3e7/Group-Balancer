# modules/output_manager.py
import pandas as pd
import numpy as np
from modules import config

def save_results(final_results):
    print(f"\nSaving to {config.OUTPUT_FILENAME}...")
    try:
        with pd.ExcelWriter(config.OUTPUT_FILENAME, engine='openpyxl') as writer:
            for sheet, groups in final_results.items():
                # Grid DF
                s_groups = sorted(groups, key=lambda x: x['id'])
                rows = []
                for i in range(0, len(s_groups), 2):
                    g1 = s_groups[i]
                    g2 = s_groups[i+1] if i+1 < len(s_groups) else None
                    
                    rows.append({'A': f"GROUP {g1['id']}", 'B': f"AVG: {g1['avg']:.2f}", 'C': '', 
                                 'D': f"GROUP {g2['id']}" if g2 else "", 'E': f"AVG: {g2['avg']:.2f}" if g2 else ""})
                    rows.append({'A': 'Name', 'B': 'Score', 'D': 'Name' if g2 else '', 'E': 'Score' if g2 else ''})
                    
                    max_len = max(len(g1['members']), len(g2['members']) if g2 else 0)
                    for k in range(max_len):
                        m1 = g1['members'][k] if k < len(g1['members']) else None
                        m2 = g2['members'][k] if g2 and k < len(g2['members']) else None
                        rows.append({
                            'A': m1[config.COL_NAME] if m1 else "", 'B': m1[config.COL_SCORE] if m1 else "",
                            'D': m2[config.COL_NAME] if m2 else "", 'E': m2[config.COL_SCORE] if m2 else ""
                        })
                    rows.append({})
                
                pd.DataFrame(rows).to_excel(writer, sheet_name=sheet, index=False, header=False, startcol=0)
                
                # Stats Table
                avgs = [g['avg'] for g in groups]
                stats = [
                    {'Stat': 'Lowest', 'Val': f"{min(avgs):.3f}"},
                    {'Stat': 'Highest', 'Val': f"{max(avgs):.3f}"},
                    {'Stat': 'Avg', 'Val': f"{np.mean(avgs):.3f}"},
                    {'Stat': 'StdDev', 'Val': f"{np.std(avgs):.3f}"}
                ]
                pd.DataFrame(stats).to_excel(writer, sheet_name=sheet, index=False, startcol=6)
                
                # CLI Output
                print(f"\n--- {sheet} ---")
                for g in s_groups:
                    print(f"Grp {g['id']} | Cnt: {len(g['members'])} | Avg: {g['avg']:.3f}")
                print(f"StdDev: {np.std(avgs):.4f}")

        print("\nSuccess! File saved.")
    except Exception as e:
        print(f"Error saving Excel file: {e}")
