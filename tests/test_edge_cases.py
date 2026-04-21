from src.core.models import (
    ConflictPriority,
    OptimizationMode,
    Participant,
    SolverConfig,
)
from src.core.solver_interface import run_optimization


def test_circular_conflict():
    """Test solver behavior with circular or contradictory constraints."""
    # A groupers B, B groupers C, C separators A
    participants = [
        Participant(name="A", scores={"S": 10}, groupers="X", separators="Z"),
        Participant(name="B", scores={"S": 10}, groupers="X", separators=""),
        Participant(name="C", scores={"S": 10}, groupers="Y", separators="X"),
    ]

    config = SolverConfig(
        num_groups=2,
        group_capacities=[2, 1],
        score_weights={"S": 1.0},
        opt_mode=OptimizationMode.SIMPLE,
        conflict_priority=ConflictPriority.GROUPERS,
    )

    # Solver should still find a feasible solution even if soft constraints conflict
    df, metrics = run_optimization(participants, config)
    assert df is not None
    assert len(df) == 3
    assert metrics["status"] in ["OPTIMAL", "FEASIBLE"]


def test_empty_tags_handling():
    """Ensure empty tag strings don't crash the solver."""
    participants = [
        Participant(name="A", scores={"S": 10}, groupers="", separators=""),
        Participant(name="B", scores={"S": 10}, groupers=" ", separators="  "),
    ]
    config = SolverConfig(
        num_groups=2,
        group_capacities=[1, 1],
        score_weights={"S": 1.0},
    )
    df, metrics = run_optimization(participants, config)
    assert metrics["status"] in ["OPTIMAL", "FEASIBLE"]
