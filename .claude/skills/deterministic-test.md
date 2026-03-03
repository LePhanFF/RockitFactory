---
name: deterministic-test
description: Run deterministic orchestrator integration tests
allowed-tools: ["Bash", "Read"]
---

Run the deterministic orchestrator integration tests.

## Usage
- `/deterministic-test` — Run fast tests only (~45s)
- `/deterministic-test all` — Run all tests including slow multi-day (~75s)
- `/deterministic-test generate` — Generate RTH snapshots for last trading day
- `/deterministic-test generate 5` — Generate RTH snapshots for last 5 days

## Steps

### For test runs:
1. Determine scope from arguments:
   - No args / `fast`: `uv run pytest packages/rockit-core/tests/test_deterministic.py -v -m "not slow" --tb=short`
   - `all`: `uv run pytest packages/rockit-core/tests/test_deterministic.py -v --tb=short`

2. Report results:
   - Tests: passed/failed count by class
   - Timing per test class
   - If failures: show the failing test names and error messages

### For snapshot generation:
1. Run: `uv run python scripts/generate_deterministic_snapshots.py --days {N} --rth-only`
2. Validate output: count lines in JSONL, verify each line is valid JSON
3. Report: snapshots generated, errors, timing, output file paths

## Test Inventory (47 tests)
- TestSingleDaySnapshot — 20 parametrized cases across Asia/London/US/IB/Post-IB
- TestModuleOutputStructure — 12 per-module key validation tests
- TestMultiDaySnapshots — 5 tests (1/3/5 fast, 10/15 slow)
- TestSchemaCompliance — 5 tests (validation, config rejection, numpy check, roundtrip)
- TestErrorHandling — 4 tests (missing ES/YM, early time, bad config)
