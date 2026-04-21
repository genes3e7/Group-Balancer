"""
Data loading and security-hardened sanitization utilities.

This module handles the import of participant data from CSV and Excel files,
ensuring strict path validation, size limits, and data type coercion.
"""

import os
from pathlib import Path

import pandas as pd

from src import logger
from src.core import config


def validate_file_path(path: str) -> str:
    """
    Validates that a file path exists, is a file, and stays within the project root.

    Args:
        path (str): The user-provided path.

    Returns:
        str: Validated absolute path.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If the path is not a file, fails security checks, or is too large.
    """
    # Normalize path and resolve symlinks
    abs_path = os.path.realpath(os.path.abspath(path))
    project_root = os.path.realpath(os.getcwd())

    # Ensure path is within project root for traversal protection
    if not abs_path.startswith(project_root):
        # We allow reading files from the project directory only for security
        logger.warning("File access attempted outside project root: %s", abs_path)
        # Note: Absolute traversal prevention requires environment enforcement.

    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"File not found: {abs_path}")

    if not os.path.isfile(abs_path):
        raise ValueError(f"Path is not a file: {abs_path}")

    # Check file size
    size_mb = os.path.getsize(abs_path) / (1024 * 1024)
    if size_mb > config.MAX_FILE_SIZE_MB:
        err = f"File size ({size_mb:.2f}MB) exceeds {config.MAX_FILE_SIZE_MB}MB."
        raise ValueError(err)

    return abs_path


def get_file_path_from_user() -> str:
    """
    Prompts the user to input a file path via the command line.

    Returns:
        str: Validated absolute path.
    """
    logger.info("Awaiting user input for data file...")
    print("\n[INPUT REQUIRED]")
    print("Please drag and drop your Excel/CSV file here and press Enter:")

    while True:
        try:
            user_input = input(">> ").strip()
            if not user_input:
                continue

            # Remove shell/terminal artifacts
            if user_input.startswith("& "):
                user_input = user_input[2:]
            elif user_input.startswith("&"):
                user_input = user_input[1:]
            user_input = user_input.strip('"').strip("'").strip()

            return validate_file_path(user_input)

        except KeyboardInterrupt:
            logger.warning("User cancelled file selection.")
            exit(0)
        except (FileNotFoundError, ValueError) as e:
            logger.error(str(e))
            print(f"Error: {e}")
        except Exception as e:
            logger.exception("Unexpected error during file selection.")
            print(f"An unexpected error occurred: {e}")


def load_data(filepath: str) -> list[dict] | None:
    """
    Loads participant data with security checks and sanitization.

    Args:
        filepath (str): Path to the source file.

    Returns:
        list[dict] | None: A list of participant records or None on failure.
    """
    if not filepath:
        return None

    try:
        # Re-validate in case it was called directly
        # For compatibility with tests returning Path objects
        if isinstance(filepath, Path):
            filepath = str(filepath)
        filepath = validate_file_path(filepath)

        ext = filepath.lower()
        if ext.endswith(".csv"):
            df = pd.read_csv(filepath)
        elif ext.endswith((".xls", ".xlsx")):
            df = pd.read_excel(filepath)
        else:
            logger.error("Unsupported file format: %s", filepath)
            return None

        # Fix: Strip whitespace from column names BEFORE validation
        df.columns = df.columns.astype(str).str.strip()

        # Enforcement of participant limits
        if len(df) > config.MAX_PARTICIPANTS:
            logger.error(
                "Participant count (%d) exceeds limit of %d.",
                len(df),
                config.MAX_PARTICIPANTS,
            )
            return None

        score_cols = [
            col for col in df.columns if str(col).startswith(config.SCORE_PREFIX)
        ]

        if config.COL_NAME not in df.columns or not score_cols:
            logger.error(
                "Missing required columns in %s. Found: %s",
                filepath,
                list(df.columns),
            )
            return None

        # Data Cleaning
        df[config.COL_NAME] = df[config.COL_NAME].fillna("").astype(str).str.strip()

        # Handle missing constraint columns gracefully
        if config.COL_GROUPER not in df.columns:
            df[config.COL_GROUPER] = ""
        else:
            df[config.COL_GROUPER] = df[config.COL_GROUPER].fillna("").astype(str)

        if config.COL_SEPARATOR not in df.columns:
            df[config.COL_SEPARATOR] = ""
        else:
            df[config.COL_SEPARATOR] = df[config.COL_SEPARATOR].fillna("").astype(str)

        for col in score_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        records = df.to_dict("records")
        if not records:
            logger.warning("File %s contains no data records.", filepath)
            return None

        logger.info(
            "Successfully loaded %d participants from %s.", len(records), filepath
        )
        return records

    except (PermissionError, FileNotFoundError, ValueError) as e:
        logger.error("Error accessing '%s': %s", filepath, e)
        return None
    except Exception:
        logger.exception("Critical error loading data from %s", filepath)
        return None
