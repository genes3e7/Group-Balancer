"""Additional tests to bump coverage for missing branches."""

from unittest.mock import MagicMock, patch

import pandas as pd

from src.core import config, data_loader, solver_interface
from src.core.models import ConflictPriority
from src.ui import steps


class DummySessionState(dict):
    """Mock session state."""

    def __getattr__(self, key: str) -> object:
        return self[key]

    def __setattr__(self, key: str, value: object) -> None:
        self[key] = value


def test_data_loader_process_service_unsupported() -> None:
    """Cover unsupported file format log."""
    with patch("src.core.data_loader.logger.error") as mock_log:
        res = data_loader._read_raw_file("test.txt")
        assert res is None
        assert mock_log.called


def test_data_loader_read_raw_xls(tmp_path) -> None:
    """Cover old Excel format branch."""
    f = tmp_path / "test.xls"
    f.touch()
    with patch("pandas.read_excel", return_value=pd.DataFrame()):
        data_loader._read_raw_file(str(f))


def test_data_loader_process_data_limit() -> None:
    """Cover participant limit log."""
    df = pd.DataFrame({"A": range(config.MAX_PARTICIPANTS + 1)})
    with patch("src.core.data_loader.logger.error") as mock_log:
        res = data_loader._process_data_service(df, "test.csv")
        assert res is None
        assert mock_log.called


def test_solver_interface_success_render_with_box() -> None:
    """Cover _render_success_status success path."""
    mock_inst = MagicMock()
    mock_inst.ObjectiveValue.return_value = 100
    mock_box = MagicMock()
    mock_box.__enter__ = MagicMock(return_value=mock_box)
    mock_box.__exit__ = MagicMock(return_value=None)

    with patch("streamlit.status") as mock_st:
        mock_st.return_value.__enter__.return_value = MagicMock()
        solver_interface._render_success_status(mock_box, "OPTIMAL", 1.0, mock_inst, 10)


def test_solver_interface_error_msg_default() -> None:
    """Cover _get_solver_error_msg default branch."""
    # Use 0 (UNKNOWN) to trigger the default branch
    msg = solver_interface._get_solver_error_msg(0, "UNKNOWN")
    assert "status: UNKNOWN" in msg


def test_steps_resolve_best_hints_hit_interactive() -> None:
    """Cover _resolve_best_hints hit on interactive_df."""
    df = pd.DataFrame({"Name": ["P1"], "S1": [10]})
    res = pd.DataFrame({"Name": ["P1"], "S1": [10], "Group": [1]})
    res.attrs = {
        "group_capacities": [1],
        "score_weights": {"S1": 1.0},
        "conflict_priority": ConflictPriority.GROUPERS,
    }

    mock_state = DummySessionState(
        {"interactive_df": res.copy(), "results_df": res.copy(), "warm_start_cache": {}}
    )

    with patch("streamlit.session_state", mock_state):
        key = steps._generate_cache_key(df, [1], {"S1": 1.0}, ConflictPriority.GROUPERS)
        out = steps._resolve_best_hints(df, key, ConflictPriority.GROUPERS)
        assert out is not None
        assert out.iloc[0]["Group"] == 1


def test_steps_handle_optimization_result_success() -> None:
    """Cover success branch of _handle_optimization_result."""
    res = pd.DataFrame({"Name": ["P1"], "Group": [1]})
    mock_state = DummySessionState({"warm_start_cache": {}})
    with (
        patch("src.ui.session_manager.go_to_step") as mock_go,
        patch("streamlit.session_state", mock_state),
        patch("time.sleep"),
    ):
        steps._handle_optimization_result(
            res, {"status": "OPTIMAL", "elapsed": 1.0}, "key"
        )
        assert mock_go.called
        assert "key" in mock_state.warm_start_cache
