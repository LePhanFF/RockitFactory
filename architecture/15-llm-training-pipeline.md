# LLM Training Pipeline Architecture

> **Revision 2** — March 2026. Complete training pipeline for ROCKIT LLM using
> Qwen3.5-35B-A3B MoE with Chain-of-Thought reasoning on DGX Spark.
> Covers: data format, CoT strategy, model selection, training framework, hardware,
> and deployment serving. Updated with DGX Spark memory optimization guidance.

## Overview

The ROCKIT LLM adds an interpretive layer on top of the deterministic engine (38 modules).
The deterministic engine computes ALL market structure. The LLM interprets, reasons,
synthesizes, and coaches — the qualitative layer that pure math cannot provide.

```
Deterministic Engine (Tier 0)          LLM (Tier 1)                Serving
──────────────────────────             ─────────────               ────────
38 modules compute:                    LLM adds:                   vLLM on DGX Spark
• IB range, extensions                 • Why this IB matters       • BF16 inference
• Day type classification              • Evidence chains           • <think> mode toggle
• DPOC regime + migration              • Strategy coaching         • Tool calling
• CRI gate                             • Position sizing           • Multi-LoRA swap
• Strategy signals                     • Risk warnings             • ~30 tok/s
• Confidence scoring                   • Evolution tracking
         │                                    │
         ▼                                    ▼
  Snapshot JSON (~1,900 tok)    →    Analysis JSON (~750 tok)
                                     + <think> reasoning (~1,500 tok)
```

---

## 1. Model Selection: Qwen3.5-35B-A3B

### Why This Model

| Requirement | Qwen3.5-35B-A3B | Fit |
|-------------|-----------------|-----|
| Fits DGX Spark 128GB | BF16: ~70GB (58GB headroom) | Yes |
| LoRA trainable on DGX Spark | BF16 LoRA: ~74GB (54GB headroom) | Yes |
| Chain-of-Thought reasoning | Native `<think>` blocks | Yes |
| Tool calling / agents | BFCL-V4: 67.3 (beats GPT-5 mini 55.5) | Yes |
| Coding for agent tasks | SWE-bench: 69.2, CodeForces: 2028 | Yes |
| Efficient inference | Only 3B active out of 35B total params | Yes |
| Long context | 262K native, 1M extended | Yes |
| Open license | Apache 2.0 | Yes |

### Architecture Details

```
Qwen3.5-35B-A3B
├── 35B total parameters, 3B active per token
├── 40 layers: 10 × (3 DeltaNet-MoE + 1 Attention-MoE)
├── 256 experts total, 8 routed + 1 shared per token
├── Hybrid: Gated DeltaNet (linear attention) + full attention (3:1 ratio)
├── Vocabulary: 248,320 tokens, 201 languages
├── Context: 262K native, 1M via YaRN
└── Native <think>...</think> Chain-of-Thought support
```

### Comparison vs Previous-Gen Qwen3-30B-A3B

| Aspect | Qwen3-30B-A3B | Qwen3.5-35B-A3B |
|--------|---------------|-----------------|
| Context | 131K | 262K (2x) |
| Tool use (BFCL-V4) | Not top tier | 67.3 |
| Agent (Terminal-Bench) | ~22.5 | 40.5 |
| Architecture | Standard Transformer MoE | Hybrid DeltaNet + Attention |
| Long-context stability | Quality drops at boundaries | Flat — no degradation |
| Reasoning quality | Vague hedging | Structured step-by-step |
| Vocabulary | 150K | 248K |

---

## 2. Training Data Format: ChatML with `<think>` CoT

### Target Format (one JSONL line per training example)

```json
{
  "messages": [
    {
      "role": "system",
      "content": "<full ROCKIT system prompt from configs/prompts/rockit_system_prompt.md>"
    },
    {
      "role": "user",
      "content": "<deterministic snapshot as pretty-printed JSON string>"
    },
    {
      "role": "assistant",
      "content": "<think>\n## Step 1: Context Assessment\n...\n## Step 2: Market Structure\n...\n## Step 3: Order Flow\n...\n## Step 4: Key Levels\n...\n## Step 5: Day Type Classification\n...\n## Step 6: Strategy Assessment\n...\n## Step 7: Risk Assessment\n...\n</think>\n\n{\"premarket_read\": \"...\", \"or_play\": \"...\", ...}"
    }
  ]
}
```

### Why ChatML + `<think>` Tags

1. **Native to Qwen3.5** — ChatML uses `<|im_start|>`/`<|im_end|>` tokens that Qwen was trained on. Zero conversion at tokenization.
2. **Leverages pre-trained reasoning** — Qwen3.5 was trained on 300K CoT examples with `<think>` blocks. Our fine-tuning reinforces this existing capability.
3. **Separates reasoning from output** — The `<think>` block contains the 7 reasoning steps. The JSON output after `</think>` is what downstream code consumes.
4. **Toggleable at inference** — Can enable/disable thinking per request. Fast mode skips reasoning for real-time use.
5. **Matches inference format** — Training data mirrors exactly how the model will be called in production.

### Token Budget Per Example

| Component | Chars | Tokens | Notes |
|-----------|-------|--------|-------|
| System prompt | ~14,800 | ~3,700 | Constant across all examples |
| User (snapshot) | ~12,300 | ~3,100 | Pretty-printed JSON |
| Assistant `<think>` block | ~3,000 | ~750 | 7 reasoning steps |
| Assistant JSON output | ~4,000 | ~1,000 | 12 analysis fields |
| **Total** | **~34,100** | **~8,550** | Fits in 16K `max_seq_length` |

### Reasoning Steps Inside `<think>` Block

```
<think>
## Step 1: Context Assessment
Opened gap_down below prior VA (VAH 25094.75, VAL 24490.75). Price 24535.0 sits
259pts below VAL. Overnight range 146.5pts, ONH 24739.25. Compression ratio 0.7.

## Step 2: Market Structure
IB complete: 471.0pts (extreme width, 2.5x ATR). IBH 25356.0, IBL 24885.0.
Extension: 93pts above IBH. IB width class: extreme. Price in upper third.

## Step 3: Order Flow
DPOC regime: stabilizing_hold forming_floor. Net migration: -100.75pts (bearish).
Avg velocity: 0 pts/30min — stalled. Wick parade: 22 bull / 25 bear — near neutral.
TPO fattening: at_vah — bullish acceptance developing.

## Step 4: Key Levels
(1) IB mid 25120.5 — 55.5pts above, major pivot
(2) Prior POC 25068.75 — 3.75pts above, strong magnet
(3) Seam level 25120.5 — bull/bear dividing line

## Step 5: Day Type Classification
Engine classifies Neutral Range because: (1) Extreme IB 471pts = responsive not
initiative, (2) Weak trend strength caps confidence, (3) DPOC stabilizing not
trending, (4) No morph confirmed.

## Step 6: Strategy Assessment
OR Reversal: Outside window (9:30-10:15). Edge Fade: Outside window (10:00-13:30).
80P Rule: No entry after 13:00 (42.3% WR, 1.74 PF). B-Day: No entry after 13:00
(46.4% WR, 1.47 PF). Mean Reversion: LOSING (42.6% WR, 0.91 PF) — unreliable.

## Step 7: Risk Assessment
CRI: STAND_DOWN. Terrain A2 (score 2.75). Bear Trap detected. Reclaim: Clean (4.0).
Breath: Shallow. Permission: Flat, no entry. No new positions permitted.
</think>
```

### JSON Output After `</think>` (what code parses)

```json
{
  "premarket_read": "Opened gap down 259pts below prior VAL 24490.75...",
  "or_play": "Outside window — OR Reversal only active 9:30-10:15.",
  "ib_read": "471pt extreme IB (2.5x ATR). Responsive two-sided trade...",
  "day_type_call": {
    "classification": "Neutral Range",
    "evidence": ["Extreme IB 471pts = responsive", "Weak trend caps conviction"],
    "confidence_breakdown": "Base 40% + time_cap = 55%. Weak trend caps at 75%.",
    "skew": "Bullish skew 0.8 strength, seam at 25120.5",
    "morph_watch": "Close above 25120.5 with accelerating DPOC = morph to Trend Up"
  },
  "strategy_assessment": {
    "or_reversal": "Outside window (9:30-10:15)",
    "or_acceptance": "Passed — no longer relevant",
    "eighty_percent": "No entry after 13:00 ET (42.3% WR, 1.74 PF)",
    "twenty_percent": "No IB extension developing",
    "b_day": "No entry after 13:00 ET (46.4% WR, 1.47 PF)",
    "edge_fade": "Outside window (10:00-13:30)",
    "mean_reversion": "WARNING: LOSING strategy (42.6% WR, 0.91 PF). Unreliable."
  },
  "value_area_play": "80P window closed. Price inside IB rotation.",
  "tpo_remarks": "Normal shape, fattening at VAH = bullish acceptance...",
  "evolution": "Bias shifted from Bearish to Bullish since 14:30...",
  "evidence": ["IB extreme 471pts", "DPOC stabilizing", "Bear Trap detected"],
  "what_could_go_wrong": ["Break below IBL 24885", "DPOC reverses down"],
  "one_liner": "Neutral Range, CRI STAND_DOWN — observe only, no entries.",
  "discipline": "CRI STAND_DOWN: no new entries. After 13:00 ET: 80P/B-Day/Edge Fade closed."
}
```

---

## 3. Dataset Composition

### Current Training Data

| Source | Pairs | Status |
|--------|-------|--------|
| 2026-02-26 | 78 | Complete (all 78 RTH snapshots) |
| 2026-02-27 | 78 | Complete (all 78 RTH snapshots) |
| 2026-03-02 | 4 | Partial (key times only) |
| 2026-03-03 | 4 | Partial (key times only) |
| **Total** | **164** | Growing daily |

### Target Scale

| Milestone | Pairs | Days | Notes |
|-----------|-------|------|-------|
| MVP (validate pipeline) | 500 | 7 | Minimum for initial LoRA test |
| V1 (production LoRA) | 2,000 | 26 | Sweet spot for LoRA on 30B+ |
| V2 (robust LoRA) | 5,000 | 65 | High quality, covers market regimes |
| V3 (full coverage) | 14,000+ | 180 | All available session data |

### Required Dataset Mix

Per Qwen3 official guidance:
- **75% with `<think>` reasoning** — full CoT analysis
- **25% without reasoning** — same JSON output, empty `<think></think>` tags

This teaches the model when to reason deeply vs respond directly.

### Market Condition Coverage

Training data should cover all 7 day types:

| Day Type | Target % | Current Status |
|----------|----------|---------------|
| Trend Up | 15% | Under-represented |
| Trend Down | 10% | 6 pairs (Feb 26 AM) |
| Open Drive | 5% | Not yet captured |
| Open Auction | 10% | Not yet captured |
| Double Distribution | 5% | Not yet captured |
| Neutral Range | 30% | 125 pairs (over-represented) |
| Balance | 25% | 33 pairs |

**Action:** Prioritize generating snapshots for days with Trend/Open Drive/DD classifications to balance the dataset.

---

## 4. Data Pipeline

### Step 1: Generate Deterministic Snapshots

```bash
# Generate 78 RTH snapshots per day at 5-min intervals
uv run python scripts/generate_deterministic_snapshots.py --days 90 --rth-only
# Output: data/json_snapshots/deterministic_{date}.jsonl
```

### Step 2: Generate Training Pairs

```bash
# Skill-based (no API cost, uses Claude subscription)
/generate-training-pairs --from 2026-01-01 --to 2026-03-03

# OR API-based (Anthropic Messages API)
uv run python scripts/training_pipeline.py prepare --days 90
uv run python scripts/training_pipeline.py generate --chunk chunk_20260226.jsonl
```

### Step 3: Convert to ChatML Format

```bash
# Convert {input, output} pairs → ChatML messages with <think> tags
uv run python scripts/convert_to_chatml.py --merge
# Output: data/training_chatml/train.jsonl
```

Conversion logic:
1. System message = full `configs/prompts/rockit_system_prompt.md`
2. User message = `json.dumps(snapshot, indent=2)` (pretty-printed)
3. Assistant message = `<think>` block from `thinking` fields + JSON from remaining fields
4. 75% of examples include full `<think>` content, 25% have empty `<think></think>`

### Step 4: Validate

```bash
uv run python scripts/generate_training_pairs.py --validate-all
uv run python scripts/generate_training_pairs.py --stats
```

### Pipeline Diagram

```
NQ/ES/YM CSVs                Deterministic Engine         Training Pair Gen
(data/sessions/)             (38 modules)                 (Claude skill or API)
      │                           │                              │
      ▼                           ▼                              ▼
 1min volumetric    →    78 snapshots/day    →    78 pairs/day (input→output)
      │                  (5-min intervals)          │
      │                           │                 ▼
      │                           │          Convert to ChatML
      │                           │          (with <think> tags)
      │                           │                 │
      │                           │                 ▼
      │                           │          data/training_chatml/
      │                           │          train.jsonl
      │                           │                 │
      │                           │                 ▼
      │                           │          LoRA Fine-Tuning
      │                           │          (Unsloth on DGX Spark)
      │                           │                 │
      │                           │                 ▼
      │                           │          LoRA Adapter
      │                           │          (outputs/rockit-lora/)
      │                           │                 │
      ▼                           ▼                 ▼
 Daily merge    →    Daily snapshots    →    Weekly retrain (if new data)
 (Google Drive)      (automated)             (automated via CI)
```

---

## 5. Training Configuration

### Framework: Unsloth

Selected for:
- 2-5x faster training than Transformers baseline
- ~12x faster for MoE models specifically
- 50% less VRAM than FlashAttention2
- Native Qwen3.5 MoE support
- DGX Spark optimization (NVIDIA partnership)

### LoRA Configuration

```python
# LoRA adapter config
r = 64                    # Rank 64 recommended for 128GB DGX Spark (r=128 max possible)
lora_alpha = 64           # Match rank (alpha = r for BF16 LoRA)
lora_dropout = 0.0        # Unsloth recommends 0
target_modules = [
    "q_proj", "k_proj", "v_proj", "o_proj",  # Attention
    "gate_proj", "up_proj", "down_proj"        # Expert FFN layers
]
# Router layers are NOT fine-tuned (default in Unsloth)
# With r=64: LoRA adds ~2.1GB params. r=128 adds ~4.2GB — still fits 128GB.
```

### Training Hyperparameters

```python
# Training config for DGX Spark (128GB unified LPDDR5X)
per_device_train_batch_size = 1
gradient_accumulation_steps = 4    # Effective batch size = 4
max_seq_length = 16384             # Covers ~8,550 token examples
learning_rate = 2e-4               # Standard for LoRA SFT
warmup_steps = 10
num_train_epochs = 3               # 3 epochs for <2000 examples
lr_scheduler_type = "cosine"
weight_decay = 0.01
optim = "adamw_torch_fused"        # BF16-native fused optimizer (faster + more stable than 8bit)
bf16 = True                        # Always bf16 on DGX Spark — never QLoRA
gradient_checkpointing = "unsloth" # Unsloth optimized (saves ~30% VRAM)
```

> **Optimizer note:** `adamw_torch_fused` is preferred for BF16 LoRA on DGX Spark because
> the unified memory architecture doesn't benefit from 8-bit quantized optimizers.
> Alternative: `paged_adamw_32bit` if memory pressure is observed at r=128.

### Flash Attention 2

Enable Flash Attention 2 for both training and inference. Reduces memory for long sequences
and improves throughput ~2x for our 8K-16K token examples.

```python
# Unsloth handles this automatically via:
model, tokenizer = FastLanguageModel.from_pretrained(
    ...,
    attn_implementation="flash_attention_2",  # Explicit if needed
)
```

### Gradient Checkpointing

Enabled via Unsloth's optimized implementation. Trades ~15% compute for ~30% VRAM savings.
Essential at r=64/128 to leave headroom for activation memory.

### DGX Spark Memory Budget (BF16 LoRA, r=64)

```
128 GB total unified LPDDR5X
├── Base model (BF16)           ~70 GB
├── LoRA adapters (r=64)         ~2 GB
├── Optimizer states            ~12 GB  (adamw_torch_fused, BF16 master weights)
├── Gradient checkpoints         ~8 GB  (Unsloth optimized)
├── Activations + KV cache      ~20 GB  (batch_size=1, seq_len=16K)
├── CUDA overhead                ~6 GB
└── Headroom                    ~10 GB  (safety margin)
```

> At r=128: optimizer states grow to ~24GB and LoRA to ~4GB. Total ~120GB — tight
> but feasible. Start with r=64, increase if underfitting.

### Training Script

See `scripts/train_lora.py` for the full standalone script. Summary:

```python
# Key settings (see scripts/train_lora.py for complete code)
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="Qwen/Qwen3.5-35B-A3B",
    max_seq_length=16384,
    load_in_4bit=False,  # CRITICAL: QLoRA NOT recommended for Qwen3.5
    dtype="bfloat16",
)

model = FastLanguageModel.get_peft_model(
    model, r=64, lora_alpha=64, lora_dropout=0,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    use_gradient_checkpointing="unsloth",
)

# Train with SFTTrainer, adamw_torch_fused, BF16, cosine LR schedule
```

### Alternative Framework: MS-Swift

If Unsloth has compatibility issues with Qwen3.5 MoE, MS-Swift (ModelScope) is the
backup framework. Key advantage: built-in support for mixed thinking/non-thinking data.

```bash
# MS-Swift training with loss_scale for mixed <think> datasets
swift sft \
  --model Qwen/Qwen3.5-35B-A3B \
  --dataset data/training_chatml/train.jsonl \
  --lora_rank 64 \
  --lora_alpha 64 \
  --target_modules q_proj k_proj v_proj o_proj gate_proj up_proj down_proj \
  --loss_scale ignore_empty_think \
  --bf16 true \
  --max_length 16384 \
  --per_device_train_batch_size 1 \
  --gradient_accumulation_steps 4 \
  --learning_rate 2e-4 \
  --num_train_epochs 3 \
  --output_dir outputs/rockit-lora
```

> `--loss_scale ignore_empty_think` ensures the model doesn't learn to suppress thinking
> from the 25% non-thinking examples — it only learns the output format for those.

### Multi-GPU Scaling (Future)

If scaling beyond DGX Spark to multi-GPU setups (e.g., DGX A100/H100 cluster):

```python
# DeepSpeed Stage 2 config (deepspeed_config.json)
{
    "bf16": {"enabled": true},
    "zero_optimization": {
        "stage": 2,
        "offload_optimizer": {"device": "none"},
        "allgather_partitions": true,
        "allgather_bucket_size": 2e8,
        "reduce_scatter": true,
        "reduce_bucket_size": 2e8
    },
    "gradient_accumulation_steps": 4,
    "train_micro_batch_size_per_gpu": 1
}
```

> DeepSpeed Stage 2 shards optimizer states + gradients across GPUs.
> Not needed for single DGX Spark but ready for horizontal scaling.

### Hardware: DGX Spark

```
NVIDIA DGX Spark
├── 128GB unified LPDDR5X (shared CPU+GPU)
├── Grace ARM CPU + Blackwell GPU
├── ~273 GB/s memory bandwidth
│
├── Inference: BF16 model ~70GB + KV cache ~58GB available
├── Training:  BF16 LoRA ~74GB + buffers ~54GB available
│
├── QLoRA: NOT recommended for Qwen3.5 (quantization errors)
└── Full fine-tune: NOT possible (would need ~140GB+)
```

---

## 6. Inference Serving

### vLLM Deployment

```bash
# Serve fine-tuned model with tool calling + thinking mode
vllm serve Qwen/Qwen3.5-35B-A3B \
  --lora-modules rockit-lora=outputs/rockit-lora/final \
  --port 8000 \
  --max-model-len 32768 \
  --reasoning-parser qwen3 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --language-model-only \
  --dtype bfloat16
```

Key flags:
- `--lora-modules`: Load the fine-tuned LoRA adapter
- `--reasoning-parser qwen3`: Parse `<think>` blocks from output
- `--enable-auto-tool-choice`: Enable function calling for agents
- `--language-model-only`: Skip vision encoder (saves memory)

### Inference Modes

| Mode | Enable Thinking | Use Case | Latency |
|------|----------------|----------|---------|
| Full analysis | `enable_thinking: true` | Dashboard, training, review | ~5s |
| Fast signal | `enable_thinking: false` | Real-time alerts | ~1s |
| Agent debate | `enable_thinking: true` + tools | Advocate/Skeptic pipeline | ~10s |

### Sampling Parameters

| Mode | Temperature | top_p | top_k | Notes |
|------|-----------|-------|-------|-------|
| Trading analysis | 0.6 | 0.95 | 20 | Precise, grounded |
| Agent reasoning | 1.0 | 0.95 | 20 | Exploratory thinking |
| Fast signal | 0.3 | 0.8 | 20 | Deterministic output |

---

## 7. Conversion Script

Converts current `{input, output}` training pairs to ChatML with `<think>` tags.

**File:** `scripts/convert_to_chatml.py`

```python
#!/usr/bin/env python3
"""Convert ROCKIT training pairs to ChatML format with <think> CoT tags."""
import json, glob, argparse, random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = PROJECT_ROOT / "configs" / "prompts" / "rockit_system_prompt.md"


def load_system_prompt():
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
    """Convert a single training pair to ChatML with <think> tags."""
    snapshot = pair["input"]
    output = pair["output"]

    user_content = json.dumps(snapshot, indent=2, ensure_ascii=False)

    # Build assistant content
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="data/training_pairs")
    parser.add_argument("--output-dir", default="data/training_chatml")
    parser.add_argument("--merge", action="store_true",
                        help="Merge all into single train.jsonl")
    parser.add_argument("--no-think-ratio", type=float, default=0.25,
                        help="Fraction of examples without thinking (default 0.25)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    system_prompt = load_system_prompt()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_files = sorted(glob.glob(f"{args.input_dir}/training_*.jsonl"))
    all_pairs = []

    for f in input_files:
        with open(f, "r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    all_pairs.append(json.loads(line))

    # Randomly select which pairs get empty <think> tags
    no_think_count = int(len(all_pairs) * args.no_think_ratio)
    no_think_indices = set(random.sample(range(len(all_pairs)), no_think_count))

    converted = []
    for i, pair in enumerate(all_pairs):
        include_thinking = i not in no_think_indices
        converted.append(convert_pair(pair, system_prompt, include_thinking))

    random.shuffle(converted)  # Shuffle for training

    out_path = output_dir / "train.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for c in converted:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"Converted {len(converted)} pairs -> {out_path}")
    print(f"  With thinking: {len(converted) - no_think_count}")
    print(f"  Without thinking: {no_think_count}")


if __name__ == "__main__":
    main()
```

---

## 8. Quality Gates

### Per-Pair Validation

- All 13 output fields present
- All 7 thinking steps present (or "NA — reason")
- `day_type_call.classification` matches `inference.day_type.type`
- Strategy WR/PF stats accurate (OR Rev 64.4%/2.96, etc.)
- Mean Reversion flagged as losing (0.91 PF)
- `one_liner` under 140 characters
- Time-phase rules respected
- CRI components cited

### Dataset-Level Validation

- Day type distribution covers all 7 types
- Time distribution covers full RTH (09:30-15:55)
- No duplicate snapshots
- Train/validation split: 90/10
- Token counts within max_seq_length

### Training Metrics

| Metric | Target | Action if Missed |
|--------|--------|-----------------|
| Train loss | Decreasing each epoch | Increase rank, check data quality |
| Validation loss | Stable or decreasing | Stop early if increasing (overfitting) |
| JSON parse rate | >98% | More structured examples in training |
| Thinking coherence | Manual spot-check | Review and regenerate low-quality pairs |
| Number grounding | Cites exact snapshot values | Add more number-heavy examples |

---

## 9. File Structure

```
RockitFactory/
├── configs/prompts/
│   ├── rockit_system_prompt.md          # Shared system prompt (training + inference)
│   └── output_schema.json              # JSON schema for output validation
│
├── data/
│   ├── sessions/                       # Source CSVs (NQ/ES/YM volumetric)
│   ├── json_snapshots/                 # Deterministic snapshots (78/day)
│   │   └── deterministic_{date}.jsonl
│   ├── training_pairs/                 # Raw training pairs (current format)
│   │   ├── training_{date}.jsonl
│   │   ├── chunks/                     # Pipeline work chunks
│   │   └── manifest.json               # Pipeline progress tracker
│   └── training_chatml/                # Converted ChatML format (training input)
│       └── train.jsonl
│
├── scripts/
│   ├── generate_deterministic_snapshots.py   # Snapshot generation
│   ├── training_pipeline.py                  # Batch pipeline (prepare/generate/merge)
│   ├── generate_training_pairs.py            # Validation + stats
│   ├── gen_training_batch.py                 # Snapshot summary helper
│   ├── convert_to_chatml.py                  # Format converter
│   └── train_lora.py                         # Unsloth training script
│
└── outputs/
    └── rockit-lora/                    # Saved LoRA adapters
        └── final/
```

---

## 10. Roadmap

| Phase | Milestone | Pairs | Timeline |
|-------|-----------|-------|----------|
| **Phase 0** (current) | Generate pairs + validate pipeline | 164 → 500 | Week 1-2 |
| **Phase 1** | Convert to ChatML, first LoRA training run | 500-1,000 | Week 3-4 |
| **Phase 2** | Evaluate, iterate on prompts, balance dataset | 1,000-2,000 | Week 5-8 |
| **Phase 3** | Production LoRA, integrate with vLLM serving | 2,000+ | Week 9-12 |
| **Phase 4** | Self-learning loop: daily retrain, A/B testing | 5,000+ | Ongoing |

### Critical Warnings

1. **Do NOT use QLoRA** for Qwen3.5 — Unsloth explicitly warns of higher quantization errors
2. **Do NOT fine-tune router layers** — destabilizes expert routing
3. **Do NOT skip the 25% non-thinking mix** — preserves hybrid fast/thinking capability
4. **Do NOT train on <500 pairs** — high overfitting risk; start with 500+ minimum
5. **Always use `encoding='utf-8'`** when writing files on Windows
