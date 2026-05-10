"""Unit tests for the solver interface module.

Ensures that the Streamlit-integrated solver callback and the primary
optimization runner handle UI updates, thread contexts, and error states
gracefully.
"""

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest
from ortools.sat.python import cp_model

from src.core import solver_interface
from src.core.models import (
    ConflictPriority,
    Participant,
    SolverConfig,
)


def test_streamlit_solver_callback_on_solution():
    """Test the callback UI update logic."""
    mock_box = MagicMock()
    cb = solver_interface.StreamlitSolverCallback(mock_box, 2)
    cb.ObjectiveValue = MagicMock(return_value=123.4)

    with (
        patch("time.time", return_value=cb.start_time + 1.0),
        patch("streamlit.columns", return_value=[MagicMock()] * 3),
        patch("streamlit.markdown"),
    ):
        cb.on_solution_callback()

    assert cb.solution_count == 1
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
        mock_status.assert_called()


def test_run_optimization_failure_with_status_box():
    """Test failed optimization with status box updates."""
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
        mock_status.assert_called()


def test_solver_interface_fallback_internal():
    """Verify fallback behavior when streamlit scriptrunner is missing."""
    with patch.dict(
        sys.modules,
        {"streamlit.runtime.scriptrunner": None, "streamlit.scriptrunner": None},
    ):
        importlib.reload(solver_interface)
        solver_interface.add_script_run_ctx(None, None)
        assert solver_interface.get_script_run_ctx() is None
    importlib.reload(solver_interface)


def test_solver_interface_callback_throttling():
    """Cover throttling logic in solution callback."""
    cb = solver_interface.StreamlitSolverCallback(MagicMock(), 10)
    cb.ctx = MagicMock()
    cb.last_update_time = 100.0
    with patch("time.time", return_value=100.1):
        cb.on_solution_callback()
        cb.status_placeholder.container.assert_not_called()


def test_solver_interface_callback_context_injection():
    """Verify callback context injection during solve."""
    participants = [Participant(name="P1", scores={"S1": 10.0}, original_index=0)]
    cfg = SolverConfig(num_groups=1, group_capacities=[1], score_weights={"S1": 1.0})
    with (
        patch("ortools.sat.python.cp_model.CpSolver") as mock_solver_cls,
        patch("src.core.solver_interface.add_script_run_ctx") as mock_add_ctx,
    ):
        mock_inst = mock_solver_cls.return_value
        mock_inst.Solve.return_value = cp_model.OPTIMAL
        mock_inst.StatusName.return_value = "OPTIMAL"
        with patch(
            "src.core.solver_interface.get_script_run_ctx", return_value=MagicMock()
        ):
            solver_interface.run_optimization(participants, cfg)
            mock_add_ctx.assert_called()


@pytest.mark.parametrize(
    ("status_code", "status_name"),
    [
        (cp_model.INFEASIBLE, "INFEASIBLE"),
        (cp_model.UNKNOWN, "UNKNOWN"),
        (cp_model.MODEL_INVALID, "MODEL_INVALID"),
    ],
)
def test_solver_interface_status_box_failure_paths(status_code, status_name):
    """Verify all non-feasible solver outcomes surface st.error to the UI."""
    participants = [Participant(name="P1", scores={"S1": 10.0}, original_index=0)]
    cfg = SolverConfig(num_groups=1, group_capacities=[1], score_weights={"S1": 1.0})
    with (
        patch("ortools.sat.python.cp_model.CpSolver") as mock_solver_cls,
        patch("src.core.solver_interface.st") as mock_st,
    ):
        mock_inst = mock_solver_cls.return_value
        mock_inst.Solve.return_value = status_code
        mock_inst.StatusName.return_value = status_name
        solver_interface.run_optimization(participants, cfg, status_box=MagicMock())
        mock_st.error.assert_called()
