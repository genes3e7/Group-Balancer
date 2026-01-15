"""
Data loading and sanitization utilities.

This module handles the import of participant data from CSV and Excel files,
ensuring that column names are normalized and data types are coerced correctly.
"""

import os
import pandas as pd
from src.core import config


def get_file_path_from_user() -> str:
    """
    Prompts the user to input a file path via the command line.

    Handles common artifacts from drag-and-drop operations, such as removing
    surrounding quotes or PowerShell's '& ' prefix.

    Returns:
        str: The absolute path to the file.

    Raises:
        SystemExit: If the user cancels the operation via KeyboardInterrupt.
    """
    print("\n[INPUT REQUIRED]")
    print("Please drag and drop your Excel/CSV file here and press Enter:")

    while True:
        try:
            user_input = input(">> ").strip()

            if user_input.startswith("& "):
                user_input = user_input[2:]
            elif user_input.startswith("&"):
                user_input = user_input[1:]

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
    Loads participant data from a CSV or Excel file.

    Args:
        filepath (str): Path to the source file.

    Returns:
        list[dict] | None: A list of participant records if successful,
        or None if validation fails.
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

        df.columns = df.columns.str.strip()

        if config.COL_NAME not in df.columns or config.COL_SCORE not in df.columns:
            print(
                f"Error: Input file must contain columns '{config.COL_NAME}' and '{config.COL_SCORE}'."
            )
            print(f"Found columns: {list(df.columns)}")
            return None

        df[config.COL_NAME] = df[config.COL_NAME].astype(str).str.strip()

        original_scores = df[config.COL_SCORE]
        df[config.COL_SCORE] = pd.to_numeric(original_scores, errors="coerce")

        coerced_mask = df[config.COL_SCORE].isna() & original_scores.notna()
        if coerced_mask.any():
            invalid_names = df.loc[coerced_mask, config.COL_NAME].tolist()
            print(f"Warning: Non-numeric scores for {invalid_names} were set to 0.")

        df[config.COL_SCORE] = df[config.COL_SCORE].fillna(0)

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
