#!/usr/bin/env python3
"""
Training data generation pipeline for ROCKIT LLM.

Batch-generates training pairs (snapshot -> LLM analysis) across arbitrary
date ranges. Each day becomes an independent "chunk" that can be processed
in parallel by separate cloud agents or API workers.

Subcommands:
  prepare   Create work chunks from existing snapshots (or generate them first)
  generate  Process a single chunk via Anthropic Messages API
  merge     Combine completed chunks into per-day training files + validate
  status    Show generation progress dashboard

Parallel cloud usage:
  # 1. Prepare all work (generates snapshots if needed)
  uv run python scripts/training_pipeline.py prepare --days 90

  # 2. Process chunks in parallel (one per cloud instance / terminal)
  uv run python scripts/training_pipeline.py generate --chunk chunk_20260226.jsonl
  uv run python scripts/training_pipeline.py generate --chunk chunk_20260227.jsonl
  #   ... up to N instances in parallel

  # 3. Merge completed chunks into final training files
  uv run python scripts/training_pipeline.py merge

  # 4. Check progress anytime
  uv run python scripts/training_pipeline.py status

Environment:
  ANTHROPIC_API_KEY  Required for 'generate' subcommand
  ROCKIT_MODEL       Model ID override (default: claude-sonnet-4-20250514)

Cost estimate (Sonnet):
  ~$0.003/input + ~$0.015/output per 1K tokens
  ~6.5K tokens per pair -> ~$0.12/pair -> ~$9.36/day (78 pairs) -> $842/90 days
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = PROJECT_ROOT / "data" / "json_snapshots"
CHUNK_DIR = PROJECT_ROOT / "data" / "training_pairs" / "chunks"
OUTPUT_DIR = PROJECT_ROOT / "data" / "training_pairs"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
PROMPT_PATH = PROJECT_ROOT / "configs" / "prompts" / "rockit_system_prompt.md"
SCHEMA_PATH = PROJECT_ROOT / "configs" / "prompts" / "output_schema.json"
SNAPSHOT_SCRIPT = PROJECT_ROOT / "scripts" / "generate_deterministic_snapshots.py"

# ---------------------------------------------------------------------------
# Cost (Sonnet 4 pricing — override with ROCKIT_PRICING env)
# ---------------------------------------------------------------------------
PRICING = {
    "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
    "claude-opus-4-20250514": {"input": 0.015, "output": 0.075},
}
DEFAULT_MODEL = "claude-sonnet-4-20250514"


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICING.get(model, PRICING[DEFAULT_MODEL])
    return input_tokens / 1000 * p["input"] + output_tokens / 1000 * p["output"]


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------
def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {"created_at": None, "model": None, "chunks": {}, "stats": {}}


def save_manifest(manifest: dict):
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def update_manifest_stats(manifest: dict):
    chunks = manifest.get("chunks", {})
    total_c = len(chunks)
    done_c = sum(1 for c in chunks.values() if c["status"] == "completed")
    total_s = sum(c["snapshot_count"] for c in chunks.values())
    done_s = sum(c.get("completed_count", 0) for c in chunks.values())
    cost = sum(c.get("cost_usd", 0) for c in chunks.values())
    manifest["stats"] = {
        "total_chunks": total_c,
        "completed_chunks": done_c,
        "pending_chunks": total_c - done_c,
        "total_snapshots": total_s,
        "completed_snapshots": done_s,
        "total_cost_usd": round(cost, 4),
    }


# ---------------------------------------------------------------------------
# Schema / prompt loading
# ---------------------------------------------------------------------------
def load_system_prompt() -> str:
    if not PROMPT_PATH.exists():
        print(f"ERROR: System prompt not found at {PROMPT_PATH}")
        sys.exit(1)
    return PROMPT_PATH.read_text(encoding="utf-8")


def load_output_schema() -> dict:
    if not SCHEMA_PATH.exists():
        print(f"ERROR: Output schema not found at {SCHEMA_PATH}")
        sys.exit(1)
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Validation (imported from generate_training_pairs.py logic)
# ---------------------------------------------------------------------------
def time_to_minutes(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


THINKING_STEP_ACTIVATION = {
    "step_1_context": "00:00",
    "step_2_structure": "09:30",
    "step_3_flow": "09:30",
    "step_4_levels": "00:00",
    "step_5_day_type": "10:30",
    "step_6_setups": "10:30",
    "step_7_risk": "10:30",
}

TIME_PHASE_RULES = {
    "or_play": ("09:30", True),
    "ib_read": ("10:00", True),
    "day_type_call": ("10:30", True),
    "strategy_assessment": ("10:00", True),
    "value_area_play": ("10:30", True),
    "tpo_remarks": ("10:00", True),
}


def validate_output(output: dict, snapshot: dict, schema: dict) -> list[str]:
    """Validate LLM output against schema + time-phase rules."""
    errors = []
    current_time = snapshot.get("current_et_time", "00:00")
    current_mins = time_to_minutes(current_time)

    for field in schema.get("required", []):
        if field not in output:
            errors.append(f"Missing required field: {field}")

    thinking = output.get("thinking", {})
    if isinstance(thinking, dict):
        for step in THINKING_STEP_ACTIVATION:
            if step not in thinking:
                errors.append(f"Missing thinking.{step}")
            else:
                step_mins = time_to_minutes(THINKING_STEP_ACTIVATION[step])
                if current_mins < step_mins and not str(thinking[step]).startswith("NA"):
                    errors.append(
                        f"thinking.{step} should be 'NA ...' before "
                        f"{THINKING_STEP_ACTIVATION[step]}, got content at {current_time}"
                    )
    else:
        errors.append("thinking must be an object")

    for field, (earliest, _) in TIME_PHASE_RULES.items():
        earliest_mins = time_to_minutes(earliest)
        value = output.get(field)
        if value is None:
            continue
        if current_mins < earliest_mins:
            if isinstance(value, str) and value.startswith("NA"):
                continue
            elif isinstance(value, dict):
                errors.append(
                    f"{field} should be 'NA ...' before {earliest}, got object at {current_time}"
                )

    for arr_field in ["evidence", "what_could_go_wrong"]:
        val = output.get(arr_field)
        if val is not None and not isinstance(val, list):
            errors.append(f"{arr_field} must be an array")
        elif isinstance(val, list) and len(val) == 0:
            errors.append(f"{arr_field} must have at least 1 item")

    one_liner = output.get("one_liner", "")
    if isinstance(one_liner, str) and len(one_liner) > 150:
        errors.append(f"one_liner too long: {len(one_liner)} chars (max 140)")

    return errors


# =========================================================================== #
# SUBCOMMAND: prepare
# =========================================================================== #
def cmd_prepare(args):
    """Create work chunks from snapshot JSONL files.

    Each chunk = one trading day = one independent work unit.
    If --with-snapshots, generates snapshots first using the orchestrator.
    """
    print("=" * 60)
    print("PREPARE: Creating work chunks")
    print("=" * 60)

    # Step 1: Generate snapshots if requested
    if args.with_snapshots:
        print(f"\nStep 1: Generating deterministic snapshots (--days {args.days})...")
        cmd = [
            sys.executable, str(SNAPSHOT_SCRIPT),
            "--days", str(args.days),
            "--rth-only",
        ]
        if args.verbose:
            cmd.append("-v")
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        if result.returncode != 0:
            print("ERROR: Snapshot generation failed")
            sys.exit(1)
        print()

    # Step 2: Find snapshot files
    snapshot_files = sorted(SNAPSHOT_DIR.glob("deterministic_*.jsonl"))
    if args.dates:
        target_dates = set(args.dates.split(","))
        snapshot_files = [
            f for f in snapshot_files
            if f.stem.replace("deterministic_", "") in target_dates
        ]
    elif args.days and not args.with_snapshots:
        snapshot_files = snapshot_files[-args.days:]

    if not snapshot_files:
        print("ERROR: No snapshot files found in data/json_snapshots/")
        print("  Run with --with-snapshots to generate them first, or")
        print("  run: uv run python scripts/generate_deterministic_snapshots.py --days N --rth-only")
        sys.exit(1)

    # Step 3: Create chunks
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    manifest["created_at"] = datetime.now().isoformat()
    model = os.environ.get("ROCKIT_MODEL", DEFAULT_MODEL)
    manifest["model"] = model

    created = 0
    skipped = 0

    for snap_file in snapshot_files:
        date_str = snap_file.stem.replace("deterministic_", "")
        chunk_name = f"chunk_{date_str}.jsonl"
        chunk_path = CHUNK_DIR / chunk_name

        # Count snapshots
        with open(snap_file, "r", encoding="utf-8") as f:
            snap_count = sum(1 for line in f if line.strip())

        # Skip if chunk already completed
        if chunk_name in manifest.get("chunks", {}) and \
           manifest["chunks"][chunk_name]["status"] == "completed":
            print(f"  {date_str}: SKIP (already completed)")
            skipped += 1
            continue

        # Check for existing training pairs to skip those times
        existing_times = set()
        existing_pair_file = OUTPUT_DIR / f"training_{date_str}.jsonl"
        if existing_pair_file.exists():
            with open(existing_pair_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        pair = json.loads(line)
                        t = pair.get("input", {}).get("current_et_time")
                        if t and pair.get("output") is not None:
                            existing_times.add(t)
                    except json.JSONDecodeError:
                        pass

        # Write chunk file (snapshots that need processing)
        pairs_written = 0
        with open(snap_file, "r", encoding="utf-8") as fin, \
             open(chunk_path, "w", encoding="utf-8") as fout:
            for line in fin:
                line = line.strip()
                if not line:
                    continue
                snap = json.loads(line)
                t = snap.get("current_et_time", "")

                # Skip if already have a completed pair for this time
                if t in existing_times:
                    continue

                pair = {
                    "input": snap,
                    "output": None,
                    "metadata": {
                        "session_date": date_str,
                        "current_et_time": t,
                        "chunk_id": chunk_name,
                        "created_at": datetime.now().isoformat(),
                    }
                }
                fout.write(json.dumps(pair, ensure_ascii=False) + "\n")
                pairs_written += 1

        manifest.setdefault("chunks", {})[chunk_name] = {
            "date": date_str,
            "snapshot_count": pairs_written,
            "total_day_snapshots": snap_count,
            "existing_pairs": len(existing_times),
            "status": "pending" if pairs_written > 0 else "completed",
            "completed_count": 0,
            "cost_usd": 0.0,
        }
        created += 1
        status = "READY" if pairs_written > 0 else "SKIP (all done)"
        print(f"  {date_str}: {pairs_written} snapshots to process "
              f"({len(existing_times)} existing) [{status}]")

    update_manifest_stats(manifest)
    save_manifest(manifest)

    stats = manifest["stats"]
    print(f"\nPrepared: {created} chunks ({skipped} skipped)")
    print(f"Total snapshots to process: {stats['total_snapshots']}")
    print(f"Chunks ready: {stats['pending_chunks']}")

    # Cost estimate
    avg_input_tokens = 6500  # system prompt + snapshot
    avg_output_tokens = 1500
    cost_per_pair = estimate_cost(model, avg_input_tokens, avg_output_tokens)
    total_est = cost_per_pair * stats["total_snapshots"]
    print(f"\nEstimated cost ({model}):")
    print(f"  Per pair:  ${cost_per_pair:.4f}")
    print(f"  Per day:   ${cost_per_pair * 78:.2f} (78 snapshots)")
    print(f"  Total:     ${total_est:.2f} ({stats['total_snapshots']} pairs)")

    print(f"\nManifest: {MANIFEST_PATH}")
    print(f"Chunks:   {CHUNK_DIR}/")
    print(f"\nNext: Run 'generate --chunk <name>' for each chunk (can be parallel)")


# =========================================================================== #
# SUBCOMMAND: generate
# =========================================================================== #
def cmd_generate(args):
    """Process a single chunk file via Anthropic Messages API."""
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package required.")
        print("  Install: uv pip install anthropic")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    # Resolve chunk path
    chunk_name = args.chunk
    chunk_path = CHUNK_DIR / chunk_name
    if not chunk_path.exists():
        # Try with full path
        chunk_path = Path(chunk_name)
    if not chunk_path.exists():
        print(f"ERROR: Chunk file not found: {chunk_name}")
        print(f"  Looked in: {CHUNK_DIR}")
        sys.exit(1)

    model = os.environ.get("ROCKIT_MODEL", args.model or DEFAULT_MODEL)
    system_prompt = load_system_prompt()
    schema = load_output_schema()

    # Load chunk
    pairs = []
    with open(chunk_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            pairs.append(json.loads(line))

    # Filter to unprocessed only
    pending = [p for p in pairs if p.get("output") is None]
    completed = [p for p in pairs if p.get("output") is not None]

    if not pending:
        print(f"All {len(completed)} pairs in {chunk_name} already completed!")
        return

    print(f"Processing {chunk_name}: {len(pending)} pending, {len(completed)} done")
    print(f"Model: {model}")

    client = anthropic.Anthropic(api_key=api_key)
    total_cost = 0.0
    success = 0
    errors = 0
    t0 = time.time()

    for i, pair in enumerate(pending):
        snapshot = pair["input"]
        t = snapshot.get("current_et_time", "?")
        date = pair.get("metadata", {}).get("session_date", "?")

        user_msg = (
            "Analyze this deterministic market snapshot. "
            "Respond with a single JSON object matching the output schema. "
            "No markdown fences, no explanation — just the JSON.\n\n"
            f"{json.dumps(snapshot)}"
        )

        try:
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )

            text = "".join(
                b.text for b in response.content if b.type == "text"
            ).strip()

            # Strip markdown fences if present
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                text = "\n".join(lines)

            output = json.loads(text)
            cost = estimate_cost(
                model, response.usage.input_tokens, response.usage.output_tokens
            )
            total_cost += cost

            # Validate
            val_errors = validate_output(output, snapshot, schema)

            pair["output"] = output
            pair["metadata"]["completed_at"] = datetime.now().isoformat()
            pair["metadata"]["cost_usd"] = round(cost, 6)
            pair["metadata"]["model"] = model
            pair["metadata"]["input_tokens"] = response.usage.input_tokens
            pair["metadata"]["output_tokens"] = response.usage.output_tokens

            success += 1
            val_status = f" ({len(val_errors)} warnings)" if val_errors else ""
            print(f"  [{i+1}/{len(pending)}] {date} {t} OK "
                  f"(${cost:.4f}, {response.usage.output_tokens} out){val_status}")

            if val_errors and args.verbose:
                for ve in val_errors:
                    print(f"    WARN: {ve}")

        except json.JSONDecodeError as e:
            errors += 1
            print(f"  [{i+1}/{len(pending)}] {date} {t} JSON ERROR: {e}")
            pair["metadata"]["error"] = f"JSON parse: {e}"

        except Exception as e:
            errors += 1
            print(f"  [{i+1}/{len(pending)}] {date} {t} ERROR: {e}")
            pair["metadata"]["error"] = str(e)

        # Write progress after each pair (resume-safe)
        all_pairs = completed + pending[:i+1] + pending[i+1:]
        with open(chunk_path, "w", encoding="utf-8") as f:
            for p in all_pairs:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")

        # Rate limiting (avoid 429s)
        if i < len(pending) - 1:
            time.sleep(args.delay)

    elapsed = time.time() - t0
    print(f"\nDone: {success} OK, {errors} errors, {elapsed:.1f}s, ${total_cost:.4f}")

    # Update manifest
    manifest = load_manifest()
    done_count = sum(1 for p in (completed + pending) if p.get("output") is not None)
    total_count = len(completed) + len(pending)
    chunk_key = chunk_path.name
    if chunk_key in manifest.get("chunks", {}):
        manifest["chunks"][chunk_key]["completed_count"] = done_count
        manifest["chunks"][chunk_key]["cost_usd"] = round(
            manifest["chunks"][chunk_key].get("cost_usd", 0) + total_cost, 4
        )
        if done_count >= total_count:
            manifest["chunks"][chunk_key]["status"] = "completed"
        else:
            manifest["chunks"][chunk_key]["status"] = "partial"
        update_manifest_stats(manifest)
        save_manifest(manifest)


# =========================================================================== #
# SUBCOMMAND: generate-batch (Anthropic Batch API — 50% cheaper)
# =========================================================================== #
def cmd_generate_batch(args):
    """Submit chunks to Anthropic Batch API for async processing (50% discount)."""
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package required. Install: uv pip install anthropic")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    model = os.environ.get("ROCKIT_MODEL", args.model or DEFAULT_MODEL)
    system_prompt = load_system_prompt()
    client = anthropic.Anthropic(api_key=api_key)

    # Collect all pending pairs from specified chunks (or all)
    if args.chunk:
        chunk_files = [CHUNK_DIR / args.chunk]
    else:
        chunk_files = sorted(CHUNK_DIR.glob("chunk_*.jsonl"))

    requests = []
    pair_index = {}  # custom_id -> (chunk_path, line_index)

    for chunk_path in chunk_files:
        if not chunk_path.exists():
            print(f"WARN: {chunk_path} not found, skipping")
            continue

        with open(chunk_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                pair = json.loads(line)
                if pair.get("output") is not None:
                    continue  # already done

                snapshot = pair["input"]
                date = pair.get("metadata", {}).get("session_date", "unknown")
                t = snapshot.get("current_et_time", "unknown")
                custom_id = f"{date}_{t.replace(':', '')}"

                requests.append({
                    "custom_id": custom_id,
                    "params": {
                        "model": model,
                        "max_tokens": 4096,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content":
                            "Analyze this deterministic market snapshot. "
                            "Respond with a single JSON object matching the output schema. "
                            "No markdown fences, no explanation — just the JSON.\n\n"
                            f"{json.dumps(snapshot)}"
                        }],
                    }
                })
                pair_index[custom_id] = (str(chunk_path), line_idx)

    if not requests:
        print("No pending pairs to process!")
        return

    print(f"Submitting {len(requests)} requests to Batch API ({model})")
    print(f"Estimated cost: ${estimate_cost(model, 6500 * len(requests), 1500 * len(requests)) * 0.5:.2f} (50% batch discount)")

    # Write batch request file
    batch_file = OUTPUT_DIR / "batch_request.jsonl"
    with open(batch_file, "w", encoding="utf-8") as f:
        for req in requests:
            f.write(json.dumps(req, ensure_ascii=False) + "\n")

    # Submit via API
    try:
        with open(batch_file, "rb") as f:
            batch = client.batches.create(
                requests=[json.loads(line) for line in open(batch_file, "r", encoding="utf-8")],
            )
        print(f"\nBatch submitted: {batch.id}")
        print(f"Status: {batch.processing_status}")
        print(f"\nTo check status: python training_pipeline.py batch-status --batch-id {batch.id}")

        # Save batch info
        batch_info = OUTPUT_DIR / "batch_info.json"
        batch_info.write_text(json.dumps({
            "batch_id": batch.id,
            "submitted_at": datetime.now().isoformat(),
            "request_count": len(requests),
            "model": model,
            "pair_index": pair_index,
        }, indent=2), encoding="utf-8")

    except Exception as e:
        print(f"ERROR submitting batch: {e}")
        print(f"Batch request file saved at: {batch_file}")
        print("You can submit manually or retry.")


# =========================================================================== #
# SUBCOMMAND: merge
# =========================================================================== #
def cmd_merge(args):
    """Merge completed chunks into per-day training files."""
    print("=" * 60)
    print("MERGE: Combining completed chunks into training files")
    print("=" * 60)

    schema = load_output_schema()
    chunk_files = sorted(CHUNK_DIR.glob("chunk_*.jsonl"))

    if not chunk_files:
        print("No chunk files found in data/training_pairs/chunks/")
        return

    by_date: dict[str, list[dict]] = {}
    total_valid = 0
    total_invalid = 0

    for chunk_path in chunk_files:
        with open(chunk_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                pair = json.loads(line)
                if pair.get("output") is None:
                    continue  # skip incomplete

                date = pair.get("metadata", {}).get("session_date", "unknown")
                by_date.setdefault(date, []).append(pair)

    # Also include existing training pair files
    for existing in sorted(OUTPUT_DIR.glob("training_*.jsonl")):
        date = existing.stem.replace("training_", "")
        with open(existing, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                pair = json.loads(line)
                if pair.get("output") is None:
                    continue
                t = pair.get("input", {}).get("current_et_time", "")
                # Avoid duplicates
                existing_times = {
                    p.get("input", {}).get("current_et_time")
                    for p in by_date.get(date, [])
                }
                if t not in existing_times:
                    by_date.setdefault(date, []).append(pair)

    # Write merged files
    for date in sorted(by_date.keys()):
        pairs = by_date[date]
        # Sort by time
        pairs.sort(key=lambda p: p.get("input", {}).get("current_et_time", ""))

        # Deduplicate by time
        seen_times = set()
        unique_pairs = []
        for p in pairs:
            t = p.get("input", {}).get("current_et_time", "")
            if t not in seen_times:
                seen_times.add(t)
                unique_pairs.append(p)
        pairs = unique_pairs

        # Validate
        valid = 0
        invalid = 0
        for pair in pairs:
            errs = validate_output(pair["output"], pair["input"], schema)
            if errs:
                invalid += 1
                if args.verbose:
                    t = pair["input"].get("current_et_time", "?")
                    print(f"  WARN {date} {t}: {errs[0]}")
            else:
                valid += 1

        total_valid += valid
        total_invalid += invalid

        # Write
        out_path = OUTPUT_DIR / f"training_{date}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for pair in pairs:
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")

        print(f"  {date}: {len(pairs)} pairs ({valid} valid, {invalid} warnings) -> {out_path.name}")

    print(f"\nTotal: {total_valid + total_invalid} pairs ({total_valid} valid, {total_invalid} with warnings)")


# =========================================================================== #
# SUBCOMMAND: status
# =========================================================================== #
def cmd_status(args):
    """Show generation progress dashboard."""
    print("=" * 60)
    print("TRAINING PIPELINE STATUS")
    print("=" * 60)

    manifest = load_manifest()
    if not manifest.get("chunks"):
        # No manifest — check for files directly
        chunk_files = sorted(CHUNK_DIR.glob("chunk_*.jsonl")) if CHUNK_DIR.exists() else []
        training_files = sorted(OUTPUT_DIR.glob("training_*.jsonl"))

        if not chunk_files and not training_files:
            print("\nNo data found. Run 'prepare' first.")
            return

        if training_files:
            print(f"\nTraining files ({len(training_files)}):")
            total = 0
            for tf in training_files:
                with open(tf, "r", encoding="utf-8") as f:
                    count = sum(1 for line in f if line.strip())
                print(f"  {tf.name}: {count} pairs")
                total += count
            print(f"  Total: {total} pairs")
        return

    # From manifest
    stats = manifest.get("stats", {})
    model = manifest.get("model", "unknown")

    print(f"\nModel: {model}")
    print(f"Created: {manifest.get('created_at', '?')}")
    print()

    print(f"Chunks:    {stats.get('completed_chunks', 0)}/{stats.get('total_chunks', 0)} completed")
    print(f"Snapshots: {stats.get('completed_snapshots', 0)}/{stats.get('total_snapshots', 0)} processed")
    print(f"Cost:      ${stats.get('total_cost_usd', 0):.4f}")
    print()

    # Per-chunk detail
    chunks = manifest.get("chunks", {})
    print(f"{'Chunk':<30} {'Status':<12} {'Done':<8} {'Total':<8} {'Cost':<10}")
    print("-" * 68)
    for name, info in sorted(chunks.items()):
        status = info.get("status", "?")
        done = info.get("completed_count", 0)
        total = info.get("snapshot_count", 0)
        cost = info.get("cost_usd", 0)
        marker = "+" if status == "completed" else ("~" if status == "partial" else " ")
        print(f"{marker} {name:<28} {status:<12} {done:<8} {total:<8} ${cost:<9.4f}")

    # Also show final training files
    training_files = sorted(OUTPUT_DIR.glob("training_*.jsonl"))
    if training_files:
        print(f"\nMerged training files:")
        total_pairs = 0
        for tf in training_files:
            with open(tf, "r", encoding="utf-8") as f:
                count = sum(1 for line in f if line.strip())
            print(f"  {tf.name}: {count} pairs")
            total_pairs += count
        print(f"  Total: {total_pairs} pairs")

    pending = stats.get("pending_chunks", 0)
    if pending > 0:
        print(f"\nNext steps:")
        pending_chunks = [n for n, c in chunks.items() if c["status"] != "completed"]
        for name in pending_chunks[:5]:
            print(f"  uv run python scripts/training_pipeline.py generate --chunk {name}")
        if len(pending_chunks) > 5:
            print(f"  ... and {len(pending_chunks) - 5} more")


# =========================================================================== #
# SUBCOMMAND: export-prompts (for agent-based generation without API)
# =========================================================================== #
def cmd_export_prompts(args):
    """Export self-contained prompt files for each snapshot.

    Each file contains the system prompt + snapshot as a user message.
    An agent (Claude Code, etc.) reads the file, generates the response,
    and writes the output JSON to a companion file.

    This enables generation via Claude Code subscription (no API cost).
    """
    print("=" * 60)
    print("EXPORT PROMPTS: Creating agent-ready prompt files")
    print("=" * 60)

    system_prompt = load_system_prompt()

    if args.chunk:
        chunk_files = [CHUNK_DIR / args.chunk]
    else:
        chunk_files = sorted(CHUNK_DIR.glob("chunk_*.jsonl"))

    prompt_dir = OUTPUT_DIR / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for chunk_path in chunk_files:
        if not chunk_path.exists():
            continue

        with open(chunk_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                pair = json.loads(line)
                if pair.get("output") is not None:
                    continue

                snapshot = pair["input"]
                date = pair.get("metadata", {}).get("session_date", "unknown")
                t = snapshot.get("current_et_time", "00:00").replace(":", "")

                # Write prompt file
                prompt_file = prompt_dir / f"prompt_{date}_{t}.md"
                with open(prompt_file, "w", encoding="utf-8") as pf:
                    pf.write("# ROCKIT Training Pair Generation\n\n")
                    pf.write("## System Prompt\n\n")
                    pf.write(system_prompt)
                    pf.write("\n\n---\n\n")
                    pf.write("## Task\n\n")
                    pf.write("Analyze this deterministic market snapshot. ")
                    pf.write("Respond with a single JSON object matching the output schema. ")
                    pf.write("No markdown fences, no explanation — just the JSON.\n\n")
                    pf.write("## Snapshot\n\n```json\n")
                    pf.write(json.dumps(snapshot, indent=2, ensure_ascii=False))
                    pf.write("\n```\n\n")
                    pf.write("## Output\n\n")
                    pf.write(f"Write your JSON response to: `responses/response_{date}_{t}.json`\n")

                total += 1

    print(f"Exported {total} prompt files to {prompt_dir}/")
    print(f"\nAgent workflow:")
    print(f"  1. Agent reads prompt file from {prompt_dir}/")
    print(f"  2. Agent generates analysis JSON following the system prompt")
    print(f"  3. Agent writes response to {prompt_dir}/responses/")
    print(f"  4. Run 'merge' to combine all responses")


# =========================================================================== #
# Main
# =========================================================================== #
def main():
    parser = argparse.ArgumentParser(
        description="ROCKIT Training Data Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Prepare 10 days (with snapshot generation)
  %(prog)s prepare --days 10 --with-snapshots

  # Prepare from existing snapshots
  %(prog)s prepare --days 10

  # Prepare specific dates
  %(prog)s prepare --dates 2026-02-26,2026-02-27,2026-03-02

  # Generate one chunk (run in parallel across instances)
  %(prog)s generate --chunk chunk_20260226.jsonl

  # Generate with Opus (higher quality, higher cost)
  ROCKIT_MODEL=claude-opus-4-20250514 %(prog)s generate --chunk chunk_20260226.jsonl

  # Submit all pending to Batch API (50%% cheaper)
  %(prog)s batch

  # Export prompt files for agent-based generation (no API cost)
  %(prog)s export-prompts

  # Merge completed chunks into training files
  %(prog)s merge

  # Check progress
  %(prog)s status
        """,
    )
    sub = parser.add_subparsers(dest="command")

    # prepare
    p_prep = sub.add_parser("prepare", help="Create work chunks from snapshots")
    p_prep.add_argument("--days", type=int, default=None,
                        help="Number of recent trading days")
    p_prep.add_argument("--dates", type=str, default=None,
                        help="Comma-separated specific dates (e.g., 2026-02-26,2026-02-27)")
    p_prep.add_argument("--with-snapshots", action="store_true",
                        help="Generate deterministic snapshots first")
    p_prep.add_argument("-v", "--verbose", action="store_true")

    # generate
    p_gen = sub.add_parser("generate", help="Process a chunk via Anthropic API")
    p_gen.add_argument("--chunk", required=True,
                       help="Chunk filename (e.g., chunk_20260226.jsonl)")
    p_gen.add_argument("--model", type=str, default=None,
                       help=f"Model ID (default: {DEFAULT_MODEL}, or ROCKIT_MODEL env)")
    p_gen.add_argument("--delay", type=float, default=0.5,
                       help="Delay between API calls in seconds (default: 0.5)")
    p_gen.add_argument("-v", "--verbose", action="store_true")

    # batch
    p_batch = sub.add_parser("batch", help="Submit to Anthropic Batch API (50%% cheaper)")
    p_batch.add_argument("--chunk", type=str, default=None,
                         help="Specific chunk (default: all pending)")
    p_batch.add_argument("--model", type=str, default=None)

    # merge
    p_merge = sub.add_parser("merge", help="Combine completed chunks into training files")
    p_merge.add_argument("-v", "--verbose", action="store_true")

    # status
    p_status = sub.add_parser("status", help="Show generation progress")

    # export-prompts
    p_export = sub.add_parser("export-prompts",
                              help="Export prompt files for agent-based generation")
    p_export.add_argument("--chunk", type=str, default=None,
                          help="Specific chunk (default: all pending)")

    args = parser.parse_args()

    if args.command == "prepare":
        cmd_prepare(args)
    elif args.command == "generate":
        cmd_generate(args)
    elif args.command == "batch":
        cmd_generate_batch(args)
    elif args.command == "merge":
        cmd_merge(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "export-prompts":
        cmd_export_prompts(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
