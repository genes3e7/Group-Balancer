"""Unit tests for the service layer.

Ensures that data cleaning, score detection, and optimization orchestration
behave correctly across success and failure paths, including warm-start
logic and hint validation.
"""

from unittest.mock import patch

import pandas as pd
import pytest

from src.core import config
from src.core.models import ConflictPriority
from src.core.services import DataService, OptimizationService


def test_data_service_cleaning() -> None:
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


def test_data_service_get_score_cols() -> None:
    """Test detection of score columns."""
    df = pd.DataFrame({"Name": ["A"], "Score1": [1], "Other": [2]})
    cols = DataService.get_score_columns(df)
    assert cols == ["Score1"]


def test_optimization_service_success_path() -> None:
    """Verify that the service correctly orchestrates a successful optimization run."""
    df = pd.DataFrame(
        {
            config.COL_NAME: ["A", "B"],
            "Score1": [10, 20],
            config.COL_GROUPER: ["", ""],
            config.COL_SEPARATOR: ["", ""],
        },
    )
    mock_results = pd.DataFrame(
        [
            {"Name": "A", "Group": 1, "Score1": 10},
            {"Name": "B", "Group": 2, "Score1": 20},
        ]
    )
    mock_metrics = {"status": "OPTIMAL", "elapsed": 0.1}

    target = "src.core.solver_interface.run_optimization"
    with patch(target, return_value=(mock_results, mock_metrics)):
        res, metrics = OptimizationService.run(
            df,
            [1, 1],
            {"Score1": 1.0},
            ConflictPriority.GROUPERS,
            10,
        )

        assert res is not None
        assert len(res) == 2
        assert metrics["status"] == "OPTIMAL"


def test_optimization_service_handles_solver_failure() -> None:
    """Ensure the service gracefully handles cases where the solver returns None."""
    df = pd.DataFrame({"Name": ["P1"], "S1": [10.0]})
    with patch(
        "src.core.solver_interface.run_optimization",
        return_value=(None, {"status": "INFEASIBLE"}),
    ):
        res, metrics = OptimizationService.run(
            df,
            [1],
            {"S1": 1.0},
            ConflictPriority.GROUPERS,
            10,
        )
        assert res is None
        assert metrics["status"] == "INFEASIBLE"


def test_optimization_service_validates_group_capacities() -> None:
    """Verify the service raises ValueError if no group capacities are provided."""
    df = pd.DataFrame({"Name": ["P1"], "S1": [10.0]})
    with pytest.raises(ValueError, match="Group capacities cannot be empty"):
        OptimizationService.run(
            df,
            [],
            {"S1": 1.0},
            ConflictPriority.GROUPERS,
            10,
        )


def test_optimization_service_warm_start_hit() -> None:
    """Verify that warm-start hints are actually used when config matches."""
    data = pd.DataFrame(
        {
            config.COL_NAME: ["P1", "P2"],
            "Score1": [10, 20],
            config.COL_GROUPER: ["", ""],
            config.COL_SEPARATOR: ["", ""],
        }
    )
    weights = {"Score1": 1.0}

    res1, metrics1 = OptimizationService.run(
        data, [1, 1], weights, ConflictPriority.GROUPERS, 10
    )

    target = "src.core.solver_interface.run_optimization"
    with patch(target, return_value=(res1, metrics1)) as mock_opt:
        OptimizationService.run(
            data,
            [1, 1],
            weights,
            ConflictPriority.GROUPERS,
            10,
            previous_results=res1,
        )

        captured_cfg = mock_opt.call_args[0][1]
        assert captured_cfg.hints_by_fingerprint is not None
        assert captured_cfg.hints_by_index is not None


def test_optimization_service_warm_start_duplicate_fingerprints() -> None:
    """Verify warm-start hints rejection when duplicate profiles exist.

    Ensures hints_by_fingerprint is None when fingerprints are non-unique,
    to prevent mapping collisions.
    """
    data = pd.DataFrame(
        {
            config.COL_NAME: ["P1", "P1"],
            "Score1": [10, 10],
            config.COL_GROUPER: ["", ""],
            config.COL_SEPARATOR: ["", ""],
        }
    )
    weights = {"Score1": 1.0}

    res1, metrics1 = OptimizationService.run(
        data, [1, 1], weights, ConflictPriority.GROUPERS, 10
    )

    target = "src.core.solver_interface.run_optimization"
    with patch(target, return_value=(res1, metrics1)) as mock_opt:
        OptimizationService.run(
            data,
            [1, 1],
            weights,
            ConflictPriority.GROUPERS,
            10,
            previous_results=res1,
        )

        captured_cfg = mock_opt.call_args[0][1]
        # Fingerprint hints disabled due to duplicates, but index-based hints
        # should fall back and be used since the multiset alignment is perfect.
        assert captured_cfg.hints_by_fingerprint is None
        assert captured_cfg.hints_by_index is not None

        # Derive expected mapping from res1 to be invariant to label swaps
        expected_mapping = dict(
            zip(
                res1["_original_index"].astype(int),
                res1[config.COL_GROUP],
                strict=False,
            )
        )
        assert dict(captured_cfg.hints_by_index) == expected_mapping


def test_data_service_cleaning_edge_cases() -> None:
    """Cover name and tag sanitization branches (None/NaN)."""
    df = pd.DataFrame(
        {
            config.COL_NAME: [None, " P1 "],
            config.COL_GROUPER: [float("nan"), " G1 "],
            config.COL_SEPARATOR: [None, " S1 "],
            "Score1": [10.0, 20.0],
        }
    )
    cleaned = DataService.clean_participants_df(df)
    assert cleaned.iloc[0][config.COL_NAME] == ""
    assert cleaned.iloc[0][config.COL_GROUPER] == ""
    assert cleaned.iloc[1][config.COL_NAME] == "P1"
    assert cleaned.iloc[1][config.COL_GROUPER] == "G1"


def test_optimization_service_unexpected_exception() -> None:
    """Cover the unexpected exception catch block in OptimizationService.run."""
    with (
        patch(
            "src.core.services.OptimizationService.reduce_score_weights",
            side_effect=RuntimeError("System crash"),
        ),
        patch("src.core.services.logger.exception") as mock_log,
    ):
        with pytest.raises(RuntimeError, match="System crash"):
            OptimizationService.run(
                pd.DataFrame(), [1], {"Score1": 1.0}, ConflictPriority.GROUPERS, 10
            )
        assert mock_log.called


def test_optimization_service_alignment_error_logging() -> None:
    """Cover the alignment error log branch in warm-start hint resolution."""
    # Data with duplicate fingerprints (same name/scores/tags)
    data = pd.DataFrame(
        {config.COL_NAME: ["P1", "P1"], "Score1": [10, 10], "_original_index": [0, 1]}
    )
    weights = {"Score1": 1.0}
    priority = ConflictPriority.GROUPERS
    capacities = [1, 1]

    res1, _ = OptimizationService.run(data, capacities, weights, priority, 5)
    assert res1 is not None

    # Metadata MUST match EXACTLY for the logic to reach the alignment check.
    res_err = res1.copy()
    res_err.attrs = res1.attrs.copy()

    # Multiset check (current_f == prev_f) must PASS.
    # But pair check (current_pairs == prev_pairs) must FAIL.
    # We swap indices to cause alignment error while keeping the multiset identical.
    res_err.at[0, "_original_index"] = 999

    with patch("src.core.services.logger.info") as mock_log:
        OptimizationService.run(
            data, capacities, weights, priority, 5, previous_results=res_err
        )
        # Verify it reached the specific 'alignment error' branch
        mock_log.assert_any_call("Ignoring stale hints (alignment error).")


def test_stale_hints_logging() -> None:
    """Verify that informational logs are emitted for stale hints."""
    data = pd.DataFrame(
        {
            config.COL_NAME: ["P1"],
            "Score1": [10],
            "Score2": [10],
            "_original_index": [0],
        }
    )
    res1, _ = OptimizationService.run(
        data, [1], {"Score1": 1.0, "Score2": 1.0}, ConflictPriority.GROUPERS, 5
    )

    with patch("src.core.services.logger.info") as mock_log:
        # 1. Config mismatch (1:1 reduces to 1:1, 1:2 reduces to 1:2)
        OptimizationService.run(
            data,
            [1],
            {"Score1": 1.0, "Score2": 2.0},
            ConflictPriority.GROUPERS,
            5,
            previous_results=res1,
        )
        mock_log.assert_any_call("Ignoring stale warm-start hints (config change).")

        # 2. Data mismatch (fingerprint change)
        data2 = data.copy()
        data2.at[0, "Score1"] = 20
        OptimizationService.run(
            data2,
            [1],
            {"Score1": 1.0, "Score2": 1.0},
            ConflictPriority.GROUPERS,
            5,
            previous_results=res1,
        )
        mock_log.assert_any_call("Ignoring stale warm-start hints (mismatch)")

        # 3. Indices mismatch (structural)
        # Corrupt indices while keeping fingerprints valid-ish (by dropping them)
        res_no_fp = res1.copy().drop(columns=["participant_fingerprint"])
        res_no_fp.attrs = res1.attrs.copy()
        res_no_fp.at[0, "_original_index"] = 999
        OptimizationService.run(
            data,
            [1],
            {"Score1": 1.0, "Score2": 1.0},
            ConflictPriority.GROUPERS,
            5,
            previous_results=res_no_fp,
        )
        mock_log.assert_any_call(
            "Ignoring stale hints (indices mismatch or duplicates)."
        )


def test_data_service_cleaning_handles_missing_names() -> None:
    """Verify COL_NAME is added and normalized to empty string if missing."""
    df = pd.DataFrame({"Score1": [10]})
    clean = DataService.clean_participants_df(df)
    assert config.COL_NAME in clean.columns
    assert clean.iloc[0][config.COL_NAME] == ""


def test_optimization_service_catches_runtime_exceptions() -> None:
    """Verify that the service captures and re-raises unexpected runtime errors."""
    df = pd.DataFrame({"Name": ["P1"], "S1": [10.0]})
    # Cause an error inside the try block
    with (
        patch("src.core.services.Participant", side_effect=RuntimeError("Fail")),
        pytest.raises(RuntimeError, match="Fail"),
    ):
        OptimizationService.run(
            df,
            [1],
            {"S1": 1.0},
            ConflictPriority.GROUPERS,
            10,
        )


def test_optimization_service_invalid_input_none() -> None:
    """Verify OptimizationService.run raises ValueError on None input."""
    with pytest.raises(ValueError, match="Participants DataFrame cannot be None"):
        OptimizationService.run(
            None,
            [1],
            {"Score1": 1.0},
            ConflictPriority.GROUPERS,
            10,
        )
