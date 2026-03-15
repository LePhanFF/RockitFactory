# RockitFactory

## Project Overview
RockitFactory is a monorepo refactoring of the Rockit quantitative trading platform. It consolidates 6 separate repositories into a unified pipeline for research, backtesting, ML training, inference, and live trading.

## Current State
Core library (`rockit-core`) is functional with backtest engine, 38 deterministic modules, strategy runner, and snapshot generator. Training pipeline (V1) generates LLM training pairs from snapshots. Tape reading intelligence design is in progress.

### Architecture & Design
See `architecture/` for the full proposal:
- `01-overview.md` — Actual repo state, problem statement, proposed solution
- `02-monorepo-structure.md` — Monorepo layout with all packages
- `03-pipeline-mlops.md` — CI/CD, MLOps, incremental/full retrain, multi-model support
- `04-platform-abstraction.md` — Annotation protocol for NinjaTrader/TradingView
- `05-data-ingestion.md` — Replacing CSV/Google Drive with GCS/API push
- `06-migration-plan.md` — 6-phase migration with validation gates
- `07-code-mapping.md` — File-by-file mapping from actual repo contents
- `08-agent-system.md` — Evidence-gathering agent architecture (Rev 3): observers → pattern miner → Advocate/Skeptic debate → Orchestrator decision
- `11-testing-and-automation.md` — Testing pyramid, baseline system, MLOps pipeline
- `12-deployment.md` — Docker Compose deployment, environment configs
- `14-bridge-deterministic-strategies.md` — Bridge: deterministic ↔ strategy integration
- `15-llm-training-pipeline.md` — Qwen3.5-35B-A3B LoRA training pipeline (Rev 2)

See `brainstorm/` for active design work:
- `07-augmenting-training-tape-reading-intelligence.md` — **Active whiteboard** (2100+ lines): tape reading intelligence, first-hour precision framework, 8 strategy observations, continuous evidence loop, DuckDB schema, agent pipeline, Two Hour Trader options overlay

### Source Repositories (to be consolidated)
- **BookMapOrderFlowStudies** — 16 Python strategies (9 Dalton core + 6 research + 1 neutral), backtest engine (5 files), filter chain (7 files), indicators (5 files), profile (6 files), reporting (4 files). Also has 2 standalone NinjaTrader C# strategies (zero overlap with Python — will be discarded). No Pine Script exists.
- **rockit-framework** (standalone) — 38 deterministic analysis modules (9,293 LOC), orchestrator.py, analyze-today.py (live LLM inference), 3 training data generators. This is the canonical version — an older copy (12 modules) exists inside BookMapOrderFlowStudies.
- **RockitDataFeed** — 105 JSONL files across 3 formats (local-analysis, local-analysis-format, xai-analysis)
- **RockitAPI** — FastAPI journal CRUD app (NOT a signals API). JWT auth, GCS storage. To be absorbed into rockit-serve.
- **RockitUI** (LePhanFF-RockitUI) — 10,131 LOC React 19 + TypeScript + Vite + Tailwind dashboard. 12 analysis tabs (Brief, Logic, Intraday, DPOC, Globex, Profile, TPO, Thinking, Coach, HTF Coach, Rockit Audit, Trade Idea), Gemini AI chat, journal CRUD (via RockitAPI), Recharts visualizations, JWT auth, Express proxy server, Dockerfile. Reads JSONL snapshots directly from GCS (`gs://rockit-data`). Production-deployed but standalone — no integration with strategy/agent pipeline yet.

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
- **Agentic framework** — LangGraph for multi-agent orchestration (Advocate/Skeptic/Orchestrator)
- **Local LLM** — Qwen3.5 via Ollama (dev/Mac Mini) or vLLM (prod/DGX) for real-time agent inference
- **Reflection LLM** — Opus 4.6 via Anthropic API for meta-reviews every 1-3 days
- **Structured retrieval** — DuckDB for historical context (Historian agent), not vector RAG

## Key Design Decisions
0. **LLM = analyst/tape reader, NOT trader**: Strategy signals trigger trades. LLM reads the tape, interprets market structure, builds evidence. Agents (Advocate/Skeptic/Orchestrator) make the trade decision.
1. **Single source of truth**: All strategy logic, backtest engine, deterministic modules live in `rockit-core` Python package
2. **rockit-core is a publishable library**: Other packages (train, serve, ingest) import it
3. **Annotation protocol**: API serves annotations (what to draw) and trade setups (what to trade). Clients render and execute. No strategy logic in clients.
4. **Pipeline-first**: Research → backtest → deterministic data → training → deployment is automated
5. **Multi-model training**: Support incremental LoRA (new data only) and full retrain (new base model). Qwen 30B, 70B, etc.
6. **Direct data upload**: Replace Google Drive sync with GCS direct upload or API push
7. **Three-tier model strategy**: Tier 0 = deterministic Python (80% of work, <10ms), Tier 1 = Qwen3.5 local (agent debates, real-time), Tier 2 = Opus 4.6 API (design, meta-review, backtesting analysis)
8. **One model, one LoRA**: Single Qwen3.5 + single LoRA adapter trained on all Rockit data. Agent role differentiation via system prompts, not separate models
9. **Self-learning loop**: Daily reflection (Qwen3.5 post-market), multi-day meta-review (Opus 4.6), A/B testing for prompt/param changes, auto-rollback on performance regression
10. **Structured retrieval over RAG**: DuckDB queries for historical context, not vector embeddings. Add embeddings only in Phase 2 if needed
11. **Version-controlled agent behavior**: All prompts, parameters, and configs versioned in git with changelogs. Branches for experiments, auto-rollback guards
12. **LangGraph for orchestration**: Graph-based agent workflow with conditional routing, state management, streaming to dashboard, and backtest replay
13. **Caution over conviction**: LLM recommends retracement entry, never chases, warns about balance day traps. At extremes: "wait for pullback" not "chase this move"
14. **First hour is the money**: 9:30-10:30 precision framework. OR Rev (64.4% WR, 2.96 PF) + OR Acceptance fire here. Good first hour = don't trade after 11:00
15. **8 tape observations**: OR Rev, OR Accept, 80P, 20P, B-Day/Edge Fade, Trend Following, Mean Reversion (regime-gated), Two Hour Trader (options overlay)
16. **Single-process runtime**: Strategy runner (1-min) + orchestrator (5-min) + agent pipeline + DuckDB — no external queues, no Redis, no Kafka

## Conventions
- Python 3.11+, managed with `uv` workspaces
- Package structure: `packages/{name}/src/{name}/`
- Tests alongside each package: `packages/{name}/tests/`
- Infrastructure as code in `infra/terraform/`
- Strategy configs in `configs/`
- **Local-first development**: All containers run locally via Docker Compose during development. No GCP dependency for dev/iteration — GCP is production only. This means local DuckDB (not Cloud SQL), local filesystem or MinIO (not GCS), local Ollama (not Vertex AI), local API (not Cloud Run). Fast iteration > cloud fidelity.
