"""Global pytest configuration and project-wide fixtures."""

import pytest


class DummySessionState(dict):
    """Mock session state that supports both dict and attribute access."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as err:
            raise AttributeError(key) from err

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError as err:
            raise AttributeError(key) from err


def pytest_configure(config):
    """Hooks into pytest startup to patch module-level decorators.

    Replaces @st.fragment with an identity decorator before any modules are
    imported by the test collection process.
    """
    import sys
    from unittest.mock import MagicMock

    # Identity decorator to ensure st.fragment doesn't block execution
    def identity_decorator(func):
        return func

    # Create a mock streamlit module if it doesn't exist, or patch the existing one
    if "streamlit" not in sys.modules:
        mock_st = MagicMock()
        mock_st.fragment = identity_decorator
        sys.modules["streamlit"] = mock_st
    else:
        import streamlit as st

        st.fragment = identity_decorator


@pytest.fixture(autouse=True)
def mock_streamlit_fragment(monkeypatch):
    """Redundant safety fixture for per-test isolation if needed."""

    def identity(func):
        return func

    monkeypatch.setattr("streamlit.fragment", identity)
