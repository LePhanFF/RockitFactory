# Training Data Pipeline for Specialist Agents

**Status**: Brainstorm / Exploration
**Date**: 2026-03-03
**Companion to**: `04-agent-specialization-and-consensus.md`

---

## The Core Idea

Generate deterministic data in bulk → extract at backtest time → tag by strategy → build supporting evidence per domain. This creates the data foundation for every specialist approach in `04-agent-specialization-and-consensus.md`.

The key insight: **we already have the machines to produce this data**. The 38 deterministic modules generate rich snapshots. The backtest engine knows which trades won and lost. We just need to connect them and structure the output for specialist training.

---

## Three-Stage Pipeline

```
STAGE 1: BULK SNAPSHOT GENERATION (one-time + incremental)
   259+ sessions × ~30 time slices = ~7,500 snapshots
   Each snapshot = full output of all 38 deterministic modules
   Store in DuckDB: one row per snapshot

STAGE 2: BACKTEST ENRICHMENT (per strategy)
   Run backtest engine through same sessions
   At each signal point: capture snapshot + trade outcome
   Tag: which strategy fired, direction, entry/stop/target, WIN/LOSS/PnL
   Store in DuckDB: one row per trade, linked to snapshot

STAGE 3: EVIDENCE EXTRACTION (per domain + per strategy)
   For each strategy: filter trades, compute domain-specific stats
   For each domain: extract relevant fields, compute accuracy tables
   Build calibration data for Bayesian scoring
   Build training pairs for LoRA fine-tuning
```

---

## Stage 1: Bulk Snapshot Generation

### What We Already Have

`orchestrator.py` already calls all 38 modules in dependency order and produces a merged JSON snapshot. The three training data generators in `rockit-framework` already do batch generation. We just need to run them for ALL 259+ sessions and store the output systematically.

### What We Build

```python
# packages/rockit-train/src/rockit_train/bulk_snapshot.py

"""
Bulk snapshot generation: run all 38 deterministic modules
across all historical sessions and store in DuckDB.
"""

import duckdb
from rockit_core.deterministic.orchestrator import generate_snapshot
from rockit_core.data import load_session_bars

def generate_all_snapshots(
    sessions_dir: str,           # Path to historical CSV sessions
    db_path: str = "data/snapshots.duckdb",
    time_slices: list[str] | None = None,  # Default: every 30 min from 10:00-16:00
) -> int:
    """
    Generate deterministic snapshots for every session × every time slice.
    Idempotent: skips sessions already in the database.

    Returns number of new snapshots generated.
    """
    con = duckdb.connect(db_path)

    # Create table if not exists
    con.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            session_date VARCHAR,
            snapshot_time VARCHAR,
            snapshot JSON,
            -- Pre-extracted fields for fast querying (no JSON parsing needed)
            ib_high DOUBLE,
            ib_low DOUBLE,
            ib_range DOUBLE,
            dpoc_regime VARCHAR,
            tpo_shape VARCHAR,
            cri_status VARCHAR,
            day_type VARCHAR,
            trend_strength VARCHAR,
            compression_bias VARCHAR,
            price_vs_ib VARCHAR,
            fvg_count_bullish INT,
            fvg_count_bearish INT,
            wick_parade_bull INT,
            wick_parade_bear INT,
            vwap DOUBLE,
            poc DOUBLE,
            vah DOUBLE,
            val DOUBLE,
            PRIMARY KEY (session_date, snapshot_time)
        )
    """)

    # Default: 13 time slices per session (every 30 min from 10:00-16:00)
    if time_slices is None:
        time_slices = [
            "10:00", "10:30", "11:00", "11:30",
            "12:00", "12:30", "13:00", "13:30",
            "14:00", "14:30", "15:00", "15:30", "16:00",
        ]

    sessions = list_sessions(sessions_dir)
    existing = set(con.execute(
        "SELECT DISTINCT session_date FROM snapshots"
    ).fetchall())

    new_count = 0
    for session_path in sessions:
        date = extract_date(session_path)
        if (date,) in existing:
            continue

        df = load_session_bars(session_path)

        for t in time_slices:
            snapshot = generate_snapshot(df, snapshot_time=t)

            # Insert with pre-extracted fields
            con.execute("""
                INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                date, t, json.dumps(snapshot),
                snapshot.get("ib_location", {}).get("ib_high"),
                snapshot.get("ib_location", {}).get("ib_low"),
                snapshot.get("ib_location", {}).get("ib_range"),
                snapshot.get("dpoc_migration", {}).get("regime"),
                snapshot.get("tpo_profile", {}).get("tpo_shape"),
                snapshot.get("cri", {}).get("status"),
                snapshot.get("inference_engine", {}).get("day_type"),
                snapshot.get("dalton", {}).get("trend_strength"),
                snapshot.get("core_confluences", {}).get("compression_bias"),
                snapshot.get("ib_location", {}).get("price_vs_ib"),
                snapshot.get("fvg_detection", {}).get("bullish_count", 0),
                snapshot.get("fvg_detection", {}).get("bearish_count", 0),
                snapshot.get("wick_parade", {}).get("bull_count", 0),
                snapshot.get("wick_parade", {}).get("bear_count", 0),
                snapshot.get("volume_profile", {}).get("vwap"),
                snapshot.get("volume_profile", {}).get("poc"),
                snapshot.get("volume_profile", {}).get("vah"),
                snapshot.get("volume_profile", {}).get("val"),
            ])
            new_count += 1

    con.close()
    return new_count
```

### Output

```
data/snapshots.duckdb
├── snapshots table
│   ├── 259 sessions × 13 time slices = ~3,367 rows
│   ├── Each row: full JSON snapshot + pre-extracted fields
│   └── Pre-extracted fields enable fast SQL without JSON parsing
```

### Why DuckDB?

- Single file, zero infrastructure, works on laptop and DGX
- Columnar storage = fast analytical queries across 3,000+ rows
- JSON support = can query nested snapshot fields when needed
- Pre-extracted columns = common queries are fast without JSON overhead
- Portable: copy the `.duckdb` file to any machine

### Cost

One-time: ~10-15 minutes to generate all 259 sessions (38 modules × 13 slices × 259 = ~130K module calls, but each is <10ms = ~22 minutes worst case). Incremental: seconds per new session.

---

## Stage 2: Backtest Enrichment

### What We Already Have

The backtest engine runs strategies through historical data and produces trade records with outcomes. What it doesn't currently do: capture the FULL deterministic snapshot at signal time.

### What We Build

Connect the backtest engine to the snapshot database. When a strategy fires a signal, look up (or generate) the snapshot at that exact time and link them.

```python
# packages/rockit-train/src/rockit_train/backtest_enrichment.py

"""
Enrich backtest trades with full deterministic snapshots.
Links each trade to the market state at signal time.
"""

def enrich_backtest_trades(
    backtest_results: list[dict],   # From BacktestEngine.run()
    snapshot_db: str = "data/snapshots.duckdb",
    output_db: str = "data/enriched_trades.duckdb",
):
    """
    For each backtest trade, find the nearest snapshot and link them.

    Input: trade records from backtest engine
        - date, signal_time, strategy, direction, entry, stop, target, outcome, pnl

    Output: enriched_trades table in DuckDB
        - All trade fields + full snapshot at signal time
        - Pre-extracted fields for fast domain queries
    """
    con = duckdb.connect(output_db)
    snap_con = duckdb.connect(snapshot_db, read_only=True)

    con.execute("""
        CREATE TABLE IF NOT EXISTS enriched_trades (
            -- Trade identity
            trade_id INTEGER PRIMARY KEY,
            session_date VARCHAR,
            signal_time VARCHAR,
            strategy VARCHAR,
            direction VARCHAR,

            -- Trade execution
            entry_price DOUBLE,
            stop_price DOUBLE,
            target_price DOUBLE,

            -- Trade outcome
            outcome VARCHAR,          -- WIN / LOSS / SCRATCH
            pnl DOUBLE,
            rr_achieved DOUBLE,
            exit_reason VARCHAR,      -- target / stop / trail / session_end

            -- Full snapshot at signal time (JSON)
            snapshot JSON,

            -- Pre-extracted: Profile domain
            tpo_shape VARCHAR,
            poc DOUBLE,
            vah DOUBLE,
            val DOUBLE,
            poor_high BOOLEAN,
            poor_low BOOLEAN,
            single_print_count INT,

            -- Pre-extracted: Momentum domain
            dpoc_regime VARCHAR,
            dpoc_velocity DOUBLE,
            wick_parade_bull INT,
            wick_parade_bear INT,
            trend_strength VARCHAR,

            -- Pre-extracted: Structure domain
            fvg_count_bullish INT,
            fvg_count_bearish INT,
            ib_accepted VARCHAR,
            compression_bias VARCHAR,
            price_vs_ib VARCHAR,

            -- Pre-extracted: VWAP domain
            vwap DOUBLE,
            price_vs_vwap VARCHAR,    -- above / below / at

            -- Pre-extracted: Setup domain
            active_setups JSON,       -- Array of setup names that triggered
            cri_status VARCHAR,
            day_type VARCHAR,
            day_type_confidence DOUBLE,

            -- Pre-extracted: HTF domain
            prior_day_trend VARCHAR,
            weekly_bias VARCHAR,
            atr14 DOUBLE
        )
    """)

    for i, trade in enumerate(backtest_results):
        # Find nearest snapshot
        snapshot_row = snap_con.execute("""
            SELECT snapshot FROM snapshots
            WHERE session_date = ?
            ORDER BY ABS(
                EPOCH(CAST(snapshot_time AS TIME)) -
                EPOCH(CAST(? AS TIME))
            )
            LIMIT 1
        """, [trade["date"], trade["signal_time"]]).fetchone()

        if snapshot_row is None:
            continue

        snapshot = json.loads(snapshot_row[0])

        # Extract domain fields and insert
        con.execute("INSERT INTO enriched_trades VALUES (?, ...)", [
            i, trade["date"], trade["signal_time"],
            trade["strategy"], trade["direction"],
            trade["entry"], trade["stop"], trade["target"],
            trade["outcome"], trade["pnl"], trade["rr_achieved"],
            trade.get("exit_reason"),
            json.dumps(snapshot),
            # ... extract all domain fields from snapshot ...
        ])

    con.close()
```

### What This Produces

```
data/enriched_trades.duckdb
├── enriched_trades table
│   ├── 283 rows (one per historical trade)
│   ├── Each row: trade outcome + full snapshot at signal time
│   ├── Pre-extracted domain fields for fast querying
│   └── Queryable by strategy, outcome, domain field
```

### Immediately Useful Queries

Once this table exists, we can answer questions that directly feed specialist training:

```sql
-- "When 20P fired long AND won, what was the DPOC regime?"
SELECT dpoc_regime, COUNT(*) as n,
       COUNT(*) FILTER (WHERE outcome = 'WIN') * 100.0 / COUNT(*) as wr
FROM enriched_trades
WHERE strategy = 'twenty_percent' AND direction = 'long'
GROUP BY dpoc_regime
ORDER BY wr DESC;

-- "What tpo_shape is most common in EdgeFade wins?"
SELECT tpo_shape, COUNT(*) as n, AVG(pnl) as avg_pnl
FROM enriched_trades
WHERE strategy = 'edge_fade' AND outcome = 'WIN'
GROUP BY tpo_shape
ORDER BY n DESC;

-- "Does wick_parade_bear > 3 predict losses across all strategies?"
SELECT
    CASE WHEN wick_parade_bear > 3 THEN 'high_bear_wicks' ELSE 'low_bear_wicks' END as category,
    COUNT(*) as n,
    COUNT(*) FILTER (WHERE outcome = 'WIN') * 100.0 / COUNT(*) as wr,
    AVG(pnl) as avg_pnl
FROM enriched_trades
GROUP BY category;

-- "What are the hidden confluence factors that separate 20P wins from losses?"
-- (This is the Pattern Miner's killer query)
SELECT
    'dpoc_regime' as field, dpoc_regime as value,
    COUNT(*) FILTER (WHERE outcome = 'WIN') as wins,
    COUNT(*) FILTER (WHERE outcome = 'LOSS') as losses,
    COUNT(*) FILTER (WHERE outcome = 'WIN') * 100.0 / COUNT(*) as wr
FROM enriched_trades
WHERE strategy = 'twenty_percent'
GROUP BY dpoc_regime
HAVING COUNT(*) >= 5

UNION ALL

SELECT
    'tpo_shape', tpo_shape,
    COUNT(*) FILTER (WHERE outcome = 'WIN'),
    COUNT(*) FILTER (WHERE outcome = 'LOSS'),
    COUNT(*) FILTER (WHERE outcome = 'WIN') * 100.0 / COUNT(*)
FROM enriched_trades
WHERE strategy = 'twenty_percent'
GROUP BY tpo_shape
HAVING COUNT(*) >= 5

ORDER BY wr DESC;
```

---

## Stage 3: Evidence Extraction

This is where the raw enriched data becomes training material for specialists. Three parallel outputs:

### Output A: Strategy-Specialist Training Data

For each strategy, extract the enriched trades and build training pairs that teach the specialist WHEN its strategy works and WHY.

```python
# packages/rockit-train/src/rockit_train/strategy_training_data.py

"""
Generate training data for strategy-specialist agents.

For each strategy:
1. Pull all enriched trades for that strategy
2. Build input/output pairs:
   - Input: snapshot at signal time
   - Output: structured analysis of WHY this trade worked or failed
3. Output as JSONL for LoRA training or prompt examples
"""

def generate_strategy_training_data(
    strategy: str,
    enriched_db: str = "data/enriched_trades.duckdb",
    output_dir: str = "data/training/strategies/",
):
    con = duckdb.connect(enriched_db, read_only=True)

    trades = con.execute("""
        SELECT * FROM enriched_trades
        WHERE strategy = ?
        ORDER BY session_date
    """, [strategy]).fetchall()

    training_pairs = []

    for trade in trades:
        snapshot = json.loads(trade["snapshot"])

        # Build the input: the snapshot as the specialist would see it
        input_data = {
            "snapshot": snapshot,
            "strategy": strategy,
            "signal_time": trade["signal_time"],
            "direction": trade["direction"],
        }

        # Build the output: what we want the specialist to learn
        # This is the KEY part — we're teaching the model to reason
        # about WHY the trade worked or failed
        output_data = build_strategy_analysis(trade, snapshot, strategy)

        training_pairs.append({
            "input": json.dumps(input_data),
            "output": json.dumps(output_data),
        })

    # Write JSONL
    output_path = f"{output_dir}/{strategy}_training.jsonl"
    with open(output_path, "w") as f:
        for pair in training_pairs:
            f.write(json.dumps(pair) + "\n")

    return len(training_pairs)


def build_strategy_analysis(trade, snapshot, strategy) -> dict:
    """
    Build a structured analysis that teaches the specialist
    to reason about this strategy.

    For WINS: "This worked because [evidence]"
    For LOSSES: "This failed because [evidence]"
    """
    outcome = trade["outcome"]

    # Pull domain-relevant evidence from snapshot
    evidence = extract_strategy_evidence(snapshot, strategy)

    # Compute supporting/contradicting factors
    supporting = [e for e in evidence if e["supports_trade"]]
    contradicting = [e for e in evidence if not e["supports_trade"]]

    return {
        "setup_present": True,
        "direction": trade["direction"],
        "confidence": compute_confidence(supporting, contradicting),
        "outcome": outcome,
        "pnl": trade["pnl"],
        "rr_achieved": trade["rr_achieved"],
        "supporting_evidence": supporting,
        "contradicting_evidence": contradicting,
        "analysis": generate_analysis_text(
            strategy, trade["direction"], outcome,
            supporting, contradicting, trade
        ),
        "lesson": generate_lesson(outcome, supporting, contradicting),
    }


def generate_analysis_text(strategy, direction, outcome, supporting, contradicting, trade) -> str:
    """
    Generate the reasoning text we want the specialist to learn.

    This is NOT an LLM call — it's rule-based template generation.
    The rules encode what we know about each strategy.
    """
    if outcome == "WIN":
        return (
            f"{strategy} {direction} setup was correct. "
            f"Key supporting factors: {', '.join(s['observation'] for s in supporting[:3])}. "
            f"Despite {len(contradicting)} cautionary signals, "
            f"the confluence of {len(supporting)} supporting factors held. "
            f"Achieved {trade['rr_achieved']:.1f}R."
        )
    else:
        return (
            f"{strategy} {direction} setup failed. "
            f"Primary failure factors: {', '.join(c['observation'] for c in contradicting[:3])}. "
            f"Although {len(supporting)} factors supported the trade, "
            f"the {len(contradicting)} contradicting signals proved decisive. "
            f"Lost {abs(trade['pnl']):.0f}."
        )


def generate_lesson(outcome, supporting, contradicting) -> str:
    """
    Generate the lesson for the specialist to internalize.
    This is the meta-learning signal.
    """
    if outcome == "WIN" and len(contradicting) > 2:
        return "Trade won despite multiple contradicting signals. High confluence overcame noise."
    elif outcome == "WIN" and len(contradicting) <= 1:
        return "Clean setup with minimal contradiction. High-conviction pattern."
    elif outcome == "LOSS" and len(supporting) > 3:
        return "Many supporting factors but still lost. Look for the specific killer — which contradicting signal was the real problem?"
    elif outcome == "LOSS" and len(contradicting) > len(supporting):
        return "Contradicting signals outnumbered support. Should have been filtered or skipped."
    else:
        return "Mixed signals with loss. Marginal setup — consider REDUCE_SIZE threshold."
```

#### Training Data Format (per strategy)

```jsonl
{"input": {"snapshot": {...}, "strategy": "twenty_percent", "direction": "long"}, "output": {"setup_present": true, "direction": "long", "confidence": 0.82, "outcome": "WIN", "pnl": 450.0, "rr_achieved": 2.3, "supporting_evidence": [{"observation": "IB accepted above prior VAH", "domain": "dalton", "supports_trade": true}, {"observation": "DPOC trending_on_the_move", "domain": "momentum", "supports_trade": true}], "contradicting_evidence": [{"observation": "Wick parade bearish count = 4", "domain": "momentum", "supports_trade": false}], "analysis": "twenty_percent long setup was correct. Key supporting factors: IB accepted above prior VAH, DPOC trending_on_the_move, FVG bullish cluster above. Despite 1 cautionary signal, the confluence of 5 supporting factors held. Achieved 2.3R.", "lesson": "Clean setup with minimal contradiction. High-conviction pattern."}}
```

### Output B: Domain-Specific Evidence Tables

For domain specialists, extract domain-specific fields across ALL strategies and compute accuracy statistics.

```python
# packages/rockit-train/src/rockit_train/domain_evidence.py

"""
Build domain-specific evidence tables.

For each domain (Dalton, VWAP, ICT, OrderFlow, HTF):
1. Extract relevant fields from all enriched trades
2. Compute: when this domain's signal was bullish, what was the actual WR?
3. Build calibration tables for Bayesian scoring
4. Build training pairs for domain-specialist LoRA
"""

DOMAIN_FIELDS = {
    "dalton": {
        "fields": ["tpo_shape", "poc", "vah", "val", "poor_high", "poor_low",
                    "single_print_count", "day_type", "day_type_confidence",
                    "ib_accepted", "price_vs_ib"],
        "snapshot_sections": ["tpo_profile", "volume_profile", "ib_location",
                              "core_confluences", "balance_classification"],
    },
    "momentum": {
        "fields": ["dpoc_regime", "dpoc_velocity", "wick_parade_bull",
                    "wick_parade_bear", "trend_strength"],
        "snapshot_sections": ["dpoc_migration", "wick_parade", "dalton"],
    },
    "structure": {
        "fields": ["fvg_count_bullish", "fvg_count_bearish",
                    "compression_bias", "price_vs_ib"],
        "snapshot_sections": ["fvg_detection", "ninety_min_pd_arrays",
                              "core_confluences", "premarket"],
    },
    "vwap": {
        "fields": ["vwap", "price_vs_vwap"],
        "snapshot_sections": ["volume_profile"],
    },
    "htf": {
        "fields": ["prior_day_trend", "weekly_bias", "atr14"],
        "snapshot_sections": ["premarket"],
    },
}


def build_domain_calibration_table(
    domain: str,
    enriched_db: str = "data/enriched_trades.duckdb",
) -> dict:
    """
    Build calibration table for a domain.

    For each possible value of each domain field:
    - How many trades had this value?
    - What was the win rate?
    - What was the avg PnL?
    - How does it compare to the base rate?

    This is the Bayesian prior for this domain.
    """
    con = duckdb.connect(enriched_db, read_only=True)

    calibration = {}
    fields = DOMAIN_FIELDS[domain]["fields"]

    # Base rate across all trades
    base = con.execute("""
        SELECT COUNT(*) as n,
               COUNT(*) FILTER (WHERE outcome = 'WIN') * 100.0 / COUNT(*) as base_wr
        FROM enriched_trades
    """).fetchone()

    calibration["base_rate"] = {"n": base[0], "wr": base[1]}

    for field in fields:
        rows = con.execute(f"""
            SELECT {field} as value,
                   COUNT(*) as n,
                   COUNT(*) FILTER (WHERE outcome = 'WIN') * 100.0 / COUNT(*) as wr,
                   AVG(pnl) as avg_pnl,
                   AVG(rr_achieved) as avg_rr
            FROM enriched_trades
            WHERE {field} IS NOT NULL
            GROUP BY {field}
            HAVING COUNT(*) >= 3
            ORDER BY wr DESC
        """).fetchall()

        calibration[field] = [
            {
                "value": r[0],
                "n": r[1],
                "wr": round(r[2], 1),
                "avg_pnl": round(r[3], 2) if r[3] else None,
                "avg_rr": round(r[4], 2) if r[4] else None,
                "lift_vs_base": round(r[2] - base[1], 1),  # +/- vs base WR
            }
            for r in rows
        ]

    return calibration
```

#### Example Output: Dalton Domain Calibration

```json
{
  "base_rate": {"n": 283, "wr": 55.5},
  "dpoc_regime": [
    {"value": "trending_on_the_move", "n": 47, "wr": 72.3, "avg_pnl": 380, "avg_rr": 1.9, "lift_vs_base": +16.8},
    {"value": "stabilizing_after_trend", "n": 31, "wr": 61.3, "avg_pnl": 180, "avg_rr": 1.2, "lift_vs_base": +5.8},
    {"value": "consolidating", "n": 52, "wr": 48.1, "avg_pnl": -45, "avg_rr": 0.6, "lift_vs_base": -7.4},
    {"value": "exhaustion", "n": 18, "wr": 33.3, "avg_pnl": -210, "avg_rr": -0.8, "lift_vs_base": -22.2}
  ],
  "tpo_shape": [
    {"value": "p_shape", "n": 38, "wr": 68.4, "avg_pnl": 290, "avg_rr": 1.7, "lift_vs_base": +12.9},
    {"value": "b_shape", "n": 41, "wr": 63.4, "avg_pnl": 220, "avg_rr": 1.4, "lift_vs_base": +7.9},
    {"value": "d_shape", "n": 22, "wr": 40.9, "avg_pnl": -120, "avg_rr": -0.3, "lift_vs_base": -14.6}
  ],
  "day_type": [
    {"value": "trend_up", "n": 65, "wr": 70.8, "avg_pnl": 340, "avg_rr": 1.8, "lift_vs_base": +15.3},
    {"value": "p_day", "n": 48, "wr": 62.5, "avg_pnl": 200, "avg_rr": 1.3, "lift_vs_base": +7.0},
    {"value": "b_day", "n": 55, "wr": 52.7, "avg_pnl": 50, "avg_rr": 0.8, "lift_vs_base": -2.8},
    {"value": "neutral", "n": 35, "wr": 37.1, "avg_pnl": -180, "avg_rr": -0.5, "lift_vs_base": -18.4}
  ]
}
```

This tells the Dalton specialist: "When you see `dpoc_regime = trending_on_the_move`, historically that's a +16.8% lift over base rate. When you see `exhaustion`, it's -22.2%. Trust accordingly."

### Output C: Cross-Domain Conditional Calibration

The most powerful data: what happens when MULTIPLE domains agree or disagree?

```python
# packages/rockit-train/src/rockit_train/cross_domain_calibration.py

"""
Build conditional calibration tables across domains.

The question: "When Dalton says bullish AND Order Flow says cautious,
what actually happened?"

These conditional probabilities are the backbone of Bayesian consensus.
"""

def build_cross_domain_calibration(
    enriched_db: str = "data/enriched_trades.duckdb",
) -> dict:
    """
    Compute pairwise conditional win rates.

    For every (domain_A_signal, domain_B_signal) combination:
    - How many trades?
    - Win rate?
    - Avg PnL?

    Requires n >= 5 to include (avoid overfitting to noise).
    """
    con = duckdb.connect(enriched_db, read_only=True)

    calibration = {}

    # Example: DPOC regime × wick_parade severity
    rows = con.execute("""
        SELECT
            dpoc_regime,
            CASE
                WHEN wick_parade_bear > 3 THEN 'high_bear_wicks'
                ELSE 'low_bear_wicks'
            END as wick_status,
            COUNT(*) as n,
            COUNT(*) FILTER (WHERE outcome = 'WIN') * 100.0 / COUNT(*) as wr,
            AVG(pnl) as avg_pnl
        FROM enriched_trades
        WHERE dpoc_regime IS NOT NULL
        GROUP BY dpoc_regime, wick_status
        HAVING COUNT(*) >= 5
        ORDER BY wr DESC
    """).fetchall()

    calibration["dpoc_x_wicks"] = [
        {"dpoc": r[0], "wicks": r[1], "n": r[2], "wr": round(r[3], 1), "pnl": round(r[4], 2)}
        for r in rows
    ]

    # DPOC regime × day_type
    rows = con.execute("""
        SELECT dpoc_regime, day_type,
               COUNT(*) as n,
               COUNT(*) FILTER (WHERE outcome = 'WIN') * 100.0 / COUNT(*) as wr,
               AVG(pnl) as avg_pnl
        FROM enriched_trades
        WHERE dpoc_regime IS NOT NULL AND day_type IS NOT NULL
        GROUP BY dpoc_regime, day_type
        HAVING COUNT(*) >= 5
        ORDER BY wr DESC
    """).fetchall()

    calibration["dpoc_x_daytype"] = [
        {"dpoc": r[0], "daytype": r[1], "n": r[2], "wr": round(r[3], 1), "pnl": round(r[4], 2)}
        for r in rows
    ]

    # FVG count × direction × outcome
    rows = con.execute("""
        SELECT
            direction,
            CASE
                WHEN fvg_count_bullish > fvg_count_bearish THEN 'more_bull_fvgs'
                WHEN fvg_count_bearish > fvg_count_bullish THEN 'more_bear_fvgs'
                ELSE 'balanced_fvgs'
            END as fvg_bias,
            COUNT(*) as n,
            COUNT(*) FILTER (WHERE outcome = 'WIN') * 100.0 / COUNT(*) as wr,
            AVG(pnl) as avg_pnl
        FROM enriched_trades
        GROUP BY direction, fvg_bias
        HAVING COUNT(*) >= 5
        ORDER BY wr DESC
    """).fetchall()

    calibration["direction_x_fvgs"] = [
        {"direction": r[0], "fvg_bias": r[1], "n": r[2], "wr": round(r[3], 1), "pnl": round(r[4], 2)}
        for r in rows
    ]

    # Strategy × dpoc_regime (strategy-specific domain evidence)
    rows = con.execute("""
        SELECT strategy, dpoc_regime,
               COUNT(*) as n,
               COUNT(*) FILTER (WHERE outcome = 'WIN') * 100.0 / COUNT(*) as wr,
               AVG(pnl) as avg_pnl
        FROM enriched_trades
        WHERE dpoc_regime IS NOT NULL
        GROUP BY strategy, dpoc_regime
        HAVING COUNT(*) >= 3
        ORDER BY strategy, wr DESC
    """).fetchall()

    calibration["strategy_x_dpoc"] = [
        {"strategy": r[0], "dpoc": r[1], "n": r[2], "wr": round(r[3], 1), "pnl": round(r[4], 2)}
        for r in rows
    ]

    return calibration
```

#### Example Output: Cross-Domain Calibration

```json
{
  "dpoc_x_wicks": [
    {"dpoc": "trending_on_the_move", "wicks": "low_bear_wicks", "n": 35, "wr": 82.9, "pnl": 450},
    {"dpoc": "trending_on_the_move", "wicks": "high_bear_wicks", "n": 12, "wr": 50.0, "pnl": 80},
    {"dpoc": "consolidating", "wicks": "high_bear_wicks", "n": 18, "wr": 27.8, "pnl": -310}
  ],
  "strategy_x_dpoc": [
    {"strategy": "twenty_percent", "dpoc": "trending_on_the_move", "n": 22, "wr": 81.8, "pnl": 520},
    {"strategy": "twenty_percent", "dpoc": "consolidating", "n": 8, "wr": 25.0, "pnl": -280},
    {"strategy": "edge_fade", "dpoc": "exhaustion", "n": 11, "wr": 72.7, "pnl": 310},
    {"strategy": "edge_fade", "dpoc": "trending_on_the_move", "n": 7, "wr": 28.6, "pnl": -190}
  ]
}
```

This is gold. It tells us:
- **20P + trending DPOC + low bear wicks = 82.9% WR** — slam dunk, full size
- **20P + consolidating DPOC = 25% WR** — never take this
- **EdgeFade + exhaustion DPOC = 72.7% WR** — perfect fit (mean reversion when momentum exhausts)
- **EdgeFade + trending DPOC = 28.6% WR** — never fade a trend (which the EdgeFade specialist should learn)

---

## How This Feeds Each Approach from Doc 04

### Feeding Strategy Specialists (Approach 1)

```
enriched_trades.duckdb
  → filter by strategy = 'twenty_percent'
  → generate_strategy_training_data('twenty_percent')
  → training/strategies/twenty_percent_training.jsonl

Each specialist gets:
  - All historical trades for its strategy
  - Full snapshot at each signal time
  - Outcome + reasoning template (WIN: why it worked, LOSS: why it failed)
  - Cross-domain calibration data specific to that strategy
```

**Training**: Fine-tune (or prompt-stuff) the specialist with its strategy's data. The specialist learns patterns like "when MY strategy fires AND dpoc is trending, it's 82% — but when dpoc is consolidating, only 25%."

### Feeding Domain Specialists (Approach 2)

```
enriched_trades.duckdb
  → build_domain_calibration_table('dalton')
  → calibration/dalton_calibration.json

Each domain specialist gets:
  - Calibration table for all its fields
  - Cross-domain conditional tables
  - All snapshot sections relevant to its domain
```

**Training**: The domain specialist doesn't learn about specific strategies — it learns "when TPO shape is P and DPOC is trending, across ALL strategies, the WR is 72%." It becomes a domain authority.

### Feeding Bayesian Chain (Approach 4)

```
enriched_trades.duckdb
  → build_cross_domain_calibration()
  → calibration/bayesian_priors.json

The Bayesian engine gets:
  - Per-field calibration (each field's predictive power)
  - Cross-field conditional calibration (field A + field B → WR)
  - Per-strategy base rates
  - Lift values (how much each observation shifts from base rate)
```

**No training needed**. The Bayesian engine is pure math — lookup tables + Bayesian updating. The calibration data IS the intelligence.

---

## The Full Pipeline Visualization

```
HISTORICAL SESSION CSVs (259+)
        │
        ▼
┌──────────────────────────┐
│  STAGE 1: BULK SNAPSHOTS │  orchestrator.py × 38 modules
│  259 sessions × 13 times │  ~3,367 snapshots
│  → snapshots.duckdb      │  (~15 minutes, one-time)
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  STAGE 2: BACKTEST       │  BacktestEngine.run()
│  ENRICHMENT              │  Link trades → snapshots
│  283 trades + snapshots  │
│  → enriched_trades.duckdb│  (~2 minutes)
└──────────┬───────────────┘
           │
           ├────────────────────────────────────────┐
           │                                        │
           ▼                                        ▼
┌─────────────────────────┐          ┌──────────────────────────┐
│  STAGE 3A: STRATEGY     │          │  STAGE 3B: DOMAIN        │
│  TRAINING DATA          │          │  CALIBRATION TABLES      │
│                         │          │                          │
│  Per strategy:          │          │  Per domain:             │
│  - twenty_percent.jsonl │          │  - dalton_calibration    │
│  - edge_fade.jsonl      │          │  - momentum_calibration  │
│  - b_day.jsonl          │          │  - structure_calibration │
│  - ...8-10 strategies   │          │  - vwap_calibration      │
│                         │          │  - htf_calibration       │
│  Used for:              │          │                          │
│  - LoRA fine-tuning     │          │  Used for:               │
│  - Specialist prompts   │          │  - Bayesian priors       │
│  - Few-shot examples    │          │  - Domain agent prompts  │
└─────────────────────────┘          │  - Pattern Miner queries │
                                     └──────────────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  STAGE 3C: CROSS-DOMAIN     │
│  CONDITIONAL CALIBRATION     │
│                              │
│  - dpoc × wick_parade → WR  │
│  - strategy × dpoc → WR     │
│  - direction × fvg_bias → WR│
│  - day_type × compression   │
│  - ... all useful combos     │
│                              │
│  Used for:                   │
│  - Bayesian conditional      │
│  - Specialist context        │
│  - Orchestrator grounding    │
│  - "When X AND Y, WR is Z"  │
└──────────────────────────────┘
```

---

## Generating the Analysis Text (No LLM Required for Labels)

A key question: how do we generate the "output" side of training pairs? The current pipeline uses LLM annotation (Qwen 2.5, Grok). But for strategy-specialist training, **we don't need an LLM to label — we have ground truth from the backtest**.

```
Current pipeline:
  Snapshot → LLM → "Here's my analysis" → JSONL {input: snapshot, output: llm_analysis}
  Problem: the LLM analysis is an opinion, not ground truth

Strategy specialist pipeline:
  Snapshot → Backtest Engine → WIN/LOSS + PnL → Template-based reasoning → JSONL
  Advantage: the label IS the ground truth
```

### Template-Based Reasoning Labels

For each trade, we can generate structured reasoning WITHOUT an LLM:

```python
def generate_ground_truth_label(trade, snapshot, calibration) -> dict:
    """
    Generate training label from backtest ground truth + calibration data.
    No LLM needed — this is deterministic label generation.
    """
    strategy = trade["strategy"]
    outcome = trade["outcome"]
    direction = trade["direction"]

    # Pull calibration for this strategy
    strat_cal = calibration.get(f"strategy_x_dpoc", [])
    dpoc = snapshot.get("dpoc_migration", {}).get("regime")

    # Find the calibration row for this strategy + dpoc combo
    match = next(
        (r for r in strat_cal
         if r["strategy"] == strategy and r["dpoc"] == dpoc),
        None,
    )

    # Build evidence assessment
    supporting = []
    contradicting = []

    # Check each domain's contribution
    if dpoc in ["trending_on_the_move", "accelerating"]:
        if direction == "long":
            supporting.append({
                "domain": "momentum",
                "observation": f"DPOC regime is {dpoc} — bullish momentum",
                "historical_wr": match["wr"] if match else None,
                "n": match["n"] if match else None,
            })
        else:
            contradicting.append({
                "domain": "momentum",
                "observation": f"DPOC regime is {dpoc} — trending against short",
                "historical_wr": match["wr"] if match else None,
                "n": match["n"] if match else None,
            })

    wick_bear = snapshot.get("wick_parade", {}).get("bear_count", 0)
    if wick_bear > 3 and direction == "long":
        contradicting.append({
            "domain": "momentum",
            "observation": f"Wick parade bearish count = {wick_bear} — sellers trapping bulls",
            "historical_wr": None,  # compute from calibration
            "n": None,
        })

    tpo_shape = snapshot.get("tpo_profile", {}).get("tpo_shape")
    if tpo_shape in ["p_shape"] and direction == "long":
        supporting.append({
            "domain": "dalton",
            "observation": f"TPO shape is {tpo_shape} — responsive buying, bullish",
        })

    # ... continue for all domain fields ...

    return {
        "strategy": strategy,
        "direction": direction,
        "outcome": outcome,
        "pnl": trade["pnl"],
        "rr_achieved": trade["rr_achieved"],
        "confidence_should_have_been": compute_ideal_confidence(
            supporting, contradicting, outcome
        ),
        "supporting_evidence": supporting,
        "contradicting_evidence": contradicting,
        "verdict": (
            "TAKE" if outcome == "WIN" else
            "SKIP" if len(contradicting) > len(supporting) else
            "REDUCE_SIZE"
        ),
        "reasoning": build_reasoning_text(
            strategy, direction, outcome,
            supporting, contradicting, trade
        ),
    }


def compute_ideal_confidence(supporting, contradicting, outcome) -> float:
    """
    Hindsight confidence: what SHOULD the confidence have been?

    For wins with strong support: high confidence (0.75-0.95)
    For wins despite contradiction: medium (0.55-0.70)
    For losses with many support: low (0.40-0.55) — overconfidence penalty
    For losses with contradiction: very low (0.20-0.40) — should have been filtered
    """
    support_count = len(supporting)
    contra_count = len(contradicting)
    ratio = support_count / max(support_count + contra_count, 1)

    if outcome == "WIN":
        return 0.5 + ratio * 0.45  # range: 0.50-0.95
    else:
        return 0.2 + ratio * 0.35  # range: 0.20-0.55
```

### Why This Matters

The model learns to reason like this:

> "I see a 20P long setup. DPOC is trending_on_the_move (historically 82% WR for this combo). TPO shape is P (bullish). But wick parade bearish = 5 (historically drops WR by 15%). My confidence should be ~0.68 — TAKE with slightly reduced size."

This is what we mean by "training the intelligence on profitable strategies and building evidence on why a trade works." The model doesn't just learn "20P + trending = good." It learns the EVIDENCE STRUCTURE — which factors support, which contradict, and how to weigh them.

---

## Incremental Updates

As new sessions are traded and added:

```
New session CSV arrives
    │
    ├─→ Stage 1: generate_snapshot() → append to snapshots.duckdb
    │       (seconds — just 13 new snapshots)
    │
    ├─→ Stage 2: run backtest for new session → append to enriched_trades.duckdb
    │       (seconds — just the new trades)
    │
    ├─→ Stage 3A: regenerate affected strategy training JSONL
    │       (seconds — append new training pairs)
    │
    ├─→ Stage 3B: recompute domain calibration tables
    │       (seconds — full table recompute is fast on DuckDB)
    │
    └─→ Stage 3C: recompute cross-domain conditionals
            (seconds — same)
```

Total time for incremental update: **under 30 seconds** per new session. The pipeline stays fresh automatically.

---

## Generating Non-Signal Snapshots (Negative Examples)

An important point: we need to train specialists on WHEN TO DO NOTHING, not just when to trade. Out of ~3,367 snapshots, only 283 led to trades. The other ~3,084 are "no setup" time slices.

```python
def generate_negative_examples(
    snapshot_db: str = "data/snapshots.duckdb",
    enriched_db: str = "data/enriched_trades.duckdb",
    strategy: str = "twenty_percent",
) -> list[dict]:
    """
    Generate training examples where the strategy should NOT have fired.

    These teach the specialist:
    - "Conditions are close but not quite there — SKIP"
    - "Setup is present but confluence is weak — SKIP"
    - "This looks like my setup but the regime is wrong — SKIP"
    """
    snap_con = duckdb.connect(snapshot_db, read_only=True)
    trade_con = duckdb.connect(enriched_db, read_only=True)

    # Get all snapshots
    all_snapshots = snap_con.execute(
        "SELECT session_date, snapshot_time, snapshot FROM snapshots"
    ).fetchall()

    # Get snapshots that DID produce trades for this strategy
    trade_times = set(trade_con.execute("""
        SELECT session_date || '_' || signal_time
        FROM enriched_trades WHERE strategy = ?
    """, [strategy]).fetchall())

    negatives = []
    for date, time, snapshot_json in all_snapshots:
        if f"{date}_{time}" in trade_times:
            continue  # This was a trade — skip

        snapshot = json.loads(snapshot_json)

        # Check if this strategy's conditions were PARTIALLY met
        # (more interesting than completely unrelated snapshots)
        partial_match = check_partial_setup(snapshot, strategy)

        if partial_match["match_score"] > 0.3:
            negatives.append({
                "input": {"snapshot": snapshot, "strategy": strategy},
                "output": {
                    "setup_present": False,
                    "partial_conditions_met": partial_match["conditions_met"],
                    "missing_conditions": partial_match["conditions_missing"],
                    "verdict": "SKIP",
                    "reasoning": (
                        f"{strategy} conditions partially met "
                        f"({partial_match['match_score']:.0%}): "
                        f"has {', '.join(partial_match['conditions_met'])} "
                        f"but missing {', '.join(partial_match['conditions_missing'])}."
                    ),
                }
            })

    return negatives
```

### Why Negative Examples Matter

Without negatives, the model learns: "When I see a snapshot and my strategy is mentioned, always say TAKE." With negatives, it learns: "Conditions exist on a spectrum. 80% of the time, conditions are NOT right for my strategy. I need to be selective."

The ratio matters: aim for roughly **3:1 negatives to positives** in training data. This teaches the specialist to be disciplined, not trigger-happy.

---

## Data Volume Summary

```
Stage 1 — Bulk Snapshots:
  259 sessions × 13 time slices = 3,367 snapshots
  Storage: ~50MB in DuckDB

Stage 2 — Enriched Trades:
  283 trades with full snapshots
  Storage: ~5MB in DuckDB

Stage 3A — Strategy Training Data:
  Per strategy, ~15-45 positive examples + ~100-200 negative examples
  Total across 8 core strategies: ~1,500-2,000 training pairs
  Storage: ~20MB JSONL

Stage 3B — Domain Calibration:
  5 domains × ~10-20 field values each = ~100 calibration entries
  Storage: <1MB JSON

Stage 3C — Cross-Domain Calibration:
  ~50-100 useful conditional combinations
  Storage: <1MB JSON

TOTAL: ~80MB, all fits in memory, all computable in <30 minutes
```

This is not big data. It's small, structured, and rich. Every byte carries signal.

---

## What We Can Start Building Today

The pipeline has zero external dependencies — it uses code that already exists:

| Component | Status | What's Needed |
|---|---|---|
| `orchestrator.py` (38 modules) | EXISTS in rockit-framework | Migrate to rockit-core |
| `BacktestEngine` | EXISTS in BookMapOrderFlowStudies | Migrate to rockit-core |
| Historical CSVs | EXISTS (259 sessions) | Already available |
| DuckDB | Zero-install, pip install duckdb | Nothing |
| Snapshot generation script | Based on existing `generate_training_data_90days.py` | Extend to all 259 sessions |
| Enrichment script | NEW but simple | Link backtest trades to snapshots |
| Calibration scripts | NEW but just SQL queries | ~200 lines of Python |
| Training JSONL generation | Based on existing `generate_lora_training_data.py` | Add evidence extraction |

The hardest part isn't building the pipeline — it's migrating `orchestrator.py` and `BacktestEngine` into `rockit-core` so they can be imported by `rockit-train`. That migration is already Phase 1 of the roadmap.

---

*Once this pipeline runs, every approach in `04-agent-specialization-and-consensus.md` has data to work with. Strategy specialists get per-strategy JSONL. Domain specialists get calibration tables. Bayesian engine gets conditional probabilities. The data pipeline is the foundation — build it first, then experiment with agent architectures on top.*
