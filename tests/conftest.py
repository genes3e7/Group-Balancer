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

    # Identity decorator to ensure Streamlit decorators don't block execution
    def identity_decorator(
        *args: object, **_kwargs: object
    ) -> Callable[..., Any] | Callable[[Callable[..., Any]], Callable[..., Any]]:
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return lambda func: func

    # Create a strict fail-fast stub for streamlit if it's not installed
    try:
        import streamlit as st
    except ModuleNotFoundError:
        st = MagicMock(name="streamlit")
        sys.modules["streamlit"] = st

    # Inject identity decorators to prevent collection-time execution blocks
    st.fragment = identity_decorator
    st.cache_data = identity_decorator

    # Ensure session_state exists as a reachable stub
    try:
        from unittest.mock import Mock

        # Reaching for the attribute on a MagicMock might return another mock,
        # so we use getattr with a sentinel and check for Mock types.
        sentinel = object()
        val = getattr(st, "session_state", sentinel)
        if val is sentinel or isinstance(val, Mock):
            st.session_state = DummySessionState()
    except (AttributeError, ImportError):
        st.session_state = DummySessionState()


@pytest.fixture(autouse=True)
def mock_streamlit_fragment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redundant safety fixture for per-test isolation if needed."""

    # Identity decorators using MagicMock to preserve decorator signatures
    def identity(func_or_val: object = None, **_kwargs: object) -> Any:
        if callable(func_or_val):
            return func_or_val
        return lambda f: f

    monkeypatch.setattr("streamlit.fragment", identity)
    monkeypatch.setattr("streamlit.cache_data", identity)


@pytest.fixture
def mock_streamlit_columns() -> Callable[[int | Iterable], list[MagicMock]]:
    """Provides a factory for mocking st.columns with number_input mocks."""

    def _factory(n: int | Iterable, **_kwargs: object) -> list[MagicMock]:
        count = n if isinstance(n, int) else len(list(n))
        mocks = []
        for _ in range(count):
            m = MagicMock()
            m.number_input.return_value = 1.0
            m.button.return_value = False
            mocks.append(m)
        return mocks

    return _factory
