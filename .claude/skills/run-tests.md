---
name: run-tests
description: Run tests for a specific package or all packages
allowed-tools: ["Bash", "Read", "Glob"]
---

Run pytest for RockitFactory packages.

## Usage
- `/run-tests` — Run all tests
- `/run-tests core` — Run rockit-core tests only
- `/run-tests data` — Run data manager tests only
- `/run-tests strategies` — Run strategy tests only
- `/run-tests engine` — Run backtest engine tests only

## Steps

1. Determine scope from arguments:
   - No args: `uv run pytest packages/rockit-core/tests/ -v --tb=short`
   - `core`: `uv run pytest packages/rockit-core/tests/ -v --tb=short`
   - `data`: `uv run pytest packages/rockit-core/tests/test_data_manager.py -v`
   - `strategies`: `uv run pytest packages/rockit-core/tests/test_strategies.py packages/rockit-core/tests/test_strategy_loader.py -v`
   - `engine`: `uv run pytest packages/rockit-core/tests/test_engine.py -v`
   - `imports`: `uv run pytest packages/rockit-core/tests/test_imports.py -v`

2. Run lint check: `uv run ruff check packages/ --fix`

3. Report results:
   - Tests: passed/failed count
   - Any lint issues found and fixed
   - If failures: show the failing test names and error messages

## Current Test Inventory (202 tests)
- test_data_manager.py — 11 tests (load, merge, dedup, info)
- test_engine.py — 26 tests (trades, execution, positions, equity)
- test_strategies.py — 17 tests (day type, signals, confidence)
- test_strategy_loader.py — 15 tests (registry, loading, config)
- test_imports.py — 94+ tests (all module imports)
- test_filters.py — 12 tests (filter chain, composites)
- test_metrics.py — 4 tests (events, collector)
- test_models.py — 5 tests (entry/stop/target models)
- test_model_registry.py — 30+ tests (model instantiation)
- test_smoke.py — 1 test (basic import)
