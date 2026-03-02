# Memory — RockitFactory

## What This Project Is
RockitFactory is a planned monorepo to consolidate the Rockit quantitative trading platform. Currently in architecture/proposal phase — no code migrated yet.

## Source Repositories
| Repo | Branch | What's There |
|------|--------|-------------|
| BookMapOrderFlowStudies | `claude/research-evaluation-strategies-QcnQK` | 16 Python strategies, backtest engine, filters, prop firm pipeline |
| BookMapOrderFlowStudies | `feature/next-improvements` | NinjaTrader C# (DualOrderFlow_Evaluation.cs, DualOrderFlow_Funded.cs), TradingView Pine Script, diagnostics |
| rockit-framework | `claude-code-inference-simplification` | orchestrator.py, 12 analysis modules, analyze-today.py (live), back-test.py (batch), LoRA training |
| RockitDataFeed | `main` | 252 JSONL files (local-analysis/), xAI annotations (xai-analysis/), newer format (local-analysis-format/) |
| RockitAPI | `main` | GCP Cloud Run API |
| LePhanFF-RockitUI | `main` | 10,131 LOC React 19/TS/Vite/Tailwind dashboard. 12 tabs (Brief, Logic, Intraday, DPOC, Globex, Profile, TPO, Thinking, Coach, HTF Coach, Rockit Audit, Trade Idea). Gemini AI chat, journal CRUD via RockitAPI, Recharts charts, JWT auth, Express proxy, Dockerfile. Reads JSONL from GCS. |

## Key Architecture Insights
- The 16 strategies all inherit from `StrategyBase` and follow: `on_session_start()` → `on_bar()` → `on_session_end()`. Strategies EMIT signals, backtest engine handles execution.
- Day type classification (Dalton) is THE primary filter — 80-82% WR with day type vs 44-56% without.
- NinjaTrader C# strategies are currently **standalone** — they re-implement order flow logic in C# and do NOT call the API. This is the biggest source of churn.
- `analyze-today.py` is the real-time pipeline: downloads CSV from Google Drive every 2 min → orchestrator generates deterministic JSON → local LLM produces analysis → JSONL uploaded to GCS.
- `back-test.py` generates batch training data: 252 days × 30 time slices = ~7,500 JSONL training examples.
- Training uses LoRA fine-tuning on Spark DGX hardware, served via vLLM at localhost:8001.
- Two LLM backends: local fine-tuned (port 8001) and GLM-4.7-Flash (port 8356).

## Current Pain Points (User's Words)
- "As I iterate from research to implementation, it is taking too much churn"
- "The most painful aspect is having to translate python code into ninja code and churn / maintain it"
- "Any tweak update from research, we have to go through the whole code update in separate repos"
- Live data via "csv dump into disk every 1 min and then use google drive to sync to cloud"

## Development Preferences
- **Local-first**: All containers run locally during development (Docker Compose). No GCP dependency for iteration. GCP is production only.

## Proposed Solution Summary
1. **Monorepo** with 6 packages: rockit-core, rockit-pipeline, rockit-train, rockit-serve, rockit-ingest, rockit-clients
2. **Annotation protocol** — NinjaTrader/TradingView become thin renderers consuming API JSON
3. **Direct GCS upload** — replace Google Drive sync
4. **Automated MLOps** — Vertex AI or DGX orchestrator for training pipeline
5. **7-phase migration** — incremental, each phase delivers value independently

## Session Notes
- GitHub connector "All repositories" was set but proxy only authorizes RockitFactory in web sessions. User may need to try locally for full repo access.
- BookMapOrderFlowStudies and RockitDataFeed were accessible via GitHub API (public repos).
- Private repos (rockit-framework standalone, RockitAPI) were not accessible in early sessions. RockitUI was reviewed locally — it's a full 10K LOC React app (not a spec).
