"""Edge case tests for UI steps."""

from unittest.mock import MagicMock, patch

import pandas as pd

from src.core import config
from src.core.models import ConflictPriority
from src.ui import steps


class DummySessionState(dict):
    """Mock session state."""

    def __getattr__(self, key: str) -> object:
        """Dict key access."""
        return self[key]

    def __setattr__(self, key: str, value: object) -> None:
        """Dict key setting."""
        self[key] = value


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
    with patch("pathlib.Path", side_effect=RuntimeError("Generic")):
        with patch("streamlit.error") as mock_err:
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
