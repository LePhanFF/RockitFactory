---
name: generate-snapshot
description: Generate deterministic analysis snapshot for a session
allowed-tools: ["Bash", "Read"]
---

Generate a deterministic snapshot using the orchestrator.

## Usage
- `/generate-snapshot 2026-01-15` — Generate snapshot for a specific date
- `/generate-snapshot 2026-01-15 11:45` — Generate snapshot at specific time

## Steps
1. Verify CSV data exists for the date
2. Run orchestrator:
   ```
   uv run python -m rockit_core.deterministic.orchestrator \
     --csv data/raw_csv/NQ_Volumetric_1.csv \
     --date {date} \
     --time {time or "all"} \
     --output data/json_snapshots/
   ```
3. Validate output against schema: `uv run python -m rockit_core.deterministic.schema_validator --input {output_file}`
4. Display key fields: day_type, bias, confidence, IB range, CRI status, matched playbook
