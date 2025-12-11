# modules/data_loader.py
import pandas as pd
import os
import sys
from modules import config

"""
Module: Data Loader
Responsibility: Handles user input for file paths and loading Excel/CSV data.
"""

def get_file_path_from_user():
    """
    Prompts the user to drag and drop a file into the terminal.
    
    Handles common CLI artifacts such as:
    1. Surrounding quotes (Windows/Mac).
    2. Leading '& ' characters (PowerShell).
    
    Returns:
        str: The clean, absolute path to the file.
    """
    print("\n[INPUT REQUIRED]")
    print("Please drag and drop your Excel/CSV file here and press Enter:")
    
    while True:
        user_input = input(">> ").strip()
        
        # Clean up PowerShell artifacts
        if user_input.startswith('& '):
            user_input = user_input[2:]
        elif user_input.startswith('&'):
            user_input = user_input[1:]
            
        # Clean up OS path artifacts
        user_input = user_input.strip('"').strip("'").strip()
        
        if os.path.exists(user_input):
            return user_input
        else:
            print(f"Error: File not found at '{user_input}'. Please try again.")

def load_data(filepath):
    """
    Loads data from Excel or CSV into a list of dictionaries.
    
    Performs validation to ensure required columns exist.
    
    Args:
        filepath (str): Path to the source file.
        
    Returns:
        list[dict] or None: A list of participant records, or None if loading failed.
    """
    try:
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
            
        # Normalize column names (remove surrounding whitespace)
        df.columns = df.columns.str.strip()
        
        # Validation
        if config.COL_NAME not in df.columns or config.COL_SCORE not in df.columns:
            print(f"Error: Columns '{config.COL_NAME}' and '{config.COL_SCORE}' must exist in the file.")
            return None
        
        # Clean Data Types
        df[config.COL_NAME] = df[config.COL_NAME].astype(str).str.strip()
        # Coerce invalid numbers to 0 to prevent crashes
        df[config.COL_SCORE] = pd.to_numeric(df[config.COL_SCORE], errors='coerce').fillna(0)
        
        return df.to_dict('records')
        
    except Exception as e:
        print(f"Read Error: {e}")
        return None
