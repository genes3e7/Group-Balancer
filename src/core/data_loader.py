"""Data loading and security-hardened sanitization utilities.

This module handles the import of participant data from CSV and Excel files,
ensuring strict path validation, size limits, and data type coercion.
"""

import os
import sys
from pathlib import Path

import pandas as pd

from src import logger
from src.core import config


def validate_file_path(path: str) -> Path:
    """Validates that a file path exists and is a file.

    Args:
        path (str): The user-provided path.

    Returns:
        Path: Validated absolute path as a Path object.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If the path is not a file or fails security checks.
    """
    # Normalize path and resolve symlinks
    abs_path = Path(path).resolve()

    if not abs_path.exists():
        msg = f"File not found: {abs_path}"
        raise FileNotFoundError(msg)

    if not abs_path.is_file():
        msg = f"Path is not a file: {abs_path}"
        raise ValueError(msg)

    # Check file size
    size_mb = os.path.getsize(abs_path) / (1024 * 1024)
    if size_mb > config.MAX_FILE_SIZE_MB:
        err = f"File size ({size_mb:.2f}MB) exceeds {config.MAX_FILE_SIZE_MB}MB."
        raise ValueError(err)

    return abs_path


def get_file_path_from_user() -> Path:
    """Prompts the user to input a file path via the command line.

    Returns:
        Path: Validated absolute path.
    """
    logger.info("Awaiting user input for data file...")
    logger.warning("\n[INPUT REQUIRED]")
    logger.warning("Please drag and drop your Excel/CSV file here and press Enter:")

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
            sys.exit(0)
        except (FileNotFoundError, ValueError) as e:
            logger.error(str(e))
        except EOFError:
            logger.warning("End of input stream detected.")
            sys.exit(1)
        except Exception:
            logger.exception("Unexpected error during file selection.")


def _sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Sanitizes the dataframe columns and values.

    Args:
        df (pd.DataFrame): The raw dataframe.

    Returns:
        pd.DataFrame: Sanitized dataframe.
    """
    df.columns = df.columns.astype(str).str.strip()
    score_cols = [col for col in df.columns if str(col).startswith(config.SCORE_PREFIX)]

    # Data Cleaning
    df[config.COL_NAME] = df[config.COL_NAME].astype(str).str.strip()

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
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    return df


def load_data(filepath: str) -> list[dict] | None:
    """Loads participant data with security checks and sanitization.

    Args:
        filepath (str): Path to the source file.

    Returns:
        list[dict] | None: A list of participant records or None on failure.
    """
    if not filepath:
        return None

    try:
        path_obj = validate_file_path(filepath)
        ext = path_obj.suffix.lower()

        if ext == ".csv":
            df = pd.read_csv(path_obj)
        elif ext in (".xls", ".xlsx"):
            df = pd.read_excel(path_obj)
        else:
            logger.error(f"Unsupported file format: {filepath}")
            return None

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

        df = _sanitize_dataframe(df)
        records = df.to_dict("records")

        if not records:
            logger.warning(f"File {filepath} contains no data records.")
            return None

        logger.info(f"Successfully loaded {len(records)} participants from {filepath}.")
        return records

    except (PermissionError, FileNotFoundError, ValueError) as e:
        logger.error(f"Error accessing '{filepath}': {e}")
        return None
    except Exception:
        logger.exception(f"Critical error loading data from {filepath}")
        return None
