---
name: run-tests
description: Run tests for a specific package or all packages
allowed-tools: ["Bash", "Read", "Glob"]
---

Run pytest for RockitFactory packages.

## Usage
- `/run-tests` — Run all tests
- `/run-tests core` — Run rockit-core tests only
- `/run-tests core::strategies` — Run strategy tests only

## Steps
1. Determine scope from arguments:
   - No args: `uv run pytest packages/ --cov --cov-report=term-missing`
   - `core`: `uv run pytest packages/rockit-core/tests/ --cov=packages/rockit-core/src --cov-report=term-missing`
   - `core::strategies`: `uv run pytest packages/rockit-core/tests/strategies/ -v`
   - `serve`: `uv run pytest packages/rockit-serve/tests/`
   - `train`: `uv run pytest packages/rockit-train/tests/`
2. Run `uv run ruff check packages/` for linting
3. Run `uv run mypy packages/rockit-core/src/` for type checking (rockit-core only)
4. Report results: tests passed/failed, coverage %, lint issues, type errors
