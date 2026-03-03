# 13 — Backtest Data Pipeline: Trade Database + Agent Training Data

**Status**: Brainstorm / Roadmap
**Related**: `08-agent-system.md`, `11-testing-and-automation.md`

---

## Problem

Backtest trades are currently saved as flat JSON files (`data/results/backtest_NQ_YYYYMMDD_HHMMSS.json`). Each run overwrites the baseline. There is:

- No persistent trade database across runs
- No deterministic snapshot attached to each trade (the 38-module analysis that describes WHY the market looked the way it did at entry)
- No way for agents to query historical trades by context (e.g., "show me all B-Day IBL fades where delta was negative at entry")
- No labeled win/loss dataset for agent debate or reflection

## Current State

```
Backtest run
  -> JSON file with trades array
     -> Each trade: strategy, direction, entry/exit price, P&L, exit reason, bars held
     -> Missing: deterministic snapshot at entry, market context, order flow state
  -> Baseline file (latest snapshot only)
  -> No database, no queryable history
```

## Core Principle: Record ALL Trades — Winners AND Losers

Every trade must be recorded with full context, regardless of outcome. **Losers are more valuable than winners** for learning — a win can be lucky, but a loss always has a structural reason that can be identified through deterministic analysis.

The system must be able to explain WHY a trade failed:
- Was the day type misclassified at entry? (e.g., B-Day that morphed into Trend)
- Was order flow diverging from the setup? (e.g., long entry with negative delta)
- Did a key level get violated before entry? (e.g., VWAP breach, IB extension beyond threshold)
- Was the stop placed incorrectly relative to structure?
- Was it simply a clean setup that got caught by a regime shift?

Without this analysis, losses are just numbers. With it, every loss becomes a training signal — either the strategy needs a new filter, or the loss was "correct" (clean setup, just lost).

## Skill: `/analyze-trade` — Post-Trade Forensics

A repeatable skill that examines any trade (win or loss) and produces a structured explanation. This is something we do over and over — manually inspecting deterministic data after a trade to understand what happened. Automating this into a skill is critical.

### What the Skill Does

Given a trade record (from backtest or live):

1. **Reconstruct market state at entry**: Pull the deterministic snapshot, order flow, day type classification, confidence scores, key levels
2. **Reconstruct market state at exit**: What changed between entry and exit? Did day type morph? Did a key level break? Did order flow reverse?
3. **Identify the failure mode** (for losses):
   - `REGIME_SHIFT` — day type changed after entry (B-Day → Trend)
   - `ORDER_FLOW_DIVERGENCE` — delta/CVD opposed the trade direction
   - `LEVEL_VIOLATION` — key structure level broke (VWAP, VA edge, IB edge)
   - `STOP_TOO_TIGHT` — MFE shows trade went right then reversed past stop
   - `STOP_TOO_WIDE` — MAE shows immediate adverse move, stop was too far
   - `TIME_DECAY` — setup was valid but ran out of time (EOD exit)
   - `CLEAN_LOSS` — everything aligned, just a statistical loss
4. **Annotate the trade** with observations, tags, and a confidence rating on whether the trade should have been taken
5. **Compare to similar historical trades** — query the database for same strategy + same context, show WR distribution

### Skill Output

```
Trade: 80P Rule SHORT @ 21450.0 on 2025-08-15
Result: STOP hit, -$1,250

Failure Mode: REGIME_SHIFT
  - Entry day type: b_day (confidence: 0.62)
  - At exit: day type morphed to trend_bull (extension 1.2x IB)
  - IB extension went from 0.15x at entry to 1.2x at stop

Order Flow at Entry:
  - Delta: +280 (OPPOSING — buyers active, short setup questionable)
  - CVD: rising (3-bar slope positive)
  - Volume: declining (exhaustion signal was valid)

Annotation: AVOID — delta divergence + low day type confidence (0.62)
  suggested filter: require delta < 0 for SHORT setups

Similar Trades (8 found):
  - Delta opposing at entry: 2/8 won (25% WR)
  - Delta confirming at entry: 4/8 won (50% WR)
```

### Why This Matters for the Agent System

- **Advocate** uses trade annotations to build confidence: "This setup has 65% WR when delta confirms"
- **Skeptic** uses failure mode analysis to challenge: "Last 5 times this fired with delta opposing, 4 were stopped out"
- **Reflection agent** aggregates annotations nightly: "3 of today's 4 losses were REGIME_SHIFT — consider tightening day type confidence threshold"
- **Training pipeline** uses annotations as labeled examples: the annotation IS the reasoning output we want the LLM to learn

## Vision: Trade Database with Deterministic Context

Every backtest trade — winner and loser — should be stored with full deterministic context at the moment of entry AND exit. This creates a labeled dataset of "what did the market look like when this strategy fired, and did it work?"

### What to Store Per Trade

**Trade Outcome** (already have):
- Strategy name, setup type, direction
- Entry/exit price, stop, target
- P&L, exit reason (TARGET, STOP, EOD, TRAILING)
- Bars held, contracts

**Market Context at Entry** (need to add):
- Day type classification + confidence scores
- IB range, IB extension, IB direction
- Prior VA levels (VAH, VAL, POC, width)
- VWAP, EMA20, EMA50 relative to price
- Session high/low at time of entry
- Time of day

**Order Flow at Entry** (need to add):
- Delta (cumulative, rolling)
- CVD trend
- Volume profile (POC location, value area skew)
- Bid/ask volume ratio

**Deterministic Snapshot at Entry** (from rockit-core/deterministic/):
- Full 38-module analysis output for the entry bar
- This is the same data format used for LLM training (JSONL)
- Enables agents to "see" exactly what a human analyst would see

**Deterministic Snapshot at Exit** (critical for loss analysis):
- Full 38-module analysis at exit bar — what changed?
- Day type at exit vs day type at entry (did it morph?)
- Order flow at exit vs entry (did delta/CVD flip?)
- Which key levels broke between entry and exit?

**Trade Annotation** (generated by `/analyze-trade` skill):
- Failure mode classification (REGIME_SHIFT, ORDER_FLOW_DIVERGENCE, etc.)
- Human-readable explanation of why the trade won or lost
- Suggested filter improvements (if loss was avoidable)
- Confidence rating: should this trade have been taken?
- Tags for querying (e.g., "delta_opposing", "low_confidence_day_type")

### Storage Options

| Option | Pros | Cons |
|--------|------|------|
| DuckDB (local) | Fast analytics, SQL, zero-config, already in architecture | Single-file, no concurrent writes |
| SQLite | Universal, simple | Slower for analytics queries |
| Parquet files | Columnar, fast reads, git-friendly sizes | No SQL without DuckDB overlay |
| PostgreSQL | Production-ready, concurrent | Overkill for local dev |

**Recommendation**: DuckDB (aligns with `08-agent-system.md` Historian agent design). Parquet export for sharing/archival.

## Use Cases for Agent System

### 1. Advocate/Skeptic Debate Fuel

The Advocate agent proposes a trade. The Skeptic queries the trade database:

> "The last 12 times 80P fired on a B-Day with delta < 0 at entry,
> 9 were stopped out. Current delta is -450. Skeptic rates this setup
> LOW confidence."

This requires structured, queryable trade history with market context.

### 2. Self-Learning Loop (Daily Reflection)

Post-market, the Reflection agent reviews today's trades:

> "Today's B-Day IBL fade lost $550. At entry, IB extension was 0.45x
> (borderline P-Day). Historical WR for B-Day fades with extension
> 0.3-0.5x is 38% vs 62% for extension < 0.3x. Consider adding
> extension filter."

### 3. Strategy Optimization Evidence

Instead of curve-fitting parameters, agents can query:

> "What is the MFE distribution for 80P trades where VA width > 200?"
> "What exit reason dominates when entry is after 12:00 ET?"

### 4. Training Data Generation

Each trade + deterministic snapshot becomes a training example:

```jsonl
{"input": {"deterministic_snapshot": {...}, "trade_setup": {...}},
 "output": {"decision": "TAKE", "confidence": 0.85, "reasoning": "..."}}
```

This is the bridge between backtesting and LLM fine-tuning.

## Implementation Roadmap

### Phase 1: Enrich Backtest Trades (near-term)
- [ ] Attach `session_context` dict to each trade in backtest engine
- [ ] Include bar-level data at entry (OHLCV, delta, volume)
- [ ] Save enriched trades to DuckDB after each backtest run
- [ ] Schema: `trades` table with JSON columns for context

### Phase 2: `/analyze-trade` Skill (near-term, high value)
- [ ] Build skill that takes a trade record and produces structured forensics
- [ ] Reconstruct entry and exit market state from stored context
- [ ] Classify failure mode (REGIME_SHIFT, ORDER_FLOW_DIVERGENCE, CLEAN_LOSS, etc.)
- [ ] Generate human-readable annotation with suggested improvements
- [ ] Compare to similar historical trades from database
- [ ] This is a repeatable workflow we do constantly — automating it is critical

### Phase 3: Deterministic Snapshots (medium-term)
- [ ] Run deterministic orchestrator at each entry AND exit bar
- [ ] Store both snapshots alongside trade record
- [ ] Diff entry vs exit snapshot to identify what changed (day type morph, level breaks, OF reversal)
- [ ] Index by strategy, day_type, direction, outcome, failure_mode for fast queries

### Phase 4: Agent Query Interface (agent-system phase)
- [ ] Historian agent with DuckDB query access
- [ ] Pre-built queries: "similar setups", "regime performance", "filter analysis"
- [ ] Advocate/Skeptic can request historical evidence during debate
- [ ] Reflection agent generates nightly insights from trade database
- [ ] Annotations from `/analyze-trade` feed directly into agent reasoning

### Phase 5: Training Pipeline (ML phase)
- [ ] Export trade + snapshot + annotation triples as JSONL training data
- [ ] Label with outcome (win/loss/scratch) and quality (clean/messy)
- [ ] The annotation IS the reasoning output we want the LLM to learn
- [ ] Feed into LoRA fine-tuning pipeline for Qwen3.5

## Open Questions

1. **Granularity**: Store only entry/exit snapshots, or full trade lifecycle (every bar from entry to exit)?
2. **Deduplication**: Same trade across multiple backtest runs — keep all or deduplicate?
3. **Versioning**: When strategy logic changes, old trades have different entry criteria. Tag with strategy version?
4. **Real-time vs backtest**: Same schema for live trades and backtest trades? Unified or separate tables?
5. **Snapshot cost**: Running 38 deterministic modules per trade × 393 trades = ~15K module runs per backtest. Acceptable latency?
6. **Annotation review**: Should annotations be auto-generated only, or should there be a human review/override step?
7. **Annotation drift**: As the system learns, early annotations may be naive. Re-annotate historical trades periodically?
