# 09 — Building the Backtest Knowledge Base

> **Purpose**: Two-tier DuckDB architecture — a **research lab** where Claude autonomously discovers, backtests, tunes, and correlates strategies, and a **production store** where live agents consume distilled knowledge and annotate trades as they learn.
>
> **Problem**: We've run hundreds of backtests and strategy studies. The results live in .md files, terminal output, and human memory. We can't answer "which stop model works best on narrow IB B-Days?" without re-running everything. Regime changes break working strategies and we have no systematic way to detect or adapt. Knowledge is being lost.
>
> **Solution**: Two DuckDB instances. **Research DB** — Claude explores freely: discovers strategies, backtests entry/stop/target combos, correlates with deterministic data, tags observations, identifies regime-dependent behavior. **Production DB** — condensed, validated knowledge consumed by live agents. Agents annotate trades as they execute, feeding learnings back into research.
>
> **Key insight**: Claude should not just run backtests you ask for — it should autonomously study, find new strategies, tune parameters, and build a body of knowledge about what works in which regimes. The data warehouse IS the memory.
>
> **Status**: Design document
> **Date**: 2026-03-05

---

## 1. The Vision: Autonomous Research → Validated Production Knowledge

### The Loop

```
┌────────────────────────────────────────────────────────────────────┐
│                    RESEARCH DB (Claude's Lab)                      │
│                    data/research.duckdb                            │
│                                                                    │
│  Claude autonomously:                                              │
│    1. Discovers strategy ideas (MACD, VWAP fade, delta divergence) │
│    2. Implements & backtests across 266+ sessions                  │
│    3. Tests every entry × stop × target combination                │
│    4. Correlates wins/losses with deterministic context             │
│    5. Identifies regime-dependent behavior                          │
│    6. Tags observations, updates confidence levels                 │
│    7. When a strategy stabilizes → PUBLISH to production           │
│                                                                    │
│  Tables: backtest_runs, trades, combo_trades, session_context,     │
│          experiments, observations, regime_analysis, correlations   │
└─────────────────────────────┬──────────────────────────────────────┘
                              │ PUBLISH (validated knowledge)
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│                   PRODUCTION DB (Agent Knowledge)                  │
│                   data/rockit.duckdb                               │
│                                                                    │
│  Agents consume:                                                   │
│    - Strategy configs with proven stop/target/entry combos         │
│    - Regime-conditional rules (narrow IB → use X, wide IB → use Y) │
│    - Historical pattern statistics for Pattern Miner               │
│    - Confidence calibration data                                   │
│                                                                    │
│  Agents annotate:                                                  │
│    - Live trade outcomes + context                                 │
│    - Debate reasoning (Advocate/Skeptic/Orchestrator)              │
│    - Regime classification accuracy                                │
│    - "This trade won because..." / "This trade lost because..."    │
│                                                                    │
│  Tables: strategy_configs, regime_rules, trade_history,            │
│          agent_annotations, pattern_statistics                     │
└─────────────────────────────┬──────────────────────────────────────┘
                              │ FEEDBACK (agent learnings)
                              ▼
                    Back to RESEARCH DB for validation
```

### Why Two Instances

| | Research DB | Production DB |
|---|---|---|
| **Purpose** | Exploration, experimentation | Execution, annotation |
| **Size** | Large (every combo, every run, full snapshots) | Compact (distilled, validated only) |
| **Who writes** | Claude (autonomous research), human (observations) | Agents (live trades, annotations) |
| **Who reads** | Claude (correlation studies), human (queries) | Agents (Pattern Miner, Historian) |
| **Schema** | Wide, flexible, JSON-heavy | Narrow, fast, indexed |
| **Lifecycle** | Append-heavy, never delete | Read-heavy, pruned periodically |
| **Regime** | Offline, batch analysis | Real-time, per-bar queries |

---

## 2. What We Have vs What We Need

### Knowledge That Exists Today (Scattered)

| Source | Format | Examples | Problem |
|--------|--------|----------|---------|
| `brainstorm/*.md` | Prose + tables | OR Rev 64.4% WR, 80P needs 30-bar acceptance | Can't query, can't join with data |
| Terminal output | Ephemeral | "548 trades, 51.5% WR, 1.91 PF" | Gone after session closes |
| `data/results/*.json` | Per-run snapshots | Strategy breakdown by session | No cross-run comparison |
| `research/strategy-studies/` | Study docs | Trend Following 58% WR, 2.8 PF | Static, no correlation with market conditions |
| Human memory | Notes | "80P works better on narrow IB days" | Unverified, unfalsifiable |
| Regime knowledge | Nowhere | "This stopped working when VIX spiked" | Not captured, not queryable |

### What We Want to Ask

```sql
-- Which stop model works best for OR Reversal on narrow IB days?
SELECT stop_model, COUNT(*) as trades,
       ROUND(AVG(CASE WHEN net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as wr,
       ROUND(SUM(CASE WHEN net_pnl > 0 THEN net_pnl ELSE 0 END) /
             NULLIF(ABS(SUM(CASE WHEN net_pnl <= 0 THEN net_pnl ELSE 0 END)), 0), 2) as pf
FROM combo_trades
WHERE strategy = 'Opening Range Rev' AND ib_width_class = 'narrow'
GROUP BY stop_model
ORDER BY pf DESC;

-- What day type + IB width combos produce the most winning B-Day trades?
SELECT day_type, ib_width_class, COUNT(*) as n,
       ROUND(AVG(CASE WHEN net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as wr
FROM trades t
JOIN session_context sc ON t.session_date = sc.session_date
GROUP BY day_type, ib_width_class
HAVING COUNT(*) >= 5
ORDER BY wr DESC;

-- Does VWAP position at entry time predict trade success?
SELECT vwap_position, outcome, COUNT(*) as n, ROUND(AVG(net_pnl), 2) as avg_pnl
FROM trades t
JOIN signal_context sx ON t.signal_id = sx.signal_id
GROUP BY vwap_position, outcome
ORDER BY vwap_position, outcome;
```

---

## 2. Architecture: Local DuckDB Research Warehouse

```
                     ┌─────────────────────────────────┐
                     │     data/rockit_research.duckdb   │
                     │                                   │
Backtest Engine ────→│  backtest_runs                    │
                     │  trades                           │
Combo Runner ───────→│  combo_runs                       │
                     │  combo_trades                     │
Deterministic ──────→│  session_context                  │
Orchestrator         │  deterministic_snapshots          │
                     │                                   │
Manual Tags ────────→│  observations                     │
& Study Notes        │  tags                             │
                     │                                   │
                     │  ──── Views ────                  │
                     │  v_trade_context (trade + session) │
                     │  v_combo_comparison               │
                     │  v_strategy_by_regime             │
                     └─────────────────────────────────┘
                              │
                    SQL queries / Python API
                              │
                     ┌────────┴────────┐
                     │  Notebooks /    │
                     │  CLI reports /  │
                     │  LLM context    │
                     └─────────────────┘
```

### Why DuckDB

- **Local-first**: No server, just a file. Matches our dev philosophy
- **Columnar analytics**: Fast aggregation over millions of rows
- **JSON support**: Native JSON columns for flexible metadata (deterministic snapshots)
- **SQL interface**: Queryable by humans, scripts, and eventually LLM agents
- **Pandas interop**: `duckdb.sql("...").df()` → instant DataFrame
- **Already in stack**: `MetricsCollector` already uses DuckDB (`rockit_core.metrics.collector`)

---

## 3. Schema Design

### 3.1 Backtest Runs (Metadata)

```sql
CREATE TABLE backtest_runs (
    run_id          VARCHAR PRIMARY KEY,   -- UUID or timestamp-based
    run_timestamp   TIMESTAMP NOT NULL,
    instrument      VARCHAR NOT NULL,      -- NQ, ES, YM
    sessions_count  INTEGER,
    strategies      JSON,                  -- ["Opening Range Rev", "B-Day", ...]
    config          JSON,                  -- risk_per_trade, max_contracts, slippage, etc.

    -- Aggregate results
    total_trades    INTEGER,
    win_rate        DOUBLE,
    profit_factor   DOUBLE,
    net_pnl         DOUBLE,
    max_drawdown    DOUBLE,

    -- Git context
    git_branch      VARCHAR,
    git_commit      VARCHAR,

    notes           TEXT                   -- Human annotation
);
```

### 3.2 Trades (Per-Trade Detail)

```sql
CREATE TABLE trades (
    trade_id        INTEGER PRIMARY KEY,
    run_id          VARCHAR REFERENCES backtest_runs(run_id),

    -- Identity
    strategy_name   VARCHAR NOT NULL,
    setup_type      VARCHAR NOT NULL,
    session_date    VARCHAR NOT NULL,
    instrument      VARCHAR NOT NULL,

    -- Timing
    entry_time      TIMESTAMP,
    exit_time       TIMESTAMP,
    bars_held       INTEGER,

    -- Execution
    direction       VARCHAR NOT NULL,      -- LONG / SHORT
    contracts       INTEGER,
    entry_price     DOUBLE NOT NULL,
    exit_price      DOUBLE NOT NULL,
    stop_price      DOUBLE NOT NULL,
    target_price    DOUBLE NOT NULL,

    -- P&L
    gross_pnl       DOUBLE,
    commission      DOUBLE,
    slippage_cost   DOUBLE,
    net_pnl         DOUBLE,
    exit_reason     VARCHAR,               -- STOP, TARGET, EOD, DAILY_LOSS, VWAP_BREACH_PM

    -- Classification
    day_type        VARCHAR,
    trend_strength  VARCHAR,

    -- Derived
    risk_points     DOUBLE,
    reward_points   DOUBLE,
    r_multiple      DOUBLE,                -- Actual R achieved
    outcome         VARCHAR GENERATED ALWAYS AS (
        CASE WHEN net_pnl > 0 THEN 'WIN' ELSE 'LOSS' END
    ) STORED
);
```

### 3.3 Combo Runs (ComboRunner Output)

```sql
CREATE TABLE combo_runs (
    combo_run_id    VARCHAR PRIMARY KEY,
    run_timestamp   TIMESTAMP NOT NULL,
    instrument      VARCHAR NOT NULL,
    strategy_name   VARCHAR NOT NULL,

    -- What was tested
    stop_models     JSON,                  -- ["1_atr", "2_atr", "fixed_15pts"]
    target_models   JSON,                  -- ["2r", "3r", "ib_1.5x"]
    combo_count     INTEGER,

    -- Best combo found
    best_stop       VARCHAR,
    best_target     VARCHAR,
    best_pf         DOUBLE,
    best_wr         DOUBLE,
    best_net_pnl    DOUBLE,

    notes           TEXT
);
```

### 3.4 Combo Trades (Per-Combo × Per-Trade)

```sql
CREATE TABLE combo_trades (
    id              INTEGER PRIMARY KEY,
    combo_run_id    VARCHAR REFERENCES combo_runs(combo_run_id),

    -- Combo identity
    strategy_name   VARCHAR NOT NULL,
    stop_model      VARCHAR NOT NULL,      -- "original", "1_atr", "fixed_15pts", etc.
    target_model    VARCHAR NOT NULL,      -- "original", "2r", "ib_1.5x", etc.

    -- Per-trade
    session_date    VARCHAR NOT NULL,
    direction       VARCHAR,
    entry_price     DOUBLE,
    stop_price      DOUBLE,
    target_price    DOUBLE,
    exit_price      DOUBLE,
    net_pnl         DOUBLE,
    exit_reason     VARCHAR,
    r_multiple      DOUBLE,

    -- Context at signal time
    day_type        VARCHAR,
    ib_range        DOUBLE,
    ib_width_class  VARCHAR,
    vwap_position   VARCHAR,               -- 'above_vwap', 'below_vwap'
    trend_strength  VARCHAR
);
```

### 3.5 Session Context (Deterministic Features)

```sql
CREATE TABLE session_context (
    session_date    VARCHAR PRIMARY KEY,
    instrument      VARCHAR NOT NULL,

    -- IB metrics
    ib_high         DOUBLE,
    ib_low          DOUBLE,
    ib_range        DOUBLE,
    ib_mid          DOUBLE,
    ib_width_class  VARCHAR,               -- narrow, normal, wide
    ib_atr_ratio    DOUBLE,

    -- Classification
    day_type_final  VARCHAR,               -- Final day type (end of session)
    trend_strength  VARCHAR,

    -- Indicators at IB close
    vwap_at_ib      DOUBLE,
    ema20_at_ib     DOUBLE,
    atr14           DOUBLE,
    adx14           DOUBLE,
    rsi14           DOUBLE,

    -- Prior session
    prior_close     DOUBLE,
    prior_vwap      DOUBLE,
    prior_va_poc    DOUBLE,
    prior_va_vah    DOUBLE,
    prior_va_val    DOUBLE,
    gap_status      VARCHAR,               -- 'above_va', 'inside_va', 'below_va'

    -- Premarket
    overnight_range DOUBLE,
    overnight_high  DOUBLE,
    overnight_low   DOUBLE,
    asia_range      DOUBLE,
    london_range    DOUBLE,

    -- Session outcome
    session_range   DOUBLE,
    max_extension   DOUBLE,
    extension_dir   VARCHAR,               -- 'up', 'down', 'both', 'none'

    -- OR context
    or_sweep_dir    VARCHAR,               -- 'UP', 'DOWN', 'BOTH', 'NONE'
    or_acceptance   VARCHAR,               -- 'LONG', 'SHORT', 'NONE'
    opening_drive   VARCHAR,               -- 'DRIVE_UP', 'DRIVE_DOWN', 'ROTATION'

    -- Full snapshot for deep queries
    snapshot_json   JSON
);
```

### 3.6 Deterministic Tape (The Growing Time-Series)

This is the foundational data layer. Every session generates ~78 deterministic snapshots (5-min intervals across RTH 9:30-16:00). These are pure market structure observations — no LLM, no opinion. The table grows forever as we add more sessions.

```sql
CREATE TABLE deterministic_tape (
    session_date    VARCHAR NOT NULL,
    snapshot_time   VARCHAR NOT NULL,       -- 'HH:MM' (5-min intervals)
    instrument      VARCHAR NOT NULL,
    bar_index       INTEGER,               -- 0-based from session start

    -- Price state at this moment
    close           DOUBLE,
    vwap            DOUBLE,
    ema20           DOUBLE,
    atr14           DOUBLE,
    adx14           DOUBLE,
    rsi14           DOUBLE,

    -- Market structure at this moment
    day_type        VARCHAR,               -- Classification at this point in time
    ib_direction    VARCHAR,               -- INSIDE / BULL / BEAR
    price_vs_ib     VARCHAR,               -- 'above_ibh', 'inside', 'below_ibl'
    ib_extension_pct DOUBLE,               -- How far beyond IB (% of IB range)

    -- Profile data at this moment
    dpoc_price      DOUBLE,
    dpoc_migration  VARCHAR,               -- 'rising', 'falling', 'stable'
    tpo_shape       VARCHAR,               -- 'p_shape', 'b_shape', 'normal', 'elongated'
    va_high         DOUBLE,
    va_low          DOUBLE,

    -- Order flow at this moment
    cumulative_delta DOUBLE,
    delta_trend     VARCHAR,               -- 'positive', 'negative', 'neutral'
    wick_parade_bull INTEGER,
    wick_parade_bear INTEGER,

    -- Confluence / CRI
    cri_score       DOUBLE,
    cri_status      VARCHAR,               -- 'GO', 'CAUTION', 'STAND_DOWN'
    confluence_count INTEGER,

    -- Full 38-module snapshot (for deep queries)
    snapshot_json   JSON,

    PRIMARY KEY (session_date, snapshot_time, instrument)
);
```

### 3.7 LLM Tape Annotations (Layered on Deterministic Data)

Once the LLM is trained, its tape readings layer on top of the deterministic data. Claude can also annotate retrospectively — reviewing historical sessions and adding analysis.

```sql
CREATE TABLE tape_annotations (
    annotation_id   INTEGER PRIMARY KEY,
    session_date    VARCHAR NOT NULL,
    snapshot_time   VARCHAR NOT NULL,       -- Links to deterministic_tape
    instrument      VARCHAR NOT NULL,

    -- Who annotated
    annotator       VARCHAR NOT NULL,       -- 'qwen3.5', 'opus', 'claude_review', 'human'
    annotated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- The analysis
    tape_read       TEXT NOT NULL,          -- Full tape reading at this moment
    market_bias     VARCHAR,               -- 'bullish', 'bearish', 'neutral', 'unclear'
    conviction      DOUBLE,                -- 0.0 to 1.0

    -- Strategy observations at this moment
    active_setups   JSON,                  -- ["or_rev_short", "80p_long_developing"]
    setup_quality   JSON,                  -- {"or_rev_short": 0.85, "80p_long": 0.6}

    -- Hindsight (added after session closes)
    was_correct     BOOLEAN,               -- Did the bias/setup play out?
    actual_outcome  TEXT,                  -- What actually happened
    lesson_learned  TEXT,                  -- What should the LLM learn from this?

    -- Benchmarking
    benchmark_score DOUBLE,                -- 0-100 quality score for this annotation
    benchmark_notes TEXT,                  -- Why this score

    FOREIGN KEY (session_date, snapshot_time, instrument)
        REFERENCES deterministic_tape(session_date, snapshot_time, instrument)
);
```

### How This Grows

```
Day 1:   259 sessions × 78 snapshots = 20,202 deterministic rows (pure data)
Day 30:  280 sessions × 78 snapshots = 21,840 rows + new daily sessions
Day 90:  320 sessions × 78 snapshots = 24,960 rows
Year 1:  ~510 sessions × 78 = 39,780 rows

LLM annotations: initially 0, then:
  - Claude reviews 5 historical sessions/week → +390 annotations/week
  - Live model produces 78 annotations/day → +390/week
  - By month 3: ~5,000 annotations layered on deterministic data

Agent annotations: post-trade reviews
  - ~3-5 trades/day × 252 trading days = ~1,000 annotations/year
```

### The Queries This Enables

```sql
-- What did the tape look like 30 minutes before every winning OR Rev trade?
SELECT dt.snapshot_time, dt.day_type, dt.dpoc_migration, dt.delta_trend,
       dt.cri_status, dt.ib_extension_pct
FROM deterministic_tape dt
JOIN trades t ON dt.session_date = t.session_date
WHERE t.strategy_name = 'Opening Range Rev' AND t.net_pnl > 0
    AND dt.snapshot_time = TIME_FORMAT(t.entry_time - INTERVAL 30 MINUTE, 'HH:MM');

-- How accurate are LLM tape readings? Benchmark over time
SELECT annotator,
       COUNT(*) as total,
       ROUND(AVG(CASE WHEN was_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as accuracy,
       ROUND(AVG(benchmark_score), 1) as avg_quality
FROM tape_annotations
WHERE was_correct IS NOT NULL
GROUP BY annotator;

-- What deterministic features predict winning trades? (correlation mining)
SELECT
    dt.cri_status,
    dt.dpoc_migration,
    dt.delta_trend,
    COUNT(*) as n,
    ROUND(AVG(CASE WHEN t.net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as wr,
    ROUND(AVG(t.net_pnl), 2) as avg_pnl
FROM deterministic_tape dt
JOIN trades t ON dt.session_date = t.session_date
    AND dt.snapshot_time = STRFTIME(t.entry_time, '%H:%M')
GROUP BY dt.cri_status, dt.dpoc_migration, dt.delta_trend
HAVING COUNT(*) >= 5
ORDER BY wr DESC;

-- Claude benchmark review: find sessions where LLM was wrong, study why
SELECT ta.session_date, ta.snapshot_time, ta.tape_read, ta.market_bias,
       ta.actual_outcome, ta.lesson_learned
FROM tape_annotations ta
WHERE ta.was_correct = FALSE AND ta.annotator = 'qwen3.5'
ORDER BY ta.session_date DESC
LIMIT 20;
```

### 3.8 Observations & Tags (Structured Notes)

```sql
CREATE TABLE observations (
    obs_id          INTEGER PRIMARY KEY,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Scope
    scope           VARCHAR NOT NULL,      -- 'strategy', 'session', 'setup', 'global'
    strategy_name   VARCHAR,               -- NULL for global observations
    session_date    VARCHAR,               -- NULL for global observations

    -- Content
    observation     TEXT NOT NULL,          -- The insight
    evidence        TEXT,                  -- Supporting data / query
    source          VARCHAR,               -- 'backtest', 'combo_study', 'manual', 'brainstorm'
    confidence      VARCHAR DEFAULT 'hypothesis',  -- 'hypothesis', 'tested', 'confirmed', 'disproven'

    -- References
    run_id          VARCHAR,               -- Backtest run that produced this
    combo_run_id    VARCHAR                -- Combo run that produced this
);

CREATE TABLE tags (
    obs_id          INTEGER REFERENCES observations(obs_id),
    tag             VARCHAR NOT NULL,      -- 'stop_model', 'ib_width', 'day_type', 'regime', etc.
    PRIMARY KEY (obs_id, tag)
);
```

---

## 4. Materialized Views for Common Queries

### 4.1 Trade + Session Context (The Join Everyone Needs)

```sql
CREATE VIEW v_trade_context AS
SELECT
    t.*,
    sc.ib_width_class,
    sc.day_type_final,
    sc.atr14,
    sc.adx14,
    sc.gap_status,
    sc.or_sweep_dir,
    sc.opening_drive,
    sc.overnight_range,
    sc.prior_va_poc,
    CASE WHEN t.entry_price > sc.vwap_at_ib THEN 'above' ELSE 'below' END as vwap_position
FROM trades t
LEFT JOIN session_context sc ON t.session_date = sc.session_date;
```

### 4.2 Combo Comparison (Ranked by Strategy)

```sql
CREATE VIEW v_combo_comparison AS
SELECT
    strategy_name,
    stop_model,
    target_model,
    COUNT(*) as trades,
    ROUND(AVG(CASE WHEN net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as wr,
    ROUND(SUM(CASE WHEN net_pnl > 0 THEN net_pnl ELSE 0 END) /
          NULLIF(ABS(SUM(CASE WHEN net_pnl <= 0 THEN net_pnl ELSE 0 END)), 0), 2) as pf,
    ROUND(SUM(net_pnl), 2) as net_pnl,
    ROUND(AVG(r_multiple), 2) as avg_r
FROM combo_trades
GROUP BY strategy_name, stop_model, target_model
ORDER BY strategy_name, pf DESC;
```

### 4.3 Strategy Performance by Market Regime

```sql
CREATE VIEW v_strategy_by_regime AS
SELECT
    t.strategy_name,
    sc.ib_width_class,
    sc.day_type_final,
    sc.gap_status,
    COUNT(*) as trades,
    ROUND(AVG(CASE WHEN t.net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as wr,
    ROUND(SUM(t.net_pnl), 2) as net_pnl
FROM trades t
JOIN session_context sc ON t.session_date = sc.session_date
GROUP BY t.strategy_name, sc.ib_width_class, sc.day_type_final, sc.gap_status
HAVING COUNT(*) >= 3
ORDER BY t.strategy_name, wr DESC;
```

---

## 5. Data Pipeline: How Data Gets In

### 5.1 Backtest Run Ingestion

After every `run_backtest.py` run, persist results:

```python
def persist_backtest_run(db: duckdb.DuckDBPyConnection, result: BacktestResult,
                         instrument: str, strategies: list, config: dict):
    """Write a backtest run + all trades to DuckDB."""
    run_id = f"{instrument}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Insert run metadata
    db.execute("""
        INSERT INTO backtest_runs (run_id, run_timestamp, instrument, ...)
        VALUES (?, CURRENT_TIMESTAMP, ?, ...)
    """, [run_id, instrument, ...])

    # Insert all trades
    for i, trade in enumerate(result.trades):
        db.execute("""
            INSERT INTO trades (trade_id, run_id, strategy_name, ...)
            VALUES (?, ?, ?, ...)
        """, [i, run_id, trade.strategy_name, ...])
```

### 5.2 Combo Runner Ingestion

After every `run_combo_backtest.py` run:

```python
def persist_combo_run(db, combo_results: list, strategy_name: str, instrument: str):
    """Write combo results + per-combo trades to DuckDB."""
    combo_run_id = f"combo_{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Insert combo run metadata
    db.execute("INSERT INTO combo_runs (...) VALUES (...)", [...])

    # Insert per-combo trades
    for result in combo_results:
        for trade in result.backtest_result.trades:
            db.execute("INSERT INTO combo_trades (...) VALUES (...)", [...])
```

### 5.3 Session Context Ingestion

Run deterministic orchestrator for each session and persist:

```python
def persist_session_context(db, session_date: str, session_context: dict, snapshot: dict):
    """Write session-level deterministic context to DuckDB."""
    db.execute("""
        INSERT OR REPLACE INTO session_context
        (session_date, instrument, ib_high, ib_low, ib_range, ...)
        VALUES (?, ?, ?, ?, ?, ...)
    """, [session_date, ...])
```

### 5.4 Manual Observation Ingestion

CLI or script for adding tagged observations:

```bash
# Add an observation
uv run python scripts/add_observation.py \
    --scope strategy \
    --strategy "Opening Range Rev" \
    --observation "OR Rev performs significantly better on narrow IB days (IB < 0.7x ATR)" \
    --evidence "SELECT ib_width_class, wr FROM v_strategy_by_regime WHERE strategy_name = 'Opening Range Rev'" \
    --source backtest \
    --confidence tested \
    --tags ib_width,or_reversal,narrow_ib
```

---

## 6. Correlation Studies: The Queries We Want

### 6.1 Stop Model Sensitivity by Strategy

> "For OR Reversal, does a wider stop reduce stopped-out-then-right trades?"

```sql
SELECT
    stop_model,
    COUNT(*) as trades,
    ROUND(AVG(CASE WHEN net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as wr,
    ROUND(SUM(CASE WHEN net_pnl > 0 THEN net_pnl ELSE 0 END) /
          NULLIF(ABS(SUM(CASE WHEN net_pnl <= 0 THEN net_pnl ELSE 0 END)), 0), 2) as pf,
    ROUND(SUM(net_pnl), 2) as net_pnl,
    SUM(CASE WHEN exit_reason = 'STOP' THEN 1 ELSE 0 END) as stop_outs
FROM combo_trades
WHERE strategy_name = 'Opening Range Rev'
GROUP BY stop_model
ORDER BY pf DESC;
```

### 6.2 Day Type × Target Model Matrix

> "Do trend days favor larger R targets? Do B-Days favor level-based targets?"

```sql
SELECT
    day_type,
    target_model,
    COUNT(*) as n,
    ROUND(AVG(CASE WHEN net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as wr,
    ROUND(AVG(r_multiple), 2) as avg_r,
    ROUND(SUM(net_pnl), 2) as total_pnl
FROM combo_trades
WHERE strategy_name = 'Opening Range Rev'
GROUP BY day_type, target_model
HAVING COUNT(*) >= 5
ORDER BY day_type, total_pnl DESC;
```

### 6.3 IB Width Impact on Execution Model

> "Does narrow IB favor tighter stops (less room for reversal) or wider stops (volatility expansion incoming)?"

```sql
SELECT
    ib_width_class,
    stop_model,
    COUNT(*) as trades,
    ROUND(AVG(CASE WHEN net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as wr,
    ROUND(SUM(net_pnl), 2) as net_pnl
FROM combo_trades ct
JOIN session_context sc ON ct.session_date = sc.session_date
GROUP BY ib_width_class, stop_model
HAVING COUNT(*) >= 5
ORDER BY ib_width_class, net_pnl DESC;
```

### 6.4 Gap Status × Strategy Performance

> "Do strategies perform differently when we open above vs below vs inside prior VA?"

```sql
SELECT
    sc.gap_status,
    t.strategy_name,
    COUNT(*) as trades,
    ROUND(AVG(CASE WHEN t.net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as wr,
    ROUND(SUM(t.net_pnl), 2) as net_pnl
FROM trades t
JOIN session_context sc ON t.session_date = sc.session_date
GROUP BY sc.gap_status, t.strategy_name
HAVING COUNT(*) >= 3
ORDER BY sc.gap_status, net_pnl DESC;
```

### 6.5 OR Sweep Direction × Stop Model Effectiveness

> "When Judas sweeps UP (short signal), which stop model protects best?"

```sql
SELECT
    sc.or_sweep_dir,
    ct.stop_model,
    COUNT(*) as trades,
    ROUND(AVG(CASE WHEN ct.net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as wr,
    SUM(CASE WHEN ct.exit_reason = 'STOP' THEN 1 ELSE 0 END) as stopped_out,
    ROUND(SUM(ct.net_pnl), 2) as net_pnl
FROM combo_trades ct
JOIN session_context sc ON ct.session_date = sc.session_date
WHERE ct.strategy_name = 'Opening Range Rev'
GROUP BY sc.or_sweep_dir, ct.stop_model
HAVING COUNT(*) >= 3
ORDER BY sc.or_sweep_dir, net_pnl DESC;
```

### 6.6 Overnight Range as Regime Filter

> "Do strategies behave differently after wide overnight ranges (>200pts)?"

```sql
SELECT
    CASE WHEN sc.overnight_range > 200 THEN 'wide_ON'
         WHEN sc.overnight_range > 100 THEN 'normal_ON'
         ELSE 'narrow_ON' END as on_regime,
    t.strategy_name,
    COUNT(*) as trades,
    ROUND(AVG(CASE WHEN t.net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as wr,
    ROUND(SUM(t.net_pnl), 2) as net_pnl
FROM trades t
JOIN session_context sc ON t.session_date = sc.session_date
GROUP BY on_regime, t.strategy_name
HAVING COUNT(*) >= 3
ORDER BY on_regime, net_pnl DESC;
```

### 6.7 Entry Model Study (Future — When Strategies Are Retrofitted)

> "For OR Reversal signals, which entry model produces the best results?"

```sql
SELECT
    entry_model,
    stop_model,
    target_model,
    COUNT(*) as trades,
    ROUND(AVG(CASE WHEN net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as wr,
    ROUND(SUM(CASE WHEN net_pnl > 0 THEN net_pnl ELSE 0 END) /
          NULLIF(ABS(SUM(CASE WHEN net_pnl <= 0 THEN net_pnl ELSE 0 END)), 0), 2) as pf,
    ROUND(SUM(net_pnl), 2) as net_pnl
FROM combo_trades
WHERE strategy_name = 'Opening Range Rev'
GROUP BY entry_model, stop_model, target_model
ORDER BY net_pnl DESC;
```

---

## 7. Seeding: Migrating Existing Knowledge

### 7.1 From Backtest Results

Current results in `data/results/` → parse and insert into `backtest_runs` + `trades`.

### 7.2 From Strategy Studies

The `.md` study files contain verified statistics. Seed as observations:

```sql
INSERT INTO observations (scope, strategy_name, observation, source, confidence)
VALUES
    ('strategy', 'Opening Range Rev', 'Best first-hour strategy: 64.4% WR, 2.96 PF, 101 trades over 266 NQ sessions', 'backtest', 'confirmed'),
    ('strategy', 'Opening Range Rev', '50% retest entry with ±0.5×ATR tolerance band', 'backtest', 'confirmed'),
    ('strategy', 'Opening Range Rev', '2×ATR14 stop, 2R target', 'backtest', 'confirmed'),
    ('strategy', 'B-Day', 'First touch only — 2nd/3rd touches degrade to ~35% WR', 'backtest', 'confirmed'),
    ('strategy', 'B-Day', 'VWAP > IB mid at touch time boosts confidence (46% raw → higher filtered)', 'backtest', 'tested'),
    ('strategy', '80P Rule', '30-bar candle acceptance (not 2×5-min). Entry at acceptance close', 'backtest', 'confirmed'),
    ('strategy', 'Mean Reversion VWAP', 'LOSING: 42.6% WR, 0.91 PF. Only use on ADX < 20 balance days', 'backtest', 'confirmed'),
    ('global', NULL, 'First hour is the money: 9:30-10:30 precision framework', 'manual', 'confirmed'),
    ('global', NULL, 'Caution over conviction: never chase, recommend retracement entry', 'manual', 'confirmed'),
    ('global', NULL, 'Narrow IB (< 0.7x ATR) → compressed energy, expect large moves', 'manual', 'tested');
```

### 7.3 From Deterministic Snapshots

Existing `data/json_snapshots/deterministic_*.jsonl` → parse and load into `session_context`.

### 7.4 From Systematic Observations (brainstorm/08)

Extract the verified accuracy-check tables into structured observations with tags.

---

## 8. Autonomous Research Loop: Claude as Strategy Scientist

### The Problem with Human-Directed Backtesting

Today the workflow is: human has an idea → asks Claude to implement → runs backtest → reads output → forms opinion → moves on. The knowledge lives in the human's head and a few .md files. This doesn't scale and doesn't compound.

### The New Model: Claude Explores Independently

Claude should operate like a quantitative researcher with a lab notebook (DuckDB). Given a research question or even just "go study what works," Claude should:

```
1. HYPOTHESIZE — "Does B-Day work better with ATR stops than fixed buffer stops?"
2. IMPLEMENT  — Build the strategy variant / combo configuration
3. BACKTEST   — Run across all 266+ sessions
4. PERSIST    — Write every trade + context to research DB
5. ANALYZE    — Query for patterns, correlations, regime effects
6. OBSERVE    — Tag findings with confidence levels
7. ITERATE    — "The ATR stop helped on normal IB days but hurt on narrow IB.
                 New hypothesis: B-Day needs regime-conditional stops."
8. REPEAT     — Go deeper or move to next strategy
```

### Research DB Tables for Autonomous Study

```sql
-- Track what Claude is studying and what it found
CREATE TABLE experiments (
    experiment_id   VARCHAR PRIMARY KEY,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- What
    hypothesis      TEXT NOT NULL,          -- "ATR stop beats fixed buffer for B-Day"
    strategy_name   VARCHAR,
    variables       JSON,                  -- {"stop_models": ["1_atr", "fixed_10pts"], ...}

    -- How
    method          TEXT,                  -- "Combo backtest across 266 NQ sessions"
    combo_run_id    VARCHAR,               -- Link to combo_runs
    run_id          VARCHAR,               -- Link to backtest_runs

    -- Result
    status          VARCHAR DEFAULT 'planned',  -- planned, running, complete, abandoned
    finding         TEXT,                  -- "ATR stop improves PF from 1.47 → 1.83 on normal IB"
    confidence      VARCHAR,               -- hypothesis, tested, confirmed, disproven

    -- Follow-up
    next_hypothesis TEXT,                  -- "Does this hold for narrow IB?"
    parent_id       VARCHAR,               -- Chain experiments together

    -- Context
    regime_notes    TEXT                   -- "Only valid in normal volatility regime"
);
```

### What Claude Should Study Autonomously

| Research Area | Example Hypotheses | Method |
|---|---|---|
| **Entry model optimization** | "Does IFVG entry beat 50% retest for OR Rev?" | Combo runner with entry model variants |
| **Stop model sensitivity** | "Wider stops reduce stopped-out-then-right for trend strategies" | Combo runner: 1/1.5/2/2.5/3 ATR |
| **Target model tuning** | "IB-range targets outperform R-multiples on B-Days" | Combo runner: 2R/3R vs IB_1.5x/adaptive |
| **New strategy discovery** | "MACD + VWAP filter after IB → is there an edge?" | Implement, backtest, analyze |
| **Regime conditioning** | "80P only works when ADX < 20 and IB is normal width" | Filter trades by regime, compare |
| **Failure analysis** | "Why do 80P trades fail? Missing deterministic signal?" | Join losing trades with session_context |
| **Time-of-day effects** | "Does OR Rev degrade after 10:15? By how much?" | Group trades by entry time bucket |
| **Cross-strategy conflict** | "When OR Rev and 80P fire same session, which wins?" | Co-occurrence analysis |

### Claude's Research Session Flow

```python
# Pseudocode for what an autonomous research session looks like

async def research_session(db, topic="regime_sensitivity"):
    # 1. Check what we already know
    known = db.sql("SELECT * FROM observations WHERE tag = ? AND confidence IN ('tested','confirmed')", [topic])

    # 2. Identify gaps
    untested = db.sql("SELECT * FROM observations WHERE tag = ? AND confidence = 'hypothesis'", [topic])

    # 3. Pick highest-value hypothesis to test
    hypothesis = pick_most_impactful(untested)

    # 4. Design experiment
    experiment = create_experiment(hypothesis)
    db.persist_experiment(experiment)

    # 5. Run backtest / combo study
    results = combo_runner.run(...)
    db.persist_combo_run(results)

    # 6. Analyze results
    analysis = db.sql("""
        SELECT regime, stop_model, wr, pf, net_pnl
        FROM v_combo_by_regime
        WHERE experiment_id = ?
    """, [experiment.id])

    # 7. Record findings
    db.update_experiment(experiment.id, finding=analysis.summary, confidence='tested')

    # 8. Generate follow-up hypotheses
    if analysis.shows_regime_dependency:
        db.insert_observation(
            "B-Day ATR stop works on normal IB (PF 1.83) but fails on narrow IB (PF 0.92)",
            confidence='tested', tags=['b_day', 'stop_model', 'regime', 'ib_width']
        )
        db.insert_experiment(
            hypothesis="B-Day needs IBEdgeStop on narrow IB days and ATRStop on normal IB",
            parent_id=experiment.id
        )
```

---

## 9. Regime Analysis: The Key Challenge

### Why Regime Change Breaks Everything

A strategy that works in one market regime fails in another. OR Rev works great in normal volatility but gets whipsawed in high-vol FOMC sessions. B-Day works on balance days but fires false signals on trend days that briefly touch IBL.

The research DB must make regime-dependent behavior **visible and queryable**.

### Regime Dimensions

| Dimension | Values | Source |
|---|---|---|
| **IB width** | narrow (< 0.7x ATR), normal, wide (> 1.3x ATR) | `session_context.ib_width_class` |
| **Volatility** | low (ATR < 100), normal, high (ATR > 200) | `session_context.atr14` |
| **Trend strength** | none (ADX < 20), moderate (20-25), strong (> 25) | `session_context.adx14` |
| **Gap status** | above_va, inside_va, below_va | `session_context.gap_status` |
| **Day type** | trend_bull/bear, p_day, b_day, neutral | `session_context.day_type_final` |
| **Overnight range** | narrow (< 80), normal, wide (> 200) | `session_context.overnight_range` |
| **OR context** | judas_up, judas_down, acceptance, rotation, both | `session_context.or_sweep_dir` |
| **VIX regime** | low (< 15), normal (15-25), high (> 25) | Future: `session_context.vix_close` |

### Regime-Conditional Rules Table (Research DB)

```sql
CREATE TABLE regime_rules (
    rule_id         INTEGER PRIMARY KEY,
    experiment_id   VARCHAR REFERENCES experiments(experiment_id),

    strategy_name   VARCHAR NOT NULL,

    -- Condition (when does this rule apply?)
    regime_dimension VARCHAR NOT NULL,     -- 'ib_width', 'adx', 'gap_status', etc.
    regime_value    VARCHAR NOT NULL,      -- 'narrow', 'high', 'above_va', etc.

    -- Recommendation
    recommended_stop    VARCHAR,           -- stop model key or NULL
    recommended_target  VARCHAR,           -- target model key or NULL
    recommended_entry   VARCHAR,           -- entry model key or NULL
    size_modifier       DOUBLE DEFAULT 1.0, -- 0.5 = half size, 0 = skip

    -- Evidence
    sample_size     INTEGER,
    win_rate        DOUBLE,
    profit_factor   DOUBLE,
    net_pnl         DOUBLE,
    confidence      VARCHAR DEFAULT 'tested',

    notes           TEXT
);
```

**Example regime rules** (what autonomous research should discover):

```sql
INSERT INTO regime_rules (strategy_name, regime_dimension, regime_value,
                         recommended_stop, size_modifier, sample_size, win_rate, profit_factor, notes)
VALUES
    -- OR Rev: skip on wide overnight range (premarket levels too far)
    ('Opening Range Rev', 'overnight_range', 'wide', NULL, 0.0, 15, 0.33, 0.6,
     'ON range > 200pts → premarket levels too distant for reliable sweep'),

    -- B-Day: use ATR stop on normal IB, IB edge stop on narrow IB
    ('B-Day', 'ib_width', 'normal', '2_atr', 1.0, 45, 0.52, 1.83,
     'ATR stop gives enough room on normal IB days'),
    ('B-Day', 'ib_width', 'narrow', 'ib_edge_10pct', 0.5, 12, 0.42, 1.1,
     'Narrow IB B-Day is low conviction — half size, tight stop'),

    -- 80P: only worth trading when ADX < 20 (balance regime)
    ('80P Rule', 'adx', 'strong', NULL, 0.0, 20, 0.30, 0.7,
     'ADX > 25 kills 80P — trending market, no mean reversion'),

    -- Mean Reversion: DISABLED unless strict balance regime
    ('Mean Reversion VWAP', 'adx', 'moderate', NULL, 0.0, 30, 0.38, 0.8,
     'MR only viable on ADX < 20 + B-Day. Even then, smallest size.');
```

### Regime Drift Detection

Over time, Claude should compare recent results to historical baseline:

```sql
-- Has OR Rev's performance degraded in the last 30 sessions vs all-time?
SELECT
    'all_time' as period,
    COUNT(*) as trades,
    ROUND(AVG(CASE WHEN net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as wr,
    ROUND(SUM(net_pnl), 2) as net_pnl
FROM trades WHERE strategy_name = 'Opening Range Rev'
UNION ALL
SELECT
    'last_30_sessions',
    COUNT(*),
    ROUND(AVG(CASE WHEN net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1),
    ROUND(SUM(net_pnl), 2)
FROM trades
WHERE strategy_name = 'Opening Range Rev'
    AND session_date >= (SELECT DISTINCT session_date FROM trades ORDER BY session_date DESC LIMIT 1 OFFSET 29);
```

If WR drops more than 10% or PF drops below 1.0 in recent window → flag as potential regime shift.

---

## 10. The Publish Workflow: Research → Production

### When to Publish

A strategy/execution model combination gets published to production when:

1. **Sample size**: 30+ trades minimum
2. **Statistical significance**: PF > 1.2, WR > 40% (for high-R strategies) or WR > 55% (for low-R)
3. **Regime-tested**: Performance checked across at least 3 regime dimensions
4. **Stable**: No significant degradation in last 30 sessions vs all-time
5. **Human review**: Trader confirms the logic makes market sense (no curve-fitting)

### What Gets Published

Research DB has everything — every failed experiment, every intermediate result. Production DB only gets the distilled output:

```sql
-- PRODUCTION DB: Compact strategy configs
CREATE TABLE strategy_configs (
    strategy_name   VARCHAR NOT NULL,
    regime          VARCHAR NOT NULL,      -- 'default', 'narrow_ib', 'high_vol', etc.

    -- Execution models
    entry_model     VARCHAR,
    stop_model      VARCHAR NOT NULL,
    target_model    VARCHAR NOT NULL,

    -- Risk
    size_modifier   DOUBLE DEFAULT 1.0,    -- 1.0 = full, 0.5 = half, 0 = disabled
    max_trades_day  INTEGER DEFAULT 2,

    -- Evidence (summary only)
    sample_size     INTEGER,
    win_rate        DOUBLE,
    profit_factor   DOUBLE,

    -- Provenance
    published_from  VARCHAR,               -- research experiment_id
    published_at    TIMESTAMP,

    PRIMARY KEY (strategy_name, regime)
);

-- PRODUCTION DB: Pattern statistics for Pattern Miner agent
CREATE TABLE pattern_statistics (
    setup_type      VARCHAR NOT NULL,
    regime          VARCHAR NOT NULL,
    deterministic_feature VARCHAR NOT NULL, -- 'dpoc_regime', 'tpo_shape', etc.
    feature_value   VARCHAR NOT NULL,

    sample_size     INTEGER,
    win_rate        DOUBLE,
    avg_pnl         DOUBLE,
    effect_size     DOUBLE,                -- How much this feature changes the outcome

    published_at    TIMESTAMP,

    PRIMARY KEY (setup_type, regime, deterministic_feature, feature_value)
);
```

### Publish Script

```bash
# Review what's ready to publish
uv run python scripts/publish_to_production.py --review

# Output:
# Ready to publish:
#   OR Reversal / narrow_ib → stop: ib_edge_10pct, target: 2r
#     Evidence: 45 trades, 68.9% WR, 3.2 PF (experiment: exp_20260305_001)
#
#   B-Day / default → stop: 2_atr, target: level_ib_mid
#     Evidence: 84 trades, 52.4% WR, 1.83 PF (experiment: exp_20260305_003)
#
# NOT ready (needs more data):
#   MACD Crossover / default → only 12 trades, need 30+

# Publish approved configs
uv run python scripts/publish_to_production.py --publish exp_20260305_001 exp_20260305_003
```

---

## 11. Agent Annotation Loop: Production Feeds Back to Research

### Agents Annotate Live Trades

When agents execute trades in production, they write back:

```sql
-- PRODUCTION DB: Agent annotations on live trades
CREATE TABLE agent_annotations (
    annotation_id   INTEGER PRIMARY KEY,
    trade_id        INTEGER REFERENCES trade_history(trade_id),
    annotated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    agent_name      VARCHAR NOT NULL,      -- 'advocate', 'skeptic', 'orchestrator', 'pattern_miner'
    annotation_type VARCHAR NOT NULL,      -- 'pre_trade', 'post_trade', 'regime_note', 'correlation'

    content         TEXT NOT NULL,          -- The annotation

    -- Pre-trade context
    confidence_at_entry DOUBLE,
    debate_outcome  VARCHAR,               -- 'TAKE', 'PASS', 'REDUCE'
    advocate_summary TEXT,
    skeptic_summary TEXT,

    -- Post-trade analysis
    what_worked     TEXT,                   -- "VWAP confirmation was strong signal"
    what_failed     TEXT,                   -- "Stop too tight for the volatility"
    missed_signal   TEXT,                   -- "Should have seen the FVG rejection"
    regime_at_trade VARCHAR,               -- Agent's regime classification

    -- Flags for research
    needs_research  BOOLEAN DEFAULT FALSE, -- "This pattern needs deeper study"
    research_topic  TEXT                    -- "FVG at sweep point → conviction booster?"
);
```

### Feedback Cycle

```
PRODUCTION                              RESEARCH
─────────                              ────────
Agent takes trade ──────────────────→  (no action yet)
Agent annotates: "stop too tight,
  stopped out then price hit target" ─→  Flag: needs_research = true
                                         topic: "stop_sensitivity_or_rev"

                                        Claude picks up research topic
                                        Claude runs combo study: wider stops
                                        Claude finds: 2.5x ATR beats 2x ATR
                                        Claude publishes new regime rule

Agent receives updated config ←──────  Published: or_rev / default → 2.5_atr
Agent uses wider stop next time
Agent annotates: "wider stop held,
  trade hit target" ─────────────────→  Observation confirmed
```

### Periodic Research Sync

```sql
-- What are agents flagging for research? (run weekly)
SELECT research_topic, COUNT(*) as flags,
       AVG(CASE WHEN what_failed IS NOT NULL THEN 1.0 ELSE 0.0 END) as failure_rate
FROM agent_annotations
WHERE needs_research = TRUE
    AND annotated_at > CURRENT_DATE - INTERVAL 7 DAY
GROUP BY research_topic
ORDER BY flags DESC;
```

Claude reads this and prioritizes its next autonomous research session accordingly.

---

## 12. Relationship to Existing DuckDB Schemas

### What Already Exists in Architecture

| Document | Schema Purpose | Tables | Status |
|----------|---------------|--------|--------|
| `architecture/08-agent-system.md` § 9 | **Live agent system**: signal lifecycle, debate history, scorecards | `deterministic_snapshots`, `enriched_outcomes`, `hidden_confluence`, `signal_outcomes`, `agent_scorecards`, `version_changes` | Design only |
| `brainstorm/07` Appendix D | **Live signal log**: signals → decisions → trades → sessions | `signals`, `decisions`, `trades`, `snapshots`, `sessions` | Design only |
| `rockit_core.metrics.collector` | **Metrics**: generic event store | `metrics` | Implemented |

### How the Three Systems Relate

```
┌─────────────────────────────────┐
│   RESEARCH DB (Claude's Lab)    │
│   data/research.duckdb          │
│                                 │  ← Claude writes: experiments, combos, correlations
│   experiments                   │  ← Claude reads: gaps, hypotheses, patterns
│   backtest_runs / trades        │
│   combo_runs / combo_trades     │
│   session_context               │
│   observations / tags           │
│   regime_rules                  │
│   correlations                  │
└──────────┬──────────────────────┘
           │ PUBLISH (validated knowledge)
           ▼
┌─────────────────────────────────┐
│   PRODUCTION DB (Agent Runtime) │
│   data/rockit.duckdb            │
│                                 │  ← Agents read: configs, patterns, history
│   strategy_configs              │  ← Agents write: trade_history, annotations
│   pattern_statistics            │
│   trade_history                 │
│   agent_annotations             │
│   signals / decisions           │  (from arch/08 + brainstorm/07)
│   enriched_outcomes             │
│   agent_scorecards              │
└──────────┬──────────────────────┘
           │ FEEDBACK (agent learnings, flags)
           ▼
     Back to RESEARCH DB
     (Claude picks up flagged topics, validates agent observations)
```

`session_context` is shared schema — same structure in both DBs. Research populates it from backtests; production populates it from live sessions.

---

## 13. Data Quality Audit: Don't Build on Bad Data

> **CRITICAL GATE**: Before generating the deterministic tape for 259+ sessions, we must validate that each module produces accurate, useful data — not noise. The warehouse is only as good as what goes in. This section audits every module and flags what needs fixing before Phase 1.

### 13.1 Module-by-Module Confidence Assessment

| Module | File | LOC | Confidence | Status | Notes |
|--------|------|-----|------------|--------|-------|
| **IB Location** | `ib_location.py` | 260 | 95% | SOLID | ADX(14), BB(20,2), IB high/low/range correct |
| **Volume Profile** | `volume_profile.py` | 148 | 95% | SOLID | True volume-at-price with tick distribution, POC, 70% VA, HVN/LVN across 5 horizons |
| **TPO Profile** | `tpo_profile.py` | 166 | 70% | GAPS | 30-min letters work, BUT missing 5-min TPO and letter-level granularity (see below) |
| **DPOC Migration** | `dpoc_migration.py` | 167 | 90% | SOLID | 30-min POC tracking, trending/stabilizing/reversal classification |
| **FVG Detection** | `fvg_detection.py` | 137 | 60% | NEEDS FIX | Multi-TF detection works, BUT filled FVG tracking is fragile (see below) |
| **Premarket** | `premarket.py` | 105 | 90% | SOLID | Asia/London/Overnight levels, compression ratio |
| **Globex VA** | `globex_va_analysis.py` | 527 | 90% | SOLID | Prior session VA, gap classification, 80% Rule models |
| **SMT Detection** | `smt_detection.py` | 299 | 80% | GOOD | Cross-market divergence at key levels |
| **20% Rule** | `twenty_percent_rule.py` | 282 | 85% | GOOD | IB extension detection + 50% retest models |
| **Balance Class** | `balance_classification.py` | 747 | 85% | GOOD | Skew/seam/morph, BUT no confidence score |
| **Mean Reversion** | `mean_reversion_engine.py` | 409 | 80% | GOOD | IB range classification, rejection tests |
| **OR Reversal** | `or_reversal.py` | 217 | 85% | GOOD | OR levels, sweep, drive classification |
| **Inference Engine** | `inference_engine.py` | 823 | 85% | SOLID | 8 deterministic rules |
| **CRI** | `cri.py` | 542 | 80% | GOOD | Terrain/identity/permission scoring |
| **Tape Context** | `tape_context.py` | 457 | 85% | GOOD | V1 tape metrics (IB touch, C-period, session open, VA depth, DPOC retention) |
| **Playbook** | `playbook_engine.py` | 480 | 85% | SOLID | Playbook recommendations |
| **Core Confluences** | `core_confluences.py` | 186 | 80% | GOOD | Confluence signals |
| **Wick Parade** | `wick_parade.py` | 42 | 50% | BASIC | Only 42 lines, minimal implementation |
| **Edge Fade** | `edge_fade.py` | 193 | 70% | BASIC | Needs validation |
| **VA Edge Fade** | `va_edge_fade.py` | 257 | 80% | GOOD | VA edge poke, rejection patterns |
| **Market Structure** | `market_structure_events.py` | 372 | 65% | NEEDS AUDIT | Complex, unvalidated |
| **Decision Engine** | `decision_engine.py` | 519 | 65% | NEEDS AUDIT | Complex post-inference |
| **Enhanced Reasoning** | `enhanced_reasoning.py` | 492 | 65% | NEEDS AUDIT | Complex reasoning layer |
| **Setup Annotator** | `setup_annotator.py` | 324 | 70% | NEEDS VALIDATION | |
| **Trader Voice** | `trader_voice.py` | 211 | 50% | PLACEHOLDER | Not useful for warehouse |
| **Cross Market** | `cross_market.py` | 0 | 0% | EMPTY STUB | Not implemented |
| **Intraday Sampling** | `intraday_sampling.py` | 0 | 0% | EMPTY STUB | Not implemented |
| **VIX Regime** | `vix_regime.py` | 0 | 0% | EMPTY STUB | Not implemented |

### 13.2 Volume Profile & HVN/LVN — SOLID

**Current implementation** (`volume_profile.py`):
- Distributes each OHLC bar's volume across tick-level price bins (0.25 tick for NQ/ES)
- Calculates POC = price level with highest volume
- Builds 70% Value Area using CBOT standard (expand outward from POC)
- Identifies HVN (top 3 price levels by volume) and LVN (3 lowest within VA)
- Computes across 5 horizons: current session, prior day, prior 3/5/10 days

**Verdict**: This is **textbook correct** volume-at-price distribution. Not just levels — actual volume allocated proportionally across each bar's range. Safe for warehouse.

**Validation query** (add to warehouse pipeline):
```sql
-- Sanity check: POC should always be within VAH/VAL
SELECT session_date, snapshot_time
FROM deterministic_tape
WHERE dpoc_price > va_high OR dpoc_price < va_low;
-- Should return 0 rows
```

### 13.3 TPO Profile — GAPS THAT MATTER

**Current implementation** (`tpo_profile.py`):
- Builds 30-min TPO letters (A, B, C...) — **correct**
- Computes TPO count per price level at tick resolution — **correct**
- Identifies single prints above/below VA — **correct**
- Calculates poor high/low (≥2 TPO at extremes) — **correct**
- Detects rejection strength at highs/lows — **correct**

**What's MISSING:**

1. **No 5-min TPO**: Only 30-min periods. Some analysis needs finer resolution (especially for first-hour precision). For OR analysis, 5-min TPO within the opening range period shows micro-structure that 30-min misses entirely.

2. **No letter-level granularity**: We store `single_prints_above_vah = 7` but NOT which letters created them. For tape reading:
   - "Periods B and C both rejected at highs" = strong exhaustion signal
   - "Only period A touched the high" = initial exploration, not exhaustion
   - This distinction matters for LLM training and correlation studies

3. **No TPO letter matrix output**: Can't answer "which price levels did period D touch that period C didn't?" — this is how experienced Market Profile traders read developing structure.

4. **No proper TPO chart rendering**: We have counts and single prints, but can't reconstruct a visual TPO chart from the data. For the LLM to truly "read the tape," it needs sequential TPO data, not just aggregates.

**What we need — a proper TPO engine**:
```python
# Current: just counts
{"single_prints_above_vah": 7, "poor_high": true, "tpo_shape": "p_shape"}

# Needed: full letter matrix
{
    "tpo_matrix": {
        "4570.50": {"letters": ["A", "B"], "count": 2, "single_print": false},
        "4571.00": {"letters": ["A"], "count": 1, "single_print": true},
        "4571.50": {"letters": ["A"], "count": 1, "single_print": true},
        ...
    },
    "period_ranges": {
        "A": {"high": 4572.00, "low": 4565.50, "open": 4567.00, "close": 4571.50},
        "B": {"high": 4570.50, "low": 4563.00, "open": 4570.00, "close": 4564.00},
        ...
    },
    "single_print_stacks": [
        {"direction": "above", "start": 4571.00, "end": 4572.00, "letters": ["A"], "count": 4}
    ]
}
```

**Decision required**: Do we build the full TPO engine before generating the deterministic tape, or generate with current (basic) TPO and enrich later?

**Recommendation**: Generate Phase 1 tape with current TPO data (it's directionally correct). Add the full letter matrix as a separate enrichment pass. The `snapshot_json` column stores the full output, so we can re-extract when the TPO engine improves.

### 13.4 FVG Detection — NEEDS ATTENTION

**Current implementation** (`fvg_detection.py`):
- Detects multi-timeframe FVGs using ICT 3-candle rule — **correct**
- Checks 6 timeframes: daily, 4h, 1h, 90min, 15min, 5min — **good**
- Filters to unfilled FVGs only — **fragile**
- Detects BPR (opposing engulfing) — **good**

**The problem: FVG lifecycle tracking**

When an FVG is filled (price retraces through it), the current code simply removes it from the output. This means:

1. **Lost history**: A snapshot at 10:30 might show 3 unfilled FVGs. At 10:35, one fills. The 10:35 snapshot shows 2 FVGs. But we **never recorded** that an FVG existed and was filled — we only know it's gone. For correlation studies ("do filled FVGs at entry time predict wins?"), this is a critical gap.

2. **No mitigation timestamp**: We can't answer "when was this FVG created, and when was it filled?" which is essential for understanding FVG relevance (fresh FVG vs stale FVG).

3. **Cross-snapshot inconsistency**: The same FVG might appear in snapshot 10:30 but not 10:35 (because it got filled), then reappear at 10:40 if a new FVG forms at a similar price level. Without FVG IDs, we can't distinguish "same FVG returned" from "new FVG at similar price."

**What we need**:
```python
# Current output (per snapshot):
{"unfilled_fvgs": [{"type": "bullish", "top": 4570.50, "bottom": 4569.00, "timeframe": "5min"}]}

# Needed: lifecycle tracking
{
    "fvg_registry": [
        {
            "fvg_id": "fvg_5min_bull_20250115_1015",
            "type": "bullish",
            "timeframe": "5min",
            "top": 4570.50,
            "bottom": 4569.00,
            "created_time": "10:15",
            "created_bar_idx": 45,
            "status": "unfilled",          # or "filled" or "partially_filled"
            "filled_time": null,            # when fully mitigated
            "filled_bar_idx": null,
            "fill_pct": 0.0,               # how much of the gap has been retraced
            "age_bars": 12,                 # how many bars since created
        },
        {
            "fvg_id": "fvg_15min_bear_20250115_0945",
            "type": "bearish",
            "timeframe": "15min",
            "top": 4575.00,
            "bottom": 4573.50,
            "created_time": "09:45",
            "status": "filled",
            "filled_time": "10:20",
            "fill_pct": 1.0,
            "age_bars": 7,
        }
    ],
    "active_fvg_count": {"5min": 2, "15min": 1, "1h": 0, ...},
    "recently_filled": [...]  # FVGs filled in last 5 bars (still relevant context)
}
```

**Decision required**: Fix FVG tracking before Phase 1, or generate tape with current (unfilled-only) output and fix later?

**Recommendation**: Fix this before Phase 1. The FVG lifecycle data is critical for correlation studies ("was there an unfilled bullish FVG at entry time?" is a common tape reading question). Without mitigation timestamps, we lose half the FVG signal.

### 13.5 Modules NOT Worth Storing in Warehouse

Some module outputs are either noise or too unstable for structured queries:

| Module | Why Skip for Warehouse |
|--------|----------------------|
| `trader_voice.py` | Prose generation, not data. LLM annotation layer, not deterministic. |
| `cri_psychology_voice.py` | Same — narrative text, not queryable metrics |
| `enhanced_reasoning.py` | Complex reasoning text, better as `snapshot_json` not indexed columns |
| `cross_market.py` | Empty stub |
| `intraday_sampling.py` | Empty stub |
| `vix_regime.py` | Empty stub |

**Store in `snapshot_json`** (full blob), but don't extract to indexed columns. These are useful for LLM training context but not for SQL correlation queries.

### 13.6 Data Quality Checks to Run on Every Snapshot

Before persisting to `deterministic_tape`, validate:

```python
def validate_snapshot(snapshot: dict, session_date: str, time: str) -> list[str]:
    """Return list of warnings. Empty = clean."""
    warnings = []

    # 1. POC must be within VAH/VAL
    if snapshot.get('poc') and snapshot.get('vah') and snapshot.get('val'):
        if snapshot['poc'] > snapshot['vah'] or snapshot['poc'] < snapshot['val']:
            warnings.append(f"POC {snapshot['poc']} outside VA [{snapshot['val']}, {snapshot['vah']}]")

    # 2. VAH must be > VAL
    if snapshot.get('vah') and snapshot.get('val'):
        if snapshot['vah'] <= snapshot['val']:
            warnings.append(f"VAH {snapshot['vah']} <= VAL {snapshot['val']}")

    # 3. IB high must be >= IB low
    if snapshot.get('ib_high') and snapshot.get('ib_low'):
        if snapshot['ib_high'] < snapshot['ib_low']:
            warnings.append(f"IB high {snapshot['ib_high']} < IB low {snapshot['ib_low']}")

    # 4. ATR must be positive
    if snapshot.get('atr14') and snapshot['atr14'] <= 0:
        warnings.append(f"ATR14 {snapshot['atr14']} <= 0")

    # 5. Day type must be valid
    valid_day_types = {'trend_bull', 'trend_bear', 'p_day', 'b_day', 'neutral', 'rotational'}
    if snapshot.get('day_type') and snapshot['day_type'] not in valid_day_types:
        warnings.append(f"Unknown day_type: {snapshot['day_type']}")

    # 6. No NaN/Infinity in numeric fields
    for key in ['poc', 'vah', 'val', 'ib_high', 'ib_low', 'atr14', 'vwap', 'adx14']:
        val = snapshot.get(key)
        if val is not None and (math.isnan(val) or math.isinf(val)):
            warnings.append(f"{key} is NaN/Inf: {val}")

    # 7. DPOC should not jump more than 2x ATR between consecutive snapshots
    # (requires previous snapshot — check in batch pipeline)

    return warnings
```

### 13.7 Priority Fixes Before Phase 1

| Priority | Fix | Impact | Effort |
|----------|-----|--------|--------|
| **P0** | FVG lifecycle tracking (filled_time, fvg_id) | Without this, FVG correlation studies are impossible | Medium (modify fvg_detection.py) |
| **P0** | Data validation pipeline (NaN/Inf/impossible values) | Prevents bad data from entering warehouse | Small (add validate_snapshot) |
| **P1** | TPO letter matrix output (which letters at which prices) | Enables "which periods rejected at highs?" queries | Medium (extend tpo_profile.py) |
| **P1** | TPO 5-min option (for OR/first-hour precision analysis) | 30-min is too coarse for first-hour tape reading | Medium (add 5-min period mode) |
| **P2** | Balance classification confidence score | Enables filtering "high confidence B-Day" from ambiguous | Small (add score to output) |
| **P2** | Wick parade expansion (currently 42 LOC) | Minimal impact — only useful for specific order flow patterns | Small |
| **P3** | Market structure events audit | Complex module, unclear accuracy | Large |
| **P3** | VIX regime stub implementation | Useful but not blocking — can add VIX data later | Medium |

**Recommendation**: Fix P0 items before generating the deterministic tape. P1 items can be added as enrichment passes after initial tape generation (re-run and update rows). P2/P3 are future improvements.

---

## 14. Implementation Phases

> **Key insight**: Generate the deterministic dataset FIRST — even without LLM output. This is the foundational layer. Everything else layers on top: backtests record trades against it, post-trade workflows correlate outcomes with it, and LLM annotations augment it later.
>
> **PREREQUISITE**: Complete P0 data quality fixes (Section 13.7) before generating the tape. Don't build on bad data.

### Phase 0: Data Quality Fixes (PREREQUISITE)

Fix P0 issues from Section 13 before generating any tape data. Don't build the warehouse on bad data.

- [ ] **FVG lifecycle tracking**: Modify `fvg_detection.py` to track `fvg_id`, `created_time`, `filled_time`, `status`, `fill_pct`. Filled FVGs stay in output with status="filled" instead of disappearing.
- [ ] **Data validation pipeline**: Add `validate_snapshot()` function — catches NaN/Inf, impossible values (VAH < VAL, POC outside VA, ATR ≤ 0), unknown day types. Run on every snapshot before persisting.
- [ ] **TPO letter matrix** (P1, can do in parallel): Extend `tpo_profile.py` to output which letters touched each price level, not just counts. Enables "which periods rejected at highs?" queries.
- [ ] **Audit tests**: Add deterministic correctness tests — known input bars → known POC, known VA, known single prints. Currently tests check for key presence but not computational accuracy.

### Phase 1: Deterministic Foundation (DO THIS FIRST)

The deterministic tape is the bedrock. Run the 38-module orchestrator across all 259+ sessions, persist every 5-min snapshot to `deterministic_tape`. This dataset grows forever and never depends on LLM output.

- [ ] Create `data/research.duckdb` with schema (all tables at once for clean DDL)
- [ ] `scripts/init_research_db.py` — DDL script to create/migrate schema
- [ ] `rockit_core.research.db` — Python module: `connect()`, `persist_deterministic()`, `query()`
- [ ] `scripts/generate_deterministic_tape.py` — batch runner:
  - Loads each session CSV from `data/sessions/`
  - Runs deterministic orchestrator (38 modules)
  - Runs `validate_snapshot()` on every output — log warnings, reject corrupt snapshots
  - Extracts 5-min snapshots (price state, market structure, profile, order flow, CRI)
  - Persists each snapshot to `deterministic_tape` table
  - Also persists session-level summary to `session_context` table
- [ ] Run for all 259+ sessions → ~20,000 deterministic rows (Day 1 seed)
- [ ] Verify: `SELECT COUNT(*), COUNT(DISTINCT session_date) FROM deterministic_tape`
- [ ] Spot-check 5 random sessions manually: does the data match what a human would see on a chart?

**Why first**: Without this table, there's nothing to correlate trades against. This is pure market structure data — no opinions, no LLM, no strategy logic. It just records what the tape looked like at every 5-min interval.

### Phase 2: Backtest Recording

Every backtest run auto-records into research DB. Every trade gets a row. This creates the second foundational table: what did the strategy DO on each session.

- [ ] `persist_backtest_run()` — writes run metadata + all trades to DuckDB
- [ ] `persist_combo_run()` — writes combo results + per-combo trades
- [ ] Hook into `run_backtest.py` — auto-persist after every run
- [ ] Hook into `run_combo_backtest.py` — auto-persist combo results
- [ ] Seed existing `data/results/*.json` into `backtest_runs` + `trades`
- [ ] Create `v_trade_context` view (trades joined with session context)
- [ ] Create `v_trade_tape` view (trades joined with deterministic_tape at entry time)

### Phase 3: Post-Trade Correlation Workflow

After each trade is recorded, run it through a correlation workflow that joins with the deterministic tape to find clues: what market conditions were present when this trade won/lost?

- [ ] `rockit_core.research.correlate` — post-trade correlation module
- [ ] For each trade, query deterministic_tape at:
  - Entry time: what was the market structure when the signal fired?
  - 30 min before entry: was there a setup developing?
  - Exit time: what changed between entry and exit?
  - Session-level: what kind of day was this overall?
- [ ] Auto-tag trades with deterministic features at entry time:
  - `cri_status` at entry, `dpoc_migration`, `delta_trend`, `tpo_shape`
  - `price_vs_ib`, `ib_extension_pct`, `vwap` position
- [ ] Generate correlation summary per strategy:
  ```sql
  -- Which deterministic features predict winning trades?
  SELECT dt.cri_status, dt.dpoc_migration, dt.delta_trend,
         COUNT(*) as n,
         ROUND(AVG(CASE WHEN t.net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as wr
  FROM trades t
  JOIN deterministic_tape dt
    ON t.session_date = dt.session_date
    AND dt.snapshot_time = STRFTIME(t.entry_time, '%H:%M')
  GROUP BY dt.cri_status, dt.dpoc_migration, dt.delta_trend
  HAVING COUNT(*) >= 5
  ORDER BY wr DESC;
  ```
- [ ] Persist correlation results as observations with tags + confidence levels

**The loop**: Backtest → record trade → correlate with deterministic tape → find clues → form hypothesis → test hypothesis → confirmed/disproven. This is how Claude builds intuition about what works.

### Phase 4: Autonomous Research Framework

- [ ] `experiments` table + experiment tracking
- [ ] Research session runner (Claude studies a topic, records findings)
- [ ] Regime analysis queries and `regime_rules` table
- [ ] Observation tagging with confidence lifecycle
- [ ] Seed from brainstorm/08 accuracy-check tables + MEMORY.md

### Phase 5: Combo Studies at Scale

- [ ] Run combo backtest for all 5 active strategies × all stop/target combos
- [ ] Run combo backtest for all entry model variants
- [ ] Persist results, build `v_combo_comparison` view
- [ ] Each combo trade → post-trade correlation with deterministic tape
- [ ] Identify which combos beat "original" for each strategy
- [ ] Regime-conditional analysis for each winning combo

### Phase 6: Production DB + Publish Workflow

- [ ] Production DB schema (`strategy_configs`, `pattern_statistics`, `trade_history`, `agent_annotations`)
- [ ] `scripts/publish_to_production.py` — review + publish workflow
- [ ] Publish readiness criteria (sample size, PF threshold, regime-tested)
- [ ] Strategy runner reads configs from production DB instead of hardcoded

### Phase 7: Agent Annotation + Feedback Loop

- [ ] Agent annotation schema in production DB
- [ ] Post-trade analysis annotations (what worked, what failed, missed signals)
- [ ] `needs_research` flag → research topic queue
- [ ] Periodic sync: Claude reads agent flags, prioritizes research
- [ ] Regime drift detection queries

---

## 15. Post-Trade Correlation Workflow: The Intelligence Engine

This is the core loop that turns raw data into actionable knowledge. Every trade — whether from backtest or live — gets processed through the same workflow.

### The Flow

```
Trade completes (backtest or live)
        │
        ▼
┌─────────────────────────────────────────────────┐
│  Step 1: RECORD the trade                        │
│  INSERT INTO trades (strategy, entry, stop, ...)│
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  Step 2: SNAPSHOT deterministic context           │
│  Query deterministic_tape at entry_time          │
│  Query deterministic_tape at exit_time           │
│  Query deterministic_tape 30 min before entry    │
│  Query session_context for full-day summary      │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  Step 3: TAG the trade                           │
│  cri_status, dpoc_migration, delta_trend,        │
│  tpo_shape, price_vs_ib, vwap_position,          │
│  ib_extension_pct at entry time                  │
│  → stored as trade metadata or indexed columns   │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  Step 4: COMPARE with similar trades             │
│  "Other trades with same strategy + same tags"   │
│  "What was different about wins vs losses?"       │
│  → e.g., winners had CRI=GO, losers had CAUTION │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  Step 5: GENERATE clues (observations)           │
│  "OR Rev wins 78% when CRI=GO at entry,         │
│   but only 41% when CRI=CAUTION"                │
│  → INSERT INTO observations (confidence='tested')│
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  Step 6: UPDATE regime rules (if sample > 30)    │
│  "OR Rev + CRI=CAUTION → size_modifier=0.5"     │
│  → INSERT INTO regime_rules                      │
└─────────────────────────────────────────────────┘
```

### The Correlation Query Templates

```python
def correlate_trade(db, trade):
    """Run post-trade correlation workflow for a single trade."""

    # 1. What did the tape look like at entry?
    entry_tape = db.sql("""
        SELECT * FROM deterministic_tape
        WHERE session_date = ? AND snapshot_time = ?
          AND instrument = ?
    """, [trade.session_date, entry_time_5min, trade.instrument]).fetchone()

    # 2. What was developing 30 min before?
    pre_tape = db.sql("""
        SELECT * FROM deterministic_tape
        WHERE session_date = ? AND snapshot_time = ?
          AND instrument = ?
    """, [trade.session_date, pre_entry_time, trade.instrument]).fetchone()

    # 3. What changed at exit?
    exit_tape = db.sql("""
        SELECT * FROM deterministic_tape
        WHERE session_date = ? AND snapshot_time = ?
          AND instrument = ?
    """, [trade.session_date, exit_time_5min, trade.instrument]).fetchone()

    # 4. Compare with historical trades (same strategy, similar context)
    similar = db.sql("""
        SELECT
            dt.cri_status,
            dt.dpoc_migration,
            dt.delta_trend,
            t.outcome,
            COUNT(*) as n,
            ROUND(AVG(t.net_pnl), 2) as avg_pnl
        FROM trades t
        JOIN deterministic_tape dt
          ON t.session_date = dt.session_date
          AND dt.snapshot_time = STRFTIME(t.entry_time, '%H:%M')
        WHERE t.strategy_name = ?
          AND dt.cri_status = ?
          AND dt.delta_trend = ?
        GROUP BY dt.cri_status, dt.dpoc_migration, dt.delta_trend, t.outcome
    """, [trade.strategy_name, entry_tape.cri_status, entry_tape.delta_trend])

    # 5. Generate clue
    return {
        'entry_context': entry_tape,
        'pre_context': pre_tape,
        'exit_context': exit_tape,
        'similar_trades': similar.df(),
        'clue': generate_clue(trade, entry_tape, similar),
    }
```

### What Clues Look Like

```
Trade: OR Rev LONG on 2025-01-15, entry 10:32, +$425 WIN
Context at entry:
  CRI: GO (confluence count: 4)
  DPOC migration: rising
  Delta trend: positive
  TPO shape: p_shape (bullish)
  Price vs IB: above_ibh (extension)

Similar trades with CRI=GO + delta=positive (n=23):
  Win rate: 74%    Avg PnL: +$380

Similar trades with CRI=CAUTION + delta=negative (n=15):
  Win rate: 33%    Avg PnL: -$210

→ OBSERVATION: "OR Rev has 74% WR when CRI=GO + delta=positive at entry,
   vs 33% when CRI=CAUTION + delta=negative. CRI status is a strong
   trade filter." (confidence: tested, sample: 38 trades)
```

### Batch Correlation After Backtest

When a full backtest runs (e.g., 266 sessions, 548 trades), run correlation for ALL trades at once:

```python
def batch_correlate(db, run_id):
    """Run correlation for all trades in a backtest run."""

    # One big join: every trade × its deterministic context at entry time
    correlations = db.sql("""
        SELECT
            t.strategy_name,
            t.outcome,
            dt.cri_status,
            dt.dpoc_migration,
            dt.delta_trend,
            dt.tpo_shape,
            dt.price_vs_ib,
            dt.ib_extension_pct,
            COUNT(*) as n,
            ROUND(AVG(CASE WHEN t.net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as wr,
            ROUND(AVG(t.net_pnl), 2) as avg_pnl
        FROM trades t
        JOIN deterministic_tape dt
          ON t.session_date = dt.session_date
          AND dt.snapshot_time = STRFTIME(t.entry_time, '%H:%M')
          AND dt.instrument = t.instrument
        WHERE t.run_id = ?
        GROUP BY t.strategy_name, t.outcome,
                 dt.cri_status, dt.dpoc_migration, dt.delta_trend,
                 dt.tpo_shape, dt.price_vs_ib, dt.ib_extension_pct
        HAVING COUNT(*) >= 3
        ORDER BY t.strategy_name, wr DESC
    """, [run_id]).df()

    # Auto-generate observations for strong correlations
    for _, row in correlations.iterrows():
        if row['n'] >= 10 and (row['wr'] > 65 or row['wr'] < 35):
            persist_observation(db,
                strategy=row['strategy_name'],
                observation=f"{row['strategy_name']}: {row['wr']}% WR when "
                           f"CRI={row['cri_status']}, delta={row['delta_trend']}, "
                           f"DPOC={row['dpoc_migration']} (n={row['n']})",
                confidence='tested',
                tags=['correlation', 'deterministic', row['cri_status'].lower()],
            )
```

---

## 16. File Layout

```
packages/rockit-core/src/rockit_core/
  research/
    __init__.py
    db.py                    # connect(), persist_backtest(), persist_combo(), query()
    schema.py                # DDL definitions, migration logic
    deterministic.py         # persist_deterministic_tape(), batch generate for all sessions
    correlate.py             # Post-trade correlation workflow, batch_correlate()
    seed.py                  # Seed from existing results/studies
    experiment.py            # Experiment tracking, autonomous research helpers
    publish.py               # Research → production publish logic
    regime.py                # Regime analysis helpers

scripts/
    init_research_db.py      # Create/migrate research DB schema
    init_production_db.py    # Create/migrate production DB schema
    generate_deterministic_tape.py  # Batch: run orchestrator for 259+ sessions → DuckDB
    add_observation.py       # CLI for tagged observations
    seed_research_db.py      # Backfill from existing data
    query_research.py        # Interactive SQL against research DB
    publish_to_production.py # Review + publish workflow
    research_session.py      # Run autonomous research session

data/
    research.duckdb          # Research warehouse (gitignored)
    rockit.duckdb            # Production agent DB (gitignored)
```

---

## 17. The Data Layering Model

The key architectural insight: **deterministic data is the foundation, everything else layers on top.**

```
Layer 4: Agent annotations (live trade learnings, debate reasoning)
         ↑ written by production agents during live trading
Layer 3: LLM tape annotations (trained model tape readings)
         ↑ written by Qwen3.5/Opus after training, or Claude reviewing
Layer 2: Backtest trades + correlation tags
         ↑ written by backtest engine + post-trade correlation workflow
Layer 1: DETERMINISTIC TAPE (pure market structure, 38 modules)
         ↑ generated FIRST, independent of everything else
         ↑ ~20,000 rows from 259 sessions, grows daily with new sessions
─────────────────────────────────────────────────────
         Session CSVs (1-min OHLCV + delta + volume)
```

**Phase 1 generates Layer 1.** No LLM needed. No strategies needed. Just the orchestrator reading raw market data and recording what the tape looked like every 5 minutes. This is the ground truth.

**Phase 2 generates Layer 2.** Run backtests, record every trade. Then correlate each trade with Layer 1 to tag it with deterministic context at entry time. This is where clues emerge.

**Phase 3+ generates Layers 3-4.** Once the LLM is trained, its tape readings augment Layer 1. Agents annotate Layer 2 trades as they learn. Claude reviews and benchmarks annotations against Layer 1 ground truth.

The database grows forever. More sessions = more deterministic rows. More backtests = more trade correlation data. More LLM runs = more annotations. More live trading = more agent feedback. Every layer makes the other layers more valuable.

---

## 18. Key Design Decisions

1. **Deterministic data first**: Generate the tape before anything else. It's the foundation every other layer references.

2. **Two separate DuckDB files**: Research (`research.duckdb`) and production (`rockit.duckdb`). Different lifecycles, different consumers, different sizes.

3. **Session context is the universal join key**: Every trade, combo trade, and observation links through `session_date`. This enables cross-cutting correlation queries.

4. **JSON columns for flexibility**: `snapshot_json`, `config`, `variables` columns store full context. DuckDB's `json_extract()` enables ad-hoc deep queries without schema changes.

5. **Confidence lifecycle**: `hypothesis` → `tested` → `confirmed` → `disproven`. No untested claims in production. Research observations must be tested before publishing.

6. **Experiments chain**: `parent_id` links experiments into research threads. Claude can follow a line of inquiry across sessions.

7. **Git-aware**: Every run records `git_branch` and `git_commit`. Trace which code version produced which results.

8. **Auto-persist, not manual**: Backtest and combo runner automatically write to research DB. Knowledge accumulates without human intervention.

9. **Post-trade correlation is automatic**: Every trade gets correlated with the deterministic tape immediately. Clues surface without human prompting.

10. **Publish gate, not auto-deploy**: Research findings require explicit publish step with human review. No untested changes reach production agents.

11. **Agent feedback drives research priority**: Agents flag what they struggle with. Claude researches those topics first. Closes the loop.

12. **Regime-first thinking**: Every finding is qualified by regime. "B-Day works" is incomplete. "B-Day works on normal IB, ADX < 20, gap inside VA" is knowledge.

---

## 19. What This Unlocks

| Before | After |
|--------|-------|
| "I think OR Rev works better on narrow IB days" | Query research DB → confirmed or disproven with data |
| Re-run backtest to remember results | `SELECT * FROM backtest_runs ORDER BY run_timestamp DESC` |
| "Which stop model is best for B-Day?" | Run combo study once → query `v_combo_comparison` forever |
| Strategy study results in .md files | Structured observations with tags, confidence, and evidence |
| "Does gap status affect 80P?" | `SELECT gap_status, wr FROM v_trade_context WHERE strategy = '80P Rule' GROUP BY gap_status` |
| Human memory as knowledge store | SQL as knowledge store. Claude queries it. Agents query it. Both learn. |
| Regime change breaks strategies silently | Regime drift detection queries flag degradation early |
| Claude only runs what you ask | Claude autonomously discovers, tests, and builds knowledge |
| Agent makes same mistake twice | Agent annotates failure → Claude researches → publishes fix |
| Knowledge scattered across conversations | Experiments chain with `parent_id`, observations tagged, everything queryable |
