"""Unit tests for the UI layer (Mocked Streamlit)."""

from unittest.mock import MagicMock, patch

import pandas as pd

from src.core import config
from src.ui import components, results_renderer, session_manager


def test_session_manager_init():
    """Verify that session state is initialized correctly."""
    mock_state = MagicMock()
    # Mocking 'in' operator
    mock_state.__contains__.return_value = False

    with patch("streamlit.session_state", mock_state):
        session_manager.init_session()
        # Verify __setitem__ was called for defaults
        mock_state.__setitem__.assert_any_call("step", 1)
        # Verify manual_df was set (via attribute access in the code)
        assert mock_state.manual_df is not None


def test_session_manager_navigation():
    """Verify that navigation logic clamps step values."""
    mock_state = MagicMock()
    mock_state.step = 1
    with (
        patch("streamlit.session_state", mock_state),
        patch("streamlit.rerun") as mock_rerun,
    ):
        session_manager.go_to_step(2)
        assert mock_state.step == 2
        mock_rerun.assert_called_once()

        # Test clamping
        session_manager.go_to_step(5)
        assert mock_state.step == 3


def test_components_setup():
    """Verify setup_page calls streamlit correctly."""
    with patch("streamlit.set_page_config") as mock_conf:
        components.setup_page()
        mock_conf.assert_called_once()


def test_components_header():
    """Verify page header renders without error."""
    with (
        patch("streamlit.markdown"),
        patch("streamlit.columns") as mock_cols,
        patch("streamlit.expander"),
    ):
        # Mock columns to return 3 mocks for labels and 3 for bar segments
        mock_cols.side_effect = [
            [MagicMock(), MagicMock(), MagicMock()],
            [MagicMock(), MagicMock(), MagicMock()],
        ]
        components.render_page_header(1)


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
        patch("streamlit.columns") as mock_cols,
        patch("src.ui.results_renderer._render_single_card"),
    ):
        # Grid of 2 columns
        mock_cols.return_value = [MagicMock(), MagicMock()]
        results_renderer.render_group_cards(df, score_cols)
        assert mock_cols.call_count >= 1


def test_results_renderer_single_card_with_members():
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

    mock_state = MagicMock()
    mock_state.get.return_value = 2

    with (
        patch("streamlit.container"),
        patch("streamlit.markdown"),
        patch("streamlit.columns") as mock_cols,
        patch("streamlit.data_editor") as mock_editor,
        patch("streamlit.expander"),
        patch("streamlit.metric"),
        patch("streamlit.session_state", mock_state),
    ):
        mock_cols.side_effect = [
            [MagicMock(), MagicMock()],  # c1, c2
            [MagicMock()],  # m_cols
        ]

        # Mock data_editor to return the same dataframe (no changes)
        def mock_data_editor(df, *args, **kwargs):
            return df

        mock_editor.side_effect = mock_data_editor

        results_renderer._render_single_card(group, ["Score1"])

        # Check dataframe was rendered via data_editor
        mock_editor.assert_called_once()
        df_arg = mock_editor.call_args[0][0]
        assert "Groupers" in df_arg.columns
        assert "Score1" in df_arg.columns
        assert "Group" in df_arg.columns


def test_steps_render_3_cards():
    """Verify Step 3 results view in Cards mode."""
    mock_df = pd.DataFrame({"Name": ["P1"], "Group": [1], "Score1": [10.0]})
    mock_state = MagicMock()
    mock_state.interactive_df = mock_df
    mock_state.__contains__.return_value = True

    def get_side_effect(key, default=None):
        if key == "solver_status":
            return "OPTIMAL"
        if key == "solver_elapsed":
            return 1.23
        if key == "score_cols":
            return ["Score1"]
        return default

    mock_state.get.side_effect = get_side_effect

    with (
        patch("streamlit.header"),
        patch("streamlit.radio") as mock_radio,
        patch("streamlit.button"),
        patch("streamlit.divider"),
        patch("streamlit.success"),
        patch("src.ui.results_renderer.render_group_cards") as mock_cards,
        patch("src.ui.steps._render_footer_actions"),
        patch("streamlit.session_state", mock_state),
    ):
        mock_radio.return_value = "Cards"
        from src.ui import steps

        steps.render_step_3()
        mock_cards.assert_called_once()


def test_components_header_branches():
    """Verify page header renders all steps (inactive/active)."""
    with (
        patch("streamlit.markdown"),
        patch("streamlit.columns") as mock_cols,
        patch("streamlit.expander"),
    ):
        # Mock calls for each step
        mock_cols.side_effect = [
            [MagicMock(), MagicMock(), MagicMock()],  # s=1 labels
            [MagicMock(), MagicMock(), MagicMock()],  # s=1 bar
            [MagicMock(), MagicMock(), MagicMock()],  # s=2 labels
            [MagicMock(), MagicMock(), MagicMock()],  # s=2 bar
            [MagicMock(), MagicMock(), MagicMock()],  # s=3 labels
            [MagicMock(), MagicMock(), MagicMock()],  # s=3 bar
        ]

        # Test each step to hit all branches
        for s in [1, 2, 3]:
            components.render_page_header(s)


def test_steps_render_footer_actions():
    """Verify footer actions render correctly."""
    mock_df = pd.DataFrame({"Name": ["P1"], "Group": [1]})
    mock_state = MagicMock()
    mock_state.interactive_df = mock_df

    with (
        patch("streamlit.columns") as mock_cols,
        patch("src.utils.exporter.generate_excel_bytes", return_value=b"bytes"),
        patch("streamlit.download_button") as mock_dl,
        patch("streamlit.button") as mock_btn,
        patch("streamlit.session_state", mock_state),
    ):
        mock_cols.return_value = [MagicMock(), MagicMock()]
        from src.ui import steps

        # Fixed signature: only takes score_cols
        steps._render_footer_actions(["Score1"])
        mock_dl.assert_called_once()
        assert mock_btn.call_count >= 1


def test_steps_render_1():
    """Verify Step 1 renders correctly with data editor."""
    with (
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.expander"),
        patch("streamlit.file_uploader"),
        patch("streamlit.button", return_value=False),
        patch("streamlit.data_editor") as mock_editor,
        patch("streamlit.session_state", MagicMock()),
    ):
        from src.ui import steps

        steps.render_step_1()
        assert mock_editor.call_count == 1


def test_steps_render_2():
    """Verify Step 2 renders configuration elements."""
    mock_df = pd.DataFrame({"Name": ["P1"], "Score1": [10.0]})
    mock_state = MagicMock()
    mock_state.participants_df = mock_df

    def get_side_effect(key, default=None):
        if key == "participants_df":
            return mock_df
        if key == "score_cols":
            return ["Score1"]
        return default

    mock_state.get.side_effect = get_side_effect

    with (
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.columns") as mock_cols,
        patch("streamlit.number_input") as mock_num,
        patch("streamlit.radio") as mock_radio,
        patch("streamlit.slider") as mock_slider,
        patch("streamlit.button", return_value=False),
        patch("streamlit.expander"),
        patch("streamlit.session_state", mock_state),
    ):
        mock_num.return_value = 1.0
        # Mock radio for both calls: Mode and Priority
        mock_radio.side_effect = ["Advanced", "Groupers"]
        mock_slider.return_value = 1

        mock_cols.side_effect = [
            [MagicMock(), MagicMock()],  # st.columns(2)
            [MagicMock()],  # st.columns(num_groups)
            [MagicMock(), MagicMock()],  # st.columns([1, 5])
        ]

        from src.ui import steps

        steps.render_step_2()


def test_steps_load_uploaded_file_csv():
    """Verify file upload callback for CSV."""
    mock_file = MagicMock()
    mock_file.name = "test.csv"
    mock_state = MagicMock()
    mock_state.u_file = mock_file

    with (
        patch("pandas.read_csv") as mock_read,
        patch("src.core.services.DataService.clean_participants_df") as mock_clean,
        patch("streamlit.session_state", mock_state),
        patch("streamlit.toast"),
    ):
        from src.ui import steps

        steps._load_uploaded_file()
        mock_read.assert_called_once()
        mock_clean.assert_called_once()


def test_steps_add_score_column():
    """Verify 'Add Score Column' button logic."""
    mock_df = pd.DataFrame({"Name": ["A"], "Score1": [1.0]})
    mock_state = MagicMock()
    mock_state.manual_df = mock_df

    with (
        patch("streamlit.button", return_value=True),
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.expander"),
        patch("streamlit.file_uploader"),
        patch("streamlit.data_editor"),
        patch("streamlit.rerun") as mock_rerun,
        patch("streamlit.session_state", mock_state),
    ):
        from src.ui import steps

        steps.render_step_1()
        # Should have added Score2
        assert "Score2" in mock_state.manual_df.columns
        mock_rerun.assert_called_once()


def test_steps_render_1_failure_paths():
    """Verify Step 1 error messages for invalid data."""
    from src.ui import steps

    mock_state = MagicMock()
    with (
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.expander"),
        patch("streamlit.file_uploader"),
        patch("streamlit.button", return_value=True),
        patch("streamlit.data_editor", return_value=pd.DataFrame()),
        patch("streamlit.warning") as mock_warn,
        patch("streamlit.error") as mock_err,
        patch("streamlit.session_state", mock_state),
    ):
        steps.render_step_1()
        mock_warn.assert_called_with("Please add participants.")

        # Test with participants but missing score cols
        with patch("streamlit.data_editor", return_value=pd.DataFrame({"Name": ["A"]})):
            steps.render_step_1()
            mock_err.assert_called_with("At least one score column is required.")


def test_steps_render_2_navigation():
    """Verify navigation buttons in Step 2."""
    from src.ui import steps

    mock_df = pd.DataFrame({"Name": ["P1"], "Score1": [10.0]})
    mock_state = MagicMock()
    mock_state.participants_df = mock_df

    def get_side_effect(key, default=None):
        if key == "participants_df":
            return mock_df
        if key == "score_cols":
            return ["Score1"]
        return default

    mock_state.get.side_effect = get_side_effect

    with (
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.columns") as mock_cols,
        patch("streamlit.button"),
        patch("src.ui.session_manager.go_to_step") as mock_go,
        patch("streamlit.session_state", mock_state),
    ):
        c1, c2 = MagicMock(), MagicMock()
        c1.number_input.return_value = 1.0

        g_col = MagicMock()
        g_col.number_input.return_value = 1.0

        c_back = MagicMock()
        c_go = MagicMock()
        c_back.button.return_value = True
        c_go.button.return_value = False

        mock_cols.side_effect = [
            [c1, c2],  # st.columns(2)
            [g_col],  # st.columns(num_groups)
            [c_back, c_go],  # st.columns([1, 5])
        ]

        steps.render_step_2()
        mock_go.assert_called_with(1)


def test_steps_render_1_success():
    """Verify Step 1 successful 'Next' navigation."""
    from src.ui import steps

    df = pd.DataFrame(
        {
            config.COL_NAME: ["A"],
            "Score1": [10.0],
            config.COL_GROUPER: [""],
            config.COL_SEPARATOR: [""],
        }
    )
    mock_state = MagicMock()

    with (
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.expander"),
        patch("streamlit.file_uploader"),
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
    mock_state = MagicMock()
    mock_state.u_file = mock_file

    with (
        patch("pandas.read_excel") as mock_read,
        patch("src.core.services.DataService.clean_participants_df") as mock_clean,
        patch("streamlit.session_state", mock_state),
        patch("streamlit.toast"),
    ):
        from src.ui import steps

        steps._load_uploaded_file()
        mock_read.assert_called_once()
        mock_clean.assert_called_once()


def test_steps_load_uploaded_file_none():
    """Verify file upload callback with no file."""
    mock_state = MagicMock()
    mock_state.u_file = None
    with patch("streamlit.session_state", mock_state):
        from src.ui import steps

        steps._load_uploaded_file()  # Should just return


def test_steps_render_3_interactive():
    """Verify interactive elements in Step 3."""
    from src.ui import steps

    mock_df = pd.DataFrame(
        {config.COL_NAME: ["P1"], config.COL_GROUP: [1], "Score1": [10.0]}
    )
    mock_state = MagicMock()
    mock_state.interactive_df = mock_df
    mock_state.__contains__.return_value = True

    def get_side_effect(key, default=None):
        if key == "solver_status":
            return "OPTIMAL"
        if key == "solver_elapsed":
            return 1.23
        if key == "score_cols":
            return ["Score1"]
        return default

    mock_state.get.side_effect = get_side_effect

    with (
        patch("streamlit.header"),
        patch("streamlit.radio", return_value="Table"),
        patch("streamlit.button") as mock_btn,
        patch("src.ui.session_manager.go_to_step") as mock_go,
        patch("src.ui.steps._render_table_view"),
        patch("src.ui.steps._render_footer_actions"),
        patch("streamlit.success"),
        patch("streamlit.session_state", mock_state),
    ):
        # Mock "Back" button
        mock_btn.side_effect = lambda label, **kwargs: label == "⬅ Back"
        steps.render_step_3()
        mock_go.assert_called_with(2)


def test_data_loader_invalid_columns_check():
    """Verify that load_data returns None when required columns are missing.

    Mocks path validation to return a valid string and CSV loading to return
    a dataframe with incorrect columns, ensuring the validation logic
    identifies the failure.
    """
    from src.core import data_loader

    df = pd.DataFrame({"Wrong": ["A"]})
    with (
        patch("src.core.data_loader.validate_file_path", return_value="test.csv"),
        patch("pandas.read_csv", return_value=df),
    ):
        assert data_loader.load_data("test.csv") is None


def test_steps_start_over():
    """Verify 'Start Over' button logic."""
    from src.ui import steps

    mock_state = MagicMock()
    with (
        patch("streamlit.button", return_value=True),
        patch("streamlit.download_button"),
        patch("src.utils.exporter.generate_excel_bytes"),
        patch("streamlit.rerun") as mock_rerun,
        patch("streamlit.session_state", mock_state),
    ):
        steps._render_footer_actions(["Score1"])
        mock_state.clear.assert_called_once()
        mock_rerun.assert_called_once()


def test_steps_render_2_clamped_groups():
    """Verify that the number of groups is correctly clamped to the participant count.

    Ensures that when only one participant is present, the default group count
    does not exceed the participant count, preventing Streamlit widget errors.
    """
    from src.ui import steps

    mock_df = pd.DataFrame({"Name": ["P1"], "Score1": [10.0]})  # total_p = 1
    mock_state = MagicMock()
    mock_state.participants_df = mock_df

    def get_side_effect(key, default=None):
        if key == "participants_df":
            return mock_df
        if key == "score_cols":
            return ["Score1"]
        return default

    mock_state.get.side_effect = get_side_effect

    with (
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.columns") as mock_cols,
        patch("streamlit.number_input"),
        patch("streamlit.radio") as mock_radio,
        patch("streamlit.slider"),
        patch("streamlit.button", return_value=False),
        patch("streamlit.expander"),
        patch("streamlit.session_state", mock_state),
    ):
        mock_radio.side_effect = ["Advanced", "Groupers"]
        c1, c2 = MagicMock(), MagicMock()
        g_col = MagicMock()
        c_back, c_go = MagicMock(), MagicMock()
        c_back.button.return_value = False
        c_go.button.return_value = False

        mock_cols.side_effect = [
            [c1, c2],  # st.columns(2)
            [g_col],  # st.columns(num_groups)
            [c_back, c_go],  # st.columns([1, 5])
        ]

        steps.render_step_2()

        # Check the call to number_input for "Groups"
        # num_groups = int(c1.number_input("Groups", 1, total_p, min(2, total_p)))
        # For total_p=1, it should be c1.number_input("Groups", 1, 1, 1)
        c1.number_input.assert_any_call("Groups", 1, 1, 1)
