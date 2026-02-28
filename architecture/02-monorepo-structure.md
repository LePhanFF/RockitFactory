# Monorepo Structure

> **Revision 2** — Updated after local code inspection. Key change: strategies and backtest engine
> are tightly coupled in the current codebase (strategies depend on `session_context` built by the engine).
> Rather than forcing a split, `rockit-core` keeps them together as a cohesive research library.
> The 38 deterministic modules from the standalone rockit-framework are also consolidated here.

## Repository Layout

```
RockitFactory/
├── architecture/              # This proposal (living documentation)
├── packages/
│   ├── rockit-core/           # THE library: strategies + engine + analysis
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   └── rockit_core/
│   │   │       ├── __init__.py
│   │   │       │
│   │   │       ├── strategies/           # 16 strategies (from BookMapOrderFlowStudies)
│   │   │       │   ├── __init__.py       # Registry: ALL_STRATEGIES, CORE_STRATEGIES
│   │   │       │   ├── base.py           # StrategyBase — "emit signals, never manage positions"
│   │   │       │   ├── signal.py         # Signal dataclass
│   │   │       │   ├── day_type.py       # DayType enum + TrendStrength + classify_day_type()
│   │   │       │   ├── day_confidence.py # DayTypeConfidenceScorer
│   │   │       │   ├── trend_bull.py     # TrendDayBull
│   │   │       │   ├── trend_bear.py     # TrendDayBear (disabled on NQ)
│   │   │       │   ├── super_trend_bull.py
│   │   │       │   ├── super_trend_bear.py  # (disabled on NQ)
│   │   │       │   ├── p_day.py          # PDayStrategy
│   │   │       │   ├── b_day.py          # BDayStrategy (IBH fade disabled)
│   │   │       │   ├── neutral_day.py    # NeutralDayStrategy (pass)
│   │   │       │   ├── pm_morph.py       # PMMorphStrategy
│   │   │       │   ├── morph_to_trend.py # MorphToTrendStrategy
│   │   │       │   ├── orb_enhanced.py   # ORBEnhanced (research, 581 LOC)
│   │   │       │   ├── orb_vwap_breakout.py
│   │   │       │   ├── ema_trend_follow.py
│   │   │       │   ├── liquidity_sweep.py
│   │   │       │   ├── eighty_percent_rule.py
│   │   │       │   └── mean_reversion_vwap.py
│   │   │       │
│   │   │       ├── engine/               # Backtest engine (from BookMapOrderFlowStudies)
│   │   │       │   ├── __init__.py
│   │   │       │   ├── backtest.py       # UnifiedBacktestEngine (bar-by-bar orchestrator)
│   │   │       │   ├── execution.py      # ExecutionModel (slippage, commission)
│   │   │       │   ├── position.py       # PositionManager + OpenPosition
│   │   │       │   ├── trade.py          # Trade dataclass
│   │   │       │   └── equity.py         # EquityCurve tracking
│   │   │       │
│   │   │       ├── filters/              # Signal filter chain
│   │   │       │   ├── __init__.py
│   │   │       │   ├── base.py           # FilterBase abstract class
│   │   │       │   ├── composite.py      # CompositeFilter (AND chain)
│   │   │       │   ├── order_flow.py     # DeltaFilter, CVDFilter, VolumeFilter
│   │   │       │   ├── regime.py         # RegimeFilter
│   │   │       │   ├── time.py           # TimeFilter
│   │   │       │   ├── trend.py          # TrendFilter
│   │   │       │   └── volatility.py     # VolatilityFilter
│   │   │       │
│   │   │       ├── indicators/           # Technical indicators
│   │   │       │   ├── __init__.py
│   │   │       │   ├── technical.py      # EMA, VWAP, ATR, RSI
│   │   │       │   ├── ict_models.py     # FVG, IFVG, BPR, MSS, CSS, OTE
│   │   │       │   ├── smt_divergence.py # Smart Money Theory divergence
│   │   │       │   ├── ib_width.py       # Initial Balance width analysis
│   │   │       │   └── value_area.py     # Value area computation (70% rule)
│   │   │       │
│   │   │       ├── profile/              # Market profile utilities
│   │   │       │   ├── __init__.py
│   │   │       │   ├── volume_profile.py # POC, VAH, VAL, HVN/LVN
│   │   │       │   ├── tpo_profile.py    # TPO letters, shape, fattening zones
│   │   │       │   ├── dpoc_migration.py # DPOC movement tracking
│   │   │       │   ├── ib_analysis.py    # IB-specific analysis
│   │   │       │   ├── confluences.py    # Level confluence detection
│   │   │       │   └── wick_parade.py    # Wick parade (extremes analysis)
│   │   │       │
│   │   │       ├── deterministic/        # Deterministic analysis (from rockit-framework)
│   │   │       │   ├── __init__.py
│   │   │       │   ├── orchestrator.py   # generate_snapshot() — merges all modules
│   │   │       │   ├── modules/          # 38 analysis modules consolidated
│   │   │       │   │   ├── __init__.py
│   │   │       │   │   ├── premarket.py          # Asia/London/overnight levels
│   │   │       │   │   ├── ib_location.py        # IB placement analysis
│   │   │       │   │   ├── volume_profile.py     # VP for snapshots
│   │   │       │   │   ├── tpo_profile.py        # TPO for snapshots
│   │   │       │   │   ├── dpoc_migration.py     # DPOC migration
│   │   │       │   │   ├── wick_parade.py        # Wick analysis
│   │   │       │   │   ├── fvg_detection.py      # Multi-TF FVG detection
│   │   │       │   │   ├── ninety_min_pd_arrays.py
│   │   │       │   │   ├── core_confluences.py   # Boolean signal confluences
│   │   │       │   │   ├── cross_market.py       # ES/YM cross-market
│   │   │       │   │   ├── vix_regime.py         # VIX regime classification
│   │   │       │   │   ├── inference_engine.py   # 8 deterministic rules
│   │   │       │   │   ├── decision_engine.py    # Day type classification
│   │   │       │   │   ├── cri.py                # Contextual Readiness Index (412 LOC)
│   │   │       │   │   ├── dalton.py             # Trend strength quantification (360 LOC)
│   │   │       │   │   ├── playbook_engine.py    # 10 playbooks (setup generation)
│   │   │       │   │   ├── playbook_engine_v2.py # Enhanced playbook
│   │   │       │   │   ├── balance_classification.py
│   │   │       │   │   ├── mean_reversion_engine.py
│   │   │       │   │   ├── or_reversal.py        # OR Reversal setup
│   │   │       │   │   ├── edge_fade.py          # Edge Fade setup
│   │   │       │   │   ├── va_edge_fade.py       # VA Edge Fade (334 LOC)
│   │   │       │   │   ├── globex_va_analysis.py # 80% rule
│   │   │       │   │   ├── twenty_percent_rule.py # 20% IB extension
│   │   │       │   │   ├── enhanced_reasoning.py # 9-step reasoning for training
│   │   │       │   │   ├── cri_psychology_voice.py
│   │   │       │   │   ├── market_structure_events.py
│   │   │       │   │   ├── outcome_labeling.py   # Training outcome labels
│   │   │       │   │   ├── intraday_sampling.py
│   │   │       │   │   ├── loader.py             # CSV loading for snapshots
│   │   │       │   │   ├── config_validator.py
│   │   │       │   │   ├── schema_validator.py
│   │   │       │   │   ├── dataframe_cache.py    # 30% speedup
│   │   │       │   │   ├── error_logger.py
│   │   │       │   │   ├── acceptance_test.py
│   │   │       │   │   └── setup_annotator.py
│   │   │       │   └── schema.json       # Snapshot validation schema
│   │   │       │
│   │   │       ├── data/                 # Data loading and features
│   │   │       │   ├── __init__.py
│   │   │       │   ├── loader.py         # CSV loader (NinjaTrader volumetric format)
│   │   │       │   ├── features.py       # OF features, IB features, day type, ICT
│   │   │       │   └── session.py        # Session grouping utilities
│   │   │       │
│   │   │       ├── reporting/            # Evaluation and reporting
│   │   │       │   ├── __init__.py
│   │   │       │   ├── metrics.py        # WR, PF, Sharpe, MDD, expectancy
│   │   │       │   ├── trade_log.py      # Trade log export
│   │   │       │   ├── day_analyzer.py   # Per-session analysis
│   │   │       │   └── comparison.py     # Cross-strategy comparison
│   │   │       │
│   │   │       └── config/               # Constants and instrument specs
│   │   │           ├── __init__.py
│   │   │           ├── constants.py      # Session times, thresholds, risk defaults
│   │   │           └── instruments.py    # NQ/MNQ/ES/MES/YM/MYM specs
│   │   │
│   │   └── tests/                        # Unit + integration tests
│   │
│   ├── rockit-train/          # ML training pipeline
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   └── rockit_train/
│   │   │       ├── __init__.py
│   │   │       ├── dataset.py            # JSONL training data builder
│   │   │       ├── trainer.py            # Training orchestrator (LoRA + full)
│   │   │       ├── evaluator.py          # Model evaluation gates
│   │   │       ├── registry.py           # Model version registry
│   │   │       ├── models/               # Model configurations
│   │   │       │   ├── qwen_30b.py       # Qwen 30B config
│   │   │       │   └── qwen_70b.py       # Qwen 70B config
│   │   │       └── strategies/           # Training strategies
│   │   │           ├── incremental.py    # Incremental LoRA on new data
│   │   │           └── full_retrain.py   # Full retrain from scratch
│   │   ├── configs/
│   │   │   ├── base.yaml                 # Base training config
│   │   │   └── experiments/              # Experiment configs
│   │   └── tests/
│   │
│   ├── rockit-serve/          # Signals API (NEW — does not exist today)
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   ├── src/
│   │   │   └── rockit_serve/
│   │   │       ├── __init__.py
│   │   │       ├── app.py                # FastAPI application
│   │   │       ├── routes/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── annotations.py    # Annotation endpoints (chart drawing)
│   │   │       │   ├── setups.py         # Trade setup endpoints
│   │   │       │   ├── inference.py      # Deterministic + LLM inference
│   │   │       │   ├── journal.py        # Journal endpoints (from existing RockitAPI)
│   │   │       │   └── health.py         # Health/readiness probes
│   │   │       ├── inference/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── deterministic.py  # Rule-based from rockit-core
│   │   │       │   └── llm.py            # LLM-based inference
│   │   │       └── middleware/
│   │   │           ├── __init__.py
│   │   │           └── auth.py           # JWT auth (from existing RockitAPI)
│   │   └── tests/
│   │
│   ├── rockit-ingest/         # Live data ingestion
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   └── rockit_ingest/
│   │   │       ├── __init__.py
│   │   │       ├── collectors/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── csv_watcher.py    # Watch for CSV files, upload to GCS
│   │   │       │   └── api_push.py       # Direct API push
│   │   │       └── publishers/
│   │   │           ├── __init__.py
│   │   │           └── gcs.py            # GCS upload with retry
│   │   └── tests/
│   │
│   └── rockit-clients/        # Platform-specific thin clients
│       ├── ninjatrader/       # (FULL REWRITE — current C# is standalone)
│       │   ├── RockitIndicator.cs    # Draws annotations from API
│       │   └── RockitStrategy.cs     # Fills trades from API setups
│       ├── tradingview/       # (NEW — no Pine Script exists today)
│       │   └── rockit_indicator.pine
│       └── dashboard/         # (NEW — only a spec exists today)
│           ├── package.json
│           ├── Dockerfile
│           └── src/
│
├── infra/
│   ├── terraform/
│   │   ├── main.tf
│   │   ├── cloud_run.tf
│   │   ├── gcs.tf
│   │   └── variables.tf
│   ├── docker/
│   │   └── docker-compose.yaml
│   └── cloudbuild/
│       ├── ci.yaml
│       ├── train.yaml
│       └── deploy.yaml
│
├── configs/
│   ├── strategies.yaml        # Strategy configuration
│   ├── instruments.yaml       # Instrument definitions
│   ├── training/              # Training configs per model
│   │   ├── qwen-30b.yaml
│   │   └── qwen-70b.yaml
│   └── snapshot-schema.json   # Deterministic snapshot validation
│
├── scripts/
│   ├── setup.sh
│   ├── backtest.sh
│   └── train.sh
│
├── pyproject.toml             # Root workspace config
├── Makefile
└── README.md
```

---

## Package Dependency Graph

```
rockit-core          (ZERO dependencies on other rockit packages)
    │                 Contains: strategies, engine, filters, indicators,
    │                 profile, deterministic modules, reporting, config
    │                 THIS is the publishable research library
    │
    ├──▶ rockit-train       (depends on core — uses deterministic modules)
    │
    ├──▶ rockit-serve       (depends on core + train — serves inference)
    │
    ├──▶ rockit-ingest      (depends on core — data normalization)
    │
    └──▶ rockit-clients     (API consumers only — no Python dependency)
         ├── ninjatrader/   (C# HTTP client)
         ├── tradingview/   (Pine Script HTTP client)
         └── dashboard/     (React/JS HTTP client)
```

**Why strategies + engine + deterministic modules are together in core:**
In the current codebase, strategies depend on `session_context` which is built by the backtest engine. The engine imports strategies, filters, indicators, and profile modules. The deterministic orchestrator imports many of the same indicators and profile modules. Splitting these into separate packages would require significant interface redesign with no real benefit. Keeping them together means:
- `rockit-core` is a self-contained research library you can `pip install`
- Backtest, strategy evaluation, and deterministic snapshot generation all work from the same import
- Other packages (train, serve) just `import rockit_core` and use what they need

---

## Workspace Management

```toml
# Root pyproject.toml
[project]
name = "rockit-factory"
requires-python = ">=3.11"

[tool.uv.workspace]
members = [
    "packages/rockit-core",
    "packages/rockit-train",
    "packages/rockit-serve",
    "packages/rockit-ingest",
]

[tool.uv.sources]
rockit-core = { workspace = true }
rockit-train = { workspace = true }
```

Each package has its own `pyproject.toml` declaring only its specific dependencies, while shared workspace resolution ensures version consistency.

---

## What Moves Where

| Source | Destination | Status |
|--------|------------|--------|
| BookMapOrderFlowStudies `strategy/` (16 strategies) | `rockit-core/strategies/` | Move as-is |
| BookMapOrderFlowStudies `engine/` (5 files) | `rockit-core/engine/` | Move as-is |
| BookMapOrderFlowStudies `filters/` (7 files) | `rockit-core/filters/` | Move as-is |
| BookMapOrderFlowStudies `indicators/` (5 files) | `rockit-core/indicators/` | Move as-is |
| BookMapOrderFlowStudies `profile/` (6 files) | `rockit-core/profile/` | Move as-is |
| BookMapOrderFlowStudies `data/` (3 files) | `rockit-core/data/` | Move as-is |
| BookMapOrderFlowStudies `config/` (2 files) | `rockit-core/config/` | Move as-is |
| BookMapOrderFlowStudies `reporting/` (4 files) | `rockit-core/reporting/` | Move as-is |
| rockit-framework `orchestrator.py` + 38 modules | `rockit-core/deterministic/` | Move from standalone repo, deduplicate shared modules |
| rockit-framework training scripts (3 generators) | `rockit-train/` | Move + wrap with MLOps |
| rockit-framework `analyze-today.py` | `rockit-serve/inference/` | Refactor into API endpoints |
| RockitAPI auth + journal endpoints | `rockit-serve/routes/journal.py` | Absorb into new API |
| RockitDataFeed JSONL files | GCS bucket (archived) | Data, not code |
| NinjaTrader C# (2 files, 923 LOC) | **DISCARD** — replaced by thin client | Full rewrite |
| RockitUI spec | `rockit-clients/dashboard/` | Build from scratch |
| Pine Script | `rockit-clients/tradingview/` | Build from scratch (none exists) |

### What Gets Discarded
- BookMapOrderFlowStudies `rockit-framework/` subdirectory (older copy, 12 modules — superseded by standalone 38-module version)
- ~72 research/diagnostic scripts — archive for reference, don't migrate (they served their research purpose)
- `DualOrderFlow_Evaluation.cs` and `DualOrderFlow_Funded.cs` — replaced entirely by thin API client
