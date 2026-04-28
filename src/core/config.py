"""Global configuration and constants for the Group Balancer.

Centralized point for developer maintenance.
"""

import os

# --- Data Schema ---
COL_NAME = "Name"
SCORE_PREFIX = "Score"
COL_GROUP = "Group"

# --- Advanced Constraints ---
COL_GROUPER = "Groupers"
COL_SEPARATOR = "Separators"

# --- Solver Core Limits ---
SCALE_FACTOR = 100000  # Scale float scores to integers for CP-SAT
SOLVER_TIMEOUT = 600  # Absolute server hard-cap (seconds)
SOLVER_NUM_WORKERS = os.cpu_count() or 4

# --- UI Constraints ---
UI_TIMEOUT_MIN = 5
UI_TIMEOUT_MAX = max(UI_TIMEOUT_MIN, SOLVER_TIMEOUT)
UI_TIMEOUT_DEFAULT = max(UI_TIMEOUT_MIN, min(60, UI_TIMEOUT_MAX))

# I/O
OUTPUT_FILENAME = "balanced_groups.xlsx"

# --- Solver Defaults ---
DEFAULT_SCORE_WEIGHT = 1.0
DEFAULT_GROUPER_WEIGHT = 100
DEFAULT_SEPARATOR_WEIGHT = 50

# --- Security Limits ---

MAX_PARTICIPANTS = 1000
MAX_GROUPS = 100
MAX_FILE_SIZE_MB = 10
