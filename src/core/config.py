"""
Global configuration and constants for the Group Balancer.
Centralized point for developer maintenance.
"""

import os

# --- Data Schema ---
COL_NAME = "Name"
COL_SCORE = "Score"
COL_GROUP = "Group"
ADVANTAGE_CHAR = "*"

# --- Solver Core Limits ---
SCALE_FACTOR = 100000  # Scale float scores to integers for CP-SAT
SOLVER_TIMEOUT = 300  # Absolute server hard-cap (seconds)
SOLVER_NUM_WORKERS = os.cpu_count() or 4

# --- UI Constraints ---
UI_TIMEOUT_MIN = 5
UI_TIMEOUT_MAX = SOLVER_TIMEOUT
UI_TIMEOUT_DEFAULT = min(60, SOLVER_TIMEOUT)

# --- I/O ---
OUTPUT_FILENAME = "balanced_groups.xlsx"
