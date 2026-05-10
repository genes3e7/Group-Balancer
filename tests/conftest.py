"""Global pytest configuration and project-wide fixtures."""

from collections.abc import Callable, Iterable
from typing import Any
from unittest.mock import MagicMock

import pytest


class DummySessionState(dict):
    """Mock session state that supports both dict and attribute access."""

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as err:
            raise AttributeError(key) from err

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value

    def __delattr__(self, key: str) -> None:
        try:
            del self[key]
        except KeyError as err:
            raise AttributeError(key) from err


def pytest_configure(config: Any) -> None:  # noqa: ARG001
    """Hooks into pytest startup to patch module-level decorators.

    Replaces @st.fragment and @st.cache_data with identity decorators before
    any modules are imported by the test collection process.
    """
    import sys
    import types

    # Identity decorator to ensure Streamlit decorators don't block execution
    def identity_decorator(*args: Any, **kwargs: Any) -> Callable[..., Any]:
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return lambda func: func

    # Create a strict fail-fast stub for streamlit if it's not installed
    try:
        import streamlit as st
    except ModuleNotFoundError:
        st = types.SimpleNamespace()
        sys.modules["streamlit"] = st

    # Inject identity decorators to prevent collection-time execution blocks
    st.fragment = identity_decorator
    st.cache_data = identity_decorator

    # Ensure session_state exists as a reachable stub
    if not hasattr(st, "session_state"):
        st.session_state = DummySessionState()


@pytest.fixture(autouse=True)
def mock_streamlit_fragment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redundant safety fixture for per-test isolation if needed."""

    def identity(func: Callable[..., Any]) -> Callable[..., Any]:
        return func

    monkeypatch.setattr("streamlit.fragment", identity)
    # Ensure cache_data is also protected and reset per test
    monkeypatch.setattr("streamlit.cache_data", identity)


@pytest.fixture
def mock_streamlit_columns() -> Callable[[int | Iterable], list[MagicMock]]:
    """Provides a factory for mocking st.columns with number_input mocks."""

    def _factory(n: int | Iterable, **_: Any) -> list[MagicMock]:
        m = MagicMock()
        m.number_input.return_value = 1.0
        m.button.return_value = False
        count = n if isinstance(n, int) else len(list(n))
        return [m] * count

    return _factory
