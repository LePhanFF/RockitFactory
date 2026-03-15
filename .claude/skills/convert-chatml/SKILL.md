---
name: convert-chatml
description: Convert training pairs to ChatML format with <think> CoT tags for Qwen3.5 LoRA training
allowed-tools: ["Bash", "Read", "Glob", "Grep"]
---

Convert ROCKIT training pairs from `data/training_pairs/` into Qwen3.5-compatible ChatML
format in `data/training_chatml/`. Inserts `<think>` reasoning blocks from the `thinking`
field and produces per-day files plus a merged `train.jsonl`.

## Usage
- `/convert-chatml` — Convert all training pairs, merge into train.jsonl
- `/convert-chatml 2026-02-26` — Convert a single day only
- `/convert-chatml --validate` — Validate existing ChatML files
- `/convert-chatml --stats` — Show token stats and dataset composition
- `/convert-chatml --no-think-ratio 0.30` — Override the non-thinking ratio (default 0.25)

## Steps

### 1. Run Conversion

Parse arguments and run the appropriate command:

**All days (default):**
```bash
uv run python scripts/convert_to_chatml.py --merge
```

**Single day:**
```bash
uv run python scripts/convert_to_chatml.py --input data/training_pairs/training_{date}.jsonl --output-dir data/training_chatml
```

**Custom no-think ratio:**
```bash
uv run python scripts/convert_to_chatml.py --merge --no-think-ratio {ratio}
```

### 2. Validate

After conversion, always validate:
```bash
uv run python scripts/convert_to_chatml.py --validate --input data/training_chatml/train.jsonl
```

### 3. Report

Show the user:
- Total examples converted
- Think ratio (target: 75% with thinking, 25% without)
- Token stats (avg/min/max) — all should be under 16,384
- Any errors or warnings
- File location: `data/training_chatml/train.jsonl`

### 4. Validate-Only Mode

If `--validate` was passed as argument:
```bash
uv run python scripts/convert_to_chatml.py --validate --input data/training_chatml/train.jsonl
```

### 5. Stats Mode

If `--stats` was passed:
```bash
uv run python scripts/convert_to_chatml.py --merge --dry-run
```

## Output Format

Each line in `train.jsonl` is a ChatML example:
```json
{
  "messages": [
    {"role": "system", "content": "<ROCKIT system prompt>"},
    {"role": "user", "content": "<deterministic snapshot as JSON>"},
    {"role": "assistant", "content": "<think>\n## Step 1: Context...\n</think>\n\n{\"premarket_read\": ...}"}
  ]
}
```

- 75% of examples have full `<think>` content (7 reasoning steps)
- 25% have empty `<think></think>` tags (teaches model to skip reasoning when appropriate)
- The `thinking` field is removed from the JSON output (it lives in the `<think>` block)
- Output JSON has 12 fields (all 13 original minus `thinking`)

## Data Flow

```
data/training_pairs/training_*.jsonl    ← Source (input + output with thinking as JSON)
    ↓
scripts/convert_to_chatml.py --merge
    ↓
data/training_chatml/train.jsonl        ← ChatML for Qwen3.5 LoRA training
```
