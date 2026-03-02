# Phase 1a: Proven Strategies — Detailed Roadmap

> **Goal:** Migrate the proven profitable strategies first, with the backtest engine and minimum
> supporting infrastructure needed to validate them. Get these running and backtested before
> migrating the full codebase.
> **Duration:** Week 2-4
> **Depends on:** Phase 0 (Foundation)
> **Blocks:** Phase 1b (remaining core library)
> **Source:** [brainstorm/03-migration.md](../brainstorm/03-migration.md),
> [research/strategy-studies/](https://github.com/LePhanFF/BookMapOrderFlowStudies/tree/claude/research-evaluation-strategies-QcnQK/research/strategy-studies)

---

## Why This Phase Exists

The strategy-studies research identified 5 strategy families with the strongest edge and
most backtesting evidence. Rather than migrating all 16 strategies + 38 deterministic
modules + entry/stop/target models at once, we lift the **proven profitable strategies first**
and validate them in the new monorepo. This gives us:

1. A working backtest engine early (validates the entire pipeline)
2. Confidence that the most important strategies survived migration intact
3. A foundation to build the signals API and training pipeline against
4. Faster time to value — these are the strategies that actually trade

---

## The 5 Proven Strategy Families

From the strategy-studies research and existing backtest results (259 sessions, 283 trades,
55.5% WR, 1.58 PF), these are the strategies to migrate first:

| Strategy Family | Source Files | Description | Existing Code |
|----------------|-------------|-------------|---------------|
| **20% Rule** (Trend Breakout) | `eighty_percent_rule.py`, `trend_bull.py`, `super_trend_bull.py` | Trend program breaking out of previous session VA range. When price breaks above VAH/below VAL and holds, trade continuation. | Yes — implemented and backtested |
| **80% Rule** (Mean Reversion) | `mean_reversion_vwap.py`, `eighty_percent_rule.py` | Mean reversion into value — when price extends beyond VA, fade back to POC/mid/opposite VA edge. | Yes — implemented and backtested |
| **Balance Day** | `b_day.py` | Rotational day within prior VA. Trade edges (VAH/VAL fades), IB fades, mean reversion. EdgeFade is the primary signal. | Yes — implemented and backtested |
| **Opening Reversal** | `orb_enhanced.py`, `orb_vwap_breakout.py` | Failed opening range breakout → reversal. Also covers successful ORB continuation. 5 variations documented in strategy-studies. | Yes — implemented and backtested |
| **Opening Acceptance** | `p_day.py`, `trend_bull.py`, `trend_bear.py` | IB acceptance: when price breaks and holds above IBH or below IBL, trade the continuation. P-Day and Trend patterns. | Yes — implemented and backtested |

### What This Maps To in `CORE_STRATEGIES`

These 5 families cover **all 8 core strategies**: `trend_bull`, `p_day`, `b_day`, `edge_fade`,
`ibh_sweep`, `bear_accept`, `or_reversal`, `ib_retest`.

---

## Tasks

### 1a.1 Migrate backtest engine (5 files) — FIRST

The engine is the prerequisite for everything. Without it, we can't validate anything.

- [ ] Move `BookMapOrderFlowStudies/engine/` → `packages/rockit-core/src/rockit_core/engine/`
  - `backtest.py`, `execution.py`, `position.py`, `trade.py`, `equity.py`
- [ ] Update imports to new package structure
- [ ] Add `MetricsCollector` parameter (optional, NullCollector default)
- [ ] Write smoke test: engine instantiates and runs on empty session list

**Acceptance:** `UnifiedBacktestEngine` imports and instantiates from `rockit_core.engine`.

### 1a.2 Migrate strategy foundation (4 files)

- [ ] Move `strategy/base.py` → `strategies/base.py` (StrategyBase)
- [ ] Move `strategy/signal.py` → `strategies/signal.py` (Signal dataclass)
- [ ] Move `strategy/day_type.py` → `strategies/day_type.py` (DayType enum)
- [ ] Move `strategy/day_confidence.py` → `strategies/day_confidence.py` (DayTypeConfidenceScorer)
- [ ] Write contract tests for StrategyBase

**Acceptance:** `StrategyBase`, `Signal`, `DayType`, `DayTypeConfidence` all import correctly.

### 1a.3 Migrate proven strategy files (9 files)

- [ ] `trend_bull.py` — 20% rule / opening acceptance (trend continuation)
- [ ] `trend_bear.py` — Opening acceptance (bearish)
- [ ] `super_trend_bull.py` — Strong 20% rule breakout
- [ ] `super_trend_bear.py` — Strong bearish breakout
- [ ] `p_day.py` — Opening acceptance (P-Day pattern)
- [ ] `b_day.py` — Balance day rotational trades
- [ ] `eighty_percent_rule.py` — 80%/20% rule (reversion + breakout)
- [ ] `mean_reversion_vwap.py` — Mean reversion to VWAP
- [ ] `orb_enhanced.py` — Opening reversal + ORB continuation (581 LOC, largest strategy)
- [ ] Update imports, add metrics parameter
- [ ] Write unit tests for each (signal conditions, no-signal conditions, edge cases)

**Acceptance:** All 9 strategies instantiate, return correct Signal objects for known inputs.

### 1a.4 Migrate minimum supporting code

These strategies need filters, indicators, and profile code to function.

**Filters (7 files):**
- [ ] Move `filters/` → `packages/rockit-core/src/rockit_core/filters/`
  - `base.py`, `composite.py`, `order_flow_filter.py`, `regime_filter.py`,
    `time_filter.py`, `trend_filter.py`, `volatility_filter.py`
- [ ] Write unit tests for CompositeFilter chain

**Indicators (minimum needed):**
- [ ] Move indicator files that the 9 strategies actually import
- [ ] Skip indicators only used by non-priority strategies (can migrate in 1b)

**Profile (minimum needed):**
- [ ] Move profile files that the engine and strategies actually import
- [ ] Volume profile, TPO at minimum (used by b_day, eighty_percent_rule)

**Data + Config:**
- [ ] Move `data/loader.py`, `data/features.py`, `data/session.py`
- [ ] Move `config/constants.py`, `config/instruments.py`

**Acceptance:** The strategy → filter → engine pipeline runs without missing imports.

### 1a.5 Add YAML config for proven strategies

- [ ] Create `configs/strategies.yaml` with entries for all 9 strategies
- [ ] All set to `enabled: true`
- [ ] Implement `load_strategies_from_config()` (basic version — full entry/stop/target model registry is Phase 1b)
- [ ] Create `CORE_STRATEGIES` list

**Acceptance:** `load_strategies_from_config("configs/strategies.yaml")` returns 9 strategy instances.

### 1a.6 Backtest validation — CRITICAL GATE

This is the main deliverable. Run the proven strategies through the migrated engine and
validate results.

- [ ] Run backtest with the 9 proven strategies over the full 259-session dataset
- [ ] Compare trade-by-trade output against original BookMapOrderFlowStudies results
- [ ] Verify: same number of trades, same signals, same outcomes
- [ ] Document per-strategy metrics:

  | Strategy | Trades | WR | PF | Max DD |
  |----------|--------|----|----|--------|
  | TrendBull | | | | |
  | PDay | | | | |
  | BDay | | | | |
  | EightyPercentRule | | | | |
  | MeanReversionVWAP | | | | |
  | ORBEnhanced | | | | |
  | TrendBear | | | | |
  | SuperTrendBull | | | | |
  | SuperTrendBear | | | | |

- [ ] Establish initial baseline (`configs/baselines/v0.1.0.json`) from these results
- [ ] Compare against strategy-studies projections (are the hypotheses validated?)

**Acceptance:** Backtest results match original output. Baseline v0.1.0 committed.

### 1a.7 Run strategy-studies backtests (NEW — fills research gap)

The strategy-studies documented entry/exit rules but **no backtests were actually run**.
Now that the engine is migrated, run them:

- [ ] Backtest the 5 variations of ORB from the study (classic, pullback, VWAP filter, prior day filter, failed fade)
- [ ] Backtest 20% rule in isolation (breakout from VA range)
- [ ] Backtest 80% rule in isolation (mean reversion into VA)
- [ ] Backtest balance day edge fades
- [ ] Backtest opening acceptance (IB acceptance → continuation)
- [ ] Document actual results vs projected results from strategy-studies
- [ ] Identify which variations are worth keeping vs discarding

**Acceptance:** Strategy-studies hypotheses validated or invalidated with real data.

---

## What Is NOT in This Phase

Deferred to Phase 1b:
- Remaining 7 strategies (`neutral_day`, `pm_morph`, `morph_to_trend`, `orb_vwap_breakout`,
  `ema_trend_follow`, `liquidity_sweep` — note: `orb_vwap_breakout` may pull forward if ORB validation needs it)
- Deterministic modules (38 modules + orchestrator) — these are for the LLM pipeline, not trading
- Entry/stop/target model registry (composable trade models)
- Reconciliation of two rockit-framework copies
- Full snapshot generation validation

---

## File Count Summary

| Component | Files | Source |
|-----------|-------|--------|
| Engine | 5 | BookMapOrderFlowStudies/engine/ |
| Strategy foundation | 4 | BookMapOrderFlowStudies/strategy/ (base, signal, day_type, day_confidence) |
| Proven strategies | 9 | BookMapOrderFlowStudies/strategy/ |
| Filters | 7 | BookMapOrderFlowStudies/filters/ |
| Indicators | ~3-5 | BookMapOrderFlowStudies/indicators/ (subset) |
| Profile | ~3-4 | BookMapOrderFlowStudies/profile/ (subset) |
| Data + Config | 5 | BookMapOrderFlowStudies/data/ + config/ |
| **Total** | **~36-39 files** | |

This is roughly 1/3 of the full Phase 1 scope, focused on the code that matters most.

---

## Definition of Done

- [ ] Backtest engine runs end-to-end in the new monorepo
- [ ] All 9 proven strategies produce correct signals
- [ ] Filter chain works with all 9 strategies
- [ ] 259-session backtest results match original (for the 9 strategies)
- [ ] Baseline v0.1.0 committed with per-strategy metrics
- [ ] Strategy-studies hypotheses validated with actual backtest data
- [ ] Unit test coverage ≥ 90% for migrated code
- [ ] `make backtest` works from repo root
