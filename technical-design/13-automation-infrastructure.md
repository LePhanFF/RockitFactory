# Automation & Infrastructure Technical Design

> **Status:** Draft
> **Covers:** APScheduler, CI/CD (GitHub Actions), Makefile, event-driven triggers, monitoring, data validation, version management, auto-rollback
> **Related:** [12-training-mlops.md](12-training-mlops.md) for training pipeline details

---

## 1. Purpose

The architecture docs describe *what* should be automated but leave gaps in *how*. This document fills those gaps with concrete implementations:

| Gap | Solution |
|-----|----------|
| CloudBuild pseudo-code | Real GitHub Actions YAML |
| "APScheduler runs jobs" | Full init, timezone, error recovery, job registry |
| "Makefile targets" | Complete Makefile with all targets |
| "GCS triggers training" | GCS → Pub/Sub → Cloud Run → pipeline |
| "Monitor and alert" | Health checks, Slack webhooks, rollback triggers |
| "Data quality validation" | Schema validation, drift detection, anomaly checks |
| "Version manager" | Adapter version tracking, promotion, rollback |

---

## 2. APScheduler Setup

### 2.1 Initialization

```python
# packages/rockit-serve/src/rockit_serve/scheduler.py
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

logger = logging.getLogger(__name__)

# US/Eastern timezone — all market-related jobs use ET
ET = "US/Eastern"


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler(
        jobstores={"default": MemoryJobStore()},
        job_defaults={
            "coalesce": True,          # If job missed multiple fires, run once
            "max_instances": 1,         # Never overlap same job
            "misfire_grace_time": 300,  # 5 min grace for late execution
        },
        timezone=ET,
    )

    # Error handling listener
    scheduler.add_listener(_on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    return scheduler


def _on_job_event(event):
    """Handle job execution and error events."""
    if event.exception:
        logger.error(
            "Job %s failed: %s",
            event.job_id,
            event.exception,
            exc_info=event.traceback,
        )
        # Send alert for critical jobs
        if event.job_id in CRITICAL_JOBS:
            send_slack_alert(
                f"CRITICAL job `{event.job_id}` failed: {event.exception}"
            )
    else:
        logger.info("Job %s completed successfully", event.job_id)


# Jobs that trigger Slack alerts on failure
CRITICAL_JOBS = {
    "daily_production_eval",
    "weekly_training_check",
    "rollback_monitor",
    "daily_reflection",
}
```

### 2.2 Job Registry

```python
# packages/rockit-serve/src/rockit_serve/jobs/__init__.py
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

ET = "US/Eastern"


def register_all_jobs(scheduler, services):
    """Register all scheduled jobs. Called once at startup."""

    # ── Market Hours Jobs (ET timezone) ──

    # Pre-market data refresh (6:00 AM ET, Mon-Fri)
    scheduler.add_job(
        services.data.refresh_premarket,
        trigger=CronTrigger(day_of_week="mon-fri", hour=6, minute=0, timezone=ET),
        id="premarket_refresh",
        name="Pre-market data refresh",
    )

    # Post-market daily reflection (5:00 PM ET, Mon-Fri)
    scheduler.add_job(
        services.reflection.daily_reflect,
        trigger=CronTrigger(day_of_week="mon-fri", hour=17, minute=0, timezone=ET),
        id="daily_reflection",
        name="Daily post-market reflection",
    )

    # Post-market production eval (5:30 PM ET, Mon-Fri)
    scheduler.add_job(
        services.eval.run_production_eval,
        trigger=CronTrigger(day_of_week="mon-fri", hour=17, minute=30, timezone=ET),
        id="daily_production_eval",
        name="Daily production model evaluation",
    )

    # Weekly training check (Friday 6:00 PM ET)
    scheduler.add_job(
        services.training.check_incremental,
        trigger=CronTrigger(day_of_week="fri", hour=18, minute=0, timezone=ET),
        id="weekly_training_check",
        name="Weekly incremental training check",
    )

    # Multi-day meta-review (Wednesday + Saturday 8:00 PM ET)
    scheduler.add_job(
        services.reflection.meta_review,
        trigger=CronTrigger(day_of_week="wed,sat", hour=20, minute=0, timezone=ET),
        id="meta_review",
        name="Multi-day meta-review (Opus 4.6)",
    )

    # ── Infrastructure Jobs ──

    # Rollback monitor (every 30 min during market hours)
    scheduler.add_job(
        services.monitoring.check_rollback,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour="9-16",          # 9 AM - 4 PM ET
            minute="0,30",
            timezone=ET,
        ),
        id="rollback_monitor",
        name="Production rollback monitor",
    )

    # Health check (every 5 min, always)
    scheduler.add_job(
        services.monitoring.health_check,
        trigger=IntervalTrigger(minutes=5),
        id="health_check",
        name="System health check",
    )

    # Data quality validation (daily 4:30 PM ET after market close)
    scheduler.add_job(
        services.data.validate_daily,
        trigger=CronTrigger(day_of_week="mon-fri", hour=16, minute=30, timezone=ET),
        id="daily_data_validation",
        name="Daily data quality validation",
    )
```

### 2.3 FastAPI Lifespan Integration

```python
# packages/rockit-serve/src/rockit_serve/app.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .scheduler import create_scheduler
from .jobs import register_all_jobs
from .services import create_services


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle for FastAPI."""
    # Startup
    scheduler = create_scheduler()
    services = create_services(app.state.config)
    register_all_jobs(scheduler, services)
    scheduler.start()

    app.state.scheduler = scheduler
    app.state.services = services

    yield

    # Shutdown
    scheduler.shutdown(wait=True)


app = FastAPI(title="Rockit API", lifespan=lifespan)
```

### 2.4 Error Recovery

```python
# packages/rockit-serve/src/rockit_serve/jobs/error_recovery.py
import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [60, 300, 900]  # 1 min, 5 min, 15 min


async def with_retry(func, *args, job_id: str, **kwargs):
    """
    Execute a job function with retry logic.
    Uses exponential backoff: 1 min, 5 min, 15 min.
    """
    for attempt in range(MAX_RETRIES):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                logger.error(
                    "Job %s failed after %d retries: %s",
                    job_id, MAX_RETRIES, e,
                )
                raise
            delay = RETRY_DELAYS[attempt]
            logger.warning(
                "Job %s attempt %d failed, retrying in %ds: %s",
                job_id, attempt + 1, delay, e,
            )
            await asyncio.sleep(delay)


class CircuitBreaker:
    """
    Prevent repeated execution of a failing job.
    After `failure_threshold` consecutive failures, stop trying
    for `recovery_timeout` seconds.
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 3600):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure: datetime | None = None
        self.state = "closed"  # closed (normal), open (blocking), half-open (testing)

    def can_execute(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if self.last_failure and (
                datetime.utcnow() - self.last_failure
                > timedelta(seconds=self.recovery_timeout)
            ):
                self.state = "half-open"
                return True
            return False
        # half-open: allow one attempt
        return True

    def record_success(self):
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure = datetime.utcnow()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.error(
                "Circuit breaker OPEN after %d failures. "
                "Will retry in %ds.",
                self.failure_count,
                self.recovery_timeout,
            )
```

---

## 3. CI/CD: GitHub Actions Workflows

### 3.1 Main CI Pipeline

```yaml
# .github/workflows/ci.yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv sync --all-packages

      - name: Lint
        run: uv run ruff check packages/

      - name: Format check
        run: uv run ruff format --check packages/

      - name: Type check
        run: uv run pyright packages/rockit-core/src/ packages/rockit-train/src/

      - name: Unit tests
        run: uv run pytest packages/ -x -q --tb=short -m "not integration and not gpu"

  backtest-regression:
    needs: lint-and-test
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv sync --package rockit-core

      - name: Run backtest regression
        run: |
          uv run python -m rockit_core.engine.backtest \
            --config configs/strategies.yaml \
            --sessions 259 \
            --output backtest-results/

      - name: Compare against baseline
        run: |
          uv run python -m rockit_core.reporting.comparison \
            --current backtest-results/ \
            --baseline configs/baseline-metrics.json \
            --fail-on-regression

      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: backtest-results
          path: backtest-results/

  deterministic-snapshot:
    needs: lint-and-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv sync --package rockit-core

      - name: Generate deterministic snapshots
        run: |
          uv run python -m rockit_core.deterministic.orchestrator \
            --config configs/strategies.yaml \
            --output snapshots/

      - name: Upload to GCS
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - run: |
          gsutil -m cp -r snapshots/ \
            gs://rockit-data/deterministic/${{ github.sha }}/
```

### 3.2 Training Pipeline

See `technical-design/12-training-mlops.md` section 7.3 for the full `training-pipeline.yaml`.

### 3.3 Deploy Pipeline

```yaml
# .github/workflows/deploy.yaml
name: Deploy

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        type: choice
        options:
          - staging
          - production
      service:
        description: 'Service to deploy'
        required: true
        type: choice
        options:
          - rockit-serve
          - all

env:
  REGION: us-central1
  PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      image_tag: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v4

      - name: Auth to GCP
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Setup Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          file: packages/rockit-serve/Dockerfile
          push: true
          tags: |
            ${{ env.REGION }}-docker.pkg.dev/${{ env.PROJECT_ID }}/rockit/serve:${{ github.sha }}
            ${{ env.REGION }}-docker.pkg.dev/${{ env.PROJECT_ID }}/rockit/serve:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Image tag
        id: meta
        run: echo "tags=${{ env.REGION }}-docker.pkg.dev/${{ env.PROJECT_ID }}/rockit/serve:${{ github.sha }}" >> "$GITHUB_OUTPUT"

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4

      - name: Auth to GCP
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Deploy to Cloud Run (staging)
        uses: google-github-actions/deploy-cloudrun@v2
        with:
          service: rockit-api-staging
          image: ${{ needs.build.outputs.image_tag }}
          region: ${{ env.REGION }}
          env_vars: |
            ENVIRONMENT=staging
            MODEL_REGISTRY=gs://rockit-models

      - name: Run integration tests
        run: |
          uv sync --package rockit-serve
          uv run pytest packages/rockit-serve/tests/integration/ \
            --api-url https://rockit-api-staging-${{ env.PROJECT_ID }}.run.app

  deploy-production:
    needs: deploy-staging
    if: inputs.environment == 'production'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Auth to GCP
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Promote staging to production
        run: |
          gcloud run services update-traffic rockit-api \
            --region ${{ env.REGION }} \
            --to-latest

      - name: Notify
        run: |
          curl -X POST ${{ secrets.SLACK_WEBHOOK }} \
            -H 'Content-Type: application/json' \
            -d '{"text": "Deployed `rockit-serve` to production: `${{ github.sha }}`"}'
```

---

## 4. Makefile

```makefile
# Makefile — RockitFactory development commands
.DEFAULT_GOAL := help
SHELL := /bin/bash

# ── Variables ──
PYTHON := uv run python
PYTEST := uv run pytest
RUFF := uv run ruff

# ── Help ──
.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

# ── Setup ──
.PHONY: install
install: ## Install all packages with uv
	uv sync --all-packages

.PHONY: install-train
install-train: ## Install training dependencies (GPU machine)
	uv sync --package rockit-train
	pip install unsloth axolotl wandb lm-eval autoawq vllm

# ── Code Quality ──
.PHONY: lint
lint: ## Run ruff linter
	$(RUFF) check packages/

.PHONY: format
format: ## Format code with ruff
	$(RUFF) format packages/

.PHONY: typecheck
typecheck: ## Run pyright type checker
	uv run pyright packages/rockit-core/src/ packages/rockit-train/src/

# ── Tests ──
.PHONY: test
test: ## Run all unit tests
	$(PYTEST) packages/ -x -q --tb=short -m "not integration and not gpu"

.PHONY: test-core
test-core: ## Run rockit-core tests only
	$(PYTEST) packages/rockit-core/tests/ -x -q

.PHONY: test-train
test-train: ## Run rockit-train tests only
	$(PYTEST) packages/rockit-train/tests/ -x -q -m "not gpu"

.PHONY: test-serve
test-serve: ## Run rockit-serve tests only
	$(PYTEST) packages/rockit-serve/tests/ -x -q -m "not integration"

.PHONY: test-integration
test-integration: ## Run integration tests (requires running API)
	$(PYTEST) packages/rockit-serve/tests/integration/ -x -q

.PHONY: test-all
test-all: lint typecheck test ## Run lint + typecheck + tests

# ── Backtest ──
.PHONY: backtest
backtest: ## Run backtest (STRATEGY=all or STRATEGY=trend_bull)
	$(PYTHON) -m rockit_core.engine.backtest \
		--config configs/strategies.yaml \
		--strategy $(or $(STRATEGY),all) \
		--sessions 259 \
		--output backtest-results/

.PHONY: backtest-compare
backtest-compare: ## Compare backtest results against baseline
	$(PYTHON) -m rockit_core.reporting.comparison \
		--current backtest-results/ \
		--baseline configs/baseline-metrics.json

# ── Deterministic ──
.PHONY: deterministic
deterministic: ## Generate deterministic snapshots
	$(PYTHON) -m rockit_core.deterministic.orchestrator \
		--config configs/strategies.yaml \
		--output snapshots/

# ── Training Data ──
.PHONY: training-data
training-data: ## Build training dataset from raw JSONL
	$(PYTHON) -m rockit_train.dataset build \
		--raw-data data/raw/ \
		--output data/training/latest/ \
		--holdout-config configs/eval/holdout-sessions.yaml

.PHONY: validate-data
validate-data: ## Validate training dataset
	$(PYTHON) -m rockit_train.dataset validate \
		--path data/training/latest/

# ── Training ──
.PHONY: train
train: ## Train model (CONFIG=path MODE=incremental|full)
	$(PYTHON) -m rockit_train.train \
		--config $(or $(CONFIG),configs/training/unsloth-qwen3.5-30b-moe.yaml) \
		--mode $(or $(MODE),incremental)

.PHONY: train-axolotl
train-axolotl: ## Train with Axolotl (multi-GPU, CONFIG=path)
	accelerate launch -m axolotl.cli.train \
		$(or $(CONFIG),configs/training/axolotl-qwen3.5-30b-moe.yaml)

# ── Evaluation ──
.PHONY: benchmark
benchmark: ## Benchmark a model (MODEL=path ADAPTER=path)
	$(PYTHON) -m rockit_train.benchmark \
		--model $(MODEL) \
		--adapter $(ADAPTER) \
		--holdout data/holdout/rockit-eval-50.jsonl

.PHONY: compare
compare: ## Compare two models (MODEL_A=path MODEL_B=path)
	$(PYTHON) -m rockit_train.benchmark \
		--compare $(MODEL_A) $(MODEL_B) \
		--holdout data/holdout/rockit-eval-50.jsonl

.PHONY: leaderboard
leaderboard: ## Generate model leaderboard
	$(PYTHON) -m rockit_train.leaderboard \
		--models-dir models/ \
		--holdout data/holdout/rockit-eval-50.jsonl \
		--output leaderboard.json

.PHONY: standard-bench
standard-bench: ## Run standard benchmarks (MMLU, HellaSwag)
	lm_eval --model hf \
		--model_args pretrained=$(MODEL),peft=$(ADAPTER) \
		--tasks mmlu,hellaswag,arc_challenge \
		--batch_size auto \
		--output_path eval_results/standard/

# ── Serving ──
.PHONY: serve
serve: ## Run API locally (deterministic only, no LLM)
	$(PYTHON) -m rockit_serve.main --no-llm

.PHONY: serve-with-llm
serve-with-llm: ## Run API with LLM inference (MODEL=name)
	$(PYTHON) -m rockit_serve.main --model $(or $(MODEL),qwen3.5-30b-a3b)

.PHONY: serve-vllm
serve-vllm: ## Start vLLM server (MODEL=path ADAPTER=path)
	python -m vllm.entrypoints.openai.api_server \
		--model $(or $(MODEL),Qwen/Qwen3.5-30B-A3B) \
		--enable-lora \
		--lora-modules production=$(ADAPTER) \
		--tensor-parallel-size 2

# ── Quantization ──
.PHONY: quantize-awq
quantize-awq: ## Quantize model to AWQ (INPUT=path OUTPUT=path)
	$(PYTHON) -m rockit_train.quantize.awq \
		--input $(INPUT) \
		--output $(OUTPUT)

.PHONY: quantize-gguf
quantize-gguf: ## Convert to GGUF for Ollama (INPUT=path OUTPUT=path)
	$(PYTHON) -m rockit_train.quantize.gguf \
		--input $(INPUT) \
		--output $(OUTPUT) \
		--quant-type q4_k_m

# ── Docker ──
.PHONY: docker-build
docker-build: ## Build rockit-serve Docker image
	docker compose build rockit-serve

.PHONY: docker-up
docker-up: ## Start all services via Docker Compose
	docker compose up -d

.PHONY: docker-down
docker-down: ## Stop all services
	docker compose down

# ── Cleanup ──
.PHONY: clean
clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf backtest-results/ snapshots/ eval_results/ outputs/
```

---

## 5. Event-Driven Triggers

### 5.1 GCS → Training Pipeline

When new data lands in GCS, trigger the training pipeline:

```python
# packages/rockit-serve/src/rockit_serve/triggers/gcs_trigger.py
"""
GCS event trigger for training pipeline.

Architecture:
  GCS upload → Pub/Sub notification → Cloud Run endpoint → GitHub Actions dispatch

Setup:
  1. Enable GCS notifications on the bucket
  2. Create Pub/Sub subscription pushing to Cloud Run endpoint
  3. Cloud Run endpoint dispatches GitHub Actions workflow
"""
import hashlib
import hmac
import json
import logging
from fastapi import APIRouter, Request, HTTPException
import httpx

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/triggers", tags=["triggers"])


@router.post("/gcs-event")
async def handle_gcs_event(request: Request):
    """
    Handle GCS Pub/Sub push notification.
    Triggers training pipeline when new data lands in gs://rockit-data/raw/.
    """
    body = await request.json()
    message = body.get("message", {})
    attributes = message.get("attributes", {})

    bucket = attributes.get("bucketId")
    object_name = attributes.get("objectId", "")
    event_type = attributes.get("eventType")

    # Only trigger on new objects in raw data path
    if event_type != "OBJECT_FINALIZE":
        return {"status": "ignored", "reason": "not a finalize event"}

    if not object_name.startswith("raw/"):
        return {"status": "ignored", "reason": "not in raw/ path"}

    if not object_name.endswith(".jsonl"):
        return {"status": "ignored", "reason": "not a JSONL file"}

    logger.info("New training data detected: gs://%s/%s", bucket, object_name)

    # Dispatch GitHub Actions training workflow
    await dispatch_training_workflow(
        mode="incremental",
        trigger_reason=f"New data: {object_name}",
    )

    return {"status": "triggered", "object": object_name}


async def dispatch_training_workflow(mode: str, trigger_reason: str):
    """Dispatch GitHub Actions workflow via API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.github.com/repos/<org>/RockitFactory/actions/workflows/training-pipeline.yaml/dispatches",
            headers={
                "Authorization": f"Bearer {get_github_token()}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={
                "ref": "main",
                "inputs": {
                    "mode": mode,
                    "trigger_reason": trigger_reason,
                },
            },
        )
        response.raise_for_status()
```

### 5.2 GCS Notification Setup

```bash
# One-time setup: enable GCS notifications → Pub/Sub
gsutil notification create \
    -t rockit-data-events \
    -f json \
    -e OBJECT_FINALIZE \
    gs://rockit-data

# Create Pub/Sub push subscription to Cloud Run
gcloud pubsub subscriptions create rockit-data-push \
    --topic rockit-data-events \
    --push-endpoint https://rockit-api-<project>.run.app/triggers/gcs-event \
    --ack-deadline 30
```

---

## 6. Monitoring & Alerting

### 6.1 Health Check Endpoint

```python
# packages/rockit-serve/src/rockit_serve/monitoring/health.py
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from fastapi import APIRouter

router = APIRouter(tags=["monitoring"])


@dataclass
class HealthStatus:
    status: str                  # "healthy", "degraded", "unhealthy"
    checks: dict = field(default_factory=dict)
    timestamp: str = ""


@router.get("/health")
async def health_check(services) -> HealthStatus:
    """
    Comprehensive health check covering all subsystems.
    Returns 200 for healthy/degraded, 503 for unhealthy.
    """
    checks = {}

    # 1. API responsiveness
    checks["api"] = {"status": "ok"}

    # 2. Model loaded
    try:
        model_info = services.inference.get_model_info()
        checks["model"] = {
            "status": "ok",
            "model_id": model_info.model_id,
            "adapter_version": model_info.adapter_version,
        }
    except Exception as e:
        checks["model"] = {"status": "error", "message": str(e)}

    # 3. Scheduler running
    scheduler = services.scheduler
    if scheduler.running:
        next_jobs = [
            {"id": job.id, "next_run": str(job.next_run_time)}
            for job in scheduler.get_jobs()[:5]
        ]
        checks["scheduler"] = {"status": "ok", "upcoming_jobs": next_jobs}
    else:
        checks["scheduler"] = {"status": "error", "message": "scheduler not running"}

    # 4. DuckDB accessible
    try:
        count = services.metrics.query_count("SELECT count(*) FROM metrics")
        checks["duckdb"] = {"status": "ok", "total_metrics": count}
    except Exception as e:
        checks["duckdb"] = {"status": "error", "message": str(e)}

    # 5. GCS accessible
    try:
        services.storage.check_bucket()
        checks["gcs"] = {"status": "ok"}
    except Exception as e:
        checks["gcs"] = {"status": "error", "message": str(e)}

    # Aggregate
    statuses = [c.get("status") for c in checks.values()]
    if all(s == "ok" for s in statuses):
        overall = "healthy"
    elif any(s == "error" for s in statuses):
        critical = {"model", "api"}
        if any(checks[k].get("status") == "error" for k in critical if k in checks):
            overall = "unhealthy"
        else:
            overall = "degraded"
    else:
        overall = "degraded"

    return HealthStatus(
        status=overall,
        checks=checks,
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/health/live")
async def liveness():
    """Kubernetes-style liveness probe. Always returns 200 if process is running."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(services):
    """Kubernetes-style readiness probe. Returns 200 only if model is loaded."""
    try:
        services.inference.get_model_info()
        return {"status": "ready"}
    except Exception:
        return {"status": "not_ready"}, 503
```

### 6.2 Slack Alerting

```python
# packages/rockit-serve/src/rockit_serve/monitoring/alerts.py
import json
import logging
import os
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    INFO = "info"          # Blue
    WARNING = "warning"    # Yellow
    CRITICAL = "critical"  # Red


SEVERITY_EMOJI = {
    AlertSeverity.INFO: "large_blue_circle",
    AlertSeverity.WARNING: "warning",
    AlertSeverity.CRITICAL: "red_circle",
}


async def send_slack_alert(
    message: str,
    severity: AlertSeverity = AlertSeverity.WARNING,
    details: dict | None = None,
):
    """Send alert to Slack webhook."""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not set, skipping alert: %s", message)
        return

    emoji = SEVERITY_EMOJI[severity]
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":{emoji}: Rockit Alert ({severity.value.upper()})",
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": message},
        },
    ]

    if details:
        detail_text = "\n".join(f"*{k}:* {v}" for k, v in details.items())
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": detail_text},
        })

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                webhook_url,
                json={"blocks": blocks},
                timeout=10,
            )
            response.raise_for_status()
        except Exception as e:
            logger.error("Failed to send Slack alert: %s", e)
```

---

## 7. Data Quality Validation

```python
# packages/rockit-train/src/rockit_train/data/validation.py
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Required top-level keys in input snapshot
REQUIRED_INPUT_KEYS = {
    "session_date", "current_et_time", "premarket", "intraday",
    "core_confluences", "inference", "cri_readiness",
}

# Required top-level keys in output analysis
REQUIRED_OUTPUT_KEYS = {
    "day_type", "bias", "confidence", "key_levels",
    "lanto_3_model", "day_type_reasoning", "one_liner",
}

VALID_DAY_TYPES = {
    "Trend", "Trend (Bullish)", "Trend (Bearish)",
    "P-Day", "P-Day (Bullish)", "P-Day (Bearish)",
    "B-Day", "B-Day (Bullish)", "B-Day (Bearish)",
    "Neutral", "Neutral Range",
    "Rotational", "Rotational Day",
}

VALID_BIASES = {"Long", "Short", "Flat", "Neutral"}


@dataclass
class ValidationResult:
    total_examples: int
    valid_examples: int
    issues: list[str]

    @property
    def valid_ratio(self) -> float:
        return self.valid_examples / max(self.total_examples, 1)

    @property
    def passed(self) -> bool:
        return self.valid_ratio >= 0.95  # 95% valid threshold


def validate_dataset(path: str) -> ValidationResult:
    """
    Validate a training JSONL file.

    Checks:
    1. JSON parseable
    2. Has required input keys
    3. Has required output keys
    4. day_type is a known value
    5. bias is a known value
    6. confidence is 0-100
    7. No duplicate (session_date, current_et_time) pairs
    8. Temporal ordering (dates are monotonic within file)
    """
    issues = []
    valid = 0
    total = 0
    seen_keys = set()

    with open(path) as f:
        for line_num, line in enumerate(f, 1):
            total += 1
            try:
                example = json.loads(line)
            except json.JSONDecodeError:
                issues.append(f"Line {line_num}: invalid JSON")
                continue

            # Check structure
            if "input" not in example or "output" not in example:
                issues.append(f"Line {line_num}: missing 'input' or 'output' key")
                continue

            inp = example["input"]
            out = example["output"]

            # Input keys
            missing_input = REQUIRED_INPUT_KEYS - set(inp.keys())
            if missing_input:
                issues.append(f"Line {line_num}: missing input keys: {missing_input}")
                continue

            # Output keys
            missing_output = REQUIRED_OUTPUT_KEYS - set(out.keys())
            if missing_output:
                issues.append(f"Line {line_num}: missing output keys: {missing_output}")
                continue

            # Validate values
            if out.get("day_type") not in VALID_DAY_TYPES:
                issues.append(f"Line {line_num}: unknown day_type '{out.get('day_type')}'")

            if out.get("bias") not in VALID_BIASES:
                issues.append(f"Line {line_num}: unknown bias '{out.get('bias')}'")

            conf = out.get("confidence", -1)
            if not (0 <= conf <= 100):
                issues.append(f"Line {line_num}: confidence {conf} out of range [0, 100]")

            # Duplicate check
            dedup_key = (inp.get("session_date"), inp.get("current_et_time"))
            if dedup_key in seen_keys:
                issues.append(f"Line {line_num}: duplicate {dedup_key}")
            seen_keys.add(dedup_key)

            valid += 1

    return ValidationResult(total_examples=total, valid_examples=valid, issues=issues)


def validate_holdout_integrity(
    training_path: str, holdout_path: str
) -> list[str]:
    """
    Verify no holdout sessions leaked into training data.
    Returns list of leaked session dates (should be empty).
    """
    holdout_dates = set()
    with open(holdout_path) as f:
        for line in f:
            example = json.loads(line)
            holdout_dates.add(example["input"]["session_date"])

    leaked = []
    with open(training_path) as f:
        for line in f:
            example = json.loads(line)
            date = example["input"]["session_date"]
            if date in holdout_dates:
                leaked.append(date)

    if leaked:
        logger.error("DATA LEAK: %d holdout sessions in training data: %s", len(leaked), leaked)

    return leaked
```

---

## 8. Version Manager

```python
# packages/rockit-train/src/rockit_train/version_manager.py
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AdapterVersion:
    version: str                    # e.g., "v003"
    base_model: str
    adapter_path: str
    created_at: str
    git_sha: str
    dataset_version: str
    eval_results: dict
    is_production: bool = False
    promoted_at: str | None = None
    retired_at: str | None = None
    retired_reason: str | None = None


class VersionManager:
    """
    Manage adapter versions in the model registry.

    Registry structure (GCS or local):
      registry/
      ├── manifest.json              # List of all versions
      ├── qwen3.5-30b-a3b/
      │   ├── v001/adapter/
      │   ├── v002/adapter/
      │   ├── v003/adapter/
      │   └── production -> v003/    # Symlink to current production
      └── ...
    """

    def __init__(self, registry_path: str):
        self.registry_path = Path(registry_path)
        self.manifest_path = self.registry_path / "manifest.json"

    def list_versions(self, model_family: str) -> list[AdapterVersion]:
        """List all versions for a model family, newest first."""
        manifest = self._load_manifest()
        versions = manifest.get(model_family, [])
        return [AdapterVersion(**v) for v in versions]

    def get_production(self, model_family: str) -> AdapterVersion | None:
        """Get the current production version."""
        for v in self.list_versions(model_family):
            if v.is_production:
                return v
        return None

    def get_previous_production(self, model_family: str) -> AdapterVersion | None:
        """Get the version that was production before current (for rollback)."""
        versions = self.list_versions(model_family)
        retired = [v for v in versions if v.retired_at and v.retired_reason == "superseded"]
        if retired:
            return retired[0]  # Most recently retired
        return None

    def register(self, version: AdapterVersion) -> str:
        """Register a new adapter version."""
        manifest = self._load_manifest()
        family = version.base_model.split("/")[-1].lower()

        if family not in manifest:
            manifest[family] = []

        manifest[family].insert(0, asdict(version))
        self._save_manifest(manifest)

        logger.info("Registered %s version %s", family, version.version)
        return version.version

    def promote(self, model_family: str, version: str) -> None:
        """Promote a version to production. Retires the current production."""
        manifest = self._load_manifest()
        versions = manifest.get(model_family, [])

        for v in versions:
            if v["is_production"]:
                v["is_production"] = False
                v["retired_at"] = datetime.utcnow().isoformat()
                v["retired_reason"] = "superseded"

            if v["version"] == version:
                v["is_production"] = True
                v["promoted_at"] = datetime.utcnow().isoformat()

        self._save_manifest(manifest)
        logger.info("Promoted %s/%s to production", model_family, version)

    def rollback(self, model_family: str) -> str:
        """Rollback to previous production version. Returns rolled-back-to version."""
        previous = self.get_previous_production(model_family)
        if not previous:
            raise ValueError(f"No previous production version for {model_family}")

        current = self.get_production(model_family)
        if current:
            # Retire current with rollback reason
            manifest = self._load_manifest()
            for v in manifest.get(model_family, []):
                if v["version"] == current.version:
                    v["is_production"] = False
                    v["retired_at"] = datetime.utcnow().isoformat()
                    v["retired_reason"] = "rollback"
            self._save_manifest(manifest)

        self.promote(model_family, previous.version)
        logger.warning("Rolled back %s to %s", model_family, previous.version)
        return previous.version

    def _load_manifest(self) -> dict:
        if self.manifest_path.exists():
            return json.loads(self.manifest_path.read_text())
        return {}

    def _save_manifest(self, manifest: dict) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(manifest, indent=2))
```

---

## 9. Auto-Rollback Monitor

```python
# packages/rockit-serve/src/rockit_serve/monitoring/auto_rollback.py
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

from .alerts import send_slack_alert, AlertSeverity

logger = logging.getLogger(__name__)


@dataclass
class RollbackConfig:
    check_interval_minutes: int = 30
    min_inferences_for_check: int = 20
    max_error_rate: float = 0.10
    max_latency_p99_ms: float = 5000
    min_confidence_avg: float = 40.0
    lookback_hours: int = 4
    auto_rollback_enabled: bool = True


async def check_and_rollback(
    config: RollbackConfig,
    metrics_store,
    version_manager,
    model_family: str,
):
    """
    Check production model health and auto-rollback if degraded.

    Called by APScheduler every 30 min during market hours.
    """
    # Query recent inference metrics
    since = datetime.utcnow() - timedelta(hours=config.lookback_hours)
    metrics = metrics_store.query_inference_metrics(since=since)

    if len(metrics) < config.min_inferences_for_check:
        logger.debug(
            "Only %d inferences in window, need %d for check",
            len(metrics), config.min_inferences_for_check,
        )
        return

    # Check error rate
    error_count = sum(1 for m in metrics if m.get("error"))
    error_rate = error_count / len(metrics)

    # Check latency
    latencies = sorted(m["latency_ms"] for m in metrics if "latency_ms" in m)
    p99_idx = int(len(latencies) * 0.99)
    p99_latency = latencies[min(p99_idx, len(latencies) - 1)] if latencies else 0

    # Check confidence
    confidences = [m["confidence"] for m in metrics if "confidence" in m]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 100

    # Evaluate
    issues = []
    if error_rate > config.max_error_rate:
        issues.append(f"Error rate {error_rate:.1%} exceeds {config.max_error_rate:.1%}")
    if p99_latency > config.max_latency_p99_ms:
        issues.append(f"P99 latency {p99_latency:.0f}ms exceeds {config.max_latency_p99_ms:.0f}ms")
    if avg_confidence < config.min_confidence_avg:
        issues.append(f"Avg confidence {avg_confidence:.1f} below {config.min_confidence_avg}")

    if not issues:
        return  # Healthy

    current = version_manager.get_production(model_family)
    details = {
        "model": current.version if current else "unknown",
        "inferences_checked": len(metrics),
        "issues": ", ".join(issues),
    }

    if len(issues) >= 2 and config.auto_rollback_enabled:
        # Multiple issues → auto-rollback
        try:
            rolled_back_to = version_manager.rollback(model_family)
            await send_slack_alert(
                f"AUTO-ROLLBACK triggered. Rolled back to `{rolled_back_to}`.\n"
                f"Issues: {', '.join(issues)}",
                severity=AlertSeverity.CRITICAL,
                details=details,
            )
        except ValueError as e:
            await send_slack_alert(
                f"Rollback FAILED: {e}\nManual intervention required.",
                severity=AlertSeverity.CRITICAL,
                details=details,
            )
    else:
        # Single issue → alert only
        await send_slack_alert(
            f"Production model degradation detected:\n{chr(10).join(issues)}",
            severity=AlertSeverity.WARNING,
            details=details,
        )
```

---

## 10. File Map

```
packages/rockit-serve/src/rockit_serve/
├── app.py                           # FastAPI app with lifespan
├── scheduler.py                     # APScheduler init + error handling
├── jobs/
│   ├── __init__.py                  # register_all_jobs
│   └── error_recovery.py           # Retry logic, circuit breaker
├── triggers/
│   └── gcs_trigger.py              # GCS → Pub/Sub → training dispatch
├── monitoring/
│   ├── health.py                    # /health endpoint
│   ├── alerts.py                    # Slack webhook alerting
│   └── auto_rollback.py            # Auto-rollback monitor

packages/rockit-train/src/rockit_train/
├── version_manager.py               # Adapter version registry
├── data/
│   └── validation.py                # Data quality validation

.github/workflows/
├── ci.yaml                          # Lint, test, backtest regression
├── deploy.yaml                      # Build, stage, promote
└── training-pipeline.yaml           # Full training CI/CD

Makefile                              # All dev commands
```
