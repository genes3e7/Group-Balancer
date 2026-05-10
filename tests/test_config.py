"""Unit tests for the configuration module.

Ensures that the application's global constants and default values are
loaded correctly and maintain their required values.
"""

from src.core import config


def test_config_constants():
    """Verify that core configuration constants are correctly defined."""
    assert config.SCORE_PREFIX == "Score"
    assert config.COL_NAME == "Name"
    assert config.SCALE_FACTOR == 100_000
    assert config.COL_GROUP == "Group"
    assert config.OUTPUT_FILENAME == "balanced_groups.xlsx"
    assert config.SOLVER_TIMEOUT == 600
