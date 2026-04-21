"""Unit tests for the solver interface module."""

from unittest.mock import MagicMock, patch

from src.core import solver_interface
from src.core.models import (
    ConflictPriority,
    OptimizationMode,
    Participant,
    SolverConfig,
)


def test_streamlit_solver_callback_on_solution():
    """Test the callback UI update logic."""
    # Create a mock status box
    mock_box = MagicMock()
    cb = solver_interface.StreamlitSolverCallback(mock_box)

    # Mock ObjectiveValue
    cb.ObjectiveValue = MagicMock(return_value=123.4)

    # Force the time to be > 0.25 seconds later to trigger the update
    with patch("time.time", return_value=cb.start_time + 1.0):
        cb.on_solution_callback()

    assert cb.solution_count == 1
    mock_box.markdown.assert_called_once()
    assert "123.4" in mock_box.markdown.call_args[0][0]


def test_run_optimization_success_with_status_box():
    """Test successful optimization with status box updates."""
    participants = [
        Participant(name="A", scores={"Score1": 10.0}),
        Participant(name="B", scores={"Score1": 20.0}),
    ]
    cfg = SolverConfig(
        num_groups=2,
        group_capacities=[1, 1],
        score_weights={"Score1": 1.0},
        opt_mode=OptimizationMode.SIMPLE,
        conflict_priority=ConflictPriority.GROUPERS,
        timeout_seconds=5,
    )

    mock_box = MagicMock()
    df, metrics = solver_interface.run_optimization(
        participants,
        cfg,
        status_box=mock_box,
    )

    assert df is not None
    assert metrics["status"] in ["OPTIMAL", "FEASIBLE"]

    # The final status markdown should be called
    assert mock_box.markdown.call_count >= 1


def test_run_optimization_failure_with_status_box():
    """Test failed optimization with status box updates."""
    # Create an impossible configuration (capacity doesn't match participants)
    participants = [
        Participant(name="A", scores={"Score1": 10.0}),
        Participant(name="B", scores={"Score1": 10.0}),
        Participant(name="C", scores={"Score1": 10.0}),
    ]
    cfg = SolverConfig(
        num_groups=2,
        group_capacities=[1, 1],
        score_weights={"Score1": 1.0},
    )

    mock_box = MagicMock()
    df, metrics = solver_interface.run_optimization(
        participants,
        cfg,
        status_box=mock_box,
    )

    assert df is None
    # Ensure error was called
    mock_box.error.assert_called_once()
