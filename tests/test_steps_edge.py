"""Edge case tests for UI steps.

Verifies that the multi-step navigation, file processing, and solver
integration handle missing data, invalid inputs, and execution failures
gracefully.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.core import config
from src.core.models import ConflictPriority
from src.ui import steps
from tests.conftest import DummySessionState


def test_load_uploaded_file_missing_cols() -> None:
    """Verify error message when uploaded file is missing required columns."""
    mock_file = MagicMock()
    mock_file.name = "test.csv"
    bad_df = pd.DataFrame({"Wrong": [1]})
    with (
        patch("src.ui.steps.st") as mock_st,
        patch("pandas.read_csv", return_value=bad_df),
    ):
        success, _ = steps._process_uploaded_file(mock_file)
        assert not success
        mock_st.error.assert_called_with(
            "File missing required columns: Name and Score*"
        )


def test_process_uploaded_file_excel_read_failure() -> None:
    """Verify error reporting for invalid Excel file reads."""
    mock_file = MagicMock()
    mock_file.name = "test.xlsx"
    with (
        patch("src.ui.steps.st") as mock_st,
        patch("pandas.read_excel", side_effect=pd.errors.ParserError("Read fail")),
    ):
        success, _ = steps._process_uploaded_file(mock_file)
        assert not success
        mock_st.error.assert_called_with("Error reading file: Read fail")


def test_process_uploaded_file_csv_missing_columns() -> None:
    """Verify error reporting for CSV files with missing required columns."""
    mock_file = MagicMock()
    mock_file.name = "test.csv"
    with (
        patch("src.ui.steps.st") as mock_st,
        patch("pandas.read_csv", return_value=pd.DataFrame({"Wrong": [1]})),
    ):
        success, _ = steps._process_uploaded_file(mock_file)
        assert not success
        mock_st.error.assert_called_with(
            "File missing required columns: Name and Score*"
        )


def test_render_step_1_error_missing_scores() -> None:
    """Verify error when navigating from Step 1 without score columns."""
    df = pd.DataFrame({"Name": ["A"]})
    mock_state = MagicMock()
    mock_state.manual_df = df
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.file_uploader.return_value = None
        mock_st.button.side_effect = lambda label, **_: label == "Next: Configure"
        mock_st.data_editor.return_value = df
        steps.render_step_1()
        mock_st.error.assert_called_with("At least one score column is required.")


def test_render_step_2_no_data_back_navigation() -> None:
    """Verify that Step 2 Back button works when no data is found."""
    mock_state = MagicMock()
    mock_state.get.return_value = None
    with (
        patch("src.ui.steps.st") as mock_st,
        patch("src.ui.session_manager.go_to_step") as mock_go,
    ):
        mock_state.manual_df = pd.DataFrame()
        mock_st.session_state = mock_state
        mock_st.button.side_effect = lambda label, **_: label == "⬅ Back"
        mock_st.stop.side_effect = RuntimeError("stop")
        with pytest.raises(RuntimeError, match="stop"):
            steps.render_step_2()
        mock_go.assert_called_with(1)


def test_render_step_2_solver_fail_metrics() -> None:
    """Verify that solver failure metrics are correctly surfaced in UI state.

    This test exercises the .get() access pattern for warm_start_cache.
    """
    mock_df = pd.DataFrame(
        {
            config.COL_NAME: ["P1"],
            "Score1": [10.0],
            "_original_index": [0],
            "participant_fingerprint": ["f"],
        }
    )
    mock_state = MagicMock()
    mock_state.get.side_effect = lambda k, d=None: {
        "participants_df": mock_df,
        "score_cols": ["Score1"],
        "warm_start_cache": {},
    }.get(k, d)

    with (
        patch("src.ui.steps.st") as mock_st,
        patch(
            "src.ui.steps.OptimizationService.run",
            return_value=(
                None,
                {"status": "INFEASIBLE", "elapsed": 0.1, "error": "No solution"},
            ),
        ),
    ):
        mock_st.session_state = mock_state
        mock_st.button.side_effect = lambda label, **_: label == "🚀 Generate"
        mock_st.number_input.return_value = 1
        mock_st.radio.return_value = "groupers"
        mock_st.slider.return_value = 10
        mock_st.columns.side_effect = lambda n, **_: (
            [MagicMock()] * (n if isinstance(n, int) else len(n))
        )
        mock_st.empty.return_value = MagicMock()

        with patch("src.ui.session_manager.go_to_step"):
            steps.render_step_2()
            assert mock_state.results_df is None
            assert mock_state.solver_error == "No solution"


def test_footer_reset_direct() -> None:
    """Verify that 'Start Over' performs a selective reset."""
    mock_df = pd.DataFrame({"A": [1]})
    session_dict = {"interactive_df": mock_df, "warm_start_cache": "cache"}
    mock_state = MagicMock()
    mock_state.__getitem__.side_effect = session_dict.__getitem__
    mock_state.__setitem__.side_effect = session_dict.__setitem__
    mock_state.__delitem__.side_effect = session_dict.__delitem__
    mock_state.keys.side_effect = session_dict.keys
    mock_state.interactive_df = mock_df

    with (
        patch("src.ui.steps.st") as mock_st,
        patch("src.ui.steps.pd.util.hash_pandas_object", return_value=pd.Series([1])),
        patch("src.ui.steps._build_excel_bytes", return_value=b"bytes"),
    ):
        mock_st.session_state = mock_state
        mock_st.button.side_effect = lambda label, **_: label == "🔄 Start Over"
        mock_st.columns.return_value = [MagicMock(), MagicMock()]

        steps._render_footer_actions(["S1"])

    assert "interactive_df" not in session_dict
    assert "warm_start_cache" in session_dict
    mock_st.rerun.assert_called_once()


def test_render_table_view_nan_std_direct() -> None:
    """Verify table view handles standard deviation calculation edge cases."""
    df = pd.DataFrame({config.COL_NAME: ["P1"], config.COL_GROUP: [1], "S1": [10.0]})
    mock_state = MagicMock()
    mock_state.interactive_df = df
    mock_state.get.side_effect = lambda k, d=None: {"num_groups_target": 1}.get(k, d)
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.columns.side_effect = lambda n, **_: (
            [MagicMock()] * (n if isinstance(n, int) else len(n))
        )
        mock_st.data_editor.return_value = df
        steps._render_table_view(["S1"])
        mock_st.metric.assert_any_call("S1 Std Dev", "0.0000")


def test_render_step_1_empty_warning() -> None:
    """Verify warning when attempting to proceed from Step 1 with empty data."""
    mock_state = MagicMock()
    mock_state.manual_df = pd.DataFrame()
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.file_uploader.return_value = None
        mock_st.button.side_effect = lambda label, **_: label == "Next: Configure"
        mock_st.data_editor.return_value = None
        steps.render_step_1()
        mock_st.warning.assert_called_with("Please add participants.")


def test_render_step_3_status_messages() -> None:
    """Verify various solver status messages in Step 3."""
    mock_state = MagicMock()

    mock_state.get.side_effect = lambda k, d=None: {
        "solver_status": "OPTIMAL",
        "solver_elapsed": 1.5,
        "interactive_df": pd.DataFrame({"A": [1]}),
    }.get(k, d)
    with (
        patch("src.ui.steps.st") as mock_st,
        patch("src.ui.steps._render_table_view"),
        patch("src.ui.steps._render_footer_actions"),
    ):
        mock_st.session_state = mock_state
        mock_st.button.return_value = False
        steps.render_step_3()
        mock_st.success.assert_called()

    mock_state.get.side_effect = lambda k, d=None: {
        "solver_status": "TIMEOUT",
        "solver_elapsed": 10.0,
        "interactive_df": pd.DataFrame({"A": [1]}),
    }.get(k, d)
    with (
        patch("src.ui.steps.st") as mock_st,
        patch("src.ui.steps._render_table_view"),
        patch("src.ui.steps._render_footer_actions"),
    ):
        mock_state.solver_status = "TIMEOUT"
        mock_st.session_state = mock_state
        mock_st.button.return_value = False
        steps.render_step_3()
        mock_st.warning.assert_any_call("⏳ Solver stopped in 10.00s (Status: TIMEOUT)")


def test_render_step_3_no_results_ui() -> None:
    """Target the 'No results found' error path in Step 3."""
    mock_state = MagicMock()
    mock_state.get.side_effect = lambda k, d=None: {
        "solver_status": "FAIL",
        "interactive_df": None,
    }.get(k, d)
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.button.return_value = False
        steps.render_step_3()
        mock_st.error.assert_any_call("No results found.")


def test_table_view_edit_rerun_direct() -> None:
    """Verify that editing the table view triggers a rerun."""
    df1 = pd.DataFrame({"Name": ["A"], "Group": [1]})
    df2 = pd.DataFrame({"Name": ["A"], "Group": [2]})
    mock_state = MagicMock()
    mock_state.interactive_df = df1
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.columns.side_effect = lambda n, **_: (
            [MagicMock()] * (n if isinstance(n, int) else len(n))
        )
        mock_st.data_editor.return_value = df2
        steps._render_table_view([])
        mock_st.rerun.assert_called_once()


def test_render_step_3_error_tips() -> None:
    """Verify that solver error messages and tips are displayed in Step 3."""
    mock_state = MagicMock()
    mock_state.get.side_effect = lambda k, d=None: {
        "solver_status": "FAIL",
        "solver_error": "Constraint Conflict",
    }.get(k, d)
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.button.return_value = False
        steps.render_step_3()
        mock_st.error.assert_called_with("❌ Constraint Conflict")
        mock_st.info.assert_called()


def test_process_uploaded_file_unexpected_exception() -> None:
    """Cover the generic exception branch in _process_uploaded_file."""
    mock_file = MagicMock()
    mock_file.name = "test.csv"
    with (
        patch("streamlit.session_state", DummySessionState()),
        patch("pandas.read_csv", side_effect=RuntimeError("System crash")),
        patch("streamlit.error") as mock_err,
    ):
        success, _ = steps._process_uploaded_file(mock_file)
        assert not success
        mock_err.assert_called_with(
            "Unexpected error reading file. Check logs for details."
        )


def test_render_step_2_warm_start_attribute_merging() -> None:
    """Verify that Step 2 correctly merges internal columns from results_df."""
    df = pd.DataFrame({"Name": ["P1"], "Score1": [10.0]})
    # interactive_df matches but lacks internal columns
    interactive_df = pd.DataFrame(
        {"Name": ["P1"], "Score1": [10.0], config.COL_GROUP: [1]}
    )

    # results_df has the internal columns
    results_df = pd.DataFrame(
        {
            "Name": ["P1"],
            "Score1": [10.0],
            config.COL_GROUP: [1],
            "_original_index": [0],
            "participant_fingerprint": ["fp1"],
        }
    )
    results_df.attrs = {
        "group_capacities": [1],
        "score_weights": {"Score1": 1.0},
        "conflict_priority": ConflictPriority.GROUPERS,
    }

    mock_state = DummySessionState(
        {
            "participants_df": df,
            "score_cols": ["Score1"],
            "warm_start_cache": {},
            "interactive_df": interactive_df,
            "results_df": results_df,
            "num_groups_target": 1,
        }
    )

    with (
        patch("streamlit.session_state", mock_state),
        patch(
            "src.core.services.OptimizationService.run",
            return_value=(results_df, {"status": "OPTIMAL", "elapsed": 0.1}),
        ) as mock_run,
        patch("src.ui.session_manager.go_to_step"),
        patch("streamlit.button", return_value=True),
        patch("streamlit.columns") as mock_cols,
        patch("streamlit.number_input", return_value=1.0),
        patch("streamlit.empty", return_value=MagicMock()),
    ):
        mock_cols.side_effect = [
            [MagicMock(), MagicMock()],
            [MagicMock()],
            [MagicMock(), MagicMock()],
        ]
        steps.render_step_2()
        # Verify that previous_results passed to run() has the merged columns
        prev_results = mock_run.call_args[1].get("previous_results")
        assert prev_results is not None
        assert "_original_index" in prev_results.columns
        assert prev_results.at[0, "participant_fingerprint"] == "fp1"


def test_add_score_column_clash_logic() -> None:
    """Verify that Add Score Column handles existing names correctly."""
    df = pd.DataFrame({"Name": ["A"], "Score1": [1.0], "Score2": [2.0]})
    mock_state = MagicMock()
    mock_state.manual_df = df
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.file_uploader.return_value = None
        mock_st.button.side_effect = lambda label, **_: label == "+ Add Score Column"
        steps.render_step_1()
        assert "Score3" in mock_state.manual_df.columns
