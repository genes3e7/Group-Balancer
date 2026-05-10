"""Global configuration and constants for the Group Balancer.

Centralized point for developer maintenance.
"""

import os

# Data Schema
COL_NAME = "Name"
SCORE_PREFIX = "Score"
COL_GROUP = "Group"

# Advanced Constraints
COL_GROUPER = "Groupers"
COL_SEPARATOR = "Separators"

# Solver Core Limits
SCALE_FACTOR = 10**5
RESOLUTION_BASE = 10**3
SOLVER_TIMEOUT = 600
SOLVER_NUM_WORKERS = os.cpu_count() or 4

# Solver Scaling Tiers (Lexicographic Bit-Slicing)
# Order ensures absolute priority. UI Priority toggle swaps HI and LO multipliers.
TIER_HI_MULTIPLIER = 10**12
TIER_LO_MULTIPLIER = 10**9
TIER_FAIRNESS_MULTIPLIER = 10**7
TIER_BALANCE_MULTIPLIER = 10**0

# UI Constraints
UI_TIMEOUT_MIN = 5
UI_TIMEOUT_MAX = max(UI_TIMEOUT_MIN, SOLVER_TIMEOUT)
UI_TIMEOUT_DEFAULT = max(UI_TIMEOUT_MIN, min(60, UI_TIMEOUT_MAX))

OUTPUT_FILENAME = "balanced_groups.xlsx"

# Solver Defaults
DEFAULT_SCORE_WEIGHT = 1.0
DEFAULT_GROUPER_WEIGHT = 1
DEFAULT_SEPARATOR_WEIGHT = 1

# Security Limits
MAX_PARTICIPANTS = 10**3
MAX_GROUPS = 10**2
MAX_FILE_SIZE_MB = 10
