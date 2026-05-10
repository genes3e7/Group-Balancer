"""Unit tests for the UI layer (Mocked Streamlit)."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.core import config
from src.ui import components, results_renderer, session_manager, steps
from tests.conftest import DummySessionState


def test_session_manager_init():
    """Verify that session state is initialized correctly."""
    mock_state = DummySessionState()

    with patch("streamlit.session_state", mock_state):
        session_manager.init_session()
        assert mock_state.step == 1
        assert mock_state.manual_df is not None


def test_session_manager_navigation():
    """Verify that navigation logic clamps step values."""
    mock_state = DummySessionState({"step": 1})
    with (
        patch("streamlit.session_state", mock_state),
        patch("streamlit.rerun") as mock_rerun,
    ):
        session_manager.go_to_step(2)
        assert mock_state.step == 2
        mock_rerun.assert_called_once()

        session_manager.go_to_step(5)
        assert mock_state.step == 3


def test_components_setup():
    """Verify setup_page calls streamlit correctly."""
    with patch("streamlit.set_page_config") as mock_conf:
        components.setup_page()
        mock_conf.assert_called_once()


def test_components_header():
    """Verify page header components render without error."""
    with (
        patch("streamlit.markdown"),
        patch("streamlit.columns", return_value=[MagicMock()] * 3),
        patch("streamlit.expander"),
    ):
        # Description
        components.render_header_description()

        # Progress
        components.render_step_progress(1)


def test_results_renderer_empty():
    """Verify behavior with empty dataframe."""
    with patch("streamlit.warning") as mock_warn:
        results_renderer.render_group_cards(None, [])
        mock_warn.assert_called_once()

        results_renderer.render_group_cards(pd.DataFrame(), [])
        assert mock_warn.call_count == 2


def test_results_renderer_grid_branches():
    """Verify grid layout branches with multiple groups."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["P1", "P2", "P3"],
            config.COL_GROUP: [1, 2, 3],
            "Score1": [10, 20, 30],
        }
    )
    score_cols = ["Score1"]

    with (
        patch("streamlit.columns", return_value=[MagicMock()] * 3) as mock_cols,
        patch("src.ui.results_renderer._render_single_card"),
    ):
        results_renderer.render_group_cards(df, score_cols)
        assert mock_cols.called


def test_results_renderer_single_card_with_members(mock_streamlit_columns):
    """Verify card rendering with members and tags."""
    group = {
        "id": 1,
        "averages": {"Score1": 15.0},
        "members": [
            {
                config.COL_NAME: "A",
                config.COL_GROUP: 1,
                "Score1": 10,
                config.COL_GROUPER: "G",
                config.COL_SEPARATOR: "S",
            },
            {config.COL_NAME: "B", config.COL_GROUP: 1, "Score1": 20},
        ],
    }

    mock_state = DummySessionState({"num_groups_target": 2})

    with (
        patch("streamlit.container"),
        patch("streamlit.markdown"),
        patch("streamlit.columns", side_effect=mock_streamlit_columns),
        patch("streamlit.data_editor") as mock_editor,
        patch("streamlit.expander"),
        patch("streamlit.metric"),
        patch("streamlit.session_state", mock_state),
    ):

        def mock_data_editor(df, *args, **kwargs):
            return df

        mock_editor.side_effect = mock_data_editor

        results_renderer._render_single_card(group, ["Score1"])

        mock_editor.assert_called_once()
        df_arg = mock_editor.call_args[0][0]
        assert "Groupers" in df_arg.columns
        assert "Score1" in df_arg.columns
        assert "Group" in df_arg.columns


def test_steps_render_3_cards():
    """Verify Step 3 results view in Cards mode."""
    mock_df = pd.DataFrame({"Name": ["P1"], "Group": [1], "Score1": [10.0]})
    mock_state = DummySessionState(
        {
            "step": 3,
            "interactive_df": mock_df,
            "solver_status": "OPTIMAL",
            "solver_elapsed": 1.23,
            "score_cols": ["Score1"],
        }
    )

    with (
        patch("streamlit.header"),
        patch("streamlit.radio", return_value="Cards"),
        patch("streamlit.button"),
        patch("streamlit.divider"),
        patch("streamlit.success"),
        patch("src.ui.results_renderer.render_group_cards") as mock_cards,
        patch("src.ui.steps._render_footer_actions"),
        patch("streamlit.session_state", mock_state),
    ):
        steps.render_step_3()
        mock_cards.assert_called_once()


def test_components_header_branches():
    """Verify header branches (active/inactive) across all steps."""
    with (
        patch("streamlit.markdown"),
        patch("streamlit.columns", return_value=[MagicMock()] * 3),
        patch("streamlit.expander"),
    ):
        for s in [1, 2, 3]:
            components.render_step_progress(s)


def test_steps_render_footer_actions(mock_streamlit_columns):
    """Verify footer actions render correctly."""
    mock_df = pd.DataFrame({"Name": ["P1"], "Group": [1]})
    mock_state = DummySessionState({"interactive_df": mock_df})

    with (
        patch("streamlit.columns", side_effect=mock_streamlit_columns),
        patch("src.utils.exporter.generate_excel_bytes", return_value=b"bytes"),
        patch("streamlit.download_button") as mock_dl,
        patch("streamlit.button"),
        patch("streamlit.session_state", mock_state),
    ):
        steps._render_footer_actions(["Score1"])
        mock_dl.assert_called_once()


def test_steps_render_1():
    """Verify Step 1 renders correctly with data editor."""
    mock_state = DummySessionState({"manual_df": pd.DataFrame()})
    with (
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.expander"),
        patch("streamlit.file_uploader", return_value=None),
        patch("streamlit.button", return_value=False),
        patch("streamlit.data_editor") as mock_editor,
        patch("streamlit.session_state", mock_state),
    ):
        steps.render_step_1()
        assert mock_editor.call_count == 1


def test_steps_render_2(mock_streamlit_columns):
    """Verify Step 2 renders configuration elements."""
    mock_df = pd.DataFrame({"Name": ["P1"], "Score1": [10.0]})
    mock_state = DummySessionState(
        {
            "participants_df": mock_df,
            "score_cols": ["Score1"],
            "warm_start_cache": {},
            "interactive_df": mock_df,
        }
    )

    with (
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.columns", side_effect=mock_streamlit_columns),
        patch("streamlit.number_input", return_value=1.0),
        patch("streamlit.radio", return_value="groupers"),
        patch("streamlit.slider") as mock_slider,
        patch("streamlit.button", return_value=False),
        patch("streamlit.expander"),
        patch("streamlit.session_state", mock_state),
    ):
        mock_slider.return_value = 1
        steps.render_step_2()


def test_steps_load_uploaded_file_csv():
    """Verify file upload callback for CSV."""
    mock_file = MagicMock()
    mock_file.name = "test.csv"
    mock_file.size = 100
    mock_state = DummySessionState({"u_file": mock_file})
    mock_df = pd.DataFrame({config.COL_NAME: ["P1"], "Score1": [100.0]})

    with (
        patch("pandas.read_csv", return_value=mock_df) as mock_read,
        patch(
            "src.core.services.DataService.get_score_columns", return_value=["Score1"]
        ),
        patch(
            "src.core.services.DataService.clean_participants_df", return_value=mock_df
        ),
        patch("streamlit.session_state", mock_state),
        patch("streamlit.toast"),
    ):
        success, _ = steps._process_uploaded_file(mock_file)
        assert success
        mock_read.assert_called_once()


def test_steps_add_score_column():
    """Verify 'Add Score Column' button logic."""
    mock_df = pd.DataFrame({"Name": ["A"], "Score1": [1.0]})
    mock_state = DummySessionState({"manual_df": mock_df})

    with (
        patch("streamlit.button", return_value=True),
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.expander"),
        patch("streamlit.file_uploader", return_value=None),
        patch("streamlit.data_editor"),
        patch("streamlit.rerun") as mock_rerun,
        patch("streamlit.session_state", mock_state),
    ):
        steps.render_step_1()
        assert "Score2" in mock_state.manual_df.columns
        mock_rerun.assert_called_once()


def test_steps_render_1_failure_paths():
    """Verify Step 1 error messages for invalid data."""
    mock_state = DummySessionState({"manual_df": pd.DataFrame()})
    with (
        patch("src.ui.steps.st.header"),
        patch("src.ui.steps.st.subheader"),
        patch("src.ui.steps.st.expander"),
        patch("src.ui.steps.st.file_uploader", return_value=None),
        patch("src.ui.steps.st.button", side_effect=[False, True]),
        patch("src.ui.steps.st.data_editor", return_value=pd.DataFrame()),
        patch("src.ui.steps.st.warning") as mock_warn,
        patch("src.ui.steps.st.error") as mock_err,
        patch("src.ui.steps.st.session_state", mock_state),
    ):
        steps.render_step_1()
        mock_warn.assert_called_with("Please add participants.")

    with (
        patch("src.ui.steps.st.header"),
        patch("src.ui.steps.st.subheader"),
        patch("src.ui.steps.st.expander"),
        patch("src.ui.steps.st.file_uploader", return_value=None),
        patch("src.ui.steps.st.button", side_effect=[False, True]),
        patch(
            "src.ui.steps.st.data_editor", return_value=pd.DataFrame({"Name": ["A"]})
        ),
        patch("src.ui.steps.st.error") as mock_err,
        patch("src.ui.steps.st.session_state", mock_state),
    ):
        steps.render_step_1()
        mock_err.assert_called_with("At least one score column is required.")


def test_steps_render_2_navigation(mock_streamlit_columns):
    """Verify navigation buttons in Step 2."""
    mock_df = pd.DataFrame({"Name": ["P1"], "Score1": [10.0]})
    mock_state = DummySessionState(
        {
            "participants_df": mock_df,
            "score_cols": ["Score1"],
            "warm_start_cache": {},
        }
    )

    with (
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.columns", side_effect=mock_streamlit_columns),
        patch("streamlit.button"),
        patch("streamlit.number_input", return_value=1.0),
        patch("streamlit.radio", return_value="groupers"),
        patch("src.ui.session_manager.go_to_step") as mock_go,
        patch("streamlit.session_state", mock_state),
    ):
        # Correctly mock buttons to only return True for Back
        # by providing specific mocks for the 3rd st.columns call
        c_back, c_go = MagicMock(), MagicMock()
        c_back.button.return_value = True
        c_go.button.return_value = False

        mock_cols_v2 = MagicMock()
        mock_cols_v2.side_effect = [
            [MagicMock()] * 2,  # Groups
            [MagicMock()],  # Capacities
            [c_back, c_go],  # Navigation
        ]

        with patch("streamlit.columns", mock_cols_v2):
            steps.render_step_2()
            mock_go.assert_called_with(1)


def test_steps_render_1_success():
    """Verify Step 1 successful 'Next' navigation."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A"],
            "Score1": [10.0],
            config.COL_GROUPER: [""],
            config.COL_SEPARATOR: [""],
        }
    )
    mock_state = DummySessionState({"manual_df": df})

    with (
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.expander"),
        patch("streamlit.file_uploader", return_value=None),
        patch("streamlit.button") as mock_btn,
        patch("streamlit.data_editor", return_value=df),
        patch("src.ui.session_manager.go_to_step") as mock_go,
        patch("streamlit.session_state", mock_state),
    ):
        mock_btn.side_effect = lambda label, **kwargs: label == "Next: Configure"
        steps.render_step_1()
        mock_go.assert_called_with(2)


def test_steps_load_uploaded_file_excel():
    """Verify file upload callback for Excel."""
    mock_file = MagicMock()
    mock_file.name = "test.xlsx"
    mock_file.size = 100
    mock_state = DummySessionState({"u_file": mock_file})
    mock_df = pd.DataFrame({config.COL_NAME: ["P1"], "Score1": [100.0]})

    with (
        patch("pandas.read_excel", return_value=mock_df) as mock_read,
        patch(
            "src.core.services.DataService.get_score_columns", return_value=["Score1"]
        ),
        patch(
            "src.core.services.DataService.clean_participants_df", return_value=mock_df
        ),
        patch("streamlit.session_state", mock_state),
        patch("streamlit.toast"),
    ):
        success, _ = steps._process_uploaded_file(mock_file)
        assert success
        mock_read.assert_called_once()


def test_steps_load_uploaded_file_none():
    """Verify file upload callback with no file."""
    with (
        patch("streamlit.session_state", MagicMock()),
        patch("streamlit.error") as mock_err,
    ):
        success, _ = steps._process_uploaded_file(None)
        assert not success
        mock_err.assert_not_called()


def test_steps_start_over():
    """Verify 'Start Over' button logic performs selective reset."""
    mock_df = pd.DataFrame({"A": [1]})
    session_state = DummySessionState(
        {
            "step": 3,
            "solver_status": "OPTIMAL",
            "interactive_df": mock_df,
            "warm_start_cache": "preserved",
        }
    )

    with (
        patch("streamlit.button", return_value=True),
        patch("streamlit.download_button"),
        patch("src.ui.steps._build_excel_bytes", return_value=b"bytes"),
        patch("streamlit.rerun") as mock_rerun,
        patch("streamlit.session_state", session_state),
    ):
        # Create a combined mock for dot/bracket access
        mock_state = MagicMock()
        mock_state.__getitem__.side_effect = session_state.__getitem__
        mock_state.__setitem__.side_effect = session_state.__setitem__
        mock_state.__delitem__.side_effect = session_state.__delitem__
        mock_state.keys.side_effect = session_state.keys
        mock_state.interactive_df = session_state["interactive_df"]

        with patch("src.ui.steps.st.session_state", mock_state):
            steps._render_footer_actions(["Score1"])

        assert "solver_status" not in session_state
        assert "warm_start_cache" in session_state
        mock_rerun.assert_called_once()


def test_steps_render_2_clamped_groups(mock_streamlit_columns):
    """Verify that groups are correctly clamped to participant count."""
    mock_df = pd.DataFrame({"Name": ["P1"], "Score1": [10.0]})
    mock_state = DummySessionState(
        {
            "participants_df": mock_df,
            "score_cols": ["Score1"],
            "warm_start_cache": {},
        }
    )

    with (
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.columns", side_effect=mock_streamlit_columns),
        patch("streamlit.number_input", return_value=1.0),
        patch("streamlit.radio", return_value="groupers"),
        patch("streamlit.slider"),
        patch("streamlit.button", return_value=False),
        patch("streamlit.expander"),
        patch("streamlit.session_state", mock_state),
    ):
        steps.render_step_2()


def test_ui_steps_load_uploaded_file_exception():
    """Cover the exception branches in _process_uploaded_file."""
    mock_file = MagicMock()
    mock_file.name = "test.csv"
    with patch("streamlit.session_state", DummySessionState()):
        with patch("pandas.read_csv", side_effect=pd.errors.ParserError("Read error")):
            with patch("streamlit.error") as mock_err:
                success, _ = steps._process_uploaded_file(mock_file)
                assert not success
                mock_err.assert_called_with("Error reading file: Read error")


def test_render_step_2_initialization_fail():
    """Cover render_step_2 initialization fail branch."""
    mock_state = DummySessionState({"participants_df": None})

    class StopError(Exception):
        pass

    with (
        patch("streamlit.session_state", mock_state),
        patch("streamlit.warning"),
        patch("streamlit.button", return_value=False),
        patch("streamlit.stop", side_effect=StopError),
    ):
        with pytest.raises(StopError):
            steps.render_step_2()


def test_render_table_view_nan_std(mock_streamlit_columns):
    """Cover lines in steps.py where std_val might be NaN."""
    df = pd.DataFrame({config.COL_NAME: ["P1"], config.COL_GROUP: [1], "S1": [10.0]})
    mock_state = DummySessionState(
        {
            "interactive_df": df,
            "num_groups_target": 1,
        }
    )

    with (
        patch("streamlit.columns", side_effect=mock_streamlit_columns),
        patch("streamlit.subheader"),
        patch("streamlit.data_editor", return_value=df),
        patch("streamlit.metric"),
        patch("streamlit.dataframe"),
        patch("streamlit.session_state", mock_state),
    ):
        steps._render_table_view(["S1"])


def test_render_footer_reset_hit_proper_mock(mock_streamlit_columns):
    """Verify reset logic via 'Start Over' button."""
    df_orig = pd.DataFrame({"Name": ["P1"], config.COL_GROUP: [1], "S1": [10.0]})

    session_state = DummySessionState(
        {
            "interactive_df": df_orig,
            "warm_start_cache": "preserved",
        }
    )

    with patch("pandas.DataFrame.copy", return_value=df_orig.copy()):
        with (
            patch("src.ui.steps.st") as mock_st_in_steps,
            patch("src.ui.steps._build_excel_bytes", return_value=b"bytes"),
            patch(
                "src.ui.steps.pd.util.hash_pandas_object",
                return_value=pd.Series([1]),
            ),
        ):
            mock_state = MagicMock()
            mock_state.__getitem__.side_effect = session_state.__getitem__
            mock_state.__setitem__.side_effect = session_state.__setitem__
            mock_state.__delitem__.side_effect = session_state.__delitem__
            mock_state.keys.side_effect = session_state.keys
            mock_state.interactive_df = session_state["interactive_df"]

            mock_st_in_steps.session_state = mock_state

            # Setup columns with button factory
            m_back, m_reset = MagicMock(), MagicMock()
            m_back.button.return_value = False
            m_reset.button.return_value = True
            mock_st_in_steps.columns.return_value = [m_back, m_reset]

            steps._render_footer_actions(["S1"])
            mock_st_in_steps.rerun.assert_called()
            assert "interactive_df" not in session_state
            assert "warm_start_cache" in session_state


def test_steps_render_2_solver_failure_surface(mock_streamlit_columns):
    """Cover the failure branch in render_step_2 when result_df is None."""
    mock_df = pd.DataFrame(
        {
            config.COL_NAME: ["P1"],
            "Score1": [10.0],
            "_original_index": [0],
            "participant_fingerprint": ["f"],
        }
    )
    mock_state = DummySessionState(
        {
            "participants_df": mock_df,
            "score_cols": ["Score1"],
            "warm_start_cache": {},
            "interactive_df": mock_df,
        }
    )

    with (
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.columns", side_effect=mock_streamlit_columns),
        patch("streamlit.number_input", return_value=1.0),
        patch("streamlit.radio", return_value="groupers"),
        patch("streamlit.slider", return_value=10),
        patch("streamlit.button", side_effect=[False, True]),
        patch("streamlit.expander"),
        patch("streamlit.empty"),
        patch("src.core.services.OptimizationService.run") as mock_run,
        patch("src.ui.session_manager.go_to_step") as mock_go,
        patch("streamlit.session_state", mock_state),
    ):
        c1, c2 = MagicMock(), MagicMock()
        g_col = MagicMock()
        c_back, c_go = MagicMock(), MagicMock()
        c_go.button.return_value = True
        c_back.button.return_value = False

        with patch("streamlit.columns") as mock_cols:
            mock_cols.side_effect = [[c1, c2], [g_col], [c_back, c_go]]
            mock_run.return_value = (
                None,
                {"status": "INFEASIBLE", "elapsed": 0.5, "error": "No solution"},
            )
            steps.render_step_2()

        assert mock_state.get("results_df") is None
        assert mock_state.solver_error == "No solution"
        mock_go.assert_called_with(3)


def test_results_renderer_std_else():
    """Cover results_renderer.py global stats display branch."""
    df = pd.DataFrame({"Name": ["P1"], config.COL_GROUP: [1], "S1": [10.0]})
    with (
        patch("streamlit.subheader"),
        patch("streamlit.dataframe"),
        patch("streamlit.metric"),
    ):
        results_renderer.render_global_stats(df, ["S1"])


def test_results_renderer_reassignment():
    """Cover the group reassignment logic in results_renderer cards."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["P1"],
            config.COL_GROUP: [1],
            "Score1": [10.0],
            "_original_index": [0],
        }
    )
    group = {"id": 1, "averages": {"Score1": 10.0}, "members": df.to_dict("records")}

    mock_state = DummySessionState({"interactive_df": df.copy()})

    edited_df = pd.DataFrame(
        {
            config.COL_GROUP: [2],
            config.COL_NAME: ["P1"],
            "Score1": [10.0],
            "_original_index": [0],
        }
    )

    with (
        patch("src.ui.results_renderer.st.container"),
        patch("src.ui.results_renderer.st.markdown"),
        patch(
            "src.ui.results_renderer.st.columns",
            return_value=[MagicMock(), MagicMock()],
        ),
        patch("src.ui.results_renderer.st.data_editor", return_value=edited_df),
        patch("src.ui.results_renderer.st.expander"),
        patch("src.ui.results_renderer.st.metric"),
        patch("src.ui.results_renderer.st.session_state", mock_state),
        patch("src.ui.results_renderer.st.rerun") as mock_rerun,
    ):
        results_renderer._render_single_card(group, ["Score1"])
        assert mock_state.interactive_df.at[0, config.COL_GROUP] == 2
        mock_rerun.assert_called_once()
