# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [6.0.0] - 2026-05-10

### Added
- **Multi-Dimensional Scoring:** Support for balancing groups across multiple score dimensions with user-configurable weights.
- **Custom Group Capacities:** Ability to explicitly define exact capacities for each group instead of strictly balanced splits.
- **Advanced Categorical Constraints:** Character-based `Groupers` (keep together) and `Separators` (spread apart) tags with proportional pigeonhole distribution.
- **Solver Optimization - Max-Min Fairness**: Integrated Lexicographical Max-Min Tier to accelerate proof times and eliminate outliers.
- **Solver Optimization - Squared Exact Math (L2)**: Architecture shift to minimize sum of squared deviations for aggressive balancing results.
- **Solver Optimization - Symmetry Breaking**: Enforces ordering on identical participants and groups to drastically reduce search space.
- **Solver Optimization - Solution Hinting**: Identity-based warm starts using previous solver results to speed up iterative tweak-and-solve cycles.
- **Solver Optimization - Configuration Cache**: Implemented a Least Recently Used (LRU) memoization layer that caches the best-found solutions for up to 50 distinct weight/capacity combinations, enabling instant comparison and iterative refinement.
- **Solver Optimization - Advanced Parameters**: Tuned CP-SAT internal parameters (`linearization_level=0`, `symmetry_level=2`) for faster partition math.
- **Solver Hardening - Dynamic Precision Scaling**: Mathematically prevents 64-bit integer overflow for large datasets ($N=1000$) while maintaining 0.001 target precision.
- **Solver Hardening - Aggregate Objective Guard**: Implemented a Fail-Fast `ValueError` if the theoretical maximum objective sum exceeds CP-SAT's 64-bit limits, ensuring absolute numerical safety.
- **Solver Hardening - Scaling Enforcement**: Added `tests/test_scaling_tiers.py` to programmatically lock in the bit-slicing priority hierarchy and resolution constants.
- **UI Hardening - State Clamping**: Added defensive session state clamping for group capacities to prevent out-of-bounds rendering when switching datasets.
- **UI Hardening - Upload Signatures**: Implemented content-based signatures (MD5) for file uploads to robustly detect edits even if filename and size remain identical.
- **UI Hardening - Selective Reset**: Optimized the 'Start Over' logic to preserve the high-value configuration cache while securely purging session-specific participant data.
- **Async High-Performance UI:** Native CSS progress bars and fragmented rendering to ensure the tool feels "alive" and responsive during engine initialization.
- **Detailed Solver Error Reporting:** The UI now surfaces specific optimization failure reasons (e.g., `INFEASIBLE`, `MODEL_INVALID`) with actionable troubleshooting tips.
- **Pre-CI Refactoring:** Cross-platform Python orchestrator using `uv` (`tools/pre_ci.py`) replacing legacy PowerShell scripts.
- **CI/CD:** Migrated workflow to use `uv` for ultra-fast dependency resolution and deterministic lockfile management (`uv.lock`).

### Changed
- **UI Modernization:** Upgraded results view to use interactive `st.data_editor` cards, enabling stable manual member reassignments.
- **Core Architecture:** Implemented Strategy, Builder, and TagProcessor patterns for professional engineering standards.
- **Documentation:** Standardized the entire codebase to 100% Google-style docstrings and updated the README with dynamic project trees.

### Fixed
- **Solver Stability:** Resolved CP-SAT integer overflow risks using global theoretical bounds tracking (`max_abs_diff_bound`).
- **Search Determinism:** Implemented deterministic tie-breaking in branching strategy (Impact DESC, Index ASC).
- **Data Ingestion:** Hardened file upload validation with column header normalization and robust numeric coercion.
- **Warm Start Reliability:** Hardened fingerprint validation to safely fall back to index-based hints if duplicate participant profiles are detected.
- **CI Integrity:** Fixed version sorting logic, added safety guards for README updates, and enforced secure workflow permissions.
