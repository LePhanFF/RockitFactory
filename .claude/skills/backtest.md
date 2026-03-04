---
name: backtest
description: Merge latest data, run backtest, compare to baseline, deep analysis
allowed-tools: ["Bash", "Read", "Glob", "Grep", "Write", "Edit"]
---

Run a full backtest cycle: merge latest data from Google Drive, run strategies, compare to baseline, analyze results.

## Usage
- `/backtest` — NQ, all core strategies, merge + run + compare
- `/backtest ES` — Run for ES instrument
- `/backtest --save-baseline` — Save current run as new baseline
- `/backtest trend_bull,p_day` — Run specific strategies only
- `/backtest --deep` — Run + deep analysis (exit reasons, day type matrix, loser dive)

## Steps

1. **Merge latest data** from `G:\My Drive\future_data\1min\` into `data/sessions/`:
   ```
   uv run python scripts/run_backtest.py --instrument {INSTRUMENT}
   ```
   If a specific instrument was requested (ES, YM), pass `--instrument`. Default is NQ.
   If specific strategies were requested, pass `--strategies {comma_list}`.
   If `--save-baseline` was requested, add `--save-baseline` flag.

2. **Review the output**:
   - Data merge: check how many new sessions were added
   - Backtest results: trades, win rate, profit factor, net P&L, max drawdown
   - Baseline comparison: check for regressions (>5% degradation in WR, PF, or P&L)

3. **Deep analysis** (if `--deep` requested or always for investigation):
   ```
   uv run python scripts/analyze_backtest.py data/results/backtest_{INSTRUMENT}_{latest}.json
   ```
   This produces:
   - **Exit reason distribution** per strategy (stops vs targets vs EOD vs VWAP breach)
   - **Day type × strategy performance matrix** (which strategies work on which day types)
   - **Loser deep dive** (OF signals, day type, extension at entry for each losing trade)
   - **Win/loss streaks** and equity curve shape
   - Reflection report saved to `data/results/reflections/`

4. **Report to user**:
   - Session count and date range
   - Key metrics: trades, WR%, PF, net P&L, max DD%
   - Per-strategy breakdown
   - Baseline diff if baseline exists
   - Flag any regressions clearly
   - If deep analysis: exit reason table, worst day types, loser patterns

5. **If no baseline exists**, suggest running with `--save-baseline` to establish one.

## Baseline Thresholds (from eval gates)
- Min 50% WR, 1.30 PF, <15% max DD, 50+ trades, 100+ sessions
- Strategy-level: 10+ trades, 45% WR, 1.10 PF minimum
- Regression: max 5% WR drop, 20% PF drop, 3% DD increase

## Strategy Targets (from strategy-studies)
| Strategy | WR | PF | Trades/Mo |
|---|---|---|---|
| 80P Rule | 44.7% | 2.57 | 4.0 |
| Balance Day IBL Fade | 82% | 9.35 | 3.4 |
| 20P IB Extension | 45.5% | 1.78 | 3.7 |
| OR Reversal | 60.9% | 2.96 | 9.6 |
| OR Acceptance v3 | 55.4% | 1.87 | 10.1 |
| **Combined** | | | **~31** |

## Data Flow
- Baseline CSVs: `data/sessions/` (local disk, persisted)
- Delta CSVs: `G:\My Drive\future_data\1min\` (Google Drive, NinjaTrader daily output)
- Results: `data/results/backtest_{INSTRUMENT}_{timestamp}.json`
- Baselines: `data/results/baselines/baseline_{INSTRUMENT}.json`
- Reflections: `data/results/reflections/`
