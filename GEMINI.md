# Project Learnings: Group Balancer

This file documents architectural decisions, framework-specific quirks, and lessons learned during development to ensure consistency and avoid repeating mistakes.

## 🚀 Post-Change Validation Workflow (Local Pre-CI & CI Pipeline)

This workflow **MUST** be executed in its entirety **BEFORE** any `git commit` or `git push` operation. It serves as a mandatory local Pre-CI check to ensure technical integrity and minimize redundant CI failures.

1. **Adversarial Mindset Vetting**: Perform a ruthless self-review of the changes to hunt for logic bugs, security flaws, or edge-case failures that automated tests might miss.
2. **Architecture Verification**: Verify that the changes align with the established design patterns and have not introduced an unintended "architecture shift."
3. **Documentation & Changelog Update**:
   - Review and update all related documentation (README, help text, etc.) to reflect the changes.
   - **MANDATORY**: Summarize all user-facing and architectural changes in `CHANGELOG.md` under the appropriate version header.
4. **Automated Technical Validation**: Run `uv run python tools/pre_ci.py`. This script is the **final gate** and ensures:
   - **EXCEPTION**: If the changes are strictly limited to non-code and non-configuration files (e.g., `.txt`, `CHANGELOG.md`), this step may be skipped.
   - **MANDATORY**: Any change to code, tests, configuration (e.g., `.yaml`, `.toml`, `.gitignore`), or `README.md` (which is auto-updated by the script) **MUST** trigger a full validation.
   - Dependencies are synced (`uv sync`).
   - Ruff linting and formatting compliance (0 errors).
   - Dead code analysis (`vulture` > 80% confidence, ensuring effectively 0 dead code).
   - Docstring coverage (`interrogate` == 100%).
   - Markdown standard compliance (`pymarkdownlnt`).
   - Functional test coverage (`pytest-cov` >= 95%).
   - README tree and metadata are updated.
   - Build integrity is verified.

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

### 2. High-Performance Progress Bars

- **Technique:** Native HTML/CSS `div` elements are used instead of `st.image` SVG data URIs to bypass Streamlit's media manager.
- **Result:** Instant rendering of progress bars without the "picture retrieval" lag observed in media-based implementations.

### 3. Stable Widget Keys

- **Lesson:** UI widgets (e.g., `st.number_input`) must have explicit, stable keys based on data identity (e.g., `key=f"cap_{num_groups}_{i}"`) or scale (e.g., incorporating `total_p`) rather than relying on positional rendering.
- **Risk:** Without stable keys, changing participant counts or reordering groups can cause Streamlit to attach stale values to the wrong inputs or trigger `StreamlitAPIException`.
- **Harden:** Always use `try/except` coercion and `max(min(...))` clamping when initializing widget values from session state to prevent crashes from stale data types or out-of-bounds values.

### 4. Decoupling Logic from Display Text

- **Lesson:** UI controls (like radio buttons) should map to stable tokens (e.g., `"groupers"`) for backend logic, rather than forwarding full display labels.
- **Risk:** Forwarding display strings into the core solver makes the logic brittle; changing a UI label could silently break branching.

### 5. Defensive State Clamping

- **Lesson:** When rendering inputs that depend on session state (like group capacities), always clamp the value to current bounds (e.g., `min_value`..`total_p`).
- **Risk:** Stale values from a previous larger dataset can persist in session state and cause validation errors when a smaller dataset is loaded.

### 6. Async UI: Fragmentation & Lazy Loading

- **Architecture:** The tool header (Description and Progress) is de-fragmented for instant primary page load. The tool body (Step content) is wrapped in `st.fragment` with **Lazy Loading** (OR-Tools imports are deferred inside the fragment).
- **Benefit:** Ensures the tool skeleton and labels appear immediately while the heavy solver engine initializes in the background.

### 7. Import Hygiene

- **Lesson:** Move all third-party imports (like `re`) to the top-level module block to comply with E402 and ensure consistent initialization.
- **Risk:** Local imports can lead to redundant overhead or confusing dependency cycles in long-running processes like `pre_ci.py`.

### 8. File Upload Resilience

- **Lesson:** Use a cryptographic hash (MD5) of raw file bytes (`uploaded.getvalue()`) rather than metadata (filename/size) to detect content edits.
- **Risk:** Filename and size remain identical if a user corrects a single cell and re-uploads, causing Streamlit to skip re-processing and leading to stale data.

### 9. Row-Stable Interactive Sync

- **Lesson:** Manual group reassignments in the results cards must be synchronized back to the global state using the `_original_index` as the anchor.
- **Implementation:** Ensure `_original_index` is included in the `data_editor` column list (even if hidden via `column_config`) to maintain state integrity during user edits.
- **Risk:** Using positional indexing (`iloc`) causes data corruption if the user reorders the UI table (e.g., by name or score) before making a change.

## Optimization & Solver (OR-Tools)

### 1. Symmetry Breaking

- **Lesson:** In multi-dimensional problems, symmetry breaking (ordering groups) must be restricted to a single "canonical" dimension (the first one with a positive weight).
- **Risk:** Over-constraining secondary dimensions or zero-weight dimensions can lead to sub-optimal solutions or unnecessary infeasibility.

### 2. Participant Identity & Warm Starts

- **Lesson:** For robust iterative optimization (warm starts), participants must be identified via a stable content-based fingerprint rather than row indices.
- **Implementation:** `Participant.fingerprint` computes a stable MD5 hash of Name, Scores, and canonicalized Tags.
- **Warm Start Logic:** `OptimizationService.run` validates the multiset of fingerprints and configuration. If identical, it applies assignments to seed the solver.
- **Risk:** Using indices for warm starts after reordering causes "hallucinated" hints.

### 3. Configuration Cache (LRU Memoization)

- **Architecture:** The application implements a high-level memoization layer using a `collections.OrderedDict` as a Least Recently Used (LRU) cache.
- **Composite Key:** Each cache entry is keyed by a hash of both the **Dataset** (content-aware) and the **Configuration** (weights, capacities, priority).
- **Behavior:** This allows users to switch between different weight profiles instantly. If the user reverts a data change, the system automatically retrieves the best-found solution for that specific state from memory, enabling "non-linear" iterative refinement.
- **Capacity:** Capped at 50 configurations per active session to maintain strict memory hygiene while providing a massive refinement buffer.
- **Persistence:** The cache is preserved during 'Start Over' operations, allowing for a continuous workspace experience while resetting the current project's data state.

### 4. Solver Determinism: Stability vs. Speed (Race Mode)

- **Observation:** In multi-threaded environments, OR-Tools' high-speed "Race Mode" (`interleave_search = False`) can return different symmetric optima across different operating systems (Linux vs. Windows) or Python versions.
- **Architecture:** The application implements **Dual-Layer Validation** to balance stability and performance:
  - **Level 1 (Interleaved):** For tests and audits, `interleave_search = True` is used to force worker synchronization, guaranteeing bit-for-bit identical personnel assignments.
  - **Level 2 (Race Mode):** For production UI, the flag is disabled to provide the absolute fastest "alive" feel, with stability guaranteed only at the mathematical quality level (identical Standard Deviations).
- **Control:** The flag is exposed via `SolverConfig` for explicit consumer control.

### 5. Integer Range & Overflows

- **Constraint:** CP-SAT operates on 64-bit integers. Objectives and penalties must be carefully scaled and capped (e.g., at `(1 << 62) - 1`) to avoid model construction failures or non-deterministic behavior due to silent overflows.
- **Implementation:** Theoretical bounds are tracked globally via `max_abs_diff_bound` to ensure `max_dev` and `sq_diff` variables stay within the 64-bit domain.
- **Fail-Fast Guard:** The solver implements a strict `ValueError` in `get_model` if the theoretical aggregate objective sum exceeds $(1 \ll 62) - 1$, preventing unsafe solves at the architecture level.

### 6. Categorical Constraints (Groupers/Separators)

- **Design:** Every character in the tag string is treated as a unique constraint.
- **Canonicalization:** Tags must be order- and whitespace-insensitive. Logic is extracted into `src/core/tag_utils.py`.

### 7. Capacity-Aware Bounds

- **Lesson:** Distribution bounds must be calculated relative to each group's specific capacity, rather than using a flat global average.

### 8. Standard Deviation of Group Averages

- **Lesson:** To balance groups effectively, the metric of interest is the dispersion between the group averages, not individual participants. Uses Sample Standard Deviation (`ddof=1`) of group means.

### 9. Squared Exact Math (L2 Optimization)

- **Architecture:** The solver minimizes the **Sum of Squared Deviations** (L2) rather than Absolute Error (L1).
- **Benefit:** L2 is significantly more aggressive at eliminating outliers, leading to the "Way Lower" optimal Standard Deviation results desired by users.
- **Formula:** Uses exact cross-multiplication: `(GroupSum * TotalPeople) - (TotalSum * GroupCapacity)` to eliminate rounding and division errors entirely.
- **Precision Mandate:** Use **Dynamic Precision Scaling** to automatically calculate the highest possible resolution (up to **0.001 precision**) that stays within 64-bit safety bounds for the given participant count.

### 10. Priority Tiering (Lexicographic Bit-Slicing)

- **Mandate:** Logical constraints MUST always be met before score balancing occurs.
- **Dynamic Hierarchy:** The UI 'Priority' toggle dynamically swaps the primary and secondary bit-slices:
  - **HI Priority Tier ($10^{12}$):** Assigned to user's choice (Separators or Groupers).
  - **LO Priority Tier ($10^9$):** Secondary constraint layer.
  - **Tier 3: Max-Min Fairness ($10^7$):** Tertiary priority (Minimize worst outlier).
  - **Tier 4: Balance (L2 Squared Error, $10^0$):** Quaternary priority (Overall balance).
- **Stable Identity:** Anchored to `original_index` to ensure that sorting in the UI never shifts the preferred mathematical optimal.

### 11. Search & Branching Strategy

- **Worker Portfolio:** Dynamically utilizes parallel search workers (defaulting to 4 or `os.cpu_count()`) with `interleave_search = False` (Race Mode) to utilize multi-core performance for rapid proof of optimality.
- **High-Impact Branching:** Explicitly prioritizes decision variables for participants with the largest absolute score magnitudes.
- **Tie-Breaker:** Uses a deterministic tie-breaker (Impact DESC, Original Index ASC) to ensure search stability. Previous implementations using enumeration indices were brittle to UI reordering; the current implementation utilizes stable dataset indices.

### 12. Relative Weight Scaling & GCD Reduction

- **Problem:** Prematurely rounding fractional weights (e.g., 0.1) to integers can coarsen the objective function and distort user-defined importance ratios.
- **Solution:** The normalization engine (now handled safely in `OptimizationService`) identifies all positive weights, scales them by $10^3$ to handle up to 0.001 UI precision, and then uses a **Greatest Common Divisor (GCD)** reduction to convert the weights into their simplest irreducible integer ratios (e.g., 0.2:0.4 becomes 1:2).
- **Performance:** This produces smaller, strictly proportional integer coefficients. Smaller coefficients allow CP-SAT's **Presolve** and **Linear Relaxation** phases to prune the search tree more aggressively, leading to much faster convergence on the optimal solution.
- **UI Integration:** The reduced weights are passed to the solver and used as part of the `Configuration Cache` composite key, ensuring that equivalent fractional ratios (e.g., 1:2 and 2:4) hit the same cache entry.

### 13. Dynamic Safety Bounds

- **Mechanism:** Theoretical objective bounds are calculated using the actual maximum `original_index` and `num_groups` present in the current dataset.
- **Safety:** This ensures that the `get_model` Fail-Fast check is precise, preventing unnecessary `ValueError` exceptions for small datasets while strictly blocking unsafe overflows for large-scale solves.

### 14. Objective Scaling & Tie-Breaker Subordination

- **Lesson:** Mathematically "pure" lexicographic priority (scaling the main objective by the tie-breaker maximum) is incompatible with CP-SAT's 64-bit integer limits when using large priority multipliers (e.g., $10^{12}$).
- **Mandate:** Use **Simple Addition** (`main_objective + tie_breaker`) instead of multiplication.
- **Context:** The 100x scale gap between the Fairness Tier ($10^7$) and the Max Tie-Breaker (~$10^5$) provides sufficient practical subordination without risking numerical overflow.
- **Enforcement:** The code comment in `get_model()` explaining this rationale is **critical** and MUST NOT be removed or "refactored" into a multiplier. Determinism is instead guaranteed via `interleave_search = True` in tests.

## Data Handling

### 1. Column Coercion

- **Lesson:** Column headers should be explicitly coerced to `str` before stripping/processing to avoid `AttributeError`.

### 2. Missing Value Normalization

- **Lesson:** Missing values in text columns normalize to `""`, numeric to `0.0`.

### 3. Path Sanitization

- **Implementation:** CLI path inputs must be stripped of shell artifacts before validation.

## 🛡️ Defensive Programming & Data Safety

- **Fail-Fast:** The program MUST terminate immediately if a validation step fails or a critical configuration is missing.
- **Supply Chain Security:** All GitHub Actions must be pinned to 40-character **immutable commit SHAs**.

## 🧪 Testing Standards

### 1. Mocking Streamlit Architecture

- **Lesson:** Use `unittest.mock.MagicMock` with explicit identity decorators for `@st.fragment` and `@st.cache_data` in `conftest.py`.
- **Constraint:** Ensure all mocked arguments to cached functions are serializable. Guard application entry points with `if __name__ == "__main__":` to allow safe imports of UI modules in non-Streamlit environments.

## 📦 Build & Distribution

### 1. Automated Tree Shaking

- **Mechanism:** The `build.py` script implements a `TreeShaker` class that performs static analysis of `src/` and `app.py` to identify imported top-level modules.
- **Exclusion Strategy:** It calculates the delta between installed packages and required imports, feeding it to PyInstaller's `--exclude-module` flag.
- **Safety:** Explicitly protects core runtime dependencies (`streamlit`, `pandas`, `ortools`, `numpy`) and avoids dynamic dependency analysis of the entire environment to prevent stripping of indirect sub-dependencies.
- **Reliability:** Anchor all build artifact paths (`build/`, `dist/`) to the project root using `os.path.join(os.path.dirname(__file__), ...)` to ensure consistent behavior across different execution environments.

## 🗒️ Complex Change Management (Planning & State)

For large-scale refactorings, follow this integrated lifecycle:

1. Drafting the Plan (Plan Mode).
2. Spec Sheet: Save as `REFACTOR_PLAN.md`.
3. Iterative Execution & Validation: Phased approach, Post-Phase Validation (`uv run python tools/pre_ci.py`).
4. Finalization & Landing: Update `GEMINI.md`, Cleanup, Final Validation, Commit.
