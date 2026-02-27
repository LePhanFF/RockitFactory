# Migration Plan

## Phased Approach

This migration is designed to be incremental. Each phase delivers value on its own, and you can pause between phases without losing progress.

---

## Phase 0: Foundation (Week 1-2)

**Goal:** Set up the monorepo skeleton and development environment.

### Tasks:
- [ ] Initialize monorepo structure in `RockitFactory`
- [ ] Set up `pyproject.toml` workspace with `uv`
- [ ] Create `rockit-core` package with empty module structure
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

## Phase 1: Core Library (Week 2-4)

**Goal:** Extract strategy logic into `rockit-core` as the single source of truth.

### Tasks:
- [ ] Define data models (`Candle`, `Session`, `Profile`, `Annotation`)
- [ ] Port strategy implementations from BookMapOrderFlowStudies:
  - [ ] `dalton_auction.py`
  - [ ] `ict_liquidity.py`
  - [ ] `tpo.py`
  - [ ] `volume_profile.py`
  - [ ] `bpr.py`
  - [ ] `fvg.py`
- [ ] Define the `Strategy` base class / protocol
- [ ] Write unit tests for each strategy against known inputs
- [ ] Port signal models (entry, risk, reward)

### Validation:
- Run strategies against same test data as original Python code
- Verify outputs match exactly

### What keeps working:
- Original repos still function — nothing breaks
- You're only building new, not tearing down old

---

## Phase 2: Pipeline (Week 4-6)

**Goal:** Port backtesting and deterministic data generation to `rockit-pipeline`.

### Tasks:
- [ ] Port backtest engine from BookMapOrderFlowStudies
- [ ] Port evaluation/reporting code
- [ ] Port deterministic data generator from rockit-framework
- [ ] Port data annotation code from rockit-framework
- [ ] Set up GCS bucket structure
- [ ] Create backtest CI step (runs on PR)
- [ ] Write regression tests comparing new pipeline output to old

### Validation:
- Run 259-session backtest through new pipeline
- Compare results to original BookMapOrderFlowStudies backtest output
- Results should match within acceptable tolerance

### Milestone:
```bash
make backtest STRATEGY=all   # 259 sessions, all strategies
make deterministic            # Generate deterministic data
# Both work locally and in CI
```

---

## Phase 3: Data Ingestion (Week 5-6, parallel with Phase 2)

**Goal:** Replace Google Drive sync with direct GCS upload.

### Tasks:
- [ ] Build `rockit-ingest` CSV file watcher
- [ ] Set up GCS bucket for live data (`gs://rockit-live-data/`)
- [ ] Test watcher with BookMap CSV exports
- [ ] Set up Eventarc trigger for new file notifications
- [ ] Deploy watcher on local trading machine
- [ ] Verify data flows from BookMap → GCS within 5 seconds

### Validation:
- Monitor GCS bucket during live session
- Confirm all CSV files arrive within expected latency
- Remove Google Drive from the workflow

---

## Phase 4: Serving (Week 6-8)

**Goal:** Deploy `rockit-serve` API with annotation protocol.

### Tasks:
- [ ] Build FastAPI app with annotation endpoints
- [ ] Implement deterministic inference (rule-based signals from core)
- [ ] Define annotation JSON schema
- [ ] Port existing RockitAPI endpoints to new structure
- [ ] Add WebSocket support for real-time streaming
- [ ] Create Dockerfile and Cloud Run deployment config
- [ ] Deploy to staging on GCP Cloud Run
- [ ] Integration tests against staging API

### Validation:
- API returns correct annotations for historical sessions
- API returns correct annotations for live data
- Compare API output to existing RockitAPI output

---

## Phase 5: Platform Clients (Week 8-10)

**Goal:** Replace complex NinjaTrader C# with thin API-consuming client.

### Tasks:
- [ ] Build `RockitIndicator.cs` (thin indicator that draws from API)
- [ ] Build `RockitStrategy.cs` (thin strategy that executes from API)
- [ ] Test in NinjaTrader Sim/Playback
- [ ] Compare NinjaTrader display to dashboard display (should match)
- [ ] Build TradingView Pine Script indicator (optional)
- [ ] Port dashboard UI from RockitUI to `rockit-clients/dashboard/`

### Validation:
- NinjaTrader shows same zones/levels as dashboard
- Strategy executes at same prices as API signals
- No strategy logic in C# code

### Key risk mitigation:
- Run old and new NinjaTrader indicators side-by-side in replay
- Compare entries/exits between old C# logic and new API-driven logic
- Only retire old indicators after confirming parity

---

## Phase 6: Training MLOps (Week 10-12)

**Goal:** Automate ML training pipeline.

### Tasks:
- [ ] Port training code from rockit-framework to `rockit-train`
- [ ] Set up model registry in GCS
- [ ] Build Vertex AI Pipeline (or DGX orchestrator)
- [ ] Set up MLflow experiment tracking
- [ ] Configure auto-trigger: new deterministic data → training run
- [ ] Add evaluation gates (model must beat baseline)
- [ ] Set up auto-deployment: good model → staging → production

### Validation:
- Change a strategy → push → pipeline trains → model deployed
- Full end-to-end cycle completes without manual SSH or file copying

---

## Phase 7: Retire Old Repos (Week 12+)

**Goal:** Archive original repositories, RockitFactory becomes the single source.

### Tasks:
- [ ] Run new system in parallel with old for 2+ weeks
- [ ] Confirm feature parity across all components
- [ ] Archive BookMapOrderFlowStudies (research + NinjaTrader branches)
- [ ] Archive rockit-framework
- [ ] Archive RockitAPI
- [ ] Archive RockitUI
- [ ] Update all documentation

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Strategy port introduces bugs | Compare outputs against original code, test with known inputs |
| NinjaTrader API latency too high | WebSocket mode for <50ms latency; can also run local cache |
| GCS upload fails during live trading | Local CSV fallback always active; upload retries with exponential backoff |
| Training pipeline too complex to set up | Start with manual trigger (`make train`), automate incrementally |
| Monorepo becomes unwieldy | Clear package boundaries; each package has independent tests and CI |

---

## What You Can Stop Doing After Each Phase

| After Phase | You Can Stop... |
|-------------|----------------|
| Phase 1 | Maintaining duplicate strategy logic |
| Phase 2 | Running backtests manually |
| Phase 3 | Using Google Drive for data sync |
| Phase 4 | Maintaining old RockitAPI separately |
| Phase 5 | Translating Python to C# |
| Phase 6 | SSH-ing into DGX to train models |
| Phase 7 | Maintaining 5+ separate repos |
