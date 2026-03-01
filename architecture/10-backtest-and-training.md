# Multi-Agent Backtesting & Training Strategy

## Part 1: 90-Day Multi-Agent Backtest

### The Problem

The current backtest (259 sessions, 283 trades) tests the **deterministic strategy rules only**. It doesn't test the multi-agent system — the Advocate/Skeptic debates, Orchestrator consensus, filter interactions, and self-learning loop. We need to replay the full agent pipeline over historical data to validate the system end-to-end.

### Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                  MULTI-AGENT BACKTEST                          │
│                                                               │
│  Input: 90 days of historical data (OHLCV + volumetric)       │
│                                                               │
│  For each session:                                            │
│    For each time slice (30 per day, every ~13 min):           │
│                                                               │
│    ┌─────────────┐    ┌──────────────┐   ┌───────────────┐   │
│    │ Deterministic│───▶│ Agent Debate  │──▶│ Consensus     │   │
│    │ Rules        │    │ (Advocate/   │   │ (Orchestrator)│   │
│    │ (rockit-core)│    │  Skeptic)    │   │               │   │
│    └─────────────┘    └──────────────┘   └───────┬───────┘   │
│                                                   │           │
│                                          ┌────────▼────────┐ │
│                                          │ Signal + Outcome │ │
│                                          │ Logger           │ │
│                                          └────────┬────────┘ │
│                                                   │           │
│    End of session:                                │           │
│    ┌──────────────┐   ┌───────────────┐          │           │
│    │ Outcome      │◀──┤ Actual prices │          │           │
│    │ Logger       │   │ (historical)  │          │           │
│    └──────┬───────┘   └───────────────┘          │           │
│           │                                       │           │
│    ┌──────▼───────┐                              │           │
│    │ Daily        │   ← Qwen3.5 reflection       │           │
│    │ Reflection   │     runs on backtest day too  │           │
│    └──────┬───────┘                              │           │
│           │                                       │           │
│    Every 3 days:                                  │           │
│    ┌──────▼───────────────┐                      │           │
│    │ Meta-Review          │   ← Simulated Opus    │           │
│    │ (can use Qwen3.5     │     review cycle      │           │
│    │  for cost savings)   │                       │           │
│    └──────────────────────┘                       │           │
│                                                               │
│  Output: Full agent performance over 90 days                  │
│          WITH self-learning loop active                        │
│          Prompt versions evolved during backtest              │
│          Complete debate transcripts for every signal          │
└───────────────────────────────────────────────────────────────┘
```

### Implementation

```python
# packages/rockit-pipeline/src/rockit_pipeline/backtest/agent_backtest.py

class MultiAgentBacktest:
    """Replay the full agent system over historical data."""

    def __init__(
        self,
        data_path: str,
        model_url: str,           # Ollama/vLLM endpoint
        initial_prompts: dict,    # Starting prompt versions
        initial_params: dict,     # Starting parameter versions
        enable_reflection: bool = True,
        enable_meta_review: bool = True,
        meta_review_interval: int = 3,  # days
    ):
        self.orchestrator = AgentOrchestrator(model_url)
        self.reflection = DailyReflection(model_url)
        self.version_manager = AgentVersionManager(initial_prompts, initial_params)
        ...

    def run(self, start_date: str, end_date: str) -> BacktestResult:
        """Run full multi-agent backtest over date range."""
        results = []

        for session_date in trading_days(start_date, end_date):
            # Load historical data for this session
            session_data = self.load_session(session_date)

            # Run through each time slice (simulating real-time)
            session_signals = []
            for time_slice in session_data.time_slices:

                # 1. Deterministic evaluation (fast, no LLM)
                det_signals = self.evaluate_deterministic(time_slice)

                # 2. Agent debate for each candidate signal
                for signal in det_signals:
                    debate = self.orchestrator.debate(
                        signal=signal,
                        context=time_slice,
                        prompts=self.version_manager.get_active_prompts(),
                    )
                    session_signals.append(debate)

            # 3. End of session: compute outcomes
            outcomes = self.compute_outcomes(session_signals, session_data)
            scorecards = self.compute_scorecards(outcomes)
            results.append(outcomes)

            # 4. Daily reflection (if enabled)
            if self.enable_reflection:
                reflection = self.reflection.run(
                    outcomes=outcomes,
                    scorecards=scorecards,
                    recent_history=results[-5:],
                )

                # Apply safe autonomous adjustments
                adjustments = reflection.get("adjustment_proposals", [])
                for adj in adjustments:
                    if self.is_safe_adjustment(adj):
                        self.version_manager.apply(adj)

            # 5. Meta-review (if enabled, every N days)
            if (self.enable_meta_review
                and len(results) % self.meta_review_interval == 0):
                self.run_meta_review(results[-self.meta_review_interval:])

        return BacktestResult(
            results=results,
            version_history=self.version_manager.get_history(),
            final_prompts=self.version_manager.get_active_prompts(),
        )
```

### Backtest Modes

```yaml
# configs/backtest/agent_backtest.yaml
modes:
  # Fast: No LLM, deterministic rules only (existing backtest)
  deterministic_only:
    llm_enabled: false
    reflection_enabled: false
    speed: "~30 seconds for 90 days"

  # Medium: LLM debates but no self-learning
  agent_static:
    llm_enabled: true
    reflection_enabled: false
    meta_review_enabled: false
    speed: "~2-4 hours for 90 days (depends on model speed)"

  # Full: Complete self-learning loop
  agent_adaptive:
    llm_enabled: true
    reflection_enabled: true
    meta_review_enabled: true
    meta_review_interval: 3
    speed: "~4-8 hours for 90 days"

  # Comparison: Run two prompt versions side-by-side
  ab_comparison:
    llm_enabled: true
    variants: ["prompts_v05", "prompts_v06"]
    split: "alternating_days"
    speed: "~6-12 hours for 90 days"
```

### LLM Cost for Backtesting

Running 90 days of multi-agent backtest with local Qwen3.5:

```
Per day:  ~30 time slices × ~2 candidate signals avg × 2 LLM calls (adv+skp)
        = ~120 LLM calls per day
        + 1 reflection call
        + 0.33 meta-review calls
        ≈ 121 calls/day

90 days: ~10,900 LLM calls total
At ~500 tokens per call: ~5.4M tokens
At Qwen3.5 ~50 tok/s: ~30 hours of GPU time

Optimizations:
  - Batch inference via vLLM: ~8-10 hours
  - Skip debates when deterministic confidence > 0.90: ~40% fewer calls
  - Cache identical market contexts: ~10% fewer calls
  - Realistic estimate: 4-8 hours on DGX
```

---

## Part 2: LoRA Training Strategy

### The Question

> Do we need a separate LoRA for the orchestrator? Separate LoRA per agent?
> Or can we use one model for everything?

### Recommendation: One Base Model + One LoRA, Structured Prompts

```
┌─────────────────────────────────────────────────────────┐
│  SINGLE MODEL APPROACH (Recommended)                     │
│                                                          │
│  Base: Qwen3.5-32B                                       │
│  LoRA: One adapter trained on ALL Rockit tasks           │
│                                                          │
│  Task differentiation via system prompts:                │
│                                                          │
│  ┌─────────────────────────────────────────┐            │
│  │  System: "You are the Advocate agent    │            │
│  │  for {strategy}. Your role is to argue  │ ──▶ Advocate│
│  │  FOR this signal based on evidence..."  │   behavior │
│  └─────────────────────────────────────────┘            │
│                                                          │
│  ┌─────────────────────────────────────────┐            │
│  │  System: "You are the Skeptic agent.    │            │
│  │  Your role is to challenge this signal  │ ──▶ Skeptic │
│  │  and identify risks..."                 │   behavior │
│  └─────────────────────────────────────────┘            │
│                                                          │
│  ┌─────────────────────────────────────────┐            │
│  │  System: "You are the Orchestrator.     │            │
│  │  Synthesize advocate and skeptic         │ ──▶ Orch   │
│  │  arguments into a consensus..."         │   behavior │
│  └─────────────────────────────────────────┘            │
│                                                          │
│  Same model, same LoRA, different prompts = different    │
│  behavior. This is how it should work.                   │
└─────────────────────────────────────────────────────────┘
```

### Why NOT Separate LoRAs

| Approach | Pros | Cons |
|----------|------|------|
| **One LoRA (recommended)** | Simple ops, one model to serve, shared market knowledge, prompt-driven specialization | Slightly less specialized per role |
| **Per-agent LoRA** | Maximum specialization | 3-8 adapters to manage, swap at inference time, each needs separate training data, small datasets per agent |
| **Per-strategy LoRA** | Strategy-specific expertise | 16 adapters (!), tiny datasets each, nightmare to manage |

The key insight: **the domain knowledge (market structure, Dalton theory, order flow) is shared across all agents**. What differs is the *reasoning stance* (argue for vs against vs synthesize). That's exactly what system prompts do well. You don't need different weights for different stances — you need the same smart model wearing different hats.

### Training Data: Use Your Existing Dataset

Your existing training data (`{input: deterministic_snapshot, output: ROCKIT_v5.6_analysis}`) is already ideal. The model learns:

1. **Market structure understanding** — how to read IB, volume profile, TPO, order flow
2. **Day type classification** — recognizing Trend, P-Day, B-Day, Neutral patterns
3. **Reasoning about setups** — connecting evidence to conclusions
4. **Structured output** — producing the 11-section analysis format

This knowledge serves ALL agent roles:

```
Existing training data teaches:     Used by:
────────────────────────────        ────────────
Market structure reading        →   All agents
Day type classification         →   All agents
Evidence-based reasoning        →   Advocate, Skeptic, Orchestrator
Confidence calibration          →   Orchestrator
Setup identification            →   Advocate
Risk identification             →   Skeptic
```

### Optional: Add Role-Specific Training Examples (Phase 2)

After the base system works, you can optionally add training examples that demonstrate ideal agent behavior:

```jsonl
{"input": "{snapshot + 'ROLE: ADVOCATE for TrendBull'}", "output": "{structured argument FOR the signal with evidence}"}
{"input": "{snapshot + 'ROLE: SKEPTIC'}", "output": "{structured challenge identifying specific risks}"}
{"input": "{snapshot + 'ROLE: ORCHESTRATOR' + advocate_arg + skeptic_arg}", "output": "{consensus decision with weighted reasoning}"}
```

These can be generated from your existing backtest results + the reflection journals:
- Take a historical signal that was correct → generate ideal Advocate output
- Take a historical signal that failed → generate ideal Skeptic output
- Take the full context → generate ideal Orchestrator consensus

This is a future optimization, not a requirement for launch.

### Training Pipeline (Updated)

```
Phase 1 (Now):
  Existing ROCKIT v5.6 dataset → Single LoRA on Qwen3.5
  → Model understands market structure and analysis
  → Agent behavior via system prompts

Phase 2 (After multi-agent backtest):
  Existing data + Role-specific examples from backtest
  → Same single LoRA, enriched dataset
  → Model gets better at each specific role

Phase 3 (After self-learning loop runs 30+ days):
  Reflection journals identify what the model gets wrong
  → Generate targeted training examples for failure modes
  → Retrain LoRA with focused corrections
  → This is the self-improvement loop paying dividends
```

---

## Part 3: Agentic Framework

### Recommendation: LangGraph

For the Rockit multi-agent system, **LangGraph** is the right fit.

### Why LangGraph

```
┌────────────────────────────────────────────────────────────┐
│  What Rockit Agents Need        │  LangGraph Feature       │
├─────────────────────────────────┼──────────────────────────┤
│  Conditional flow               │  Graph-based routing     │
│  (debate only when needed)      │  with conditional edges  │
│                                 │                          │
│  State that persists across     │  Built-in state mgmt     │
│  agent calls within a session   │  (TypedDict/Pydantic)    │
│                                 │                          │
│  Human-in-the-loop for          │  Breakpoints, interrupt  │
│  meta-review approval           │  nodes, resume           │
│                                 │                          │
│  Streaming debate output        │  Native streaming with   │
│  to dashboard                   │  astream_events          │
│                                 │                          │
│  Works with any LLM backend    │  Provider-agnostic, works│
│  (Ollama, vLLM, Anthropic API) │  with OpenAI-compatible  │
│                                 │                          │
│  Replay/debug agent decisions   │  Full execution trace    │
│  in backtest                    │  with state at each step │
│                                 │                          │
│  Time travel for debugging      │  State checkpointing     │
│  ("what was the state at 10:32")│  and replay              │
└─────────────────────────────────┴──────────────────────────┘
```

### Why NOT Other Frameworks

| Framework | Why Not |
|-----------|---------|
| **CrewAI** | Higher-level abstraction, less control over graph flow. Good for simple role-play, but Rockit needs precise conditional routing (debate only when deterministic confidence < threshold). |
| **AutoGen** | Microsoft's framework. Good for conversational agents, but Rockit agents aren't having open-ended conversations — they follow a strict debate protocol. Over-featured for this use case. |
| **Raw Python** | Could work, but you'd reinvent state management, streaming, checkpointing, and replay. LangGraph gives these for free. |
| **Semantic Kernel** | Microsoft/.NET focused. Python support exists but not primary. |

### Agent Graph Architecture

```python
# packages/rockit-serve/src/rockit_serve/agents/graph.py

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver  # or DuckDB/Postgres
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
    final_signals: Annotated[list[dict], operator.add]  # Accumulates
    debate_log: Annotated[list[dict], operator.add]     # For dashboard


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

    # Entry point
    graph.set_entry_point("evaluate_deterministic")

    # Edges with conditions
    graph.add_conditional_edges(
        "evaluate_deterministic",
        should_debate,
        {
            "debate": "check_historian",   # Confidence < threshold → debate
            "auto_take": "risk_check",     # Confidence > 0.90 → skip debate
            "no_signal": END,              # No signals → done
        },
    )

    graph.add_edge("check_historian", "advocate")
    graph.add_edge("advocate", "skeptic")
    graph.add_edge("skeptic", "orchestrator")

    graph.add_conditional_edges(
        "orchestrator",
        consensus_decision,
        {
            "take": "risk_check",
            "skip": END,
        },
    )

    graph.add_conditional_edges(
        "risk_check",
        risk_approved,
        {
            "approved": "emit_signal",
            "rejected": END,
        },
    )

    graph.add_edge("emit_signal", END)

    return graph.compile(checkpointer=MemorySaver())


def should_debate(state: AgentState) -> str:
    """Route based on deterministic confidence."""
    signals = state["deterministic_signals"]
    if not signals:
        return "no_signal"
    # High confidence → skip expensive LLM debate
    if signals[0]["confidence"] > 0.90:
        return "auto_take"
    return "debate"
```

### Model Integration (Ollama / vLLM)

```python
# packages/rockit-serve/src/rockit_serve/agents/model.py

from langchain_openai import ChatOpenAI

def get_model(tier: str = "local") -> ChatOpenAI:
    """Get the right model for the right task."""
    if tier == "local":
        # Qwen3.5 via Ollama or vLLM (OpenAI-compatible)
        return ChatOpenAI(
            base_url="http://localhost:11434/v1",  # Ollama
            # base_url="http://dgx:8000/v1",       # vLLM on DGX
            model="qwen3.5",
            api_key="not-needed",
            temperature=0.3,
        )
    elif tier == "opus":
        # Opus 4.6 for meta-review (via Anthropic API)
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model="claude-opus-4-6",
            temperature=0.2,
        )
```

### Streaming to Dashboard

```python
# packages/rockit-serve/src/rockit_serve/agents/runner.py

async def run_agent_cycle(time_slice: dict):
    """Run one agent evaluation cycle, streaming to dashboard."""
    graph = build_agent_graph()

    async for event in graph.astream_events(
        {"time_slice": time_slice},
        version="v2",
    ):
        if event["event"] == "on_chat_model_stream":
            # Stream debate tokens to dashboard WebSocket
            await broadcast_to_dashboard({
                "type": "debate_token",
                "agent": event["metadata"].get("agent_role"),
                "token": event["data"]["chunk"].content,
            })
        elif event["event"] == "on_chain_end":
            # Node completed — update dashboard state
            await broadcast_to_dashboard({
                "type": "node_complete",
                "node": event["name"],
                "state": event["data"]["output"],
            })
```

### Updated Package Dependencies

```toml
# packages/rockit-serve/pyproject.toml
[project]
dependencies = [
    "rockit-core",
    "rockit-pipeline",
    "fastapi>=0.110",
    "langgraph>=0.2",
    "langchain-openai>=0.2",
    "langchain-anthropic>=0.2",    # For Opus meta-review
    "duckdb>=1.0",                 # Historian structured retrieval
]
```

---

## Updated Monorepo Additions

```
packages/rockit-serve/src/rockit_serve/
├── agents/
│   ├── __init__.py
│   ├── graph.py                 # LangGraph agent workflow
│   ├── model.py                 # Model provider (Ollama/vLLM/Anthropic)
│   ├── runner.py                # Agent cycle runner with streaming
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── advocate.py          # Advocate node
│   │   ├── skeptic.py           # Skeptic node
│   │   ├── orchestrator.py      # Orchestrator consensus node
│   │   ├── historian.py         # Structured retrieval node
│   │   └── risk_check.py        # Risk validation node
│   └── prompts/
│       ├── advocate.py          # Advocate prompt templates
│       ├── skeptic.py           # Skeptic prompt templates
│       └── orchestrator.py      # Orchestrator prompt templates

packages/rockit-pipeline/src/rockit_pipeline/
├── backtest/
│   ├── agent_backtest.py        # Multi-agent backtester
│   └── replay.py                # Historical replay engine
├── reflection/
│   ├── outcome_logger.py
│   ├── scorecard.py
│   ├── daily_reflection.py
│   ├── meta_review.py
│   ├── ab_test.py
│   ├── version_manager.py
│   └── auto_adjust.py
```
