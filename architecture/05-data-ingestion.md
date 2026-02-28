# Live Data Ingestion Redesign

> **Revision 2** — Updated after inspecting actual `analyze-today.py` (500+ lines) in rockit-framework
> and confirming RockitAPI is a journal app, not a signals API.

## Current State: What Actually Runs Today

From inspecting `rockit-framework/analyze-today.py`:

```
NinjaTrader (exports 1-min OHLCV+volumetric CSV for NQ/ES/YM)
    │
    ▼
Google Drive (CSV hosting — unreliable sync)
    │
    ▼
analyze-today.py (downloads CSVs from Google Drive every 2 min)
    │
    ├──▶ orchestrator.py (38 modules → deterministic JSON snapshot)
    │        ├── premarket.py (Asia/London/ON levels, compression, SMT)
    │        ├── ib_location.py (IB range, price vs IB, technicals)
    │        ├── volume_profile.py (POC/VAH/VAL/HVN/LVN, current + prior days)
    │        ├── tpo_profile.py (TPO shape, fattening zones, single prints)
    │        ├── dpoc_migration.py (30-min DPOC slices, migration direction)
    │        ├── wick_parade.py (bullish/bearish wick counts, 60-min window)
    │        ├── ninety_min_pd_arrays.py (premium/discount, expansion status)
    │        ├── fvg_detection.py (daily/4H/1H/90min FVGs)
    │        ├── globex_va_analysis.py (80% rule)
    │        ├── twenty_percent_rule.py (IB extension breakout)
    │        ├── va_edge_fade.py (VA poke-and-fail setups)
    │        ├── core_confluences.py (boolean signal confluences from all above)
    │        ├── inference_engine.py (8 high-priority deterministic rules)
    │        ├── decision_engine.py (day type classification)
    │        ├── cri.py (Contextual Readiness Index)
    │        ├── dalton.py (trend strength quantification)
    │        ├── playbook_engine.py (10 fundamental playbooks)
    │        ├── balance_classification.py, mean_reversion_engine.py
    │        ├── or_reversal.py, edge_fade.py
    │        └── + more modules (38 total, 9,293 LOC)
    │
    ├──▶ Local LLM (localhost:8001, Qwen 2.5 14B with LoRA)
    │        └── Produces ROCKIT v5.6 analysis
    │            (day type, LANTO model, bias, key levels, confidence, one-liner)
    │
    └──▶ JSONL output {input: snapshot, output: llm_analysis}
             │
             ▼
         GCS bucket "rockit-data" (uploaded incrementally after each LLM call)
             │
             ▼
         RockitAPI (journal CRUD app — does NOT serve this data to clients)
         NinjaTrader (standalone C# — does NOT consume this data)
```

**The actual problems:**
1. **Google Drive sync** — Adds seconds to minutes of unpredictable latency. Sometimes files don't sync.
2. **2-minute polling** — `analyze-today.py` downloads CSVs every 2 minutes, so signals are always at least 2 minutes stale.
3. **Single script, single point of failure** — If `analyze-today.py` crashes during market hours, everything stops. No automatic restart.
4. **Two LLM backends** — `analyze-today.py` uses port 8001, `analyze-today-glm.py` uses port 8356. No unified config.
5. **No consumers** — The JSONL output goes to GCS but nothing reads it in real-time. RockitAPI is a journal app. NinjaTrader runs its own standalone strategies.
6. **No schema validation** — Bad CSV data or LLM hallucinations propagate into training data silently.
7. **No replay** — Can't re-run a past session's analysis. No event sourcing.

---

## Proposed Options (Simplest to Most Robust)

### Option 1: Direct GCS Upload (Start Here)

Replace Google Drive with a local file watcher that uploads CSVs directly to GCS. Minimal change to existing workflow.

```
NinjaTrader CSV export                     GCP
────────────────────                       ───
CSV dump to disk ──▶ rockit-ingest ──▶ GCS bucket (gs://rockit-live/)
(every 1 min)       (file watcher)             │
                                               ▼
                                          Eventarc trigger
                                               │
                                               ▼
                                          rockit-serve (runs orchestrator
                                           + optional LLM → annotations)
                                               │
                                     ┌─────────┼─────────┐
                                     ▼         ▼         ▼
                               NinjaTrader  TradingView  Dashboard
                               (API client) (webhooks)   (React)
```

```python
# packages/rockit-ingest/src/rockit_ingest/collectors/csv_watcher.py
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from google.cloud import storage
import time

class CSVUploader(FileSystemEventHandler):
    def __init__(self, bucket_name: str, prefix: str):
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.prefix = prefix

    def on_modified(self, event):
        """Trigger on modify (NinjaTrader appends to existing CSV)."""
        if not event.src_path.endswith('.csv'):
            return
        path = Path(event.src_path)
        self._wait_for_stable(path)
        blob_name = f"{self.prefix}/{path.name}"
        blob = self.bucket.blob(blob_name)
        blob.upload_from_filename(str(path))

    def _wait_for_stable(self, path: Path, timeout: float = 10.0):
        """Wait until file size stops changing (NinjaTrader done writing)."""
        prev_size = -1
        start = time.time()
        while time.time() - start < timeout:
            curr_size = path.stat().st_size
            if curr_size == prev_size and curr_size > 0:
                return
            prev_size = curr_size
            time.sleep(0.5)
```

**Pros:** Dead simple, reuses CSV workflow, 2-5 second latency, no Google Drive
**Cons:** Still file-based, still batch (1-minute granularity)

### Option 2: Direct API Push (Recommended Next Step)

Instead of uploading CSVs, push data directly to the signals API:

```
NinjaTrader CSV export                     GCP
────────────────────                       ───
CSV dump to disk ──▶ rockit-ingest ──▶ HTTPS POST ──▶ rockit-serve
(every 1 min)       (watcher + parser)    /api/v1/ingest    │
                                                             ├──▶ Run orchestrator (38 modules)
                                                             ├──▶ Optional LLM inference
                                                             ├──▶ Generate annotations + setups
                                                             ├──▶ Push to WebSocket clients
                                                             └──▶ Archive to GCS
```

```python
# packages/rockit-ingest/src/rockit_ingest/collectors/api_push.py
import csv
import httpx
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class APIPusher(FileSystemEventHandler):
    def __init__(self, api_url: str, api_key: str):
        self.client = httpx.Client(
            base_url=api_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    def on_modified(self, event):
        if not event.src_path.endswith('.csv'):
            return
        path = Path(event.src_path)
        self._wait_for_stable(path)
        # Parse new rows since last push
        rows = self._parse_new_rows(path)
        if rows:
            self.client.post("/api/v1/ingest", json={
                "instrument": self._instrument_from_filename(path.name),
                "bars": rows,
            })
```

**Pros:** Sub-second end-to-end, server processes immediately, archives automatically
**Cons:** Requires the signals API to exist (it doesn't today)

### Option 3: Pub/Sub Streaming (Future — Only If Needed)

For multi-consumer scenarios or if latency becomes critical:

```
Local collector ──HTTPS──▶ GCP Pub/Sub topic ──▶ rockit-serve (signals)
                                              ──▶ GCS archiver (storage)
                                              ──▶ rockit-train (live eval)
```

**Pros:** Decoupled, replay-capable, infinite scale
**Cons:** More infrastructure than needed right now

---

## Migration Path

```
Phase 1 (Now)              Phase 2 (With API)          Phase 3 (If Needed)
──────────────              ──────────────────          ────────────────────
Option 1: GCS Upload        Option 2: API Push          Option 3: Pub/Sub

- Keep CSV workflow         - Remove CSV dependency     - Full event streaming
- Replace Google Drive      - Direct HTTP push          - Multi-consumer
  with file watcher → GCS   - Sub-second latency        - Replay capability
- 2-5s latency             - Server-side archival
- analyze-today.py refactored
  to read from GCS instead
  of Google Drive
```

**Start with Option 1** because:
1. It requires the least change to the existing BookMap/NinjaTrader setup
2. The signals API doesn't exist yet, so Option 2 isn't possible immediately
3. You can validate the GCS pipeline while building the API in parallel

---

## Data Storage Layout (GCS)

```
gs://rockit-data/
├── live/                              # Real-time incoming data
│   ├── NQ/
│   │   └── 2025-01-15/
│   │       ├── NQ_Volumetric_1.csv    # Raw from NinjaTrader
│   │       └── snapshots/
│   │           ├── 09-30.json         # Deterministic snapshot
│   │           ├── 09-35.json
│   │           └── ...
│   ├── ES/
│   └── YM/
│
├── historical/                        # Curated historical data
│   └── csv/                           # Consolidated CSV archive
│
├── deterministic/                     # Generated deterministic snapshots
│   ├── {commit_sha}/                  # Version-tagged by code version
│   │   └── {session_date}/
│   │       └── snapshots.jsonl
│   └── latest -> {commit_sha}/
│
├── training/                          # Training datasets
│   ├── local-analysis/                # Existing 252 days (migrated from RockitDataFeed)
│   ├── xai-analysis/                  # Existing 43 days (migrated from RockitDataFeed)
│   ├── {run_id}/
│   │   ├── train.jsonl
│   │   ├── val.jsonl
│   │   └── test.jsonl
│   └── latest -> {run_id}/
│
├── models/                            # Trained models
│   ├── qwen-30b/
│   │   ├── v001/
│   │   └── production -> v001/
│   └── qwen-70b/
│       └── ...
│
├── config/                            # App configs (from existing RockitAPI)
│   └── users.json
│
└── journals/                          # Trading journals (from existing RockitAPI)
    └── {username}/
        └── YYYY-MM-DD.json
```

---

## Local Development

```bash
# Watch a local directory and upload to GCS (Option 1)
python -m rockit_ingest.collectors.csv_watcher \
  --watch-dir "C:/Users/lehph/NinjaTrader/export/" \
  --bucket rockit-data \
  --prefix live/NQ/$(date +%Y-%m-%d)

# Watch and push to local API (Option 2, once API exists)
python -m rockit_ingest.collectors.api_push \
  --watch-dir "C:/Users/lehph/NinjaTrader/export/" \
  --api-url http://localhost:8000

# Replay a historical session through the pipeline
python -m rockit_core.deterministic.orchestrator \
  --csv data/raw_csv/NQ_Volumetric_1.csv \
  --date 2025-01-02 \
  --output data/json_snapshots/
```
