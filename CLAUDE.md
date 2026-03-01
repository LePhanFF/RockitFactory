# RockitFactory

## Project Overview
RockitFactory is a monorepo refactoring of the Rockit quantitative trading platform. It consolidates 6 separate repositories into a unified pipeline for research, backtesting, ML training, inference, and live trading.

## Current State
This repo currently contains the architecture proposal for the refactoring. No code has been migrated yet.

### Architecture Proposal
See `architecture/` for the full proposal:
- `01-overview.md` — Problem statement, proposed solution, design principles
- `02-monorepo-structure.md` — Monorepo layout with all packages
- `03-pipeline-mlops.md` — CI/CD, MLOps, training pipeline automation
- `04-platform-abstraction.md` — Annotation protocol for NinjaTrader/TradingView
- `05-data-ingestion.md` — Replacing CSV/Google Drive with GCS/API push
- `06-migration-plan.md` — 7-phase migration with validation gates
- `07-code-mapping.md` — File-by-file mapping from current repos
- `08-self-learning.md` — Self-learning reflection loop, daily/multi-day review cycles, A/B testing, version control for agent behavior
- `09-agent-dashboard.md` — Agent monitoring dashboard for ops visibility into debates, signals, performance, and self-learning
- `10-backtest-and-training.md` — Multi-agent backtesting (90-day replay), LoRA training strategy, agentic framework (LangGraph)
- `11-testing-and-automation.md` — Testing pyramid (unit/integration/agent/live), baseline performance system, automated MLOps retraining pipeline, Claude Code as autonomous developer
- `12-deployment.md` — Deployment architecture: Docker Compose (not Kubernetes), agents as LangGraph nodes (not containers), environment configs (dev/prod/cloud)

### Source Repositories (to be consolidated)
- **BookMapOrderFlowStudies** — 16 Python strategies (Dalton day types, ICT, order flow), backtest engine, NinjaTrader C# strategies, TradingView Pine Script
- **rockit-framework** — Deterministic data generation (orchestrator.py + 12 analysis modules), LLM inference pipeline (analyze-today.py), batch training data generation
- **RockitDataFeed** — JSONL training/inference output (~252 days × 30 snapshots)
- **RockitAPI** — GCP Cloud Run API serving deterministic + LLM analysis
- **RockitUI** — Dashboard for trading signals and analysis display

## Domain Context
- **Trading framework**: Dalton Market Profile / Auction Market Theory
- **Instruments**: NQ, MNQ, ES, MES, YM, MYM futures
- **Strategies**: 16 strategies based on day type classification (Trend, P-Day, B-Day, Neutral, etc.)
- **Key principle**: "Strategies emit signals, they do NOT manage positions" (StrategyBase design)
- **Core portfolio**: TrendBull, PDay, BDay, EdgeFade, IBHSweep, BearAccept, ORReversal, IBRetest
- **Backtest**: 259 sessions, 283 trades, 55.5% WR, 1.58 PF
- **Training data**: JSONL format with {input: deterministic_snapshot, output: ROCKIT_v5.6_analysis}

## Tech Stack
- **Python** — Core strategy logic, backtesting, data generation, ML training
- **C# (NinjaTrader 8)** — Live execution (currently standalone, to become thin API client)
- **Pine Script (TradingView)** — Visual indicators
- **GCP** — Cloud Run (API), GCS (storage), Vertex AI (training)
- **ML** — LoRA fine-tuning on Spark DGX, vLLM serving
- **Agentic framework** — LangGraph for multi-agent orchestration (Advocate/Skeptic/Orchestrator)
- **Local LLM** — Qwen3.5 via Ollama (dev/Mac Mini) or vLLM (prod/DGX) for real-time agent inference
- **Reflection LLM** — Opus 4.6 via Anthropic API for meta-reviews every 1-3 days
- **Structured retrieval** — DuckDB for historical context (Historian agent), not vector RAG

## Key Design Decisions
1. **Single source of truth**: All strategy logic lives in `rockit-core` Python package
2. **Annotation protocol**: NinjaTrader/TradingView become thin API consumers that draw from JSON annotations — no strategy logic in C#
3. **Pipeline-first**: Research → backtest → deterministic data → training → deployment is automated
4. **Direct data upload**: Replace Google Drive sync with GCS direct upload or API push
5. **Three-tier model strategy**: Tier 0 = deterministic Python (80% of work, <10ms), Tier 1 = Qwen3.5 local (agent debates, real-time), Tier 2 = Opus 4.6 API (design, meta-review, backtesting analysis)
6. **One model, one LoRA**: Single Qwen3.5 + single LoRA adapter trained on all Rockit data. Agent role differentiation via system prompts, not separate models
7. **Self-learning loop**: Daily reflection (Qwen3.5 post-market), multi-day meta-review (Opus 4.6), A/B testing for prompt/param changes, auto-rollback on performance regression
8. **Structured retrieval over RAG**: DuckDB queries for historical context, not vector embeddings. Add embeddings only in Phase 2 if needed
9. **Version-controlled agent behavior**: All prompts, parameters, and configs versioned in git with changelogs. Branches for experiments, auto-rollback guards
10. **LangGraph for orchestration**: Graph-based agent workflow with conditional routing, state management, streaming to dashboard, and backtest replay

## Conventions
- Python 3.11+, managed with `uv` workspaces
- Package structure: `packages/{name}/src/{name}/`
- Tests alongside each package: `packages/{name}/tests/`
- Infrastructure as code in `infra/terraform/`
- Strategy configs in `configs/`
