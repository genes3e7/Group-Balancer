"""Unit tests for the configuration module.

Ensures that the application's global constants and default values are
loaded correctly and maintain their required values.
"""

from src.core import config


def test_config_constants() -> None:
    """Verify core configuration values and constants."""
    assert config.SCORE_PREFIX == "Score"
    assert config.COL_NAME == "Name"

    expected_scale = 100_000
    assert config.SCALE_FACTOR == expected_scale

    assert config.COL_GROUP == "Group"
    assert config.OUTPUT_FILENAME == "balanced_groups.xlsx"

    expected_timeout = 600
    assert config.SOLVER_TIMEOUT == expected_timeout
