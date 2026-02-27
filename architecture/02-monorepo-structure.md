# Monorepo Structure

## Repository Layout

```
RockitFactory/
├── architecture/              # This proposal (living documentation)
├── packages/
│   ├── rockit-core/           # Strategy logic, signals, indicators
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   └── rockit_core/
│   │   │       ├── __init__.py
│   │   │       ├── strategies/
│   │   │       │   ├── __init__.py        # Registry + CORE_STRATEGIES portfolio
│   │   │       │   ├── base.py            # StrategyBase — "emit signals, never manage positions"
│   │   │       │   ├── signal.py          # Signal dataclass (entry/stop/target/direction/confidence)
│   │   │       │   ├── day_type.py        # Dalton day type (SUPER_TREND/TREND/P_DAY/B_DAY/NEUTRAL)
│   │   │       │   ├── day_confidence.py  # Real-time day type probability scorer
│   │   │       │   ├── trend_bull.py      # TrendDayBull — VWAP pullback, IBH acceptance
│   │   │       │   ├── trend_bear.py      # TrendDayBear — mirror
│   │   │       │   ├── super_trend_bull.py # SuperTrendBull — >2x IB extension
│   │   │       │   ├── super_trend_bear.py # SuperTrendBear — mirror
│   │   │       │   ├── p_day.py           # PDayStrategy — skewed balance 0.5-1.0x
│   │   │       │   ├── b_day.py           # BDayStrategy — IBL fade narrow days
│   │   │       │   ├── neutral_day.py     # NeutralDayStrategy — range trading
│   │   │       │   ├── pm_morph.py        # PMMorphStrategy — PM session morphs
│   │   │       │   ├── morph_to_trend.py  # MorphToTrendStrategy — intra-session morph
│   │   │       │   ├── edge_fade.py       # EdgeFadeStrategy — IB edge mean reversion
│   │   │       │   ├── bear_accept.py     # BearAcceptShort — acceptance below IBL
│   │   │       │   ├── ibh_sweep.py       # IBHSweepFail — fade failed IBH breakouts
│   │   │       │   ├── or_reversal.py     # OpeningRangeReversal — ICT Judas Swing
│   │   │       │   ├── or_acceptance.py   # ORAcceptanceStrategy — OR continuation
│   │   │       │   ├── ib_retest.py       # IBRetestStrategy — IB level retest
│   │   │       │   ├── balance_signal.py  # BalanceSignal — consolidation detection
│   │   │       │   └── eighty_percent.py  # 80% Rule — VA mean reversion
│   │   │       ├── filters/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── composite.py       # CompositeFilter — signal must pass ALL
│   │   │       │   ├── order_flow.py      # Delta, CVD, imbalance thresholds
│   │   │       │   ├── regime.py          # Strategy-regime-specific gates
│   │   │       │   ├── time.py            # Session time windows
│   │   │       │   ├── trend.py           # Trend alignment filter
│   │   │       │   └── volatility.py      # Volatility regime gates
│   │   │       ├── indicators/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── ict.py             # FVG, IFVG, BPR detection
│   │   │       │   ├── volume_profile.py  # Volume profile computation
│   │   │       │   └── tpo.py             # TPO market profile
│   │   │       ├── data/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── loader.py          # CSV loader (OHLCV + volumetric data)
│   │   │       │   ├── features.py        # OF features, IB features, day type, ICT
│   │   │       │   ├── session.py         # Session grouping utilities
│   │   │       │   └── annotations.py     # Platform-agnostic annotation schema
│   │   │       └── config/
│   │   │           ├── __init__.py
│   │   │           ├── constants.py       # Session times, thresholds, risk defaults
│   │   │           └── instruments.py     # NQ/MNQ/ES/MES/YM/MYM specs
│   │   └── tests/
│   │
│   ├── rockit-pipeline/       # Backtesting, evaluation, deterministic data
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   └── rockit_pipeline/
│   │   │       ├── __init__.py
│   │   │       ├── backtest/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── engine.py          # Backtest runner
│   │   │       │   ├── portfolio.py       # Multi-strategy portfolio
│   │   │       │   └── metrics.py         # Performance metrics/stats
│   │   │       ├── evaluation/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── session_eval.py    # Per-session evaluation
│   │   │       │   └── report.py          # Evaluation reports
│   │   │       ├── deterministic/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── generator.py       # Deterministic data gen
│   │   │       │   ├── annotator.py       # Data annotation
│   │   │       │   └── benchmark.py       # Benchmarking
│   │   │       └── data/
│   │   │           ├── __init__.py
│   │   │           ├── loaders.py         # Data source loaders
│   │   │           └── transforms.py      # Data transformations
│   │   └── tests/
│   │
│   ├── rockit-train/          # ML training, LoRA, model management
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   └── rockit_train/
│   │   │       ├── __init__.py
│   │   │       ├── dataset.py             # Training dataset builder
│   │   │       ├── lora_config.py         # LoRA hyperparameters
│   │   │       ├── trainer.py             # Training orchestrator
│   │   │       ├── evaluator.py           # Model evaluation
│   │   │       └── registry.py            # Model version registry
│   │   ├── configs/
│   │   │   ├── base.yaml                  # Base training config
│   │   │   └── experiments/               # Experiment configs
│   │   └── tests/
│   │
│   ├── rockit-serve/          # API, inference, deployment
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   ├── src/
│   │   │   └── rockit_serve/
│   │   │       ├── __init__.py
│   │   │       ├── app.py                 # FastAPI application
│   │   │       ├── routes/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── signals.py         # Live signal endpoints
│   │   │       │   ├── annotations.py     # Annotation endpoints
│   │   │       │   ├── setups.py          # Trade setup endpoints
│   │   │       │   └── health.py          # Health/readiness probes
│   │   │       ├── inference/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── deterministic.py   # Rule-based inference
│   │   │       │   └── llm.py             # LLM-based inference
│   │   │       └── middleware/
│   │   │           ├── __init__.py
│   │   │           └── auth.py            # API authentication
│   │   └── tests/
│   │
│   ├── rockit-ingest/         # Live data ingestion
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   └── rockit_ingest/
│   │   │       ├── __init__.py
│   │   │       ├── collectors/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── csv_watcher.py     # Legacy CSV file watcher
│   │   │       │   ├── gcs_uploader.py    # Direct GCS upload
│   │   │       │   └── stream.py          # Streaming collector
│   │   │       ├── processors/
│   │   │       │   ├── __init__.py
│   │   │       │   └── normalizer.py      # Data normalization
│   │   │       └── publishers/
│   │   │           ├── __init__.py
│   │   │           └── pubsub.py          # Pub/Sub publisher
│   │   └── tests/
│   │
│   └── rockit-clients/        # Platform-specific thin clients
│       ├── ninjatrader/
│       │   ├── RockitIndicator.cs         # Generic API-driven indicator
│       │   └── RockitStrategy.cs          # Generic API-driven strategy
│       ├── tradingview/
│       │   └── rockit_indicator.pine      # Pine Script indicator
│       └── dashboard/
│           ├── package.json
│           ├── Dockerfile
│           └── src/                       # React/Next.js dashboard
│
├── infra/                     # Infrastructure as Code
│   ├── terraform/
│   │   ├── main.tf
│   │   ├── cloud_run.tf                   # API + UI deployment
│   │   ├── gcs.tf                         # Storage buckets
│   │   ├── pubsub.tf                      # Pub/Sub topics
│   │   ├── vertex_ai.tf                   # Training pipelines
│   │   └── variables.tf
│   ├── docker/
│   │   └── docker-compose.yaml            # Local dev environment
│   └── cloudbuild/
│       ├── ci.yaml                        # CI pipeline
│       ├── train.yaml                     # Training pipeline
│       └── deploy.yaml                    # Deployment pipeline
│
├── configs/
│   ├── strategies.yaml                    # Strategy configuration
│   ├── instruments.yaml                   # Instrument definitions
│   └── sessions.yaml                      # Session schedules
│
├── scripts/
│   ├── setup.sh                           # Dev environment setup
│   ├── backtest.sh                        # Run backtests locally
│   └── train.sh                           # Kick off training
│
├── pyproject.toml             # Root workspace config
├── Makefile                   # Common commands
└── README.md
```

---

## Package Dependency Graph

```
rockit-core          (zero dependencies on other rockit packages)
    │
    ├──▶ rockit-pipeline     (depends on core)
    │        │
    │        └──▶ rockit-train    (depends on core + pipeline)
    │
    ├──▶ rockit-serve        (depends on core + pipeline + train)
    │
    ├──▶ rockit-ingest       (depends on core)
    │
    └──▶ rockit-clients      (API consumers only — no Python dependency)
```

**Key rule:** `rockit-core` has zero internal dependencies. It's a pure library of strategy logic, data models, and indicators. Everything else depends on it, never the reverse.

---

## Workspace Management

Use Python workspace tooling to manage the monorepo:

```toml
# Root pyproject.toml
[project]
name = "rockit-factory"
requires-python = ">=3.11"

[tool.uv.workspace]
members = [
    "packages/rockit-core",
    "packages/rockit-pipeline",
    "packages/rockit-train",
    "packages/rockit-serve",
    "packages/rockit-ingest",
]

[tool.uv.sources]
rockit-core = { workspace = true }
rockit-pipeline = { workspace = true }
rockit-train = { workspace = true }
```

Each package has its own `pyproject.toml` declaring only its specific dependencies, while shared workspace resolution ensures version consistency.

---

## What Moves Where (from current repos)

| Current Location | New Location | Notes |
|-----------------|-------------|-------|
| BookMapOrderFlowStudies (Python strategies) | `packages/rockit-core/src/rockit_core/strategies/` | Canonical strategy logic |
| BookMapOrderFlowStudies (NinjaTrader C#) | `packages/rockit-clients/ninjatrader/` | Rewritten as thin API client |
| rockit-framework (deterministic data gen) | `packages/rockit-pipeline/src/rockit_pipeline/deterministic/` | Data generation |
| rockit-framework (training code) | `packages/rockit-train/` | Training orchestration |
| RockitAPI | `packages/rockit-serve/` | API serving |
| RockitUI | `packages/rockit-clients/dashboard/` | Dashboard UI |
