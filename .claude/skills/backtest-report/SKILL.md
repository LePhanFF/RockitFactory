# /backtest-report — Post-Backtest Analysis & Report Generation

Generate a comprehensive, consistent report after any backtest run. Analyzes winning trades, losing trades, skipped/filtered signals, agent decisions, and deterministic context. Outputs a shareable markdown report.

## Usage
```
/backtest-report                          # Latest run
/backtest-report NQ_20260311_192328_f401a8  # Specific run_id
/backtest-report --compare RUN_A RUN_B    # Compare two runs
```

## Steps

### Step 1: Identify the run
If no run_id provided, query DuckDB for the most recent run:
```sql
SELECT run_id, instrument, total_trades, win_rate, profit_factor, net_pnl, notes, timestamp
FROM backtest_runs ORDER BY timestamp DESC LIMIT 5
```
Let user pick or use the latest. Store as $RUN_ID.

### Step 2: Pull run summary
```sql
SELECT * FROM backtest_runs WHERE run_id = '$RUN_ID'
```
Extract: instrument, sessions, total_trades, win_rate, profit_factor, net_pnl, max_drawdown, avg_win, avg_loss, expectancy, by_strategy (JSON), config (JSON), notes.

### Step 3: Pull all trades for this run
```sql
SELECT t.*, sc.day_type, sc.bias
FROM trades t
LEFT JOIN session_context sc ON t.session_date = sc.session_date
WHERE t.run_id = '$RUN_ID'
ORDER BY t.session_date, t.entry_time
```

### Step 4: Classify trades
For each trade, classify:
- **strong_win**: net_pnl > avg_win, exit_reason = TARGET
- **lucky_win**: net_pnl > 0 but exit_reason = EOD (ran out of time, happened to be positive)
- **clean_loss**: net_pnl < 0, exit_reason = STOP (expected, risk was managed)
- **avoidable_loss**: net_pnl < 0, AND deterministic warnings present (could have been filtered)
- **barely_profitable**: 0 < net_pnl < 0.5 * avg_win (marginal)

### Step 5: Pull agent decisions (if available)
```sql
SELECT ad.*
FROM agent_decisions ad
WHERE ad.run_id = '$RUN_ID'
ORDER BY ad.session_date, ad.signal_time
```
Key analysis:
- How many signals were TAKE vs SKIP vs REDUCE_SIZE?
- For SKIP decisions: what was the reasoning? What was advocate vs skeptic confidence?
- Cross-reference: did SKIP decisions avoid losses? (check if signal appears as a trade in a no-filter baseline run)

### Step 6: Pull skipped/filtered signals analysis
Query trades from the BASELINE run (Run A, no filters) for the same instrument/period:
```sql
SELECT t.strategy_name, t.direction, t.session_date, t.net_pnl, t.outcome
FROM trades t
WHERE t.run_id = (
    SELECT run_id FROM backtest_runs
    WHERE notes LIKE '%No filters%' OR notes LIKE '%baseline%'
    ORDER BY timestamp DESC LIMIT 1
)
AND NOT EXISTS (
    SELECT 1 FROM trades t2
    WHERE t2.run_id = '$RUN_ID'
    AND t2.session_date = t.session_date
    AND t2.strategy_name = t.strategy_name
)
```
This gives us "trades that existed in baseline but were filtered out in this run."
Analyze: how many filtered trades were winners vs losers? Net PnL of filtered trades?

### Step 7: Deterministic context enrichment
For top 5 winners and top 5 losers, pull deterministic tape context:
```sql
SELECT dt.cri_status, dt.tpo_shape, dt.day_type, dt.dpoc_migration, dt.trend_strength,
       dt.extension_multiple, dt.delta_cumulative, dt.bias
FROM deterministic_tape dt
WHERE dt.session_date = $TRADE_SESSION_DATE
AND dt.snapshot_time <= $TRADE_ENTRY_TIME
ORDER BY dt.snapshot_time DESC LIMIT 1
```
Summarize: what deterministic conditions were present at entry for winners vs losers?

### Step 8: Strategy health scorecards
For each strategy in the run, produce:
- Trades, WR, PF, net PnL, avg win, avg loss, expectancy
- Win rate by direction (LONG vs SHORT)
- Win rate by day_type
- Win rate by bias alignment (aligned vs counter vs neutral)
- Best trade + worst trade with context
- Signals generated vs filtered vs taken (if agent data available)
- Comparison to study target WR (from configs or memory)

### Step 9: Pattern discovery
Look for patterns in the trade data:
```sql
-- Time-of-day analysis
SELECT EXTRACT(HOUR FROM entry_time) as hour, COUNT(*),
       ROUND(100.0 * SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) / COUNT(*), 1) as wr
FROM trades WHERE run_id = '$RUN_ID' GROUP BY 1 ORDER BY 1

-- Day type performance
SELECT day_type, COUNT(*),
       ROUND(100.0 * SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) / COUNT(*), 1) as wr
FROM trades t JOIN session_context sc ON t.session_date = sc.session_date
WHERE t.run_id = '$RUN_ID' GROUP BY 1

-- Consecutive loss analysis
-- Win/loss streaks
-- MAE/MFE distributions for winners vs losers
```

### Step 10: Generate report
Write to `reports/backtest_{RUN_ID}.md` with consistent structure:

```markdown
# Backtest Report: {RUN_ID}
> Date: {timestamp} | Instrument: {instrument} | Sessions: {N} | Branch: {git_branch}

## Executive Summary
- {1-3 sentence summary of results}
- Key finding: {most important insight}

## Portfolio Metrics
| Metric | Value |
|--------|-------|
{standard metrics table}

## Strategy Scorecards
### {Strategy 1}
{per-strategy metrics + direction + day_type breakdown}

## Trade Classification
| Category | Count | Net PnL | Notes |
|----------|-------|---------|-------|
| Strong wins | N | $X | ... |
| Lucky wins | N | $X | ... |
| Clean losses | N | $X | ... |
| Avoidable losses | N | $X | ... |

## Agent Decision Analysis (if applicable)
- Signals generated: N
- Signals filtered (mechanical): N
- Signals debated (LLM): N
- TAKE decisions: N (X% won)
- SKIP decisions: N (X% would have lost)
- Filter accuracy: "Filters avoided $X in losses, but also missed $Y in wins"

## Filtered Signal Analysis
- Trades filtered out: N
- Of those, N were winners ($X PnL) and N were losers ($Y PnL)
- Net PnL of filtered trades: $Z
- Filter value: {positive = filters helped, negative = filters too aggressive}

## Top 5 Winners (with deterministic context)
{per-trade detail with CRI, TPO, DPOC, day_type at entry}

## Top 5 Losers (with deterministic context)
{per-trade detail — what went wrong?}

## Pattern Discoveries
- {Time-of-day patterns}
- {Day type patterns}
- {Streak analysis}
- {MAE/MFE insights}

## Recommendations
- {Strategy-specific suggestions}
- {Filter adjustments}
- {Agent tuning}

## Comparison to Baseline (if available)
{Side-by-side with Run A or previous run}
```

### Step 11: Persist observations
For any significant pattern discoveries (WR > 70% or < 30% in a segment, or avoidable losses > 20% of total losses), persist as observations:
```python
persist_observation(conn, {
    "strategy": strategy_name,
    "observation": description,
    "evidence": supporting_data,
    "confidence": 0.6-0.9,
    "source": "backtest_report",
    "scope": "strategy" or "portfolio",
})
```

### Step 12: Print summary and report path
Print key metrics to terminal. Confirm report saved to `reports/backtest_{RUN_ID}.md`.

## Compare Mode (--compare)
When comparing two runs:
- Side-by-side metrics table
- Per-strategy delta (WR change, PF change, PnL change)
- Trades gained/lost between runs
- Which filter/agent changes drove the difference
- Save to `reports/compare_{RUN_A}_vs_{RUN_B}.md`

## Notes
- Always use `uv run python` for DuckDB queries
- Use `encoding='utf-8'` for all file writes
- Round all percentages to 1 decimal, PnL to 2 decimals
- Study targets: OR Rev 64.4%, OR Accept 59.9%, 20P 45.5%, B-Day 82%, 80P 42.3%
- Baseline reference: Run A (no filters) from most recent A/B test
