# modules/config.py

"""
Configuration settings for the Group Balancer application.
Centralizes all constants to avoid magic numbers in the code.
"""

# Output Settings
OUTPUT_FILENAME = 'balanced_groups.xlsx'

# Input Data Column Headers (Must match Excel file)
COL_NAME = 'Name'
COL_SCORE = 'Score'

# Excel Sheet Names for the Output File
SHEET_WITH_CONSTRAINT = 'With_Star_Constraint'
SHEET_WITHOUT_CONSTRAINT = 'No_Constraints'

# Symbol used to identify "Star" or "Advantaged" participants
ADVANTAGE_CHAR = '*'

# Solver Settings
# Time limit for the Google OR-Tools CP-SAT solver in seconds.
# 300 seconds (5 minutes) is a safe upper bound, though typical
# convergence for N<100 occurs in <10 seconds.
SOLVER_TIMEOUT = 300
