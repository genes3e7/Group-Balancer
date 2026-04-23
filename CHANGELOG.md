# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [6.0.0] - 2026-04-22

### Added
- **Detailed Solver Error Reporting:** The UI now surfaces specific optimization failure reasons (e.g., `INFEASIBLE`, `MODEL_INVALID`) with actionable troubleshooting tips.
- **GitHub CLI Integration (GEMINI.md):** Added a mandate for using the GitHub CLI (`gh`) to check PR reviews and CI status before starting work.
- **Workflow Refinement (GEMINI.md):** Introduced an exception to skip the mandatory pre-CI validation if changes are strictly limited to non-code/non-config files (e.g., CHANGELOG). Note: `README.md` and configuration files still trigger full validation.
- **Project Mandates (GEMINI.md):** Formalized architectural decisions, framework-specific quirks (Streamlit `width="stretch"`), and a mandatory post-change validation workflow to ensure long-term codebase integrity.
- **Multi-Dimensional Scoring:** Support for balancing groups across multiple score dimensions with user-configurable weights.
- **Custom Group Capacities:** Ability to explicitly define exact capacities for each group instead of strictly balanced splits.
- **Advanced Categorical Constraints:** Replaced legacy "star player" logic with character-based `Groupers` (keep together) and `Separators` (spread apart) tags.
- **Core Architecture:** Implemented Strategy, Builder, and TagProcessor patterns for the Google OR-Tools CP-SAT solver.
- **Service Layer:** Introduced `DataService` and `OptimizationService` to cleanly decouple UI from business logic.
- **Live Solver UI:** Added live optimization progress tracking and clear feedback on "Optimal" vs "Feasible" solutions.
- **Enhanced Exports:** Excel exporter now dynamically adapts to multi-dimensional score columns and includes dataset-level statistics.
- **CI/CD:** Migrated workflow to use `uv` for ultra-fast dependency resolution and lockfile management (`uv.lock`).

### Changed
- **UI Modernization:** Upgraded results view to use interactive `st.data_editor` cards, enabling stable, index-based manual member reassignments.
- **Parameter Reversion:** Restored `width='stretch'` instead of `use_container_width` to maintain backward compatibility and avoid future deprecations (codified in `GEMINI.md`).
- **Documentation:** Standardized the entire codebase to 100% Google-style docstrings and updated the README with dynamic project trees.
- **Dependency Management:** Removed legacy `requirements.in/txt` in favor of `pyproject.toml` and `uv`.

### Fixed
- **Solver Stability:** Resolved CP-SAT integer overflow risks using dynamic bounds scaling and tightened symmetry-breaking rules to prevent over-constraining models.
- **Data Ingestion:** Hardened file upload validation with column header normalization and robust numeric coercion for sparse data.
- **UI State Corruption:** Fixed group assignment corruption by ensuring stable original row indices are preserved during aggregations.
- **CI Integrity:** Fixed version sorting logic, added safety guards for README updates, and enforced secure workflow permissions (`contents: read`).
- **Tooling:** Refined `.gitignore` parsing to handle symlinks safely and improved regex for Python version badges.
