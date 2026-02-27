# Rockit Architecture Proposal — Overview

## Current State: What's Broken

Today, Rockit is split across 6 repositories with manual handoffs at every stage:

```
BookMapOrderFlowStudies (Research)       rockit-framework (Deterministic + Training)
  ├── 16 Python strategies                 ├── orchestrator.py (JSON snapshots)
  │   (Dalton day types, ICT, OF)          ├── 12 analysis modules
  ├── Backtest engine (259 sessions)       ├── analyze-today.py (live: downloads
  ├── Filter chain (5 filters)            │    CSV from Google Drive every 2 min,
  ├── Prop firm pipeline                   │    runs local LLM, uploads JSONL to GCS)
  ├── NinjaTrader C# strategies            ├── back-test.py (batch: 252 days × 30 snapshots)
  │   (DualOrderFlow_Evaluation.cs         └── Manual Spark DGX + LoRA training
  │    DualOrderFlow_Funded.cs)
  └── TradingView Pine Script           RockitDataFeed (Output Store)
        ↓ (manual translation)            ├── 252 JSONL files (1 year training data)
        ↓                                 └── local-analysis-format/ (live output)
  RockitAPI (GCP Cloud Run)                      ↓
        ↓                               NinjaTrader (live execution)
  RockitUI (Dashboard)                   (standalone C# — does NOT call API)
```

**Pain points:**
1. **Research-to-implementation churn** — 16 Python strategies must be manually translated when any tweak occurs
2. **Python ↔ NinjaTrader C# translation** — `DualOrderFlow_Evaluation.cs` re-implements order flow logic (delta, CVD, imbalance percentiles, signal detection) entirely in C#, standalone
3. **Backtest ≠ NinjaTrader performance** — two implementations (Python strategy logic vs C# signal logic) inevitably diverge
4. **ML training is manual** — SSH into DGX, run LoRA training, copy model artifacts
5. **Fragile data pipeline** — CSV dump → disk → Google Drive → `analyze-today.py` downloads every 2 min → local LLM → JSONL → GCS upload. Multiple failure points
6. **Duplicated computation** — IB calculation, volume profile, TPO, FVG detection exist in both BookMapOrderFlowStudies AND rockit-framework
7. **No single source of truth** — strategy logic, indicator computation, and data models are scattered across repos

---

## Proposed State: Unified Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                     RockitFactory Monorepo                       │
│                                                                 │
│  ┌──────────┐   ┌──────────────┐   ┌──────────┐   ┌─────────┐ │
│  │ rockit-   │   │ rockit-      │   │ rockit-  │   │ rockit- │ │
│  │ core      │──▶│ pipeline     │──▶│ train    │──▶│ serve   │ │
│  │           │   │              │   │          │   │         │ │
│  │ Strategy  │   │ Backtest     │   │ Data gen │   │ API     │ │
│  │ Signals   │   │ Evaluation   │   │ LoRA     │   │ Infra   │ │
│  │ Indicators│   │ Deterministic│   │ MLOps    │   │ Deploy  │ │
│  └──────────┘   └──────────────┘   └──────────┘   └─────────┘ │
│        │                                                │       │
│        │         ┌──────────────┐                       │       │
│        └────────▶│ rockit-      │◀──────────────────────┘       │
│                  │ clients      │                               │
│                  │              │                               │
│                  │ NinjaTrader  │                               │
│                  │ TradingView  │                               │
│                  │ Dashboard UI │                               │
│                  └──────────────┘                               │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ rockit-ingest  (live data ingestion)                      │   │
│  │ BookMap/Platform → GCS Bucket → Pub/Sub → Pipeline        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Design Principles

### 1. Single Source of Truth for Strategy Logic
All strategy definitions (Dalton auction theory, ICT liquidity, TPO, volume profile, BPR, FVG) live in `rockit-core` as Python modules. These are the canonical implementations used everywhere — backtesting, training data generation, live inference, and client visualization.

### 2. Write Once, Deploy Everywhere
Strategy logic is written once in Python. Platform-specific clients (NinjaTrader, TradingView) consume **output data** via API, never re-implement logic. This eliminates the Python → C# translation problem entirely.

### 3. Pipeline-First
Every stage — data ingestion, backtesting, training, deployment — is an automated pipeline step, not a manual operation. Changes flow from research to production through CI/CD.

### 4. Containerized and Cloud-Native
Every component runs in a container. Local development mirrors cloud deployment. GCP Cloud Run for serving, GCS for storage, Vertex AI for training orchestration.

---

## What Changes for the User

| Today | After Refactor |
|-------|---------------|
| Edit Python strategy → manually translate to C# → manually update API | Edit Python strategy → push → pipeline handles everything |
| CSV dump → Google Drive → manual cloud copy | Platform → GCS bucket direct upload (or streaming) |
| SSH into DGX → run training → copy model | Push config change → Vertex AI trains → model auto-deployed |
| Backtest in Python, different results in NinjaTrader | Same Python code runs backtest AND generates live signals |
| 5+ repos to maintain | 1 monorepo with shared libraries |

---

## Current Codebase By the Numbers

| Metric | Value |
|--------|-------|
| Python strategies | 16 (StrategyBase subclasses) |
| Backtest sessions | 259 |
| Backtest result | 283 trades, 55.5% WR, $19.5K net P&L, 1.58 PF |
| Core portfolio strategies | 7-8 (TrendBull, PDay, BDay, EdgeFade, IBHSweep, BearAccept, ORReversal, IBRetest) |
| Filter chain | 5 filters (OrderFlow, Regime, Time, Trend, Volatility) |
| rockit-framework modules | 12 analysis modules in orchestrator |
| Training data | 252 JSONL files (1 full year, ~30 snapshots/day) |
| NinjaTrader C# files | 2 (Evaluation + Funded mode, 500+ lines each) |
| TradingView indicators | 2 Pine Script files |
| Repos to maintain | 6 |

---

## Documents in This Proposal

| Document | Description |
|----------|-------------|
| [02-monorepo-structure.md](02-monorepo-structure.md) | Repository layout, package structure, dependency graph |
| [03-pipeline-mlops.md](03-pipeline-mlops.md) | Pipeline automation, MLOps, CI/CD design |
| [04-platform-abstraction.md](04-platform-abstraction.md) | NinjaTrader/TradingView client architecture, annotation protocol |
| [05-data-ingestion.md](05-data-ingestion.md) | Live data ingestion redesign (replacing CSV/Google Drive) |
| [06-migration-plan.md](06-migration-plan.md) | Phased migration from current repos to monorepo |
| [07-code-mapping.md](07-code-mapping.md) | Detailed file-by-file mapping from current repos to monorepo |
