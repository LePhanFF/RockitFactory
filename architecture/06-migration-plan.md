# Migration Plan

> **Revision 2** — Updated with realistic scope based on actual code inspection.
> Key corrections:
> - RockitUI and Pine Script are net-new builds, not migrations
> - NinjaTrader C# is a full rewrite (923 LOC discarded, ~300 LOC new)
> - Two rockit-framework copies must be reconciled first
> - RockitAPI journal functionality is absorbed into new signals API

## Phased Approach

Each phase delivers value on its own. You can pause between phases without losing progress.

---

## Phase 0: Foundation (Week 1-2)

**Goal:** Set up the monorepo skeleton and development environment.

### Tasks:
- [ ] Initialize monorepo structure in `RockitFactory`
- [ ] Set up `pyproject.toml` workspace with `uv`
- [ ] Create package skeletons (`rockit-core`, `rockit-train`, `rockit-serve`, `rockit-ingest`)
- [ ] Create `Makefile` with common commands
- [ ] Set up `docker-compose.yaml` for local dev
- [ ] Set up basic CI (lint + test) via GitHub Actions or Cloud Build
- [ ] Create `configs/` directory with strategy and instrument definitions

### Deliverable:
```bash
git clone RockitFactory
make setup    # Installs dependencies
make test     # Runs (empty) test suite
make serve    # Starts local API (hello world)
```

---

## Phase 1: Core Library — Strategies + Engine (Week 2-5)

**Goal:** Move the research codebase into `rockit-core` as a publishable library.

This is the biggest phase because `rockit-core` contains the most code. The good news: the BookMapOrderFlowStudies code is well-organized and can be moved largely as-is.

### Tasks:
- [ ] **Reconcile two rockit-framework copies** — The standalone repo (38 modules) is canonical. The copy inside BookMapOrderFlowStudies (12 modules) is discarded. Identify any unique logic in the older copy that needs merging.
- [ ] Move strategies from `BookMapOrderFlowStudies/strategy/` (16 strategies + base + signal + day_type + day_confidence) → `rockit-core/strategies/`
- [ ] Move engine from `BookMapOrderFlowStudies/engine/` (5 files) → `rockit-core/engine/`
- [ ] Move filters from `BookMapOrderFlowStudies/filters/` (7 files) → `rockit-core/filters/`
- [ ] Move indicators from `BookMapOrderFlowStudies/indicators/` (5 files) → `rockit-core/indicators/`
- [ ] Move profile from `BookMapOrderFlowStudies/profile/` (6 files) → `rockit-core/profile/`
- [ ] Move data loading from `BookMapOrderFlowStudies/data/` (3 files) → `rockit-core/data/`
- [ ] Move config from `BookMapOrderFlowStudies/config/` (2 files) → `rockit-core/config/`
- [ ] Move reporting from `BookMapOrderFlowStudies/reporting/` (4 files) → `rockit-core/reporting/`
- [ ] Move deterministic modules from `rockit-framework/modules/` (38 modules) → `rockit-core/deterministic/modules/`
- [ ] Move orchestrator from `rockit-framework/orchestrator.py` → `rockit-core/deterministic/orchestrator.py`
- [ ] Move snapshot schema from `rockit-framework/config/schema.json` → `rockit-core/deterministic/schema.json`
- [ ] Deduplicate shared modules (volume_profile, tpo_profile, fvg_detection, ib, etc. exist in both repos — keep the most complete version, ensure both backtest and orchestrator use the same code)
- [ ] Write unit tests for each strategy against known inputs
- [ ] Verify `make backtest STRATEGY=all` works end-to-end

### Validation:
- Run 259-session backtest through new `rockit-core` — results must match original BookMapOrderFlowStudies output exactly
- Run deterministic orchestrator — snapshots must match original rockit-framework output exactly
- Both backtest engine and deterministic orchestrator share the same indicator/profile code

### File counts being moved:
| Component | Files | Source |
|-----------|-------|--------|
| Strategies | 20 | BookMapOrderFlowStudies/strategy/ |
| Engine | 5 | BookMapOrderFlowStudies/engine/ |
| Filters | 7 | BookMapOrderFlowStudies/filters/ |
| Indicators | 5 | BookMapOrderFlowStudies/indicators/ |
| Profile | 6 | BookMapOrderFlowStudies/profile/ |
| Data | 3 | BookMapOrderFlowStudies/data/ |
| Config | 2 | BookMapOrderFlowStudies/config/ |
| Reporting | 4 | BookMapOrderFlowStudies/reporting/ |
| Deterministic modules | 38 | rockit-framework/modules/ |
| Orchestrator + schema | 2 | rockit-framework/ |
| **Total** | **~92 files** | |

---

## Phase 2: Data Ingestion (Week 5-6, can overlap with Phase 1)

**Goal:** Replace Google Drive sync with direct GCS upload.

### Tasks:
- [ ] Build `rockit-ingest` CSV file watcher (Option 1 from data ingestion doc)
- [ ] Set up GCS bucket for live data (`gs://rockit-data/live/`)
- [ ] Test watcher with NinjaTrader CSV exports
- [ ] Refactor `analyze-today.py` to read from GCS instead of Google Drive
- [ ] Deploy watcher on local trading machine
- [ ] Verify data flows from NinjaTrader → GCS within 5 seconds

### Validation:
- Monitor GCS bucket during a live session
- Confirm all CSV files arrive within expected latency
- Remove Google Drive from the workflow

---

## Phase 3: Signals API (Week 6-9)

**Goal:** Build the signals API that doesn't exist today. Absorb journal functionality from RockitAPI.

This is **net-new development**. The current RockitAPI is a journal CRUD app (FastAPI, JWT auth, GCS storage for journal entries). We keep its journal endpoints but build the signals/annotations layer on top.

### Tasks:
- [ ] Build FastAPI app in `rockit-serve` with annotation endpoints
- [ ] Implement deterministic inference (orchestrator.py runs server-side on incoming data)
- [ ] Define annotation JSON schema (zones, levels, signals, trade setups)
- [ ] Absorb journal endpoints from existing RockitAPI (`auth.py`, `storage.py`, journal routes)
- [ ] Add WebSocket support for real-time annotation streaming
- [ ] Add LLM inference endpoint (optional — can serve deterministic-only initially)
- [ ] Create Dockerfile and Cloud Run deployment config
- [ ] Deploy to staging on GCP Cloud Run
- [ ] Integration tests against staging API

### Validation:
- API returns correct annotations for historical sessions
- API returns correct annotations when fed live data
- Journal endpoints still work (backward compatibility with existing RockitAPI)
- WebSocket stream pushes updates within 1 second of new data

---

## Phase 4: Training Pipeline (Week 8-11, overlaps with Phase 3)

**Goal:** Automate ML training with support for incremental and full retraining.

### Tasks:
- [ ] Port training scripts from `rockit-framework` to `rockit-train`:
  - `generate_training_data_with_synthetic_output.py` → `dataset.py`
  - `generate_lora_training_data.py` → `trainer.py`
  - `train_lora_adapter.py` → integration into trainer
- [ ] Set up model registry in GCS
- [ ] Implement incremental LoRA training (train on new data, keep previous adapter)
- [ ] Implement full retrain (from base model with all data)
- [ ] Add multi-model support (Qwen 30B, 70B configs)
- [ ] Set up MLflow experiment tracking
- [ ] Add evaluation gates (model must beat current production)
- [ ] Configure pipeline: deterministic data → training JSONL → train → evaluate → register
- [ ] Test with `make train CONFIG=configs/training/qwen-30b.yaml MODE=incremental`

### Validation:
- Change a strategy → push → pipeline regenerates deterministic data → retrains → new model version
- Incremental training produces model that passes evaluation gates
- Full retrain with Qwen 70B completes successfully
- MLflow tracks all experiments with reproducible configs

---

## Phase 5: Platform Clients (Week 10-12)

**Goal:** Build thin clients that consume the signals API.

### NinjaTrader (Full Rewrite)
The current C# code (923 LOC of standalone order flow strategies) is **discarded**. New code:
- [ ] `RockitIndicator.cs` (~150 LOC) — draws annotations from API
- [ ] `RockitStrategy.cs` (~150 LOC) — fills trades from API setups, manages stops/trails locally
- [ ] Test in NinjaTrader Sim/Playback against API
- [ ] Verify annotations match what the API serves

### TradingView (Net-New)
No Pine Script exists today. Build from scratch:
- [ ] `rockit_indicator.pine` — webhook-driven annotation display
- [ ] Set up webhook integration with `rockit-serve`

### Dashboard (Net-New)
Only a spec document exists today. Build from scratch:
- [ ] React app consuming annotation API
- [ ] Session view: chart + annotations + trade setups
- [ ] Analysis view: deterministic summary + LLM commentary
- [ ] Deploy to Cloud Run

### Validation:
- NinjaTrader shows same annotations as dashboard (both consume same API)
- NinjaTrader strategy fills trades at prices API specifies
- All three clients display consistent information

---

## Phase 6: Retire Old Repos (Week 12+)

**Goal:** Archive original repositories, RockitFactory becomes the single source.

### Tasks:
- [ ] Run new system in parallel with old for 2+ weeks
- [ ] Confirm feature parity:
  - Backtest results match original
  - Deterministic snapshots match original
  - Training pipeline produces equivalent models
  - API serves correct data
- [ ] Archive BookMapOrderFlowStudies (read-only)
- [ ] Archive rockit-framework (read-only)
- [ ] Archive RockitAPI (absorbed into rockit-serve)
- [ ] Archive RockitDataFeed (data migrated to GCS)
- [ ] RockitUI was never built — nothing to archive
- [ ] Update all documentation

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Module deduplication breaks something | Compare outputs of both versions before choosing canonical one |
| Two rockit-framework reconciliation is complex | Start by identifying which modules exist in both; the standalone (38 modules) is the superset |
| NinjaTrader API latency too high for execution | Client-side caching of annotations; local stop/trail management; minimum 1 Cloud Run instance |
| LLM training on new model size fails on DGX | Start with Qwen 30B (fits in memory), validate before trying 70B |
| Building 3 clients (NT, TV, Dashboard) is a lot | Dashboard is MVP first; NinjaTrader second; TradingView is optional |

---

## What You Can Stop Doing After Each Phase

| After Phase | You Can Stop... |
|-------------|----------------|
| Phase 1 | Maintaining code in 3 repos (BookMap + rockit-framework + rockit-framework copy) |
| Phase 2 | Using Google Drive for data sync |
| Phase 3 | Running `analyze-today.py` manually; maintaining RockitAPI separately |
| Phase 4 | SSH-ing into DGX to train models manually |
| Phase 5 | Translating Python to C#; maintaining standalone NinjaTrader strategies |
| Phase 6 | Maintaining any of the old repos |
