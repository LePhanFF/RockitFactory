# Detailed Code Mapping: Current Repos → Monorepo

This document maps every significant module from the existing repositories to its
new home in the RockitFactory monorepo. Based on deep analysis of the actual codebase.

---

## BookMapOrderFlowStudies → rockit-core + rockit-pipeline

### Strategy Logic → `packages/rockit-core/src/rockit_core/strategies/`

The existing repo has 16 strategies inheriting from `StrategyBase`. All move to core:

| Current File | New File | Strategy |
|-------------|----------|----------|
| `strategy/base.py` | `strategies/base.py` | `StrategyBase` — "strategies emit signals, never manage positions" |
| `strategy/signal.py` | `strategies/signal.py` | `Signal` dataclass (timestamp, direction, entry/stop/target, confidence, metadata) |
| `strategy/day_type.py` | `strategies/day_type.py` | Dalton day type classification (SUPER_TREND, TREND, P_DAY, B_DAY, NEUTRAL) |
| `strategy/day_confidence.py` | `strategies/day_confidence.py` | `DayTypeConfidenceScorer` — real-time probability estimates |
| `strategy/__init__.py` | `strategies/__init__.py` | Registry + `CORE_STRATEGIES` portfolio definition |
| `strategy/trend_bull.py` | `strategies/trend_bull.py` | `TrendDayBull` — VWAP pullback, IBH acceptance, OF quality gates |
| `strategy/trend_bear.py` | `strategies/trend_bear.py` | `TrendDayBear` — mirror of bull |
| `strategy/super_trend_bull.py` | `strategies/super_trend_bull.py` | `SuperTrendBull` — >2x IB extension |
| `strategy/super_trend_bear.py` | `strategies/super_trend_bear.py` | `SuperTrendBear` — mirror |
| `strategy/p_day.py` | `strategies/p_day.py` | `PDayStrategy` — skewed balance, 0.5–1.0x extension |
| `strategy/b_day.py` | `strategies/b_day.py` | `BDayStrategy` — IBL fade on narrow days |
| `strategy/neutral_day.py` | `strategies/neutral_day.py` | `NeutralDayStrategy` — range trading |
| `strategy/pm_morph.py` | `strategies/pm_morph.py` | `PMMorphStrategy` — PM session morphs |
| `strategy/morph_to_trend.py` | `strategies/morph_to_trend.py` | `MorphToTrendStrategy` — intra-session morph detection |
| `strategy/edge_fade.py` | `strategies/edge_fade.py` | `EdgeFadeStrategy` — mean reversion from lower IB edge, 58.1% WR, PF 1.75 |
| `strategy/bear_accept.py` | `strategies/bear_accept.py` | `BearAcceptShort` — acceptance below IBL |
| `strategy/ibh_sweep.py` | `strategies/ibh_sweep.py` | `IBHSweepFail` — fade failed IBH breakouts |
| `strategy/or_reversal.py` | `strategies/or_reversal.py` | `OpeningRangeReversal` — ICT Judas Swing, 80% WR in 62 sessions |
| `strategy/or_acceptance.py` | `strategies/or_acceptance.py` | `ORAcceptanceStrategy` — OR acceptance continuation |
| `strategy/ib_retest.py` | `strategies/ib_retest.py` | `IBRetestStrategy` — IB level retest entries |
| `strategy/balance_signal.py` | `strategies/balance_signal.py` | `BalanceSignal` — balance/consolidation detection |
| `strategy/eighty_percent_rule.py` | `strategies/eighty_percent_rule.py` | 80% Rule — VA mean reversion (v1/v2/v3 research) |

### Filter Chain → `packages/rockit-core/src/rockit_core/filters/`

| Current File | New File | Purpose |
|-------------|----------|---------|
| `filters/composite.py` | `filters/composite.py` | `CompositeFilter` — chains all filters, signal must pass ALL |
| `filters/order_flow_filter.py` | `filters/order_flow.py` | Delta, CVD, imbalance thresholds |
| `filters/strategy_regime_filter.py` | `filters/regime.py` | Regime-specific gates |
| `filters/time_filter.py` | `filters/time.py` | Session time windows |
| `filters/trend_filter.py` | `filters/trend.py` | Trend alignment |
| `filters/volatility_filter.py` | `filters/volatility.py` | Volatility regime gates |

### Data Models & Features → `packages/rockit-core/src/rockit_core/data/`

| Current File | New File | Purpose |
|-------------|----------|---------|
| `data/loader.py` | `data/loader.py` | CSV loader for NinjaTrader volumetric exports (OHLCV + vol_ask/bid/delta + indicators) |
| `data/features.py` | `data/features.py` | Feature engineering: `compute_order_flow_features()`, `compute_ib_features()`, `compute_day_type()`, `add_ict_features()` |
| `data/session.py` | `data/session.py` | Session grouping utilities |
| `indicators/ict_models.py` | `indicators/ict.py` | FVG, IFVG, BPR detection |
| `profile/volume_profile.py` | `indicators/volume_profile.py` | Volume profile computation |
| `profile/tpo_profile.py` | `indicators/tpo.py` | TPO market profile |

### Configuration → `configs/`

| Current File | New File | Purpose |
|-------------|----------|---------|
| `config/constants.py` | `configs/constants.yaml` | Session times, thresholds, risk defaults ($150K account, $4K max DD, $400 risk/trade) |
| `config/instruments.py` | `configs/instruments.yaml` | NQ ($20/pt), MNQ ($2/pt), ES ($50/pt), MES ($5/pt), YM, MYM with tick sizes and commissions |

### Backtest Engine → `packages/rockit-pipeline/src/rockit_pipeline/backtest/`

| Current File | New File | Purpose |
|-------------|----------|---------|
| `engine/backtest.py` | `backtest/engine.py` | Unified bar-by-bar backtest (IB computation → day type → session context → signal → filter → execute) |
| `engine/execution.py` | `backtest/execution.py` | Slippage (1 tick/side), commission ($2.05/contract NQ), position sizing |
| `engine/position.py` | `backtest/position.py` | Open position tracking, trailing stops (BE activation, R-multiple, session extreme), risk limits |
| `engine/trade.py` | `backtest/trade.py` | Completed trade dataclass with full cost accounting |
| `engine/equity.py` | `backtest/equity.py` | Equity curve tracking |
| `reporting/metrics.py` | `evaluation/metrics.py` | Win rate, profit factor, expectancy, drawdown, Sharpe |
| `reporting/trade_log.py` | `evaluation/trade_log.py` | CSV export of trade log |

### Prop Firm Pipeline → `packages/rockit-pipeline/src/rockit_pipeline/prop/`

| Current File | New File | Purpose |
|-------------|----------|---------|
| `prop/pipeline.py` | `prop/pipeline.py` | `PropPipeline` — multi-account simulation (eval → funded → scale to 5 accounts) |
| `prop/account.py` | `prop/account.py` | `PropAccount` — evaluation/funded lifecycle |
| `prop/sizer.py` | `prop/sizer.py` | `PropSizer` — setup-grade-based position sizing |
| `prop/rules.py` | `prop/rules.py` | Prop firm rules (eval targets, max drawdown) |

### Diagnostics → `packages/rockit-pipeline/src/rockit_pipeline/diagnostics/`

| Current | New | Purpose |
|---------|-----|---------|
| `diagnostics/` (20+ scripts) | `diagnostics/` | Trade quality, entry models, OF analysis, day type validation |
| `scripts/` | `scripts/` | Backtest runners, diagnostic scripts, analysis tools |

---

## BookMapOrderFlowStudies (NinjaTrader) → rockit-clients

### Current NinjaTrader Code (Complex — 500+ lines each)

| Current File | What It Does |
|-------------|-------------|
| `DualOrderFlow_Evaluation.cs` | Full strategy logic in C#: OF feature computation, percentile calculation, signal generation, position management. 31 contracts, $1500 daily loss, 10:00-13:00 ET. |
| `DualOrderFlow_Funded.cs` | Same + 5-minute HTF filter layer. 20 contracts, $800 daily loss. Multi-timeframe CVD alignment + VWAP context. |
| `export/ninjatrader.py` | Python code generator that auto-generates C# from backtest params |

### New NinjaTrader Code (Thin — ~200 lines each)

| New File | What It Does |
|----------|-------------|
| `RockitIndicator.cs` | HTTP client → draws zones/levels/signals from API annotation JSON. No strategy logic. |
| `RockitStrategy.cs` | HTTP client → reads trade setups from API → places orders at specified prices. No strategy logic. |

**What gets eliminated:** All C# implementations of delta/CVD/imbalance computation, percentile calculation, day type classification, signal logic. All of this runs server-side in Python.

---

## rockit-framework → rockit-pipeline (deterministic) + rockit-train

### Orchestrator / Snapshot Generation → `packages/rockit-pipeline/src/rockit_pipeline/deterministic/`

| Current Module | New Location | Purpose |
|---------------|-------------|---------|
| `orchestrator.py` | `deterministic/orchestrator.py` | `generate_snapshot()` — orchestrates all modules |
| `modules/loader.py` | Reuse `rockit_core/data/loader.py` | Already in core |
| `modules/premarket.py` | `deterministic/modules/premarket.py` | London/Asia/overnight levels |
| `modules/ib_location.py` | Reuse `rockit_core/data/features.py` | IB computation already in core |
| `modules/wick_parade.py` | `deterministic/modules/wick_parade.py` | Candle wick analysis |
| `modules/dpoc_migration.py` | `deterministic/modules/dpoc_migration.py` | DPOC migration tracking |
| `modules/volume_profile.py` | Reuse `rockit_core/indicators/volume_profile.py` | Already in core |
| `modules/tpo_profile.py` | Reuse `rockit_core/indicators/tpo.py` | Already in core |
| `modules/ninety_min_pd_arrays.py` | `deterministic/modules/pd_arrays.py` | 90-min price discovery arrays |
| `modules/fvg_detection.py` | Reuse `rockit_core/indicators/ict.py` | FVG detection already in core |
| `modules/core_confluences.py` | `deterministic/modules/confluences.py` | Pre-computed confluence signals |
| `modules/cross_market.py` | `deterministic/modules/cross_market.py` | SMT divergence (ES/YM vs NQ) |
| `modules/vix_regime.py` | `deterministic/modules/vix_regime.py` | VIX regime classification |

**Key benefit:** Several modules (IB, volume profile, TPO, FVG) are duplicated between BookMapOrderFlowStudies and rockit-framework today. In the monorepo, they exist once in `rockit-core` and are shared.

### Training Code → `packages/rockit-train/`

Training code from rockit-framework moves to `rockit-train` with MLOps automation layered on top (see [03-pipeline-mlops.md](03-pipeline-mlops.md)).

---

## TradingView → rockit-clients

| Current File | New File | Change |
|-------------|----------|--------|
| `tradingview/OR_Reversal_Indicator.pine` | `rockit-clients/tradingview/or_reversal.pine` | Rewrite as API consumer (fetch annotation JSON, draw) |
| `tradingview/Edge_Fade_Indicator.pine` | `rockit-clients/tradingview/edge_fade.pine` | Rewrite as API consumer |

---

## RockitAPI → rockit-serve

Existing API endpoints port into the FastAPI application at `packages/rockit-serve/`. The new API adds the annotation protocol layer on top (see [04-platform-abstraction.md](04-platform-abstraction.md)).

---

## RockitUI → rockit-clients/dashboard

The existing dashboard UI moves into `packages/rockit-clients/dashboard/` with the same tech stack. It now consumes the annotation protocol JSON from rockit-serve.

---

## Deduplication Wins

Code that exists in multiple places today and will exist once in the monorepo:

| Duplicated Logic | Current Locations | Single Location |
|-----------------|-------------------|-----------------|
| IB computation | BookMap `data/features.py` + Framework `modules/ib_location.py` + NinjaTrader C# | `rockit-core/data/features.py` |
| Volume profile | BookMap `profile/volume_profile.py` + Framework `modules/volume_profile.py` | `rockit-core/indicators/volume_profile.py` |
| TPO profile | BookMap `profile/tpo_profile.py` + Framework `modules/tpo_profile.py` | `rockit-core/indicators/tpo.py` |
| FVG detection | BookMap `indicators/ict_models.py` + Framework `modules/fvg_detection.py` | `rockit-core/indicators/ict.py` |
| Day type classification | BookMap `strategy/day_type.py` + NinjaTrader C# inline | `rockit-core/strategies/day_type.py` |
| Delta/CVD computation | BookMap `data/features.py` + NinjaTrader C# `CalculateOrderFlowFeatures()` | `rockit-core/data/features.py` |
| Signal logic | BookMap Python strategies + NinjaTrader C# `CheckEntrySignals()` | `rockit-core/strategies/*.py` |

**Total: 7 major deduplication wins.** Each of these is a source of "backtest doesn't match NinjaTrader" bugs today.
