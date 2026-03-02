# Phase 2: Data Ingestion — Detailed Roadmap

> **Goal:** Replace Google Drive CSV sync with direct GCS upload.
> **Duration:** Week 5-6 (can overlap with Phase 1)
> **Depends on:** Phase 0 (package skeleton)
> **Blocks:** Phase 3 (API needs data source)

---

## Tasks

### 2.1 Build CSV file watcher
- [ ] `rockit-ingest/collectors/csv_watcher.py` — watches NinjaTrader export directory
- [ ] Detect new/modified CSV files within 2 seconds
- [ ] Parse and validate CSV format (NinjaTrader volumetric)
- [ ] Emit data quality metrics (parse errors, missing fields, gaps)

### 2.2 GCS upload pipeline
- [ ] `rockit-ingest/publishers/gcs.py` — upload with retry and dedup
- [ ] Set up GCS bucket `gs://rockit-data/live/`
- [ ] Upload within 5 seconds of file detection
- [ ] Emit latency metrics

### 2.3 Refactor analyze-today.py
- [ ] Modify to read from GCS instead of Google Drive
- [ ] Remove Google Drive polling loop
- [ ] Keep JSONL output format unchanged

### 2.4 Deploy and validate
- [ ] Deploy watcher on local trading machine
- [ ] Monitor GCS bucket during a live session
- [ ] Confirm all CSV files arrive within expected latency
- [ ] Remove Google Drive from the workflow

---

## Definition of Done

- [ ] CSV → GCS within 5 seconds, measured and logged
- [ ] Data quality metrics emitted for every file processed
- [ ] Google Drive dependency removed
- [ ] Zero data loss over 5 consecutive trading sessions
