"""Unit tests for the service layer logic."""

from unittest.mock import patch

import pandas as pd
import pytest

from src.core import config
from src.core.models import ConflictPriority, Participant
from src.core.services import (
    DataService,
    HintResolutionConfig,
    OptimizationService,
    _resolve_warm_start_hints,
)


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Fixture providing a sanitized participant DataFrame."""
    return pd.DataFrame(
        [
            {"Name": "A", "Score1": 10.0, "Score2": 20.0, "_original_index": 0},
            {"Name": "B", "Score1": 20.0, "Score2": 10.0, "_original_index": 1},
        ]
    )


def test_data_service_cleaning(sample_df: pd.DataFrame) -> None:
    """Verify that DataService cleans and coerces raw data correctly."""
    cleaned = DataService.clean_participants_df(sample_df)
    assert cleaned.columns.tolist() == [
        "Name",
        "Score1",
        "Score2",
        "_original_index",
        "Groupers",
        "Separators",
    ]


def test_data_service_get_score_cols(sample_df: pd.DataFrame) -> None:
    """Verify detection of score columns based on prefix."""
    cols = DataService.get_score_columns(sample_df)
    assert cols == ["Score1", "Score2"]


def test_optimization_service_success_path(sample_df: pd.DataFrame) -> None:
    """Verify that OptimizationService.run handles the end-to-end flow."""
    with patch("src.core.solver_interface.run_optimization") as mock_run:
        mock_run.return_value = (pd.DataFrame(), {"status": "OPTIMAL"})

        _, metrics = OptimizationService.run(
            sample_df,
            [1, 1],
            {"Score1": 1.0, "Score2": 1.0},
            ConflictPriority.GROUPERS,
            10,
        )

        assert metrics["status"] == "OPTIMAL"
        assert mock_run.called


def test_optimization_service_handles_solver_failure(sample_df: pd.DataFrame) -> None:
    """Verify error reporting when the underlying solver fails."""
    with patch("src.core.solver_interface.run_optimization") as mock_run:
        mock_run.return_value = (None, {"status": "ERROR", "error": "test"})

        res, metrics = OptimizationService.run(
            sample_df, [1, 1], {"S": 1.0}, ConflictPriority.GROUPERS, 10
        )
        assert res is None
        assert metrics["status"] == "ERROR"


def test_optimization_service_validates_group_capacities(
    sample_df: pd.DataFrame,
) -> None:
    """Verify that OptimizationService prevents empty capacity lists."""
    with pytest.raises(ValueError, match="Group capacities cannot be empty"):
        OptimizationService.run(
            sample_df, [], {"S": 1.0}, ConflictPriority.GROUPERS, 10
        )


def test_optimization_service_warm_start_hit(sample_df: pd.DataFrame) -> None:
    """Verify that warm-start hints are generated for valid previous results."""
    # 1. Create a previous result snapshot
    prev_results = sample_df.copy()
    prev_results[config.COL_GROUP] = [1, 2]
    prev_results["participant_fingerprint"] = [
        Participant("A", {"Score1": 10, "Score2": 20}).fingerprint,
        Participant("B", {"Score1": 20, "Score2": 10}).fingerprint,
    ]
    prev_results.attrs = {
        "score_weights": {"Score1": 1.0, "Score2": 1.0},
        "conflict_priority": ConflictPriority.GROUPERS,
        "group_capacities": [1, 1],
        "grouper_weight": 1,
        "separator_weight": 1,
    }

    # 2. Mock solver and run with previous results
    with patch("src.core.solver_interface.run_optimization") as mock_run:
        mock_run.return_value = (pd.DataFrame(), {"status": "OPTIMAL"})
        OptimizationService.run(
            sample_df,
            [1, 1],
            {"Score1": 1.0, "Score2": 1.0},
            ConflictPriority.GROUPERS,
            10,
            previous_results=prev_results,
        )

        # 3. Verify hints were passed to the solver config
        cfg = mock_run.call_args[0][1]
        assert cfg.hints_by_fingerprint is not None
        assert (
            cfg.hints_by_fingerprint[prev_results.loc[0, "participant_fingerprint"]]
            == 1
        )


def test_optimization_service_warm_start_duplicate_fingerprints() -> None:
    """Verify that index-based fallback is used when fingerprints are not unique."""
    # 1. Create identical profiles
    data = pd.DataFrame(
        [
            {"Name": "X", "Score1": 10, "_original_index": 0},
            {"Name": "X", "Score1": 10, "_original_index": 1},
        ]
    )
    fp = Participant("X", {"Score1": 10}).fingerprint
    res1 = data.copy()
    res1[config.COL_GROUP] = [1, 2]
    res1["participant_fingerprint"] = [fp, fp]  # Duplicate fingerprints
    res1.attrs = {
        "score_weights": {"Score1": 1.0},
        "conflict_priority": ConflictPriority.GROUPERS,
        "group_capacities": [1, 1],
        "grouper_weight": 1,
        "separator_weight": 1,
    }

    with patch("src.core.solver_interface.run_optimization") as mock_run:
        mock_run.return_value = (pd.DataFrame(), {"status": "OPTIMAL"})
        OptimizationService.run(
            data,
            [1, 1],
            {"Score1": 1.0},
            ConflictPriority.GROUPERS,
            10,
            previous_results=res1,
        )
        cfg = mock_run.call_args[0][1]
        # In this case, hints_by_fingerprint should be None (due to duplication)
        # but hints_by_index should be populated.
        assert cfg.hints_by_fingerprint is None
        assert cfg.hints_by_index is not None
        assert cfg.hints_by_index[0] == 1


def test_data_service_cleaning_edge_cases() -> None:
    """Cover cleaning logic when categorical columns are missing."""
    df = pd.DataFrame({"Name": ["A"], "Score1": [10]})
    cleaned = DataService.clean_participants_df(df)
    assert "Groupers" in cleaned.columns
    assert cleaned.loc[0, "Groupers"] == ""


def test_optimization_service_unexpected_exception(sample_df: pd.DataFrame) -> None:
    """Verify that OptimizationService logs and re-raises unknown errors."""
    with patch(
        "src.core.services.OptimizationService.reduce_score_weights",
        side_effect=RuntimeError("Crash"),
    ):
        with pytest.raises(RuntimeError, match="Crash"):
            OptimizationService.run(
                sample_df, [1, 1], {"S": 1.0}, ConflictPriority.GROUPERS, 10
            )


def test_optimization_service_alignment_error_logging() -> None:
    """Exercise the alignment error fallback branch in hint resolution."""
    data = pd.DataFrame(
        [
            {"Name": "X", "Score1": 10, "_original_index": 0},
            {"Name": "X", "Score1": 10, "_original_index": 1},
        ]
    )
    fp = Participant("X", {"Score1": 10}).fingerprint
    res1 = data.copy()
    res1[config.COL_GROUP] = [1, 2]
    res1["participant_fingerprint"] = [fp, fp]
    res1.attrs = {
        "score_weights": {"Score1": 1.0},
        "conflict_priority": ConflictPriority.GROUPERS,
        "group_capacities": [1, 1],
        "grouper_weight": 1,
        "separator_weight": 1,
    }

    # Corrupt the index mapping in res1 to trigger the alignment error
    res_err = res1.copy()
    res_err.loc[0, "_original_index"] = 999
    res_err.attrs = res1.attrs.copy()

    with patch("src.core.services.logger.info") as mock_log:
        OptimizationService.run(
            data,
            [1, 1],
            {"Score1": 1.0},
            ConflictPriority.GROUPERS,
            10,
            previous_results=res_err,
        )
        # Check for any log starting with "Ignoring stale hints"
        found = any(
            "Ignoring stale hints" in call.args[0] for call in mock_log.call_args_list
        )
        assert found


def test_stale_hints_logging(sample_df: pd.DataFrame) -> None:
    """Verify that informational logs are emitted for stale hints."""
    res1 = sample_df.copy()
    res1[config.COL_GROUP] = [1, 2]
    res1["participant_fingerprint"] = ["f1", "f2"]
    res1.attrs = {
        "score_weights": {"Score1": 9.9},  # Changed
        "conflict_priority": ConflictPriority.GROUPERS,
        "group_capacities": [1, 1],
        "grouper_weight": 1,
        "separator_weight": 1,
    }

    with patch("src.core.services.logger.info") as mock_log:
        # 1. Config change
        OptimizationService.run(
            sample_df,
            [1, 1],
            {"Score1": 1.0, "Score2": 1.0},
            ConflictPriority.GROUPERS,
            5,
            previous_results=res1,
        )
        mock_log.assert_any_call("Ignoring stale warm-start hints (config change).")

        # 2. Data mismatch (fingerprint change)
        data2 = sample_df.copy()
        data2.loc[0, "Score1"] = 20
        OptimizationService.run(
            data2,
            [1, 1],
            {"Score1": 1.0, "Score2": 1.0},
            ConflictPriority.GROUPERS,
            5,
            previous_results=res1,
        )

        # 3. Indices mismatch (structural)
        res_no_fp = res1.copy().drop(columns=["participant_fingerprint"])
        res_no_fp.attrs = res1.attrs.copy()
        res_no_fp.loc[0, "_original_index"] = 999
        OptimizationService.run(
            sample_df,
            [1, 1],
            {"Score1": 1.0, "Score2": 1.0},
            ConflictPriority.GROUPERS,
            5,
            previous_results=res_no_fp,
        )


def test_data_service_cleaning_handles_missing_names() -> None:
    """Ensure Name column is created if missing in clean_participants_df."""
    df = pd.DataFrame({"Score1": [10]})
    cleaned = DataService.clean_participants_df(df)
    assert config.COL_NAME in cleaned.columns
    assert cleaned.loc[0, config.COL_NAME] == ""


def test_optimization_service_catches_runtime_exceptions(
    sample_df: pd.DataFrame,
) -> None:
    """Verify that general exceptions in run are re-raised after logging."""
    with patch(
        "src.core.services.Participant", side_effect=RuntimeError("Object crash")
    ):
        with pytest.raises(RuntimeError):
            OptimizationService.run(
                sample_df, [1, 1], {"S": 1}, ConflictPriority.GROUPERS, 5
            )


def test_optimization_service_invalid_input_none() -> None:
    """Verify that run() raises ValueError if participants_df is None."""
    with pytest.raises(ValueError, match="Participants DataFrame cannot be None"):
        OptimizationService.run(None, [1], {"S": 1}, ConflictPriority.GROUPERS, 5)


def test_services_resolve_hints_mismatch_fp() -> None:
    """Cover current_f != prev_f mismatch branch."""
    p = [Participant(name="A", scores={"S1": 10}, original_index=0)]
    prev = pd.DataFrame(
        {config.COL_GROUP: [1], "participant_fingerprint": ["stale_fp"]}
    )
    prev.attrs = {
        "score_weights": {"S1": 1.0},
        "conflict_priority": ConflictPriority.GROUPERS,
        "group_capacities": [1],
        "grouper_weight": 1,
        "separator_weight": 1,
    }
    cfg = HintResolutionConfig(
        score_weights={"S1": 1.0},
        conflict_priority=ConflictPriority.GROUPERS,
        group_capacities=[1],
        grouper_weight=1,
        separator_weight=1,
    )
    with patch("src.core.services.logger.info") as mock_log:
        fp, idx = _resolve_warm_start_hints(p, prev, cfg)
        assert fp is None
        assert idx is None
        assert mock_log.called


def test_services_reduce_weights_empty() -> None:
    """Cover not weights branch."""
    assert OptimizationService.reduce_score_weights({}) == {}


def test_services_reduce_weights_validation() -> None:
    """Cover weight validation loop."""
    with pytest.raises(ValueError, match="Invalid weight"):
        OptimizationService.reduce_score_weights({"S1": -1.0})
    with pytest.raises(ValueError, match="Invalid weight"):
        OptimizationService.reduce_score_weights({"S1": float("nan")})


def test_services_run_value_error() -> None:
    """Cover ValueError branch in run for empty capacities."""
    df = pd.DataFrame({"A": [1]})
    with pytest.raises(ValueError, match="Group capacities cannot be empty"):
        OptimizationService.run(df, [], {}, ConflictPriority.GROUPERS, 10)
