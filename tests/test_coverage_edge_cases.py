"""Targeted tests for remaining coverage gaps."""

from unittest.mock import patch

import pandas as pd

from src.core import data_loader, services, solver, solver_interface
from src.core.models import (
    ConflictPriority,
    OptimizationMode,
    Participant,
    SolverConfig,
)


def test_data_loader_exceptions():
    """Test PermissionError and general Exception in load_data."""
    with patch("pandas.read_csv", side_effect=PermissionError):
        assert data_loader.load_data("test.csv") is None

    with patch("pandas.read_csv", side_effect=Exception):
        assert data_loader.load_data("test.csv") is None


def test_optimization_service_run_failure():
    """Test failure path in OptimizationService.run (line 67)."""
    # Create an infeasible config
    df = pd.DataFrame({"Name": ["A"], "Score1": [10]})
    # Fix: Patch the internal run_optimization imported by services
    with patch(
        "src.core.services.solver_interface.run_optimization",
        return_value=(None, {"status": "FAILED"}),
    ):
        res, metrics = services.OptimizationService.run(
            df,
            [2],
            {"Score1": 1.0},
            OptimizationMode.ADVANCED,
            ConflictPriority.GROUPERS,
            10,
        )
        assert res is None
        # Assertion now expects FAILED as mocked
        assert metrics["status"] == "FAILED"


def test_solver_overflow_scaling_path():
    """Trigger the scaling down path in solver (lines 264-273)."""
    # Large score to trigger scaling
    _ = [Participant(name="A", scores={"Score1": 1e20})]
    cfg = SolverConfig(
        num_groups=1,
        group_capacities=[1],
        score_weights={"Score1": 1.0},
        timeout_seconds=1,
    )
    # This might trigger actual OR-Tools overflow but will trigger the python
    # scaling logic
    with patch("src.logger.warning") as mock_warn:
        solver.solve_with_ortools([{"Name": "A", "Score1": 1e20}], cfg)
        # Verify warning was logged
        assert mock_warn.called


def test_solver_interface_import_error_mock():
    """Test solver_interface without streamlit ctx (lines 23-43)."""
    # This is partially covered by tests but we ensure the fallback logic is exercised
    with patch("src.core.solver_interface.get_script_run_ctx", return_value=None):
        callback = solver_interface.StreamlitSolverCallback(None)
        assert callback.ctx is None
        callback.on_solution_callback()  # Should not crash
