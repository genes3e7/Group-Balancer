"""Additional tests to boost coverage above 90%."""

from unittest.mock import MagicMock, patch

import pandas as pd

from src.core import config
from src.ui import results_renderer, steps


def test_results_renderer_reassignment():
    """Cover the group reassignment logic in results_renderer."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["P1"],
            config.COL_GROUP: [1],
            "Score1": [10.0],
            "_original_index": [0],
        }
    )
    group = {"id": 1, "averages": {"Score1": 10.0}, "members": df.to_dict("records")}

    mock_state = MagicMock()
    mock_state.interactive_df = df.copy()

    # Mock edited_df to have a different group
    edited_df = pd.DataFrame(
        {config.COL_GROUP: [2], config.COL_NAME: ["P1"], "Score1": [10.0]}
    )

    with (
        patch("streamlit.container"),
        patch("streamlit.markdown"),
        patch("streamlit.columns", return_value=[MagicMock(), MagicMock()]),
        patch("streamlit.data_editor", return_value=edited_df),
        patch("streamlit.expander"),
        patch("streamlit.metric"),
        patch("streamlit.session_state", mock_state),
        patch("streamlit.rerun") as mock_rerun,
    ):
        results_renderer._render_single_card(group, ["Score1"])
        assert mock_state.interactive_df.at[0, config.COL_GROUP] == 2
        mock_rerun.assert_called_once()


def test_steps_render_2_solver_failure_surface():
    """Cover the failure branch in render_step_2 when result_df is None."""
    mock_df = pd.DataFrame({"Name": ["P1"], "Score1": [10.0]})
    mock_state = MagicMock()
    mock_state.participants_df = mock_df
    mock_state.get.side_effect = lambda key, default=None: {
        "participants_df": mock_df,
        "score_cols": ["Score1"],
    }.get(key, default)

    with (
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.columns") as mock_cols,
        patch("streamlit.number_input", return_value=1),
        patch("streamlit.radio", side_effect=["advanced", "groupers"]),
        patch("streamlit.slider", return_value=10),
        patch("streamlit.button", side_effect=[False, True]),  # Back/Gen
        patch("streamlit.expander"),
        patch("streamlit.empty"),
        patch("src.core.services.OptimizationService.run") as mock_run,
        patch("src.ui.session_manager.go_to_step") as mock_go,
        patch("streamlit.session_state", mock_state),
    ):
        mock_run.return_value = (
            None,
            {"status": "INFEASIBLE", "elapsed": 0.5, "error": "No solution"},
        )

        c1, c2 = MagicMock(), MagicMock()
        g_col = MagicMock()
        c_back, c_go = MagicMock(), MagicMock()
        c_back.button.return_value = False
        c_go.button.return_value = True

        mock_cols.side_effect = [
            [c1, c2],  # st.columns(2)
            [g_col],  # st.columns(num_groups)
            [c_back, c_go],  # st.columns([1, 5])
        ]

        steps.render_step_2()

        assert mock_state.results_df is None
        assert mock_state.solver_error == "No solution"
        mock_go.assert_called_with(3)
