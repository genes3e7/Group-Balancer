import logging

import pandas as pd

from src.core import config
from src.core.models import ConflictPriority, OptimizationMode
from src.core.services import OptimizationService

# Setup logging
logging.basicConfig(level=logging.INFO)


def create_sample_data():
    """15 participants, 2 groups, with identical scores to test symmetry."""
    data = {
        config.COL_NAME: [f"Person {i}" for i in range(15)],
        "Score1": [10, 10, 10, 20, 20, 20, 30, 30, 30, 40, 40, 40, 50, 50, 50],
        "Score2": [10, 10, 10, 20, 20, 20, 30, 30, 30, 40, 40, 40, 50, 50, 50],
        config.COL_GROUPER: [""] * 15,
        config.COL_SEPARATOR: [""] * 15,
    }
    return pd.DataFrame(data)


def run_test():
    """Execute determinism diagnostics."""
    df = create_sample_data()
    group_capacities = [8, 7]
    score_weights = {"Score1": 1.0, "Score2": 1.0}

    print("\n>>> DETERMINISM TEST: 3 COLD STARTS")
    results = []
    for i in range(3):
        res, metrics = OptimizationService.run(
            df,
            group_capacities,
            score_weights,
            OptimizationMode.ADVANCED,
            ConflictPriority.GROUPERS,
            10,
        )
        std = res.groupby(config.COL_GROUP)["Score1"].mean().std(ddof=1)
        print(f"Run {i + 1} Cold: Status={metrics['status']}, Std={std:.6f}")
        results.append(res[config.COL_GROUP].tolist())

    if all(r == results[0] for r in results):
        print("✅ SUCCESS: Cold starts are deterministic.")
    else:
        print("❌ FAILURE: Cold starts are non-deterministic!")

    print("\n>>> DETERMINISM TEST: WEIGHT TOGGLE (W1=1:W2=0 vs W1=0:W2=1)")
    res_a, m_a = OptimizationService.run(
        df,
        group_capacities,
        {"Score1": 1.0, "Score2": 0.0},
        OptimizationMode.ADVANCED,
        ConflictPriority.GROUPERS,
        10,
    )
    res_b, m_b = OptimizationService.run(
        df,
        group_capacities,
        {"Score1": 0.0, "Score2": 1.0},
        OptimizationMode.ADVANCED,
        ConflictPriority.GROUPERS,
        10,
    )

    std_a = res_a.groupby(config.COL_GROUP)["Score1"].mean().std(ddof=1)
    std_b = res_b.groupby(config.COL_GROUP)["Score2"].mean().std(ddof=1)

    print(f"W1=1, W2=0: Status={m_a['status']}, Std1={std_a:.6f}")
    print(f"W1=0, W2=1: Status={m_b['status']}, Std2={std_b:.6f}")

    if res_a[config.COL_GROUP].tolist() == res_b[config.COL_GROUP].tolist():
        print("✅ SUCCESS: Weight toggle is deterministic.")
    else:
        print("❌ FAILURE: Weight toggle produced different results!")

    print("\n>>> DETERMINISM TEST: WARM START CONTINUITY")
    res_c, m_c = OptimizationService.run(
        df,
        group_capacities,
        {"Score1": 1.0, "Score2": 0.0},
        OptimizationMode.ADVANCED,
        ConflictPriority.GROUPERS,
        10,
        previous_results=res_a,
    )

    if res_a[config.COL_GROUP].tolist() == res_c[config.COL_GROUP].tolist():
        print("✅ SUCCESS: Warm start preserved the solution.")
    else:
        print("❌ FAILURE: Warm start drifted from the previous solution!")


if __name__ == "__main__":
    run_test()
