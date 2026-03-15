---
name: regression-check
description: Full pipeline validation — tests, lint, backtest, baseline comparison
allowed-tools: ["Bash", "Read", "Glob", "Grep"]
---

Run the complete regression pipeline: unit tests, lint, merge data, backtest, compare to baseline.

## Usage
- `/regression-check` — Full pipeline for NQ
- `/regression-check ES` — Full pipeline for specific instrument
- `/regression-check --quick` — Tests + lint only (skip backtest)

## Steps

1. **Run unit tests**:
   ```bash
   uv run pytest packages/rockit-core/tests/ -v --tb=short
   ```
   If ANY tests fail, stop and report. Do not proceed to backtest.

2. **Run lint**:
   ```bash
   uv run ruff check packages/ --fix
   ```

3. **Merge latest data** (unless --quick):
   ```bash
   uv run python -c "
   from rockit_core.data.manager import SessionDataManager
   mgr = SessionDataManager()
   mgr.merge_delta('{INSTRUMENT}')
   "
   ```

4. **Run backtest** (unless --quick):
   ```bash
   uv run python scripts/run_backtest.py --instrument {INSTRUMENT}
   ```

5. **Report results**:
   - Tests: X passed, Y failed
   - Lint: clean or issues found
   - Data: X sessions loaded, Y new sessions merged
   - Backtest: trades, WR%, PF, net P&L, max DD%
   - Baseline comparison: regressions flagged (>5% WR drop, >20% PF drop, >3% DD increase)
   - **PASS/FAIL** verdict based on eval gates:
     - Min 50% WR, 1.30 PF, <15% max DD, 50+ trades, 100+ sessions

## When to Use
- After any strategy logic changes
- After feature engineering changes
- After data pipeline changes
- Before creating a PR
- After merging new strategy code from other branches
