# Training & MLOps Technical Design

> **Status:** Draft
> **Covers:** Model selection, training pipeline, evaluation, registry, quantization, serving, benchmarking, automation
> **Does NOT cover:** Deterministic strategy code (see 04-10), agent orchestration (see 14-agent-graph.md)

---

## 1. Purpose & Scope

This document specifies the end-to-end training pipeline for RockitFactory's LLM component. It answers:

1. **How do we train?** — LoRA fine-tuning with Unsloth (single GPU) or Axolotl (multi-GPU DGX)
2. **How do we evaluate?** — Domain-specific eval suite + standard benchmarks + LLM-as-judge
3. **How do we compare models?** — Side-by-side benchmarking framework with leaderboard
4. **How do we deploy?** — AWQ quantization, vLLM multi-LoRA serving, auto-rollback
5. **How do we automate?** — APScheduler triggers, GitHub Actions CI/CD, GCS event pipeline

### What This Doc Replaces

This supersedes the training-related pseudo-code in `architecture/03-pipeline-mlops.md` with concrete tool choices, real configs, and tested commands. Key changes from the architecture doc:

| Architecture Doc | This Design Doc |
|-----------------|-----------------|
| MLflow for tracking | **W&B** (free tier, native HF/TRL integration) |
| Generic "LoRA training" | **Unsloth** (single GPU) + **Axolotl** (multi-GPU) |
| 4-bit QLoRA everywhere | **bf16 LoRA for MoE** models (QLoRA breaks router layers) |
| Generic "model serving" | **vLLM multi-LoRA** + **AWQ/Marlin** quantization |
| CloudBuild pseudo-code | **GitHub Actions** concrete YAML |

---

## 2. Tool Stack

### 2.1 Training

| Tool | Use Case | Why |
|------|----------|-----|
| **Unsloth** | Single-GPU LoRA training (dev, experiments) | 2-5x speedup, native Qwen3.5 support, fused kernels |
| **Axolotl** | Multi-GPU training on DGX | FSDP/DeepSpeed ZeRO-2, proven multi-node, YAML-driven |
| **TRL** | Underlying SFT/DPO trainer | HuggingFace standard, used by both Unsloth and Axolotl |
| **PEFT** | LoRA adapter management | Load/merge/save adapters, industry standard |

### 2.2 Experiment Tracking

| Tool | Use Case | Why |
|------|----------|-----|
| **Weights & Biases (W&B)** | Experiment tracking, hyperparameter sweeps | Free tier sufficient, native HF Trainer callback, better UX than MLflow |

**Why W&B over MLflow:**
- Zero infrastructure — no tracking server to host
- Native `wandb` callback in HuggingFace Trainer (1-line integration)
- Free tier: unlimited experiments, 100GB artifacts, team of 1
- Built-in hyperparameter sweep (Bayesian, grid, random)
- Better visualization for loss curves, gradient norms, learning rate schedules

### 2.3 Evaluation

| Tool | Use Case | Why |
|------|----------|-----|
| **lm-eval-harness** | Standard benchmarks (MMLU, HellaSwag, ARC) | Sanity check that fine-tuning didn't break general capability |
| **Custom Rockit eval suite** | Domain-specific evaluation | Day type accuracy, bias accuracy, confidence MAE, etc. |
| **Opus 4.6 LLM-as-judge** | Analysis quality scoring | Grades narrative quality, reasoning depth, section completeness |

### 2.4 Quantization

| Format | Use Case | Tool | Notes |
|--------|----------|------|-------|
| **AWQ** | Production vLLM serving | AutoAWQ | 4-bit, Marlin kernel support (741 tok/s) |
| **GGUF** | Local dev via Ollama | llama.cpp `convert` | Q4_K_M or Q5_K_M for Mac Mini |
| **BitsAndBytes** | Training-time quantization | bitsandbytes | 4-bit NF4 for dense models ONLY |

**Critical: MoE quantization**
- Dense models (Qwen3.5-14B, 32B): QLoRA 4-bit via BitsAndBytes is fine
- MoE models (Qwen3.5-30B-A3B): Use **bf16 LoRA only**, NOT QLoRA
  - QLoRA 4-bit quantizes router weights, breaking expert selection
  - The 3B active parameter footprint fits in bf16 on a single 80GB GPU
  - Post-training AWQ quantization is safe (router weights stay fp16)

### 2.5 Serving

| Tool | Use Case | Why |
|------|----------|-----|
| **vLLM** | Production inference (DGX) | Multi-LoRA hot-swap, PagedAttention, continuous batching |
| **SGLang** | Alternative to vLLM (evaluate in Phase 2) | 29% faster on H100, RadixAttention for multi-turn agent conversations |
| **Ollama** | Local dev inference (Mac Mini) | Simple GGUF loading, good enough for development |

**vLLM multi-LoRA serving** — Load the base model once, swap LoRA adapters per-request:
```bash
# Start vLLM with multi-LoRA support
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3.5-30B-A3B \
    --enable-lora \
    --lora-modules advocate=adapters/advocate-v003 \
                   skeptic=adapters/skeptic-v003 \
    --max-loras 4 \
    --max-lora-rank 64 \
    --tensor-parallel-size 2
```

> **Note:** With the "one model, one LoRA" design (architecture decision #8), we use a single adapter. Agent role differentiation is via system prompts. The multi-LoRA capability is reserved for A/B testing different adapter versions simultaneously.

### 2.6 Data Versioning

| Phase | Approach | Tool |
|-------|----------|------|
| Phase 1 (now) | GCS path convention with commit SHA | `gs://rockit-data/{commit_sha}/` |
| Phase 2 (later) | DVC for proper versioning | `dvc push/pull` with GCS remote |

```
gs://rockit-data/
├── training/
│   ├── v001/                         # Versioned datasets
│   │   ├── train.jsonl
│   │   ├── val.jsonl
│   │   ├── test.jsonl
│   │   └── manifest.json             # { commit_sha, num_examples, date_range, split_strategy }
│   ├── v002/
│   └── current -> v002/
├── holdout/
│   └── rockit-eval-50.jsonl          # 50-session holdout (NEVER used in training)
└── raw/
    ├── local-analysis/
    ├── local-analysis-format/
    └── xai-analysis/
```

---

## 3. Model Registry & Comparison Framework

### 3.1 ModelCard

Every trained model (adapter) gets a ModelCard stored alongside it:

```python
# packages/rockit-train/src/rockit_train/registry.py
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

@dataclass
class ModelCard:
    """Metadata for a trained adapter."""
    # Identity
    model_id: str                          # e.g., "qwen3.5-30b-a3b/v003"
    base_model: str                        # e.g., "Qwen/Qwen3.5-30B-A3B"
    adapter_path: str                      # GCS or local path to adapter weights

    # Architecture
    architecture: str                      # "dense" or "moe"
    total_params_b: float                  # Total parameters in billions
    active_params_b: float                 # Active params (= total for dense, < total for MoE)
    lora_rank: int
    lora_alpha: int
    target_modules: list[str]

    # Training
    training_mode: str                     # "incremental" or "full"
    training_tool: str                     # "unsloth" or "axolotl"
    quantization_training: str             # "bf16", "4bit-bnb", "8bit"
    dataset_version: str                   # e.g., "v002"
    num_training_examples: int
    epochs: int
    learning_rate: float
    wandb_run_url: str | None = None

    # Evaluation
    eval_results: dict = field(default_factory=dict)  # metric_name -> score
    eval_gate_passed: bool = False
    beats_production: bool = False

    # Metadata
    git_sha: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = "automated"          # "automated" or user name
    notes: str = ""


@dataclass
class ModelLeaderboard:
    """Ranked list of models by domain metrics."""
    entries: list[ModelCard]
    ranked_by: str = "day_type_accuracy"   # Primary ranking metric

    def to_json(self, path: Path) -> None:
        """Write leaderboard to JSON for dashboard consumption."""
        ...

    def best_model(self) -> ModelCard:
        """Return the top-ranked model."""
        return self.entries[0]

    def compare(self, model_a: str, model_b: str) -> dict:
        """Side-by-side metric comparison between two models."""
        ...
```

### 3.2 ModelBenchmark Runner

```python
# packages/rockit-train/src/rockit_train/benchmark.py
from dataclasses import dataclass
from pathlib import Path

@dataclass
class BenchmarkResult:
    model_id: str
    # Domain metrics
    day_type_accuracy: float          # % correct day type classification
    bias_accuracy: float              # % correct bias direction
    confidence_mae: float             # Mean absolute error on confidence (0-100)
    section_completeness: float       # % of 11 mandatory sections present and valid
    key_level_accuracy: float         # % of key levels within 2 ticks of reference
    # Oracle comparison
    deterministic_agreement: float    # % agreement with deterministic engine signals
    # LLM-as-judge
    analysis_quality_score: float     # Opus 4.6 quality grade (0-100)
    # Standard benchmarks
    mmlu_score: float | None = None
    hellaswag_score: float | None = None

class ModelBenchmark:
    """Run any model through the Rockit evaluation suite."""

    def __init__(self, holdout_path: str, production_model_id: str | None = None):
        self.holdout_path = holdout_path
        self.production_model_id = production_model_id

    def run(self, model_id: str, adapter_path: str, base_model: str) -> BenchmarkResult:
        """
        Full benchmark pipeline:
        1. Load model + adapter
        2. Run on holdout set (50 sessions)
        3. Score predictions against reference labels
        4. Run LLM-as-judge on a sample
        5. Optionally run lm-eval-harness standard benchmarks
        """
        ...

    def compare(self, result_a: BenchmarkResult, result_b: BenchmarkResult) -> dict:
        """
        Side-by-side comparison with statistical significance.
        Returns dict with per-metric comparison and overall recommendation.
        """
        ...
```

### 3.3 CLI Interface

```bash
# Benchmark a single model
uv run python -m rockit_train.benchmark \
    --model Qwen/Qwen3.5-30B-A3B \
    --adapter gs://rockit-models/qwen3.5-30b-a3b/v003/adapter \
    --holdout gs://rockit-data/holdout/rockit-eval-50.jsonl

# Compare against production
uv run python -m rockit_train.benchmark \
    --model Qwen/Qwen3.5-30B-A3B \
    --adapter gs://rockit-models/qwen3.5-30b-a3b/v003/adapter \
    --compare production \
    --holdout gs://rockit-data/holdout/rockit-eval-50.jsonl

# Run leaderboard across all registered models
uv run python -m rockit_train.leaderboard \
    --holdout gs://rockit-data/holdout/rockit-eval-50.jsonl \
    --output leaderboard.json

# Quick model health check (subset of holdout)
uv run python -m rockit_train.benchmark \
    --model Qwen/Qwen3.5-30B-A3B \
    --adapter adapters/v003 \
    --quick  # 10 sessions instead of 50
```

---

## 4. Training Pipeline (End-to-End)

### 4.1 Dataset Builder

Converts deterministic snapshots + labels into training-ready JSONL:

```python
# packages/rockit-train/src/rockit_train/dataset.py
from dataclasses import dataclass
from pathlib import Path

@dataclass
class DatasetConfig:
    raw_data_dir: str                  # Path to raw JSONL files
    output_dir: str                    # Where to write train/val/test splits
    holdout_sessions: list[str]        # Session dates reserved for evaluation (NEVER train on these)
    val_ratio: float = 0.1            # 10% validation
    test_ratio: float = 0.1           # 10% test
    temporal_split: bool = True        # Split by time, not random
    min_sections: int = 8             # Minimum output sections to keep example
    max_seq_length: int = 4096        # Truncate examples longer than this

class DatasetBuilder:
    """Build training datasets from raw JSONL files."""

    def __init__(self, config: DatasetConfig):
        self.config = config

    def build(self) -> dict:
        """
        Pipeline:
        1. Load all raw JSONL files (local-analysis, local-analysis-format, xai-analysis)
        2. Validate schema (required fields present)
        3. Deduplicate (same session_date + current_et_time)
        4. Remove holdout sessions
        5. Quality filter (min_sections, max_seq_length)
        6. Format for training (chat template or completion format)
        7. Temporal split (train/val/test by date, not random)
        8. Write output files + manifest
        """
        ...

    def format_example(self, raw: dict) -> dict:
        """
        Convert raw JSONL to training format.
        Uses chat template format for instruct models:
        {
            "messages": [
                {"role": "system", "content": ROCKIT_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(raw["input"])},
                {"role": "assistant", "content": json.dumps(raw["output"])}
            ]
        }
        """
        ...
```

### 4.2 Training Configs

#### Unsloth (Single GPU — Dev/Experiments)

```python
# packages/rockit-train/src/rockit_train/train_unsloth.py
from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
import wandb

def train_with_unsloth(config_path: str):
    """Single-GPU training with Unsloth (2-5x speedup)."""

    # Load config
    config = load_yaml(config_path)

    # Initialize W&B
    wandb.init(
        project="rockit-training",
        name=f"{config['model']['name']}-{config['training']['mode']}",
        config=config,
    )

    # Load model with Unsloth optimizations
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config["model"]["name"],
        max_seq_length=config["training"]["max_seq_length"],
        dtype=None,       # Auto-detect (bf16 on Ampere+)
        load_in_4bit=config["model"]["architecture"] != "moe",  # NO 4-bit for MoE!
    )

    # Apply LoRA
    model = FastLanguageModel.get_peft_model(
        model,
        r=config["training"]["lora"]["rank"],
        lora_alpha=config["training"]["lora"]["alpha"],
        target_modules=config["training"]["lora"]["target_modules"],
        lora_dropout=0,        # Unsloth optimized = 0 dropout
        bias="none",
        use_gradient_checkpointing="unsloth",  # 60% less VRAM
    )

    # Training arguments
    training_args = TrainingArguments(
        output_dir=f"./outputs/{config['model']['name']}",
        num_train_epochs=config["training"]["epochs"],
        per_device_train_batch_size=config["training"]["batch_size"],
        gradient_accumulation_steps=config["training"].get("gradient_accumulation_steps", 4),
        learning_rate=config["training"]["learning_rate"],
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        bf16=True,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=50,
        save_strategy="steps",
        save_steps=100,
        report_to="wandb",
    )

    # Load dataset
    train_dataset = load_dataset_from_jsonl(config["training"]["dataset_path"], split="train")
    val_dataset = load_dataset_from_jsonl(config["training"]["dataset_path"], split="val")

    # Train
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        args=training_args,
        max_seq_length=config["training"]["max_seq_length"],
    )
    trainer.train()

    # Save adapter
    model.save_pretrained(f"./outputs/{config['model']['name']}/adapter")
    wandb.finish()
```

#### Axolotl (Multi-GPU DGX — Production Training)

```yaml
# configs/training/axolotl-qwen3.5-30b-moe.yaml
# Axolotl config for MoE model on DGX (multi-GPU)

base_model: Qwen/Qwen3.5-30B-A3B
model_type: AutoModelForCausalLM
tokenizer_type: AutoTokenizer

# CRITICAL: bf16 for MoE, NOT load_in_4bit
load_in_4bit: false
bf16: true

# LoRA configuration
adapter: lora
lora_r: 32
lora_alpha: 64
lora_dropout: 0.0
lora_target_modules:
  - q_proj
  - k_proj
  - v_proj
  - o_proj
  - gate_proj
  - up_proj
  - down_proj
# CRITICAL: Do NOT include router modules (gate) in LoRA targets for MoE
# The router must stay frozen to preserve expert selection behavior
lora_modules_to_save: []

# Dataset
datasets:
  - path: data/train.jsonl
    type: sharegpt               # Chat template format
    conversation: chatml_qwen    # Qwen-specific chat template

# Training
sequence_len: 4096
micro_batch_size: 2
gradient_accumulation_steps: 8
num_epochs: 3
learning_rate: 1.5e-5
lr_scheduler: cosine
warmup_ratio: 0.05
optimizer: adamw_torch_fused

# Multi-GPU (DGX with 8x H100)
# Use FSDP for MoE models (better than DeepSpeed for expert sharding)
fsdp:
  - full_shard
  - auto_wrap
fsdp_config:
  fsdp_transformer_layer_cls_to_wrap: Qwen3MoeDecoderLayer

# Gradient checkpointing (saves VRAM)
gradient_checkpointing: true
gradient_checkpointing_kwargs:
  use_reentrant: false

# Evaluation
val_set_size: 0.1
eval_steps: 50
save_steps: 100
logging_steps: 10

# W&B tracking
wandb_project: rockit-training
wandb_entity: null               # Uses default entity
wandb_run_id: null               # Auto-generated
```

```yaml
# configs/training/axolotl-qwen3.5-14b-dense.yaml
# Axolotl config for dense model — QLoRA 4-bit is safe here

base_model: Qwen/Qwen3.5-14B
model_type: AutoModelForCausalLM
tokenizer_type: AutoTokenizer

# 4-bit QLoRA is fine for dense models
load_in_4bit: true
bnb_4bit_compute_dtype: bfloat16
bnb_4bit_quant_type: nf4
bnb_4bit_use_double_quant: true

adapter: lora
lora_r: 16
lora_alpha: 32
lora_dropout: 0.0
lora_target_modules:
  - q_proj
  - k_proj
  - v_proj
  - o_proj

datasets:
  - path: data/train.jsonl
    type: sharegpt
    conversation: chatml_qwen

sequence_len: 4096
micro_batch_size: 4
gradient_accumulation_steps: 4
num_epochs: 3
learning_rate: 2e-5
lr_scheduler: cosine
warmup_ratio: 0.05
optimizer: adamw_torch_fused

gradient_checkpointing: true

val_set_size: 0.1
eval_steps: 50
save_steps: 100
logging_steps: 10

wandb_project: rockit-training
```

### 4.3 LoRA Config Reference by Model Family

| Model | Architecture | Quantization | LoRA Rank | Alpha | Target Modules | Batch Size |
|-------|-------------|-------------|-----------|-------|----------------|------------|
| Qwen3.5-14B | Dense | 4-bit QLoRA | 16 | 32 | q,k,v,o | 4 |
| Qwen3.5-32B | Dense | 4-bit QLoRA | 32 | 64 | q,k,v,o,gate,up,down | 2 |
| Qwen3.5-30B-A3B | MoE | **bf16** | 32 | 64 | q,k,v,o,gate,up,down | 2 |
| Qwen3.5-235B-A22B | MoE | **bf16** | 64 | 128 | q,k,v,o | 1 |

### 4.4 MoE Training Gotchas

These are critical — violating them produces silent quality degradation:

1. **Never use QLoRA (4-bit) for MoE models.** The router (`gate`) weights control which experts activate. Quantizing them to 4-bit introduces rounding errors that corrupt expert selection. Use bf16 LoRA instead. The active parameter count of MoE models is small enough to fit.

2. **Never fine-tune the router.** Include expert layers (q/k/v/o/gate_proj/up_proj/down_proj within experts) in LoRA targets, but exclude the top-level router/gate layer. The router's job is load balancing — fine-tuning it on a small domain dataset will overfit and collapse expert utilization.

3. **Use fused kernels.** Unsloth provides fused attention + MLP kernels for Qwen MoE. Without them, MoE training is ~3x slower due to expert dispatch overhead.

4. **Monitor expert utilization.** During training, log the entropy of router probabilities. If entropy drops significantly, experts are collapsing (router learned to always pick the same experts). Add an auxiliary load-balancing loss if needed.

5. **FSDP over DeepSpeed for MoE.** FSDP handles expert parameter sharding more naturally than DeepSpeed ZeRO. Use `fsdp_transformer_layer_cls_to_wrap` with the MoE decoder layer class.

### 4.5 Incremental vs Full Retrain

#### Incremental LoRA

```bash
# Continue training from existing adapter with new data
accelerate launch -m axolotl.cli.train configs/training/axolotl-qwen3.5-30b-moe.yaml \
    --resume_from_checkpoint gs://rockit-models/qwen3.5-30b-a3b/v002/adapter \
    --datasets.0.path data/incremental-v003.jsonl
```

**When to use:**
- New trading sessions accumulated (weekly/monthly)
- Minor strategy parameter tweaks
- New annotation data from same format

**Risks:**
- Catastrophic forgetting if new data distribution differs significantly
- Solution: always evaluate on full holdout set, not just new data

#### Full Retrain

```bash
# Train from base model with full dataset
accelerate launch -m axolotl.cli.train configs/training/axolotl-qwen3.5-30b-moe.yaml \
    --datasets.0.path data/train-full-v003.jsonl
```

**When to use:**
- Switching base model (e.g., Qwen3.5-14B → Qwen3.5-30B-A3B)
- New HuggingFace model release to evaluate
- Fundamental changes to annotation format or strategy logic
- Incremental training shows diminishing returns

### 4.6 W&B Integration

```python
# packages/rockit-train/src/rockit_train/tracking.py
import wandb
from dataclasses import asdict

def init_tracking(config: dict, model_card: ModelCard) -> None:
    """Initialize W&B run with full config and model metadata."""
    wandb.init(
        project="rockit-training",
        name=f"{model_card.model_id}",
        config={
            **config,
            "model_card": asdict(model_card),
        },
        tags=[
            model_card.architecture,
            model_card.training_mode,
            model_card.training_tool,
        ],
    )

def log_eval_results(results: BenchmarkResult) -> None:
    """Log evaluation results to W&B."""
    wandb.log({
        "eval/day_type_accuracy": results.day_type_accuracy,
        "eval/bias_accuracy": results.bias_accuracy,
        "eval/confidence_mae": results.confidence_mae,
        "eval/section_completeness": results.section_completeness,
        "eval/key_level_accuracy": results.key_level_accuracy,
        "eval/deterministic_agreement": results.deterministic_agreement,
        "eval/analysis_quality_score": results.analysis_quality_score,
    })

def log_comparison(model_a: str, model_b: str, comparison: dict) -> None:
    """Log model comparison to W&B as a table."""
    table = wandb.Table(
        columns=["Metric", model_a, model_b, "Winner"],
        data=[
            [metric, scores["a"], scores["b"], scores["winner"]]
            for metric, scores in comparison.items()
        ],
    )
    wandb.log({"model_comparison": table})
```

---

## 5. Evaluation Suite

### 5.1 Standard Benchmarks (Sanity Check)

Run via `lm-eval-harness` to verify fine-tuning didn't break general capabilities:

```bash
# Standard benchmark suite (runs ~15 min on single GPU)
lm_eval --model hf \
    --model_args pretrained=Qwen/Qwen3.5-30B-A3B,peft=adapters/v003 \
    --tasks mmlu,hellaswag,arc_challenge,winogrande \
    --batch_size auto \
    --output_path eval_results/standard/

# Compare base model vs fine-tuned
lm_eval --model hf \
    --model_args pretrained=Qwen/Qwen3.5-30B-A3B \
    --tasks mmlu,hellaswag \
    --batch_size auto \
    --output_path eval_results/standard-base/
```

**Gate:** Fine-tuned model must not drop more than 2% on MMLU vs base model. A larger drop indicates catastrophic forgetting.

### 5.2 Domain Evaluation (Rockit-Specific)

#### Holdout Set Construction

```python
# packages/rockit-train/src/rockit_train/eval/holdout.py

# 50-session holdout set: 10 per day type
# These sessions are NEVER used in training
HOLDOUT_SESSIONS = {
    "Trend": [
        "2025-10-15", "2025-11-03", "2025-11-20", "2025-12-04", "2025-12-18",
        "2026-01-08", "2026-01-22", "2026-02-05", "2026-02-19", "2026-03-01",
    ],
    "P-Day": [
        "2025-10-16", "2025-11-04", "2025-11-21", "2025-12-05", "2025-12-19",
        "2026-01-09", "2026-01-23", "2026-02-06", "2026-02-20", "2026-02-28",
    ],
    "B-Day": [
        "2025-10-17", "2025-11-05", "2025-11-22", "2025-12-06", "2025-12-20",
        "2026-01-10", "2026-01-24", "2026-02-07", "2026-02-21", "2026-02-27",
    ],
    "Neutral": [
        "2025-10-18", "2025-11-06", "2025-11-23", "2025-12-07", "2025-12-21",
        "2026-01-11", "2026-01-25", "2026-02-08", "2026-02-22", "2026-02-26",
    ],
    "Rotational": [
        "2025-10-19", "2025-11-07", "2025-11-24", "2025-12-08", "2025-12-22",
        "2026-01-12", "2026-01-26", "2026-02-09", "2026-02-23", "2026-02-25",
    ],
}
```

#### Domain Metrics

```python
# packages/rockit-train/src/rockit_train/eval/domain_metrics.py
from dataclasses import dataclass

@dataclass
class DomainMetrics:
    """Metrics specific to the Rockit trading analysis task."""

    # Classification accuracy
    day_type_accuracy: float       # Exact match on day type (Trend, P-Day, B-Day, etc.)
    day_type_family_accuracy: float  # Correct family (bullish/bearish variant OK)
    bias_accuracy: float           # Correct bias direction (Long/Short/Flat)

    # Calibration
    confidence_mae: float          # Mean absolute error on confidence (0-100 scale)
    confidence_correlation: float  # Correlation between predicted and actual confidence

    # Completeness
    section_completeness: float    # % of 11 mandatory sections present
    section_validity: float        # % of present sections that parse correctly

    # Key level accuracy
    key_level_accuracy: float      # % of key levels within 2 ticks of reference
    key_level_coverage: float      # % of reference key levels mentioned

    # Oracle agreement
    deterministic_agreement: float # % agreement with deterministic engine on signals

def compute_domain_metrics(predictions: list[dict], references: list[dict]) -> DomainMetrics:
    """
    Compare model predictions against reference labels.

    Each prediction and reference is the full analysis output dict with:
    - day_type, bias, confidence, key_levels, lanto_3_model, etc.
    """
    ...
```

#### LLM-as-Judge Scoring

```python
# packages/rockit-train/src/rockit_train/eval/llm_judge.py
import anthropic

JUDGE_PROMPT = """You are evaluating a trading analysis produced by a fine-tuned LLM.
Score the analysis on these dimensions (0-100 each):

1. **Reasoning Quality** — Is the day type reasoning logical and well-supported?
2. **Market Context** — Does it correctly interpret IB, TPO, volume profile, DPOC?
3. **Level Identification** — Are key levels accurate and actionable?
4. **Risk Assessment** — Does it correctly assess ATR regime, confidence?
5. **Actionability** — Would a trader find this useful for decision-making?

Input snapshot:
{input}

Model analysis:
{prediction}

Reference analysis (ground truth):
{reference}

Return JSON: {{"reasoning": <score>, "context": <score>, "levels": <score>,
"risk": <score>, "actionability": <score>, "overall": <avg>, "comments": "<text>"}}
"""

class LLMJudge:
    """Use Opus 4.6 to grade analysis quality."""

    def __init__(self):
        self.client = anthropic.Anthropic()

    def score(self, input_snapshot: dict, prediction: dict, reference: dict) -> dict:
        """Score a single prediction using Opus 4.6 as judge."""
        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": JUDGE_PROMPT.format(
                    input=json.dumps(input_snapshot, indent=2),
                    prediction=json.dumps(prediction, indent=2),
                    reference=json.dumps(reference, indent=2),
                ),
            }],
        )
        return json.loads(response.content[0].text)

    def score_batch(self, examples: list[dict], sample_size: int = 10) -> dict:
        """
        Score a random sample of predictions.
        Returns aggregate scores across dimensions.
        Full holdout is 50 sessions; we judge 10 to save API cost.
        """
        ...
```

### 5.3 A/B Model Comparison

```python
# packages/rockit-train/src/rockit_train/eval/ab_compare.py
from dataclasses import dataclass

@dataclass
class ABResult:
    model_a_id: str
    model_b_id: str
    metrics_a: DomainMetrics
    metrics_b: DomainMetrics
    winner: str                    # "a", "b", or "tie"
    significant: bool              # Statistical significance (p < 0.05)
    recommendation: str            # Human-readable recommendation

def ab_compare(
    model_a_path: str,
    model_b_path: str,
    holdout_path: str,
    base_model: str,
) -> ABResult:
    """
    Run the same holdout set through both models and compare.

    Uses paired bootstrap resampling (n=1000) for statistical significance
    on the primary metric (day_type_accuracy).
    """
    ...
```

### 5.4 Evaluation Gates

A model must pass ALL of these before being promoted to production:

```python
# packages/rockit-train/src/rockit_train/eval/gates.py
from dataclasses import dataclass

@dataclass
class EvaluationGate:
    """Minimum thresholds for production deployment."""
    # Hard thresholds (must pass)
    min_day_type_accuracy: float = 0.80
    min_bias_accuracy: float = 0.75
    max_confidence_mae: float = 15.0
    min_section_completeness: float = 0.90
    min_key_level_accuracy: float = 0.70
    min_analysis_quality_score: float = 60.0

    # Relative thresholds (must beat production)
    must_beat_production: bool = True
    max_regression_pct: float = 0.02      # Allow max 2% regression on any metric

    # Standard benchmark guard
    max_mmlu_drop_pct: float = 0.02       # Max 2% drop vs base model on MMLU

def check_gate(
    result: BenchmarkResult,
    gate: EvaluationGate,
    production_result: BenchmarkResult | None = None,
) -> tuple[bool, list[str]]:
    """
    Check if a model passes all evaluation gates.
    Returns (passed, list_of_failures).
    """
    failures = []

    if result.day_type_accuracy < gate.min_day_type_accuracy:
        failures.append(
            f"day_type_accuracy {result.day_type_accuracy:.3f} < {gate.min_day_type_accuracy}"
        )
    if result.bias_accuracy < gate.min_bias_accuracy:
        failures.append(
            f"bias_accuracy {result.bias_accuracy:.3f} < {gate.min_bias_accuracy}"
        )
    if result.confidence_mae > gate.max_confidence_mae:
        failures.append(
            f"confidence_mae {result.confidence_mae:.1f} > {gate.max_confidence_mae}"
        )
    if result.section_completeness < gate.min_section_completeness:
        failures.append(
            f"section_completeness {result.section_completeness:.3f} < {gate.min_section_completeness}"
        )
    if result.key_level_accuracy < gate.min_key_level_accuracy:
        failures.append(
            f"key_level_accuracy {result.key_level_accuracy:.3f} < {gate.min_key_level_accuracy}"
        )
    if result.analysis_quality_score < gate.min_analysis_quality_score:
        failures.append(
            f"analysis_quality_score {result.analysis_quality_score:.1f} < {gate.min_analysis_quality_score}"
        )

    # Must beat production
    if gate.must_beat_production and production_result:
        for metric in ["day_type_accuracy", "bias_accuracy", "key_level_accuracy"]:
            new_val = getattr(result, metric)
            prod_val = getattr(production_result, metric)
            if new_val < prod_val * (1 - gate.max_regression_pct):
                failures.append(
                    f"{metric} regressed: {new_val:.3f} vs production {prod_val:.3f}"
                )

    return (len(failures) == 0, failures)
```

---

## 6. Quantization & Serving Pipeline

### 6.1 Post-Training Quantization

#### AWQ for vLLM (Production)

```bash
# Quantize merged model (base + adapter) to AWQ
# NOTE: Merge adapter into base first, then quantize
python -c "
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

# Load and merge
base = AutoModelForCausalLM.from_pretrained('Qwen/Qwen3.5-30B-A3B', torch_dtype='auto')
model = PeftModel.from_pretrained(base, 'adapters/v003')
merged = model.merge_and_unload()
merged.save_pretrained('merged-model/')

tokenizer = AutoTokenizer.from_pretrained('Qwen/Qwen3.5-30B-A3B')
tokenizer.save_pretrained('merged-model/')
"

# AWQ quantization
python -c "
from awq import AutoAWQForCausalLM
from transformers import AutoTokenizer

model = AutoAWQForCausalLM.from_pretrained('merged-model/')
tokenizer = AutoTokenizer.from_pretrained('merged-model/')

quant_config = {
    'zero_point': True,
    'q_group_size': 128,
    'w_bit': 4,
    'version': 'marlin',    # Enable Marlin kernels (741 tok/s vs 67 without)
}

model.quantize(tokenizer, quant_config=quant_config)
model.save_quantized('merged-model-awq/')
tokenizer.save_pretrained('merged-model-awq/')
"
```

#### GGUF for Ollama (Local Dev)

```bash
# Convert to GGUF for local Ollama usage
python llama.cpp/convert_hf_to_gguf.py \
    merged-model/ \
    --outfile rockit-qwen3.5-30b-Q4_K_M.gguf \
    --outtype q4_k_m

# Import into Ollama
ollama create rockit:latest -f Modelfile
```

```dockerfile
# Modelfile for Ollama
FROM rockit-qwen3.5-30b-Q4_K_M.gguf
PARAMETER temperature 0.3
PARAMETER num_ctx 4096
SYSTEM """You are ROCKIT, a quantitative trading analysis system..."""
```

### 6.2 Quantization Quality Check

Always verify that quantization didn't degrade domain performance:

```bash
# Run domain eval on full-precision merged model
uv run python -m rockit_train.benchmark \
    --model merged-model/ \
    --holdout gs://rockit-data/holdout/rockit-eval-50.jsonl \
    --output eval_results/merged-fp16/

# Run domain eval on AWQ quantized model
uv run python -m rockit_train.benchmark \
    --model merged-model-awq/ \
    --holdout gs://rockit-data/holdout/rockit-eval-50.jsonl \
    --output eval_results/merged-awq/

# Compare
uv run python -m rockit_train.benchmark \
    --compare eval_results/merged-fp16/ eval_results/merged-awq/ \
    --output eval_results/quant-comparison.json
```

**Gate:** AWQ model must not drop more than 1% on day_type_accuracy vs fp16 merged model.

### 6.3 Multi-LoRA Serving via vLLM

In production, vLLM loads the base model once and swaps adapters per-request:

```python
# packages/rockit-serve/src/rockit_serve/inference/vllm_server.py
from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest

class VLLMMultiLoRAServer:
    """Production inference server with multi-LoRA support."""

    def __init__(self, base_model: str, lora_adapters: dict[str, str]):
        """
        Args:
            base_model: HuggingFace model ID or local path
            lora_adapters: {name: path} mapping of available adapters
        """
        self.llm = LLM(
            model=base_model,
            enable_lora=True,
            max_loras=4,
            max_lora_rank=64,
            tensor_parallel_size=2,  # 2x H100 on DGX
        )
        self.adapters = {
            name: LoRARequest(name, idx + 1, path)
            for idx, (name, path) in enumerate(lora_adapters.items())
        }
        self.sampling_params = SamplingParams(
            temperature=0.3,
            max_tokens=2048,
            top_p=0.9,
        )

    def infer(self, prompt: str, adapter: str = "production") -> str:
        """Run inference with specified adapter."""
        lora_request = self.adapters.get(adapter)
        outputs = self.llm.generate(
            [prompt],
            self.sampling_params,
            lora_request=lora_request,
        )
        return outputs[0].outputs[0].text

    def compare(self, prompt: str, adapter_a: str, adapter_b: str) -> dict:
        """A/B inference: same prompt through two adapters."""
        result_a = self.infer(prompt, adapter_a)
        result_b = self.infer(prompt, adapter_b)
        return {"a": result_a, "b": result_b}
```

### 6.4 Latency Benchmarks

Target latencies for production serving:

| Configuration | Tokens/sec | First Token (ms) | Notes |
|--------------|-----------|------------------|-------|
| AWQ + Marlin (vLLM, 2x H100) | ~741 | ~50 | Production target |
| AWQ (vLLM, 2x H100) | ~320 | ~80 | Without Marlin kernels |
| bf16 (vLLM, 2x H100) | ~180 | ~120 | Full precision, no quant |
| GGUF Q4_K_M (Ollama, Mac Mini M4) | ~45 | ~200 | Local dev only |

**Benchmark command:**
```bash
# Production latency benchmark
python -m vllm.entrypoints.openai.api_server \
    --model merged-model-awq/ \
    --quantization marlin \
    --tensor-parallel-size 2 &

# Run benchmark (100 requests, Rockit-sized prompts)
python benchmark_serving.py \
    --backend openai \
    --base-url http://localhost:8000 \
    --model merged-model-awq \
    --dataset rockit-prompts.jsonl \
    --num-prompts 100 \
    --request-rate 5
```

---

## 7. Automation & Scheduling

### 7.1 APScheduler Setup

See `technical-design/13-automation-infrastructure.md` for full implementation.

Key training-related jobs:

```python
# Post-market: trigger incremental training check
scheduler.add_job(
    check_incremental_training,
    trigger=CronTrigger(day_of_week="fri", hour=18, minute=0, timezone="US/Eastern"),
    id="weekly_training_check",
)

# Post-market: trigger evaluation on production model
scheduler.add_job(
    run_production_eval,
    trigger=CronTrigger(day_of_week="mon-fri", hour=17, minute=0, timezone="US/Eastern"),
    id="daily_production_eval",
)
```

### 7.2 Retraining Triggers

| Trigger | Condition | Action |
|---------|-----------|--------|
| **Scheduled** | Every Friday 6PM ET | Check if new data warrants incremental training |
| **Performance drop** | Production eval drops below gate thresholds | Alert + trigger investigation |
| **A/B conclusion** | A/B test reaches statistical significance | Promote winner, retire loser |
| **New base model** | Manual trigger when new HF model released | Full retrain pipeline |
| **Data quality issue** | Data validation catches anomalies | Alert, pause training |

### 7.3 GitHub Actions CI/CD

```yaml
# .github/workflows/training-pipeline.yaml
name: Training Pipeline

on:
  workflow_dispatch:
    inputs:
      mode:
        description: 'Training mode'
        required: true
        type: choice
        options:
          - incremental
          - full
      base_model:
        description: 'Base model (HuggingFace ID)'
        required: true
        default: 'Qwen/Qwen3.5-30B-A3B'
      config:
        description: 'Axolotl config file'
        required: true
        default: 'configs/training/axolotl-qwen3.5-30b-moe.yaml'
  schedule:
    # Weekly incremental training check (Friday 6PM ET = Saturday 11PM UTC in winter)
    - cron: '0 23 * * 5'

env:
  WANDB_API_KEY: ${{ secrets.WANDB_API_KEY }}
  GCS_BUCKET: rockit-data
  MODEL_REGISTRY: gs://rockit-models

jobs:
  prepare-data:
    runs-on: ubuntu-latest
    outputs:
      dataset_version: ${{ steps.build.outputs.version }}
      should_train: ${{ steps.check.outputs.should_train }}
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv sync --package rockit-train

      - name: Check if training warranted
        id: check
        run: |
          uv run python -m rockit_train.data.check_new_data \
            --bucket $GCS_BUCKET \
            --min-new-sessions 10
          echo "should_train=$?" >> "$GITHUB_OUTPUT"

      - name: Build dataset
        id: build
        if: steps.check.outputs.should_train == '0'
        run: |
          VERSION=$(uv run python -m rockit_train.dataset build \
            --raw-data gs://$GCS_BUCKET/raw/ \
            --output gs://$GCS_BUCKET/training/ \
            --holdout-config configs/eval/holdout-sessions.yaml)
          echo "version=$VERSION" >> "$GITHUB_OUTPUT"

  train:
    needs: prepare-data
    if: needs.prepare-data.outputs.should_train == '0'
    runs-on: [self-hosted, gpu, dgx]
    steps:
      - uses: actions/checkout@v4

      - name: Setup training environment
        run: |
          uv sync --package rockit-train
          pip install unsloth axolotl wandb

      - name: Download dataset
        run: |
          gsutil -m cp -r \
            gs://$GCS_BUCKET/training/${{ needs.prepare-data.outputs.dataset_version }}/ \
            data/

      - name: Train
        run: |
          accelerate launch -m axolotl.cli.train \
            ${{ inputs.config || 'configs/training/axolotl-qwen3.5-30b-moe.yaml' }}

      - name: Upload adapter
        run: |
          ADAPTER_VERSION=$(date +%Y%m%d-%H%M%S)
          gsutil -m cp -r outputs/adapter/ \
            $MODEL_REGISTRY/${{ inputs.base_model }}/$ADAPTER_VERSION/

  evaluate:
    needs: [prepare-data, train]
    runs-on: [self-hosted, gpu]
    steps:
      - uses: actions/checkout@v4

      - name: Run domain evaluation
        run: |
          uv run python -m rockit_train.benchmark \
            --model ${{ inputs.base_model }} \
            --adapter $MODEL_REGISTRY/${{ inputs.base_model }}/latest/ \
            --holdout gs://$GCS_BUCKET/holdout/rockit-eval-50.jsonl \
            --compare production \
            --output eval_results/

      - name: Check evaluation gates
        run: |
          uv run python -m rockit_train.eval.check_gates \
            --results eval_results/benchmark.json \
            --gates configs/eval/gates.yaml

      - name: Run standard benchmarks
        run: |
          lm_eval --model hf \
            --model_args pretrained=${{ inputs.base_model }},peft=outputs/adapter \
            --tasks mmlu,hellaswag \
            --batch_size auto \
            --output_path eval_results/standard/

  promote:
    needs: evaluate
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4

      - name: Promote to production
        run: |
          uv run python -m rockit_train.registry promote \
            --model ${{ inputs.base_model }} \
            --adapter latest \
            --registry $MODEL_REGISTRY

      - name: Update vLLM deployment
        run: |
          # Signal vLLM to reload adapter (graceful hot-swap)
          curl -X POST http://dgx-host:8000/v1/lora/reload \
            -H "Authorization: Bearer ${{ secrets.VLLM_API_KEY }}" \
            -d '{"adapter": "production", "path": "'$MODEL_REGISTRY'/${{ inputs.base_model }}/production/"}'

      - name: Notify
        run: |
          curl -X POST ${{ secrets.SLACK_WEBHOOK }} \
            -H 'Content-Type: application/json' \
            -d '{"text": "New model promoted to production: ${{ inputs.base_model }} adapter ${{ needs.train.outputs.version }}"}'
```

### 7.4 Auto-Rollback Monitor

```python
# packages/rockit-serve/src/rockit_serve/monitoring/rollback.py
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class RollbackConfig:
    """Configuration for automatic rollback monitoring."""
    check_interval_minutes: int = 30
    min_inferences_for_check: int = 20    # Need enough data points
    max_error_rate: float = 0.10          # 10% error rate triggers rollback
    max_latency_p99_ms: float = 5000      # 5s P99 latency triggers rollback
    min_confidence_avg: float = 40.0      # Average confidence below 40 is suspicious
    lookback_hours: int = 4               # Check last 4 hours of data

class RollbackMonitor:
    """Monitor production model and auto-rollback on degradation."""

    def __init__(self, config: RollbackConfig, registry_client, metrics_client):
        self.config = config
        self.registry = registry_client
        self.metrics = metrics_client

    def check(self) -> dict:
        """
        Check production model health.
        Returns {"healthy": bool, "issues": [...], "action": "none"|"alert"|"rollback"}
        """
        recent_metrics = self.metrics.query(
            window=timedelta(hours=self.config.lookback_hours)
        )

        if len(recent_metrics) < self.config.min_inferences_for_check:
            return {"healthy": True, "issues": [], "action": "none",
                    "reason": "insufficient data"}

        issues = []
        error_rate = recent_metrics.error_count / len(recent_metrics)
        if error_rate > self.config.max_error_rate:
            issues.append(f"Error rate {error_rate:.1%} > {self.config.max_error_rate:.1%}")

        p99_latency = recent_metrics.latency_p99_ms
        if p99_latency > self.config.max_latency_p99_ms:
            issues.append(f"P99 latency {p99_latency:.0f}ms > {self.config.max_latency_p99_ms:.0f}ms")

        avg_confidence = recent_metrics.confidence_avg
        if avg_confidence < self.config.min_confidence_avg:
            issues.append(f"Avg confidence {avg_confidence:.1f} < {self.config.min_confidence_avg}")

        if issues:
            return {
                "healthy": False,
                "issues": issues,
                "action": "rollback" if len(issues) >= 2 else "alert",
            }

        return {"healthy": True, "issues": [], "action": "none"}

    def rollback(self) -> str:
        """
        Rollback to previous production adapter version.
        Returns the version rolled back to.
        """
        previous = self.registry.get_previous_production()
        self.registry.promote(previous.model_id)
        return previous.model_id
```

---

## 8. Practical Setup Guide

### 8.1 DGX Setup (Production Training + Serving)

```bash
# 1. System prerequisites (CUDA 12.4+, Python 3.11)
# Assumes DGX with 8x H100 80GB, CUDA already installed

# 2. Clone repo and setup
git clone https://github.com/<org>/RockitFactory.git
cd RockitFactory
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --package rockit-train

# 3. Install training tools
pip install unsloth              # Single-GPU fast training
pip install axolotl              # Multi-GPU training
pip install wandb                # Experiment tracking
pip install lm-eval              # Standard benchmarks
pip install autoawq              # AWQ quantization
pip install vllm                 # Production serving

# 4. Authenticate
wandb login                      # Paste API key from wandb.ai/authorize
gcloud auth login                # For GCS access
gcloud auth application-default login

# 5. Verify GPU setup
python -c "import torch; print(f'GPUs: {torch.cuda.device_count()}, CUDA: {torch.version.cuda}')"
# Expected: GPUs: 8, CUDA: 12.4

# 6. Download base model (one-time, cached)
python -c "
from transformers import AutoModelForCausalLM, AutoTokenizer
AutoModelForCausalLM.from_pretrained('Qwen/Qwen3.5-30B-A3B', torch_dtype='auto')
AutoTokenizer.from_pretrained('Qwen/Qwen3.5-30B-A3B')
"
```

### 8.2 Local Dev Setup (Mac Mini / Workstation)

```bash
# 1. Install tools
brew install ollama              # Local LLM inference
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and setup
git clone https://github.com/<org>/RockitFactory.git
cd RockitFactory
uv sync

# 3. Install dev tools
uv pip install ruff pytest wandb

# 4. Pull a GGUF model for local inference
ollama pull qwen3.5:30b-a3b-q4_K_M

# 5. (Optional) If you have a GPU for local training experiments
pip install unsloth
```

### 8.3 First Training Run Walkthrough

```bash
# Step 1: Prepare dataset
uv run python -m rockit_train.dataset build \
    --raw-data data/raw/ \
    --output data/training/v001/ \
    --holdout-config configs/eval/holdout-sessions.yaml

# Step 2: Verify dataset
uv run python -m rockit_train.dataset validate \
    --path data/training/v001/
# Expected output:
#   train.jsonl: 6,750 examples
#   val.jsonl: 375 examples
#   test.jsonl: 375 examples
#   Holdout excluded: 50 sessions
#   Schema validation: PASS

# Step 3: Train (single GPU with Unsloth for first experiment)
uv run python -m rockit_train.train \
    --config configs/training/unsloth-qwen3.5-30b-moe.yaml \
    --dataset data/training/v001/train.jsonl \
    --val-dataset data/training/v001/val.jsonl
# W&B dashboard will show loss curves in real-time

# Step 4: Evaluate
uv run python -m rockit_train.benchmark \
    --model Qwen/Qwen3.5-30B-A3B \
    --adapter outputs/qwen3.5-30b-a3b/adapter/ \
    --holdout data/holdout/rockit-eval-50.jsonl
# Output:
#   day_type_accuracy: 0.84
#   bias_accuracy: 0.79
#   confidence_mae: 11.2
#   ...
#   GATE: PASSED (all metrics above threshold)
```

### 8.4 First Model Comparison Walkthrough

```bash
# Scenario: New Qwen3.5-32B (dense) released, want to compare vs current 30B-A3B (MoE)

# Step 1: Train on new model
uv run python -m rockit_train.train \
    --config configs/training/axolotl-qwen3.5-32b-dense.yaml \
    --dataset data/training/v001/train.jsonl

# Step 2: Benchmark new model
uv run python -m rockit_train.benchmark \
    --model Qwen/Qwen3.5-32B \
    --adapter outputs/qwen3.5-32b/adapter/ \
    --holdout data/holdout/rockit-eval-50.jsonl \
    --output eval_results/qwen3.5-32b/

# Step 3: Compare against production
uv run python -m rockit_train.benchmark \
    --compare eval_results/qwen3.5-32b/ eval_results/production/ \
    --output eval_results/32b-vs-30b-comparison.json

# Output:
#   === Model Comparison ===
#   Metric                 Qwen3.5-32B   Qwen3.5-30B-A3B   Winner
#   day_type_accuracy      0.86          0.84               32B (+2.4%)
#   bias_accuracy          0.81          0.79               32B (+2.5%)
#   confidence_mae         10.8          11.2               32B (-3.6%)
#   latency (tok/s)        280           741                30B-A3B (MoE)
#
#   Recommendation: Qwen3.5-32B wins on accuracy but 2.6x slower.
#   Consider if latency tradeoff is acceptable.

# Step 4: Run leaderboard
uv run python -m rockit_train.leaderboard \
    --models-dir gs://rockit-models/ \
    --holdout data/holdout/rockit-eval-50.jsonl \
    --output leaderboard.json
```

---

## 9. Configuration Reference

### 9.1 Evaluation Gates Config

```yaml
# configs/eval/gates.yaml
gates:
  # Hard thresholds
  min_day_type_accuracy: 0.80
  min_bias_accuracy: 0.75
  max_confidence_mae: 15.0
  min_section_completeness: 0.90
  min_key_level_accuracy: 0.70
  min_analysis_quality_score: 60.0

  # Relative thresholds
  must_beat_production: true
  max_regression_pct: 0.02

  # Standard benchmark guard
  max_mmlu_drop_pct: 0.02

holdout:
  path: gs://rockit-data/holdout/rockit-eval-50.jsonl
  sessions_per_day_type: 10
  day_types:
    - Trend
    - P-Day
    - B-Day
    - Neutral
    - Rotational

llm_judge:
  model: claude-opus-4-6
  sample_size: 10              # Judge 10 out of 50 holdout sessions
  max_cost_per_run: 5.00       # USD budget cap
```

### 9.2 Model Registry Config

```yaml
# configs/registry.yaml
registry:
  backend: gcs                  # "gcs" or "local"
  gcs_bucket: rockit-models
  local_path: ./models/         # For local dev

  # Model families to track
  families:
    - name: qwen3.5-30b-a3b
      base_model: Qwen/Qwen3.5-30B-A3B
      architecture: moe
      active_params_b: 3.0
    - name: qwen3.5-14b
      base_model: Qwen/Qwen3.5-14B
      architecture: dense
      active_params_b: 14.0
    - name: qwen3.5-32b
      base_model: Qwen/Qwen3.5-32B
      architecture: dense
      active_params_b: 32.0

serving:
  engine: vllm                  # "vllm" or "sglang"
  tensor_parallel_size: 2
  max_loras: 4
  max_lora_rank: 64
```

---

## 10. SGLang as vLLM Alternative

SGLang is evaluated as an alternative to vLLM for production serving:

| Feature | vLLM | SGLang |
|---------|------|--------|
| Throughput (H100) | 741 tok/s (AWQ+Marlin) | ~955 tok/s (RadixAttention) |
| Multi-LoRA | Native support | Supported (v0.4+) |
| Multi-turn caching | Limited | RadixAttention (prefix caching across requests) |
| Ecosystem | Mature, widely deployed | Newer, faster iteration |
| Quantization | AWQ, GPTQ, FP8 | AWQ, GPTQ, FP8, INT4 |

**RadixAttention advantage:** For agent conversations (Advocate/Skeptic debate with shared context), SGLang's RadixAttention caches the shared system prompt + market snapshot prefix, only computing the divergent agent responses. This gives ~29% speedup on multi-turn workloads.

**Recommendation:** Start with vLLM (mature, well-tested). Benchmark SGLang in Phase 2 when agent system is implemented and multi-turn latency matters.

```bash
# SGLang serving (for benchmarking)
python -m sglang.launch_server \
    --model-path Qwen/Qwen3.5-30B-A3B \
    --tp 2 \
    --enable-lora \
    --lora-paths production=adapters/v003
```

---

## 11. File Map

Files created or referenced by this design:

```
packages/rockit-train/
├── src/rockit_train/
│   ├── __init__.py
│   ├── __main__.py              # CLI entry point
│   ├── registry.py              # ModelCard, ModelLeaderboard
│   ├── benchmark.py             # ModelBenchmark runner
│   ├── dataset.py               # DatasetBuilder
│   ├── train_unsloth.py         # Unsloth single-GPU training
│   ├── tracking.py              # W&B integration helpers
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── domain_metrics.py    # DomainMetrics, compute_domain_metrics
│   │   ├── llm_judge.py         # LLMJudge (Opus 4.6)
│   │   ├── ab_compare.py        # A/B model comparison
│   │   ├── gates.py             # EvaluationGate, check_gate
│   │   └── holdout.py           # HOLDOUT_SESSIONS constant
│   └── quantize/
│       ├── __init__.py
│       ├── awq.py               # AWQ quantization pipeline
│       └── gguf.py              # GGUF conversion for Ollama
├── tests/
│   ├── test_registry.py
│   ├── test_benchmark.py
│   ├── test_dataset.py
│   └── test_eval_gates.py
configs/
├── training/
│   ├── axolotl-qwen3.5-30b-moe.yaml
│   ├── axolotl-qwen3.5-14b-dense.yaml
│   ├── axolotl-qwen3.5-32b-dense.yaml
│   └── unsloth-qwen3.5-30b-moe.yaml
├── eval/
│   ├── gates.yaml
│   └── holdout-sessions.yaml
└── registry.yaml
.github/workflows/
└── training-pipeline.yaml
```
