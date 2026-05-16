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
# Lexicographic Bit-Slicing Multipliers
# These constants define the priority hierarchy of optimization objectives.
# By scaling each tier by several orders of magnitude, we ensure that higher-tier
# goals (e.g. Conflicts) are mathematically prioritized over lower-tier ones
# (e.g. Balance) without requiring multiple solver passes.
# Note: Multipliers are designed to stay within 64-bit integer limits assuming
# a maximum deviation of ~10^3 per participant.
TIER_HI_MULTIPLIER = 10**12  # Primary Priority (User Choice)
TIER_LO_MULTIPLIER = 10**9  # Secondary Priority
TIER_FAIRNESS_MULTIPLIER = 10**7  # Max-Min Fairness (Minimize worst outlier)
TIER_BALANCE_MULTIPLIER = 10**0  # Overall L2 Balance (Sum of Squares)

# Safety Invariant: (TIER_HI_MULTIPLIER * MAX_PARTICIPANTS) must be < (1 << 62)
# to prevent numerical overflow in CP-SAT's 64-bit domain.
assert (TIER_HI_MULTIPLIER * 1000) < (1 << 62), (
    "Scaling constants risk 64-bit overflow."
)

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
