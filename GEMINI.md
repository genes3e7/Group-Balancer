# Project Learnings: Group Balancer

This file documents architectural decisions, framework-specific quirks, and lessons learned during development to ensure consistency and avoid repeating mistakes.

## 🚀 Post-Change Validation Workflow (Local Pre-CI)
This workflow **MUST** be executed in its entirety **BEFORE** any `git commit` or `git push` operation. It serves as a mandatory local Pre-CI check to ensure technical integrity and minimize redundant CI failures.

1.  **Adversarial Mindset Vetting**: Perform a ruthless self-review of the changes to hunt for logic bugs, security flaws, or edge-case failures that automated tests might miss.
2.  **Architecture Verification**: Verify that the changes align with the established design patterns and have not introduced an unintended "architecture shift."
3.  **Documentation & Changelog Update**: 
    -   Review and update all related documentation (README, help text, etc.) to reflect the changes.
    -   **MANDATORY**: Summarize all user-facing and architectural changes in `CHANGELOG.md` under the appropriate version header.
4.  **Automated Technical Validation**: Run `powershell.exe -File tools/pre_ci.ps1`. This script is the **final gate** and ensures:
    -   Dependencies are synced (`uv sync`).
    -   Ruff linting and formatting compliance (0 errors).
    -   Dead code analysis (`vulture` > 80% confidence).
    -   Docstring coverage (`interrogate` > 80%).
    -   Functional test coverage (`pytest-cov` > 80%).
    -   README tree and metadata are updated.
    -   Build integrity is verified.

## 💻 Environment & Syntax
- **Preferred Shell**: Windows PowerShell.
- **Syntax Strategy**: Always attempt Windows PowerShell syntax first to minimize token usage and execution errors.

## Streamlit UI & Components

### 1. Parameter Deprecation: `use_container_width`
- **Observation:** As of April 2026, Streamlit has deprecated `use_container_width` in favor of a more unified `width` parameter.
- **Constraint:** 
  - Use `width="stretch"` instead of `use_container_width=True`.
  - Use `width="content"` instead of `use_container_width=False`.
- **Reasoning:** Ensures compatibility with Streamlit >= 1.49.0 and avoids runtime deprecation warnings.

### 2. Progress Bar Implementation
- **Technique:** Custom SVG data URIs rendered via `st.image` are used to create a contiguous, themed progress bar.
- **Quirk:** Must use `width="stretch"` to ensure the SVG fills the column container exactly.

### 3. Stable Widget Keys
- **Lesson:** UI widgets (e.g., `st.number_input`) must have explicit, stable keys based on data identity (e.g., `key=f"weight_{col}"`) rather than relying on positional rendering.
- **Risk:** Without stable keys, renaming or reordering columns can cause Streamlit to attach values to the wrong inputs on rerun.

### 4. Decoupling Logic from Display Text
- **Lesson:** UI controls (like radio buttons) should map to stable tokens (e.g., `"simple"` or `"advanced"`) for backend logic, rather than forwarding full display labels.
- **Risk:** Forwarding display strings into the core solver makes the logic brittle; changing a UI label could silently break `startswith` branching.

## Optimization & Solver (OR-Tools)

### 1. Symmetry Breaking
- **Lesson:** In multi-dimensional problems, symmetry breaking (ordering groups) must be restricted to a single "canonical" dimension (the first one with a positive weight).
- **Risk:** Over-constraining secondary dimensions or zero-weight dimensions can lead to sub-optimal solutions or unnecessary infeasibility.

### 2. Integer Range & Overflows
- **Constraint:** CP-SAT operates on 64-bit integers. Objectives and penalties must be carefully scaled and capped (e.g., at `(1 << 60) - 1`) to avoid model construction failures.
- **Implementation:** Weighted deviations and cohesion penalties are multiplied by a `SCALE_FACTOR` but validated against safety bounds before being added to the model.

### 3. Categorical Constraints (Groupers/Separators)
- **Design:** Every character in the tag string is treated as a unique constraint.
- **UI Mapping:** The `_original_index` must be preserved through any DataFrame transformations (like aggregation for group cards) to ensure UI edits can be mapped back to the global state correctly.

### 4. Capacity-Aware Bounds
- **Lesson:** Distribution bounds (like pigeonhole constraints for "stars" or separators) must be calculated relative to each group's specific capacity, rather than using a flat global average.
- **Risk:** Using flat distribution bounds can mathematically force infeasibility when custom capacities are skewed.

## Data Handling

### 1. Column Coercion
- **Lesson:** When loading data from Excel/CSV, column headers should be explicitly coerced to `str` before stripping/processing.
- **Risk:** Numeric or null headers in the raw file can cause `AttributeError` during prefix checks (e.g., `.startswith("Score")`).

### 2. Missing Value Normalization
- **Lesson:** Missing values (NaN) in text columns (like `Grouper` and `Separator`) must be explicitly normalized to empty strings (`""`).
- **Risk:** Casting `NaN` directly to a string results in `"nan"`, which the logic would incorrectly parse as the distinct tags `'n'` and `'a'`.

### 3. Coercion Warnings
- **Lesson:** When using `pd.to_numeric(errors="coerce")`, distinguish between originally missing data (blank cells) and truly invalid strings.
- **Risk:** Failing to separate these cases leads to false-positive warnings that confuse users about "invalid" data.

## Code Quality & Conventions

### 1. Docstrings
- **Standard:** The project strictly standardizes on **Google-style docstrings** for all modules, classes, and functions to maintain a professional, readable codebase.

