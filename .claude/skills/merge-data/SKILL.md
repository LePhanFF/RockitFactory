---
name: merge-data
description: Merge latest volumetric data from Google Drive into local sessions
allowed-tools: ["Bash", "Read"]
---

Merge the latest NinjaTrader volumetric CSV data from Google Drive into the local `data/sessions/` directory.

## Usage
- `/merge-data` — Merge all instruments (NQ, ES, YM)
- `/merge-data NQ` — Merge single instrument

## Steps

1. **Merge data** using SessionDataManager:
   ```bash
   uv run python -c "
   from rockit_core.data.manager import SessionDataManager
   mgr = SessionDataManager()
   mgr.merge_delta('NQ')
   mgr.merge_delta('ES')
   mgr.merge_delta('YM')
   "
   ```
   If a single instrument was specified, only merge that one.

2. **Report**:
   - How many new sessions were added per instrument
   - How many duplicate rows were removed
   - Total sessions and date range after merge
   - Whether Google Drive path was accessible

## Data Flow
- Delta source: `G:\My Drive\future_data\1min\{INSTRUMENT}_Volumetric_1.csv`
- Local storage: `data/sessions/{INSTRUMENT}_Volumetric_1.csv`
- Deduplication: on `['timestamp', 'instrument']` columns
