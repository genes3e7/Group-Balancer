"""
Unit tests/Sanity checks for config module.
"""

from src.core import config


def test_config_constants():
    """Ensure critical constants are set."""
    assert config.COL_NAME
    assert config.COL_SCORE
    assert config.COL_GROUP
    assert config.OUTPUT_FILENAME.endswith(".xlsx")
    assert isinstance(config.SOLVER_TIMEOUT, int)
