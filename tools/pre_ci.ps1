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
# Default to project stable range (3.10-3.14) for local runs
# Use $args[0] and $args[1] if user wants to override
$min_v = if ($args[0]) { $args[0] } else { "3.10" }
$max_v = if ($args[1]) { $args[1] } else { "3.14" }
uv run python tools/update_readme.py $min_v $max_v

# 7. Verify Build (Mirrors CI build step)
Write-Host "`n [7/7] Verifying Build script integrity..."
uv run python build.py

# Cleanup Artifacts
Write-Host "`n Cleaning up artifacts..."
Remove-Item -Path .coverage, .ruff_cache, .pytest_cache, dist, build -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "`n Pre-CI Checks Passed! Ready to commit.`n"
