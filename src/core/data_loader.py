"""
Data Loader Module.

This module handles:
1. User interaction for retrieving file paths via standard input.
2. Sanitization of input strings (removing artifacts from drag-and-drop).
3. Loading and parsing of data from Excel or CSV files.
4. Validation and cleaning of the loaded dataset.
"""

import os
import pandas as pd
from src.core import config


def get_file_path_from_user() -> str:
    """
    Prompt the user to input a file path via standard input.

    This function handles artifacts commonly introduced by dragging and dropping
    files into a terminal, such as surrounding quotes or PowerShell's '& ' prefix.

    Returns:
        str: The sanitized, absolute file path entered by the user.

    Raises:
        SystemExit: If the user interrupts the input (Ctrl+C).
    """
    print("\n[INPUT REQUIRED]")
    print("Please drag and drop your Excel/CSV file here and press Enter:")

    while True:
        try:
            user_input = input(">> ").strip()

            # Sanitize input: Remove PowerShell '& ' artifacts
            if user_input.startswith("& "):
                user_input = user_input[2:]
            elif user_input.startswith("&"):
                user_input = user_input[1:]

            # Sanitize input: Remove surrounding quotes
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
    Load data from an Excel or CSV file into a list of dictionaries.

    This function performs the following steps:
    1. Determines file type by extension.
    2. Reads the file into a pandas DataFrame.
    3. Normalizes column headers.
    4. Validates the existence of required columns.
    5. Cleans data types (strings for names, numerics for scores).

    Args:
        filepath (str): The absolute path to the source file.

    Returns:
        list[dict] | None: A list of participant records (dict) if successful,
                           or None if validation fails or an error occurs.
    """
    if not filepath:
        return None

    try:
        # Determine loader based on extension
        if filepath.lower().endswith(".csv"):
            df = pd.read_csv(filepath)
        elif filepath.lower().endswith((".xls", ".xlsx")):
            df = pd.read_excel(filepath)
        else:
            print("Error: Unsupported file format. Please use .csv or .xlsx")
            return None

        # Normalize column names
        df.columns = df.columns.str.strip()

        # Validate schema
        if config.COL_NAME not in df.columns or config.COL_SCORE not in df.columns:
            print(
                f"Error: Input file must contain columns '{config.COL_NAME}' and '{config.COL_SCORE}'."
            )
            print(f"Found columns: {list(df.columns)}")
            return None

        # Clean Data: Enforce string type for names
        df[config.COL_NAME] = df[config.COL_NAME].astype(str).str.strip()

        # Clean Data: Enforce numeric type for scores, handling coercion
        original_scores = df[config.COL_SCORE]
        df[config.COL_SCORE] = pd.to_numeric(original_scores, errors="coerce")

        # Check for values that became NaN (were not numeric)
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
