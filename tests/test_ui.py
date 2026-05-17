"""Unit tests for UI step rendering and logic."""

from collections.abc import Callable, Iterable
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.core import config
from src.core.models import ConflictPriority
from src.ui import components, results_renderer, steps


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


def test_session_manager_init() -> None:
    """Verify session manager initializes with Step 1."""
    from src.ui import session_manager

    mock_state = DummySessionState({})
    with patch("streamlit.session_state", mock_state):
        session_manager.init_session()
        assert mock_state.step == 1
        assert "manual_df" in mock_state


def test_session_manager_navigation() -> None:
    """Verify manual step navigation updates state."""
    from src.ui import session_manager

    mock_state = DummySessionState({"step": 1})
    with (
        patch("streamlit.session_state", mock_state),
        patch("streamlit.rerun"),
    ):
        session_manager.go_to_step(2)
        assert mock_state.step == 2


def test_components_setup() -> None:
    """Check that components.py basic setup works."""
    with patch("streamlit.set_page_config") as mock_cfg:
        components.setup_page()
        assert mock_cfg.called


def test_components_header() -> None:
    """Verify page header components render without error."""
    with (
        patch("streamlit.markdown"),
        patch("streamlit.columns", return_value=[MagicMock()] * 3),
        patch("streamlit.expander"),
        patch("streamlit.title"),
    ):
        # Description
        components.render_header_description()


def test_results_renderer_empty() -> None:
    """Verify results renderer handles empty/None inputs gracefully."""
    with patch("streamlit.warning") as mock_warn:
        results_renderer.render_global_stats(None, ["Score1"])
        assert mock_warn.called


def test_results_renderer_grid_branches(
    mock_streamlit_columns: Callable[[int], list[MagicMock]],
) -> None:
    """Cover the multi-row grid rendering logic in render_group_cards."""
    # 4 groups, 3 cols per row = 2 rows
    df = pd.DataFrame({config.COL_GROUP: [1, 2, 3, 4], "S": [1, 1, 1, 1]})
    with (
        patch("streamlit.columns", side_effect=mock_streamlit_columns) as mock_cols,
        patch("src.ui.results_renderer._render_single_card"),
    ):
        results_renderer.render_group_cards(df, ["S"])
        # Should call columns twice (2 rows)
        assert mock_cols.call_count == 2


def test_results_renderer_single_card_with_members() -> None:
    """Verify that _render_single_card renders a data_editor for non-empty groups."""
    group = {
        "id": 1,
        "averages": {"Score1": 10.0},
        "members": [
            {
                "Name": "A",
                config.COL_GROUP: 1,
                "Score1": 10.0,
                "_original_index": 0,
            }
        ],
    }
    with (
        patch("streamlit.container") as mock_container,
        patch("streamlit.columns", return_value=[MagicMock()]),
        patch("streamlit.metric"),
        patch("streamlit.data_editor") as mock_editor,
    ):
        mock_container.return_value.__enter__.return_value = MagicMock()
        results_renderer._render_single_card(group, ["Score1"])
        assert mock_editor.called


def test_steps_render_3_cards() -> None:
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
        assert mock_cards.called


def test_components_header_branches() -> None:
    """Exercise coverage in components.py step rendering."""
    # Step 1
    with patch("streamlit.columns", return_value=[MagicMock()] * 3):
        components.render_step_progress(1)
        # Step 2
        components.render_step_progress(2)
        # Step 3
        components.render_step_progress(3)


def test_steps_render_footer_actions(
    mock_streamlit_columns: Callable[[int], list[MagicMock]],
) -> None:
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
        assert mock_dl.called


def test_steps_render_1() -> None:
    """Verify Step 1 basic rendering."""
    mock_state = DummySessionState({"manual_df": pd.DataFrame()})
    with (
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.expander"),
        patch("streamlit.file_uploader", return_value=None),
        patch("streamlit.button", return_value=False),
        patch("streamlit.data_editor"),
        patch("streamlit.session_state", mock_state),
    ):
        steps.render_step_1()


def test_steps_render_2(
    mock_streamlit_columns: Callable[[int], list[MagicMock]],
) -> None:
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
        patch("streamlit.info"),
    ):
        mock_slider.return_value = 1
        steps.render_step_2()


def test_steps_load_uploaded_file_csv() -> None:
    """Verify Step 1 file loading (CSV path)."""
    mock_df = pd.DataFrame({"Name": ["A"], "Score1": [1.0]})
    mock_file = MagicMock()
    mock_file.name = "test.csv"
    mock_file.getvalue.return_value = b"bytes"
    mock_state = DummySessionState({"manual_df": pd.DataFrame()})

    with (
        patch("pandas.read_csv", return_value=mock_df),
        patch("streamlit.toast"),
        patch("streamlit.session_state", mock_state),
    ):
        success, _ = steps._process_uploaded_file(mock_file)
        assert success
        assert not mock_state.manual_df.empty


def test_steps_add_score_column() -> None:
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
        assert mock_rerun.called


def test_steps_render_1_failure_paths() -> None:
    """Cover Step 1 navigation validation failures."""
    mock_df = pd.DataFrame({"Name": ["A"]})  # Missing Score*
    mock_state = DummySessionState({"manual_df": mock_df})
    mock_file = MagicMock()
    mock_file.getvalue.return_value = b"bytes"

    with (
        patch("streamlit.button", return_value=True),
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.expander"),
        patch("streamlit.file_uploader", return_value=mock_file),
        patch("streamlit.data_editor", return_value=mock_df),
        patch("streamlit.error") as mock_err,
        patch("streamlit.session_state", mock_state),
    ):
        steps.render_step_1()
        assert mock_err.called


def test_steps_render_2_navigation() -> None:
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
        patch("streamlit.columns") as mock_cols,
        patch("streamlit.button"),
        patch("streamlit.number_input", return_value=1.0),
        patch("streamlit.radio", return_value="groupers"),
        patch("src.ui.session_manager.go_to_step") as mock_go,
        patch("streamlit.session_state", mock_state),
        patch("streamlit.info"),
    ):
        # Correctly mock buttons to only return True for Back
        # by providing specific mocks for the 3rd st.columns call
        c_back, c_go = MagicMock(), MagicMock()
        c_back.button.return_value = True
        c_go.button.return_value = False

        mock_cols.side_effect = [
            [MagicMock()] * 2,  # Groups
            [MagicMock()],  # Capacities
            [c_back, c_go],  # Navigation
        ]

        steps.render_step_2()
        assert mock_go.called


def test_steps_render_1_success() -> None:
    """Cover success navigation from Step 1."""
    mock_df = pd.DataFrame({"Name": ["A"], "Score1": [10]})
    mock_state = DummySessionState({"manual_df": mock_df})
    mock_file = MagicMock()
    mock_file.getvalue.return_value = b"bytes"

    with (
        patch("streamlit.button", return_value=True),
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.expander"),
        patch("streamlit.file_uploader", return_value=mock_file),
        patch("streamlit.data_editor", return_value=mock_df),
        patch("src.ui.session_manager.go_to_step") as mock_go,
        patch("streamlit.session_state", mock_state),
    ):
        steps.render_step_1()
        assert mock_go.called


def test_steps_load_uploaded_file_excel() -> None:
    """Verify Step 1 file loading (Excel path)."""
    mock_df = pd.DataFrame({"Name": ["A"], "Score1": [1.0]})
    mock_file = MagicMock()
    mock_file.name = "test.xlsx"
    mock_file.getvalue.return_value = b"bytes"
    mock_state = DummySessionState({"manual_df": pd.DataFrame()})

    with (
        patch("pandas.read_excel", return_value=mock_df),
        patch("streamlit.toast"),
        patch("streamlit.session_state", mock_state),
    ):
        success, _ = steps._process_uploaded_file(mock_file)
        assert success
        assert not mock_state.manual_df.empty


def test_steps_load_uploaded_file_none() -> None:
    """Verify _process_uploaded_file returns False for None."""
    success, sig = steps._process_uploaded_file(None)
    assert not success
    assert sig == ""


def test_steps_start_over() -> None:
    """Verify Start Over resets state but preserves cache."""
    mock_state = DummySessionState(
        {"interactive_df": pd.DataFrame(), "warm_start_cache": {"k": "v"}}
    )
    with (
        patch("streamlit.button", return_value=True),
        patch("streamlit.rerun"),
        patch("streamlit.session_state", mock_state),
        patch("src.ui.steps._build_excel_bytes", return_value=b"bytes"),
        patch("streamlit.download_button"),
        patch("streamlit.columns", return_value=[MagicMock()]),
    ):
        steps._render_footer_actions(["S1"])
        assert "interactive_df" not in mock_state
        assert "warm_start_cache" in mock_state


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
        patch("streamlit.info"),
    ):
        steps.render_step_2()
        assert mock_state.groups_input == 1


def test_ui_steps_load_uploaded_file_exception() -> None:
    """Cover the exception handler in _process_uploaded_file."""
    mock_file = MagicMock()
    mock_file.name = "err.csv"
    mock_file.getvalue.return_value = b"bytes"
    with patch("pandas.read_csv", side_effect=pd.errors.ParserError("Bad CSV")):
        with patch("streamlit.error") as mock_err:
            success, _ = steps._process_uploaded_file(mock_file)
            assert not success
            assert mock_err.called


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
        pytest.raises(StopError),
    ):
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
        patch("streamlit.markdown"),
    ):
        steps._render_table_view(["S1"])


def test_render_footer_reset_hit_proper_mock() -> None:
    """Exercise Start Over with full patch context."""
    from src.ui import steps as steps_mod

    mock_state = DummySessionState(
        {"interactive_df": pd.DataFrame(), "warm_start_cache": {}}
    )
    with (
        patch("streamlit.session_state", mock_state),
        patch("streamlit.button", return_value=True),
        patch("streamlit.rerun") as mock_rerun,
        patch("src.ui.steps._build_excel_bytes", return_value=b""),
        patch("streamlit.download_button"),
        patch("streamlit.columns", return_value=[MagicMock()]),
    ):
        steps_mod._render_footer_actions([])
        assert "interactive_df" not in mock_state
        assert mock_rerun.called


def test_steps_render_2_solver_failure_surface() -> None:
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
        patch("streamlit.columns") as mock_cols,
        patch("streamlit.number_input", return_value=1.0),
        patch("streamlit.radio", return_value="groupers"),
        patch("streamlit.slider", return_value=10),
        patch("streamlit.button", side_effect=[False, True]),
        patch("streamlit.expander"),
        patch("streamlit.empty"),
        patch("src.core.services.OptimizationService.run") as mock_run,
        patch("src.ui.session_manager.go_to_step") as mock_go,
        patch("streamlit.session_state", mock_state),
        patch("streamlit.info"),
    ):
        c1, c2 = MagicMock(), MagicMock()
        g_col = MagicMock()
        c_back, c_go = MagicMock(), MagicMock()
        c_go.button.return_value = True
        c_back.button.return_value = False

        mock_cols.side_effect = [[c1, c2], [g_col], [c_back, c_go]]
        mock_run.return_value = (
            None,
            {"status": "INFEASIBLE", "elapsed": 0.5, "error": "No solution"},
        )
        steps.render_step_2()
        assert mock_go.called
        assert mock_state.solver_status == "INFEASIBLE"


def test_results_renderer_std_else() -> None:
    """Cover results_renderer.py global stats display branch."""
    df = pd.DataFrame({"Name": ["P1"], config.COL_GROUP: [1], "S1": [10.0]})
    with (
        patch("streamlit.subheader"),
        patch("streamlit.dataframe"),
        patch("streamlit.metric"),
        patch("streamlit.expander") as mock_exp,
    ):
        mock_exp.return_value.__enter__.return_value = MagicMock()
        results_renderer.render_global_stats(df, ["S1"])
        assert mock_exp.called


def test_results_renderer_reassignment() -> None:
    """Verify manual reassignment logic in single card editor."""
    df = pd.DataFrame(
        [
            {
                config.COL_NAME: "P1",
                config.COL_GROUP: 1,
                "S1": 10.0,
                "_original_index": 0,
            },
        ]
    )
    edited = df.copy()
    edited.loc[0, config.COL_GROUP] = 2

    mock_state = DummySessionState(
        {"interactive_df": df.copy(), "num_groups_target": 2}
    )

    with (
        patch("streamlit.session_state", mock_state),
        patch("streamlit.data_editor", return_value=edited),
        patch("streamlit.rerun") as mock_rerun,
    ):
        results_renderer._render_member_editor(df, 1, ["S1"])
        assert mock_state.interactive_df.iloc[0][config.COL_GROUP] == 2
        assert mock_rerun.called


def test_table_view_edit_rerun_direct() -> None:
    """Exercise the manual edit sync branch in _render_table_view."""
    df = pd.DataFrame(
        [
            {
                config.COL_NAME: "P1",
                config.COL_GROUP: 1,
                "S1": 10.0,
                "_original_index": 0,
            },
        ]
    )
    edited = df.copy()
    edited.loc[0, config.COL_GROUP] = 2

    mock_state = DummySessionState(
        {
            "interactive_df": df.copy(),
            "num_groups_target": 2,
        }
    )

    with (
        patch("streamlit.session_state", mock_state),
        patch("streamlit.data_editor", return_value=edited),
        patch("streamlit.rerun") as mock_rerun,
        patch("streamlit.columns", return_value=[MagicMock(), MagicMock()]),
        patch("streamlit.subheader"),
        patch("src.utils.group_helpers.aggregate_groups", return_value=[{"id": 1}]),
        patch(
            "src.utils.group_helpers.calculate_balancing_stats",
            return_value=[{"Score Dimension": "S1", "Avg Std Dev (Balance)": 0.0}],
        ),
    ):
        steps._render_table_view(["S1"])
        assert mock_state.interactive_df.iloc[0][config.COL_GROUP] == 2
        assert mock_rerun.called


def test_render_step_3_status_messages() -> None:
    """Cover the status message branches in render_step_3."""
    mock_df = pd.DataFrame({"Name": ["P1"], config.COL_GROUP: [1]})
    common_state = {
        "interactive_df": mock_df,
        "solver_elapsed": 1.0,
        "score_cols": [],
        "solver_error": None,
    }

    with (
        patch("streamlit.button"),
        patch("streamlit.header"),
        patch("streamlit.radio"),
        patch("src.ui.results_renderer.render_global_stats"),
        patch("src.ui.steps._render_footer_actions"),
        patch("streamlit.divider"),
    ):
        # Case 1: OPTIMAL
        with (
            patch(
                "streamlit.session_state",
                DummySessionState({**common_state, "solver_status": "OPTIMAL"}),
            ),
            patch("streamlit.success") as mock_success,
        ):
            steps.render_step_3()
            assert mock_success.called

        # Case 2: FEASIBLE
        with (
            patch(
                "streamlit.session_state",
                DummySessionState({**common_state, "solver_status": "FEASIBLE"}),
            ),
            patch("streamlit.warning") as mock_warn,
        ):
            steps.render_step_3()
            assert mock_warn.called

        # Case 3: OTHER
        with (
            patch(
                "streamlit.session_state",
                DummySessionState({**common_state, "solver_status": "STOPPED"}),
            ),
            patch("streamlit.warning") as mock_warn_other,
        ):
            steps.render_step_3()
            assert mock_warn_other.called


def test_render_step_3_error_tips() -> None:
    """Cover the error message branch in render_step_3."""
    mock_state = DummySessionState(
        {
            "solver_error": "Failed!",
            "solver_status": "ERROR",
        }
    )
    with (
        patch("streamlit.session_state", mock_state),
        patch("streamlit.button"),
        patch("streamlit.header"),
        patch("streamlit.error") as mock_err,
        patch("streamlit.info") as mock_info,
    ):
        steps.render_step_3()
        assert mock_err.called
        assert mock_info.called


def test_process_uploaded_file_unexpected_exception() -> None:
    """Cover the general Exception catch-all in _process_uploaded_file."""
    mock_file = MagicMock()
    mock_file.name = "bomb.csv"
    # Cause a generic exception during Path creation or string logic
    with (
        patch("pathlib.Path", side_effect=RuntimeError("Generic")),
        patch("streamlit.error") as mock_err,
    ):
        success, sig = steps._process_uploaded_file(mock_file)
        assert not success
        assert sig == ""
        assert mock_err.called


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
        patch(
            "streamlit.button",
            side_effect=lambda label, **_kwargs: label == "🚀 Generate",
        ),
        patch("streamlit.columns") as mock_cols,
        patch("streamlit.number_input", return_value=1.0),
        patch("streamlit.radio", return_value="groupers"),
        patch("streamlit.empty", return_value=MagicMock()),
        patch("streamlit.info"),
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
        assert prev_results.loc[0, "participant_fingerprint"] == "fp1"


def test_add_score_column_clash_logic() -> None:
    """Verify that Add Score Column handles existing names correctly."""
    df = pd.DataFrame({"Name": ["A"], "Score1": [1.0], "Score2": [2.0]})
    mock_state = DummySessionState({"manual_df": df})
    with (
        patch("streamlit.session_state", mock_state),
        patch("streamlit.rerun"),
    ):
        steps._add_new_score_column()
        # Should skip 1 and 2, create Score3
        assert "Score3" in mock_state.manual_df.columns


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
        {
            "interactive_df": res.copy(),
            "results_df": res.copy(),
            "warm_start_cache": {},
        }
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
