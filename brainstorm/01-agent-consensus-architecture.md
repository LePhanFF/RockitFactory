# ROCKIT Agent Consensus Architecture

## Brainstorm: From Decision Support to Autonomous Agent Trading

**Status**: Brainstorm / RFC
**Date**: 2026-03-01

---

## 1. The Shift

The current RockitFactory proposal treats the system as **decision support** — generate analysis, display it, let the human decide. That's valuable, but it underutilizes what we've built.

We have:
- **259 days** of historical session data with full deterministic analysis
- **~7,500 training examples** (252 days x 30 snapshots) of input/output pairs
- **16 battle-tested strategies** with known win rates and profit factors
- **Fine-tuned models** that understand Dalton Market Profile, ICT, and order flow
- **Real-time data ingestion** generating minute-by-minute snapshots

The question: **What if we stop advising and start acting?**

### New Frame: Multi-Agent Consensus Trading System

Instead of one pipeline producing one analysis for one human, we deploy **specialized agents** that:

1. Each own a strategy (or a cluster of related strategies)
2. Run continuous analysis against real-time AND historical data
3. Debate internally via sub-agents for signal confirmation
4. Report consensus signals to orchestrator agents
5. Orchestrators filter, rank, and optionally **execute trades**

This turns Rockit from a dashboard into an **autonomous trading desk** with human oversight.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HUMAN OVERSIGHT LAYER                        │
│  Dashboard  │  Alert Console  │  Kill Switch  │  P&L Monitor        │
└──────┬──────┴────────┬────────┴───────┬───────┴────────┬────────────┘
       │               │                │                │
       ▼               ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR AGENTS (1-2)                       │
│                                                                     │
│  ┌─────────────────┐              ┌─────────────────┐               │
│  │  Chief Strategist │◄──────────►│  Risk Manager    │              │
│  │  (Consensus Mgr)  │            │  (Position Mgr)  │              │
│  └────────┬─────────┘              └────────┬─────────┘              │
│           │  Aggregated signals              │  Risk gates           │
│           │  + confidence scores             │  + portfolio limits   │
└───────────┼──────────────────────────────────┼──────────────────────┘
            │                                  │
            ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STRATEGY SPECIALIST AGENTS                        │
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │  Trend   │ │  P-Day   │ │  B-Day   │ │  ICT     │ │  Edge    │  │
│  │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │ │  Fade    │  │
│  │          │ │          │ │          │ │          │ │  Agent   │  │
│  │ ┌──────┐ │ │ ┌──────┐ │ │ ┌──────┐ │ │ ┌──────┐ │ │ ┌──────┐ │  │
│  │ │Confirm│ │ │ │Confirm│ │ │ │Confirm│ │ │ │Confirm│ │ │ │Confirm│ │  │
│  │ │Sub-   │ │ │ │Sub-   │ │ │ │Sub-   │ │ │ │Sub-   │ │ │ │Sub-   │ │  │
│  │ │Agents │ │ │ │Agents │ │ │ │Agents │ │ │ │Agents │ │ │ │Agents │ │  │
│  │ └──────┘ │ │ └──────┘ │ │ └──────┘ │ │ └──────┘ │ │ └──────┘ │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                            │
│  │  IB      │ │  OR      │ │  Balance │  ... (up to 16 strategy    │
│  │  Retest  │ │  Reversal│ │  Agent   │      specialists)          │
│  │  Agent   │ │  Agent   │ │          │                            │
│  └──────────┘ └──────────┘ └──────────┘                            │
└─────────────────────────────────────────────────────────────────────┘
            │                                  │
            ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       SHARED DATA & MODELS                          │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────────┐    │
│  │ Real-Time   │  │ Historical  │  │ Model Inference          │    │
│  │ Analysis    │  │ Database    │  │ (Local vLLM on DGX)      │    │
│  │ (Live Feed) │  │ (259 days)  │  │                          │    │
│  └─────────────┘  └─────────────┘  └──────────────────────────┘    │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Minute-by-Minute Store (TimescaleDB / ClickHouse)           │   │
│  │ Every snapshot, every signal, every agent decision — stored  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      EXECUTION LAYER                                │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐    │
│  │ NinjaTrader │  │ Browser     │  │ API Direct              │    │
│  │ API Client  │  │ Automation  │  │ (Broker API)            │    │
│  │             │  │ (Playwright)│  │                         │    │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Agent Hierarchy & Roles

### 3.1 Strategy Specialist Agents

Each specialist owns **one strategy** (or a closely related cluster). It is a persistent process that:

1. **Consumes real-time data** — every minute-by-minute snapshot from the deterministic pipeline
2. **Queries historical context** — "In the 259 stored sessions, when conditions looked like THIS, what happened?"
3. **Runs its strategy logic** — deterministic rules from `rockit-core`
4. **Calls its fine-tuned model** — for nuanced analysis the rules can't capture
5. **Debates via sub-agents** — confirmation/rejection before emitting a signal

#### Strategy Groupings (8 Specialist Agents)

Rather than 16 agents (one per strategy), we group related strategies to reduce overhead and enable internal cross-referencing:

| Agent | Strategies | Focus |
|-------|-----------|-------|
| **Trend Agent** | TrendBull, TrendBear, SuperTrendBull, SuperTrendBear, MorphToTrend | Directional moves, IB extensions |
| **P-Day Agent** | PDayStrategy, PMMorphStrategy | Skewed balance, PM session morphs |
| **B-Day Agent** | BDayStrategy, NeutralDay | Narrow range, balance, IBL fades |
| **ICT Agent** | OpeningRangeReversal, ORAcceptanceStrategy | ICT concepts, Judas Swing, FVG |
| **Edge Fade Agent** | EdgeFadeStrategy, 80% Rule | Mean reversion, VA plays |
| **Sweep Agent** | IBHSweepFail, BearAcceptShort | Failed breakouts, acceptance plays |
| **IB Retest Agent** | IBRetestStrategy, BalanceSignal | Retest entries, consolidation |
| **Cross-Market Agent** | (new) SMT divergence, VIX regime, cross-instrument | Macro context, intermarket |

#### Sub-Agent Debate Protocol

Each specialist has 2-3 **confirmation sub-agents** that play distinct roles:

```
┌─────────────────────────────────────────┐
│          TREND AGENT (Specialist)        │
│                                         │
│  Input: Real-time snapshot + history     │
│                                         │
│  ┌───────────┐  ┌───────────┐           │
│  │ Advocate   │  │ Skeptic   │           │
│  │ Sub-Agent  │  │ Sub-Agent │           │
│  │            │  │           │           │
│  │ "IB ext    │  │ "Volume   │           │
│  │  >1.5x,   │  │  declining,│          │
│  │  DPOC      │  │  prior day│           │
│  │  migrating,│  │  was trend,│          │
│  │  GO LONG"  │  │  reversion│           │
│  │            │  │  risk"    │           │
│  └─────┬─────┘  └─────┬─────┘           │
│        │               │                │
│        ▼               ▼                │
│  ┌──────────────────────────┐           │
│  │  Historian Sub-Agent      │           │
│  │                          │           │
│  │  "In 259 sessions, when  │           │
│  │   IB ext >1.5x + DPOC   │           │
│  │   migration + declining  │           │
│  │   volume: 62% continued, │           │
│  │   38% reversed by PM.    │           │
│  │   Avg P&L: +$420 long"  │           │
│  └─────────┬────────────────┘           │
│            │                            │
│            ▼                            │
│  ┌──────────────────────────┐           │
│  │  CONSENSUS: LONG         │           │
│  │  Confidence: 68%         │           │
│  │  Historical backing: 62% │           │
│  │  Risk flag: volume       │           │
│  └──────────────────────────┘           │
└─────────────────────────────────────────┘
```

**Sub-Agent Roles:**

| Role | Directive | What It Checks |
|------|-----------|----------------|
| **Advocate** | Find reasons TO take the trade | Strategy rules, confluence, model output |
| **Skeptic** | Find reasons NOT to take it | Filters, risk factors, contradicting signals |
| **Historian** | Ground the debate in data | Historical database: "when conditions matched, what happened?" |

The specialist agent synthesizes these three perspectives into a **consensus signal** with:
- Direction (Long / Short / Flat)
- Confidence score (0-100)
- Historical backing (% of similar setups that worked)
- Risk flags (enumerated concerns from Skeptic)
- Key levels (entry, stop, targets from Advocate)

### 3.2 Orchestrator Agents

Two orchestrator agents sit above the specialists:

#### Chief Strategist (Consensus Manager)

Receives signals from all active specialist agents and:

1. **Detects agreement** — If Trend Agent says Long and P-Day Agent confirms P-Day developing, signal is strengthened
2. **Detects conflict** — If ICT Agent says short (Judas Swing) while Trend Agent says long, flag as contested
3. **Weighs by track record** — Weight each specialist's signal by its historical accuracy for current conditions
4. **Produces a portfolio-level recommendation**:
   - Strong consensus (3+ agents agree, >70% avg confidence) → Auto-execute eligible
   - Moderate consensus (2 agents agree, 50-70%) → Alert + recommend
   - Weak/conflicting → Monitor only, alert human
   - Contradiction (agents disagree with high confidence) → Sit out, flag anomaly

```python
# Pseudocode for Chief Strategist consensus logic
class ChiefStrategist:
    def aggregate_signals(self, signals: list[AgentSignal]) -> PortfolioAction:
        # Group by direction
        longs = [s for s in signals if s.direction == "LONG"]
        shorts = [s for s in signals if s.direction == "SHORT"]

        # Weighted confidence (by historical accuracy of each agent)
        long_score = sum(s.confidence * s.agent_accuracy for s in longs)
        short_score = sum(s.confidence * s.agent_accuracy for s in shorts)

        # Consensus threshold
        if long_score > short_score and len(longs) >= 3:
            action = "LONG"
            consensus = "STRONG" if avg_confidence(longs) > 70 else "MODERATE"
        elif short_score > long_score and len(shorts) >= 3:
            action = "SHORT"
            consensus = "STRONG" if avg_confidence(shorts) > 70 else "MODERATE"
        else:
            action = "FLAT"
            consensus = "WEAK"

        return PortfolioAction(
            direction=action,
            consensus_level=consensus,
            contributing_agents=longs if action == "LONG" else shorts,
            dissenting_agents=shorts if action == "LONG" else longs,
            historical_similar_setups=self.query_historical(signals),
            recommended_size=self.size_by_consensus(consensus),
        )
```

#### Risk Manager (Position Manager)

Runs in parallel with Chief Strategist. Independent authority to:

1. **Enforce portfolio limits** — max contracts, max daily loss, max correlated exposure
2. **Gate execution** — even Strong consensus can be blocked by risk rules
3. **Monitor open positions** — trailing stops, partial exits, time-based exits
4. **Circuit breakers** — auto-flatten if daily P&L hits -$X or if 3+ consecutive losers

```
Chief Strategist says: "LONG NQ, 2 contracts, strong consensus"
Risk Manager checks:
  ├── Daily P&L: -$200 (under -$2000 limit) ✓
  ├── Open positions: 0 (under 3 max) ✓
  ├── Correlated exposure: No ES/YM positions ✓
  ├── Time: 10:45 ET (within trading window) ✓
  ├── Consecutive losses: 1 (under 3 circuit breaker) ✓
  └── APPROVED → Execute
```

### 3.3 Execution Modes

The system supports three execution modes (configurable per session):

| Mode | Behavior | Use Case |
|------|----------|----------|
| **Monitor** | Agents run, signals logged, no execution | Paper trading, research |
| **Alert** | Agents run, human gets alerts, human executes | Assisted trading |
| **Auto-Execute** | Agents run, strong consensus auto-executes | Autonomous trading |

---

## 4. Data Architecture

### 4.1 Historical Analysis Database

Store the 259 days of deterministic analysis in a queryable format:

```
┌──────────────────────────────────────────────────────────┐
│              HISTORICAL ANALYSIS DATABASE                  │
│              (PostgreSQL + TimescaleDB)                    │
│                                                           │
│  session_analysis (hypertable, partitioned by date)       │
│  ├── session_date        DATE                             │
│  ├── time_slice          TIMESTAMPTZ                      │
│  ├── instrument          TEXT (NQ, ES, YM)                │
│  ├── deterministic_snap  JSONB (full orchestrator output) │
│  ├── model_analysis      JSONB (ROCKIT v5.6 output)       │
│  ├── day_type            TEXT                             │
│  ├── ib_range            NUMERIC                          │
│  ├── ib_location         TEXT (above/below/inside VA)     │
│  ├── dpoc               NUMERIC                          │
│  ├── volume_profile      JSONB                            │
│  ├── signals_emitted     JSONB[]                          │
│  └── actual_outcome      JSONB (filled post-session)      │
│                                                           │
│  agent_signals (append-only log)                          │
│  ├── timestamp           TIMESTAMPTZ                      │
│  ├── agent_id            TEXT                             │
│  ├── strategy            TEXT                             │
│  ├── signal_type         TEXT (entry/exit/alert)          │
│  ├── direction           TEXT                             │
│  ├── confidence          NUMERIC                          │
│  ├── consensus_detail    JSONB (advocate/skeptic/hist)    │
│  ├── historical_matches  JSONB[] (similar past setups)    │
│  └── orchestrator_action TEXT (approved/rejected/alert)   │
│                                                           │
│  trades (execution log)                                   │
│  ├── trade_id            UUID                             │
│  ├── timestamp           TIMESTAMPTZ                      │
│  ├── agent_signals       UUID[] (which signals triggered) │
│  ├── instrument          TEXT                             │
│  ├── direction           TEXT                             │
│  ├── entry_price         NUMERIC                          │
│  ├── exit_price          NUMERIC                          │
│  ├── pnl                 NUMERIC                          │
│  ├── consensus_at_entry  JSONB                            │
│  └── execution_mode      TEXT (auto/manual)               │
│                                                           │
│  minute_snapshots (high-frequency time series)            │
│  ├── timestamp           TIMESTAMPTZ                      │
│  ├── instrument          TEXT                             │
│  ├── price               NUMERIC                          │
│  ├── volume              BIGINT                           │
│  ├── delta               NUMERIC                          │
│  ├── cvd                 NUMERIC                          │
│  ├── deterministic_snap  JSONB (live orchestrator output) │
│  └── active_signals      JSONB[]                          │
└──────────────────────────────────────────────────────────┘
```

**Why TimescaleDB?**
- Native time-series compression (10-20x for minute data)
- Continuous aggregates for session-level rollups
- Fast `WHERE time > now() - interval '30 minutes'` queries
- PostgreSQL-compatible (agents use normal SQL)
- Hypertable partitioning handles years of minute data

**Storage estimates:**
- 259 historical days x 30 snapshots x ~10KB = ~78 MB (historical)
- Live: ~390 snapshots/day (6.5 hours x 60 min) x ~5KB = ~2 MB/day
- Agent signals: ~50-200/day x ~2KB = ~400 KB/day
- Total Year 1: < 5 GB — trivially small

### 4.2 Real-Time Data Flow

```
NinjaTrader/Data Feed
        │
        ▼ (every 1 min)
┌─────────────────┐
│ rockit-ingest    │ ── CSV/API push ──▶ minute_snapshots table
│ (data collector) │
└────────┬────────┘
         │
         ▼ (every 1 min)
┌─────────────────┐
│ rockit-pipeline  │ ── Deterministic analysis ──▶ session_analysis table
│ (orchestrator)   │
└────────┬────────┘
         │
         ▼ (broadcast)
┌─────────────────────────────────────┐
│ Agent Message Bus (Redis Streams)    │
│                                     │
│ Channel: snapshots.NQ               │
│ Channel: snapshots.ES               │
│ Channel: signals.trend              │
│ Channel: signals.orchestrator       │
│ Channel: execution.orders           │
└─────────────────────────────────────┘
         │
    ┌────┴────┬────────┬────────┬─────────┐
    ▼         ▼        ▼        ▼         ▼
 Trend     P-Day    B-Day    ICT      ... (all specialists)
 Agent     Agent    Agent    Agent
    │         │        │        │
    └────┬────┘────────┘────────┘
         ▼
   Orchestrator Agents
         │
         ▼
   Execution Layer
```

### 4.3 Historical Query Patterns

The Historian sub-agent needs fast access to questions like:

```sql
-- "When IB range was 60-80 ticks and DPOC was above VAH, what happened?"
SELECT day_type, actual_outcome, COUNT(*)
FROM session_analysis
WHERE (deterministic_snap->'intraday'->'ib'->>'range')::numeric BETWEEN 60 AND 80
  AND (deterministic_snap->'intraday'->'volume_profile'->>'poc')::numeric >
      (deterministic_snap->'intraday'->'volume_profile'->>'vah')::numeric
GROUP BY day_type, actual_outcome->>'direction';

-- "Show me the last 5 times Trend Agent fired with >70% confidence"
SELECT * FROM agent_signals
WHERE agent_id = 'trend' AND confidence > 70
ORDER BY timestamp DESC LIMIT 5;

-- "What was the P&L when 3+ agents agreed on LONG?"
SELECT AVG(t.pnl), COUNT(*)
FROM trades t
WHERE jsonb_array_length(t.agent_signals) >= 3
  AND t.direction = 'LONG';
```

For fast pattern matching, we pre-compute **feature vectors** on each session and index them:

```sql
-- Materialized features for similarity search
CREATE TABLE session_features AS
SELECT
    session_date,
    (snap->'intraday'->'ib'->>'range')::numeric AS ib_range,
    snap->>'day_type' AS day_type,
    (snap->'intraday'->'volume_profile'->>'poc')::numeric AS poc,
    (snap->'core_confluences'->'ib_acceptance'->>'score')::numeric AS ib_score,
    -- ... 20+ features
FROM session_analysis
WHERE time_slice = (SELECT MAX(time_slice) FROM session_analysis sa2
                    WHERE sa2.session_date = session_analysis.session_date);

CREATE INDEX idx_features_ib ON session_features(ib_range);
CREATE INDEX idx_features_daytype ON session_features(day_type);
```

---

## 5. Agent Framework & Runtime

### 5.1 Framework Choice: Agent Protocol Agnostic

Rather than locking into one agent framework, we define a **standard agent interface** that any framework can implement:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class AgentSignal:
    agent_id: str
    strategy: str
    direction: str          # LONG | SHORT | FLAT
    confidence: float       # 0-100
    entry_price: float | None
    stop_price: float | None
    target_prices: list[float]
    risk_flags: list[str]
    historical_match_count: int
    historical_win_rate: float
    advocate_reasoning: str
    skeptic_reasoning: str
    historian_summary: str
    timestamp: str
    raw_model_output: dict | None

@dataclass
class Snapshot:
    timestamp: str
    instrument: str
    deterministic: dict     # Full orchestrator output
    model_analysis: dict    # ROCKIT v5.6 output
    price: float
    volume: int
    delta: float

class StrategyAgent(ABC):
    """Base interface for all strategy specialist agents."""

    @abstractmethod
    async def on_snapshot(self, snapshot: Snapshot) -> AgentSignal | None:
        """Process a new market snapshot. Return signal or None."""
        ...

    @abstractmethod
    async def query_history(self, conditions: dict) -> list[dict]:
        """Query historical database for similar conditions."""
        ...

    @abstractmethod
    async def get_status(self) -> dict:
        """Return current agent state for monitoring."""
        ...

class OrchestratorAgent(ABC):
    """Base interface for orchestrator agents."""

    @abstractmethod
    async def on_signal(self, signal: AgentSignal) -> dict:
        """Process incoming signal from a specialist."""
        ...

    @abstractmethod
    async def get_portfolio_state(self) -> dict:
        """Return current portfolio / position state."""
        ...
```

### 5.2 Supported Frameworks

Any of these can implement the `StrategyAgent` / `OrchestratorAgent` interface:

| Framework | Best For | How It Fits |
|-----------|----------|-------------|
| **Claude Code / Claude Agent SDK** | Complex reasoning, debate protocol | Orchestrator + Skeptic sub-agents |
| **OpenCode** | Local-first, code-heavy agents | Strategy specialists with tool use |
| **OpenClaw** | Multi-agent orchestration | Full hierarchy management |
| **LangGraph** | Stateful agent workflows | Sub-agent debate graphs |
| **CrewAI** | Role-based agent teams | Advocate/Skeptic/Historian roles |
| **Custom (lightweight)** | Minimal overhead, max speed | Deterministic strategy agents |

**Recommended hybrid approach:**

```
┌────────────────────────────────────────────────────┐
│  ORCHESTRATOR LAYER                                 │
│  Claude Agent SDK / OpenClaw                        │
│  (needs strong reasoning for consensus decisions)   │
│  Runs on: API call to Claude or local large model   │
└─────────────────────┬──────────────────────────────┘
                      │
┌─────────────────────┼──────────────────────────────┐
│  SPECIALIST LAYER   │                               │
│  Lightweight custom agents                          │
│  (mostly deterministic + model inference calls)     │
│  Runs on: Spark DGX (Qwen 3.5 / local models)      │
│                                                     │
│  Sub-agents (Advocate/Skeptic/Historian):            │
│  - Advocate: deterministic rules + model call        │
│  - Skeptic: deterministic filters + model call       │
│  - Historian: SQL queries (no LLM needed)            │
└─────────────────────────────────────────────────────┘
```

### 5.3 Local Model Strategy (Spark DGX 128GB)

The DGX is the workhorse. With 128GB VRAM, we can run:

| Model | VRAM | Role | Concurrent |
|-------|------|------|------------|
| **Qwen3-32B** (or Qwen3.5 when available) | ~40GB (4-bit) | Strategy analysis, debate | 2-3 instances |
| **ROCKIT fine-tuned LoRA** (on Qwen3 base) | ~40GB | Specialist analysis (ROCKIT v5.6 format) | 2-3 instances |
| **Qwen3-8B** | ~8GB (4-bit) | Fast sub-agent tasks (filtering, summarization) | 8-10 instances |
| **Embedding model** (e.g., bge-large) | ~2GB | Historical similarity search | 1 instance |

**Total VRAM budget**: ~90GB active, ~38GB headroom for batching

**Serving stack:**
- **vLLM** — batched inference, PagedAttention, continuous batching
- Multiple model slots via vLLM's multi-model support
- Prefix caching for repeated system prompts (each agent's directive)

```yaml
# vLLM serving config on DGX
models:
  - name: rockit-specialist
    path: /models/rockit-lora-v5.6
    gpu_memory_utilization: 0.35
    max_model_len: 8192

  - name: qwen3-orchestrator
    path: /models/qwen3-32b-awq
    gpu_memory_utilization: 0.35
    max_model_len: 16384

  - name: qwen3-subagent
    path: /models/qwen3-8b-awq
    gpu_memory_utilization: 0.08
    max_model_len: 4096
    quantization: awq
```

**Cost**: $0. All local. Only costs are electricity and the hardware you already own.

For Claude API calls (orchestrator-level reasoning on complex consensus decisions), estimated cost is ~$5-15/trading day based on:
- ~50 orchestrator decisions/day x ~4K tokens each = ~200K tokens/day
- At Sonnet pricing: ~$0.60/day input + ~$2.40/day output ≈ $3/day
- With occasional Opus for high-stakes decisions: ~$5-15/day total
- **Optional**: Replace with local Qwen3-32B for $0/day

---

## 6. Agent Communication Protocol

### 6.1 Message Bus: Redis Streams

Redis Streams provides ordered, persistent, fan-out messaging:

```python
import redis.asyncio as redis

class AgentBus:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)

    async def publish_snapshot(self, instrument: str, snapshot: dict):
        """Publish market snapshot to all specialist agents."""
        await self.redis.xadd(
            f"snapshots:{instrument}",
            {"data": json.dumps(snapshot)},
            maxlen=1000,  # Keep last 1000 snapshots in stream
        )

    async def publish_signal(self, agent_id: str, signal: AgentSignal):
        """Specialist publishes signal to orchestrator."""
        await self.redis.xadd(
            "signals:all",
            {"data": signal.to_json()},
        )
        # Also to strategy-specific channel for monitoring
        await self.redis.xadd(
            f"signals:{agent_id}",
            {"data": signal.to_json()},
        )

    async def publish_execution(self, order: dict):
        """Orchestrator publishes execution order."""
        await self.redis.xadd(
            "execution:orders",
            {"data": json.dumps(order)},
        )

    async def subscribe_snapshots(self, instrument: str, agent_id: str):
        """Agent subscribes to market snapshots."""
        last_id = "0"
        while True:
            results = await self.redis.xread(
                {f"snapshots:{instrument}": last_id},
                block=5000,  # 5 second timeout
                count=1,
            )
            if results:
                for stream, messages in results:
                    for msg_id, data in messages:
                        last_id = msg_id
                        yield json.loads(data[b"data"])
```

### 6.2 Agent Lifecycle

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  BOOT    │────▶│  READY   │────▶│  ACTIVE  │────▶│  COOLDOWN│
│          │     │          │     │          │     │          │
│ Load     │     │ Connected│     │ Process- │     │ Session  │
│ config,  │     │ to bus,  │     │ ing      │     │ ended,   │
│ models,  │     │ history  │     │ snapshots│     │ write    │
│ history  │     │ loaded   │     │ + signals│     │ summary  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                       │                                │
                       ▼                                ▼
                 ┌──────────┐                    ┌──────────┐
                 │  ERROR   │                    │ LEARNING │
                 │          │                    │          │
                 │ Auto-    │                    │ Post-    │
                 │ restart  │                    │ session  │
                 │ with     │                    │ review,  │
                 │ backoff  │                    │ update   │
                 │          │                    │ weights  │
                 └──────────┘                    └──────────┘
```

---

## 7. Execution Layer

### 7.1 Trade Execution Options

Three pathways to execute trades, from safest to most autonomous:

#### Option A: NinjaTrader ATM Strategy via API

Use NinjaTrader's existing infrastructure. The execution agent sends orders via NinjaTrader's API:

```csharp
// RockitAgentBridge.cs — NinjaTrader side
// Listens for orders from the agent system via local HTTP/WebSocket
protected override void OnBarUpdate()
{
    var order = PollAgentOrders();  // HTTP GET from local agent API
    if (order != null && order.Approved)
    {
        EnterLong(order.Quantity, "AgentEntry");
        SetStopLoss("AgentEntry", CalculationMode.Price, order.StopPrice, false);
        SetProfitTarget("AgentEntry", CalculationMode.Price, order.TargetPrice);
    }
}
```

**Pros**: Uses existing broker connection, ATM strategies handle order management
**Cons**: Requires NinjaTrader running, Windows dependency

#### Option B: Browser Automation (Playwright)

For platforms with web interfaces but no API:

```python
from playwright.async_api import async_playwright

class BrowserTrader:
    async def place_order(self, order: ExecutionOrder):
        """Place trade via broker web interface."""
        page = self.browser_context.pages[0]

        # Navigate to order entry
        await page.click('[data-testid="order-ticket"]')
        await page.fill('[data-testid="quantity"]', str(order.quantity))
        await page.select_option('[data-testid="order-type"]', order.order_type)

        if order.order_type == "LIMIT":
            await page.fill('[data-testid="limit-price"]', str(order.price))

        # Direction
        if order.direction == "LONG":
            await page.click('[data-testid="buy-button"]')
        else:
            await page.click('[data-testid="sell-button"]')

        # Confirm
        await page.click('[data-testid="confirm-order"]')

        # Verify fill
        await page.wait_for_selector('[data-testid="order-filled"]', timeout=5000)
```

**Pros**: Works with any web-based broker, no API needed
**Cons**: Fragile to UI changes, slower execution, screenshot verification needed

#### Option C: Direct Broker API (Future)

For brokers with REST/FIX APIs (Interactive Brokers, Tradovate, etc.):

```python
class DirectBrokerExecution:
    async def place_order(self, order: ExecutionOrder):
        """Place order directly via broker API."""
        response = await self.client.post("/orders", json={
            "instrument": order.instrument,
            "side": order.direction,
            "quantity": order.quantity,
            "type": order.order_type,
            "price": order.price,
            "stop_loss": order.stop_price,
            "take_profit": order.target_price,
        })
        return response.json()
```

### 7.2 Execution Safety Rails

**Every execution path** goes through these gates:

```python
class ExecutionGuard:
    def __init__(self, config: RiskConfig):
        self.config = config
        self.daily_pnl = 0.0
        self.open_positions = []
        self.consecutive_losses = 0

    def can_execute(self, order: ExecutionOrder) -> tuple[bool, str]:
        # Hard limits
        if self.daily_pnl <= self.config.max_daily_loss:
            return False, f"Daily loss limit reached: ${self.daily_pnl}"

        if len(self.open_positions) >= self.config.max_positions:
            return False, f"Max positions reached: {len(self.open_positions)}"

        if self.consecutive_losses >= self.config.max_consecutive_losses:
            return False, f"Circuit breaker: {self.consecutive_losses} consecutive losses"

        if not self.config.trading_window.contains(now()):
            return False, f"Outside trading window"

        if order.quantity > self.config.max_contracts:
            return False, f"Order size {order.quantity} exceeds max {self.config.max_contracts}"

        # Correlation check
        for pos in self.open_positions:
            if self.is_correlated(pos.instrument, order.instrument):
                return False, f"Correlated exposure: already in {pos.instrument}"

        return True, "Approved"
```

---

## 8. Day-in-the-Life: Full Session Flow

### 8:00 AM ET — Pre-Market Boot

```
1. Agent Manager starts all 8 specialist agents + 2 orchestrators
2. Each specialist loads:
   - Its strategy config from rockit-core
   - Pre-market analysis (Asia, London, overnight from rockit-pipeline)
   - Yesterday's session context from historical DB
   - Its model instance on DGX via vLLM
3. Cross-Market Agent analyzes overnight:
   - ES/NQ/YM correlation
   - VIX regime
   - Globex range and key levels
4. All agents publish READY status to bus
```

### 9:30 AM ET — Market Open

```
1. rockit-ingest begins streaming minute-by-minute data
2. Each minute:
   a. Ingest writes raw bar to minute_snapshots table
   b. Pipeline runs 12-module deterministic analysis
   c. Snapshot published to Redis "snapshots:NQ"
   d. All 8 specialist agents receive snapshot simultaneously

3. Each specialist (in parallel):
   a. Runs strategy rules against snapshot (deterministic, <10ms)
   b. If rules trigger: spawns sub-agent debate
      - Advocate: "Rules say entry, model confirms" (~200ms on DGX)
      - Skeptic: "Filter check, risk check" (~200ms on DGX)
      - Historian: SQL query to historical DB (~5ms)
   c. If consensus: publishes AgentSignal to bus

4. Orchestrator receives signals:
   a. Chief Strategist aggregates across specialists
   b. Risk Manager checks portfolio constraints
   c. If approved: publishes to execution channel
   d. Dashboard updated in real-time
```

### 10:00 AM ET — IB Forms (Example Scenario)

```
Snapshot arrives: IB range = 72 ticks, IB High = 21850, DPOC migrating up

Trend Agent:
  Advocate: "IB >60 ticks, DPOC migration, accepting above prior VAH → Trend Day developing"
  Skeptic: "Volume declining from open, only 30 min in, could be false move"
  Historian: "37 sessions with IB 60-80 + DPOC up: 24 were Trend Days (65%), avg +$680"
  → Signal: LONG, 72% confidence, entry 21855, stop 21815, target 21920

P-Day Agent:
  Advocate: "Skewed profile, one-time framing up, P-Day criteria met"
  Skeptic: "Not enough extension yet (only 1.03x IB), need 1.5x to confirm"
  Historian: "42 sessions with skew + early migration: 28 extended (67%)"
  → Signal: LONG, 65% confidence (lower due to insufficient extension)

ICT Agent:
  → Signal: FLAT (no ICT setup active, watching for Judas Swing completion)

Edge Fade Agent:
  → Signal: FLAT (price not at VA edge, no mean reversion setup)

Chief Strategist:
  2 agents agree LONG (Trend 72%, P-Day 65%), 0 disagree, 6 flat
  Weighted consensus: 68.5% (Trend accuracy: 58%, P-Day accuracy: 62%)
  → MODERATE consensus
  → Action: ALERT human, recommend LONG 1 MNQ

Risk Manager:
  Daily P&L: $0, no positions, within window
  → APPROVED

Dashboard shows:
  "MODERATE LONG — Trend + P-Day agents agree, 68.5% consensus
   Entry: 21855, Stop: 21815, Target: 21920
   Historical: 65% win rate in similar setups
   Dissent: ICT watching for possible Judas Swing"
```

### 11:30 AM ET — Signal Strengthens

```
IB extension reaches 1.5x, volume returns, 3rd push above IBH

P-Day Agent upgrades: 82% confidence (extension confirmed)
Sweep Agent activates: "IBH sweep failed to reverse, acceptance confirmed"
  → Signal: LONG, 71% confidence

Chief Strategist:
  3 agents agree LONG (Trend 75%, P-Day 82%, Sweep 71%)
  → STRONG consensus (avg 76%)
  → Action: AUTO-EXECUTE eligible (if mode = auto-execute)

If auto-execute:
  Execution layer places 2 MNQ LONG at market
  Stop: 21815, Target 1: 21920, Target 2: trail
```

### 3:30 PM ET — Session End / Post-Market

```
1. All positions closed (time-based exit rule)
2. Session results logged to trades table
3. Each specialist enters LEARNING mode:
   - Compare signals emitted vs actual outcomes
   - Update internal confidence calibration
   - Flag any signals that would have been profitable but were filtered
4. Cross-Market Agent writes session summary
5. Historical DB updated with actual_outcome for today's session
```

---

## 9. Learning & Adaptation

### 9.1 Post-Session Review (Daily)

After each session, an automated review agent:

```python
class PostSessionReviewer:
    async def review(self, session_date: str):
        # 1. Get all signals emitted today
        signals = await db.query(
            "SELECT * FROM agent_signals WHERE date = %s", session_date
        )

        # 2. Get actual market outcome
        outcome = await db.query(
            "SELECT * FROM session_analysis WHERE session_date = %s "
            "ORDER BY time_slice DESC LIMIT 1", session_date
        )

        # 3. Score each signal
        for signal in signals:
            was_correct = self.evaluate_signal(signal, outcome)
            await db.update_signal_outcome(signal.id, was_correct)

        # 4. Update agent accuracy weights
        for agent in self.agents:
            accuracy = await db.query(
                "SELECT AVG(CASE WHEN correct THEN 1.0 ELSE 0.0 END) "
                "FROM agent_signals WHERE agent_id = %s "
                "AND date >= %s",
                agent.id, session_date - timedelta(days=20)
            )
            agent.rolling_accuracy = accuracy

        # 5. Generate session report
        report = {
            "date": session_date,
            "signals_emitted": len(signals),
            "signals_correct": sum(1 for s in signals if s.correct),
            "consensus_trades": self.count_consensus_trades(signals),
            "pnl": outcome.daily_pnl,
            "best_agent": max(self.agents, key=lambda a: a.rolling_accuracy),
            "worst_agent": min(self.agents, key=lambda a: a.rolling_accuracy),
            "missed_opportunities": self.find_missed(signals, outcome),
        }

        return report
```

### 9.2 Agent Weight Evolution

Over time, the system learns which agents to trust more:

```
Week 1: All agents weighted equally (12.5% each)
Week 4: Trend Agent: 18%, P-Day Agent: 15%, ICT Agent: 8% (adjusting to performance)
Week 8: Weights stabilize based on rolling 20-day accuracy
```

This is **not retraining the models** — it's adjusting the orchestrator's weighting of each specialist's signals. Lightweight and immediate.

### 9.3 Monthly Model Refresh

Every month (or when performance degrades):
1. New month of data (20 sessions) added to training set
2. LoRA fine-tune refreshed on DGX with expanded dataset
3. New model evaluated against historical benchmarks
4. If it passes gates, swap into production
5. All automated via the existing `rockit-train` pipeline

---

## 10. Infrastructure & Deployment

### 10.1 Hardware Layout

```
┌──────────────────────────────────────────────────────┐
│                  SPARK DGX (128GB VRAM)               │
│                                                      │
│  vLLM Server                                         │
│  ├── Slot 1: ROCKIT LoRA model (~40GB)               │
│  ├── Slot 2: Qwen3-32B orchestrator (~40GB)          │
│  ├── Slot 3: Qwen3-8B sub-agents (~8GB)              │
│  └── Slot 4: Embedding model (~2GB)                  │
│                                                      │
│  Agent Runtime                                       │
│  ├── 8 Strategy Specialist processes                 │
│  ├── 2 Orchestrator processes                        │
│  ├── 1 Post-session reviewer                         │
│  └── 1 Agent manager (supervisor)                    │
│                                                      │
│  Data Services                                       │
│  ├── TimescaleDB (PostgreSQL)                        │
│  ├── Redis (message bus)                             │
│  └── rockit-pipeline (deterministic analysis)        │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│              TRADING MACHINE (Windows)                │
│                                                      │
│  NinjaTrader 8                                       │
│  ├── RockitAgentBridge.cs (receives orders)          │
│  └── Data export → rockit-ingest                     │
│                                                      │
│  rockit-ingest (data collector)                      │
│  └── Pushes data to DGX via API                      │
│                                                      │
│  Browser (optional)                                  │
│  └── Playwright for web-based broker execution       │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│              GCP (Optional / Hybrid)                  │
│                                                      │
│  Cloud Run: rockit-serve (API for dashboard/mobile)  │
│  GCS: Backup storage, model artifacts                │
│  (Most compute stays on DGX to minimize costs)       │
└──────────────────────────────────────────────────────┘
```

### 10.2 Docker Compose (Local Development / DGX)

```yaml
version: "3.8"

services:
  # --- Data Layer ---
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: rockit
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    command: redis-server --appendonly yes

  # --- Model Serving ---
  vllm:
    image: vllm/vllm-openai:latest
    runtime: nvidia
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    ports: ["8000:8000"]
    volumes:
      - /models:/models
    command: >
      --model /models/rockit-lora-v5.6
      --served-model-name rockit-specialist
      --gpu-memory-utilization 0.85
      --max-model-len 8192
      --enable-prefix-caching

  # --- Agent Runtime ---
  agent-manager:
    build: ./packages/rockit-agents
    depends_on: [timescaledb, redis, vllm]
    environment:
      DATABASE_URL: postgresql://postgres:${DB_PASSWORD}@timescaledb:5432/rockit
      REDIS_URL: redis://redis:6379
      VLLM_URL: http://vllm:8000/v1
      EXECUTION_MODE: monitor  # monitor | alert | auto-execute
    volumes:
      - ./configs:/app/configs

  # --- Data Pipeline ---
  pipeline:
    build: ./packages/rockit-pipeline
    depends_on: [timescaledb, redis]
    environment:
      DATABASE_URL: postgresql://postgres:${DB_PASSWORD}@timescaledb:5432/rockit
      REDIS_URL: redis://redis:6379

  # --- Dashboard ---
  dashboard:
    build: ./packages/rockit-clients/dashboard
    ports: ["3000:3000"]
    depends_on: [redis, timescaledb]
    environment:
      API_URL: http://agent-manager:8080
      WS_URL: ws://redis:6379

volumes:
  pgdata:
```

### 10.3 Monitoring & Alerting

```yaml
# Agent health monitoring
alerts:
  - name: agent_down
    condition: "agent.status != 'ACTIVE' for > 60s during market hours"
    action: restart_agent, notify_slack

  - name: consensus_timeout
    condition: "no orchestrator decision within 30s of signal"
    action: notify_slack

  - name: execution_failure
    condition: "order placed but not filled within 10s"
    action: cancel_order, notify_slack, log_failure

  - name: daily_loss_warning
    condition: "daily_pnl < -$500"
    action: notify_slack, reduce_to_alert_mode

  - name: daily_loss_halt
    condition: "daily_pnl < -$1500"
    action: flatten_all, switch_to_monitor_mode, notify_slack

  - name: model_latency
    condition: "vllm_inference_p95 > 2000ms"
    action: notify_slack, check_gpu_utilization
```

---

## 11. New Package: `rockit-agents`

This adds a new package to the monorepo:

```
packages/rockit-agents/
├── src/rockit_agents/
│   ├── __init__.py
│   ├── core/
│   │   ├── base.py              # StrategyAgent, OrchestratorAgent ABC
│   │   ├── signal.py            # AgentSignal, Snapshot dataclasses
│   │   ├── bus.py               # Redis Streams message bus
│   │   └── lifecycle.py         # Agent state machine (boot/ready/active/cooldown)
│   │
│   ├── specialists/
│   │   ├── trend_agent.py       # TrendBull/Bear, SuperTrend, MorphToTrend
│   │   ├── pday_agent.py        # P-Day, PM Morph
│   │   ├── bday_agent.py        # B-Day, Neutral
│   │   ├── ict_agent.py         # OR Reversal, OR Acceptance
│   │   ├── edge_fade_agent.py   # Edge Fade, 80% Rule
│   │   ├── sweep_agent.py       # IBH Sweep Fail, Bear Accept
│   │   ├── ib_retest_agent.py   # IB Retest, Balance Signal
│   │   └── cross_market_agent.py# SMT, VIX, intermarket
│   │
│   ├── sub_agents/
│   │   ├── advocate.py          # Finds reasons FOR the trade
│   │   ├── skeptic.py           # Finds reasons AGAINST the trade
│   │   └── historian.py         # Queries historical DB for precedent
│   │
│   ├── orchestrators/
│   │   ├── chief_strategist.py  # Consensus aggregation, portfolio recommendation
│   │   └── risk_manager.py      # Position limits, circuit breakers, execution gates
│   │
│   ├── execution/
│   │   ├── base.py              # ExecutionOrder, ExecutionGuard
│   │   ├── ninjatrader.py       # NinjaTrader API bridge
│   │   ├── browser.py           # Playwright browser automation
│   │   └── direct_api.py        # Direct broker API (IB, Tradovate)
│   │
│   ├── learning/
│   │   ├── post_session.py      # Daily review, signal scoring
│   │   ├── weight_evolution.py  # Rolling accuracy → agent weights
│   │   └── performance.py       # P&L tracking, drawdown analysis
│   │
│   └── manager.py               # Agent supervisor (start/stop/restart/monitor)
│
├── configs/
│   ├── agents.yaml              # Agent definitions, groupings
│   ├── risk.yaml                # Risk limits, circuit breakers
│   ├── execution.yaml           # Execution mode, broker config
│   └── models.yaml              # vLLM model assignments per agent role
│
├── tests/
│   ├── test_consensus.py        # Consensus logic unit tests
│   ├── test_risk_manager.py     # Risk gate tests
│   ├── test_historian.py        # Historical query tests
│   └── test_execution_guard.py  # Safety rail tests
│
└── pyproject.toml
```

**Dependency graph update:**

```
rockit-core          (0 deps — strategies, indicators, signals)
     │
rockit-pipeline      (depends on: rockit-core)
     │
rockit-agents        (depends on: rockit-core, rockit-pipeline)  ← NEW
     │
rockit-serve         (depends on: rockit-core, rockit-agents)
```

---

## 12. Migration Path: Incremental Adoption

This doesn't replace the existing architecture proposal — it **extends** it. We can adopt incrementally:

### Phase A: Historical Database (Week 1)
- Set up TimescaleDB
- Load 259 days of deterministic analysis
- Build query interface for Historian sub-agent
- **Value**: Searchable historical context, no agents needed yet

### Phase B: Single Strategy Agent (Weeks 2-3)
- Implement Trend Agent (highest volume strategy)
- Run in MONITOR mode alongside existing system
- Compare agent signals vs what human would have done
- **Value**: Proof of concept, validate signal quality

### Phase C: Sub-Agent Debate (Weeks 3-4)
- Add Advocate/Skeptic/Historian to Trend Agent
- Measure: Does debate improve signal quality vs raw strategy output?
- **Value**: Quantified improvement from consensus

### Phase D: Multi-Specialist (Weeks 4-6)
- Deploy remaining 7 specialist agents
- All in MONITOR mode
- Dashboard shows agent signals in real-time
- **Value**: Full coverage, human can see all agent opinions

### Phase E: Orchestrator (Weeks 6-8)
- Deploy Chief Strategist + Risk Manager
- ALERT mode: human gets consensus-weighted recommendations
- Track consensus accuracy vs individual agents
- **Value**: Filtered, weighted recommendations

### Phase F: Auto-Execution (Weeks 8-10)
- Enable AUTO-EXECUTE for STRONG consensus only
- Start with 1 MNQ (smallest position)
- Human monitors via dashboard + kill switch
- Gradual position size increase as trust builds
- **Value**: Autonomous trading with safety rails

### Phase G: Learning Loop (Weeks 10-12)
- Post-session reviewer runs daily
- Agent weights evolve based on performance
- Monthly model refresh automated
- **Value**: Self-improving system

---

## 13. Open Questions

1. **Latency budget**: Sub-agent debate adds ~500ms. Is that acceptable for entry signals? (Most entries are limit orders, so probably yes)

2. **Agent framework lock-in**: Should we start with a specific framework (CrewAI, LangGraph) or build lightweight custom agents first? Custom is faster to prototype but harder to scale.

3. **Execution priority**: NinjaTrader bridge vs browser automation vs direct broker API? NinjaTrader bridge is lowest effort since the C# code already exists.

4. **Model allocation**: Run one large model (Qwen3-32B) for everything, or specialize (LoRA for analysis, base model for reasoning)? Specialized is better but more complex to manage.

5. **Consensus threshold**: What confidence % and agent count should trigger auto-execution? Needs backtesting against the 259 historical sessions.

6. **Correlation handling**: When NQ and ES agents both signal LONG, is that 2 votes or 1 (since they're correlated)? Need instrument correlation logic.

7. **Backtesting agents**: Can we replay the 259 sessions through the agent system to get simulated P&L before going live? This is critical for validation.

---

## 14. Why This Works

The existing Rockit system already proved the concept:
- 16 strategies with 55.5% WR, 1.58 PF across 259 sessions
- Deterministic analysis pipeline generating rich snapshots
- Fine-tuned models that understand the domain

What's missing is **automation of the decision loop**. A human currently:
1. Reads the analysis ← agents do this
2. Cross-references strategies ← specialists do this
3. Checks historical precedent ← historian does this
4. Weighs conflicting signals ← orchestrator does this
5. Manages risk ← risk manager does this
6. Places the trade ← execution layer does this

Every step is automatable. The multi-agent consensus approach adds robustness that a single model can't match — the same way a trading desk works better than a solo trader.

**The 259-day historical database is the secret weapon.** No other retail system has 259 days of rich, structured market analysis mapped to outcomes. This is the grounding data that makes the agents' reasoning verifiable rather than hallucinated.

**Cost: Near zero.** DGX handles all inference. TimescaleDB and Redis are lightweight. The only variable cost is optional Claude API calls for orchestrator reasoning, which can be replaced by local Qwen3-32B.
