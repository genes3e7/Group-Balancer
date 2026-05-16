# Group Balancer

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://group-balancer.streamlit.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python: 3.11-3.14](https://img.shields.io/badge/Python-3.11--3.14-blue.svg)](https://www.python.org/downloads/)

A high-performance team optimization engine built with Streamlit and Google OR-Tools. Efficiently partitions participants into groups while balancing multiple score dimensions and satisfying categorical constraints (Groupers and Separators).

## 🌟 Key Features

- **Multi-Dimensional Balancing:** Simultaneously balance groups across an unlimited number of scoring categories (e.g., Skill, Experience, Seniority).
- **Proportional Categorical Distribution:**
  - **Groupers:** Keep participants with matching tags together in the same group.
  - **Separators:** Spread participants with matching tags across as many different groups as possible (proportional pigeonhole distribution).
- **Custom Group Capacities:** Define exact group sizes or use strictly balanced defaults.
- **Deterministic Quality Metrics:** Ensures consistent balancing quality (identical standard deviations) across runs via stable warm-starts and seed-based search. (Bit-for-bit assignment identity is guaranteed when `interleave_search=True` is enabled).
- **Security Hardened:**
  - Strict input validation and participant count limits.
  - Fail-Fast architecture that prevents unsafe numerical overflows ($> 2^{62}-1$).
  - Dynamic Precision Scaling to maximize balancing quality within 64-bit safety.

## 🚀 Quick Start

- **Installation:**

  ```powershell
  uv sync
  ```

- **Running the App:**

  ```powershell
  uv run streamlit run app.py
  ```

## 🛠️ Developer Workflow

The project utilizes `uv` for dependency management and a custom Pre-CI gate for quality enforcement.

### Validation Pipeline

Before submitting code, run the local validation gate:

```powershell
uv run python tools/pre_ci.py
```

This gate enforces:

- **Linting & Formatting:** Ruff (Python) and Markdown standards.
- **Static Analysis:** Vulture (Dead code) and Interrogate (Docstring coverage).
- **Testing:** 100% pass rate with >=95% functional coverage.
- **Build Integrity:** PyInstaller verification.

## 📂 Project Structure

<!-- PROJECT_TREE_START -->

```text
.
├── .coderabbit.yaml
├── .gitattributes
├── .github/
│   ├── dependabot.yml
│   └── workflows/
│       └── ci.yml
├── .gitignore
├── .pymarkdown
├── CHANGELOG.md
├── GEMINI.md
├── LICENSE
├── README.md
├── app.py
├── build.py
├── group_balancer.py
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── data_loader.py
│   │   ├── models.py
│   │   ├── services.py
│   │   ├── solver.py
│   │   ├── solver_interface.py
│   │   └── tag_utils.py
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── components.py
│   │   ├── results_renderer.py
│   │   ├── session_manager.py
│   │   └── steps.py
│   └── utils/
│       ├── __init__.py
│       ├── exporter.py
│       └── group_helpers.py
├── streamlit_launcher.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_data_loader.py
│   ├── test_determinism.py
│   ├── test_exporter.py
│   ├── test_infra.py
│   ├── test_models_unit.py
│   ├── test_scaling_tiers.py
│   ├── test_services.py
│   ├── test_solver.py
│   ├── test_solver_interface.py
│   ├── test_solver_unit.py
│   ├── test_statistics.py
│   ├── test_steps_edge.py
│   ├── test_ui.py
│   └── test_utils.py
├── tools/
│   ├── __init__.py
│   ├── pre_ci.py
│   └── update_readme.py
└── uv.lock
```

<!-- PROJECT_TREE_END -->

---
Built with ❤️ for balanced teams.
