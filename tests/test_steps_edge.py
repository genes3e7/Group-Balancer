"""Edge case tests for UI steps.

Verifies that the multi-step navigation, file processing, and solver
integration handle missing data, invalid inputs, and execution failures
gracefully.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.core import config
from src.ui import steps


def test_load_uploaded_file_missing_cols():
    """Verify error message when uploaded file is missing required columns."""
    mock_file = MagicMock()
    mock_file.name = "test.csv"
    bad_df = pd.DataFrame({"Wrong": [1]})
    with patch("src.ui.steps.st") as mock_st:
        with patch("pandas.read_csv", return_value=bad_df):
            success, sig = steps._process_uploaded_file(mock_file)
            assert not success
            mock_st.error.assert_called_with(
                "File missing required columns: Name and Score*"
            )


def test_render_step_1_error_missing_scores():
    """Verify error when navigating from Step 1 without score columns."""
    df = pd.DataFrame({"Name": ["A"]})
    mock_state = MagicMock()
    mock_state.manual_df = df
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.button.side_effect = lambda label, **kwargs: label == "Next: Configure"
        mock_st.data_editor.return_value = df
        steps.render_step_1()
        mock_st.error.assert_called_with("At least one score column is required.")


def test_render_step_2_no_data_back_navigation():
    """Verify that Step 2 Back button works when no data is found."""
    mock_state = MagicMock()
    mock_state.get.return_value = None
    with patch("src.ui.steps.st") as mock_st:
        mock_state.manual_df = pd.DataFrame()
        mock_st.session_state = mock_state
        mock_st.button.side_effect = lambda label, **kwargs: label == "⬅ Back"
        mock_st.stop.side_effect = RuntimeError("stop")
        with patch("src.ui.session_manager.go_to_step") as mock_go:
            with pytest.raises(RuntimeError, match="stop"):
                steps.render_step_2()
            mock_go.assert_called_with(1)


def test_render_step_2_solver_fail_metrics():
    """Verify that solver failure metrics are correctly surfaced in UI state."""
    mock_df = pd.DataFrame({config.COL_NAME: ["P1"], "Score1": [10.0]})
    mock_state = MagicMock()
    mock_state.warm_start_cache = {}
    mock_state.get.side_effect = lambda k, d=None: {
        "participants_df": mock_df,
        "score_cols": ["Score1"],
        "warm_start_cache": {},
    }.get(k, d)

    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.button.side_effect = lambda label, **kwargs: label == "🚀 Generate"
        mock_st.number_input.return_value = 1
        mock_st.radio.return_value = "groupers"
        mock_st.slider.return_value = 10
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        mock_st.empty.return_value = MagicMock()

        with patch(
            "src.ui.steps.OptimizationService.run",
            return_value=(
                None,
                {"status": "INFEASIBLE", "elapsed": 0.1, "error": "No solution"},
            ),
        ):
            with patch("src.ui.session_manager.go_to_step"):
                steps.render_step_2()
                assert mock_state.results_df is None
                assert mock_state.solver_error == "No solution"


def test_footer_reset_direct():
    """Verify that 'Start Over' performs a selective reset.

    Ensures project data is cleared but the warm_start_cache is preserved.
    """
    df_orig = pd.DataFrame({"Name": ["P1"], config.COL_GROUP: [1], "S1": [10.0]})
    mock_state = MagicMock()
    # Simulate existing state
    mock_state.keys.return_value = ["participants_df", "warm_start_cache"]
    mock_state.interactive_df = df_orig

    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.button.side_effect = lambda label, **kwargs: label == "🔄 Start Over"

        with patch("src.ui.steps._build_excel_bytes", return_value=b"bytes"):
            steps._render_footer_actions(["S1"])

        # Should NOT call clear()
        assert not mock_state.clear.called
        # Should call __delitem__ for everything except cache
        mock_state.__delitem__.assert_called_with("participants_df")
        mock_st.rerun.assert_called_once()


def test_render_table_view_nan_std_direct():
    """Verify table view handles standard deviation calculation edge cases."""
    df = pd.DataFrame({config.COL_NAME: ["P1"], config.COL_GROUP: [1], "S1": [10.0]})
    mock_state = MagicMock()
    mock_state.interactive_df = df
    mock_state.get.side_effect = lambda k, d=None: {"num_groups_target": 1}.get(k, d)
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        mock_st.data_editor.return_value = df
        steps._render_table_view(["S1"])
        mock_st.metric.assert_any_call("S1 Std Dev", "0.0000")


def test_steps_process_file_errors():
    """Verify error handling for invalid file reads."""
    mock_file = MagicMock()
    mock_file.name = "test.xlsx"
    with patch("src.ui.steps.st") as mock_st:
        # 1. Excel read fail
        with patch("pandas.read_excel", side_effect=Exception("Read fail")):
            success, sig = steps._process_uploaded_file(mock_file)
            assert not success
            mock_st.error.assert_called_with("Error reading file: Read fail")

        # 2. CSV missing columns
        mock_file.name = "test.csv"
        with patch("pandas.read_csv", return_value=pd.DataFrame({"Wrong": [1]})):
            success, sig = steps._process_uploaded_file(mock_file)
            assert not success
            mock_st.error.assert_called_with(
                "File missing required columns: Name and Score*"
            )


def test_render_step_1_empty_warning():
    """Verify warning when attempting to proceed from Step 1 with empty data."""
    with patch("src.ui.steps.st") as mock_st:
        mock_st.button.side_effect = lambda label, **kwargs: label == "Next: Configure"
        mock_st.data_editor.return_value = None
        steps.render_step_1()
        mock_st.warning.assert_called_with("Please add participants.")


def test_render_step_2_capacity_mismatch():
    """Verify error reporting for group capacity mismatches."""
    df = pd.DataFrame({config.COL_NAME: ["P1"], "S1": [10]})
    mock_state = MagicMock()
    mock_state.get.side_effect = lambda k, d=None: {
        "participants_df": df,
        "score_cols": ["S1"],
    }.get(k, d)

    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.number_input.return_value = 1
        mock_st.radio.return_value = "groupers"

        # Mock columns for capacities loop
        mock_col = MagicMock()
        mock_col.number_input.return_value = 5  # Total P is 1, Cap is 5
        mock_st.columns.side_effect = [
            [MagicMock(), MagicMock()],  # Groups input
            [mock_col],  # Capacities loop
            [MagicMock(), MagicMock()],  # Solver controls
        ]

        steps.render_step_2()
        mock_st.error.assert_any_call("Capacity mismatch: 5 != 1")


def test_render_step_3_status_messages():
    """Verify various solver status messages in Step 3."""
    mock_state = MagicMock()

    # 1. OPTIMAL status
    mock_state.get.side_effect = lambda k, d=None: {
        "solver_status": "OPTIMAL",
        "solver_elapsed": 1.5,
        "interactive_df": pd.DataFrame({"A": [1]}),
    }.get(k, d)
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.button.return_value = False
        with patch("src.ui.steps._render_table_view"):
            with patch("src.ui.steps._render_footer_actions"):
                steps.render_step_3()
                mock_st.success.assert_called()

    # 2. Other status (e.g., TIMEOUT)
    mock_state.get.side_effect = lambda k, d=None: {
        "solver_status": "TIMEOUT",
        "solver_elapsed": 10.0,
        "interactive_df": pd.DataFrame({"A": [1]}),
    }.get(k, d)
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.button.return_value = False
        with patch("src.ui.steps._render_table_view"):
            with patch("src.ui.steps._render_footer_actions"):
                steps.render_step_3()
                mock_st.warning.assert_any_call(
                    "⏳ Solver stopped in 10.00s (Status: TIMEOUT)"
                )


def test_render_step_3_no_results_ui():
    """Target the 'No results found' error path in Step 3."""
    mock_state = MagicMock()
    mock_state.get.side_effect = lambda k, d=None: {
        "solver_status": "FAIL",
        "interactive_df": None,
    }.get(k, d)
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        steps.render_step_3()
        mock_st.error.assert_any_call("No results found.")


def test_table_view_edit_rerun_direct():
    """Verify that editing the table view triggers a rerun."""
    df1 = pd.DataFrame({"Name": ["A"], "Group": [1]})
    df2 = pd.DataFrame({"Name": ["A"], "Group": [2]})
    mock_state = MagicMock()
    mock_state.interactive_df = df1
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        mock_st.data_editor.return_value = df2
        steps._render_table_view([])
        mock_st.rerun.assert_called_once()


def test_render_step_3_error_tips():
    """Verify that solver error messages and tips are displayed in Step 3."""
    mock_state = MagicMock()
    mock_state.get.side_effect = lambda k, d=None: {
        "solver_status": "FAIL",
        "solver_error": "Constraint Conflict",
    }.get(k, d)
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        steps.render_step_3()
        mock_st.error.assert_called_with("❌ Constraint Conflict")
        mock_st.info.assert_called()


def test_add_score_column_clash_logic():
    """Verify that Add Score Column handles existing names correctly."""
    df = pd.DataFrame({"Name": ["A"], "Score1": [1.0], "Score2": [2.0]})
    mock_state = MagicMock()
    mock_state.manual_df = df
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.button.side_effect = lambda label, **kwargs: (
            label == "➕ Add Score Column"
        )
        steps.render_step_1()
        assert "Score3" in mock_state.manual_df.columns
