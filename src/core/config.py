"""Global configuration and constants for the Group Balancer.

Centralized point for developer maintenance.
"""

import os

# =============================================================================
# 1. Data Schema & Identifiers
# =============================================================================
COL_NAME = "Name"
SCORE_PREFIX = "Score"
COL_GROUP = "Group"
COL_GROUPER = "Groupers"
COL_SEPARATOR = "Separators"

# Application Step Identifiers
STEP_DATA_ENTRY = 1
STEP_CONFIGURE = 2
STEP_RESULTS = 3

# =============================================================================
# 2. Solver Core Limits & Tiers
# =============================================================================
SCALE_FACTOR = 10**5
RESOLUTION_BASE = 10**3
SOLVER_TIMEOUT = 600
SOLVER_NUM_WORKERS = os.cpu_count() or 4

# Solver Scaling Tiers (Lexicographic Bit-Slicing)
# Order ensures absolute priority. UI Priority toggle swaps HI and LO multipliers.
TIER_HI_MULTIPLIER = 10**12  # Primary Priority (User Choice)
TIER_LO_MULTIPLIER = 10**9  # Secondary Priority
TIER_FAIRNESS_MULTIPLIER = 10**7  # Max-Min Fairness (Minimize worst outlier)
TIER_BALANCE_MULTIPLIER = 10**0  # Overall L2 Balance (Sum of Squares)

# =============================================================================
# 3. Mathematical Domain Constants (CRITICAL)
# =============================================================================
# CP-SAT operates on 64-bit integers.
MAX_INT_LIMIT = (1 << 62) - 1
# Target sum for normalized score resolution
PRECISION_TARGET_SUM = 10**15
# Maximum internal resolution multiplier
MAX_PRECISION_RESOLUTION = 1000.0
# Internal penalty for logical constraint violations
MAX_WEIGHT_LIMIT = 1_000_000

# =============================================================================
# 4. UI Constraints & Defaults
# =============================================================================
UI_TIMEOUT_MIN = 5
UI_TIMEOUT_MAX = max(UI_TIMEOUT_MIN, SOLVER_TIMEOUT)
UI_TIMEOUT_DEFAULT = max(UI_TIMEOUT_MIN, min(60, UI_TIMEOUT_MAX))

DEFAULT_SCORE_WEIGHT = 1.0
DEFAULT_GROUPER_WEIGHT = 1
DEFAULT_SEPARATOR_WEIGHT = 1
DEFAULT_UI_WEIGHT = 1.0

MIN_PARTICIPANTS_FOR_BALANCING = 2
MAX_WARM_CACHE_SIZE = 50
UPDATE_INTERVAL_SECONDS = 0.25
DISPLAY_OBJECTIVE_DIVISOR_FACTOR = 100

# Keys that should not be deleted when the user clicks 'Start Over'
RESET_PRESERVE_KEYS = frozenset({"warm_start_cache"})

# =============================================================================
# 5. Excel Export Layout Constants
# =============================================================================
OUTPUT_FILENAME = "balanced_groups.xlsx"
MIN_HEADER_COUNT = 50
COLS_PER_GROUP_BASE = 1
GAP_COLUMN_WIDTH = 1
STATS_COLUMN_OFFSET = 5
STATS_PRECISION = 2

# =============================================================================
# 6. Security & Resource Limits
# =============================================================================
MAX_PARTICIPANTS = 10**3
MAX_GROUPS = 10**2
MAX_FILE_SIZE_MB = 10

# Safety Invariant: (TIER_HI_MULTIPLIER * MAX_PARTICIPANTS) must be < MAX_INT_LIMIT
# to prevent numerical overflow in CP-SAT's 64-bit domain.
if (TIER_HI_MULTIPLIER * MAX_PARTICIPANTS) >= MAX_INT_LIMIT:  # pragma: no cover
    msg = (
        f"Scaling constants risk 64-bit overflow: "
        f"{TIER_HI_MULTIPLIER} * {MAX_PARTICIPANTS} must be < {MAX_INT_LIMIT}"
    )
    raise ValueError(msg)
