"""
Data Loader Module.

This module is responsible for:
1. interacting with the user to get file paths.
2. sanitizing drag-and-drop input strings.
3. loading data from Excel or CSV files.
4. validating the structure and content of the loaded data.
"""

import os
import pandas as pd
from src.core import config


def get_file_path_from_user() -> str:
    """
    Prompts the user to input a file path via standard input.

    Handles common artifacts introduced by drag-and-dropping files into
    terminal windows, such as surrounding quotes or leading '& ' symbols
    often seen in PowerShell.

    Returns:
        str: The sanitized, absolute file path entered by the user.
    """
    print("\n[INPUT REQUIRED]")
    print("Please drag and drop your Excel/CSV file here and press Enter:")

    while True:
        try:
            user_input = input(">> ").strip()

            # Remove leading '& ' often added by PowerShell drag-and-drop
            if user_input.startswith("& "):
                user_input = user_input[2:]
            elif user_input.startswith("&"):
                user_input = user_input[1:]

            # Remove surrounding quotes (common in Windows/macOS paths)
            user_input = user_input.strip('"').strip("'").strip()

            if not user_input:
                continue

            if os.path.exists(user_input):
                return os.path.abspath(user_input)
            else:
                print(f"Error: File not found at '{user_input}'. Please try again.")

        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            exit(0)
        except Exception as e:
            print(f"An unexpected error occurred during input: {e}")


def load_data(filepath: str) -> list[dict] | None:
    """
    Loads data from an Excel or CSV file into a list of dictionaries.

    Performs validation to ensure required columns exist and cleans up data types.

    Args:
        filepath (str): The absolute path to the source file.

    Returns:
        list[dict] | None: A list of participant records if successful,
                           or None if an error occurred.
    """
    if not filepath:
        return None

    try:
        if filepath.lower().endswith(".csv"):
            df = pd.read_csv(filepath)
        elif filepath.lower().endswith((".xls", ".xlsx")):
            df = pd.read_excel(filepath)
        else:
            print("Error: Unsupported file format. Please use .csv or .xlsx")
            return None

        # Normalize column names (strip whitespace)
        df.columns = df.columns.str.strip()

        # Validate required columns
        if config.COL_NAME not in df.columns or config.COL_SCORE not in df.columns:
            print(
                f"Error: Input file must contain columns '{config.COL_NAME}' and '{config.COL_SCORE}'."
            )
            print(f"Found columns: {list(df.columns)}")
            return None

        # Clean Data
        # Ensure names are strings and strip whitespace
        df[config.COL_NAME] = df[config.COL_NAME].astype(str).str.strip()

        # Ensure scores are numeric, coercing errors to NaN then filling with 0
        df[config.COL_SCORE] = pd.to_numeric(
            df[config.COL_SCORE], errors="coerce"
        ).fillna(0)

        records = df.to_dict("records")
        if not records:
            print("Error: The input file appears to be empty.")
            return None

        return records

    except PermissionError:
        print(f"Error: Permission denied accessing '{filepath}'. Is the file open?")
        return None
    except Exception as e:
        print(f"Error loading data: {e}")
        return None
