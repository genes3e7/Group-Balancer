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


def test_optimization_service_success():
    """Test successful optimization wrap."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A", "B"],
            "Score1": [10, 20],
            config.COL_GROUPER: ["", ""],
            config.COL_SEPARATOR: ["", ""],
        },
    )
    res, metrics = OptimizationService.run(
        df,
        [1, 1],
        {"Score1": 1.0},
        opt_mode=OptimizationMode.SIMPLE,
        conflict_priority=ConflictPriority.GROUPERS,
        timeout_seconds=5,
    )

    assert res is not None
    assert len(res) == 2
    assert metrics["status"] in ["OPTIMAL", "FEASIBLE"]


def test_optimization_service_run_fail_branch():
    """Cover line 41 (res is None)."""
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


def test_optimization_service_empty_caps():
    """Cover line 108 (Group capacities cannot be empty)."""
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


def test_data_service_cleaning_no_name():
    """Cover line 41 (COL_NAME not in columns)."""
    df = pd.DataFrame({"Score1": [10]})
    clean = DataService.clean_participants_df(df)
    assert config.COL_NAME in clean.columns
    assert clean.iloc[0][config.COL_NAME] == ""


def test_optimization_service_error_handling_hit_108():
    """Cover line 108 (Exception branch)."""
    df = pd.DataFrame({"Name": ["P1"], "S1": [10.0]})
    with patch(
        "src.core.services.solver_interface.run_optimization",
        side_effect=RuntimeError("Fail"),
    ):
        res, metrics = OptimizationService.run(
            df,
            [1],
            {"S1": 1.0},
            OptimizationMode.ADVANCED,
            ConflictPriority.GROUPERS,
            10,
        )
        assert metrics["status"] == "ERROR"
