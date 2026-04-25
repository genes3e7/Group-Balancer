# 🛠️ Developer Guide

## 🏗️ Project Structure
* `src/core/`: Mathematical models and solver orchestration.
* `src/ui/`: Streamlit interface and step-based routing.
* `src/utils/`: Data export and helper functions.
* `tools/`: CI/CD automation and validation scripts.

## 🧪 Testing
We maintain a strict >90% coverage mandate.
```bash
uv run python tools/pre_ci.py
```
This script runs Ruff (linting), Vulture (dead code), Interrogate (docstrings), and Pytest.

## 🚀 Environment Setup
The project uses `uv` for dependency management.
```bash
# Clone the repo
git clone ...
# Sync dependencies
uv sync
# Run the app
uv run streamlit run app.py
```
