"""
Configuration constants for the Group Balancer application.

This module stores all hardcoded constants, column names, and solver settings
to ensure a single source of truth for configuration.
"""

# Column Headers
COL_NAME = "Name"
COL_SCORE = "Score"
COL_GROUP = "Group"

# Solver Settings
SOLVER_TIMEOUT = 300  # seconds
SOLVER_NUM_WORKERS = 8  # Parallel search workers

# Data Processing
SCALE_FACTOR = 10**5  # Multiplier to convert float scores to integers for the solver
ADVANTAGE_CHAR = "*"  # Suffix to identify "Star" participants

# Output
OUTPUT_FILENAME = "balanced_groups.xlsx"
