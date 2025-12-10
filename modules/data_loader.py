# modules/data_loader.py
import pandas as pd
import os
import sys
from modules import config

def get_file_path_from_user():
    """
    Asks user for file input. Handles drag-and-drop artifacts 
    like surrounding quotes or the leading '&' from PowerShell.
    """
    print("\n[INPUT REQUIRED]")
    print("Please drag and drop your Excel/CSV file here and press Enter:")
    
    while True:
        user_input = input(">> ").strip()
        
        # 1. Remove leading '& ' (Common PowerShell artifact)
        if user_input.startswith('& '):
            user_input = user_input[2:]
        elif user_input.startswith('&'):
            user_input = user_input[1:]
            
        # 2. Remove surrounding quotes
        user_input = user_input.strip('"').strip("'").strip()
        
        if os.path.exists(user_input):
            return user_input
        else:
            print(f"Error: File not found at '{user_input}'. Please try again.")

def load_data(filepath):
    """Loads Excel or CSV into a list of dicts."""
    try:
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
            
        # Standardize columns
        df.columns = df.columns.str.strip()
        
        if config.COL_NAME not in df.columns or config.COL_SCORE not in df.columns:
            print(f"Error: Columns '{config.COL_NAME}' and '{config.COL_SCORE}' missing.")
            return None
        
        # Clean Data
        df[config.COL_NAME] = df[config.COL_NAME].astype(str).str.strip()
        df[config.COL_SCORE] = pd.to_numeric(df[config.COL_SCORE], errors='coerce').fillna(0)
        
        return df.to_dict('records')
        
    except Exception as e:
        print(f"Read Error: {e}")
        return None
