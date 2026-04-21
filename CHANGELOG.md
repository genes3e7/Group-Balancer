# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [6.1.0] - 2025-02-18

### Added
- **Security Hardening:**
  - Strict file path validation and normalization.
  - File size limits (max 10MB) and participant limits (max 1000).
  - Explicit integer overflow protection for CP-SAT objective functions.
- **Service Layer:** Introduced `src.core.services` to decouple Streamlit UI from business logic.
- **Type System:** Comprehensive typing using `dataclasses` and `Enums` for `Participant` and `SolverConfig`.
- **Global Logging:** Professional logging configuration with stream handlers and formatted output.
- **New Tests:** Added `test_edge_cases.py`, `test_infra.py`, `test_ui.py`, and `test_utils.py`.

### Changed
- **Solver Refactoring:**
  - Implemented **Builder Pattern** (`ConstraintBuilder`) for complex model construction.
  - Implemented **Strategy Pattern** (`ScoringStrategy`) for different optimization modes (Simple vs Advanced).
  - Isolated tag processing logic into `TagProcessor`.
- **Project Structure:** Moved core logic into `src.core` and UI components into `src.ui`.
- **Streamlit Interface:** Updated to use the new `OptimizationService` for better maintainability and testability.

### Fixed
- Potential integer overflow in CP-SAT when dealing with large score ranges and weights.
- Inconsistent tag handling (now ignores whitespace and commas within tag strings).
- Missing docstrings and module-level documentation across the codebase.
