#!/usr/bin/env python3
"""Fine-tune Qwen3.5-35B-A3B with LoRA on ROCKIT training data.

Prerequisites:
    pip install unsloth datasets trl transformers

Usage:
    # Standard training (DGX Spark, 128GB)
    uv run python scripts/train_lora.py

    # Custom rank
    uv run python scripts/train_lora.py --rank 128

    # Resume from checkpoint
    uv run python scripts/train_lora.py --resume outputs/rockit-lora/checkpoint-100

    # Dry run — load model and dataset, print stats, don't train
    uv run python scripts/train_lora.py --dry-run

Environment:
    ROCKIT_MODEL: Override model name (default: Qwen/Qwen3.5-35B-A3B)
    WANDB_PROJECT: Set to enable W&B logging (optional)
"""
import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fine-tune Qwen3.5-35B-A3B with LoRA on ROCKIT data"
    )
    parser.add_argument("--data", default="data/training_chatml/train.jsonl",
                        help="Training data in ChatML JSONL format")
    parser.add_argument("--output-dir", default="outputs/rockit-lora",
                        help="Output directory for checkpoints and final model")
    parser.add_argument("--model", default=None,
                        help="Model name/path (default: Qwen/Qwen3.5-35B-A3B)")
    parser.add_argument("--rank", type=int, default=64,
                        help="LoRA rank (default: 64, max recommended: 128)")
    parser.add_argument("--epochs", type=int, default=3,
                        help="Training epochs (default: 3)")
    parser.add_argument("--lr", type=float, default=2e-4,
                        help="Learning rate (default: 2e-4)")
    parser.add_argument("--batch-size", type=int, default=1,
                        help="Per-device batch size (default: 1)")
    parser.add_argument("--grad-accum", type=int, default=4,
                        help="Gradient accumulation steps (default: 4)")
    parser.add_argument("--max-seq-length", type=int, default=16384,
                        help="Max sequence length (default: 16384)")
    parser.add_argument("--resume", default=None,
                        help="Resume from checkpoint path")
    parser.add_argument("--dry-run", action="store_true",
                        help="Load model/data, print stats, don't train")
    parser.add_argument("--save-steps", type=int, default=50,
                        help="Save checkpoint every N steps")
    return parser.parse_args()


def main():
    args = parse_args()

    # Validate data file exists
    data_path = PROJECT_ROOT / args.data
    if not data_path.exists():
        print(f"ERROR: Training data not found at {data_path}")
        print("Run: uv run python scripts/convert_to_chatml.py --merge")
        sys.exit(1)

    # Count examples
    with open(data_path, "r", encoding="utf-8") as f:
        num_examples = sum(1 for line in f if line.strip())
    print(f"Training data: {num_examples} examples from {data_path}")

    if num_examples < 500:
        print(f"WARNING: Only {num_examples} examples. Minimum 500 recommended to avoid overfitting.")
        print("Continue? Training will proceed but results may be poor.")

    # Determine model
    model_name = args.model or os.environ.get("ROCKIT_MODEL", "Qwen/Qwen3.5-35B-A3B")
    print(f"Model: {model_name}")
    print(f"LoRA rank: {args.rank}")
    print(f"Max seq length: {args.max_seq_length}")
    print(f"Effective batch size: {args.batch_size * args.grad_accum}")
    print(f"Epochs: {args.epochs}")
    print(f"Output: {args.output_dir}")
    print()

    # Import ML libraries (slow imports, do after arg parsing)
    try:
        from unsloth import FastLanguageModel
    except ImportError:
        print("ERROR: unsloth not installed. Run: pip install unsloth")
        sys.exit(1)

    from datasets import load_dataset
    from trl import SFTTrainer
    from transformers import TrainingArguments

    # 1. Load model (BF16 — NEVER use QLoRA for Qwen3.5)
    print("Loading model (BF16)...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=args.max_seq_length,
        load_in_4bit=False,  # CRITICAL: QLoRA NOT recommended for Qwen3.5
        dtype="bfloat16",
    )
    print(f"Model loaded: {model.num_parameters() / 1e9:.1f}B parameters")

    # 2. Add LoRA adapters
    print(f"Adding LoRA adapters (r={args.rank})...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.rank,
        lora_alpha=args.rank,  # alpha = rank for BF16 LoRA
        lora_dropout=0,        # Unsloth recommends 0
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",   # Attention
            "gate_proj", "up_proj", "down_proj",        # Expert FFN
        ],
        # Router layers are NOT fine-tuned (Unsloth default)
        use_gradient_checkpointing="unsloth",
    )

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"Trainable: {trainable / 1e6:.1f}M / {total / 1e9:.1f}B ({trainable / total * 100:.2f}%)")

    # 3. Load ChatML dataset
    print("Loading dataset...")
    dataset = load_dataset(
        "json",
        data_files={"train": str(data_path)},
        split="train",
    )
    print(f"Dataset: {len(dataset)} examples")

    # 4. Apply chat template
    def format_fn(example):
        text = tokenizer.apply_chat_template(
            example["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )
        return {"text": text}

    dataset = dataset.map(format_fn, desc="Applying chat template")

    # Check token lengths
    token_lengths = []
    for example in dataset:
        tokens = tokenizer(example["text"], return_length=True)
        token_lengths.append(tokens["length"][0])

    avg_len = sum(token_lengths) / len(token_lengths)
    max_len = max(token_lengths)
    over_limit = sum(1 for l in token_lengths if l > args.max_seq_length)
    print(f"Token lengths: avg={avg_len:.0f}, max={max_len}, over {args.max_seq_length}: {over_limit}")

    if over_limit > 0:
        print(f"WARNING: {over_limit} examples will be truncated at {args.max_seq_length} tokens")

    if args.dry_run:
        print("\n--- Dry run complete. No training performed. ---")
        return

    # 5. Train
    print("\nStarting training...")
    output_dir = str(PROJECT_ROOT / args.output_dir)

    training_args = TrainingArguments(
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        warmup_steps=10,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        bf16=True,
        optim="adamw_torch_fused",  # BF16-native fused optimizer
        output_dir=output_dir,
        logging_steps=1,
        save_steps=args.save_steps,
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        report_to="wandb" if os.environ.get("WANDB_PROJECT") else "none",
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
        args=training_args,
    )

    if args.resume:
        print(f"Resuming from {args.resume}")
        trainer.train(resume_from_checkpoint=args.resume)
    else:
        trainer.train()

    # 6. Save final LoRA adapter
    final_path = os.path.join(output_dir, "final")
    print(f"\nSaving LoRA adapter to {final_path}")
    model.save_pretrained(final_path)
    tokenizer.save_pretrained(final_path)

    # 7. Save training metadata
    metadata = {
        "model": model_name,
        "lora_rank": args.rank,
        "lora_alpha": args.rank,
        "epochs": args.epochs,
        "learning_rate": args.lr,
        "effective_batch_size": args.batch_size * args.grad_accum,
        "max_seq_length": args.max_seq_length,
        "num_examples": num_examples,
        "avg_token_length": avg_len,
        "max_token_length": max_len,
        "optimizer": "adamw_torch_fused",
        "dtype": "bfloat16",
        "framework": "unsloth",
    }
    meta_path = os.path.join(final_path, "training_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Metadata saved to {meta_path}")

    print("\nTraining complete!")
    print(f"LoRA adapter: {final_path}")
    print(f"\nTo serve:")
    print(f"  vllm serve {model_name} \\")
    print(f"    --lora-modules rockit-lora={final_path} \\")
    print(f"    --reasoning-parser qwen3 \\")
    print(f"    --enable-auto-tool-choice \\")
    print(f"    --dtype bfloat16")


if __name__ == "__main__":
    main()
