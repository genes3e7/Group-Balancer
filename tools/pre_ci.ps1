# Group Balancer: Local Pre-CI Script
# Automates deterministic checks: Linting, Dead Code, Docstrings, Tests, README, and Build.

$ErrorActionPreference = "Stop"

Write-Host "`n Running Local Pre-CI Checks..."

# 1. Sync dependencies
Write-Host "`n [1/7] Syncing dependencies..."
uv sync --all-extras

# 2. Ruff Linting and Formatting
Write-Host "`n [2/7] Running Ruff (Linting and Formatting)..."
uv run ruff check . --fix
uv run ruff format .

# 3. Vulture (Dead Code Analysis)
Write-Host "`n [3/7] Running Vulture (Dead Code Analysis)..."
uv run vulture src/ --min-confidence 80

# 4. Interrogate (Docstring Coverage)
Write-Host "`n [4/7] Running Interrogate (Docstring Coverage)..."
uv run interrogate .

# 5. Pytest (Functional Tests and Coverage)
Write-Host "`n [5/7] Running Pytest (Tests and Coverage)..."
uv run pytest

# 6. Update README (Mirrors CI finalize-updates)
Write-Host "`n [6/7] Updating README structure and metadata..."
# Note: Locally we use the current python version as a placeholder for min/max
# unless specified otherwise. This ensures the Tree structure is updated.
$current_ver = (uv run python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
uv run python tools/update_readme.py $current_ver $current_ver

# 7. Verify Build (Mirrors CI build step)
Write-Host "`n [7/7] Verifying Build script integrity..."
uv run python build.py

# Cleanup Artifacts
Write-Host "`n Cleaning up artifacts..."
Remove-Item -Path .coverage, .ruff_cache, .pytest_cache, dist, build -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "`n Pre-CI Checks Passed! Ready to commit.`n"
