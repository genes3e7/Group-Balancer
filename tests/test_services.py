"""Unit tests for the service layer."""

from unittest.mock import patch

import pandas as pd
import pytest

from src.core import config
from src.core.models import ConflictPriority, OptimizationMode
from src.core.services import DataService, OptimizationService


def test_data_service_cleaning():
    """Test standard dataframe cleaning and coercion."""
    df = pd.DataFrame(
        {
            config.COL_NAME: [" Alice ", "Bob "],
            "Score1": [" 10 ", 20],
            "Other": ["x", "y"],
        },
    )
    clean = DataService.clean_participants_df(df)

    assert clean.iloc[0][config.COL_NAME] == "Alice"
    assert clean.iloc[0]["Score1"] == 10.0
    assert config.COL_GROUPER in clean.columns
    assert config.COL_SEPARATOR in clean.columns


def test_data_service_get_score_cols():
    """Test detection of score columns."""
    df = pd.DataFrame({"Name": ["A"], "Score1": [1], "Other": [2]})
    cols = DataService.get_score_columns(df)
    assert cols == ["Score1"]


def test_optimization_service_success_path():
    """Verify that the service correctly orchestrates a successful optimization run."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A", "B"],
            "Score1": [10, 20],
            config.COL_GROUPER: ["", ""],
            config.COL_SEPARATOR: ["", ""],
        },
    )
    mock_results = [{"Name": "A", "Group": 1}, {"Name": "B", "Group": 2}]
    mock_metrics = {"status": "OPTIMAL", "elapsed": 0.1}

    target = "src.core.services.solver_interface.run_optimization"
    with patch(target, return_value=(mock_results, mock_metrics)):
        res, metrics = OptimizationService.run(
            df,
            [1, 1],
            {"Score1": 1.0},
            OptimizationMode.SIMPLE,
            ConflictPriority.GROUPERS,
            10,
        )

        assert res is not None
        assert len(res) == 2
        assert metrics["status"] == "OPTIMAL"


def test_optimization_service_handles_solver_failure():
    """Ensure the service gracefully handles cases where the solver returns None."""
    df = pd.DataFrame({"Name": ["P1"], "S1": [10.0]})
    with patch(
        "src.core.services.solver_interface.run_optimization",
        return_value=(None, {"status": "INFEASIBLE"}),
    ):
        res, metrics = OptimizationService.run(
            df,
            [1],
            {"S1": 1.0},
            OptimizationMode.ADVANCED,
            ConflictPriority.GROUPERS,
            10,
        )
        assert res is None
        assert metrics["status"] == "INFEASIBLE"


def test_optimization_service_validates_group_capacities():
    """The service should raise ValueError if no group capacities are provided."""
    df = pd.DataFrame({"Name": ["P1"], "S1": [10.0]})
    with pytest.raises(ValueError, match="Group capacities cannot be empty"):
        OptimizationService.run(
            df,
            [],
            {"S1": 1.0},
            OptimizationMode.ADVANCED,
            ConflictPriority.GROUPERS,
            10,
        )


def test_data_service_cleaning_handles_missing_names():
    """COL_NAME should be added and normalized to empty string if missing."""
    df = pd.DataFrame({"Score1": [10]})
    clean = DataService.clean_participants_df(df)
    assert config.COL_NAME in clean.columns
    assert clean.iloc[0][config.COL_NAME] == ""


def test_optimization_service_catches_runtime_exceptions():
    """Verify that the service captures and reports unexpected runtime errors."""
    df = pd.DataFrame({"Name": ["P1"], "S1": [10.0]})
    target = "src.core.services.solver_interface.run_optimization"
    with patch(target, side_effect=RuntimeError("Fail")):
        _, metrics = OptimizationService.run(
            df,
            [1],
            {"S1": 1.0},
            OptimizationMode.ADVANCED,
            ConflictPriority.GROUPERS,
            10,
        )
        assert metrics["status"] == "ERROR"
        assert "Fail" in metrics["error"]
