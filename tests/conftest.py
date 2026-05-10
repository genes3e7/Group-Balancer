import pytest


@pytest.fixture(autouse=True)
def mock_streamlit_fragment(monkeypatch):
    """Globally bypass st.fragment decorator for coverage.

    Ensures decorated functions are counted in functional coverage reports.
    """

    def identity(func):
        return func

    monkeypatch.setattr("streamlit.fragment", identity)
