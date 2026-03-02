# Self-Learning & Reflection Architecture

## The Core Idea

The system doesn't just trade — it watches itself trade, evaluates its own reasoning, and makes small adjustments autonomously. Large redesigns are escalated to Opus 4.6 every 1–3 days. Every change is versioned and revertible.

```
                     ┌─────────────────────────────────┐
                     │        DAILY CYCLE               │
                     │                                   │
  Market Hours       │   Post-Market (4:15 PM ET)        │
  ─────────────      │   ─────────────────────────       │
  Deterministic      │   1. Outcome Logger               │
  rules + Qwen3.5    │      (what actually happened)     │
  debate agents      │   2. Per-Agent Scorecards          │
  emit signals       │      (prediction vs reality)      │
       │             │   3. Reflection Journal            │
       │             │      (Qwen3.5 self-analysis)       │
       │             │   4. Adjustment Proposals           │
       │             │      (small parameter tweaks)      │
       │             │                                     │
       ▼             └──────────┬──────────────────────────┘
  Trade outcomes                │
  logged with                   ▼
  full context          ┌───────────────────────────┐
                        │   MULTI-DAY CYCLE          │
                        │   (Every 1-3 days)         │
                        │                             │
                        │   Opus 4.6 Meta-Review      │
                        │   • Reviews reflection logs │
                        │   • Proposes prompt changes  │
                        │   • A/B test design          │
                        │   • Code/calc improvements   │
                        │   • All changes on branches  │
                        └───────────────────────────┘
```

---

## Layer 1: Daily Outcome Logging (Deterministic, No LLM)

After market close every day, a cron job runs the **Outcome Logger** — pure Python, no model needed.

### What Gets Recorded

For every signal emitted during the session:

```python
# packages/rockit-pipeline/src/rockit_pipeline/reflection/outcome_logger.py

@dataclass
class SignalOutcome:
    """Complete record of one signal and what happened after."""
    # Identity
    date: str                          # "2026-03-01"
    strategy: str                      # "TrendDayBull"
    agent_id: str                      # "advocate_trend_bull"
    signal_time: str                   # "10:32"

    # What the system predicted
    direction: str                     # "long"
    entry_price: float                 # 21850.0
    stop_price: float                  # 21830.0
    target_price: float                # 21890.0
    confidence: float                  # 0.78
    day_type_prediction: str           # "P-Day (Bullish)"
    advocate_reasoning: str            # Full text of advocate argument
    skeptic_reasoning: str             # Full text of skeptic argument
    consensus_decision: str            # "TAKE" / "SKIP" / "REDUCE_SIZE"
    consensus_confidence: float        # 0.72

    # What actually happened
    actual_day_type: str               # "Trend Day" (computed from full session data)
    price_at_target_time: float        # Where price went
    max_favorable_excursion: float     # Best price in signal direction
    max_adverse_excursion: float       # Worst price against signal
    outcome: str                       # "WIN" / "LOSS" / "SCRATCH" / "NOT_TAKEN"
    pnl: float                         # Actual P&L if taken
    rr_achieved: float                 # R-multiple achieved

    # Context snapshot (for RAG retrieval later)
    market_context: dict               # IB range, volume, regime, etc.
    filter_results: dict               # Which filters passed/failed
    order_flow_snapshot: dict           # Delta, CVD, imbalance at signal time
```

### Per-Agent Scorecard

Aggregated daily for each agent:

```python
@dataclass
class AgentScorecard:
    date: str
    agent_id: str
    strategy: str

    # Signal quality
    signals_emitted: int
    signals_taken: int                 # After consensus filter
    signals_correct_direction: int     # Price moved in predicted direction
    signals_hit_target: int
    signals_hit_stop: int

    # Reasoning quality
    day_type_accuracy: float           # Did it call the day type right?
    advocate_win_rate: float           # When advocate argued FOR, was it right?
    skeptic_save_rate: float           # When skeptic argued AGAINST, did it prevent a loss?
    consensus_override_accuracy: float # When consensus overrode a signal, was that right?

    # Calibration
    confidence_vs_outcome: list[tuple] # [(confidence, was_correct), ...]
    # Ideally: 80% confidence → 80% win rate (calibrated)

    # Filter effectiveness
    filter_value_added: dict           # {filter_name: signals_correctly_blocked}
```

Storage: `gs://rockit-data/reflection/outcomes/{date}.jsonl` and `gs://rockit-data/reflection/scorecards/{date}.jsonl`

---

## Layer 2: Daily Reflection (Qwen3.5 — Runs Post-Market)

After the Outcome Logger runs, Qwen3.5 does a structured self-analysis. This is the system "thinking about its own thinking."

### Reflection Prompt Template

```python
# packages/rockit-pipeline/src/rockit_pipeline/reflection/daily_reflection.py

REFLECTION_PROMPT = """
You are the Rockit trading system reviewing your own performance today.

## Today's Scorecards
{scorecards_json}

## Today's Signal Outcomes
{outcomes_json}

## Recent History (last 5 days)
{recent_scorecards}

## Your Current Prompt Versions
{current_prompts}

Analyze the following and be specific:

1. ACCURACY REVIEW
   - Which strategies called the day type correctly?
   - Which signals would have been profitable? Which were wrong and why?
   - Were there setups the system MISSED that it should have caught?

2. REASONING QUALITY
   - Review each Advocate/Skeptic debate. Was the reasoning sound?
   - Did the Skeptic catch real risks or was it just noise?
   - Did the Orchestrator weigh evidence correctly?

3. CALIBRATION CHECK
   - Is confidence well-calibrated? (70% confidence → ~70% win rate)
   - Any systematic over/under-confidence?

4. PATTERN OBSERVATIONS
   - Recurring failure modes (e.g., "always wrong on low-IB-range mornings")
   - Emerging edge (e.g., "DPOC migration + high delta = reliable trend signal")
   - Regime shifts (e.g., "choppy week, trend strategies underperforming")

5. ADJUSTMENT PROPOSALS (small, specific, testable)
   - Parameter tweaks: "Reduce TrendBull confidence by 5% when IB range < 30pts"
   - Filter additions: "Add VIX > 25 gate to EdgeFade"
   - Prompt tweaks: "Advocate should weight DPOC migration more heavily"
   - Each proposal must include: what to change, expected impact, how to measure

Output as structured JSON.
"""
```

### Reflection Output Schema

```json
{
  "date": "2026-03-01",
  "session_summary": "Choppy B-Day, 2 signals emitted, 1 taken (loss), 1 skipped (would have won)",
  "accuracy": {
    "day_type_correct": false,
    "day_type_predicted": "P-Day",
    "day_type_actual": "B-Day",
    "signal_accuracy": 0.50
  },
  "reasoning_quality": {
    "advocate_sound": true,
    "skeptic_useful": false,
    "skeptic_note": "Skeptic raised generic concerns, missed the key issue (narrow IB = B-Day)",
    "orchestrator_decision_quality": "poor — should have weighted IB range more"
  },
  "calibration": {
    "confidence_bias": "overconfident",
    "avg_confidence": 0.75,
    "actual_win_rate": 0.45,
    "note": "System consistently 15-20% overconfident on choppy days"
  },
  "patterns_observed": [
    "Third consecutive day where narrow IB (< 35pts) was misclassified as Trend/P-Day",
    "EdgeFade signals on B-Days performing well — 3/3 this week"
  ],
  "adjustment_proposals": [
    {
      "id": "adj-20260301-001",
      "type": "parameter",
      "target": "day_confidence_scorer",
      "change": "Increase B-Day probability weight when IB range < 35pts",
      "parameter": "ib_range_bday_threshold",
      "current_value": 30,
      "proposed_value": 35,
      "expected_impact": "Fewer false Trend/P-Day calls on narrow days",
      "measurable": "Day type accuracy on < 35pt IB days",
      "risk": "low — conservative change, easy to revert"
    },
    {
      "id": "adj-20260301-002",
      "type": "prompt",
      "target": "skeptic_agent",
      "change": "Add explicit instruction to check IB range vs day type claim",
      "expected_impact": "Skeptic catches narrow-IB misclassification",
      "risk": "low"
    }
  ]
}
```

Storage: `gs://rockit-data/reflection/journals/{date}.json`

---

## Layer 3: Multi-Day Meta-Review (Opus 4.6 — Every 1–3 Days)

This is the "senior partner" review. Opus 4.6 reads the accumulated reflection journals and proposes structural changes. Runs as a scheduled job or triggered when patterns accumulate.

### Trigger Conditions

```yaml
# configs/meta_review.yaml
meta_review:
  schedule: "every_3_days"
  early_triggers:
    - condition: "day_type_accuracy < 0.5 for 2 consecutive days"
    - condition: "overall_win_rate drops > 10% from 20-day average"
    - condition: "3+ adjustment_proposals accumulated without review"
    - condition: "new regime detected (VIX spike, volume shift)"
```

### What Opus 4.6 Does

```
Input to Opus 4.6:
  1. Last 3-5 daily reflection journals
  2. Agent scorecards (rolling 20-day window)
  3. Current prompt versions for all agents
  4. Current parameter configs
  5. Recent backtest results
  6. Adjustment proposals from Qwen3.5 (pending review)

Opus 4.6 outputs:
  1. APPROVED adjustments (from Qwen3.5 proposals)
  2. NEW adjustments Opus identifies
  3. A/B test designs for uncertain changes
  4. Prompt rewrites (full new versions)
  5. Code change suggestions (deterministic calc improvements)
```

### A/B Testing Framework

```python
# packages/rockit-pipeline/src/rockit_pipeline/reflection/ab_test.py

@dataclass
class ABTest:
    test_id: str                     # "ab-20260301-skeptic-ib-check"
    hypothesis: str                  # "Adding IB range check to skeptic reduces false signals"
    variant_a: str                   # "current skeptic prompt"
    variant_b: str                   # "skeptic prompt with IB range instruction"
    metric: str                      # "day_type_accuracy"
    target_improvement: float        # 0.10 (10% improvement)
    min_sample_size: int             # 20 trading sessions
    allocation: float                # 0.5 (50/50 split — alternate days)
    start_date: str
    status: str                      # "running" / "concluded" / "rolled_back"

    # Results (filled in as test runs)
    sessions_a: int = 0
    sessions_b: int = 0
    metric_a: float = 0.0
    metric_b: float = 0.0
    p_value: float = 1.0
    winner: str = "pending"          # "a" / "b" / "inconclusive"
```

A/B tests alternate between variants by day (not within a day — consistency matters for trading).

---

## Layer 4: Version Control for Agent Behavior

Every piece of agent behavior is versioned — prompts, parameters, configs. Changes live in git branches until validated.

### What Gets Versioned

```
configs/
├── agents/
│   ├── prompts/
│   │   ├── advocate_v12.txt         # Advocate system prompt
│   │   ├── skeptic_v08.txt          # Skeptic system prompt
│   │   ├── orchestrator_v05.txt     # Orchestrator system prompt
│   │   └── prompt_changelog.yaml    # What changed and why
│   ├── parameters/
│   │   ├── strategy_params_v03.yaml # Confidence thresholds, IB gates, etc.
│   │   ├── filter_params_v02.yaml   # Filter thresholds
│   │   └── param_changelog.yaml
│   └── ab_tests/
│       ├── active/                  # Currently running tests
│       └── archive/                 # Concluded tests with results
```

### Git Branch Strategy for Self-Modifications

```
main                               ← Stable, validated agent behavior
  │
  ├── reflect/2026-03-01           ← Daily reflection artifacts (auto-merged)
  ├── reflect/2026-03-02
  │
  ├── adjust/skeptic-ib-check      ← Proposed adjustment (from meta-review)
  │   └── Prompt change + A/B test config
  │
  ├── adjust/bday-threshold-35     ← Parameter tweak
  │   └── strategy_params_v04.yaml
  │
  └── experiment/new-dpoc-weight   ← Larger experiment
      └── Code changes + new tests
```

### Rollback Protocol

```python
# packages/rockit-pipeline/src/rockit_pipeline/reflection/version_manager.py

class AgentVersionManager:
    """Manages prompt/param versions with instant rollback."""

    def get_active_version(self, agent_id: str) -> AgentConfig:
        """Returns current active prompt + params for an agent."""
        ...

    def promote(self, agent_id: str, version: str, reason: str):
        """Promote a new version to active. Logs reason."""
        ...

    def rollback(self, agent_id: str, reason: str):
        """Instant rollback to previous version."""
        # Triggered automatically if:
        # - Win rate drops > 15% within 3 sessions after a change
        # - Any single session loss exceeds 2x historical average
        ...

    def get_history(self, agent_id: str) -> list[VersionEntry]:
        """Full history of what ran when and why."""
        ...
```

### Auto-Rollback Guards

```yaml
# configs/safety.yaml
auto_rollback:
  enabled: true
  triggers:
    - metric: "session_win_rate"
      condition: "< 0.30"
      window: "3 sessions after version change"
      action: "rollback to previous version"

    - metric: "session_pnl"
      condition: "< -2x rolling_20d_avg_loss"
      window: "1 session"
      action: "rollback + pause agent + alert"

    - metric: "day_type_accuracy"
      condition: "< 0.25"
      window: "5 sessions after version change"
      action: "rollback"

  notifications:
    - channel: "dashboard"  # Always
    - channel: "alert"      # On rollback
```

---

## RAG: Yes, But Targeted

Full RAG (vector database over all historical data) is overkill and adds complexity. Instead, use **structured retrieval** — the system knows what it needs and queries it directly.

### What Agents Need to Retrieve

```
┌─────────────────────────────────────────────────────────┐
│                  Retrieval Needs                         │
├────────────────────┬────────────────────────────────────┤
│  Need              │  Solution                          │
├────────────────────┼────────────────────────────────────┤
│  "Last time we saw │  SQL/DuckDB query over outcomes    │
│  this day type     │  table. Structured, fast, exact.   │
│  pattern"          │  No embeddings needed.             │
├────────────────────┼────────────────────────────────────┤
│  "How did this     │  Direct lookup in scorecards.      │
│  strategy perform  │  agent_id + date range → stats.    │
│  last 20 days?"    │  Historian agent already does this.│
├────────────────────┼────────────────────────────────────┤
│  "Similar market   │  DuckDB query: IB range, volume,   │
│  conditions in     │  VIX regime, day type → top-10     │
│  history"          │  most similar sessions.            │
├────────────────────┼────────────────────────────────────┤
│  "What did the     │  Direct file read from             │
│  reflection say    │  reflection/journals/{date}.json   │
│  about this        │                                    │
│  failure mode?"    │                                    │
├────────────────────┼────────────────────────────────────┤
│  "What prompt      │  Git log on configs/agents/prompts │
│  changes were      │  + prompt_changelog.yaml           │
│  made recently?"   │                                    │
└────────────────────┴────────────────────────────────────┘
```

### The Historian Agent (Structured Retrieval, Not RAG)

```python
# packages/rockit-core/src/rockit_core/agents/historian.py

class HistorianAgent:
    """Retrieves historical context via structured queries, not vector search."""

    def __init__(self, db_path: str):
        self.db = duckdb.connect(db_path)

    def similar_sessions(self, current_context: dict, top_k: int = 5) -> list[dict]:
        """Find historically similar sessions by market structure."""
        return self.db.execute("""
            SELECT date, day_type, ib_range, volume_regime, vix_regime,
                   signals_emitted, win_rate, pnl
            FROM session_outcomes
            WHERE ABS(ib_range - ?) < 10
              AND volume_regime = ?
              AND vix_regime = ?
            ORDER BY ABS(ib_range - ?) ASC
            LIMIT ?
        """, [
            current_context["ib_range"],
            current_context["volume_regime"],
            current_context["vix_regime"],
            current_context["ib_range"],
            top_k,
        ]).fetchall()

    def strategy_performance(self, strategy: str, days: int = 20) -> dict:
        """Rolling performance for a strategy."""
        ...

    def recent_reflections(self, days: int = 5) -> list[dict]:
        """Load recent reflection journals for meta-review context."""
        ...

    def failed_patterns(self, strategy: str) -> list[dict]:
        """Recurring failure modes for a strategy from reflection logs."""
        ...
```

### When You DO Want Embeddings (Phase 2)

Later, if you want the model to answer open-ended questions like "why do we keep losing on Wednesdays after Fed days" — that's where a lightweight embedding search over reflection journals adds value. But start with structured queries. Add embeddings only when you hit a question the structured queries can't answer.

```
Phase 1 (now):   DuckDB structured retrieval — covers 90% of needs
Phase 2 (later): Add ChromaDB/pgvector over reflection journals for
                 open-ended pattern discovery
```

---

## Complete Daily Cycle

```
 6:00 AM ET  ─── Pre-Market ──────────────────────────────────
              │  Load overnight context (Asia, London levels)
              │  Historian: fetch similar historical sessions
              │  Load active prompt/param versions
              │  Check for any A/B test — which variant today?

 9:30 AM ET  ─── Market Open ─────────────────────────────────
              │  Deterministic rules run continuously
              │  Strategies emit signals → Advocate/Skeptic debate
              │  Orchestrator builds consensus
              │  All reasoning logged with full context

 4:00 PM ET  ─── Market Close ────────────────────────────────
              │  Final price data collected

 4:15 PM ET  ─── Outcome Logger (Python, no LLM) ────────────
              │  Compute actual outcomes for every signal
              │  Generate per-agent scorecards
              │  Store to outcomes/ and scorecards/

 4:30 PM ET  ─── Daily Reflection (Qwen3.5) ──────────────────
              │  Self-analysis of reasoning quality
              │  Calibration check
              │  Pattern observations
              │  Adjustment proposals (small, specific)
              │  Store to journals/

 5:00 PM ET  ─── Auto-Adjustment (if safe) ───────────────────
              │  Apply "low-risk" parameter tweaks
              │  (Only within pre-approved bounds)
              │  Version bump + changelog entry
              │  Commit to reflect/ branch

 ─── Every 1-3 Days ──────────────────────────────────────────
              │  Meta-Review triggered (Opus 4.6 via API)
              │  Reviews accumulated reflections
              │  Approves/rejects Qwen3.5 proposals
              │  Designs A/B tests for uncertain changes
              │  Proposes prompt rewrites, code changes
              │  All changes on named branches
              │  Human reviews and merges (or auto-merge if
              │  within safety bounds)
```

---

## Self-Modification Boundaries

Not all changes are equal. The system has clear boundaries on what it can change autonomously vs. what requires review.

```
┌──────────────────────────────────────────────────────────────┐
│  AUTONOMOUS (Qwen3.5 can apply after daily reflection)       │
│  ─────────────────────────────────────────────────────────── │
│  • Confidence threshold adjustments (within ±10%)            │
│  • Filter parameter tuning (within pre-set bounds)           │
│  • Agent prompt emphasis shifts (not structural rewrites)    │
│  • A/B test variant selection (following test protocol)      │
│  • Historical context window changes (±5 days)               │
│                                                              │
│  Guard: All changes logged, auto-rollback if metrics drop    │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  REQUIRES OPUS REVIEW (Meta-review proposes, human approves) │
│  ─────────────────────────────────────────────────────────── │
│  • Full prompt rewrites for any agent                        │
│  • New filter rules or filter removal                        │
│  • Strategy enable/disable decisions                         │
│  • Changes to deterministic calculations                     │
│  • New agent roles or removal of agents                      │
│  • Risk parameter changes (position size, max loss)          │
│  • A/B test design and success criteria                      │
│                                                              │
│  Guard: Changes on named branches, require merge approval    │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  NEVER AUTONOMOUS (Human decision only)                      │
│  ─────────────────────────────────────────────────────────── │
│  • Account risk limits ($4K max DD, $400/trade)              │
│  • Instrument selection (which futures to trade)             │
│  • Prop firm rule parameters                                 │
│  • Infrastructure changes (model swap, hardware)             │
│  • Enabling live trading on a new strategy                   │
└──────────────────────────────────────────────────────────────┘
```

---

## Updated Monorepo Structure (New Additions)

```
packages/rockit-pipeline/src/rockit_pipeline/
├── reflection/
│   ├── __init__.py
│   ├── outcome_logger.py        # Post-market outcome computation
│   ├── scorecard.py             # Per-agent daily scorecards
│   ├── daily_reflection.py      # Qwen3.5 self-analysis
│   ├── meta_review.py           # Opus 4.6 multi-day review
│   ├── ab_test.py               # A/B test framework
│   ├── version_manager.py       # Prompt/param version control
│   └── auto_adjust.py           # Safe autonomous adjustments

configs/agents/
├── prompts/
│   ├── advocate_v01.txt
│   ├── skeptic_v01.txt
│   ├── orchestrator_v01.txt
│   └── prompt_changelog.yaml
├── parameters/
│   ├── strategy_params_v01.yaml
│   ├── filter_params_v01.yaml
│   └── param_changelog.yaml
├── ab_tests/
│   ├── active/
│   └── archive/
└── safety.yaml                  # Auto-rollback rules
```
