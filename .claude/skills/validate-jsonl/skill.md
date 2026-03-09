---
name: validate-jsonl
description: Validate deterministic JSONL snapshots for data quality — null checks, missing data, cross-consistency
allowed-tools: ["Bash", "Read"]
---

Validate deterministic JSONL snapshot files for data quality issues.

## What it checks
- **Null/None values** in critical fields (IB, VP, TPO, OR, inference)
- **"not_available"** or empty sections that should have data
- **Confidence=0** or suspiciously low values
- **IB not established** after 10:30
- **OR data missing** after 09:55 (should have 6+ EOR bars)
- **OR/drive persistence** — once detected, should persist all day
- **Volume profile** current session POC/VAH/VAL missing after 09:45
- **DPOC migration** missing current_dpoc after 11:30
- **Day type vs IB extension** cross-check (Balance with 0.5x+ extension = bug)
- **Morph consistency** with IB extension
- **NaN/Infinity** floats in any field
- **Schema validation** against snapshot schema

## Usage
- `/validate-jsonl` — Validate all JSONL files in data/json_snapshots/
- `/validate-jsonl 2026-03-04` — Validate a specific date
- `/validate-jsonl --errors-only` — Show only ERROR level (skip WARN/INFO)

## Steps
1. Run the validator:
   ```bash
   uv run python scripts/validate_jsonl.py data/json_snapshots/deterministic_{date}.jsonl --no-info
   ```
   Or for all files:
   ```bash
   uv run python scripts/validate_jsonl.py data/json_snapshots/ --no-info
   ```

2. If errors found, investigate by reading the specific time slice:
   ```python
   python3 -c "
   import json
   with open('data/json_snapshots/deterministic_{date}.jsonl', 'r') as f:
       lines = f.readlines()
   snap = json.loads(lines[{line_number}])
   print(json.dumps(snap.get('{section}', {}), indent=2))
   "
   ```

3. For deep audit with cross-checks (day_type vs IB extension, morph, etc.):
   ```bash
   uv run python scripts/validate_jsonl.py data/json_snapshots/deterministic_{date}.jsonl
   ```
   (Without --no-info to see all checks including early-time expected sparse data)

## Issue severity
- **ERROR** — Data that should be present is missing or contradictory
- **WARNING** — Suspicious values (NaN, None in optional fields, low confidence)
- **INFO** — Expected sparse output at early times (not a bug)
