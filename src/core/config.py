"""
Configuration module for the Group Balancer application.

This module centralizes all constant values used across the application,
including file names, column headers, solver settings, and formatting options.
"""

# Output Settings
OUTPUT_FILENAME = "balanced_groups.xlsx"

# Input Data Column Headers (Must match the input Excel/CSV file)
COL_NAME = "Name"
COL_SCORE = "Score"
COL_GROUP = "Group"  # <--- Added this missing line

# Excel Sheet Names for the Output File
SHEET_WITH_CONSTRAINT = "With_Star_Constraint"
SHEET_WITHOUT_CONSTRAINT = "No_Constraints"

# Symbol used to identify "Star" or "Advantaged" participants in their name
ADVANTAGE_CHAR = "*"

# Solver Settings
# Time limit for the Google OR-Tools CP-SAT solver in seconds.
# 300 seconds (5 minutes) is a conservative upper bound.
SOLVER_TIMEOUT = 60 * 5

# Scaling factor to convert floating point scores to integers for the solver.
# 100,000 allows for 5 decimal places of precision.
SCALE_FACTOR = 10**5

# Number of workers for the solver to use in parallel search
SOLVER_NUM_WORKERS = 8
