# Group Balancer

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://group-balancer.streamlit.app/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10 through 3.14](https://img.shields.io/badge/python-3.10%20-%203.14-blue.svg)](https://www.python.org/downloads/)

**Group Balancer** is an advanced mathematical partitioning tool designed to solve the "Fair Team" problem. Whether you are organizing a classroom, a corporate workshop, or a gaming tournament, this tool ensures your groups are balanced by skill, diverse by expertise, and respectful of social dynamics.

## Key Features

- **Multi-Dimensional Balancing:** Balance groups across multiple numeric scores simultaneously (e.g., Skill, Experience, Strength).
- **Categorical Constraints (Tags):**
  - **Groupers:** Keep participants with matching tags together in the same group.
  - **Separators:** Spread participants with matching tags across as many different groups as possible (pigeonhole principle).
- **Custom Group Sizes:** Define exact capacity requirements for every individual group.
- **Mathematical Optimization:** Powered by **Google OR-Tools (CP-SAT)** to provide provably optimal or high-quality feasible solutions within seconds.
- **Security Hardened:**
  - Strict input validation and participant count limits.
  - Professional logging and error handling.
  - Protected against common numeric overflows and large-scale DoS inputs.
  - *Note: While path normalization and size checks are implemented, absolute path traversal prevention requires environment-level restricted file access.*

## Getting Started

### 1. Requirements
*   Python 3.10 through 3.14
*   Git (to clone the repo).

### 2. Installation

#### Using uv (Recommended)
```bash
# Install dependencies and setup environment from uv.lock
uv sync

# Launch the UI
uv run streamlit run app.py
```

#### Using pip
```bash
# Setup virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies from pyproject.toml
pip install .

# Run the app
streamlit run app.py
```

## How it Works

The tool uses a **Constraint Programming (CP)** approach. It models the group assignment as a set of boolean variables $x_{i,g}$ (is participant $i$ in group $g$). 

1.  **Hard Constraints:** Enforce exact group capacities and Pigeonhole distribution for separator tags.
2.  **Objective Function:** Minimizes the weighted sum of absolute deviations from the global average for every score dimension, while penalizing the splitting of grouper tags.

---

## Project Structure

<!-- PROJECT_TREE_START -->
```text
.
├── .coderabbit.yaml
├── .github/
│   ├── dependabot.yml
│   └── workflows/
│       └── ci.yml
├── .gitignore
├── CHANGELOG.md
├── GEMINI.md
├── LICENSE
├── README.md
├── REFACTOR_PLAN.md
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
│   ├── test_config.py
│   ├── test_data_loader.py
│   ├── test_exporter.py
│   ├── test_infra.py
│   ├── test_models_unit.py
│   ├── test_services.py
│   ├── test_solver.py
│   ├── test_solver_interface.py
│   ├── test_solver_unit.py
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

## Development

The project follows high-quality engineering standards:
- **SOLID & SRP:** Decoupled Service, UI, and Core layers.
- **Type Safety:** Strong typing with `dataclasses` and `TypedDict`.
- **Testing:** 90%+ functional coverage with isolated sandboxed test execution.
- **CI/CD:** Automated testing across Python 3.10 through 3.14 using `uv`.
