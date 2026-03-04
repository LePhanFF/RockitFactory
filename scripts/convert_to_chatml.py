#!/usr/bin/env python3
"""Convert ROCKIT training pairs to ChatML format with <think> CoT tags.

Usage:
    # Convert all training pairs, merge into single file
    uv run python scripts/convert_to_chatml.py --merge

    # Convert a single day
    uv run python scripts/convert_to_chatml.py --input data/training_pairs/training_2026-02-26.jsonl

    # Custom no-think ratio (default 25%)
    uv run python scripts/convert_to_chatml.py --merge --no-think-ratio 0.20

    # Dry run — show stats without writing
    uv run python scripts/convert_to_chatml.py --merge --dry-run
"""
import json
import glob
import argparse
import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = PROJECT_ROOT / "configs" / "prompts" / "rockit_system_prompt.md"


def load_system_prompt():
    """Load the shared ROCKIT system prompt."""
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_think_block(thinking: dict) -> str:
    """Convert structured thinking JSON to <think> block with markdown steps."""
    steps = [
        ("Step 1: Context Assessment", "step_1_context"),
        ("Step 2: Market Structure", "step_2_structure"),
        ("Step 3: Order Flow", "step_3_flow"),
        ("Step 4: Key Levels", "step_4_levels"),
        ("Step 5: Day Type Classification", "step_5_day_type"),
        ("Step 6: Strategy Assessment", "step_6_setups"),
        ("Step 7: Risk Assessment", "step_7_risk"),
    ]
    lines = []
    for title, key in steps:
        content = thinking.get(key, "")
        if content:
            lines.append(f"## {title}")
            lines.append(content)
            lines.append("")
    return "\n".join(lines).strip()


def convert_pair(pair: dict, system_prompt: str, include_thinking: bool = True) -> dict:
    """Convert a single training pair to ChatML with <think> tags.

    Args:
        pair: Dict with 'input' (snapshot) and 'output' (analysis)
        system_prompt: Full ROCKIT system prompt text
        include_thinking: If True, populate <think> block; if False, use empty tags

    Returns:
        ChatML dict with 'messages' array (system/user/assistant)
    """
    snapshot = pair["input"]
    output = pair["output"]

    # Deep copy output so we don't mutate the original
    output = json.loads(json.dumps(output))

    user_content = json.dumps(snapshot, indent=2, ensure_ascii=False)

    # Extract thinking from output (it goes into <think> block, not JSON)
    thinking = output.pop("thinking", {})

    if include_thinking and isinstance(thinking, dict):
        think_text = build_think_block(thinking)
        think_block = f"<think>\n{think_text}\n</think>"
    else:
        think_block = "<think>\n</think>"

    json_output = json.dumps(output, indent=2, ensure_ascii=False)
    assistant_content = f"{think_block}\n\n{json_output}"

    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content},
        ]
    }


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English + JSON."""
    return len(text) // 4


def main():
    parser = argparse.ArgumentParser(
        description="Convert ROCKIT training pairs to ChatML with <think> CoT"
    )
    parser.add_argument("--input", help="Single input file (or use --merge for all)")
    parser.add_argument("--input-dir", default="data/training_pairs",
                        help="Directory with training_*.jsonl files")
    parser.add_argument("--output-dir", default="data/training_chatml",
                        help="Output directory for ChatML files")
    parser.add_argument("--merge", action="store_true",
                        help="Merge all training files into single train.jsonl")
    parser.add_argument("--no-think-ratio", type=float, default=0.25,
                        help="Fraction of examples without thinking (default 0.25)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show stats without writing files")
    parser.add_argument("--validate", action="store_true",
                        help="Validate existing ChatML file")
    args = parser.parse_args()

    random.seed(args.seed)

    # Validation mode
    if args.validate:
        validate_chatml(args)
        return

    # Load system prompt
    if not PROMPT_PATH.exists():
        print(f"ERROR: System prompt not found at {PROMPT_PATH}")
        return
    system_prompt = load_system_prompt()

    # Gather input files
    if args.input:
        input_files = [args.input]
    elif args.merge:
        input_files = sorted(glob.glob(f"{args.input_dir}/training_*.jsonl"))
    else:
        print("ERROR: Specify --input <file> or --merge to process all files")
        return

    if not input_files:
        print(f"No training files found in {args.input_dir}/")
        return

    # Load all pairs
    all_pairs = []
    skipped = 0
    for f in input_files:
        with open(f, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                pair = json.loads(line)
                if pair.get("output") is None:
                    skipped += 1
                    continue
                all_pairs.append(pair)

    print(f"Loaded {len(all_pairs)} complete pairs from {len(input_files)} files")
    if skipped:
        print(f"  Skipped {skipped} pairs with null output")

    # Select which pairs get empty <think> tags
    no_think_count = int(len(all_pairs) * args.no_think_ratio)
    no_think_indices = set(random.sample(range(len(all_pairs)), no_think_count))

    # Convert
    converted = []
    token_counts = []
    for i, pair in enumerate(all_pairs):
        include_thinking = i not in no_think_indices
        chatml = convert_pair(pair, system_prompt, include_thinking)
        converted.append(chatml)

        # Estimate tokens
        total_text = "".join(m["content"] for m in chatml["messages"])
        token_counts.append(estimate_tokens(total_text))

    # Shuffle for training
    random.shuffle(converted)

    # Stats
    avg_tokens = sum(token_counts) / len(token_counts) if token_counts else 0
    max_tokens = max(token_counts) if token_counts else 0
    min_tokens = min(token_counts) if token_counts else 0

    print(f"\nConversion stats:")
    print(f"  Total examples: {len(converted)}")
    print(f"  With thinking: {len(converted) - no_think_count}")
    print(f"  Without thinking: {no_think_count}")
    print(f"  Token estimates: avg={avg_tokens:.0f}, min={min_tokens}, max={max_tokens}")
    print(f"  Max seq length needed: {max_tokens} (limit: 16384)")

    if max_tokens > 16384:
        print(f"  WARNING: {sum(1 for t in token_counts if t > 16384)} examples exceed 16K tokens!")

    if args.dry_run:
        print("\n(Dry run — no files written)")
        return

    # Write output
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    out_path = output_dir / "train.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for c in converted:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(converted)} ChatML examples to {out_path}")


def validate_chatml(args):
    """Validate an existing ChatML JSONL file."""
    input_path = args.input or f"{args.output_dir}/train.jsonl"
    if not Path(input_path).exists():
        print(f"File not found: {input_path}")
        return

    errors = []
    warnings = []
    total = 0
    with_think = 0
    without_think = 0

    with open(input_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            total += 1

            try:
                example = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: Invalid JSON: {e}")
                continue

            messages = example.get("messages", [])
            if len(messages) != 3:
                errors.append(f"Line {line_num}: Expected 3 messages, got {len(messages)}")
                continue

            roles = [m["role"] for m in messages]
            if roles != ["system", "user", "assistant"]:
                errors.append(f"Line {line_num}: Wrong roles: {roles}")
                continue

            assistant = messages[2]["content"]
            if "<think>" not in assistant:
                errors.append(f"Line {line_num}: Missing <think> tag")
            elif "</think>" not in assistant:
                errors.append(f"Line {line_num}: Missing </think> tag")
            else:
                think_start = assistant.index("<think>") + len("<think>")
                think_end = assistant.index("</think>")
                think_content = assistant[think_start:think_end].strip()
                if think_content:
                    with_think += 1
                else:
                    without_think += 1

            # Check JSON output after </think>
            if "</think>" in assistant:
                after_think = assistant[assistant.index("</think>") + len("</think>"):].strip()
                try:
                    json.loads(after_think)
                except json.JSONDecodeError:
                    errors.append(f"Line {line_num}: Invalid JSON after </think>")

            # Token estimate
            total_text = "".join(m["content"] for m in messages)
            tokens = len(total_text) // 4
            if tokens > 16384:
                warnings.append(f"Line {line_num}: ~{tokens} tokens (exceeds 16K)")

    print(f"Validation: {input_path}")
    print(f"  Total examples: {total}")
    print(f"  With thinking: {with_think}")
    print(f"  Without thinking: {without_think}")
    think_ratio = with_think / total * 100 if total else 0
    print(f"  Think ratio: {think_ratio:.1f}% (target: 75%)")

    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for e in errors[:10]:
            print(f"    {e}")
        if len(errors) > 10:
            print(f"    ... and {len(errors) - 10} more")
    else:
        print(f"\n  No errors found")

    if warnings:
        print(f"\n  WARNINGS ({len(warnings)}):")
        for w in warnings[:5]:
            print(f"    {w}")


if __name__ == "__main__":
    main()
