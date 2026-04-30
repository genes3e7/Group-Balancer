# Solver Balancing and Determinism Technical Summary

## 1. Non-Determinism in Optimal Solves
- **The Issue**: The solver reported "OPTIMAL" but produced different assignment results across identical runs.
- **Root Cause**: The solver was encountering a "plateau" of equivalent L1-norm solutions. Subtle internal model construction variances (e.g., dictionary iteration order, floating-point noise in normalization) caused the solver to explore different search paths within this plateau of equal optima.
- **Fix**: Implemented a **Synthetic Tie-Breaking Objective** (`g * x[i, g]`) that forces a unique, canonical solution. Also enforced absolute model construction determinism via mandatory sorting of all iterative structures (tags, participant indices, identity buckets) and fixed random seeds.

## 2. Multi-Dimensional Balancing ("Score2")
- **The Issue**: Balancing dimensions beyond the first ("Score2") appeared ineffective, even with high weights.
- **Root Cause**: Magnitude-based objective domination. The CP-SAT solver optimizes based on the raw numeric sum of differences. A Score1 dimension with a raw scale of 100 dominated a Score2 dimension with a scale of 0.1, making the effective weight of Score2 negligible despite a high user-set multiplier.
- **Fix**: Implemented **High-Precision Integer Normalization** ($10^{10}$ scaling) for both `Simple` and `Advanced` modes. Each dimension is now scaled to a uniform magnitude before weights are applied, ensuring that user weights are the sole driver of priority, regardless of the input data's raw range.
