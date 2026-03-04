---
name: generate-training-pairs
description: Generate LLM training pairs from deterministic snapshots (no API cost)
allowed-tools: ["Bash", "Read", "Glob", "Grep", "Write", "Edit"]
---

Generate training pairs for ROCKIT LLM fine-tuning by analyzing deterministic snapshots
and producing analysis output inline. No external API calls — Claude produces the output
directly using the shared system prompt as guidance.

Each training pair is: `{"input": <snapshot>, "output": <analysis_json>}`

## Usage
- `/generate-training-pairs` — Process all snapshot days, 4 key times per day
- `/generate-training-pairs 2026-03-02` — Process a specific date
- `/generate-training-pairs --all-times` — Process every 5-min snapshot (78/day)
- `/generate-training-pairs --times 09:30,10:30,12:00,14:00` — Custom time selection
- `/generate-training-pairs --validate` — Validate existing training pairs only

## Default Sample Times

When no `--all-times` or `--times` flag, use these 4 representative times per day:
- `09:30` — Market open (minimal data, premarket only)
- `10:30` — IB complete (first full analysis)
- `12:00` — Midday (full data, DPOC migration active)
- `14:00` — Afternoon (mature profile, late-session assessment)

## Steps

### 1. Load Reference Materials

Read the system prompt and output schema:
- `configs/prompts/rockit_system_prompt.md` — The ROCKIT system prompt with strategy stats, time-phase rules, position sizing
- `configs/prompts/output_schema.json` — JSON schema defining required output fields

**Internalize these completely.** You ARE the ROCKIT analyst for this task.

### 2. Find Snapshot Files

```bash
ls data/json_snapshots/deterministic_*.jsonl
```

If a specific date was given, only process that file. Otherwise process all.

### 3. For Each Snapshot File

Create output file: `data/training_pairs/training_{date}.jsonl`

For each selected time in the JSONL file:

#### a. Read the snapshot
Extract the JSON line matching the target `current_et_time`.

#### b. Produce the analysis
Using the system prompt as your guide, produce a JSON analysis object with ALL required fields:

```json
{
  "thinking": {
    "step_1_context": "...",
    "step_2_structure": "...",
    "step_3_flow": "...",
    "step_4_levels": "...",
    "step_5_day_type": "...",
    "step_6_setups": "...",
    "step_7_risk": "..."
  },
  "premarket_read": "...",
  "or_play": "...",
  "ib_read": "...",
  "day_type_call": {
    "classification": "...",
    "evidence": [...],
    "confidence_breakdown": "...",
    "skew": "...",
    "morph_watch": "..."
  },
  "strategy_assessment": {
    "or_reversal": "...",
    "or_acceptance": "...",
    "eighty_percent": "...",
    "twenty_percent": "...",
    "b_day": "...",
    "edge_fade": "...",
    "mean_reversion": "..."
  },
  "value_area_play": "...",
  "tpo_remarks": "...",
  "evolution": "...",
  "evidence": ["...", "..."],
  "what_could_go_wrong": ["...", "..."],
  "one_liner": "...",
  "discipline": "..."
}
```

**Critical rules when producing output:**
- Reference EXACT numbers from the snapshot (prices, ranges, percentages)
- Respect time-phase rules: use `"NA — [reason]"` for sections not yet active
- day_type_call must be an object (not string) after 10:30, string "NA — ..." before
- day_type_call.confidence_breakdown must explain which deltas built the confidence score
- day_type_call.skew must reference balance_classification.skew + skew_strength + seam_level
- strategy_assessment must check ALL 7 strategy signals, cite WR/PF for each active one
- Quote strategy WR/PF from the system prompt's strategy table
- Cite CRI component scores (terrain, breath, reclaim, trap) to explain CRI gate
- evolution must track: is bias strengthening/weakening? DPOC accelerating/decelerating?
- Keep one_liner under 25 words
- Every thinking step must cite specific snapshot numbers

#### c. Validate the output
Run validation using the script:
```bash
# Write the pair, then validate
uv run python scripts/generate_training_pairs.py --validate-only data/training_pairs/training_{date}.jsonl
```

#### d. Write the training pair
Append one JSON line to the output file:
```json
{"input": <snapshot>, "output": <analysis>, "metadata": {"session_date": "...", "current_et_time": "...", "generated_at": "...", "generator": "claude-skill"}}
```

### 4. Report Results

After processing, report:
- Number of pairs generated per day
- Number of validation errors
- Total pairs generated
- Output file locations

## Quality Checklist (per pair)

- [ ] All 11 required output fields present
- [ ] thinking steps cite actual numbers from snapshot
- [ ] Strategy mentions use correct WR/PF (OR Rev: 64.4%/2.96, 80P: 42.3%/1.74, etc.)
- [ ] Time-phase rules respected (no day_type_call object before 10:30)
- [ ] day_type_call.classification matches inference.day_type.type from snapshot
- [ ] CRI status referenced correctly
- [ ] one_liner is concise (under 20 words)
- [ ] Mean Reversion VWAP flagged as losing if mentioned

## Example Output (10:30 snapshot)

For a snapshot with: IB range 342.75, day_type "Balance", bias "Bullish", confidence 55, CRI "STAND_DOWN"

```json
{
  "thinking": {
    "step_1_context": "Opened gap down below prior VA (prior VAH 25094.75, VAL 24490.75). Overnight range 146.5pts with ONH 24739.25 well below prior POC 25022.25. Gap fill potential toward prior POC.",
    "step_2_structure": "IB range 342.75pts — wide IB suggesting responsive activity. Price at upper_third_hug of IB (current 25040.75 vs IBH 24947.75). Extension above IBH confirmed.",
    "step_3_flow": "DPOC migration data pending (pre-11:05). Wick parade: 22 bullish vs 25 bearish in 60-min window — near neutral, slight bearish edge.",
    "step_4_levels": "Key levels: IBH 24947.75 (93pts below), prior POC 25022.25 (18pts below), overnight high 24739.25 (301pts below).",
    "step_5_day_type": "Balance classification with Bullish bias at 55% confidence. Evidence: (1) Wide IB 342.75 = responsive, (2) Extension above IBH but Weak trend strength, (3) day_type_morph locked — no morph detected, (4) Confidence capped by Weak trend.",
    "step_6_setups": "No active strategy triggers. OR Reversal outside window (9:30-10:15). Edge Fade window not yet open. B-Day balance_type 'neutral' — no probe confirmed.",
    "step_7_risk": "CRI STAND_DOWN — no new entries. Permission: Flat size, No entry. Bear Trap detected (danger_flags). Discipline: observe only."
  },
  "premarket_read": "Opening below prior VA (VAH 25094.75 – VAL 24490.75). Overnight range 146.5pts, ONH 24739.25. Gap down from prior close. Nearest levels: prior POC 25022.25 (18pts), IBH 24947.75 (93pts).",
  "or_play": "Wide opening drive absorbed 342.75pts of range in IB. No OR Reversal signal triggered. Aggressive buying pushed through overnight levels.",
  "ib_read": "342.75pt IB — wide range suggesting responsive two-sided trade. Price accepted above IBH (25040.75 vs 24947.75). Inside prior VA range but below prior POC. Wide IB reduces trend day probability.",
  "day_type_call": {
    "classification": "Balance",
    "evidence": [
      "Wide IB (342.75pts) = responsive activity, not initiative — reduces trend probability",
      "Weak trend strength despite Bullish bias — market lacks conviction for follow-through",
      "Confidence only 55% — deterministic engine sees mixed signals",
      "No day_type_morph detected — structure holding as Balance"
    ],
    "skew": "Slight b-skew bullish — extension above IBH but no sustained follow-through. Watch for acceptance below IBH to confirm rotation.",
    "morph_watch": "A sustained close below IBH 24947.75 with DPOC flattening would confirm Balance. Conversely, new highs above 25045.25 with accelerating DPOC migration could morph to Trend."
  },
  "value_area_play": "Price opened below prior VA, rallied back inside. 80P Rule not triggered — would need acceptance confirmation with 30-bar candle close. VA width needs verification against 25pt minimum.",
  "tpo_remarks": "Upper fattening detected with single prints both above and below — volatile two-sided auction. Profile shape suggests balance with slight upward skew. DPOC migration data pending (available after 11:05).",
  "evidence": [
    "1. IB range 342.75pts with extension above IBH 24947.75 by 93pts — wide responsive range",
    "2. Deterministic: Balance day type, Bullish bias at 55% confidence, Weak trend strength",
    "3. CRI STAND_DOWN with Bear Trap detected — wick parade 22 bull vs 25 bear",
    "4. No strategy triggers active — OR Rev outside window, Edge Fade not yet open"
  ],
  "what_could_go_wrong": [
    "Bear trap resolves with sharp reversal below IBH 24947.75 — trapped longs from morning rally unwind",
    "DPOC migration (pending) shows flat/down — would negate Bullish bias and confirm rotation day"
  ],
  "one_liner": "Balance day, Bullish lean but Weak trend — CRI says stand down, observe only.",
  "discipline": "CRI STAND_DOWN: no new entries. Size cap Flat. Bear Trap in play — do not chase the morning rally. Wait for CRI upgrade before any position."
}
```
