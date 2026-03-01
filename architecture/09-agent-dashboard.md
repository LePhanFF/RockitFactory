# Agent Monitoring Dashboard

## Purpose

Real-time visibility into what every agent is doing, why, and how well. This is not the trading dashboard (RockitUI) — this is the **ops dashboard** for monitoring the multi-agent system itself.

```
┌─────────────────────────────────────────────────────────────────────┐
│  ROCKIT AGENT MONITOR                          2026-03-01 10:32 ET  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  SYSTEM STATUS: LIVE ●         Model: Qwen3.5 (vLLM)   Queue: 0   │
│  Session: RTH Day 142          Day Type: P-Day (72%)    IB: 45pts  │
│                                                                     │
├────────────────────┬────────────────────────────────────────────────┤
│  ACTIVE AGENTS     │  LIVE DEBATE                                   │
│  ──────────────    │  ─────────────────────────────────             │
│  ● TrendBull       │  TrendBull Advocate:                           │
│  ● EdgeFade        │  "IBH accepted with strong delta (+450),       │
│  ○ BDay            │   DPOC migrating up. Trend continuation."      │
│  ○ BearAccept      │                                                │
│  ○ IBHSweep        │  TrendBull Skeptic:                            │
│  ○ ORReversal      │  "Volume declining since 10:15. P-shape TPO    │
│  ○ PDay            │   suggests exhaustion, not continuation."      │
│  ○ IBRetest        │                                                │
│                    │  Orchestrator: TAKE (confidence: 0.72)          │
│  ● = signal active │  Historian: 4/5 similar sessions were P-Day    │
│  ○ = monitoring    │  Risk: Within limits ($380 risk on 2 MNQ)      │
│                    │                                                │
├────────────────────┼────────────────────────────────────────────────┤
│  TODAY'S SIGNALS   │  AGENT HEALTH                                  │
│  ──────────────    │  ─────────────────────────────────             │
│  10:15 TrendBull   │  LLM Latency    : 1.2s avg (OK)              │
│    LONG 21850      │  Queue Depth    : 0 (OK)                      │
│    conf: 0.72      │  Deterministic  : 8ms avg (OK)               │
│    status: ACTIVE  │  API Response   : 45ms avg (OK)               │
│                    │  Memory         : 42GB / 128GB                 │
│  09:45 ORReversal  │  GPU Util       : 35%                          │
│    SKIP (skeptic   │                                                │
│    overruled)      │  ERRORS TODAY   : 0                            │
│                    │  ROLLBACKS      : 0                            │
├────────────────────┴────────────────────────────────────────────────┤
│  REFLECTION (Yesterday)                                             │
│  ─────────────────────                                              │
│  Day Type Accuracy: 1/1 ✓    Win Rate: 2/3 (67%)                  │
│  Adjustment Applied: skeptic IB-range check (v08 → v09)            │
│  A/B Test Running: skeptic-ib-check (day 3/20)                     │
│  Meta-Review: Scheduled tomorrow (3 reflections pending)            │
│                                                                     │
│  20-Day Rolling: WR 58% | PF 1.62 | Sharpe 1.8 | MaxDD -$1,200   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Dashboard Architecture

```
┌──────────────────┐     WebSocket      ┌──────────────────┐
│  Dashboard UI    │◀──────────────────│  rockit-serve     │
│  (React)         │                    │  /api/v1/agents/* │
│                  │                    │                    │
│  Components:     │     REST           │  Data sources:     │
│  • Agent Grid    │◀──────────────────│  • Live agent state│
│  • Debate Feed   │                    │  • Signal log      │
│  • Signal Log    │                    │  • Scorecards DB   │
│  • Health Panel  │                    │  • Reflection logs │
│  • Reflection    │                    │  • System metrics  │
│  • Performance   │                    │                    │
└──────────────────┘                    └──────────────────┘
```

### API Endpoints for Dashboard

```
# Live state (WebSocket)
WSS  /api/v1/agents/stream
     → Push: agent state changes, new signals, debate messages

# Agent status
GET  /api/v1/agents/status
     → All agents with current state (active/monitoring/error)

GET  /api/v1/agents/{agent_id}/debates?date={date}
     → Full debate transcripts for an agent today

# Signals
GET  /api/v1/agents/signals?date={date}
     → All signals emitted today with outcomes (if market closed)

GET  /api/v1/agents/signals/{signal_id}
     → Detailed signal with advocate/skeptic/consensus reasoning

# Performance
GET  /api/v1/agents/scorecards?date={date}
     → Daily scorecards for all agents

GET  /api/v1/agents/performance?days={n}
     → Rolling performance metrics

GET  /api/v1/agents/performance/{strategy}?days={n}
     → Per-strategy performance breakdown

# Reflection
GET  /api/v1/agents/reflections?date={date}
     → Daily reflection journal

GET  /api/v1/agents/reflections/proposals
     → Pending adjustment proposals

GET  /api/v1/agents/ab-tests
     → Active A/B tests with current results

# System health
GET  /api/v1/agents/health
     → LLM latency, queue depth, GPU utilization, errors

# Version management
GET  /api/v1/agents/versions
     → Current prompt/param versions for all agents

GET  /api/v1/agents/versions/history
     → Version change history with reasons

POST /api/v1/agents/versions/{agent_id}/rollback
     → Manual rollback trigger (with confirmation)
```

---

## Dashboard Pages

### 1. Live View (Default)

Real-time during market hours:
- Agent grid showing which strategies are active vs monitoring
- Live debate feed (streaming advocate/skeptic/consensus)
- Signal feed with entry/stop/target levels
- System health gauges (latency, queue, GPU)

### 2. Signals & Outcomes

Post-market or historical:
- Every signal emitted with full context
- Drill into any signal to see: advocate reasoning, skeptic reasoning, consensus, filter results, order flow snapshot, outcome
- Filter by strategy, date, outcome (win/loss/skip)

### 3. Performance

Rolling metrics:
- Per-strategy win rate, PF, expectancy over 5/10/20/60 days
- Confidence calibration chart (predicted vs actual win rate)
- Equity curve by strategy and combined
- Drawdown analysis
- Comparison: before vs after each version change

### 4. Reflection & Learning

Self-improvement visibility:
- Daily reflection journals (readable format)
- Pending adjustment proposals with approve/reject buttons
- A/B test progress with statistical significance indicator
- Version timeline (what changed when and why)
- Rollback history

### 5. Backtest Replay

Multi-agent system backtesting (see next section):
- Run the full agent system over historical data
- Replay debates and consensus at any historical point
- Compare current behavior vs historical behavior
- Validate changes before going live

---

## Implementation

The dashboard extends the existing `rockit-clients/dashboard/` with new pages. Same tech stack (React/Next.js), same deployment (Cloud Run alongside the API).

### New Monorepo Structure

```
packages/rockit-clients/dashboard/src/
├── pages/
│   ├── index.tsx              # Existing trading dashboard
│   ├── agents/
│   │   ├── index.tsx          # Live agent monitor (default)
│   │   ├── signals.tsx        # Signal log & outcomes
│   │   ├── performance.tsx    # Rolling performance metrics
│   │   ├── reflection.tsx     # Reflection & learning view
│   │   └── backtest.tsx       # Multi-agent backtest replay
│   └── ...
├── components/
│   ├── agents/
│   │   ├── AgentGrid.tsx      # Agent status grid
│   │   ├── DebateFeed.tsx     # Live debate transcript
│   │   ├── SignalCard.tsx     # Individual signal display
│   │   ├── ScoreChart.tsx     # Performance charts
│   │   ├── ReflectionView.tsx # Reflection journal display
│   │   ├── ABTestCard.tsx     # A/B test progress
│   │   ├── VersionTimeline.tsx# Version change history
│   │   └── HealthGauges.tsx   # System health indicators
│   └── ...
└── hooks/
    ├── useAgentStream.ts      # WebSocket hook for live updates
    ├── useScorecard.ts        # Fetch agent scorecards
    └── useReflection.ts       # Fetch reflection data
```

### Data Storage for Dashboard

```
DuckDB (local or GCS-backed):
├── signal_outcomes      # Every signal with outcome
├── agent_scorecards     # Daily per-agent scorecards
├── debate_transcripts   # Full advocate/skeptic/consensus text
├── session_context      # Market context snapshots
└── version_changes      # Prompt/param version history

GCS:
├── reflection/journals/ # Daily reflection JSON
├── reflection/outcomes/ # Outcome JSONL
└── reflection/meta/     # Opus meta-review outputs
```
