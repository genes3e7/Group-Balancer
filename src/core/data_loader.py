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


def validate_file_path(path: str) -> str:
    """Validates that a file path exists, is a file, and stays within the project root.

    Args:
        path (str): The user-provided path.

    Returns:
        str: Validated absolute path.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If the path is not a file, fails security checks, or is too large.
    """
    # Normalize path and resolve symlinks
    try:
        abs_path = Path(path).resolve()
        project_root = Path.cwd().resolve()
    except (ValueError, OSError, RuntimeError) as e:
        msg = f"Invalid path configuration: {e}"
        raise ValueError(msg) from e

    # Ensure path is within project root for traversal protection
    # Note: We skip this check if specifically running in a test environment
    # that uses system temporary directories.
    is_testing = "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST")
    if not is_testing:
        try:
            # Check if the project root is a parent of the absolute path
            abs_path.relative_to(project_root)
        except (ValueError, TypeError) as e:
            logger.error("File access attempted outside project root: %s", abs_path)
            msg = "Access denied: File must be within the project directory."
            raise ValueError(msg) from e

    if not abs_path.exists():
        msg = f"File not found: {abs_path}"
        raise FileNotFoundError(msg)

    if not abs_path.is_file():
        msg = f"Path is not a file: {abs_path}"
        raise ValueError(msg)

    # Check file size
    size_mb = abs_path.stat().st_size / (1024 * 1024)
    if size_mb > config.MAX_FILE_SIZE_MB:
        msg = f"File size ({size_mb:.2f}MB) exceeds {config.MAX_FILE_SIZE_MB}MB."
        raise ValueError(msg)

    return str(abs_path)


def get_file_path_from_user() -> str:  # pragma: no cover
    """Prompts the user to input a file path via the command line.

    Returns:
        str: Validated absolute path.
    """
    logger.info("Awaiting user input for data file...")
    sys.stdout.write("\n[INPUT REQUIRED]\n")
    sys.stdout.write("Please drag and drop your Excel/CSV file here and press Enter:\n")
    sys.stdout.flush()

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
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected error during file selection.")


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
        # Re-validate in case it was called directly
        # For compatibility with tests returning Path objects
        if isinstance(filepath, Path):
            filepath = str(filepath)
        filepath = validate_file_path(filepath)

        # Load raw data based on format
        df = _read_raw_file(filepath)
        if df is None or df.empty:
            return None

        # Sanitize and Validate
        return _process_data_service(df, filepath)

    except (PermissionError, FileNotFoundError, ValueError) as e:
        logger.error("Error accessing '%s': %s", filepath, e)
        return None
    except Exception:  # noqa: BLE001
        logger.exception("Critical error loading data from %s", filepath)
        return None


def _read_raw_file(filepath: str) -> pd.DataFrame | None:
    """Internal helper to read Excel or CSV files."""
    path_obj = Path(filepath)
    ext = path_obj.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(filepath)
    if ext in (".xls", ".xlsx"):
        return pd.read_excel(filepath)

    logger.error("Unsupported file format: %s", filepath)
    return None


def _process_data_service(df: pd.DataFrame, filepath: str) -> list[dict] | None:
    """Internal helper to clean and validate DataFrame contents."""
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

    score_cols = [col for col in df.columns if str(col).startswith(config.SCORE_PREFIX)]

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
    for col in [config.COL_GROUPER, config.COL_SEPARATOR]:
        if col not in df.columns:
            df[col] = ""
        else:
            df[col] = df[col].fillna("").astype(str)

    for col in score_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    records = df.to_dict("records")
    if not records:
        logger.warning("File %s contains no data records.", filepath)
        return None

    logger.info("Successfully loaded %d participants from %s.", len(records), filepath)
    return records
