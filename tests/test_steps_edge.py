from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.core import config
from src.ui import steps


def test_load_uploaded_file_missing_cols():
    """Cover steps.py line 39."""
    mock_file = MagicMock()
    mock_file.name = "test.csv"
    bad_df = pd.DataFrame({"Wrong": [1]})
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state.u_file = mock_file
        with patch("pandas.read_csv", return_value=bad_df):
            steps._load_uploaded_file()
            mock_st.error.assert_called_with(
                "File missing required columns: Name and Score*"
            )


def test_render_step_1_error_missing_scores():
    """Cover steps.py line 106."""
    df = pd.DataFrame({"Name": ["A"]})
    mock_state = MagicMock()
    mock_state.manual_df = df
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.button.side_effect = [False, True]  # AddScore=False, Next=True
        mock_st.data_editor.return_value = df
        steps.render_step_1()
        mock_st.error.assert_called_with("At least one score column is required.")


def test_render_step_2_no_data_stop():
    """Cover steps.py line 134."""
    mock_state = MagicMock()
    mock_state.get.return_value = None
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.button.return_value = False
        mock_st.stop.side_effect = RuntimeError("stop")
        with pytest.raises(RuntimeError, match="stop"):
            steps.render_step_2()
        mock_st.warning.assert_called_with("No data found.")


def test_render_step_2_solver_fail_metrics():
    """Cover steps.py lines 200-206."""
    mock_df = pd.DataFrame({"Name": ["P1"], "Score1": [10.0]})
    mock_state = MagicMock()
    mock_state.get.side_effect = lambda k, d=None: {
        "participants_df": mock_df,
        "score_cols": ["Score1"],
    }.get(k, d)
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.button.side_effect = [False, True]  # Back=False, Generate=True
        mock_st.number_input.return_value = 1

        c1, c2 = MagicMock(), MagicMock()
        g1 = MagicMock()
        cb, cg = MagicMock(), MagicMock()
        # side_effect for st.columns calls: 2, 1, [1,5]
        mock_st.columns.side_effect = [[c1, c2], [g1], [cb, cg]]

        mock_st.radio.side_effect = ["advanced", "groupers"]
        mock_st.slider.return_value = 10
        with patch(
            "src.ui.steps.OptimizationService.run",
            return_value=(
                None,
                {"status": "INFEASIBLE", "elapsed": 0.1, "error": "No solution"},
            ),
        ):
            steps.render_step_2()
            assert mock_state.results_df is None
            assert mock_state.solver_error == "No solution"


def test_footer_reset_direct():
    """Cover steps.py line 253."""
    df_orig = pd.DataFrame({"Name": ["P1"], config.COL_GROUP: [1], "S1": [10.0]})
    mock_state = MagicMock()
    mock_state.results_df = df_orig
    with patch("src.ui.steps.st") as mock_st:
        mock_st.session_state = mock_state
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        # Reset button is index 1
        mock_st.columns.return_value[1].button.return_value = True
        mock_st.columns.return_value[0].button.return_value = False
        with patch("pandas.DataFrame.copy", return_value=df_orig.copy()):
            steps._render_footer_actions(["S1"])
            mock_st.rerun.assert_called()


def test_render_table_view_nan_std_direct():
    """Cover steps.py lines 292-293."""
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
