# Live Data Ingestion Redesign

## Current State: CSV + Google Drive

```
BookMap/Platform                    Cloud
─────────────────                   ─────
CSV dump to disk ──▶ Google Drive ──▶ Sync to cloud
(every 1 min)        (file sync)      (variable latency)
```

**Problems:**
- 1-minute resolution ceiling (batch by nature)
- Google Drive sync adds unpredictable latency (seconds to minutes)
- File-based sync is fragile (conflicts, partial writes, quota limits)
- No schema validation — bad data propagates silently
- Hard to scale or add new data sources
- No replay capability for debugging

---

## Proposed Options (from simplest to most robust)

### Option 1: Direct GCS Upload (Simplest — Start Here)

Replace Google Drive with direct uploads to GCS. Minimal change to existing workflow.

```
BookMap/Platform                        GCP
─────────────────                       ───
CSV dump to disk ──▶ Local watcher ──▶ GCS Bucket
(every 1 min)        (rockit-ingest)    (gs://rockit-live-data/)
                                            │
                                            ▼
                                        Cloud Function / Eventarc
                                            │
                                            ▼
                                        rockit-serve (processes new data)
```

```python
# packages/rockit-ingest/src/rockit_ingest/collectors/gcs_uploader.py
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from google.cloud import storage

class CSVUploader(FileSystemEventHandler):
    def __init__(self, bucket_name: str, prefix: str):
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.prefix = prefix

    def on_created(self, event):
        if not event.src_path.endswith('.csv'):
            return
        path = Path(event.src_path)
        # Wait for file to finish writing
        self._wait_for_stable(path)
        # Upload to GCS
        blob_name = f"{self.prefix}/{path.name}"
        blob = self.bucket.blob(blob_name)
        blob.upload_from_filename(str(path))
        print(f"Uploaded {path.name} → gs://{self.bucket.name}/{blob_name}")

    def _wait_for_stable(self, path: Path, timeout: float = 10.0):
        """Wait until file size stops changing."""
        prev_size = -1
        start = time.time()
        while time.time() - start < timeout:
            curr_size = path.stat().st_size
            if curr_size == prev_size and curr_size > 0:
                return
            prev_size = curr_size
            time.sleep(0.5)

def run_watcher(watch_dir: str, bucket: str, prefix: str):
    handler = CSVUploader(bucket, prefix)
    observer = Observer()
    observer.schedule(handler, watch_dir, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
```

**Pros:** Simple, reuses CSV workflow, 2-5 second end-to-end latency
**Cons:** Still file-based, still 1-minute batches

---

### Option 2: Direct API Push (Recommended)

Instead of writing CSVs, push data directly to the Rockit API over HTTP.

```
BookMap/Platform                        GCP
─────────────────                       ───
Local collector  ──▶  HTTPS POST  ──▶  rockit-serve
(rockit-ingest)       (every tick       (Cloud Run)
                       or every N sec)      │
                                            ├──▶ Process & compute signals
                                            ├──▶ Store to GCS (archival)
                                            └──▶ Push to WebSocket clients
```

```python
# packages/rockit-ingest/src/rockit_ingest/collectors/api_push.py
import csv
import time
import httpx
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class APIPusher(FileSystemEventHandler):
    """Watch for CSV files and push data directly to API."""

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.client = httpx.Client(
            base_url=api_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )

    def on_created(self, event):
        if not event.src_path.endswith('.csv'):
            return
        path = Path(event.src_path)
        self._wait_for_stable(path)
        rows = self._parse_csv(path)
        self._push_data(rows)

    def _parse_csv(self, path: Path) -> list[dict]:
        with open(path) as f:
            return list(csv.DictReader(f))

    def _push_data(self, rows: list[dict]):
        resp = self.client.post("/api/v1/ingest", json={"bars": rows})
        resp.raise_for_status()

    def _wait_for_stable(self, path: Path, timeout: float = 10.0):
        prev_size = -1
        start = time.time()
        while time.time() - start < timeout:
            curr_size = path.stat().st_size
            if curr_size == prev_size and curr_size > 0:
                return
            prev_size = curr_size
            time.sleep(0.5)
```

**Pros:** Data goes directly to processing, no intermediate storage hop, sub-second latency
**Cons:** Requires API to handle ingest (slightly more API complexity)

---

### Option 3: Pub/Sub Streaming (Most Scalable)

For future scaling, use GCP Pub/Sub as the data backbone:

```
BookMap/Platform           GCP Pub/Sub              Subscribers
─────────────────          ───────────              ───────────
Local collector ──HTTPS──▶ Topic: market-data ──▶  rockit-serve (signals)
                                              ──▶  GCS archiver (storage)
                                              ──▶  rockit-train (live eval)
```

```python
# packages/rockit-ingest/src/rockit_ingest/publishers/pubsub.py
from google.cloud import pubsub_v1
import json

class MarketDataPublisher:
    def __init__(self, project_id: str, topic_id: str):
        self.publisher = pubsub_v1.PublisherClient()
        self.topic_path = self.publisher.topic_path(project_id, topic_id)

    def publish_bars(self, instrument: str, bars: list[dict]):
        for bar in bars:
            data = json.dumps({
                "instrument": instrument,
                "timestamp": bar["timestamp"],
                "open": float(bar["open"]),
                "high": float(bar["high"]),
                "low": float(bar["low"]),
                "close": float(bar["close"]),
                "volume": int(bar["volume"]),
            }).encode("utf-8")

            future = self.publisher.publish(
                self.topic_path,
                data,
                instrument=instrument,
            )
            future.result()  # Block until published
```

**Pros:** Decoupled, multiple consumers, replay capability, scales infinitely
**Cons:** More infrastructure, higher complexity

---

## Recommended Migration Path

```
Phase 1 (Now)           Phase 2 (Next)           Phase 3 (Later)
─────────────           ──────────────           ────────────────
Option 1: GCS Upload    Option 2: API Push       Option 3: Pub/Sub
                                                 (only if needed)
- Keep CSV workflow     - Remove CSV dependency
- Replace Google Drive  - Direct HTTP push        - Full event streaming
- Add file watcher      - Sub-second latency      - Multi-consumer
- 2-5s latency          - Server-side archival     - Replay capability
```

**Start with Option 1** because it requires the least change to your existing BookMap setup. You just replace Google Drive with a local script that uploads to GCS. Then move to Option 2 when you're ready to eliminate CSV files entirely.

---

## Data Storage Layout (GCS)

```
gs://rockit-data/
├── live/                          # Real-time incoming data
│   ├── ES/
│   │   ├── 2024-01-15/
│   │   │   ├── 09-30.csv
│   │   │   ├── 09-31.csv
│   │   │   └── ...
│   │   └── 2024-01-16/
│   └── NQ/
│       └── ...
├── historical/                    # Curated historical data
│   ├── ES/
│   │   └── sessions.parquet       # Consolidated session data
│   └── NQ/
├── deterministic/                 # Generated deterministic data
│   ├── {commit_sha}/
│   │   └── output.parquet
│   └── latest -> {commit_sha}/
├── training/                      # Training datasets
│   ├── {run_id}/
│   │   ├── train.parquet
│   │   ├── val.parquet
│   │   └── test.parquet
│   └── latest -> {run_id}/
└── models/                        # Trained models
    ├── {version}/
    │   ├── model.safetensors
    │   └── metrics.json
    └── production -> {version}/
```

---

## Local Development Setup

For local development, the ingestion pipeline runs against a local directory or a local emulator:

```bash
# Watch a local directory and push to local API
python -m rockit_ingest.collectors.api_push \
  --watch-dir /path/to/bookmap/export/ \
  --api-url http://localhost:8000

# Or upload to GCS emulator
python -m rockit_ingest.collectors.gcs_uploader \
  --watch-dir /path/to/bookmap/export/ \
  --bucket rockit-live-data \
  --emulator-host localhost:9023
```
