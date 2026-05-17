"""Unit tests for the solver interface."""

from unittest.mock import MagicMock, patch

import pytest
from ortools.sat.python import cp_model

from src.core import solver_interface
from src.core.models import Participant, SolverConfig

# Expected Constants
EXPECTED_P_COUNT = 2


@pytest.fixture
def sample_participants() -> list[Participant]:
    """Provides a list of strongly-typed participant models."""
    return [
        Participant(name="A", scores={"S1": 10}, original_index=0),
        Participant(name="B", scores={"S1": 20}, original_index=1),
    ]


@pytest.fixture
def sample_config() -> SolverConfig:
    """Provides a basic solver configuration."""
    return SolverConfig(
        num_groups=2,
        group_capacities=[1, 1],
        score_weights={"S1": 1.0},
        interleave_search=True,
    )


def test_run_optimization_success(
    sample_participants: list[Participant], sample_config: SolverConfig
) -> None:
    """Verify standard success path of run_optimization."""
    with (
        patch("streamlit.status") as mock_status,
        patch("streamlit.write"),
        patch("streamlit.empty"),
    ):
        mock_status.return_value.__enter__.return_value = MagicMock()
        df, metrics = solver_interface.run_optimization(
            sample_participants, sample_config
        )

        assert df is not None
        assert len(df) == EXPECTED_P_COUNT
        assert metrics["status"] == "OPTIMAL"


def test_run_optimization_infeasible() -> None:
    """Verify handling of infeasible constraints."""
    # Force infeasibility via impossible capacities (Total P=2, Total Cap=1)
    cfg = SolverConfig(
        num_groups=1,
        group_capacities=[1],
        score_weights={"S1": 1.0},
        interleave_search=True,
    )
    p = [
        Participant(name="A", scores={"S1": 10}, original_index=0),
        Participant(name="B", scores={"S1": 10}, original_index=1),
    ]

    with (
        patch("streamlit.status") as mock_status,
        patch("streamlit.write"),
        patch("streamlit.error"),
        patch("streamlit.empty"),
    ):
        mock_status.return_value.__enter__.return_value = MagicMock()
        df, metrics = solver_interface.run_optimization(p, cfg)

        assert df is None
        assert metrics["status"] == "INFEASIBLE"


def test_run_optimization_status_callback(
    sample_participants: list[Participant], sample_config: SolverConfig
) -> None:
    """Verify that the Streamlit callback is invoked during solve."""
    with (
        patch("src.core.solver_interface.StreamlitSolverCallback") as mock_cb,
        patch("ortools.sat.python.cp_model.CpSolver.Solve"),
        patch("streamlit.status"),
        patch("streamlit.empty"),
    ):
        solver_interface.run_optimization(sample_participants, sample_config)
        assert mock_cb.called


def test_run_optimization_metadata_attachment(
    sample_participants: list[Participant], sample_config: SolverConfig
) -> None:
    """Verify that configuration metadata is attached to result DataFrame."""
    with (
        patch("streamlit.status"),
        patch("streamlit.write"),
        patch("streamlit.empty"),
    ):
        df, _ = solver_interface.run_optimization(sample_participants, sample_config)
        assert df is not None
        assert df.attrs["score_weights"] == dict(sample_config.score_weights)
        assert df.attrs["conflict_priority"] == sample_config.conflict_priority


def test_solver_error_msg_branches() -> None:
    """Cover all branches of user-friendly error message derivation."""
    assert solver_interface._get_solver_error_msg(cp_model.OPTIMAL, "OPTIMAL") is None
    assert "invalid" in solver_interface._get_solver_error_msg(
        cp_model.MODEL_INVALID, "MODEL_INVALID"
    )
    assert "No solution" in solver_interface._get_solver_error_msg(
        cp_model.INFEASIBLE, "INFEASIBLE"
    )
    assert "status: UNKNOWN" in solver_interface._get_solver_error_msg(
        cp_model.UNKNOWN, "UNKNOWN"
    )


def test_run_optimization_no_status_box(
    sample_participants: list[Participant], sample_config: SolverConfig
) -> None:
    """Ensure run_optimization works without a status_box placeholder."""
    # This covers the 'if status_box:' False branches
    df, _ = solver_interface.run_optimization(
        sample_participants, sample_config, status_box=None
    )
    assert df is not None


def test_render_failure_status_no_msg() -> None:
    """Cover failure rendering when no specific error message is provided."""
    mock_box = MagicMock()
    with (
        patch("src.core.solver_interface.st.status") as mock_status,
        patch("src.core.solver_interface.st.write") as mock_write,
    ):
        solver_interface._render_failure_status(mock_box, "UNKNOWN", None)
        assert mock_status.called
        assert mock_write.called
