# Phase 5a: Agent System — Detailed Roadmap

> **Goal:** LLM tape reader + Advocate/Skeptic/Orchestrator debate pipeline with DuckDB context.
> **Duration:** Week 10-12
> **Depends on:** Phase 3 (API), Phase 4 (trained model)
> **Blocks:** Phase 5b (dashboard needs agent API), Phase 5c (clients need signals)

---

## Architecture Overview

See `architecture/08-agent-system.md` (Rev 3) for full architecture.
See `brainstorm/07-augmenting-training-tape-reading-intelligence.md` for tape reading design.

### Runtime Architecture (Single Process)
```
┌───────────────────────────────────────────────────────────┐
│  Data Feed (1-min bars from NinjaTrader or replay)        │
│       │                         │                          │
│       ▼                         ▼                          │
│  Strategy Runner (1-min)  Orchestrator (5-min snapshots)  │
│  • Check signals           • 38 deterministic modules      │
│  • Manage open trades      • LLM tape reading (~2-3s)      │
│       │                    • Publish to dashboard           │
│       │signal                                               │
│       ▼                                                     │
│  DuckDB (in-process) ← signals, decisions, trades,         │
│       │                  snapshots, sessions                │
│       │signal event                                         │
│       ▼                                                     │
│  Agent Pipeline:                                            │
│  1. Load tape reading + signal + DuckDB history             │
│  2. Advocate + Skeptic in PARALLEL (same LoRA, diff prompts)│
│  3. Orchestrator decides: TAKE / PASS / REDUCE              │
│  4. Write decision → DuckDB + Dashboard                     │
│                                                             │
│  Also: UI can ask agents for opinions (after 10:30)         │
│  even without a strategy signal                             │
└───────────────────────────────────────────────────────────┘
```

### Key Design Decisions
- **Same LoRA, three personas** — Advocate/Skeptic/Orchestrator via system prompts
- **Strategy runner triggers agents** — but UI can also request on-demand analysis after 10:30
- **DuckDB is the single source of truth** — signals, decisions, trades, historical context
- **No external message queues** — Python asyncio events + DuckDB in-process
- **~2-5 agent debates per day** — most snapshots are tape read only (dashboard)

---

## Tasks

### 5a.1 DuckDB Schema & Signal Store
- [ ] Implement DuckDB schema (5 tables: signals, decisions, trades, snapshots, sessions)
- [ ] Signal write on strategy trigger → asyncio event → agent pipeline
- [ ] Snapshot write on 5-min orchestrator run
- [ ] Session summary write at EOD
- [ ] See `brainstorm/07...md` Appendix D for full schema

### 5a.2 LLM Tape Reader Integration
- [ ] vLLM serving Qwen3.5-35B-A3B + LoRA adapter (DGX Spark)
- [ ] Tape reader called every 5-min snapshot → produces analysis JSON
- [ ] Tape reading stored alongside snapshot in DuckDB
- [ ] Dual bull/bear evidence columns feed Advocate/Skeptic

### 5a.3 Agent Pipeline (LangGraph)
- [ ] `agents/graph.py` — StateGraph: gate → observe → mine → debate → decide → emit
- [ ] `agents/advocate.py` — builds case FROM evidence (not raw signal)
- [ ] `agents/skeptic.py` — challenges weak evidence, identifies traps, balance day warnings
- [ ] `agents/orchestrator.py` — weighs both + CRI gate + risk budget → TAKE/PASS/REDUCE
- [ ] `agents/pattern_miner.py` — DuckDB queries for historical context (replaces Historian)
- [ ] CRI STAND_DOWN = always PASS (hard gate, no debate needed)
- [ ] Advocate + Skeptic run in PARALLEL (same model, different prompts)

### 5a.4 Strategy Runner + Agent Coexistence
- [ ] Single-process main loop with two cadences (1-min signals, 5-min snapshots)
- [ ] Strategy runner manages open trades independently of agents
- [ ] Agent debate is async — doesn't block the main loop
- [ ] See `brainstorm/07...md` §D.6 for pseudocode

### 5a.5 UI On-Demand Agent Opinions
- [ ] After 10:30, user can ask agents for analysis even without signals
- [ ] WebSocket endpoint for requesting agent opinion on current market state
- [ ] Agents use latest tape reading + DuckDB context to reason
- [ ] Rich backtest data and study reasoning available in responses

### 5a.6 Agent Prompt Templates
- [ ] Advocate prompt: "Build the case FROM the evidence cards. Cite study stats."
- [ ] Skeptic prompt: "Find the flaw. Warn about balance day traps, exhaustion, 2nd touch degradation."
- [ ] Orchestrator prompt: "Weigh both. CRI is hard gate. Caution over conviction."
- [ ] All prompts versioned in `configs/agents/prompts/`

### 5a.7 Streaming to Dashboard
- [ ] WebSocket push: tape reading on every snapshot
- [ ] WebSocket push: agent debate when signal fires
- [ ] Dashboard tabs: Brief, Logic, Intraday, DPOC, Coach, Trade Idea (agent debate)

### 5a.8 Self-Learning Reflection Loop
- [ ] Outcome Logger (post-market, pure Python, no LLM)
- [ ] Per-agent scorecards (Advocate accuracy, Skeptic catch rate)
- [ ] Daily reflection (Qwen3.5 post-market)
- [ ] Meta-review (Opus 4.6 API, every 1-3 days)
- [ ] Auto-rollback if agent performance degrades

### 5a.9 Walk-Forward & Multi-Agent Backtest
- [ ] 90-day replay with full debate + reflection
- [ ] Compare agent_adaptive vs deterministic_only
- [ ] Walk-forward: train window → test window → measure OOS improvement

---

## Definition of Done

- [ ] Agent debate produces structured TAKE/PASS/REDUCE decisions
- [ ] DuckDB stores all signals, decisions, trades with full lineage
- [ ] Tape reader runs every 5-min and publishes to dashboard
- [ ] UI can request on-demand agent opinions after 10:30
- [ ] Walk-forward validation shows OOS improvement
- [ ] Auto-rollback triggers correctly when metrics degrade
- [ ] Strategy runner + agents coexist in single process without blocking
