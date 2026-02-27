# Pipeline & MLOps Design

## Pipeline Overview

The Rockit pipeline has three distinct phases, each automated end-to-end:

```
Phase 1: Research         Phase 2: Training        Phase 3: Serving
─────────────────         ──────────────────        ────────────────
Strategy Code             Dataset Generation        API Deployment
    │                         │                         │
    ▼                         ▼                         ▼
Backtest (259 sessions)   Annotation & Labels       Model Loading
    │                         │                         │
    ▼                         ▼                         ▼
Evaluation Reports        LoRA Fine-Tuning          Deterministic + LLM
    │                         │                     Inference
    ▼                         ▼                         │
Deterministic Data Gen    Model Registry                ▼
    │                         │                     Signal API
    ▼                         ▼                         │
Merge to main ────────▶  Auto-triggered ───────▶   Auto-deployed
```

---

## Phase 1: Research Pipeline (CI-Triggered)

**Trigger:** Push to `main` or PR with changes in `packages/rockit-core/` or `packages/rockit-pipeline/`

```yaml
# infra/cloudbuild/ci.yaml (simplified)
steps:
  - name: 'lint-and-test'
    script: |
      uv run ruff check packages/
      uv run pytest packages/rockit-core/tests/
      uv run pytest packages/rockit-pipeline/tests/

  - name: 'backtest-regression'
    script: |
      uv run python -m rockit_pipeline.backtest.engine \
        --config configs/strategies.yaml \
        --sessions 259 \
        --output gs://$BUCKET/backtests/$COMMIT_SHA/

  - name: 'evaluate'
    script: |
      uv run python -m rockit_pipeline.evaluation.report \
        --input gs://$BUCKET/backtests/$COMMIT_SHA/ \
        --output gs://$BUCKET/evaluations/$COMMIT_SHA/ \
        --compare gs://$BUCKET/evaluations/baseline/

  - name: 'generate-deterministic'
    script: |
      uv run python -m rockit_pipeline.deterministic.generator \
        --config configs/strategies.yaml \
        --output gs://$BUCKET/deterministic/$COMMIT_SHA/
```

**Outputs:**
- Backtest results stored in GCS with commit SHA tagging
- Evaluation reports comparing against baseline
- Deterministic data ready for training

**Gate:** If backtest metrics regress beyond threshold, pipeline fails and PR cannot merge.

---

## Current Training Data Format (Preserved)

The existing training data format is JSONL with `{input, output}` pairs. This format is preserved in the new pipeline.

**Input** (deterministic snapshot from `orchestrator.py`):
```json
{
  "session_date": "2026-01-02",
  "current_et_time": "11:45",
  "premarket": { "asia": {...}, "london": {...}, "overnight": {...} },
  "intraday": {
    "ib": { "high": 21850, "low": 21780, "range": 70, "mid": 21815, ... },
    "volume_profile": { "poc": 21820, "vah": 21845, "val": 21790, ... },
    "tpo_profile": { "letters": [...], "single_prints": [...], "shape": "p-shape" },
    "dpoc_migration": { "direction": "up", "magnitude": 15, ... },
    "wick_parade": { "bullish": 8, "bearish": 3 },
    "fvg_detection": { "daily": [...], "15min": [...], ... },
    "ninety_min_pd_arrays": { ... }
  },
  "core_confluences": {
    "ib_acceptance": {...}, "dpoc_vs_ib": {...},
    "dpoc_compression": {...}, "price_location": {...},
    "tpo_signals": {...}, "migration": {...}
  }
}
```

**Output** (LLM analysis following ROCKIT v5.6 rules — 11 mandatory sections):
```json
{
  "day_type": "P-Day (Bullish)",
  "lanto_3_model": { "drawn_bias": 1, "price_action": 1, "entry_model": 0, "score": "2/3" },
  "bias": "Long",
  "key_levels": { "ibh": 21850, "ibl": 21780, "vah": 21845, "val": 21790, "dpoc": 21820 },
  "liquidity_sweeps": { "asia_high": "Tested", "london_low": "Swept", ... },
  "atr_regime": "Normal",
  "value_acceptance": { "poc_location": "upper_third", ... },
  "tpo_read": { "profile_signals": [...], "dpoc_migration": "...", "compression": false },
  "confidence": 72,
  "day_type_reasoning": ["IB accepted above prior VAH...", "DPOC migrating up..."],
  "one_liner": "Bullish P-Day developing with DPOC migration..."
}
```

**Data volumes:**
- `back-test.py` generates ~252 days × 30 time slices = ~7,500 training examples
- Three annotation sources: local fine-tuned model, GLM-4.7-Flash, xAI Grok
- Stored in RockitDataFeed: `local-analysis/`, `local-analysis-format/`, `xai-analysis/`

---

## Phase 2: Training Pipeline (MLOps)

**Trigger:** New deterministic data lands in GCS (after Phase 1 completes on `main`)

### Option A: Vertex AI Pipelines (Recommended for GCP)

```python
# packages/rockit-train/src/rockit_train/vertex_pipeline.py
from kfp import dsl
from kfp.dsl import component

@component(base_image="us-docker.pkg.dev/rockit/train:latest")
def generate_training_data(
    deterministic_path: str,
    output_path: str,
):
    """Convert deterministic data into training format."""
    from rockit_train.dataset import build_dataset
    build_dataset(deterministic_path, output_path)

@component(base_image="us-docker.pkg.dev/rockit/train:latest")
def train_lora(
    dataset_path: str,
    config_path: str,
    model_output: str,
):
    """Run LoRA fine-tuning."""
    from rockit_train.trainer import train
    train(dataset_path, config_path, model_output)

@component(base_image="us-docker.pkg.dev/rockit/train:latest")
def evaluate_model(
    model_path: str,
    test_data: str,
    metrics_output: str,
):
    """Evaluate trained model against benchmarks."""
    from rockit_train.evaluator import evaluate
    evaluate(model_path, test_data, metrics_output)

@dsl.pipeline(name="rockit-training-pipeline")
def training_pipeline(
    deterministic_path: str,
    config_path: str,
):
    data_task = generate_training_data(
        deterministic_path=deterministic_path,
        output_path="gs://rockit-data/training/latest/",
    )
    train_task = train_lora(
        dataset_path=data_task.outputs["output_path"],
        config_path=config_path,
        model_output="gs://rockit-models/latest/",
    )
    eval_task = evaluate_model(
        model_path=train_task.outputs["model_output"],
        test_data="gs://rockit-data/test/",
        metrics_output="gs://rockit-metrics/latest/",
    )
```

### Option B: Self-Hosted on Spark DGX (Current Hardware)

If staying on the DGX hardware, use a lightweight orchestrator:

```yaml
# configs/training/pipeline.yaml
pipeline:
  trigger:
    type: gcs_event
    bucket: rockit-data
    prefix: deterministic/

  steps:
    - name: generate-dataset
      command: python -m rockit_train.dataset
      args:
        input: "{{ trigger.path }}"
        output: /data/training/{{ run_id }}/

    - name: train-lora
      command: python -m rockit_train.trainer
      args:
        dataset: /data/training/{{ run_id }}/
        config: configs/training/base.yaml
        output: /models/{{ run_id }}/
      resources:
        gpu: 8  # DGX allocation

    - name: evaluate
      command: python -m rockit_train.evaluator
      args:
        model: /models/{{ run_id }}/
        test_data: /data/test/
      gate:
        metric: accuracy
        threshold: 0.85

    - name: register-model
      command: python -m rockit_train.registry
      args:
        model: /models/{{ run_id }}/
        metrics: /models/{{ run_id }}/metrics.json
        registry: gs://rockit-models/
```

### Model Registry

```
gs://rockit-models/
├── registry.json              # Model version manifest
├── v001/
│   ├── model.safetensors      # Model weights
│   ├── adapter_config.json    # LoRA config
│   ├── metrics.json           # Evaluation metrics
│   └── metadata.json          # Training config, data version, git SHA
├── v002/
│   └── ...
└── production/
    └── model -> ../v002/      # Symlink to current production model
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
        --set-env-vars MODEL_VERSION=$MODEL_VERSION \
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

---

## Experiment Tracking

Use **MLflow** (self-hosted on GCP or Vertex AI Experiments) to track:

```python
# packages/rockit-train/src/rockit_train/trainer.py
import mlflow

def train(dataset_path: str, config_path: str, output_path: str):
    config = load_config(config_path)

    with mlflow.start_run():
        mlflow.log_params(config)
        mlflow.log_param("dataset", dataset_path)
        mlflow.log_param("git_sha", get_git_sha())

        model = run_lora_training(dataset_path, config)
        metrics = evaluate(model)

        mlflow.log_metrics(metrics)
        mlflow.log_artifact(output_path)
```

---

## CI/CD Summary

| Event | Trigger | Pipeline | Output |
|-------|---------|----------|--------|
| PR opened | Code change | Lint + Test + Backtest regression | Pass/Fail gate |
| Merge to main | PR merge | Full backtest + Deterministic data gen | Data in GCS |
| New data in GCS | Cloud event | Training + Evaluation + Model registry | New model version |
| New model registered | Registry event | Build + Staging deploy + Integration test + Prod deploy | Live API |
| Config change | `configs/` change | Re-run backtest with new params | Updated results |

---

## Local Development

Developers can run any pipeline stage locally:

```bash
# Run backtest for a single strategy
make backtest STRATEGY=dalton_auction

# Generate deterministic data locally
make deterministic

# Train locally (requires GPU)
make train CONFIG=configs/training/experiments/small.yaml

# Run API locally
make serve

# Full pipeline (backtest → data → serve, no training)
make pipeline-local
```
