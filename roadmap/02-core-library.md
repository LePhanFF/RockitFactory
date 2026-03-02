# Phase 1: Core Library — Detailed Roadmap

> **Goal:** Migrate all strategy, engine, filter, indicator, profile, and deterministic code into `rockit-core`.
> **Duration:** Week 2-5
> **Depends on:** Phase 0
> **Blocks:** Phases 2, 3, 4, 5

---

## Tasks

### 1.1 Reconcile two rockit-framework copies
- [ ] Diff standalone rockit-framework (38 modules) vs BookMapOrderFlowStudies copy (12 modules)
- [ ] Identify any unique logic in the older copy that's missing from standalone
- [ ] Merge any unique logic into the standalone version
- [ ] Document reconciliation decisions

**Acceptance:** Single canonical set of deterministic modules, zero ambiguity about which version is used.

### 1.2 Migrate strategies (20 files)
- [ ] Move `BookMapOrderFlowStudies/strategy/` → `rockit-core/strategies/`
- [ ] Includes: base.py, signal.py, day_type.py, day_confidence.py, 16 strategy files
- [ ] Update imports to use new package structure
- [ ] Add metrics emission to StrategyBase.evaluate()
- [ ] Write unit tests for each strategy against known inputs

**Acceptance:** All 16 strategies import and instantiate. Unit tests pass.

### 1.3 Migrate engine (5 files)
- [ ] Move `BookMapOrderFlowStudies/engine/` → `rockit-core/engine/`
- [ ] Includes: backtest.py, execution.py, position.py, trade.py, equity.py
- [ ] Update imports
- [ ] Add metrics emission for trade outcomes

**Acceptance:** `UnifiedBacktestEngine` runs without errors.

### 1.4 Migrate filters (7 files)
- [ ] Move `BookMapOrderFlowStudies/filters/` → `rockit-core/filters/`
- [ ] Add metrics emission for filter pass/block decisions
- [ ] Unit tests for each filter type

**Acceptance:** `CompositeFilter.default()` chains all filters correctly.

### 1.5 Migrate indicators (5 files)
- [ ] Move `BookMapOrderFlowStudies/indicators/` → `rockit-core/indicators/`
- [ ] Add metrics emission for indicator calculations

### 1.6 Migrate profile (6 files)
- [ ] Move `BookMapOrderFlowStudies/profile/` → `rockit-core/profile/`
- [ ] Add metrics emission

### 1.7 Migrate data + config + reporting (9 files)
- [ ] Move `BookMapOrderFlowStudies/data/` → `rockit-core/data/`
- [ ] Move `BookMapOrderFlowStudies/config/` → `rockit-core/config/`
- [ ] Move `BookMapOrderFlowStudies/reporting/` → `rockit-core/reporting/`

### 1.8 Migrate deterministic modules (38 modules + orchestrator)
- [ ] Move `rockit-framework/orchestrator.py` → `rockit-core/deterministic/orchestrator.py`
- [ ] Move `rockit-framework/modules/` → `rockit-core/deterministic/modules/`
- [ ] Move `rockit-framework/config/schema.json` → `rockit-core/deterministic/schema.json`
- [ ] Deduplicate shared modules (volume_profile, tpo_profile, fvg_detection, ib)
- [ ] Ensure both backtest engine and orchestrator use same indicator/profile code

**Acceptance:** `orchestrator.generate_snapshot()` works with shared modules.

### 1.9 Implement entry/stop/target model registry
- [ ] Implement concrete entry models from FAQ Q5 (unicorn_ict, orderflow_cvd, smt_divergence, liquidity_sweep, tpo_rejection, three_drive, double_top, trendline, trendline_backside, tick_divergence, bpr)
- [ ] Implement concrete stop models (1_atr, 2_atr, lvn_hvn, ifvg)
- [ ] Implement concrete target models (1_atr, 2_atr, 2r, 3r, 4h_gap_fill, 1h_gap_fill, time_based_liquidity, trail_be_fvg, trail_be_bpr)
- [ ] Wire into strategy YAML config loader
- [ ] Unit tests for each model

**Acceptance:** Strategies can compose entry/stop/target models via YAML config.

### 1.10 Full backtest validation
- [ ] Run 259-session backtest through new `rockit-core`
- [ ] Compare results to original BookMapOrderFlowStudies output
- [ ] Run deterministic orchestrator over test sessions
- [ ] Compare snapshots to original rockit-framework output

**Acceptance:** Zero diff on backtest results. Zero diff on deterministic snapshots.

---

## File Count Summary

| Component | Files | Source |
|-----------|-------|--------|
| Strategies | 20 | BookMapOrderFlowStudies/strategy/ |
| Engine | 5 | BookMapOrderFlowStudies/engine/ |
| Filters | 7 | BookMapOrderFlowStudies/filters/ |
| Indicators | 5 | BookMapOrderFlowStudies/indicators/ |
| Profile | 6 | BookMapOrderFlowStudies/profile/ |
| Data | 3 | BookMapOrderFlowStudies/data/ |
| Config | 2 | BookMapOrderFlowStudies/config/ |
| Reporting | 4 | BookMapOrderFlowStudies/reporting/ |
| Deterministic modules | 38 | rockit-framework/modules/ |
| Orchestrator + schema | 2 | rockit-framework/ |
| Entry/Stop/Target models | ~25 | New code |
| **Total** | **~117 files** | |

---

## Definition of Done

- [ ] All ~92 files migrated from source repos
- [ ] ~25 entry/stop/target model files created
- [ ] `make backtest STRATEGY=all` matches original output
- [ ] `make snapshot SESSION=2025-10-15` matches original output
- [ ] Unit test coverage ≥ 90% for rockit-core
- [ ] No imports from old repo paths remain
- [ ] Metrics emitted at strategy, filter, and indicator levels
