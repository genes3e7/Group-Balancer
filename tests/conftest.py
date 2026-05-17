"""Global pytest configuration and project-wide fixtures."""

import sys
from collections.abc import Callable, Iterable
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest


class DummySessionState(dict):
    """Mock session state that supports both dict and attribute access."""

    def __getattr__(self, key: str) -> object:
        """Allow attribute access to dict keys."""
        try:
            return self[key]
        except KeyError as err:
            raise AttributeError(key) from err

    def __setattr__(self, key: str, value: object) -> None:
        """Allow attribute setting to dict keys."""
        self[key] = value

    def __delattr__(self, key: str) -> None:
        """Allow attribute deletion from dict keys."""
        try:
            del self[key]
        except KeyError as err:
            raise AttributeError(key) from err


def pytest_configure(config: "pytest.Config") -> None:  # noqa: ARG001
    """Hooks into pytest startup to patch module-level decorators.

    Replaces @st.fragment and @st.cache_data with identity decorators before
    any modules are imported by the test collection process.
    """
    # 1. Ensure Streamlit is mocked/stubbed before any imports
    try:
        import streamlit as st
    except (ImportError, AttributeError):
        st = MagicMock(name="streamlit")
        sys.modules["streamlit"] = st

    # 2. Aggressively patch all rendering methods to prevent internal Streamlit errors
    # This prevents the "TypeError: bad argument type" in protobuf serialization.
    rendering_methods = [
        "info",
        "warning",
        "error",
        "success",
        "header",
        "subheader",
        "title",
        "markdown",
        "columns",
        "container",
        "empty",
        "metric",
        "expander",
        "data_editor",
        "download_button",
        "file_uploader",
        "write",
        "caption",
        "number_input",
        "radio",
        "slider",
        "status",
        "toast",
        "table",
        "dataframe",
        "divider",
        "rerun",
        "stop",
        "set_page_config",
    ]
    for method in rendering_methods:
        if not isinstance(getattr(st, method, None), MagicMock):
            m = MagicMock(name=f"st.{method}")
            # Ensure context managers work
            m.return_value.__enter__.return_value = m
            setattr(st, method, m)

    # 3. Identity decorator for fragments/cache
    def identity_decorator(
        *args: object, **_kwargs: object
    ) -> Callable[..., Any] | Callable[[Callable[..., Any]], Callable[..., Any]]:
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return lambda func: func

    st.fragment = identity_decorator
    st.cache_data = identity_decorator

    # 4. Ensure session_state exists as a reachable stub
    try:
        sentinel = object()
        val = getattr(st, "session_state", sentinel)
        if val is sentinel or isinstance(val, Mock):
            st.session_state = DummySessionState()
    except (AttributeError, ImportError):
        st.session_state = DummySessionState()


@pytest.fixture(autouse=True)
def mock_streamlit_fragment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redundant safety fixture for per-test isolation if needed."""

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
            m.__enter__ = MagicMock(return_value=m)
            m.__exit__ = MagicMock(return_value=None)
            mocks.append(m)
        return mocks

    return _factory
