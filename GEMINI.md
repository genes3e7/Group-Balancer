# Project Learnings: Group Balancer

This file documents architectural decisions, framework-specific quirks, and lessons learned during development to ensure consistency and avoid repeating mistakes.

## 🚀 Post-Change Validation Workflow (Local Pre-CI & CI Pipeline)

This workflow **MUST** be executed in its entirety **BEFORE** any `git commit` or `git push` operation. It serves as a mandatory local Pre-CI check to ensure technical integrity and minimize redundant CI failures.

1.  **Adversarial Mindset Vetting**: Perform a ruthless self-review of the changes to hunt for logic bugs, security flaws, or edge-case failures that automated tests might miss.
2.  **Architecture Verification**: Verify that the changes align with the established design patterns and have not introduced an unintended "architecture shift."
3.  **Documentation & Changelog Update**: 
    -   Review and update all related documentation (README, help text, etc.) to reflect the changes.
    -   **MANDATORY**: Summarize all user-facing and architectural changes in `CHANGELOG.md` under the appropriate version header.
4.  **Automated Technical Validation**: Run `uv run python tools/pre_ci.py`. This script is the **final gate** and ensures:
    -   **EXCEPTION**: If the changes are strictly limited to non-code and non-configuration files (e.g., `.txt`, `CHANGELOG.md`), this step may be skipped.
    -   **MANDATORY**: Any change to code, tests, configuration (e.g., `.yaml`, `.toml`, `.gitignore`), or `README.md` (which is auto-updated by the script) **MUST** trigger a full validation.
    -   Dependencies are synced (`uv sync`).
    -   Ruff linting and formatting compliance (0 errors).
    -   Dead code analysis (`vulture` > 80% confidence, ensuring effectively 0 dead code).
    -   Docstring coverage (`interrogate` == 100%).
    -   Functional test coverage (`pytest-cov` >= 90%).
    -   README tree and metadata are updated.
    -   Build integrity is verified.

### 💡 CI/CD & Pipeline Learnings

- **Pre-CI Refactoring**: The validation pipeline utilizes a cross-platform, object-oriented `PreCIPipeline` Python class orchestrated via `uv` instead of a legacy PowerShell script. This prevents state leakage, natively integrates with the `uv` toolchain, and provides deterministic execution and clear `PASS/FAIL/SKIP` summary reporting.
- **Compute Optimization**: To drastically reduce CI runtimes, the remote test-matrix runs `pytest -n auto` (via `pytest-xdist`). The unified local Pre-CI gate (`tools/pre_ci.py`) executes tests sequentially to ensure stable coverage merging and provide a clear progress breakdown.
- **Least Privilege Configuration**: CI workflows (`ci.yml`) should never grant global `permissions: contents: write`. Instead, write permissions are scoped exclusively to the specific job (e.g., `finalize-updates`) that needs to push automated commits back to the branch.

## 💻 Environment & Syntax
- **Maintainer's local shell**: PowerShell — examples may use PowerShell syntax.
- **POSIX Equivalents**: POSIX equivalents apply on Linux/macOS, and CI runners (e.g., `runs-on: ubuntu-latest`) should use POSIX syntax. The `PreCIPipeline` orchestrator and `uv` toolchain are designed to be strictly cross-platform.

## 🧠 AI Behavioral Mandates
- **GitHub CLI Integration**: Always check if the GitHub CLI (`gh`) is available and authenticated. If so, use it to fetch PR reviews, check CI status, or manage issues before starting work on a branch or PR. This ensures you are aware of feedback or pending requests that might not be visible in the local git history.
- **Anti-Sycophancy**: Do **NOT** blindly accept reviews or suggestions (from human or AI reviewers) if they contradict established design intent or architectural logic.
- **Design Intent Integrity**: Always prioritize the long-term vision and stability of the codebase. If a change feels forced or illogical, question it.
- **Clarification**: Proactively ask for clarifications if a request or review is ambiguous, instead of making assumptions that might lead to technical debt.
- **Technical Pushback**: Provide clear, reasoned technical explanations when resisting a change. Use data, performance metrics, or architectural principles to support your stance.

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
- **Lesson:** UI widgets (e.g., `st.number_input`) must have explicit, stable keys based on data identity (e.g., `key=f"cap_{num_groups}_{i}"`) or scale (e.g., incorporating `total_p`) rather than relying on positional rendering.
- **Risk:** Without stable keys, changing participant counts or reordering groups can cause Streamlit to attach stale values to the wrong inputs or trigger `StreamlitAPIException`.

### 4. Decoupling Logic from Display Text
- **Lesson:** UI controls (like radio buttons) should map to stable tokens (e.g., `"simple"` or `"advanced"`) for backend logic, rather than forwarding full display labels.
- **Risk:** Forwarding display strings into the core solver makes the logic brittle; changing a UI label could silently break `startswith` branching.

### 5. Defensive State Clamping
- **Lesson**: When rendering inputs that depend on session state (like group capacities), always clamp the value to current bounds (e.g., `min_value`..`total_p`).
- **Risk**: Stale values from a previous larger dataset can persist in session state and cause validation errors when a smaller dataset is loaded.

### 6. Performance: UI Caching
- **Lesson**: Memoize heavy binary generation (e.g., `exporter.generate_excel_bytes`) using `@st.cache_data` to ensure the UI remains responsive during rapid reassignments.
- **Risk**: Without caching, the entire Excel file is re-generated on every streamlit rerun, causing significant lag.

### 7. Import Hygiene
- **Lesson**: Move all third-party imports (like `re`) to the top-level module block to comply with E402 and ensure consistent initialization.
- **Risk**: Local imports can lead to redundant overhead or confusing dependency cycles in long-running processes like `pre_ci.py`.

## Optimization & Solver (OR-Tools)

### 1. Symmetry Breaking
- **Lesson:** In multi-dimensional problems, symmetry breaking (ordering groups) must be restricted to a single "canonical" dimension (the first one with a positive weight).
- **Risk:** Over-constraining secondary dimensions or zero-weight dimensions can lead to sub-optimal solutions or unnecessary infeasibility.

### 2. Participant Identity & Warm Starts

- **Lesson:** For robust iterative optimization (warm starts), participants must be identified via a stable content-based fingerprint rather than row indices.
- **Implementation:** `Participant.fingerprint` computes a stable MD5 hash of Name, Scores, and canonicalized Tags.
- **Warm Start Logic:** `OptimizationService.run` validates the full fingerprint **multiset** of the current session against previous results. If identical, it maps fingerprints to group assignments to seed the solver.
- **Risk:** Row indices are regenerated on every reorder/edit in Step 1. Using indices for warm starts after reordering causes "hallucinated" hints where assignments are applied to the wrong people.

### 3. Integer Range & Overflows

- **Constraint:** CP-SAT operates on 64-bit integers. Objectives and penalties must be carefully scaled and capped (e.g., at `(1 << 60) - 1`) to avoid model construction failures.
- **Implementation:** Weighted deviations and cohesion penalties are multiplied by a `SCALE_FACTOR` but validated against safety bounds before being added to the model.
- **Optimization:** The cohesion penalty budget (`per_term_cap`) is calculated by counting only active grouper sets (`len(g_set) > 1`) to maximize the available penalty range while preventing overflow.
- **Tuning:** Partitioning math is significantly faster with `linearization_level=0` and `symmetry_level=2`. These are centralized in `solver.apply_solver_tuning`.

### 4. Categorical Constraints (Groupers/Separators)

- **Design:** Every character in the tag string is treated as a unique constraint.
- **Canonicalization:** Tags must be order- and whitespace-insensitive (e.g., `"A,B"` == `"B A"`). Logic is extracted into `src/core/tag_utils.py` to prevent circular imports between Models and Solver.
- **UI Mapping:** The `_original_index` must be preserved through any DataFrame transformations (like aggregation for group cards) to ensure UI edits can be mapped back to the global state correctly.

### 5. Capacity-Aware Bounds
- **Lesson:** Distribution bounds (like pigeonhole constraints for "stars" or separators) must be calculated relative to each group's specific capacity, rather than using a flat global average.
- **Risk:** Using flat distribution bounds can mathematically force infeasibility when custom capacities are skewed.

## Data Handling

### 1. Column Coercion
- **Lesson:** When loading data from Excel/CSV, column headers should be explicitly coerced to `str` before stripping/processing.
- **Risk:** Numeric or null headers in the raw file can cause `AttributeError` during prefix checks (e.g., `.startswith("Score")`).

### 2. Missing Value Normalization
- **Lesson:** Missing values (`NaN`, `None`, `pd.NA`, `pd.NaT`) in both text and numeric columns must be explicitly normalized.
- **Implementation**: 
  - Text columns (`Grouper`, `Separator`) normalize to empty strings (`""`).
  - Score columns normalize to `0.0`.
- **Risk:** OR-Tools solvers and pandas operations can crash or produce non-deterministic results when encountering mixed-type missing scalars.

### 3. Coercion Warnings
- **Lesson:** When using `pd.to_numeric(errors="coerce")`, distinguish between originally missing data (blank cells) and truly invalid strings.
- **Risk:** Failing to separate these cases leads to false-positive warnings that confuse users about "invalid" data.

### 4. Path Sanitization
- **Lesson**: CLI path inputs must be stripped of shell artifacts (quotes, ampersands) before validation.
- **Implementation**: `get_file_path_from_user` uses a regex to sanitize raw input before passing it to `validate_file_path`.

## 🛡️ Defensive Programming & Data Safety

- **Fail-Fast**: The program MUST terminate immediately if a validation step fails or a critical configuration is missing.
- **Idempotency**: Ensure solver operations and file exports are idempotent; multiple runs with the same input should yield deterministic results.
- **Supply Chain Security**: All GitHub Actions in `.github/workflows/` MUST be pinned to 40-character **immutable commit SHAs** rather than mutable version tags (e.g., `@v4`). This prevents supply-chain attacks via tag-shifting and ensures deterministic CI behavior.

## 🧪 Testing Standards

### 1. Mocking Streamlit Cache
- **Lesson**: When testing functions decorated with `@st.cache_data` (or `@st.cache_resource`), ensure all mocked arguments are serializable (no `MagicMock`).
- **Risk**: Streamlit's caching mechanism attempts to hash/pickle arguments; passing a `MagicMock` triggers `UnserializableReturnValueError` or `TypeError`.
- **Mitigation**: Mock the cached function itself rather than its internal dependencies when unit testing UI logic, or provide real but minimal data objects (e.g., small DataFrames).

## 🗒️ Complex Change Management (Planning & State)

For large-scale refactorings or multi-phase integrations, follow this integrated lifecycle:

1.  **Drafting the Plan**: Enter `Plan Mode` to research and design a comprehensive execution strategy.
2.  **Creating the Spec Sheet**: Save the plan as a standalone markdown file (e.g., `REFACTOR_PLAN.md`) in the project root. This acts as a persistent "Source of Truth" that survives session crashes or pauses.
3.  **Iterative Execution & Validation**:
    -   Perform work in distinct phases.
    -   **Post-Phase Validation**: After every phase, you MUST execute the **Post-Change Validation Workflow** (`uv run python tools/pre_ci.py`). This is a mandatory gate to prevent regression accumulation.
    -   **Update the Spec**: Explicitly mark tasks as completed in the spec sheet file only after a successful `pre_ci.py` pass.
4.  **Finalization & Landing**:
    -   **Update Learnings**: Before closing the task, review the changes for new architectural insights, quirks, or standard shifts and document them in `GEMINI.md`.
    -   **Cleanup**: Delete the ephemeral spec sheet (`REFACTOR_PLAN.md`).
    -   **Final Validation**: Run a final, full pass of `tools/pre_ci.py` **AFTER** deleting the spec sheet to ensure the `README.md` project tree is accurate for the final push.
    -   **Commit & Push**: Push the finalized code and updated learnings.
    -   **Review Scheduling**: By default, schedule the next review in **60 minutes** using the `@coderabbitai review` command (NEVER `@coderabbitai resume` as it triggers mass replies and immediate rate throttling). Using `review` while paused ensures the system remains paused for future manual triggers.


