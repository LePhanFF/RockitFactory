# Rockit Architecture Proposal — Overview

> **Revision 2** — Updated after local inspection of all 6 source repositories.
> Previous revision made assumptions without repo access. This version reflects actual code state.

## Current State: What Actually Exists

After inspecting all repositories locally, here is the real picture:

```
BookMapOrderFlowStudies                    rockit-framework (standalone)
├── 16 Python strategies                   ├── orchestrator.py (38 analysis modules)
│   (9 Dalton core + 6 research + neutral) │   ├── CRI, Dalton, playbook engines v1/v2
│   StrategyBase → emit signals only       │   ├── balance classification, mean reversion
├── Backtest engine (259 sessions)         │   ├── OR reversal, edge fade, VA edge fade
│   engine/{backtest,position,execution,   │   ├── 80% rule, 20% rule, enhanced reasoning
│           trade,equity}.py               │   └── + 20 more modules (9,293 LOC total)
├── Filter chain (7 files, 5 filter types) ├── analyze-today.py (live inference)
├── Indicators (5 files: ICT, SMT, tech)   │   downloads CSV from Google Drive every 2 min
├── Market Profile (6 files: TPO, VP, etc) │   calls local LLM at localhost:8001
├── Config (constants, instruments)        │   uploads JSONL to GCS incrementally
├── Reporting (metrics, trade log, etc)    ├── 3 training data generators
│                                          │   (synthetic, LoRA, 90-day batch)
├── rockit-framework/ (OLDER COPY)         ├── config/ + schema.json validation
│   orchestrator + 12 modules              └── 72 Python files total
│   (subset of standalone repo)
│                                          RockitDataFeed
├── 2 NinjaTrader C# files                ├── local-analysis/ (58 files, 252 days)
│   DualOrderFlow_Evaluation.cs (397 LOC)  ├── local-analysis-format/ (4 files, 2026)
│   DualOrderFlow_Funded.cs (526 LOC)      └── xai-analysis/ (43 files, Oct-Dec 2025)
│   ** Standalone order flow strategies,       3 different annotation formats
│      ZERO overlap with Python strategies **
│                                          RockitAPI
├── ~200 Python files total                ├── FastAPI journal CRUD app (NOT signals API)
│   (72 research/diagnostic scripts)       ├── JWT auth, GCS storage
│                                          ├── Endpoints: health, login, journal CRUD
└── NO Pine Script files anywhere          └── Has nothing to do with strategy signals

                                           RockitUI
                                           └── prompt/project-design.md (spec only)
                                              NO implementation code
```

**Pain points (confirmed by code inspection):**

1. **Two divergent rockit-frameworks** — BookMapOrderFlowStudies has an older copy (12 modules) while the standalone repo has evolved to 38 modules (9,293 LOC). They've drifted apart.

2. **NinjaTrader C# is completely independent** — The C# files implement their own delta/CVD/imbalance/signal detection from scratch. They share zero logic with the 16 Python strategies. Any strategy change requires reimplementation in a different language.

3. **No signals API exists** — RockitAPI is a trading journal app (login, save/load journal entries). The analysis-serving API that clients would consume doesn't exist yet.

4. **No dashboard exists** — RockitUI is a one-page design spec. No React code.

5. **No Pine Script exists** — Despite being mentioned in docs, there are zero `.pine` files in any repo.

6. **Manual LLM training** — `analyze-today.py` downloads CSVs from Google Drive, calls a local LLM (Qwen 2.5 14B at localhost:8001), uploads JSONL to GCS. Training happens manually on Spark DGX.

7. **Fragile data pipeline** — Google Drive sync, 2-minute polling, file-based handoffs, no schema validation, no replay capability.

---

## The Vision: Research-Driven Pipeline

The core idea: **research is the engine, everything else consumes its output**.

```
┌──────────────────────────────────────────────────────────────────────┐
│                          RockitFactory                                │
│                                                                      │
│  RESEARCH & BACKTEST                                                 │
│  ┌────────────────────────────────────────┐                          │
│  │ rockit-core                             │                          │
│  │  Strategies + Engine + Filters +        │                          │
│  │  Indicators + Deterministic Modules     │                          │
│  │  (single source of truth)               │                          │
│  │                                         │                          │
│  │  Backtest 259+ sessions                 │                          │
│  │  Generate deterministic snapshots       │                          │
│  │  Publishable as library                 │                          │
│  └──────────────┬──────────────────────────┘                          │
│                 │                                                     │
│        ┌────────┼──────────┐                                          │
│        ▼        ▼          ▼                                          │
│  ┌──────────┐ ┌─────────┐ ┌──────────────┐                           │
│  │ rockit-  │ │ rockit- │ │ rockit-serve │                           │
│  │ train    │ │ ingest  │ │ (signals API)│                           │
│  │          │ │         │ │              │──▶ Annotations JSON        │
│  │ LoRA     │ │ CSV→GCS │ │ Deterministic│──▶ Trade setups           │
│  │ Qwen     │ │ live    │ │ + LLM output │   (entry/stop/target/     │
│  │ 30B/70B  │ │ data    │ │              │    trail instructions)     │
│  │ incr/full│ │         │ │              │                           │
│  └──────────┘ └─────────┘ └──────┬───────┘                           │
│                                  │                                    │
│                    ┌─────────────┼─────────────┐                      │
│                    ▼             ▼              ▼                      │
│              ┌──────────┐ ┌──────────┐  ┌───────────┐                │
│              │NinjaTrader│ │TradingView│  │ Dashboard │                │
│              │thin client│ │thin client│  │ (React)   │                │
│              │           │ │           │  │           │                │
│              │Draws from │ │Draws from │  │Shows from │                │
│              │API JSON   │ │API JSON   │  │API JSON   │                │
│              │           │ │           │  │           │                │
│              │Fills trades│ │          │  │           │                │
│              │at prices  │ │          │  │           │                │
│              │API says   │ │          │  │           │                │
│              └──────────┘ └──────────┘  └───────────┘                │
└──────────────────────────────────────────────────────────────────────┘
```

**Key principle:** The API provides instructions — annotations to draw, trade setups with entry/stop/target/trail. It's up to the client to render charts and execute trades. The API does not manage positions.

---

## Core Design Principles

### 1. Research Is the Foundation
All strategy logic, backtesting, and deterministic analysis live in `rockit-core`. This is the single source of truth. When research produces a new strategy or tweaks an existing one, everything downstream (training, inference, API, clients) automatically picks it up.

### 2. Publish and Consume
`rockit-core` is a publishable Python library. Other packages import it — the backtest engine, training pipeline, inference API all use the same code. No translation, no duplication.

### 3. API Provides Instructions, Clients Execute
The API serves two things:
- **Annotations**: zones, levels, signals — what to draw on a chart
- **Trade setups**: entry price, stop price, targets, trail rules — what trades to take

Clients (NinjaTrader, TradingView, Dashboard) are thin renderers/executors. They draw what the API says, fill trades at the prices the API specifies, and manage execution locally (stops, exits, trailing). No strategy logic in any client.

### 4. LLM Training Is Continuous
The hardest problem: keeping the LLM current as strategies evolve. The pipeline must support:
- **Incremental training** — add new strategy data without retraining from scratch
- **Full retraining** — retrain on everything when the model or approach changes
- **Model flexibility** — swap between Qwen 30B, 70B, or other base models
- **A/B comparison** — run multiple model versions in parallel to evaluate

### 5. Measure Everything, From Day One
Every layer of the system emits metrics — component-level (did the FVG detection work?), strategy-level (win rate, PF per strategy), data quality (schema compliance, completeness), LLM quality (day type accuracy pre vs post training), agent quality (are agents adding value over raw deterministic signals?), and system-level (net P&L, Sharpe, drawdown). All metrics flow to DuckDB. Evaluation gates block bad changes from reaching production. No change ships without a measurable comparison to the baseline. See the 6-layer evaluation table in [11-testing-and-automation.md](11-testing-and-automation.md).

### 6. Containerized and Automated
Every component runs in a container. Local development mirrors production. Strategy change → push → pipeline handles backtest, data gen, training, deployment.

### 7. Validated by Industry Precedent

| Our Pattern | Industry Precedent |
|-------------|-------------------|
| Advocate/Skeptic consensus | [TradingAgents](https://github.com/TradingAgents) (Columbia U, LangGraph multi-agent trading) |
| LoRA fine-tuning for finance | [FinGPT / FinLoRA](https://github.com/AI4Finance-Foundation/FinGPT) (Columbia U, validated on stock prediction) |
| Agent-based trading systems | [FinRL](https://github.com/AI4Finance-Foundation/FinRL) (Columbia U, RL for trading) |
| Structured retrieval over RAG | Common in financial systems (structured data > embeddings) |
| Self-learning reflection loop | Novel for trading, standard in ML experiment tracking |

---

## What Changes

| Today | After Refactor |
|-------|---------------|
| 6 repos, 2 divergent rockit-frameworks | 1 monorepo, 1 source of truth |
| Strategies in Python AND reimplemented in C# | Strategies only in Python, C# draws from API |
| No signals API (only a journal app) | Full signals API with annotations + trade setups |
| No dashboard (only a spec) | Dashboard consuming API |
| No Pine Script | TradingView thin client consuming API |
| Google Drive CSV sync → local LLM → manual upload | Direct GCS upload → automated pipeline |
| Manual training on Spark DGX | Automated training with model registry |
| One model (Qwen 2.5 14B), manual LoRA | Multi-model support (Qwen 30B/70B), incremental + full retrain |
| 12 deterministic modules (older copy) | 38 modules consolidated from standalone rockit-framework |

---

## Actual Codebase By the Numbers

| Metric | Value |
|--------|-------|
| Python strategies | 16 (9 Dalton core + 6 research + 1 neutral pass) |
| StrategyBase pattern | strategies emit signals, engine handles positions |
| Backtest sessions | 259 |
| Filter types | 5 (OrderFlow, Regime, Time, Trend, Volatility) in 7 files |
| rockit-framework modules (standalone) | 38 modules, 9,293 LOC |
| rockit-framework modules (in BookMap, older) | 12 modules, ~1,059 LOC |
| Training data | 252 JSONL files + 4 new-format + 43 xai-format |
| NinjaTrader C# files | 2 standalone strategies (923 LOC total, zero Python overlap) |
| TradingView Pine Script | 0 files (does not exist) |
| RockitUI implementation | 0 files (spec only) |
| RockitAPI | Journal CRUD app, not a signals API |
| Backtest engine files | 5 (backtest, execution, position, trade, equity) |
| Indicator files | 5 (ICT, SMT divergence, technical, IB width, value area) |
| Profile files | 6 (TPO, volume, DPOC, IB analysis, confluences, wick parade) |
| Research/diagnostic scripts | ~72 (23 studies + 34 diagnostics + 15 analysis) |

---

## Documents in This Proposal

| Document | Description |
|----------|-------------|
| [02-monorepo-structure.md](02-monorepo-structure.md) | Repository layout, package structure, dependency graph, file-by-file code mapping |
| [03-pipeline-mlops.md](03-pipeline-mlops.md) | Pipeline automation, MLOps, training pipeline with incremental/full retrain, LoRA strategy |
| [04-platform-abstraction.md](04-platform-abstraction.md) | Annotation protocol, NinjaTrader/TradingView client architecture |
| [05-data-ingestion.md](05-data-ingestion.md) | Live data ingestion redesign (replacing CSV/Google Drive) |
| [06-migration-plan.md](06-migration-plan.md) | Phased migration with realistic scope based on actual code |
| [07-code-mapping.md](07-code-mapping.md) | File-by-file mapping from actual repo contents to monorepo (detail appendix) |
| [08-agent-system.md](08-agent-system.md) | Complete agent architecture: LangGraph, Advocate/Skeptic/Orchestrator, self-learning loop, A/B testing, dashboard, multi-agent backtesting |
| [11-testing-and-automation.md](11-testing-and-automation.md) | Testing pyramid, baseline performance, automated MLOps retraining, Claude Code as autonomous developer |
| [12-deployment.md](12-deployment.md) | Deployment architecture: Docker Compose, agents as graph nodes, environment configs |
| [archive/FAQ-architecture.md](archive/FAQ-architecture.md) | Archived — 16 ADRs now incorporated into the docs above + Design Principle #7 |
