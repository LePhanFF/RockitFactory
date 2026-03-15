---
name: generate-training-pairs
description: Generate LLM training pairs from deterministic snapshots (no API cost)
allowed-tools: ["Bash", "Read", "Glob", "Grep", "Write", "Edit", "Agent"]
---

Generate training pairs for ROCKIT LLM fine-tuning by analyzing every deterministic
snapshot and producing analysis output inline. Uses 3 parallel agents per JSONL file
to maximize throughput. No external API calls — Claude produces the output directly.

Each training pair is: `{"input": <snapshot>, "output": <analysis_json>}`

## Usage
- `/generate-training-pairs` — Process all snapshot JSONL files found in data/json_snapshots/
- `/generate-training-pairs 2026-03-02` — Process a single date
- `/generate-training-pairs --from 2026-02-26 --to 2026-03-03` — Process a date range (inclusive)
- `/generate-training-pairs --validate` — Validate existing training pairs only

## Argument Parsing

Parse the user's arguments to determine mode:
- If `--validate` is present → run validation only (step 5)
- If `--from` and `--to` are present → filter JSONL files to that date range (inclusive)
- If a single date like `2026-03-02` is present → process only that date
- If no arguments → process all JSONL files found

## Steps

### 1. Load Reference Materials

Read these files and internalize them — you ARE the ROCKIT analyst:
- `configs/prompts/rockit_system_prompt.md` — System prompt with strategy stats, oaths, time-phase rules
- `configs/prompts/output_schema.json` — JSON schema (13 required fields)

### 2. Build File List

Find all snapshot JSONL files:
```bash
ls data/json_snapshots/deterministic_*.jsonl
```

Filter by argument:
- **Date range** (`--from X --to Y`): keep files where date >= X and date <= Y
- **Single date**: keep only that file
- **No argument**: keep all

Sort files by date ascending. These will be processed **one at a time, sequentially**.

### 3. Process Each JSONL File (one at a time)

For each JSONL file in the sorted list:

#### 3a. Determine Pending Times

Check what times already have completed training pairs:
```python
import json
existing = set()
try:
    with open(f'data/training_pairs/training_{date}.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            pair = json.loads(line.strip())
            if pair.get('output') is not None:
                existing.add(pair['input']['current_et_time'])
except FileNotFoundError:
    pass

# Get all times from snapshot file that still need processing
pending_times = []
with open(f'data/json_snapshots/deterministic_{date}.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        snap = json.loads(line)
        if snap['current_et_time'] not in existing:
            pending_times.append(snap['current_et_time'])
```

If no pending times, print "Skipping {date} — all pairs complete" and move to next file.

#### 3b. Split Into 3 Segments

```python
n = len(pending_times)
third = n // 3
seg_a = pending_times[:third]
seg_b = pending_times[third:2*third]
seg_c = pending_times[2*third:]
```

Print: `"Processing {date}: {n} pending snapshots → 3 agents ({len(seg_a)}/{len(seg_b)}/{len(seg_c)})""`

#### 3c. Launch 3 Agents in Parallel

Launch **ALL 3 agents in a single message** so they run concurrently. Use the Agent tool
with `subagent_type: "general-purpose"` for each.

Each agent writes to its own segment file:
- Agent A → `data/training_pairs/seg_{date}_A.jsonl`
- Agent B → `data/training_pairs/seg_{date}_B.jsonl`
- Agent C → `data/training_pairs/seg_{date}_C.jsonl`

**Agent prompt** (fill in {date}, {segment_label}, {times_csv}, {output_file}):

```
You are generating ROCKIT LLM training pairs. For each snapshot time assigned to you,
read the full snapshot, produce an analysis JSON, and write the completed pair to your
output file.

## Assignment
- Date: {date}
- Segment: {segment_label}
- Times: {times_csv}
- Output: {output_file}

## Step 1: Read Reference Materials
Read completely:
- configs/prompts/rockit_system_prompt.md (system prompt — strategy stats, oaths, time-phase rules)
- configs/prompts/output_schema.json (13 required fields)

## Step 2: Read Snapshots
Read data/json_snapshots/deterministic_{date}.jsonl

For quick context on your snapshots, run:
uv run python scripts/gen_training_batch.py --day {date} --times {times_csv} --output /dev/null --summary-only

Then for each time, extract the FULL snapshot from the JSONL file (you'll need the complete
data to cite exact numbers).

## Step 3: For EACH Time, Generate Analysis

Produce a JSON object with ALL 13 required fields. Critical rules:

- Reference EXACT numbers from snapshot (prices, ranges, percentages)
- ALL 7 thinking steps present (use "NA — reason" for inactive time phases)
- day_type_call: object after 10:30 (classification/evidence/confidence_breakdown/skew/morph_watch), string "NA — IB not complete" before
- day_type_call.classification MUST match inference.day_type.type from snapshot
- strategy_assessment: object after 10:00 (or_reversal/or_acceptance/eighty_percent/twenty_percent/b_day/edge_fade/mean_reversion), string "NA — pre-IB" before
- Strategy stats to cite: OR Rev 64.4%/2.96, OR Accept 59.9%/1.46, 80P 42.3%/1.74, B-Day 46.4%/1.47, Mean Rev 42.6%/0.91 (LOSING — always warn)
- Cite CRI component scores (terrain, breath, reclaim, trap)
- one_liner max 140 characters
- evolution tracks bias strengthening/weakening, DPOC trend

### Time-Phase Rules:
| Time | Active | Inactive (= "NA — reason") |
|------|--------|---------------------------|
| Pre-9:30 | premarket_read, steps 1+4 | Everything else |
| 9:30-10:00 | + or_play, steps 2+3 | ib_read, day_type_call, strategy_assessment, value_area_play, tpo_remarks, steps 5-7 |
| 10:00-10:30 | + ib_read, tpo_remarks, strategy_assessment, step 5 | day_type_call object, value_area_play, steps 6-7 |
| 10:30+ | ALL active | None |
| After 13:00 | + "No new entries after 13:00" in discipline for 80P/B-Day/Edge Fade | None |

## Step 4: Write Each Pair

After generating analysis for a snapshot, IMMEDIATELY write it as one JSON line:

```python
import json
from datetime import datetime

pair = {
    "input": snapshot,  # full snapshot dict
    "output": analysis,  # your generated analysis dict
    "metadata": {
        "session_date": "{date}",
        "current_et_time": time_str,
        "generated_at": datetime.now().isoformat(),
        "generator": "claude-skill"
    }
}

with open("{output_file}", "a", encoding="utf-8") as f:
    f.write(json.dumps(pair, ensure_ascii=False) + "\n")
```

Process ALL assigned times. Do not skip any. Write each pair before moving to the next.
Report how many pairs you wrote when done.
```

#### 3d. Wait for All 3 Agents to Complete

After all 3 agents return, report their results.

#### 3e. Merge Segment Files

Run this Python to merge segments + existing pairs:
```python
import json

date = "{date}"
pairs_by_time = {}

# Load existing training pairs first
try:
    with open(f"data/training_pairs/training_{date}.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            pair = json.loads(line)
            t = pair["input"]["current_et_time"]
            if pair.get("output") is not None:
                pairs_by_time[t] = pair
except FileNotFoundError:
    pass

# Load all 3 segments
for seg in ["A", "B", "C"]:
    seg_file = f"data/training_pairs/seg_{date}_{seg}.jsonl"
    try:
        with open(seg_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                pair = json.loads(line)
                t = pair["input"]["current_et_time"]
                if pair.get("output") is not None:
                    pairs_by_time[t] = pair
    except FileNotFoundError:
        print(f"  WARNING: {seg_file} not found")

# Write final file sorted by time
with open(f"data/training_pairs/training_{date}.jsonl", "w", encoding="utf-8") as f:
    for t in sorted(pairs_by_time.keys()):
        f.write(json.dumps(pairs_by_time[t], ensure_ascii=False) + "\n")

print(f"Merged {len(pairs_by_time)} total pairs for {date}")
```

Clean up segment files:
```bash
rm -f data/training_pairs/seg_{date}_A.jsonl data/training_pairs/seg_{date}_B.jsonl data/training_pairs/seg_{date}_C.jsonl
```

#### 3f. Validate This Day

```bash
uv run python scripts/generate_training_pairs.py --validate data/training_pairs/training_{date}.jsonl
```

Report results for this day, then **proceed to the next JSONL file** in the list.

### 4. Final Report

After all days are processed, show:
- Total pairs generated across all days
- Per-day breakdown (pairs / validation status)
- Any days that had errors or incomplete segments

```bash
uv run python scripts/generate_training_pairs.py --validate-all
uv run python scripts/generate_training_pairs.py --stats
```

## Flow Diagram

```
/generate-training-pairs --from 2026-02-26 --to 2026-03-02

For each date in range (sequentially):

  deterministic_2026-02-26.jsonl (74 pending)
    ├── Agent A (09:35–11:35, ~24)  → seg_2026-02-26_A.jsonl
    ├── Agent B (11:40–13:40, ~24)  → seg_2026-02-26_B.jsonl  ← concurrent
    └── Agent C (13:45–15:55, ~26)  → seg_2026-02-26_C.jsonl
    → Merge → training_2026-02-26.jsonl (78 total)
    → Validate → report

  deterministic_2026-02-27.jsonl (74 pending)
    ├── Agent A → seg_2026-02-27_A.jsonl
    ├── Agent B → seg_2026-02-27_B.jsonl  ← concurrent
    └── Agent C → seg_2026-02-27_C.jsonl
    → Merge → training_2026-02-27.jsonl
    → Validate → report

  ... next date ...

Final: validate-all + stats
```
