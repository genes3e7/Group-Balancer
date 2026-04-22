# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [6.1.1] - 2026-04-22

### Fixed
- **UI:** Resolved group assignment corruption by switching to index-based row matching in result editors.
- **Data Entry:** Improved file upload validation to catch missing required columns early.
- **Solver Interface:** Removed dead `stop_early` logic and redundant script-run context re-attachment.
- **CI/CD:** Fixed operator precedence bug in version determination and added empty-file guard for README updates.
- **Tools:** Refined `.gitignore` parsing and Python version badge regex in `update_readme.py`.
- **Tests:** Fixed duplicate assertions and updated solver status checks to use enum constants.
- **Type Safety:** Enhanced type hints and defaults in test configuration helpers.

## [6.1.0] - 2026-04-21

### Added
- **Core Architecture:** Implemented Strategy, Builder, and TagProcessor patterns for the CP-SAT solver.
- **Service Layer:** Introduced `DataService` and `OptimizationService` to decouple UI from business logic.
- **Security:** Hardened input validation with path sanitization, size limits, and CP-SAT overflow scaling.
- **Type System:** Migrated to strongly-typed models using `dataclasses` and `MappingProxyType`.
- **Logging:** Standardized internal telemetry using Python's logging library.
- **New Tests:** 
  - `test_models_unit.py`: Validation logic for configurations.
  - `test_services.py`: Integration checks for the service layer.
  - `test_coverage_edge_cases.py`: Defensive error path verification.
  - `test_infra.py`: Build and app importability tests.
- **CI/CD:** Migrated CI pipeline to `uv` for 3x faster execution and improved dependency resolution.

### Changed
- **UI Restoration:** Restored original red-themed progress bar using safe native Streamlit components.
- **Modernization:** Updated all deprecated `use_container_width` parameters to `width='stretch'`.
- **Refactoring:** Consolidated solver "God function" into modular components.

### Fixed
- Potential integer overflow in CP-SAT when dealing with large score ranges and weights.
- Inconsistent tag handling (now ignores whitespace and commas within tag strings).
- Missing docstrings and module-level documentation across the codebase.
