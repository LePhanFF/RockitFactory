---
name: backtest
description: Run strategy backtests against historical data
allowed-tools: ["Bash", "Read", "Glob", "Grep"]
---

Run a backtest for the specified strategy or all strategies.

## Usage
- `/backtest` — Run all core strategies (259 sessions)
- `/backtest trend_bull` — Run single strategy
- `/backtest --quick` — Run 30-session quick validation

## Steps
1. Check that rockit-core is installed: `uv run python -c "import rockit_core"`
2. Run the backtest command:
   - All strategies: `uv run python -m rockit_core.engine.backtest --config configs/strategies.yaml --sessions 259`
   - Single strategy: `uv run python -m rockit_core.engine.backtest --config configs/strategies.yaml --strategy {strategy_name}`
   - Quick mode: `uv run python -m rockit_core.engine.backtest --config configs/strategies.yaml --sessions 30`
3. Compare results against baseline if `configs/baselines/current.json` exists
4. Report: win rate, profit factor, Sharpe, max drawdown, total trades
5. Flag any regressions (metrics worse than baseline by >5%)
