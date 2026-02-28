# Pipeline & MLOps Design

> **Revision 2** — Updated with actual training pipeline details from rockit-framework inspection.
> Key addition: addresses the hard problem of continuously updating LLMs with new strategies,
> incremental vs full retraining, and multi-model support (Qwen 30B, 70B, etc).

## Pipeline Overview

```
Phase 1: Research         Phase 2: Training           Phase 3: Serving
─────────────────         ──────────────────           ────────────────
Strategy Code             Dataset Generation           API Deployment
    │                         │                            │
    ▼                         ▼                            ▼
Backtest (259+ sessions)  JSONL {input, output} pairs  Model Loading
    │                         │                            │
    ▼                         ▼                            ▼
Evaluation Reports        LoRA or Full Fine-Tuning     Deterministic + LLM
    │                     (Qwen 30B / 70B / etc)       Inference
    ▼                         │                            │
Deterministic Snapshots       ▼                            ▼
(orchestrator + 38 modules)  Model Registry              Signals API
    │                         │                      (annotations + setups)
    ▼                         ▼                            │
Merge to main ──────────▶ Auto-triggered ──────────▶  Auto-deployed
```

---

## Phase 1: Research Pipeline (CI-Triggered)

**Trigger:** Push to `main` or PR with changes in `packages/rockit-core/`

```yaml
# infra/cloudbuild/ci.yaml (simplified)
steps:
  - name: 'lint-and-test'
    script: |
      uv run ruff check packages/
      uv run pytest packages/rockit-core/tests/

  - name: 'backtest-regression'
    script: |
      uv run python -m rockit_core.engine.backtest \
        --config configs/strategies.yaml \
        --sessions 259 \
        --output gs://$BUCKET/backtests/$COMMIT_SHA/

  - name: 'evaluate'
    script: |
      uv run python -m rockit_core.reporting.comparison \
        --input gs://$BUCKET/backtests/$COMMIT_SHA/ \
        --compare gs://$BUCKET/backtests/baseline/

  - name: 'generate-deterministic'
    script: |
      uv run python -m rockit_core.deterministic.orchestrator \
        --config configs/strategies.yaml \
        --output gs://$BUCKET/deterministic/$COMMIT_SHA/
```

**Outputs:**
- Backtest results stored in GCS with commit SHA tagging
- Evaluation reports comparing against baseline (WR, PF, Sharpe, MDD)
- Deterministic snapshots ready for training data generation

**Gate:** If backtest metrics regress beyond threshold, pipeline fails and PR cannot merge.

---

## Training Data Format (Preserved from Current System)

The existing JSONL format with `{input, output}` pairs is kept. This is what the 252+ days of data already use.

**Input** (deterministic snapshot from orchestrator — 38 modules merged):
```json
{
  "session_date": "2025-01-02",
  "current_et_time": "11:45",
  "premarket": {
    "asia_high": 22310.75, "asia_low": 22033.75,
    "london_high": 22336.5, "london_low": 22230.0,
    "overnight_high": 22402.5, "overnight_low": 22247.0,
    "compression_flag": false, "smt_preopen": "neutral"
  },
  "intraday": {
    "ib": { "ib_high": 22275.0, "ib_low": 22257.25, "ib_range": 17.75,
            "current_close": 22259.75, "current_vwap": 22272.07,
            "ema20": 22316.08, "rsi14": 29.68, "atr14": 25.82 },
    "volume_profile": { "current_session": { "poc": 22723.0, "vah": 22750.0, "val": 22700.0 },
                        "previous_day": {...}, "previous_3_days": {...} },
    "tpo_profile": { "current_poc": 22721.25, "tpo_shape": "p_shape",
                     "single_prints_above_vah": 28, "fattening_zone": "at_val" },
    "dpoc_migration": { "migration_direction": "down", "steps_since_1030": 137.75 },
    "wick_parade": { "bullish_wick_parade_count": 4, "bearish_wick_parade_count": 6 },
    "fvg_detection": { "daily_fvg": [], "4h_fvg": [], "1h_fvg": [...], "90min_fvg": [...] },
    "ninety_min_pd_arrays": { "equilibrium_50": 22732.88, "bias_potential": "bullish" },
    "globex_va_analysis": {...},
    "twenty_percent_rule": {...},
    "va_edge_fade": {...}
  },
  "core_confluences": {
    "ib_acceptance": {...}, "dpoc_vs_ib": {...},
    "price_location": {...}, "tpo_signals": {...}
  },
  "inference": {
    "day_type": "Neutral Range", "bias": "Flat",
    "confidence": 50, "trend_strength": "Weak"
  },
  "cri_readiness": {
    "overall_status": "STAND_DOWN",
    "terrain": {"classification": "A2"},
    "identity": {"permitted": "Squire"},
    "permission": {"aggression": "No entry"}
  },
  "playbook_setup": { "matched_playbook": "Standby" },
  "balance_classification": {...},
  "mean_reversion": {...},
  "or_reversal": {...},
  "edge_fade": {...}
}
```

**Output** (LLM analysis following ROCKIT v5.6 rules — 11 mandatory sections):
```json
{
  "day_type": "P-Day (Bullish)",
  "lanto_3_model": { "drawn_bias": 1, "price_action": 1, "entry_model": 0, "score": "2/3" },
  "bias": "Long",
  "key_levels": { "ibh": 21850, "ibl": 21780, "vah": 21845, "val": 21790, "dpoc": 21820 },
  "liquidity_sweeps": { "asia_high": "Tested", "london_low": "Swept" },
  "atr_regime": "Normal",
  "value_acceptance": { "poc_location": "upper_third" },
  "tpo_read": { "profile_signals": [...], "dpoc_migration": "...", "compression": false },
  "confidence": 72,
  "day_type_reasoning": ["IB accepted above prior VAH...", "DPOC migrating up..."],
  "one_liner": "Bullish P-Day developing with DPOC migration..."
}
```

**Existing data volumes:**
- `local-analysis/` — 58 JSONL files (252 trading days, ~30 snapshots/day = ~7,500 examples)
- `local-analysis-format/` — 4 JSONL files (newer format, 2026 dates)
- `xai-analysis/` — 43 JSONL files (Oct-Dec 2025, enhanced analysis from xAI Grok)
- Three annotation sources today: local fine-tuned model, GLM-4.7-Flash, xAI Grok
- Total: ~105 JSONL files across 3 format variants

---

## Phase 2: Training Pipeline — The Hard Problem

This is the most critical and complex piece. The challenge:

1. **Strategy changes need to propagate to LLM** — When you tweak a strategy or add a new one, the LLM needs to learn the updated behavior
2. **Incremental vs full retrain** — Sometimes you just need to update with new data, sometimes you need to start fresh
3. **Model flexibility** — Want to experiment with Qwen 30B, 70B, or other models
4. **Multiple annotation sources** — Local model, GLM, xAI Grok produce different quality labels

### Training Strategy Matrix

| Scenario | Strategy | When to Use |
|----------|----------|-------------|
| New trading data (more sessions) | **Incremental LoRA** | Weekly/monthly as new sessions accumulate |
| New/modified strategy | **Regenerate + Incremental** | After strategy code changes merge to main |
| New base model (Qwen 30B → 70B) | **Full retrain** | When switching model architecture |
| Label quality improvement | **Full retrain** | When annotation approach changes fundamentally |
| Hyperparameter tuning | **Experiment run** | Ad-hoc, tracked in MLflow |

### Training Pipeline (Vertex AI + DGX Hybrid)

```python
# packages/rockit-train/src/rockit_train/pipeline.py
from dataclasses import dataclass
from enum import Enum

class TrainMode(Enum):
    INCREMENTAL = "incremental"   # LoRA on new data only
    FULL = "full"                  # Full retrain from scratch

@dataclass
class TrainConfig:
    mode: TrainMode
    base_model: str               # "qwen-2.5-30b", "qwen-2.5-70b", etc.
    dataset_path: str             # GCS path to training JSONL
    prior_adapter: str | None     # For incremental: path to previous LoRA adapter
    lora_rank: int = 16
    lora_alpha: int = 32
    learning_rate: float = 2e-5
    epochs: int = 3
    batch_size: int = 4
    max_seq_length: int = 4096
    gradient_accumulation_steps: int = 4

def build_training_pipeline(config: TrainConfig):
    """
    Pipeline steps:
    1. Validate dataset (schema, completeness, no data leakage)
    2. Split train/val/test (80/10/10, temporal split — no future data)
    3. Train (LoRA or full, depending on mode)
    4. Evaluate against held-out test set
    5. Compare against current production model
    6. Register if better, reject if worse
    """
    pass
```

### Incremental Training Flow

When new sessions accumulate or a strategy is tweaked:

```
Strategy code change merges to main
    │
    ▼
CI generates deterministic snapshots (orchestrator + 38 modules)
    │
    ▼
New JSONL training data generated
(new snapshots as input, existing LLM labels OR re-annotated)
    │
    ▼
Incremental LoRA training
├── Load previous production LoRA adapter
├── Train on NEW data only (delta from last training)
├── Evaluate on full held-out test set
└── If better → register as new version
    If worse  → reject, alert for investigation
```

### Full Retrain Flow

When switching base models or fundamentally changing approach:

```
Choose new base model (e.g., Qwen 2.5 70B)
    │
    ▼
Regenerate ALL deterministic snapshots
(259+ sessions × 30 snapshots through current orchestrator)
    │
    ▼
Re-annotate ALL training data
├── Option A: Use current best model to re-label (self-distillation)
├── Option B: Use external models (GLM, Grok) for labeling
└── Option C: Use synthetic labels from deterministic engine
    │
    ▼
Full LoRA fine-tuning from base model
├── Full dataset (all sessions, all time slices)
├── Hyperparameter sweep (learning rate, rank, alpha)
├── Track all experiments in MLflow
└── Best model → register → deploy
```

### Multi-Model Support

```yaml
# configs/training/qwen-30b.yaml
model:
  name: "qwen-2.5-30b"
  source: "huggingface"
  quantization: "4bit"   # For DGX memory constraints
training:
  mode: incremental
  lora:
    rank: 16
    alpha: 32
    target_modules: ["q_proj", "v_proj", "k_proj", "o_proj"]
  learning_rate: 2e-5
  epochs: 3
  batch_size: 4
  max_seq_length: 4096
evaluation:
  metrics: ["day_type_accuracy", "bias_accuracy", "confidence_mae", "setup_quality"]
  min_day_type_accuracy: 0.80
  min_bias_accuracy: 0.75

---
# configs/training/qwen-70b.yaml
model:
  name: "qwen-2.5-70b"
  source: "huggingface"
  quantization: "4bit"
training:
  mode: full
  lora:
    rank: 32            # Higher rank for larger model
    alpha: 64
    target_modules: ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj"]
  learning_rate: 1e-5   # Lower LR for larger model
  epochs: 2
  batch_size: 2         # Smaller batch for memory
  max_seq_length: 4096
  gradient_checkpointing: true
evaluation:
  metrics: ["day_type_accuracy", "bias_accuracy", "confidence_mae", "setup_quality"]
  min_day_type_accuracy: 0.85
  min_bias_accuracy: 0.80
```

### Model Registry

```
gs://rockit-models/
├── registry.json                  # Version manifest
├── qwen-30b/
│   ├── v001/
│   │   ├── adapter_model.safetensors
│   │   ├── adapter_config.json
│   │   ├── metrics.json           # { day_type_acc: 0.82, bias_acc: 0.78 }
│   │   ├── training_config.yaml   # Exact config used
│   │   ├── data_version.json      # { commit_sha, num_sessions, date_range }
│   │   └── metadata.json          # { git_sha, timestamp, mode: "incremental" }
│   ├── v002/
│   │   └── ...
│   └── production -> v002/
├── qwen-70b/
│   ├── v001/
│   │   └── ...
│   └── production -> v001/
└── experiments/                   # Non-production experiment runs
    └── {mlflow_run_id}/
```

### Evaluation Gates

A model must pass these gates before deployment:

```python
# packages/rockit-train/src/rockit_train/evaluator.py
@dataclass
class EvaluationGate:
    """Model must beat these thresholds AND the current production model."""
    min_day_type_accuracy: float = 0.80   # Correct day type classification
    min_bias_accuracy: float = 0.75        # Correct bias direction
    max_confidence_mae: float = 15.0       # Mean absolute error on confidence score
    min_setup_quality: float = 0.70        # Trade setups that match deterministic signals
    must_beat_production: bool = True       # Must outperform current prod model

def evaluate_model(model_path: str, test_data: str, gate: EvaluationGate) -> bool:
    """
    Run model on held-out test set.
    Compare predictions vs ground truth (deterministic signals as reference).
    Return True if model passes all gates.
    """
    pass
```

---

## Phase 3: Serving Pipeline (Auto-Deploy)

**Trigger:** New model registered and passes evaluation gates

```yaml
# infra/cloudbuild/deploy.yaml
steps:
  - name: 'build-serve-image'
    script: |
      docker build -t us-docker.pkg.dev/rockit/serve:$MODEL_VERSION \
        -f packages/rockit-serve/Dockerfile .

  - name: 'deploy-staging'
    script: |
      gcloud run deploy rockit-api-staging \
        --image us-docker.pkg.dev/rockit/serve:$MODEL_VERSION \
        --set-env-vars MODEL_VERSION=$MODEL_VERSION,MODEL_BASE=$MODEL_BASE \
        --tag staging

  - name: 'integration-test'
    script: |
      uv run pytest packages/rockit-serve/tests/integration/ \
        --api-url https://staging---rockit-api.run.app

  - name: 'deploy-production'
    script: |
      gcloud run services update-traffic rockit-api \
        --to-tags staging=100
```

### A/B Model Serving

For comparing models (e.g., Qwen 30B vs 70B) in production:

```python
# packages/rockit-serve/src/rockit_serve/inference/llm.py
class MultiModelInference:
    """Serve multiple models, route by config or A/B test."""

    def __init__(self):
        self.models = {}  # model_name -> loaded model

    async def infer(self, snapshot: dict, model: str = "production") -> dict:
        """
        Run inference with specified model.
        For A/B testing, caller specifies which model.
        """
        pass

    async def compare(self, snapshot: dict) -> dict:
        """
        Run same snapshot through all loaded models.
        Return side-by-side comparison for evaluation.
        """
        results = {}
        for name, model in self.models.items():
            results[name] = await self._run(model, snapshot)
        return results
```

---

## Experiment Tracking

Use **MLflow** to track all training runs:

```python
# packages/rockit-train/src/rockit_train/trainer.py
import mlflow

def train(config: TrainConfig):
    with mlflow.start_run(run_name=f"{config.base_model}-{config.mode.value}"):
        mlflow.log_params({
            "base_model": config.base_model,
            "mode": config.mode.value,
            "lora_rank": config.lora_rank,
            "learning_rate": config.learning_rate,
            "epochs": config.epochs,
            "dataset": config.dataset_path,
            "prior_adapter": config.prior_adapter,
            "git_sha": get_git_sha(),
        })

        model = run_training(config)
        metrics = evaluate(model, config)

        mlflow.log_metrics(metrics)
        mlflow.log_artifact(config.dataset_path)

        if metrics["passes_gate"]:
            register_model(model, config, metrics)
```

---

## CI/CD Summary

| Event | Trigger | Pipeline | Output |
|-------|---------|----------|--------|
| PR opened | Code change in rockit-core | Lint + Test + Backtest regression | Pass/Fail gate |
| Merge to main | PR merge | Full backtest + Deterministic snapshot gen | Snapshots in GCS |
| New snapshots in GCS | Cloud event | Generate training JSONL | Training data in GCS |
| Training triggered | Manual or auto | LoRA/Full train + Evaluate + Register | New model version |
| New model registered | Registry event | Build + Stage + Test + Deploy | Live API |
| Config change | `configs/` change | Re-run backtest with new params | Updated results |

---

## Local Development

```bash
# Run backtest for all strategies (259 sessions)
make backtest STRATEGY=all

# Run backtest for a single strategy
make backtest STRATEGY=trend_bull

# Generate deterministic snapshots locally
make deterministic

# Generate training JSONL from snapshots
make training-data

# Train locally (requires GPU)
make train CONFIG=configs/training/qwen-30b.yaml MODE=incremental

# Full retrain with new base model
make train CONFIG=configs/training/qwen-70b.yaml MODE=full

# Run API locally (deterministic only, no LLM)
make serve

# Run API locally with LLM inference
make serve-with-llm MODEL=qwen-30b

# Compare two models on same data
make compare MODEL_A=qwen-30b/v002 MODEL_B=qwen-70b/v001
```
