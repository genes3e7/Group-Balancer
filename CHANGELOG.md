# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [6.0.0] - 2026-05-10

### Added

- **Multi-Dimensional Scoring:** Support for balancing groups across multiple score dimensions with user-configurable weights.
- **Custom Group Capacities:** Ability to explicitly define exact capacities for each group instead of strictly balanced splits.
- **Advanced Categorical Constraints:** Character-based `Groupers` (keep together) and `Separators` (spread apart) tags with proportional pigeonhole distribution.
- **Build Hardening:** Secured the build pipeline by resolving absolute PyInstaller paths and implementing static tree-shaking using protected/dev/banned package lists to minimize bundle size while protecting core dependencies.
- **Solver Optimization - Relative Weight Scaling (GCD Reduction):** Implemented a refined weight normalization engine that scales all coefficients relative to the smallest positive weight before using Greatest Common Divisor (GCD) reduction to convert them to their simplest irreducible integer ratios. This ensures that fractional user-defined ratios are perfectly preserved in the solver's objective function, leading to denser search trees and significantly faster pruning/convergence.
- **Solver Optimization - Max-Min Fairness:** Integrated Lexicographical Max-Min Tier to accelerate proof times and eliminate outliers.
- **Solver Optimization - Squared Exact Math (L2):** Architecture shift to minimize sum of squared deviations for aggressive balancing results.
- **Solver Optimization - Symmetry Breaking:** Enforces ordering on identical participants and groups to drastically reduce search space.
- **Solver Optimization - Solution Hinting:** Identity-based warm starts using previous solver results to speed up iterative tweak-and-solve cycles.
- **Solver Optimization - Configuration Cache:** Implemented a Least Recently Used (LRU) memoization layer that caches the best-found solutions for up to 50 distinct weight/capacity combinations, enabling instant comparison and iterative refinement.
- **Solver Optimization - Advanced Parameters:** Tuned CP-SAT internal parameters (`linearization_level=0`, `symmetry_level=2`) for faster partition math.
- **Solver Hardening - Dynamic Precision Scaling:** Mathematically prevents 64-bit integer overflow for large datasets ($N=1000$) while maintaining 0.001 target precision.
- **Solver Hardening - Aggregate Objective Guard:** Implemented a Fail-Fast `ValueError` if the theoretical maximum objective sum exceeds CP-SAT's 64-bit limits, ensuring absolute numerical safety.
- **Solver Hardening - Scaling Enforcement:** Added `tests/test_scaling_tiers.py` to programmatically lock in the bit-slicing priority hierarchy and resolution constants.
- **Solver Hardening - Dual-Layer Determinism:** Implemented a 'Stability vs. Representation' validation strategy. Integrated an `interleave_search` flag to guarantee bit-for-bit identity for audits (Level 1) while maintaining high-speed 'Race Mode' for production UX (Level 2), with tests covering both scenarios.
- **UI Hardening - State Clamping:** Added defensive session state clamping for group capacities to prevent out-of-bounds rendering when switching datasets.
- **UI Hardening - Upload Resilience:** Implemented MD5 cryptographic signatures for file uploads to robustly detect edits even if filename and size remain identical.
- **UI Hardening - Selective Reset:** Optimized the 'Start Over' logic to preserve the high-value configuration cache while securely purging session-specific participant data.
- **Async High-Performance UI:** Native CSS progress bars and fragmented rendering to ensure the tool feels "alive" and responsive during engine initialization.
- **Detailed Solver Error Reporting:** The UI now surfaces specific optimization failure reasons (e.g., `INFEASIBLE`, `MODEL_INVALID`) with actionable troubleshooting tips.
- **Pre-CI Refactoring:** Cross-platform Python orchestrator using `uv` (`tools/pre_ci.py`) replacing legacy PowerShell scripts.
- **CI/CD:** Migrated workflow to use `uv` for ultra-fast dependency resolution and deterministic lockfile management (`uv.lock`).

### Changed

- **UI Modernization:** Upgraded results view to use interactive `st.data_editor` cards, enabling stable manual member reassignments.
- **Core Architecture:** Implemented Strategy, Builder, and TagProcessor patterns for professional engineering standards.
- **Documentation:** Standardized the entire codebase to 100% Google-style docstrings and updated the README with dynamic project trees.

### Fixed

- **Solver Logic Fix:** Resolved `KeyError` in branching strategy by decoupling decision variables from non-contiguous participant indices.
- **Solver Optimization:** Fixed `OptimizationService.run` to correctly apply weight reduction, ensuring peak solver performance as intended by the architectural design.
- **UI Resilience:** Added defensive coercion and clamping to group capacity inputs to prevent application crashes from stale session state.
- **Manual Sync Integrity:** Restored the ability to sync manual reassignments from the data editor by preserving the hidden `_original_index` anchor.
- **Accessibility:** Standardized progress bar ARIA semantics and step coloring for improved screen reader compatibility.
- **Build Pipeline:** Hardened artifact path anchoring in the build script to prevent file scattering during execution from outside the project root.
- **Solver Stability:** Resolved CP-SAT integer overflow risks using global theoretical bounds tracking (`max_abs_diff_bound`) and surfaced `random_seed` for total search control.
