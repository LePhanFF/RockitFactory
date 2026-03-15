---
name: analyze-trades
description: Analyze trades using DuckDB research database — deterministic context, setup evaluation, pattern discovery
allowed-tools: ["Bash", "Read", "Glob", "Grep", "Write", "Edit", "Agent"]
---

Analyze trades from the research DuckDB, correlating each trade with deterministic tape data to understand why setups worked or failed.

## Usage
- `/analyze-trades` — Analyze all trades from the latest backtest run
- `/analyze-trades OR Rev` — Analyze trades for a specific strategy
- `/analyze-trades losers` — Deep dive into losing trades only
- `/analyze-trades 2025-03-05` — Analyze trades for a specific session date
- `/analyze-trades winners --strategy "80P Rule"` — Winners for a strategy

## Prerequisites

The research database must be initialized. If `data/research.duckdb` doesn't exist, run:
```
uv run python scripts/init_research_db.py
```

## Steps

1. **Connect to DuckDB** and verify data exists:
   ```python
   import sys
   sys.path.insert(0, "packages/rockit-core/src")
   from rockit_core.research.db import connect, query_df, table_counts
   conn = connect()
   counts = table_counts(conn)
   ```

2. **Get the latest backtest run** (or filter by user request):
   ```sql
   SELECT run_id, instrument, total_trades, win_rate, profit_factor, net_pnl
   FROM backtest_runs ORDER BY timestamp DESC LIMIT 1
   ```

3. **Pull trades** with deterministic context using the v_trade_context view:
   ```sql
   SELECT * FROM v_trade_context WHERE run_id = ? ORDER BY session_date, entry_time
   ```

4. **For each trade (or filtered subset), evaluate**:

   a. **Pre-signal context** — Pull deterministic tape 30 min BEFORE entry:
   ```sql
   SELECT * FROM deterministic_tape
   WHERE session_date = ?
     AND snapshot_time <= ?
     AND snapshot_time >= ?
   ORDER BY snapshot_time
   ```
   Look at: CRI status trajectory, DPOC migration trend, OTF bias evolution, TPO shape changes

   b. **At signal time** — What conditions were present at entry?
   - Did the setup align with deterministic evidence (bias, day type, CRI)?
   - Was there confluence (multiple deterministic signals agreeing)?
   - Were there warnings (CRI STAND_DOWN, counter-trend, balance trap)?

   c. **Post-trade context** — What happened after entry?
   - Did day type morph? Did bias flip?
   - Did DPOC migration confirm or deny the trade direction?

   d. **Assessment** — Classify each trade:
   - `outcome_quality`: strong_win | lucky_win | barely_profitable | expected_loss | avoidable_loss
   - `why_worked`: deterministic evidence that supported the winning trade
   - `why_failed`: deterministic warnings that were ignored or conditions that deteriorated
   - `deterministic_support`: signals that confirmed the setup
   - `deterministic_warning`: signals that should have caused caution
   - `improvement_suggestion`: actionable insight (better stop, skip this setup type, etc.)

5. **Store assessments** in trade_assessments table:
   ```python
   conn.execute("""
       INSERT OR REPLACE INTO trade_assessments (
           trade_id, run_id, outcome_quality,
           why_worked, why_failed,
           deterministic_support, deterministic_warning,
           improvement_suggestion, pre_signal_context
       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
   """, [...])
   ```

6. **Create observations** for pattern-level findings:
   ```python
   conn.execute("""
       INSERT INTO observations (
           obs_id, scope, strategy, observation, evidence, source, confidence
       ) VALUES (?, ?, ?, ?, ?, ?, ?)
   """, [...])
   ```

7. **Report findings** to the user:
   - Summary table: strategy, trades analyzed, strong wins, avoidable losses
   - Top 3 patterns discovered (e.g., "80P Rule wins 75% when CRI is READY at entry")
   - Top 3 avoidable loss patterns (e.g., "OR Rev losses cluster when day_type morphs to Trend")
   - Specific improvement suggestions

## Key Queries

**Win rate by CRI status at entry:**
```sql
SELECT ctx_cri_status, COUNT(*) as trades,
       SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
       ROUND(SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as wr
FROM v_trade_context
WHERE run_id = ?
GROUP BY ctx_cri_status
```

**Trades with deterministic context timeline:**
```sql
SELECT t.trade_id, t.strategy_name, t.direction, t.net_pnl, t.outcome,
       dt.snapshot_time, dt.bias, dt.cri_status, dt.day_type, dt.tpo_shape
FROM trades t
JOIN deterministic_tape dt ON t.session_date = dt.session_date
WHERE t.run_id = ?
  AND dt.snapshot_time BETWEEN ? AND ?
ORDER BY t.session_date, dt.snapshot_time
```

**Avoidable losses (CRI was STAND_DOWN):**
```sql
SELECT t.strategy_name, t.session_date, t.direction, t.net_pnl, t.exit_reason
FROM v_trade_context t
WHERE t.run_id = ? AND t.outcome = 'LOSS' AND t.ctx_cri_status = 'STAND_DOWN'
ORDER BY t.net_pnl
```

## Notes
- This skill uses deterministic data only (no LLM calls). The AI analysis layer (Phase 4) will build on these assessments.
- Deterministic tape may not be available for all sessions yet. Skip trades without tape data.
- Focus on actionable insights: "what should change" not just "what happened"
