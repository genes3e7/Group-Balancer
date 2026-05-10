"""Global pytest configuration and project-wide fixtures."""

from unittest.mock import MagicMock

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

    Replaces @st.fragment and @st.cache_data with identity decorators before
    any modules are imported by the test collection process.
    """
    import sys

    # Identity decorator to ensure Streamlit decorators don't block execution
    def identity_decorator(*args, **kwargs):
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return lambda func: func

    # Create a permissive but pre-configured stub for streamlit
    if "streamlit" not in sys.modules:
        mock_st = MagicMock()
        mock_st.fragment = identity_decorator
        mock_st.cache_data = identity_decorator
        mock_st.session_state = DummySessionState()
        sys.modules["streamlit"] = mock_st
    else:
        import streamlit as st

        st.fragment = identity_decorator
        st.cache_data = identity_decorator
        if not hasattr(st, "session_state"):
            st.session_state = DummySessionState()


@pytest.fixture(autouse=True)
def mock_streamlit_fragment(monkeypatch):
    """Redundant safety fixture for per-test isolation if needed."""

    def identity(func):
        return func

    monkeypatch.setattr("streamlit.fragment", identity)


@pytest.fixture
def mock_streamlit_columns():
    """Provides a factory for mocking st.columns with number_input mocks."""

    def _factory(n: int | list, **_):
        m = MagicMock()
        m.number_input.return_value = 1.0
        m.button.return_value = False
        count = n if isinstance(n, int) else len(n)
        return [m] * count

    return _factory
