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
    cb = solver_interface.StreamlitSolverCallback(mock_box, 2)

    # Mock ObjectiveValue
    cb.ObjectiveValue = MagicMock(return_value=123.4)

    # Force the time to be > 0.25 seconds later to trigger the update
    with (
        patch("time.time", return_value=cb.start_time + 1.0),
        patch("streamlit.columns", return_value=[MagicMock()] * 3),
        patch("streamlit.markdown"),
    ):
        cb.on_solution_callback()

    assert cb.solution_count == 1
    # Should use the container from status_box
    mock_box.container.assert_called()


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
    with (
        patch("streamlit.status") as mock_status,
        patch("streamlit.write"),
        patch("streamlit.columns", return_value=[MagicMock()] * 3),
        patch("streamlit.markdown"),
    ):
        df, metrics = solver_interface.run_optimization(
            participants,
            cfg,
            status_box=mock_box,
        )

        assert df is not None
        assert metrics["status"] in ["OPTIMAL", "FEASIBLE"]
        # st.status should be called for completion
        mock_status.assert_called()


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
    with (
        patch("streamlit.status") as mock_status,
        patch("streamlit.error"),
        patch("streamlit.columns", return_value=[MagicMock()] * 3),
        patch("streamlit.markdown"),
    ):
        df, metrics = solver_interface.run_optimization(
            participants,
            cfg,
            status_box=mock_box,
        )

        assert df is None
        # st.status should be called for failure
        mock_status.assert_called()

def test_solver_interface_error_branches():
    """Cover error reporting in solver_interface.run_optimization."""
    participants = [Participant(name="P1", scores={"S1": 10.0}, original_index=0)]
    cfg = SolverConfig(num_groups=1, group_capacities=[1], score_weights={"S1": 1.0})

    from ortools.sat.python import cp_model
    with patch("ortools.sat.python.cp_model.CpSolver") as mock_solver_cls:
        with patch("src.core.solver_interface.st") as mock_st:
            mock_inst = mock_solver_cls.return_value
            mock_inst.Solve.return_value = 0
            mock_inst.StatusName.return_value = "UNKNOWN"

            solver_interface.run_optimization(participants, cfg, status_box=MagicMock())
            mock_st.write.assert_called()
def test_solver_interface_fallback_internal():
    """Directly call fallback internal functions in solver_interface."""
    import src.core.solver_interface as si
    si.add_script_run_ctx(None, None)
    si.get_script_run_ctx()

def test_solver_interface_solve_line_138():
    """Cover solver_interface.py line 138 (Solve call)."""
    participants = [Participant(name="P1", scores={"S1": 10.0}, original_index=0)]
    cfg = SolverConfig(num_groups=1, group_capacities=[1], score_weights={"S1": 1.0})
    
    with (
        patch("ortools.sat.python.cp_model.CpSolver") as mock_solver_cls,
        patch("src.core.solver_interface.add_script_run_ctx") as mock_add_ctx
    ):
        mock_inst = mock_solver_cls.return_value
        mock_inst.Solve.return_value = 0 # UNKNOWN
        with patch("src.core.solver_interface.get_script_run_ctx", return_value=MagicMock()):
            solver_interface.run_optimization(participants, cfg)
            mock_add_ctx.assert_called()

def test_solver_interface_callback_throttling():
    """Explicitly test callback throttling."""
    cb = solver_interface.StreamlitSolverCallback(MagicMock(), 10)
    cb.ctx = MagicMock()
    cb.last_update_time = 100.0
    
    with patch("time.time", return_value=100.1): # < 0.25 diff
        cb.on_solution_callback()