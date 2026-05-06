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
    -   Functional test coverage (`pytest-cov` >= 95%).
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
- **Warm Start Logic:** `OptimizationService.run` validates the multiset of fingerprints and configuration. If identical, it applies assignments to seed the solver.
- **Risk:** Using indices for warm starts after reordering causes "hallucinated" hints.

### 3. Absolute Solver Determinism
- **Lesson:** Absolute determinism is maintained even in multi-core modes by using `num_search_workers = 8` combined with `interleave_search = True` and a fixed `random_seed = 42`.
- **Consistency:** All internal iterations (tags, participants) are explicitly sorted before adding constraints to ensure the search tree is built identically across runs.

### 4. Integer Range & Overflows
- **Constraint:** CP-SAT operates on 64-bit integers. Objectives and penalties must be carefully scaled and capped (e.g., at `(1 << 62) - 1`) to avoid model construction failures or non-deterministic behavior due to silent overflows.
- **Implementation:** Multipliers are calibrated into "Bit-Slices" to ensure high-priority terms always dominate lower ones without exceeding $9 \times 10^{18}$.

### 5. Categorical Constraints (Groupers/Separators)
- **Design:** Every character in the tag string is treated as a unique constraint.
- **Canonicalization:** Tags must be order- and whitespace-insensitive. Logic is extracted into `src/core/tag_utils.py`.

### 6. Capacity-Aware Bounds
- **Lesson:** Distribution bounds must be calculated relative to each group's specific capacity, rather than using a flat global average.

### 7. Standard Deviation of Group Averages
- **Lesson:** To balance groups effectively, the metric of interest is the dispersion between the group averages, not individual participants. Uses Sample Standard Deviation (`ddof=1`) of group means.

### 8. Squared Exact Math (L2 Optimization)
- **Architecture:** The solver minimizes the **Sum of Squared Deviations** (L2) rather than Absolute Error (L1).
- **Benefit:** L2 is significantly more aggressive at eliminating outliers, leading to the "Way Lower" optimal Standard Deviation results desired by users.
- **Formula:** Uses exact cross-multiplication: `(GroupSum * TotalPeople) - (TotalSum * GroupCapacity)` to eliminate rounding and division errors entirely.
- **Precision Mandate:** Use `norm_multiplier = 1000 * len(participants)` to provide **0.001 precision**. This granularity is confirmed as necessary for L2 math to achieve peak balancing quality.

### 9. Priority Tiering (Calibrated Bit-Slicing)
- **Mandate:** Logical constraints MUST always be met before score balancing occurs.
- **Tiers:**
    - **Tier 1: Separators ($10^{12}$):** Highest priority (Disperse). Max total $\approx 10^{15}$.
    - **Tier 2: Groupers ($10^9$):** Secondary priority (Cohesion). Max total $\approx 10^{12}$.
    - **Tier 3: Balance (L2 Squared Error, $\approx 10^{10}$):** Tertiary priority (Balancing). Multiplied by $100$ for tie-breaker separation.
    - **Tier 4: Tie-Breaker ($10^0$):** Lowest priority (Determinism).
- **Stable Identity:** Anchored to `original_index` to ensure that sorting in the UI never shifts the preferred mathematical optimal.

### 10. Search & Branching Strategy
- **Worker Portfolio:** Uses 8 search workers with `interleave_search = True` to utilize multi-core performance while guaranteeing thread-safe, repeatable results.
- **High-Impact Branching:** Explicitly prioritizes decision variables for participants with the largest absolute score magnitudes. This prunes high-variance branches earlier in the search tree and accelerates both finding and proving optimality.

## Data Handling

### 1. Column Coercion
- **Lesson:** Column headers should be explicitly coerced to `str` before stripping/processing to avoid `AttributeError`.

### 2. Missing Value Normalization
- **Lesson:** Missing values in text columns normalize to `""`, numeric to `0.0`.

### 3. Path Sanitization
- **Implementation**: CLI path inputs must be stripped of shell artifacts before validation.

## 🛡️ Defensive Programming & Data Safety

- **Fail-Fast**: The program MUST terminate immediately if a validation step fails or a critical configuration is missing.
- **Supply Chain Security**: All GitHub Actions must be pinned to 40-character **immutable commit SHAs**.

## 🧪 Testing Standards

### 1. Mocking Streamlit Cache
- **Lesson**: Ensure all mocked arguments to `@st.cache_data` are serializable (no `MagicMock`).

## 🗒️ Complex Change Management (Planning & State)

For large-scale refactorings, follow this integrated lifecycle:
1. Drafting the Plan (Plan Mode).
2. Spec Sheet: Save as `REFACTOR_PLAN.md`.
3. Iterative Execution & Validation: Phased approach, Post-Phase Validation (`uv run python tools/pre_ci.py`).
4. Finalization & Landing: Update `GEMINI.md`, Cleanup, Final Validation, Commit.
