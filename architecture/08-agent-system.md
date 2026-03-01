# Agent System Architecture

> **Consolidation of:** Self-Learning (old 08), Agent Dashboard (old 09), Multi-Agent Backtest & LoRA (old 10).
> These three documents described the same system from different angles. This document presents
> the unified agent architecture end-to-end.

---

## Architecture Summary

The Rockit agent system has four layers:

```
Layer 1: REAL-TIME INFERENCE (Market Hours)
  Deterministic rules (rockit-core) + LangGraph agent debate + signal emission

Layer 2: POST-MARKET EVALUATION (Daily, 4:15 PM ET)
  Outcome logging + per-agent scorecards + Qwen3.5 daily reflection

Layer 3: META-REVIEW (Every 1-3 Days)
  Opus 4.6 reviews accumulated reflections, proposes structural changes

Layer 4: SELF-IMPROVEMENT LOOP
  A/B testing + version management + auto-rollback + retraining triggers
```

---

## 1. Agent Graph (LangGraph)

Agents are **nodes in a LangGraph graph**, not separate containers. They run as function calls within `rockit-serve`. No inter-service communication needed.

### Architecture Decision: LangGraph over alternatives

| Framework | Why Not |
|-----------|---------|
| **LangGraph** | **Chosen.** Conditional graph routing, state management, streaming, checkpointing, replay. |
| CrewAI | Too high-level; Rockit needs precise conditional routing (debate only when confidence < threshold). |
| AutoGen | Over-featured for strict debate protocol (not open-ended conversation). |
| Raw Python | Would reinvent state mgmt, streaming, checkpointing. |

### Graph Definition

```python
# packages/rockit-serve/src/rockit_serve/agents/graph.py

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Annotated
import operator

class AgentState(TypedDict):
    """State that flows through the agent graph."""
    # Market context
    time_slice: dict                    # Current deterministic snapshot
    session_date: str
    current_time: str

    # Strategy evaluation
    deterministic_signals: list[dict]   # Raw signals from rockit-core
    active_signal: dict | None          # Signal currently being debated

    # Debate
    advocate_argument: str | None
    skeptic_argument: str | None
    historian_context: list[dict]

    # Consensus
    consensus_decision: str | None      # TAKE / SKIP / REDUCE_SIZE
    consensus_confidence: float
    consensus_reasoning: str | None

    # Output
    final_signals: Annotated[list[dict], operator.add]
    debate_log: Annotated[list[dict], operator.add]


def build_agent_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("evaluate_deterministic", evaluate_deterministic)
    graph.add_node("check_historian", check_historian)
    graph.add_node("advocate", run_advocate)
    graph.add_node("skeptic", run_skeptic)
    graph.add_node("orchestrator", run_orchestrator)
    graph.add_node("risk_check", run_risk_check)
    graph.add_node("emit_signal", emit_signal)

    graph.set_entry_point("evaluate_deterministic")

    # High confidence → skip debate, go straight to risk check
    graph.add_conditional_edges(
        "evaluate_deterministic",
        should_debate,
        {
            "debate": "check_historian",
            "auto_take": "risk_check",
            "no_signal": END,
        },
    )

    graph.add_edge("check_historian", "advocate")
    graph.add_edge("advocate", "skeptic")
    graph.add_edge("skeptic", "orchestrator")

    graph.add_conditional_edges(
        "orchestrator",
        consensus_decision,
        {"take": "risk_check", "skip": END},
    )

    graph.add_conditional_edges(
        "risk_check",
        risk_approved,
        {"approved": "emit_signal", "rejected": END},
    )

    graph.add_edge("emit_signal", END)
    return graph.compile(checkpointer=MemorySaver())


def should_debate(state: AgentState) -> str:
    signals = state["deterministic_signals"]
    if not signals:
        return "no_signal"
    if signals[0]["confidence"] > 0.90:
        return "auto_take"
    return "debate"
```

### Agent Nodes

| Node | Role | LLM? |
|------|------|------|
| `evaluate_deterministic` | Run rockit-core strategies, emit candidate signals | No |
| `check_historian` | DuckDB query for similar historical sessions | No |
| `advocate` | Argue FOR the signal with evidence | Yes (Qwen3.5) |
| `skeptic` | Challenge the signal, identify risks | Yes (Qwen3.5) |
| `orchestrator` | Synthesize debate into TAKE/SKIP/REDUCE_SIZE | Yes (Qwen3.5) |
| `risk_check` | Validate position limits, daily loss | No |
| `emit_signal` | Emit final signal to API + dashboard | No |

### Architecture Decision: One Model + One LoRA

All agents share the same Qwen3.5 model with one LoRA adapter. Differentiation is via system prompts, not separate models.

**Why:** Domain knowledge (market structure, Dalton theory, order flow) is shared across all agents. What differs is reasoning stance — argue for vs against vs synthesize. That's exactly what system prompts do well.

| Approach | Verdict |
|----------|---------|
| **One LoRA, prompt-driven** | **Chosen.** Simple ops, shared knowledge, one model to serve. |
| Per-agent LoRA | 3-8 adapters to manage, tiny datasets each, swap at inference. |
| Per-strategy LoRA | 16 adapters — nightmare to manage. |

### Model Integration

```python
from langchain_openai import ChatOpenAI

def get_model(tier: str = "local") -> ChatOpenAI:
    if tier == "local":
        return ChatOpenAI(
            base_url="http://localhost:11434/v1",  # Ollama or vLLM
            model="qwen3.5",
            api_key="not-needed",
            temperature=0.3,
        )
    elif tier == "opus":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-opus-4-6", temperature=0.2)
```

### Streaming to Dashboard

```python
async def run_agent_cycle(time_slice: dict):
    graph = build_agent_graph()
    async for event in graph.astream_events(
        {"time_slice": time_slice}, version="v2",
    ):
        if event["event"] == "on_chat_model_stream":
            await broadcast_to_dashboard({
                "type": "debate_token",
                "agent": event["metadata"].get("agent_role"),
                "token": event["data"]["chunk"].content,
            })
```

---

## 2. Structured Retrieval (Historian Agent)

### Architecture Decision: DuckDB, not vector RAG

Structured SQL queries over DuckDB cover 90% of retrieval needs. Embeddings are Phase 2 only for unstructured text (reflection journals, Dalton theory docs).

| Need | Solution |
|------|----------|
| "Last time we saw this day type pattern" | SQL query over `session_outcomes` |
| "Strategy performance last 20 days" | Direct lookup in `agent_scorecards` |
| "Similar market conditions in history" | DuckDB: IB range + volume regime + VIX → top-10 matches |
| "What did the reflection say about this failure?" | Direct file read from `reflection/journals/` |
| "Recent prompt changes?" | Git log on `configs/agents/prompts/` |

```python
class HistorianAgent:
    """Structured retrieval via DuckDB, not vector search."""

    def __init__(self, db_path: str):
        self.db = duckdb.connect(db_path)

    def similar_sessions(self, current_context: dict, top_k: int = 5) -> list[dict]:
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
```

---

## 3. Post-Market Evaluation (Daily Cycle)

After market close, three things happen automatically:

```
4:15 PM ET  → Outcome Logger (Python, no LLM)
4:30 PM ET  → Daily Reflection (Qwen3.5)
5:00 PM ET  → Auto-Adjustment (safe parameter tweaks only)
```

### 3a. Outcome Logger

Pure Python — computes what actually happened for every signal emitted.

```python
@dataclass
class SignalOutcome:
    # Identity
    date: str
    strategy: str
    agent_id: str
    signal_time: str

    # What the system predicted
    direction: str
    entry_price: float
    stop_price: float
    target_price: float
    confidence: float
    day_type_prediction: str
    advocate_reasoning: str
    skeptic_reasoning: str
    consensus_decision: str       # "TAKE" / "SKIP" / "REDUCE_SIZE"

    # What actually happened
    actual_day_type: str
    max_favorable_excursion: float
    max_adverse_excursion: float
    outcome: str                  # "WIN" / "LOSS" / "SCRATCH" / "NOT_TAKEN"
    pnl: float
    rr_achieved: float

    # Context snapshot (for RAG retrieval later)
    market_context: dict
    filter_results: dict
    order_flow_snapshot: dict
```

### 3b. Per-Agent Scorecards

```python
@dataclass
class AgentScorecard:
    date: str
    agent_id: str
    strategy: str

    # Signal quality
    signals_emitted: int
    signals_taken: int
    signals_hit_target: int
    signals_hit_stop: int

    # Reasoning quality
    day_type_accuracy: float
    advocate_win_rate: float
    skeptic_save_rate: float
    consensus_override_accuracy: float

    # Calibration
    confidence_vs_outcome: list[tuple]  # [(confidence, was_correct), ...]
```

### 3c. Daily Reflection (Qwen3.5)

Structured self-analysis covering:
1. **Accuracy Review** — Which strategies called the day type correctly?
2. **Reasoning Quality** — Was Advocate/Skeptic reasoning sound?
3. **Calibration Check** — Is confidence well-calibrated?
4. **Pattern Observations** — Recurring failure modes, emerging edges
5. **Adjustment Proposals** — Small, specific, testable parameter/prompt tweaks

Output stored as JSON in `gs://rockit-data/reflection/journals/{date}.json`.

---

## 4. Meta-Review (Opus 4.6, Every 1-3 Days)

Triggered on schedule or when:
- `day_type_accuracy < 0.5` for 2 consecutive days
- `win_rate` drops >10% from 20-day average
- 3+ adjustment proposals accumulated without review

### What Opus 4.6 Does

**Input:** Last 3-5 daily reflections, agent scorecards (20-day rolling), current prompts/params, pending adjustment proposals.

**Output:**
- APPROVED adjustments (from Qwen3.5 proposals)
- NEW adjustments Opus identifies
- A/B test designs for uncertain changes
- Prompt rewrites (full new versions)
- Code change suggestions (deterministic calc improvements)

---

## 5. Version Control & Self-Modification Boundaries

### What Gets Versioned

```
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
└── safety.yaml
```

### Self-Modification Tiers

| Tier | Who | What | Guard |
|------|-----|------|-------|
| **AUTONOMOUS** | Qwen3.5 (daily reflection) | Confidence thresholds (within +-10%), filter param tuning (within bounds), prompt emphasis shifts, A/B variant selection | All changes logged, auto-rollback if metrics drop |
| **REQUIRES OPUS REVIEW** | Opus 4.6 meta-review | Full prompt rewrites, new/removed filters, strategy enable/disable, deterministic calc changes, risk parameters, A/B test design | Changes on named branches, require merge approval |
| **NEVER AUTONOMOUS** | Human only | Account risk limits ($4K max DD, $400/trade), instrument selection, prop firm rules, infrastructure changes, enabling live trading | Human decision only |

### Auto-Rollback Guards

```yaml
# configs/safety.yaml
auto_rollback:
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
```

### A/B Testing

Tests alternate between variants by day (not within a day — trading consistency matters).

```python
@dataclass
class ABTest:
    test_id: str
    hypothesis: str
    variant_a: str                   # "current skeptic prompt"
    variant_b: str                   # "skeptic prompt with IB range instruction"
    metric: str                      # "day_type_accuracy"
    target_improvement: float        # 0.10 (10% improvement)
    min_sample_size: int             # 20 trading sessions
    allocation: float                # 0.5 (50/50 split — alternate days)
    start_date: str
    status: str                      # "running" / "concluded" / "rolled_back"
```

---

## 6. Multi-Agent Backtesting

The existing 259-session backtest tests deterministic rules only. The multi-agent backtest replays the **full pipeline** — debates, consensus, self-learning — over historical data.

### Backtest Modes

| Mode | LLM? | Reflection? | Speed (90 days) |
|------|------|-------------|-----------------|
| `deterministic_only` | No | No | ~30 seconds |
| `agent_static` | Yes | No | ~2-4 hours |
| `agent_adaptive` | Yes | Yes | ~4-8 hours |
| `ab_comparison` | Yes | Two variants | ~6-12 hours |

### Implementation

```python
class MultiAgentBacktest:
    def run(self, start_date: str, end_date: str) -> BacktestResult:
        results = []
        for session_date in trading_days(start_date, end_date):
            session_data = self.load_session(session_date)

            # Run through each time slice (simulating real-time)
            session_signals = []
            for time_slice in session_data.time_slices:
                det_signals = self.evaluate_deterministic(time_slice)
                for signal in det_signals:
                    debate = self.orchestrator.debate(
                        signal=signal,
                        context=time_slice,
                        prompts=self.version_manager.get_active_prompts(),
                    )
                    session_signals.append(debate)

            # End of session: compute outcomes
            outcomes = self.compute_outcomes(session_signals, session_data)
            results.append(outcomes)

            # Daily reflection (if enabled)
            if self.enable_reflection:
                reflection = self.reflection.run(
                    outcomes=outcomes,
                    recent_history=results[-5:],
                )
                for adj in reflection.get("adjustment_proposals", []):
                    if self.is_safe_adjustment(adj):
                        self.version_manager.apply(adj)

        return BacktestResult(
            results=results,
            version_history=self.version_manager.get_history(),
        )
```

### LLM Cost Estimate (90 Days)

```
Per day: ~30 time slices x ~2 signals x 2 LLM calls (adv+skp) = ~120 calls
         + 1 reflection + 0.33 meta-review = ~121 calls/day
90 days: ~10,900 calls total (~5.4M tokens)

With optimizations (batch inference, skip high-confidence, cache):
  Realistic: 4-8 hours on DGX with vLLM
```

---

## 7. Agent Monitoring Dashboard

This is the **ops dashboard** for monitoring the agent system — separate from the trading dashboard.

### Dashboard Mock

```
┌──────────────────────────────────────────────────────────────────┐
│  ROCKIT AGENT MONITOR                         2026-03-01 10:32   │
├──────────────────────────────────────────────────────────────────┤
│  SYSTEM STATUS: LIVE          Model: Qwen3.5      Queue: 0      │
│  Day Type: P-Day (72%)        IB: 45pts            CRI: GREEN   │
├───────────────────┬──────────────────────────────────────────────┤
│  ACTIVE AGENTS    │  LIVE DEBATE                                  │
│  ● TrendBull      │  Advocate: "IBH accepted, delta +450..."     │
│  ● EdgeFade       │  Skeptic: "Volume declining, P-shape TPO..." │
│  ○ BDay           │  Orchestrator: TAKE (conf: 0.72)             │
│  ○ PDay           │  Historian: 4/5 similar sessions = P-Day     │
├───────────────────┼──────────────────────────────────────────────┤
│  TODAY'S SIGNALS  │  AGENT HEALTH                                 │
│  10:15 TrendBull  │  LLM: 1.2s avg  |  Det: 8ms  |  API: 45ms  │
│    LONG 21850     │  GPU: 35%        |  Queue: 0  |  Errors: 0  │
│    conf: 0.72     │                                               │
├───────────────────┴──────────────────────────────────────────────┤
│  20-Day Rolling: WR 58% | PF 1.62 | Sharpe 1.8 | MaxDD -$1,200 │
└──────────────────────────────────────────────────────────────────┘
```

### API Endpoints

```
# Live state
WSS  /api/v1/agents/stream              → Push agent state, signals, debates

# Status
GET  /api/v1/agents/status              → All agents with current state
GET  /api/v1/agents/{id}/debates        → Debate transcripts

# Signals
GET  /api/v1/agents/signals?date=       → All signals with outcomes
GET  /api/v1/agents/signals/{id}        → Signal detail with reasoning

# Performance
GET  /api/v1/agents/scorecards?date=    → Daily scorecards
GET  /api/v1/agents/performance?days=   → Rolling performance metrics

# Reflection
GET  /api/v1/agents/reflections?date=   → Daily reflection journal
GET  /api/v1/agents/reflections/proposals → Pending adjustments
GET  /api/v1/agents/ab-tests            → Active A/B tests

# Version management
GET  /api/v1/agents/versions            → Current prompt/param versions
POST /api/v1/agents/versions/{id}/rollback → Manual rollback
```

### Dashboard Pages

1. **Live View** — Agent grid, live debate feed, signal log, system health
2. **Signals & Outcomes** — Every signal with drill-down into reasoning
3. **Performance** — Rolling metrics, confidence calibration, equity curves
4. **Reflection & Learning** — Journals, proposals, A/B test progress, version timeline
5. **Backtest Replay** — Replay agent debates over historical data

---

## 8. DuckDB Storage Schema

```sql
-- All agent data lives in a single DuckDB file
CREATE TABLE deterministic_snapshots (
    date VARCHAR, time VARCHAR, instrument VARCHAR,
    snapshot JSON,  -- Full orchestrator output
    PRIMARY KEY (date, time, instrument)
);

CREATE TABLE signal_outcomes (
    date VARCHAR, signal_time VARCHAR, strategy VARCHAR,
    direction VARCHAR, entry_price DOUBLE, stop_price DOUBLE, target_price DOUBLE,
    confidence DOUBLE, consensus_decision VARCHAR,
    advocate_reasoning TEXT, skeptic_reasoning TEXT,
    actual_day_type VARCHAR, outcome VARCHAR, pnl DOUBLE, rr_achieved DOUBLE,
    market_context JSON, filter_results JSON
);

CREATE TABLE agent_scorecards (
    date VARCHAR, agent_id VARCHAR, strategy VARCHAR,
    signals_emitted INT, signals_taken INT,
    signals_hit_target INT, signals_hit_stop INT,
    day_type_accuracy DOUBLE, advocate_win_rate DOUBLE,
    skeptic_save_rate DOUBLE, confidence_calibration JSON
);

CREATE TABLE version_changes (
    timestamp VARCHAR, agent_id VARCHAR,
    change_type VARCHAR,  -- "prompt" / "parameter" / "rollback"
    old_version VARCHAR, new_version VARCHAR,
    reason TEXT, approved_by VARCHAR
);
```

---

## 9. Complete Daily Cycle

```
 6:00 AM ET  ─── Pre-Market ────────────────────────
              │  Load overnight context (Asia, London)
              │  Historian: fetch similar sessions
              │  Load active prompt/param versions
              │  Check A/B test — which variant today?

 9:30 AM ET  ─── Market Open ───────────────────────
              │  Deterministic rules run continuously
              │  Strategies emit signals → Advocate/Skeptic debate
              │  Orchestrator builds consensus
              │  All reasoning logged with full context

 4:00 PM ET  ─── Market Close ──────────────────────
 4:15 PM ET  ─── Outcome Logger (no LLM) ──────────
 4:30 PM ET  ─── Daily Reflection (Qwen3.5) ────────
 5:00 PM ET  ─── Auto-Adjustment (if safe) ─────────

 Every 1-3 Days ── Meta-Review (Opus 4.6 API) ─────
              │  Reviews reflections → proposes changes
              │  All changes on named branches
```

---

## Monorepo Structure (Agent-Related)

```
packages/rockit-serve/src/rockit_serve/
├── agents/
│   ├── graph.py                 # LangGraph agent workflow
│   ├── model.py                 # Model provider (Ollama/vLLM/Anthropic)
│   ├── runner.py                # Agent cycle runner with streaming
│   └── nodes/
│       ├── advocate.py
│       ├── skeptic.py
│       ├── orchestrator.py
│       ├── historian.py
│       └── risk_check.py

packages/rockit-pipeline/src/rockit_pipeline/
├── reflection/
│   ├── outcome_logger.py        # Post-market outcome computation
│   ├── scorecard.py             # Per-agent daily scorecards
│   ├── daily_reflection.py      # Qwen3.5 self-analysis
│   ├── meta_review.py           # Opus 4.6 multi-day review
│   ├── ab_test.py               # A/B test framework
│   ├── version_manager.py       # Prompt/param version control
│   └── auto_adjust.py           # Safe autonomous adjustments
├── backtest/
│   ├── agent_backtest.py        # Multi-agent backtester
│   └── replay.py                # Historical replay engine

packages/rockit-clients/dashboard/src/pages/agents/
├── index.tsx                    # Live agent monitor
├── signals.tsx                  # Signal log & outcomes
├── performance.tsx              # Rolling performance metrics
├── reflection.tsx               # Reflection & learning view
└── backtest.tsx                 # Multi-agent backtest replay
```
