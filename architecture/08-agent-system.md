# Agent System Architecture

> **Consolidation of:** Self-Learning (old 08), Agent Dashboard (old 09), Multi-Agent Backtest & LoRA (old 10).
> These three documents described the same system from different angles. This document presents
> the unified agent architecture end-to-end.
>
> **Revision 3 — Evidence-Gathering Confluence Model.** Replaces the threshold-gated debate model
> with a full pipeline: specialist observers gather evidence, Advocate and Skeptic debate the
> quality and meaning of that evidence, Pattern Miner provides historical backing, and the
> Orchestrator makes the final call grounded in all three intelligence layers.

---

## Architecture Summary

The Rockit agent system operates on **three intelligence layers** and a **five-stage pipeline**:

### Three Intelligence Layers

```
Layer 0: CERTAINTY (Deterministic — <10ms)
  38 rockit-framework modules → observer agents read snapshot → evidence cards
  Hard conditions. Boolean. "IB accepted above IBH = true."

Layer 1: PROBABILISTIC (Pattern Mining — DuckDB)
  Historical backtest data → statistical patterns
  "Last 12 times we saw this combination, 10 won."

Layer 2: INSTINCT (LLM Debate + Synthesis — Qwen3.5)
  Advocate builds the case from evidence. Skeptic challenges weak evidence.
  Orchestrator weighs both sides + patterns → TAKE / SKIP / REDUCE_SIZE.
```

### Five-Stage Pipeline

```
Stage 1: GATE         → CRI readiness check (deterministic, no LLM)
Stage 2: OBSERVE      → 4 specialist observers gather evidence cards in parallel (no LLM)
Stage 3: MINE         → Pattern Miner queries DuckDB for historical backing (no LLM)
Stage 4: DEBATE       → Advocate builds the case, Skeptic challenges it (LLM)
Stage 5: DECIDE       → Orchestrator makes final TAKE/SKIP/REDUCE_SIZE (LLM)
         RISK CHECK   → Position limits, daily loss gate (no LLM)
         EMIT         → Signal to API + dashboard
```

### Four Operational Cycles

```
REAL-TIME INFERENCE (Market Hours)
  Observe → Mine → Debate → Decide → Emit (per time slice)

POST-MARKET EVALUATION (Daily, 4:15 PM ET)
  Outcome logging + per-agent scorecards + Qwen3.5 daily reflection

META-REVIEW (Every 1-3 Days)
  Opus 4.6 reviews accumulated reflections, proposes structural changes

SELF-IMPROVEMENT LOOP
  A/B testing + version management + auto-rollback + retraining triggers
```

### How This Differs from the Original Debate Model

| Original (Threshold-Gated Debate) | Current (Evidence-Gathering + Debate) |
|---|---|
| Signal fires → confidence threshold gate → debate if uncertain | Observers gather evidence first → debate happens on the evidence |
| Advocate/Skeptic debate a raw signal | Advocate/Skeptic debate which evidence is strong, which is noise |
| Confidence is a threshold you set | Confidence emerges from evidence weight + debate outcome |
| Historian is a lookup step before debate | Pattern Miner actively discovers hidden confluence from backtest data |
| One debate per signal (process `signals[0]`) | Observers report ALL evidence → debate covers the full picture |
| LLM sees raw deterministic data | LLM sees structured evidence cards + statistical patterns |
| 3 LLM calls per signal | 3 LLM calls per time slice, but grounded in richer context |

The key shift: **the debate is no longer about "should we take this signal?" — it's about "what does this evidence mean and is it strong enough to act on?"** The Advocate builds a case from the evidence cards. The Skeptic identifies weak cards, contradictions, and noise. The Orchestrator sees both arguments plus the Pattern Miner's historical backing and makes the final call.

---

## 1. Three Intelligence Layers

### Layer 0: Certainty (Deterministic — Already Built)

The 38 rockit-framework modules produce a rich snapshot every time slice. This is the foundation — pure Python, <10ms, no LLM. The key outputs:

| Module Group | What It Observes | Key Outputs |
|---|---|---|
| `ib_location` | IB structure | IBH, IBL, range, price location, ATR14 |
| `volume_profile` | Volume distribution | POC, VAH, VAL, HVN/LVN nodes (current + prior) |
| `tpo_profile` | Auction quality | Single prints, poor H/L, fattening, TPO shape, naked levels |
| `dpoc_migration` | Intraday momentum | DPOC regime (7 states), velocity, exhaustion, stabilization |
| `fvg_detection` | ICT imbalances | FVGs across 6 timeframes, BPRs, engulfed clusters |
| `premarket` | Overnight context | Asia/London/ON levels, compression flag, SMT divergence |
| `wick_parade` | Trap detection | Bullish/bearish wick counts → trap flags |
| `globex_va_analysis` | 80% rule | Gap status, 3 entry models, trade params |
| `twenty_percent_rule` | IB breakout | 3x close extension trigger |
| `va_edge_fade` | VA edge rejection | Poke count, confirmation method |
| `or_reversal` | Opening range sweep | Judas swing detection, swept levels |
| `edge_fade` | IB edge mean reversion | Edge zone, delta, CVD divergence, FVG confluence |
| `core_confluences` | Boolean signals | IB acceptance, DPOC position, compression, migration |
| `cri` | Readiness gate | STAND_DOWN/PROBE_ONLY/READY, identity, danger flags |
| `inference_engine` | Bias classification | 7-level bias, day type, trend strength, confidence |
| `playbook_engine` | Setup generator | Matched playbook, entry/stop/target prices |

**No changes needed here.** This layer is solid. The observer agents consume its output and translate it into evidence cards.

### Layer 1: Probabilistic (Pattern Mining — NEW)

**This is the key new capability.** The system mines historical data to find statistical patterns that make setups work beyond the explicit conditions.

#### How it works:

1. **Backtest Enrichment (one-time + incremental):** For each of the 259 backtest sessions (and growing), store the FULL deterministic snapshot at signal time alongside the outcome. Every field from every module, tagged with WIN/LOSS/SCRATCH.

2. **Pattern Mining Queries:** When a setup is detected live, query DuckDB for all historical instances of that setup type and analyze what ELSE was true when it worked vs when it failed.

   Example queries:
   ```sql
   -- "When 20P triggered long AND won, what was the DPOC regime?"
   SELECT dpoc_regime, COUNT(*) as n, AVG(pnl) as avg_pnl
   FROM enriched_outcomes
   WHERE setup_type = '20p_long' AND outcome = 'WIN'
   GROUP BY dpoc_regime
   ORDER BY avg_pnl DESC

   -- "When edge_fade fired AND tpo_shape contained 'b_shape', what was the WR?"
   SELECT
     COUNT(*) FILTER (WHERE outcome = 'WIN') * 100.0 / COUNT(*) as win_rate,
     COUNT(*) as n
   FROM enriched_outcomes
   WHERE setup_type = 'edge_fade'
     AND snapshot->'tpo_profile'->>'tpo_shape' LIKE '%b_shape%'

   -- "What hidden factors correlate with 20P wins that aren't in the entry conditions?"
   SELECT
     field_name,
     AVG(CASE WHEN outcome = 'WIN' THEN field_value END) as avg_when_win,
     AVG(CASE WHEN outcome = 'LOSS' THEN field_value END) as avg_when_loss,
     ABS(AVG(CASE WHEN outcome = 'WIN' THEN field_value END) -
         AVG(CASE WHEN outcome = 'LOSS' THEN field_value END)) as separation
   FROM enriched_outcomes_unpivoted
   WHERE setup_type = '20p_long'
   GROUP BY field_name
   ORDER BY separation DESC
   LIMIT 20
   ```

3. **Evidence Cards:** The universal currency of agent communication. Every observation — from any layer — is an evidence card:

   ```python
   @dataclass
   class EvidenceCard:
       source: str           # "observer_profile" | "observer_momentum" | "pattern_miner" |
                             # "advocate" | "skeptic"
       layer: str            # "certainty" | "probabilistic" | "instinct"
       observation: str      # "DPOC regime is trending_on_the_move"
       direction: str        # "bullish" | "bearish" | "neutral"
       strength: float       # 0.0-1.0
       historical_support: str | None  # "8/10 similar sessions were wins (80%)"
       data_points: int      # How many historical data points back this
       admitted: bool | None  # Set by debate stage — None before debate
       raw_data: dict        # The underlying numbers
   ```

   Note the `admitted` field: evidence cards start as observations. During debate, the Advocate argues which cards are strong enough to admit as evidence. The Skeptic challenges weak ones. The Orchestrator sees which cards survived debate.

4. **Confluence Score:** Computed after debate — only admitted cards contribute:

   ```python
   def compute_confluence(cards: list[EvidenceCard]) -> ConfluenceResult:
       admitted = [c for c in cards if c.admitted is True]
       bullish = [c for c in admitted if c.direction == "bullish"]
       bearish = [c for c in admitted if c.direction == "bearish"]

       # Weight by layer: certainty=1.0, probabilistic=0.8, instinct=0.6
       # Weight by historical support: more data points = more weight
       bull_score = sum(
           c.strength * layer_weight(c.layer) * data_weight(c.data_points)
           for c in bullish
       )
       bear_score = sum(
           c.strength * layer_weight(c.layer) * data_weight(c.data_points)
           for c in bearish
       )

       return ConfluenceResult(
           direction="bullish" if bull_score > bear_score else "bearish",
           conviction=abs(bull_score - bear_score) / (bull_score + bear_score + 1e-6),
           total_evidence=len(admitted),
           total_rejected=len([c for c in cards if c.admitted is False]),
           bull_cards=len(bullish),
           bear_cards=len(bearish),
           cards=cards,
       )
   ```

### Layer 2: Instinct (LLM Debate + Synthesis)

The LLM layer has three roles, each with a distinct job:

**Advocate** — Builds the case from evidence:
1. Reviews all evidence cards from observers + pattern miner
2. Identifies the strongest cards and the confluence they form
3. Argues which cards should be admitted and why
4. Connects evidence across domains ("DPOC trending + IB accepted + 3 unfilled FVGs all pointing long")
5. Produces its own instinct-layer evidence cards for soft observations the rules don't capture

**Skeptic** — Challenges the evidence:
1. Identifies weak evidence cards (low strength, few data points, ambiguous direction)
2. Finds contradictions ("20P says long but wick parade shows 6 bearish traps")
3. Argues which cards should be rejected as noise
4. Checks for overconfidence ("pattern miner says 80% but n=5 — not enough data")
5. Produces counter-evidence cards tagged `layer: "instinct"`

**Orchestrator** — Makes the final call:
1. Sees ALL evidence cards (admitted + rejected) with the debate reasoning
2. Sees the pattern miner's historical backing
3. Computes the confluence score from admitted cards
4. Decides: TAKE / SKIP / REDUCE_SIZE
5. Writes the narrative for the dashboard

This is NOT a free-form debate. It's structured:
- Advocate and Skeptic each produce a JSON response with `admit: [card_ids]`, `reject: [card_ids]`, `instinct_cards: [...]`, and `reasoning: "..."`
- The Orchestrator gets both responses + the computed confluence and makes the decision

---

## 2. Agent Graph (LangGraph)

Agents are **nodes in a LangGraph graph**, not separate containers. They run as function calls within `rockit-serve`. No inter-service communication needed.

### Architecture Decision: LangGraph over alternatives

| Framework | Why Not |
|-----------|---------|
| **LangGraph** | **Chosen.** Parallel fan-out for observers, state accumulation for evidence cards, sequential debate chain, conditional routing (CRI gate, confluence threshold), streaming to dashboard, checkpointing for backtest replay. |
| CrewAI | Too high-level; Rockit needs precise fan-out/fan-in control for parallel observers + sequential debate. |
| AutoGen | Over-featured; Rockit debate is structured JSON, not open-ended conversation. |
| Raw Python | Would reinvent state mgmt, parallel fan-out, streaming, checkpointing. |

### Graph State

```python
# packages/rockit-serve/src/rockit_serve/agents/graph.py

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Annotated
import operator

class AgentState(TypedDict):
    """State that flows through the agent graph."""
    # Market context
    time_slice: dict                      # Full deterministic snapshot
    session_date: str
    current_time: str

    # Evidence accumulation (observers + pattern miner append here)
    evidence_cards: Annotated[list[dict], operator.add]

    # Pattern mining results
    historical_matches: list[dict]        # Similar sessions from DuckDB
    hidden_confluence: list[dict]         # Factors that correlate with wins

    # Debate
    advocate_argument: dict | None        # Advocate's structured response
    skeptic_argument: dict | None         # Skeptic's structured response

    # Decision
    confluence_result: dict | None        # Bull/bear score from admitted cards
    consensus_decision: str | None        # TAKE / SKIP / REDUCE_SIZE
    consensus_confidence: float
    consensus_reasoning: str | None
    trade_idea: dict | None              # Entry/stop/target if TAKE
    narrative: str | None                # One-liner for dashboard

    # Output
    final_signals: Annotated[list[dict], operator.add]
    observation_log: Annotated[list[dict], operator.add]
```

### Graph Definition

```python
def build_agent_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Stage 1: Readiness gate (deterministic, no LLM)
    graph.add_node("readiness_gate", check_readiness)

    # Stage 2: Observers (parallel fan-out, no LLM)
    graph.add_node("observe_profile", observe_profile)
    graph.add_node("observe_momentum", observe_momentum)
    graph.add_node("observe_structure", observe_structure)
    graph.add_node("observe_setups", observe_setups)

    # Stage 3: Pattern mining (DuckDB queries, no LLM)
    graph.add_node("mine_patterns", mine_patterns)

    # Stage 4: Debate (LLM — Qwen3.5)
    graph.add_node("advocate", run_advocate)
    graph.add_node("skeptic", run_skeptic)

    # Stage 5: Decision (LLM — Qwen3.5)
    graph.add_node("orchestrator", run_orchestrator)

    # Post-decision
    graph.add_node("risk_check", run_risk_check)
    graph.add_node("emit_signal", emit_signal)

    # === Routing ===

    # Entry: readiness gate
    graph.set_entry_point("readiness_gate")
    graph.add_conditional_edges("readiness_gate", readiness_decision, {
        "stand_down": END,
        "observe": "fan_out_observers",
    })

    # Fan-out: all 4 observers run in parallel
    graph.add_node("fan_out_observers", fan_out)
    graph.add_edge("fan_out_observers", "observe_profile")
    graph.add_edge("fan_out_observers", "observe_momentum")
    graph.add_edge("fan_out_observers", "observe_structure")
    graph.add_edge("fan_out_observers", "observe_setups")

    # Fan-in: all observers complete → mine patterns
    graph.add_edge("observe_profile", "mine_patterns")
    graph.add_edge("observe_momentum", "mine_patterns")
    graph.add_edge("observe_structure", "mine_patterns")
    graph.add_edge("observe_setups", "mine_patterns")

    # Mine → Debate (sequential: advocate then skeptic)
    graph.add_edge("mine_patterns", "advocate")
    graph.add_edge("advocate", "skeptic")

    # Skeptic → Orchestrator
    graph.add_edge("skeptic", "orchestrator")

    # Orchestrator decides
    graph.add_conditional_edges("orchestrator", consensus_decision, {
        "take": "risk_check",
        "reduce_size": "risk_check",
        "skip": END,
    })

    # Risk check gate
    graph.add_conditional_edges("risk_check", risk_approved, {
        "approved": "emit_signal",
        "rejected": END,
    })

    graph.add_edge("emit_signal", END)
    return graph.compile(checkpointer=MemorySaver())
```

### Pipeline Visualization

```
                    ┌──────────────┐
                    │  Readiness   │
                    │  Gate (CRI)  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
              ┌─────│  Fan-Out     │─────┐
              │     └──────────────┘     │
     ┌────────▼──┐ ┌──────▼──┐ ┌──▼────────┐ ┌──▼──────┐
     │  Profile  │ │Momentum │ │ Structure │ │ Setups  │
     │  Observer │ │Observer │ │ Observer  │ │Observer │
     └────────┬──┘ └──────┬──┘ └──┬────────┘ └──┬──────┘
              │           │       │              │
              └─────┬─────┴───────┴──────────────┘
                    │  ~12-25 evidence cards
              ┌─────▼──────────┐
              │ Pattern Miner  │  DuckDB queries
              │ (historical    │  + hidden confluence
              │  backing)      │  + similar sessions
              └─────┬──────────┘
                    │  + probabilistic cards
              ┌─────▼──────────┐
              │   Advocate     │  Builds case from evidence
              │   (Qwen3.5)    │  Admits strong cards
              └─────┬──────────┘
                    │
              ┌─────▼──────────┐
              │   Skeptic      │  Challenges weak evidence
              │   (Qwen3.5)    │  Rejects noise
              └─────┬──────────┘
                    │
              ┌─────▼──────────┐
              │  Orchestrator  │  Weighs debate + patterns
              │  (Qwen3.5)     │  TAKE / SKIP / REDUCE_SIZE
              └─────┬──────────┘
                    │
              ┌─────▼──────────┐
              │  Risk Check    │  Position limits, daily loss
              └─────┬──────────┘
                    │
              ┌─────▼──────────┐
              │  Emit Signal   │  → API + Dashboard
              └────────────────┘
```

### Stage 2: Observer Agents (Deterministic, No LLM)

Each observer reads its slice of the deterministic snapshot and produces evidence cards. These are pure Python — fast, testable, no LLM cost.

| Observer | Reads From Snapshot | Evidence Cards Produced |
|---|---|---|
| **Profile Observer** | `tpo_profile`, `volume_profile`, `core_confluences` | TPO shape, poor H/L, single prints, naked levels, fattening, VAH/VAL/POC positions |
| **Momentum Observer** | `dpoc_migration`, `wick_parade`, `dalton` | DPOC regime, velocity, exhaustion, trap detection, trend confirmation, morph status |
| **Structure Observer** | `fvg_detection`, `premarket`, `ninety_min_pd_arrays`, `core_confluences` | Unfilled FVGs, overnight levels, IB acceptance, compression, price location |
| **Setup Observer** | `globex_va_analysis`, `twenty_percent_rule`, `va_edge_fade`, `or_reversal`, `edge_fade`, `mean_reversion_engine`, `playbook_engine` | Active setups with entry/stop/target, confidence, which models triggered |

Each observer produces 3-8 evidence cards per time slice. Total: ~12-25 evidence cards flowing into the Pattern Miner.

### Stage 3: Pattern Miner (DuckDB, No LLM)

The Pattern Miner takes the evidence cards and queries DuckDB to find:

1. **Historical match rate:** "Of the evidence cards pointing bullish, how often did similar combinations lead to wins?"
2. **Hidden confluence:** "What other fields were consistently true when this setup won, that aren't in the setup conditions?"
3. **Similar sessions:** "Top 5 historical sessions with the most similar evidence profile."

Produces additional evidence cards tagged `layer: "probabilistic"` with `historical_support` and `data_points` filled in.

**This is where the system gets smarter over time.** As more sessions are logged, the Pattern Miner has more data to find hidden patterns. The intelligence scales with data.

### Stage 4: Debate (Advocate + Skeptic — Qwen3.5)

The debate is **structured**, not free-form. Both agents receive the same evidence cards + pattern miner results and produce JSON responses.

#### Advocate Prompt

```
You are the Advocate agent in the Rockit trading system.

## Your Role
Build the strongest possible case from the available evidence. You are NOT
blindly bullish or bearish — you argue for whichever direction the evidence
supports. Your job is to identify which evidence cards are strong, connect
them into a coherent thesis, and argue which cards should be admitted.

## Evidence Cards
{evidence_cards_json}

## Pattern Miner Results
{pattern_miner_json}

## Historical Matches
{similar_sessions_json}

## Your Task
1. Which evidence cards are strongest? Why?
2. What confluence do you see across domains?
3. Which cards should be ADMITTED as credible evidence?
4. Add your own instinct-layer observations the rules might have missed.
5. What direction does the evidence support? How strongly?

Output as JSON:
{
  "admit": ["card_id_1", "card_id_2", ...],
  "reject": ["card_id_x", ...],
  "instinct_cards": [
    {
      "observation": "...",
      "direction": "bullish" | "bearish" | "neutral",
      "strength": 0.0-1.0,
      "reasoning": "..."
    }
  ],
  "thesis": "...",           // One paragraph: the case for action
  "direction": "bullish" | "bearish" | "neutral",
  "key_evidence": ["...", "...", "..."]  // Top 3 strongest cards
}
```

#### Skeptic Prompt

```
You are the Skeptic agent in the Rockit trading system.

## Your Role
Challenge the evidence. You are NOT contrarian for its own sake — you ensure
only strong evidence gets admitted. Your job is to find weak cards (low data
backing, ambiguous signals, contradictions), flag overconfidence, and prevent
the system from acting on noise.

## Evidence Cards
{evidence_cards_json}

## Pattern Miner Results
{pattern_miner_json}

## Advocate's Argument
{advocate_argument_json}

## Your Task
1. Which of the Advocate's admitted cards are actually weak? Why?
2. Are there contradictions the Advocate ignored?
3. Is the pattern miner backing statistically meaningful (n >= 10)?
4. Which cards should be REJECTED as noise or insufficiently supported?
5. Add counter-evidence the Advocate may have downplayed.

Output as JSON:
{
  "challenge_admit": ["card_id_1", ...],     // Cards Advocate admitted that you dispute
  "challenge_reject": ["card_id_y", ...],    // Cards Advocate rejected that actually matter
  "reject": ["card_id_a", ...],             // Additional cards to reject
  "instinct_cards": [
    {
      "observation": "...",
      "direction": "bullish" | "bearish" | "neutral",
      "strength": 0.0-1.0,
      "reasoning": "..."
    }
  ],
  "counter_thesis": "...",     // Why the Advocate's case might be wrong
  "warnings": ["...", "..."],  // Specific risks and contradictions
  "confidence_check": "..."    // Is the evidence strong enough to act on?
}
```

### Stage 5: Orchestrator (Decision — Qwen3.5)

The Orchestrator sees everything: all evidence cards, both debate arguments, the pattern miner results, and the computed confluence score (from cards both sides agreed to admit). It makes the final call.

#### Orchestrator Prompt

```
You are the Orchestrator agent in the Rockit trading system.

## Your Role
Make the final trading decision. You've seen the evidence, heard both sides
of the debate, and have historical backing. Your decision must be grounded —
cite specific evidence cards and debate points in your reasoning.

## All Evidence Cards
{evidence_cards_json}

## Pattern Miner Results
{pattern_miner_json}

## Advocate's Case
{advocate_argument_json}

## Skeptic's Challenge
{skeptic_argument_json}

## Confluence Score (from agreed-upon cards)
{confluence_result_json}

## Your Task
1. Resolve the debate: which disputed cards do you admit or reject?
2. Compute your final assessment of the evidence.
3. Make your decision: TAKE, SKIP, or REDUCE_SIZE.
4. If TAKE or REDUCE_SIZE: specify direction, setup, entry/stop/target.
5. Write a one-liner narrative for the dashboard.

Output as JSON:
{
  "final_admitted": ["card_id_1", ...],
  "final_rejected": ["card_id_x", ...],
  "decision": "TAKE" | "SKIP" | "REDUCE_SIZE",
  "confidence": 0.0-1.0,
  "trade_idea": {                   // null if SKIP
    "direction": "long" | "short",
    "setup_name": "...",
    "entry": float, "stop": float, "target": float,
    "rationale": "...",
    "confluence_count": int,
    "historical_win_rate": float,
    "key_evidence": ["...", "..."]
  },
  "narrative": "...",
  "reasoning": "..."              // Why this decision, citing evidence + debate
}
```

### How Multiple Strategies Are Handled

1. **Setup Observer** reports ALL active setups as evidence cards (20P long, edge_fade long, VA edge fade short, etc.)
2. **Pattern Miner** checks each setup's historical performance with the current evidence profile
3. **Advocate** sees all setups as evidence and builds a case for the strongest confluence direction
4. **Skeptic** challenges — are conflicting setups a warning sign? Is one setup noise?
5. **Orchestrator** picks the strongest confluence or notes conflicting setups as reason to SKIP
6. If two setups point the same direction with strong confluence → higher conviction
7. If setups conflict → the debate surfaces this, Orchestrator may SKIP or REDUCE_SIZE

### Architecture Decision: One Model + One LoRA

All three LLM agents (Advocate, Skeptic, Orchestrator) share the same Qwen3.5 model with one LoRA adapter. Role differentiation is via system prompts, not separate models.

**Why:** Domain knowledge (market structure, Dalton theory, order flow) is shared across all agents. What differs is reasoning stance — build case vs challenge vs decide. That's exactly what system prompts do well.

| Approach | Verdict |
|----------|---------|
| **One LoRA, prompt-driven roles** | **Chosen.** Shared knowledge, one model to serve, role differentiation via prompts. |
| Per-agent LoRA | 3 adapters to manage, tiny datasets each, swap at inference. |
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
        if event["event"] == "on_chain_end":
            node = event["metadata"].get("langgraph_node")
            if node and node.startswith("observe_"):
                await broadcast_to_dashboard({
                    "type": "evidence_card",
                    "observer": node,
                    "cards": event["data"]["output"].get("evidence_cards", []),
                })
            elif node == "mine_patterns":
                await broadcast_to_dashboard({
                    "type": "pattern_results",
                    "historical_matches": event["data"]["output"].get("historical_matches", []),
                })
        elif event["event"] == "on_chat_model_stream":
            agent_role = event["metadata"].get("agent_role")
            await broadcast_to_dashboard({
                "type": "debate_token",
                "agent": agent_role,  # "advocate" | "skeptic" | "orchestrator"
                "token": event["data"]["chunk"].content,
            })
```

---

## 3. Structured Retrieval & Pattern Mining (DuckDB)

### Architecture Decision: DuckDB, not vector RAG

Structured SQL queries over DuckDB cover 90% of retrieval needs. The Pattern Miner uses DuckDB for statistical pattern discovery — not just lookup but active mining. Embeddings are Phase 2 only for unstructured text (reflection journals, Dalton theory docs).

| Need | Solution |
|------|----------|
| "Historical match rate for this setup + evidence combo" | SQL query over `enriched_outcomes` |
| "Hidden confluence factors for 20P wins" | Pre-computed `hidden_confluence` table |
| "Top 5 similar sessions to today" | DuckDB: evidence card similarity scoring |
| "Strategy performance last 20 days" | Direct lookup in `agent_scorecards` |
| "What did the reflection say about this failure?" | Direct file read from `reflection/journals/` |
| "Recent prompt changes?" | Git log on `configs/agents/prompts/` |

### Backtest Intelligence Mining

#### Phase 1: Enrich Historical Data

For each of the 259 backtest sessions (and growing), regenerate the full deterministic snapshot at signal time and store it in DuckDB alongside the outcome:

```sql
CREATE TABLE enriched_outcomes (
    date VARCHAR,
    signal_time VARCHAR,
    setup_type VARCHAR,
    direction VARCHAR,
    outcome VARCHAR,           -- WIN / LOSS / SCRATCH
    pnl DOUBLE,
    rr_achieved DOUBLE,

    -- Full snapshot at signal time (JSON)
    snapshot JSON,

    -- Pre-computed evidence cards (JSON array)
    evidence_cards JSON,

    -- Specific fields extracted for fast querying
    dpoc_regime VARCHAR,
    tpo_shape VARCHAR,
    ib_range DOUBLE,
    wick_parade_bull INT,
    wick_parade_bear INT,
    cri_status VARCHAR,
    price_vs_ib VARCHAR,
    compression_bias VARCHAR,
    trend_strength VARCHAR,
    fvg_count_bullish INT,
    fvg_count_bearish INT,
    naked_levels_count INT,
    -- ... more extracted fields
);
```

#### Phase 2: Discovery Queries (Run Once, Cache Results)

Pre-compute "hidden confluence" patterns:

```sql
-- For each setup type, find which snapshot fields have the highest
-- separation between wins and losses
CREATE TABLE hidden_confluence AS
SELECT
    setup_type,
    field_name,
    AVG(CASE WHEN outcome = 'WIN' THEN field_value END) as avg_win,
    AVG(CASE WHEN outcome = 'LOSS' THEN field_value END) as avg_loss,
    COUNT(*) FILTER (WHERE outcome = 'WIN') as win_count,
    COUNT(*) FILTER (WHERE outcome = 'LOSS') as loss_count,
    ABS(avg_win - avg_loss) / NULLIF(STDDEV(field_value), 0) as effect_size
FROM enriched_outcomes_unpivoted
GROUP BY setup_type, field_name
HAVING COUNT(*) >= 10  -- minimum sample
ORDER BY effect_size DESC;
```

This discovers things like: "When 20P triggers long, wins have avg DPOC velocity of 4.2 pts/30min but losses have 1.1 — DPOC velocity is a hidden confluence factor for 20P."

#### Phase 3: Continuous Learning

Every new live session gets enriched and added to DuckDB. The Pattern Miner's queries get better as data grows. No retraining needed — it's pure SQL.

### How the Three Layers Map to Evidence

| Layer | Implementation | Example |
|---|---|---|
| **Certainty** | 38 deterministic modules → observer agents read snapshot | "IB acceptance above IBH = true" (boolean, instant) |
| **Probabilistic** | Pattern Miner DuckDB queries on enriched backtest data | "Last 8 times 20P fired with trending DPOC regime: 7 wins (87.5%)" |
| **Instinct** | Advocate/Skeptic debate + Orchestrator synthesis | "The 20P triggered but wick parade shows 6 bearish wicks — buyers are getting trapped. Skeptic's counter-evidence outweighs. SKIP." |

---

## 4. Post-Market Evaluation (Daily Cycle)

After market close, three things happen automatically:

```
4:15 PM ET  → Outcome Logger (Python, no LLM)
4:30 PM ET  → Daily Reflection (Qwen3.5)
5:00 PM ET  → Auto-Adjustment (safe parameter tweaks only)
```

### 4a. Outcome Logger

Pure Python — computes what actually happened for every signal emitted. The outcome record includes the full evidence card set, debate arguments, and Orchestrator decision.

```python
@dataclass
class SignalOutcome:
    # Identity
    date: str
    strategy: str
    signal_time: str

    # What the system predicted
    direction: str
    entry_price: float
    stop_price: float
    target_price: float

    # Evidence context
    evidence_cards: list[dict]          # All cards (admitted + rejected)
    confluence_result: dict             # Bull/bear score from admitted cards
    advocate_argument: dict             # Advocate's structured response
    skeptic_argument: dict              # Skeptic's structured response
    consensus_decision: str             # TAKE / SKIP / REDUCE_SIZE
    consensus_confidence: float
    consensus_reasoning: str            # Orchestrator's reasoning
    narrative: str                      # Dashboard one-liner

    # What actually happened
    actual_day_type: str
    max_favorable_excursion: float
    max_adverse_excursion: float
    outcome: str                  # "WIN" / "LOSS" / "SCRATCH" / "NOT_TAKEN"
    pnl: float
    rr_achieved: float

    # Full snapshot for enrichment
    snapshot: dict
```

### 4b. Per-Agent Scorecards

Scorecards track observer accuracy, debate quality, and confluence calibration:

```python
@dataclass
class AgentScorecard:
    date: str

    # Signal quality
    signals_emitted: int
    signals_taken: int
    signals_hit_target: int
    signals_hit_stop: int

    # Observer accuracy
    observer_accuracy: dict           # Per-observer: how often their cards were correct
    most_predictive_observer: str     # Which observer had highest signal-to-noise

    # Debate quality
    advocate_admit_accuracy: float    # Were admitted cards actually predictive?
    skeptic_reject_accuracy: float    # Were rejected cards actually noise?
    orchestrator_override_accuracy: float  # When Orchestrator overrode debate, was it right?

    # Confluence calibration
    confluence_vs_outcome: list[tuple]  # [(conviction_score, was_correct), ...]
    avg_evidence_cards_on_wins: float
    avg_evidence_cards_on_losses: float

    # Pattern miner value
    pattern_miner_hit_rate: float     # When miner said "historically 80%+", was it right?
    hidden_confluence_accuracy: float  # Did identified hidden factors predict outcomes?
```

### 4c. Daily Reflection (Qwen3.5)

Structured self-analysis covering:
1. **Accuracy Review** — Which observers produced the strongest signals?
2. **Debate Quality** — Was the Advocate/Skeptic debate sound? Did the Orchestrator weigh both sides?
3. **Calibration Check** — Is confluence score well-calibrated?
4. **Pattern Observations** — Which evidence combinations are emerging as reliable?
5. **Adjustment Proposals** — Observer weight tweaks, prompt emphasis shifts, pattern miner config

Output stored as JSON in `gs://rockit-data/reflection/journals/{date}.json`.

---

## 5. Meta-Review (Opus 4.6, Every 1-3 Days)

Triggered on schedule or when:
- `confluence_calibration` error exceeds 15% for 2 consecutive days
- `win_rate` drops >10% from 20-day average
- 3+ adjustment proposals accumulated without review

### What Opus 4.6 Does

**Input:** Last 3-5 daily reflections, agent scorecards (20-day rolling), current prompts (advocate, skeptic, orchestrator), observer configs, pending adjustment proposals.

**Output:**
- APPROVED adjustments (from Qwen3.5 proposals)
- NEW adjustments Opus identifies
- A/B test designs for uncertain changes
- Prompt rewrites (full new versions for any agent role)
- Observer weight changes
- Code change suggestions (deterministic calc improvements)

---

## 6. Version Control & Self-Modification Boundaries

### What Gets Versioned

```
configs/agents/
├── prompts/
│   ├── advocate_v01.txt
│   ├── skeptic_v01.txt
│   ├── orchestrator_v01.txt
│   └── prompt_changelog.yaml
├── parameters/
│   ├── observer_weights_v01.yaml     # Per-observer, per-layer weights
│   ├── confluence_thresholds_v01.yaml
│   ├── pattern_miner_config_v01.yaml
│   └── param_changelog.yaml
├── ab_tests/
│   ├── active/
│   └── archive/
└── safety.yaml
```

### Self-Modification Tiers

| Tier | Who | What | Guard |
|------|-----|------|-------|
| **AUTONOMOUS** | Qwen3.5 (daily reflection) | Observer weights (within +-15%), confluence threshold tuning (within bounds), prompt emphasis shifts (no structural rewrite), A/B variant selection | All changes logged, auto-rollback if metrics drop |
| **REQUIRES OPUS REVIEW** | Opus 4.6 meta-review | Full prompt rewrites (advocate, skeptic, orchestrator), new/removed observers, observer logic changes, pattern miner query changes, risk parameters, A/B test design | Changes on named branches, require merge approval |
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
    - metric: "confluence_calibration_error"
      condition: "> 0.25"
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
    variant_b: str                   # "skeptic prompt with IB range emphasis"
    metric: str                      # "skeptic_reject_accuracy"
    target_improvement: float        # 0.10 (10% improvement)
    min_sample_size: int             # 20 trading sessions
    allocation: float                # 0.5 (50/50 split — alternate days)
    start_date: str
    status: str                      # "running" / "concluded" / "rolled_back"
```

---

## 7. Multi-Agent Backtesting

The existing 259-session backtest tests deterministic rules only. The multi-agent backtest replays the **full pipeline** — evidence gathering, debate, decision, self-learning — over historical data.

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
                # Run the full evidence → debate → decide pipeline
                graph_result = self.agent_graph.invoke({
                    "time_slice": time_slice,
                    "session_date": session_date,
                    "current_time": time_slice["time"],
                })
                if graph_result.get("consensus_decision") in ("TAKE", "REDUCE_SIZE"):
                    session_signals.append(graph_result)

            # End of session: compute outcomes
            outcomes = self.compute_outcomes(session_signals, session_data)
            results.append(outcomes)

            # Enrich DuckDB with this session's outcomes
            self.enrich_outcomes(outcomes, session_data)

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
Per day: ~30 time slices x ~2 signals x 3 LLM calls (adv+skp+orch) = ~180 calls
         + 1 reflection + 0.33 meta-review = ~181 calls/day
90 days: ~16,300 calls total (~8.2M tokens)

With optimizations (skip when CRI=STAND_DOWN, skip when no setups active,
  batch inference, cache pattern miner):
  Realistic: 4-8 hours on DGX with vLLM
```

---

## 8. Agent Monitoring Dashboard

This is the **ops dashboard** for monitoring the agent system — separate from the trading dashboard.

### Dashboard Mock

```
┌──────────────────────────────────────────────────────────────────┐
│  ROCKIT AGENT MONITOR                         2026-03-01 10:32   │
├──────────────────────────────────────────────────────────────────┤
│  SYSTEM STATUS: LIVE          Model: Qwen3.5      Queue: 0      │
│  Day Type: P-Day (72%)        IB: 45pts            CRI: GREEN   │
├───────────────────┬──────────────────────────────────────────────┤
│  EVIDENCE CARDS   │  LIVE DEBATE                                  │
│  ● Profile:  5    │  Advocate: "IB accepted, DPOC trending,     │
│  ● Momentum: 4    │   3 unfilled bullish FVGs. 14 cards admitted │
│  ● Structure:3    │   — strong trend continuation case."          │
│  ● Setups:   2    │  Skeptic: "Wick parade bear count = 4.       │
│  ● Miner:    3    │   Rejecting 2 weak structure cards. Buyers    │
│  ─────────────    │   getting trapped at each push."              │
│  Admitted: 12     │  Orchestrator: TAKE (conf: 0.72)             │
│  Rejected: 5      │   "Advocate case holds — trap signal early,   │
│  Disputed: 3      │    trend structure dominant. 20P long."       │
├───────────────────┼──────────────────────────────────────────────┤
│  TODAY'S SIGNALS  │  AGENT HEALTH                                 │
│  10:15 20P Long   │  LLM: 1.2s avg  |  Det: 8ms  |  API: 45ms  │
│    entry: 21850   │  GPU: 35%        |  Queue: 0  |  Errors: 0  │
│    conf: 0.72     │  Pattern Miner: 23ms avg  |  DuckDB: 2ms    │
├───────────────────┴──────────────────────────────────────────────┤
│  20-Day Rolling: WR 58% | PF 1.62 | Sharpe 1.8 | MaxDD -$1,200 │
└──────────────────────────────────────────────────────────────────┘
```

### API Endpoints

```
# Live state
WSS  /api/v1/agents/stream              → Push evidence cards, debate tokens, signals

# Status
GET  /api/v1/agents/status              → All agents with current state
GET  /api/v1/agents/{id}/evidence       → Evidence cards for current time slice
GET  /api/v1/agents/{id}/debates        → Debate transcripts (advocate + skeptic + orchestrator)

# Signals
GET  /api/v1/agents/signals?date=       → All signals with outcomes
GET  /api/v1/agents/signals/{id}        → Signal detail with evidence + debate + reasoning

# Performance
GET  /api/v1/agents/scorecards?date=    → Daily scorecards
GET  /api/v1/agents/performance?days=   → Rolling performance metrics

# Confluence
GET  /api/v1/agents/confluence          → Current confluence state (live)
GET  /api/v1/agents/patterns?setup=     → Pattern miner results for a setup

# Reflection
GET  /api/v1/agents/reflections?date=   → Daily reflection journal
GET  /api/v1/agents/reflections/proposals → Pending adjustments
GET  /api/v1/agents/ab-tests            → Active A/B tests

# Version management
GET  /api/v1/agents/versions            → Current prompt/param versions
POST /api/v1/agents/versions/{id}/rollback → Manual rollback
```

### Dashboard Pages

1. **Live View** — Evidence card grid, live debate feed, signal log, system health
2. **Signals & Outcomes** — Every signal with drill-down into evidence cards, debate, and reasoning
3. **Performance** — Rolling metrics, confluence calibration, debate quality, equity curves
4. **Patterns** — Pattern miner discoveries, hidden confluence factors, historical match browser
5. **Reflection & Learning** — Journals, proposals, A/B test progress, version timeline
6. **Backtest Replay** — Replay full evidence + debate pipeline over historical data

---

## 9. DuckDB Storage Schema

```sql
-- All agent data lives in a single DuckDB file

-- Full deterministic snapshots (unchanged)
CREATE TABLE deterministic_snapshots (
    date VARCHAR, time VARCHAR, instrument VARCHAR,
    snapshot JSON,  -- Full orchestrator output
    PRIMARY KEY (date, time, instrument)
);

-- Enriched outcomes for pattern mining (NEW)
CREATE TABLE enriched_outcomes (
    date VARCHAR,
    signal_time VARCHAR,
    setup_type VARCHAR,
    direction VARCHAR,
    outcome VARCHAR,           -- WIN / LOSS / SCRATCH
    pnl DOUBLE,
    rr_achieved DOUBLE,
    snapshot JSON,             -- Full snapshot at signal time
    evidence_cards JSON,       -- Pre-computed evidence cards
    -- Extracted fields for fast querying
    dpoc_regime VARCHAR,
    tpo_shape VARCHAR,
    ib_range DOUBLE,
    wick_parade_bull INT,
    wick_parade_bear INT,
    cri_status VARCHAR,
    price_vs_ib VARCHAR,
    compression_bias VARCHAR,
    trend_strength VARCHAR,
    fvg_count_bullish INT,
    fvg_count_bearish INT,
    naked_levels_count INT
);

-- Pre-computed hidden confluence patterns (NEW)
CREATE TABLE hidden_confluence (
    setup_type VARCHAR,
    field_name VARCHAR,
    avg_win DOUBLE,
    avg_loss DOUBLE,
    win_count INT,
    loss_count INT,
    effect_size DOUBLE
);

-- Signal outcomes with evidence + debate context (UPDATED)
CREATE TABLE signal_outcomes (
    date VARCHAR, signal_time VARCHAR, setup_type VARCHAR,
    direction VARCHAR, entry_price DOUBLE, stop_price DOUBLE, target_price DOUBLE,
    confluence_conviction DOUBLE, confluence_direction VARCHAR,
    evidence_card_count INT, admitted_count INT, rejected_count INT,
    advocate_reasoning TEXT, skeptic_reasoning TEXT,
    consensus_decision VARCHAR,        -- TAKE / SKIP / REDUCE_SIZE
    consensus_confidence DOUBLE,
    consensus_reasoning TEXT,
    narrative TEXT,
    actual_day_type VARCHAR, outcome VARCHAR, pnl DOUBLE, rr_achieved DOUBLE,
    market_context JSON
);

-- Agent scorecards (UPDATED for evidence + debate model)
CREATE TABLE agent_scorecards (
    date VARCHAR,
    signals_emitted INT, signals_taken INT,
    signals_hit_target INT, signals_hit_stop INT,
    observer_accuracy JSON,
    most_predictive_observer VARCHAR,
    advocate_admit_accuracy DOUBLE,
    skeptic_reject_accuracy DOUBLE,
    orchestrator_override_accuracy DOUBLE,
    confluence_calibration JSON,
    pattern_miner_hit_rate DOUBLE,
    hidden_confluence_accuracy DOUBLE
);

-- Version changes (unchanged)
CREATE TABLE version_changes (
    timestamp VARCHAR, component VARCHAR,
    change_type VARCHAR,  -- "prompt" / "parameter" / "rollback"
    old_version VARCHAR, new_version VARCHAR,
    reason TEXT, approved_by VARCHAR
);
```

---

## 10. Complete Daily Cycle

```
 6:00 AM ET  ─── Pre-Market ────────────────────────
              │  Load overnight context (Asia, London)
              │  Pattern Miner: pre-cache similar sessions for likely day types
              │  Load active prompt/param versions (advocate, skeptic, orchestrator)
              │  Check A/B test — which variant today?

 9:30 AM ET  ─── Market Open ───────────────────────
              │  Every time slice:
              │    1. Readiness gate (CRI check)
              │    2. Observers run in parallel (4 observers → evidence cards)
              │    3. Pattern Miner queries DuckDB (statistical patterns)
              │    4. Advocate builds case from evidence (LLM)
              │    5. Skeptic challenges evidence (LLM)
              │    6. Orchestrator decides: TAKE / SKIP / REDUCE_SIZE (LLM)
              │    7. Risk check → emit or reject
              │  Evidence cards + debate + signals streamed to dashboard

 4:00 PM ET  ─── Market Close ──────────────────────
 4:15 PM ET  ─── Outcome Logger (no LLM) ──────────
              │  Enrich outcomes with full snapshot + evidence + debate
 4:30 PM ET  ─── Daily Reflection (Qwen3.5) ────────
              │  Review observer accuracy, debate quality, calibration
 5:00 PM ET  ─── Auto-Adjustment (if safe) ─────────
              │  Observer weight tweaks, prompt emphasis shifts

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
│   ├── evidence.py              # EvidenceCard, ConfluenceResult dataclasses
│   └── nodes/
│       ├── readiness_gate.py    # CRI check (deterministic)
│       ├── observers/
│       │   ├── profile.py       # Profile Observer
│       │   ├── momentum.py      # Momentum Observer
│       │   ├── structure.py     # Structure Observer
│       │   └── setups.py        # Setup Observer
│       ├── pattern_miner.py     # DuckDB pattern mining
│       ├── advocate.py          # Builds case from evidence (LLM)
│       ├── skeptic.py           # Challenges evidence (LLM)
│       ├── orchestrator.py      # Final decision (LLM)
│       ├── risk_check.py        # Position limits, daily loss
│       └── emit.py              # Final signal emission

packages/rockit-pipeline/src/rockit_pipeline/
├── reflection/
│   ├── outcome_logger.py        # Post-market outcome computation + enrichment
│   ├── scorecard.py             # Daily scorecards (observer + debate accuracy)
│   ├── daily_reflection.py      # Qwen3.5 self-analysis
│   ├── meta_review.py           # Opus 4.6 multi-day review
│   ├── ab_test.py               # A/B test framework
│   ├── version_manager.py       # Prompt/param version control
│   └── auto_adjust.py           # Safe autonomous adjustments
├── backtest/
│   ├── agent_backtest.py        # Multi-agent backtester
│   ├── enrichment.py            # Backtest data enrichment for pattern miner
│   └── replay.py                # Historical replay engine

packages/rockit-clients/dashboard/src/pages/agents/
├── index.tsx                    # Live agent monitor (evidence + debate + signals)
├── signals.tsx                  # Signal log & outcomes
├── performance.tsx              # Rolling performance metrics
├── patterns.tsx                 # Pattern miner discoveries & hidden confluence
├── reflection.tsx               # Reflection & learning view
└── backtest.tsx                 # Multi-agent backtest replay
```
