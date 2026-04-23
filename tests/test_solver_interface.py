"""Unit tests for the solver interface module."""

import importlib
import sys
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


def test_solver_interface_fallback_internal():
    """Cover lines 24-34."""
    # We use a sub-test or reload logic here
    # Actually, we can just call them from the module if we can get them
    # But since they are shadowed, we reload.
    with patch.dict(
        sys.modules,
        {"streamlit.runtime.scriptrunner": None, "streamlit.scriptrunner": None},
    ):
        importlib.reload(solver_interface)
        solver_interface.add_script_run_ctx(None, None)
        assert solver_interface.get_script_run_ctx() is None
    # Restore the module for other tests
    importlib.reload(solver_interface)


def test_solver_interface_callback_throttling():
    """Cover line 67."""
    cb = solver_interface.StreamlitSolverCallback(MagicMock(), 10)
    cb.ctx = MagicMock()
    cb.last_update_time = 100.0
    with patch("time.time", return_value=100.1):  # < 0.25 diff
        cb.on_solution_callback()


def test_solver_interface_solve_line_145():
    """Cover line 145."""
    participants = [Participant(name="P1", scores={"S1": 10.0}, original_index=0)]
    cfg = SolverConfig(num_groups=1, group_capacities=[1], score_weights={"S1": 1.0})
    with (
        patch("ortools.sat.python.cp_model.CpSolver") as mock_solver_cls,
        patch("src.core.solver_interface.add_script_run_ctx") as mock_add_ctx,
    ):
        mock_inst = mock_solver_cls.return_value
        mock_inst.Solve.return_value = 4  # OPTIMAL
        mock_inst.StatusName.return_value = "OPTIMAL"
        with patch(
            "src.core.solver_interface.get_script_run_ctx", return_value=MagicMock()
        ):
            solver_interface.run_optimization(participants, cfg)
            mock_add_ctx.assert_called()


def test_solver_interface_status_box_infeasible():
    """Cover line 202."""
    participants = [Participant(name="P1", scores={"S1": 10.0}, original_index=0)]
    cfg = SolverConfig(num_groups=1, group_capacities=[1], score_weights={"S1": 1.0})
    with patch("ortools.sat.python.cp_model.CpSolver") as mock_solver_cls:
        with patch("src.core.solver_interface.st") as mock_st:
            mock_inst = mock_solver_cls.return_value
            mock_inst.Solve.return_value = 3  # INFEASIBLE
            mock_inst.StatusName.return_value = "INFEASIBLE"
            status_box = MagicMock()
            solver_interface.run_optimization(participants, cfg, status_box=status_box)
            mock_st.error.assert_called()


def test_solver_interface_status_box_unknown():
    """Cover line 213."""
    participants = [Participant(name="P1", scores={"S1": 10.0}, original_index=0)]
    cfg = SolverConfig(num_groups=1, group_capacities=[1], score_weights={"S1": 1.0})
    with patch("ortools.sat.python.cp_model.CpSolver") as mock_solver_cls:
        with patch("src.core.solver_interface.st") as mock_st:
            mock_inst = mock_solver_cls.return_value
            mock_inst.Solve.return_value = 0  # UNKNOWN
            mock_inst.StatusName.return_value = "UNKNOWN"
            status_box = MagicMock()
            solver_interface.run_optimization(participants, cfg, status_box=status_box)
            mock_st.write.assert_called()


def test_solver_interface_status_box_invalid():
    """Cover MODEL_INVALID status branch."""
    participants = [Participant(name="P1", scores={"S1": 10.0}, original_index=0)]
    cfg = SolverConfig(num_groups=1, group_capacities=[1], score_weights={"S1": 1.0})
    with patch("ortools.sat.python.cp_model.CpSolver") as mock_solver_cls:
        with patch("src.core.solver_interface.st") as mock_st:
            mock_inst = mock_solver_cls.return_value
            mock_inst.Solve.return_value = 1  # MODEL_INVALID
            mock_inst.StatusName.return_value = "MODEL_INVALID"
            status_box = MagicMock()
            solver_interface.run_optimization(participants, cfg, status_box=status_box)
            mock_st.error.assert_called()
