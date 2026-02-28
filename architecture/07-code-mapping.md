# Detailed Code Mapping: Current Repos → Monorepo

> **Revision 2** — Updated with actual file inventory from local inspection of all 6 repos.
> Every file path below has been verified to exist.

---

## BookMapOrderFlowStudies → rockit-core

### Strategies → `packages/rockit-core/src/rockit_core/strategies/`

Source: `BookMapOrderFlowStudies/strategy/`

| Current File | Strategy Class | LOC | Notes |
|-------------|---------------|-----|-------|
| `base.py` | `StrategyBase` | 81 | Abstract base — "emit signals, never manage positions" |
| `signal.py` | `Signal` | 46 | Dataclass: timestamp, direction, entry/stop/target, confidence, metadata |
| `day_type.py` | `DayType` enum, `TrendStrength` enum | 139 | SUPER_TREND/TREND/P_DAY/B_DAY/NEUTRAL + classify functions |
| `day_confidence.py` | `DayTypeConfidenceScorer` | 332 | Real-time day type probability scorer |
| `__init__.py` | Registry | 86 | `ALL_STRATEGIES`, `CORE_STRATEGIES`, `RESEARCH_STRATEGIES` |
| **Dalton Core (9)** | | | |
| `trend_bull.py` | `TrendDayBull` | 363 | VWAP pullback, IBH acceptance, OF quality gates |
| `trend_bear.py` | `TrendDayBear` | 289 | Mirror of bull — **disabled on NQ** |
| `super_trend_bull.py` | `SuperTrendBull` | 199 | >2x IB extension, multiple pyramids |
| `super_trend_bear.py` | `SuperTrendBear` | 193 | Mirror — **disabled on NQ** |
| `p_day.py` | `PDayStrategy` | 230 | Skewed balance, 80% success from IB boundary |
| `b_day.py` | `BDayStrategy` | 182 | IBL fade on narrow days — IBH fade **disabled** |
| `neutral_day.py` | `NeutralDayStrategy` | 38 | Pass — no trading |
| `pm_morph.py` | `PMMorphStrategy` | 170 | PM session morph (min 15 pts beyond AM range) |
| `morph_to_trend.py` | `MorphToTrendStrategy` | 122 | Balance → trend transition (min 30 pts beyond IB) |
| **Research (6)** | | | |
| `orb_enhanced.py` | `ORBEnhanced` | 581 | Opening Range Breakout with advanced filters |
| `orb_vwap_breakout.py` | `ORBVwapBreakout` | 220 | ORB + VWAP confluence |
| `ema_trend_follow.py` | `EMATrendFollow` | 273 | EMA20/50 trend following |
| `liquidity_sweep.py` | `LiquiditySweep` | 311 | Liquidity sweep reversal entries |
| `eighty_percent_rule.py` | `EightyPercentRule` | 265 | 80% rule VA mean reversion |
| `mean_reversion_vwap.py` | `MeanReversionVWAP` | 255 | VWAP mean reversion scalping |

**Total: 20 files, ~4,375 LOC**

### Backtest Engine → `packages/rockit-core/src/rockit_core/engine/`

Source: `BookMapOrderFlowStudies/engine/`

| Current File | Class | LOC | Purpose |
|-------------|-------|-----|---------|
| `backtest.py` | `BacktestEngine` | ~800 | Bar-by-bar orchestrator: IB computation → day type → session context → signal → filter → execute |
| `execution.py` | `ExecutionModel` | ~120 | Slippage (1 tick/side), commission ($2.05/contract NQ), position sizing |
| `position.py` | `PositionManager`, `OpenPosition` | ~220 | Position tracking, trailing stops (BE, R-multiple, session extreme), daily loss limit |
| `trade.py` | `Trade` | ~80 | Completed trade dataclass with cost accounting |
| `equity.py` | `EquityCurve` | ~75 | Equity curve tracking, max drawdown |

**Total: 5 files, ~1,295 LOC**

### Filter Chain → `packages/rockit-core/src/rockit_core/filters/`

Source: `BookMapOrderFlowStudies/filters/`

| Current File | Class(es) | Purpose |
|-------------|----------|---------|
| `base.py` | `FilterBase` | Abstract base: `should_trade(signal, bar, session_context) -> bool` |
| `composite.py` | `CompositeFilter` | Chains multiple filters with AND logic |
| `order_flow_filter.py` | `DeltaFilter`, `CVDFilter`, `VolumeFilter` | Order flow thresholds |
| `regime_filter.py` | `RegimeFilter` | Market regime classification gates |
| `time_filter.py` | `TimeFilter` | Session time window restriction |
| `trend_filter.py` | `TrendFilter` | Trend alignment confirmation |
| `volatility_filter.py` | `VolatilityFilter` | ATR/volatility regime gates |

**Total: 7 files**

### Indicators → `packages/rockit-core/src/rockit_core/indicators/`

Source: `BookMapOrderFlowStudies/indicators/`

| Current File | Purpose | LOC |
|-------------|---------|-----|
| `technical.py` | EMA, VWAP, ATR, RSI computation | ~130 |
| `ict_models.py` | FVG, IFVG, BPR, MSS, CSS, OTE detection | ~380 |
| `smt_divergence.py` | Smart Money Theory divergence (NQ vs ES/YM) | ~310 |
| `ib_width.py` | Initial Balance width analysis | ~310 |
| `value_area.py` | Value area computation (70% rule) | ~350 |

**Total: 5 files, ~1,480 LOC**

### Market Profile → `packages/rockit-core/src/rockit_core/profile/`

Source: `BookMapOrderFlowStudies/profile/`

| Current File | Purpose |
|-------------|---------|
| `volume_profile.py` | POC, VAH, VAL, HVN/LVN computation |
| `tpo_profile.py` | TPO letters, profile shape, fattening zones |
| `dpoc_migration.py` | DPOC movement tracking through session |
| `ib_analysis.py` | IB-specific metrics and analysis |
| `confluences.py` | Level confluence detection |
| `wick_parade.py` | Wick parade (extreme rejection analysis) |

**Total: 6 files**

### Data Loading → `packages/rockit-core/src/rockit_core/data/`

Source: `BookMapOrderFlowStudies/data/`

| Current File | Purpose |
|-------------|---------|
| `loader.py` | CSV loader for NinjaTrader volumetric exports (OHLCV + vol_ask/bid/delta + indicators) |
| `features.py` | Feature engineering: OF features, IB features, day type, ICT features |
| `session.py` | Session grouping and date-based filtering utilities |

**Total: 3 files**

### Reporting → `packages/rockit-core/src/rockit_core/reporting/`

Source: `BookMapOrderFlowStudies/reporting/`

| Current File | Purpose |
|-------------|---------|
| `metrics.py` | Win rate, profit factor, expectancy, max drawdown, Sharpe ratio |
| `trade_log.py` | CSV/JSON export of trade log |
| `day_analyzer.py` | Per-session analysis |
| `comparison.py` | Cross-strategy comparison (by day type, setup type, time window) |

**Total: 4 files**

### Config → `packages/rockit-core/src/rockit_core/config/`

Source: `BookMapOrderFlowStudies/config/`

| Current File | Purpose |
|-------------|---------|
| `constants.py` (72 LOC) | Session times (RTH 9:30-16:00), IB params (60 bars), day type thresholds, risk defaults ($2K max daily loss, 30 max contracts) |
| `instruments.py` (42 LOC) | `InstrumentSpec` dataclass: NQ ($20/pt, $5/tick), MNQ ($2/pt), ES ($50/pt), MES ($5/pt), YM, MYM |

**Total: 2 files, 114 LOC**

---

## rockit-framework (standalone) → rockit-core deterministic

### Deterministic Modules → `packages/rockit-core/src/rockit_core/deterministic/`

Source: `rockit-framework/modules/` (38 modules, 9,293 LOC) + `rockit-framework/orchestrator.py` (359 LOC)

**Orchestrator:**
| Current File | Purpose |
|-------------|---------|
| `orchestrator.py` (359 LOC) | `generate_snapshot()` — calls all modules in dependency order, merges into single JSON |

**Core Data Modules:**
| Module | LOC | Purpose |
|--------|-----|---------|
| `loader.py` | 35 | CSV data loading (`load_nq_csv()`) |
| `premarket.py` | 104 | Asia/London/overnight ranges, compression flag, SMT preopen |
| `ib_location.py` | 96 | IB placement, price vs IB, technicals, ATR |
| `volume_profile.py` | 116 | POC/VAH/VAL/HVN/LVN (current + prior sessions) |
| `tpo_profile.py` | 166 | TPO shape, fattening zones, single prints, poor highs/lows |
| `dpoc_migration.py` | 167 | 30-min DPOC slices, migration direction/magnitude |
| `wick_parade.py` | 42 | Bullish/bearish wick counts in 60-min window |
| `fvg_detection.py` | 137 | Fair Value Gap detection (5/15/1H/90min/daily timeframes) |
| `ninety_min_pd_arrays.py` | 50 | 90-min premium/discount zones, expansion status |
| `core_confluences.py` | 146 | Boolean signal merge from all raw modules |
| `cross_market.py` | 0 | Stub — ES/YM cross-market (future) |
| `vix_regime.py` | 0 | Stub — VIX regime classification (future) |

**Signal Composition Modules:**
| Module | LOC | Purpose |
|--------|-----|---------|
| `inference_engine.py` | ~250 | 8 high-priority deterministic rules (day_type, bias, confidence) |
| `decision_engine.py` | ~250 | Day type classification rules (Trend/Balance/Open Drive) |
| `cri.py` | 412 | Contextual Readiness Index (terrain, identity, permission, trap detection) |
| `dalton.py` | 360 | Trend strength quantification (Weak/Moderate/Strong/Super) |

**Setup Generation Modules:**
| Module | LOC | Purpose |
|--------|-----|---------|
| `playbook_engine.py` | ~300 | 10 fundamental playbooks (setup generation) |
| `playbook_engine_v2.py` | ~300 | Enhanced playbook version |
| `balance_classification.py` | ~200 | Balance day specific analysis |
| `mean_reversion_engine.py` | ~200 | Mean reversion target generation |
| `or_reversal.py` | ~200 | Opening Range Reversal setup |
| `edge_fade.py` | ~200 | Edge Fade mean reversion (10:00-13:30) |
| `va_edge_fade.py` | 334 | VA Edge Fade (poke beyond VA, fail, fade) |
| `globex_va_analysis.py` | ~200 | 80% Rule (Globex gap rejection) |
| `twenty_percent_rule.py` | ~200 | 20% IB extension breakout |

**Training/Reasoning Modules:**
| Module | LOC | Purpose |
|--------|-----|---------|
| `enhanced_reasoning.py` | ~200 | 9-step reasoning chain for LLM training output |
| `cri_psychology_voice.py` | ~150 | Trader voice interpretation |
| `market_structure_events.py` | ~150 | Market structure event detection |
| `outcome_labeling.py` | ~150 | Training outcome labels |
| `intraday_sampling.py` | ~100 | Intraday sampling and smoothing |
| `setup_annotator.py` | ~100 | Annotation setup |

**Infrastructure Modules:**
| Module | LOC | Purpose |
|--------|-----|---------|
| `config_validator.py` | ~100 | Config validation |
| `schema_validator.py` | ~100 | Snapshot schema validation |
| `dataframe_cache.py` | ~100 | DataFrame caching (30% speedup documented) |
| `error_logger.py` | ~100 | Centralized error logging |
| `acceptance_test.py` | ~100 | Acceptance test harness |

**Total: 39 files (orchestrator + 38 modules), ~9,652 LOC**

---

## rockit-framework → rockit-train

### Training Scripts → `packages/rockit-train/`

Source: `rockit-framework/` (root-level scripts)

| Current File | New Location | Purpose |
|-------------|-------------|---------|
| `generate_training_data_with_synthetic_output.py` | `rockit_train/dataset.py` | Synthetic labels from snapshot features (no external LLM needed) |
| `generate_lora_training_data.py` | `rockit_train/trainer.py` | Full LoRA pipeline: snapshots → LLM → JSONL |
| `generate_training_data_90days.py` | Absorbed into dataset.py | 90-day batch generation |
| `train_lora_adapter.py` | `rockit_train/lora.py` | LoRA fine-tuning execution |
| `validate_training_data.py` | `rockit_train/validation.py` | Training data quality checks |
| `validate_session_integrity.py` | `rockit_train/validation.py` | Session integrity verification |
| `config/config.yaml` | `configs/training/base.yaml` | Training configuration |
| `config/schema.json` | `rockit_core/deterministic/schema.json` | Snapshot validation schema |

---

## rockit-framework → rockit-serve

### Live Inference → `packages/rockit-serve/`

Source: `rockit-framework/` (root-level scripts)

| Current File | New Location | Purpose |
|-------------|-------------|---------|
| `analyze-today.py` (500+ LOC) | `rockit_serve/inference/pipeline.py` | Refactored: no Google Drive download, receives data via API instead |
| `analyze-today-glm.py` | Absorbed into `llm.py` | GLM variant becomes a model config option |
| `analyze-today2.py` | Absorbed into `llm.py` | Alternative analyzer becomes a config option |

---

## RockitAPI → rockit-serve (absorbed)

Source: `RockitAPI/`

| Current File | New Location | Purpose |
|-------------|-------------|---------|
| `main.py` (306 LOC) | `rockit_serve/routes/journal.py` | Journal CRUD endpoints preserved |
| `auth.py` (155 LOC) | `rockit_serve/middleware/auth.py` | JWT authentication reused |
| `storage.py` (271 LOC) | `rockit_serve/storage.py` | GCS client with checksum verification reused |
| `models.py` (80 LOC) | `rockit_serve/models/` | Pydantic schemas extended |
| `config.py` (32 LOC) | `rockit_serve/config.py` | Settings management extended |
| `Dockerfile` | `rockit_serve/Dockerfile` | Updated for new app |
| `cloudbuild.yaml` | `infra/cloudbuild/deploy.yaml` | Updated deployment config |

---

## RockitDataFeed → GCS (data migration, not code)

Source: `RockitDataFeed/`

| Current Location | GCS Location | File Count |
|-----------------|-------------|------------|
| `local-analysis/*.jsonl` | `gs://rockit-data/training/local-analysis/` | 58 files (252 days) |
| `local-analysis-format/*.jsonl` | `gs://rockit-data/training/local-analysis-format/` | 4 files (2026) |
| `xai-analysis/*.jsonl` | `gs://rockit-data/training/xai-analysis/` | 43 files (Oct-Dec 2025) |

These are training data files, not code. They get uploaded to GCS and referenced by the training pipeline.

---

## NinjaTrader C# → DISCARD and Rebuild

Source: `BookMapOrderFlowStudies/` (root level)

| Current File | LOC | Action |
|-------------|-----|--------|
| `DualOrderFlow_Evaluation.cs` | 397 | **DISCARD** — standalone order flow strategy, zero overlap with Python |
| `DualOrderFlow_Funded.cs` | 526 | **DISCARD** — same, conservative variant |
| `output/ninjatrader/DaltonPlaybookStrategy.cs` | ~200 | **DISCARD** — was auto-generated from Python |
| `export/ninjatrader.py` | ~100 | **DISCARD** — C# code generator no longer needed |

**New files (built from scratch):**
| New File | LOC | Purpose |
|----------|-----|---------|
| `RockitIndicator.cs` | ~150 | HTTP client → draws zones/levels/signals from API annotation JSON |
| `RockitStrategy.cs` | ~150 | HTTP client → fills trades from API setups, manages stops/trails locally |

---

## TradingView → NEW (nothing exists today)

| New File | LOC | Purpose |
|----------|-----|---------|
| `rockit_indicator.pine` | ~100 | Webhook-driven annotation display on TradingView charts |

---

## RockitUI → NEW (only a spec exists)

Source: `RockitUI/prompt/project-design.md` (spec document only)

| New Location | Purpose |
|-------------|---------|
| `packages/rockit-clients/dashboard/` | React dashboard consuming annotation API |

---

## Research/Diagnostic Scripts → Archive

Source: `BookMapOrderFlowStudies/` (root level, ~72 files)

These scripts served their research purpose. They are not migrated to the monorepo but can be referenced from the archived repo:

| Category | Count | Examples |
|----------|-------|---------|
| `study_*.py` | 23 | `study_balance_day_edge_fade.py`, `study_mfe.py`, `study_va_breakout_continuation.py` |
| `diagnostic_*.py` | 34 | `diagnostic_bday_quality.py`, `diagnostic_deep_orderflow.py`, `diagnostic_trade_quality.py` |
| `analyze_*.py` | 15 | `analyze_70wr_optimal.py`, `analyze_gap_fill_80p.py`, `analyze_regime_directional.py` |

---

## Deduplication Wins

Code that exists in multiple places today and will exist once in the monorepo:

| Duplicated Logic | Location 1 | Location 2 | Location 3 | Single Location |
|-----------------|-----------|-----------|-----------|----------------|
| Volume Profile | BookMap `profile/volume_profile.py` | Framework `modules/volume_profile.py` | — | `rockit-core/profile/volume_profile.py` (shared by engine + orchestrator) |
| TPO Profile | BookMap `profile/tpo_profile.py` | Framework `modules/tpo_profile.py` | — | `rockit-core/profile/tpo_profile.py` |
| FVG Detection | BookMap `indicators/ict_models.py` | Framework `modules/fvg_detection.py` | — | `rockit-core/indicators/ict_models.py` |
| IB Analysis | BookMap `data/features.py` + `profile/ib_analysis.py` | Framework `modules/ib_location.py` | C# inline | `rockit-core/profile/ib_analysis.py` |
| DPOC Migration | BookMap `profile/dpoc_migration.py` | Framework `modules/dpoc_migration.py` | — | `rockit-core/profile/dpoc_migration.py` |
| Wick Parade | BookMap `profile/wick_parade.py` | Framework `modules/wick_parade.py` | — | `rockit-core/profile/wick_parade.py` |
| Day Type | BookMap `strategy/day_type.py` | Framework `modules/decision_engine.py` | C# inline | `rockit-core/strategies/day_type.py` |
| Delta/CVD | BookMap `data/features.py` | — | C# `CalculateOrderFlowFeatures()` | `rockit-core/data/features.py` |

**Total: 8 deduplication wins.** Each removes a source of "backtest doesn't match live" or "framework output differs from backtest" bugs.

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Files moving to `rockit-core` | ~92 (strategies + engine + filters + indicators + profile + data + config + reporting + deterministic) |
| Files moving to `rockit-train` | ~8 (training scripts + configs) |
| Files absorbed into `rockit-serve` | ~7 (RockitAPI) + 3 (analyze-today variants) |
| Files discarded (C#) | 4 (replaced by ~2 new thin client files) |
| Files archived (research scripts) | ~72 (stay in old repo) |
| Data files migrated to GCS | ~105 JSONL files |
| Net-new code needed | Signals API, Dashboard, Pine Script, thin NinjaTrader client |
