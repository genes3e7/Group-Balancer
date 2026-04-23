# Group Balancer: Local Pre-CI Script
# Automates deterministic checks: Linting, Dead Code, Docstrings, Tests, README, and Build.

$ErrorActionPreference = "Stop"

function Assert-ExitCode {
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Command failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}

Write-Host "`n Running Local Pre-CI Checks..."

# 1. Sync dependencies
Write-Host "`n [1/7] Syncing dependencies..."
uv sync --all-extras --frozen
Assert-ExitCode

# 2. Ruff Linting and Formatting
Write-Host "`n [2/7] Running Ruff (Linting and Formatting)..."
uv run ruff check . --fix
Assert-ExitCode
uv run ruff format .
Assert-ExitCode

# 3. Vulture (Dead Code Analysis)
Write-Host "`n [3/7] Running Vulture (Dead Code Analysis)..."
uv run vulture src/ --min-confidence 80
Assert-ExitCode

# 4. Interrogate (Docstring Coverage)
Write-Host "`n [4/7] Running Interrogate (Docstring Coverage)..."
uv run interrogate .
Assert-ExitCode

# 5. Pytest (Functional Tests and Coverage)
Write-Host "`n [5/7] Running Pytest (Tests and Coverage)..."
uv run pytest
Assert-ExitCode

# 6. Update README (Mirrors CI finalize-updates)
Write-Host "`n [6/7] Updating README structure and metadata..."
# Default to project stable range (3.10-3.14) for local runs
# Use $args[0] and $args[1] if user wants to override
$min_v = if ($args.Count -gt 0 -and $null -ne $args[0]) { $args[0] } else { "3.10" }
$max_v = if ($args.Count -gt 1 -and $null -ne $args[1]) { $args[1] } else { "3.14" }
uv run python tools/update_readme.py $min_v $max_v
Assert-ExitCode

# 7. Verify Build (Mirrors CI build step)
Write-Host "`n [7/7] Verifying Build script integrity..."
uv run python build.py
Assert-ExitCode

# Cleanup Artifacts
Write-Host "`n Cleaning up artifacts..."
Remove-Item -Path .coverage, .ruff_cache, .pytest_cache, dist, build -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "`n Pre-CI Checks Passed! Ready to commit.`n"
