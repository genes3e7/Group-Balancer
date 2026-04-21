"""Unit tests/Sanity checks for config module."""

from src.core import config


def test_config_constants():
    """Verify that core constants are loaded."""
    assert config.SCORE_PREFIX == "Score"
    assert config.COL_NAME == "Name"
    assert config.SCALE_FACTOR == 100_000
