# RockitFactory

## Project Overview
RockitFactory is a monorepo refactoring of the Rockit quantitative trading platform. It consolidates 6 separate repositories into a unified pipeline for research, backtesting, ML training, inference, and live trading.

## Current State
This repo currently contains the architecture proposal for the refactoring (Revision 2 — based on local inspection of all 6 source repos). No code has been migrated yet.

### Architecture Proposal
See `architecture/` for the full proposal:
- `01-overview.md` — Actual repo state, problem statement, proposed solution
- `02-monorepo-structure.md` — Monorepo layout with all packages
- `03-pipeline-mlops.md` — CI/CD, MLOps, incremental/full retrain, multi-model support
- `04-platform-abstraction.md` — Annotation protocol for NinjaTrader/TradingView
- `05-data-ingestion.md` — Replacing CSV/Google Drive with GCS/API push
- `06-migration-plan.md` — 6-phase migration with validation gates
- `07-code-mapping.md` — File-by-file mapping from actual repo contents

### Source Repositories (to be consolidated)
- **BookMapOrderFlowStudies** — 16 Python strategies (9 Dalton core + 6 research + 1 neutral), backtest engine (5 files), filter chain (7 files), indicators (5 files), profile (6 files), reporting (4 files). Also has 2 standalone NinjaTrader C# strategies (zero overlap with Python — will be discarded). No Pine Script exists.
- **rockit-framework** (standalone) — 38 deterministic analysis modules (9,293 LOC), orchestrator.py, analyze-today.py (live LLM inference), 3 training data generators. This is the canonical version — an older copy (12 modules) exists inside BookMapOrderFlowStudies.
- **RockitDataFeed** — 105 JSONL files across 3 formats (local-analysis, local-analysis-format, xai-analysis)
- **RockitAPI** — FastAPI journal CRUD app (NOT a signals API). JWT auth, GCS storage. To be absorbed into rockit-serve.
- **RockitUI** — Only a spec document (prompt/project-design.md). No implementation code.

## Domain Context
- **Trading framework**: Dalton Market Profile / Auction Market Theory
- **Instruments**: NQ, MNQ, ES, MES, YM, MYM futures
- **Strategies**: 16 strategies based on day type classification (Trend, P-Day, B-Day, Neutral, etc.)
- **Key principle**: "Strategies emit signals, they do NOT manage positions" (StrategyBase design)
- **API principle**: "API provides instructions (annotations + trade setups), clients execute"
- **Core portfolio**: TrendBull, PDay, BDay, EdgeFade, IBHSweep, BearAccept, ORReversal, IBRetest
- **Backtest**: 259 sessions, 283 trades, 55.5% WR, 1.58 PF
- **Training data**: JSONL format with {input: deterministic_snapshot, output: ROCKIT_v5.6_analysis}

## Tech Stack
- **Python** — Core strategy logic, backtesting, deterministic analysis (38 modules), ML training
- **C# (NinjaTrader 8)** — Currently standalone order flow strategies (to be replaced with thin API client)
- **Pine Script (TradingView)** — Does not exist yet (to be built as thin API client)
- **GCP** — Cloud Run (API), GCS (storage), Vertex AI (training)
- **ML** — LoRA fine-tuning on Spark DGX, multi-model support (Qwen 30B/70B), incremental + full retrain

## Key Design Decisions
1. **Single source of truth**: All strategy logic, backtest engine, deterministic modules live in `rockit-core` Python package
2. **rockit-core is a publishable library**: Other packages (train, serve, ingest) import it
3. **Annotation protocol**: API serves annotations (what to draw) and trade setups (what to trade). Clients render and execute. No strategy logic in clients.
4. **Pipeline-first**: Research → backtest → deterministic data → training → deployment is automated
5. **Multi-model training**: Support incremental LoRA (new data only) and full retrain (new base model). Qwen 30B, 70B, etc.
6. **Direct data upload**: Replace Google Drive sync with GCS direct upload or API push

## Conventions
- Python 3.11+, managed with `uv` workspaces
- Package structure: `packages/{name}/src/{name}/`
- Tests alongside each package: `packages/{name}/tests/`
- Infrastructure as code in `infra/terraform/`
- Strategy configs in `configs/`
