# Phase 1b: Full Core Library — Detailed Roadmap

> **Goal:** Migrate remaining strategies, deterministic modules, and build the entry/stop/target
> model registry. Complete the full `rockit-core` package.
> **Duration:** Week 4-6
> **Depends on:** Phase 1a (Proven Strategies)
> **Blocks:** Phases 2, 3, 4, 5

---

## Context

Phase 1a migrated the **9 proven strategies**, the backtest engine, filters, and minimum
supporting code. This phase completes the picture:

- Remaining 7 strategies (research/experimental)
- All 38 deterministic modules + orchestrator (needed for LLM pipeline)
- Entry/stop/target model registry (composable trade models)
- Reporting module
- Full reconciliation of the two rockit-framework copies

---

## Tasks

### 1b.1 Reconcile two rockit-framework copies

- [ ] Diff standalone rockit-framework (38 modules) vs BookMapOrderFlowStudies copy (12 modules)
- [ ] Identify any unique logic in the older copy that's missing from standalone
- [ ] Merge any unique logic into the standalone version
- [ ] Document reconciliation decisions

**Acceptance:** Single canonical set of deterministic modules, zero ambiguity about which version is used.

### 1b.2 Migrate remaining strategies (7 files)

These are research/experimental strategies not in the proven core portfolio:

- [ ] `neutral_day.py` (~20 LOC, pass-through)
- [ ] `pm_morph.py` (~130 LOC)
- [ ] `morph_to_trend.py` (~100 LOC)
- [ ] `orb_vwap_breakout.py` (~200 LOC)
- [ ] `ema_trend_follow.py` (~150 LOC)
- [ ] `liquidity_sweep.py` (~180 LOC)
- [ ] Update `ALL_STRATEGIES` registry to include all 16
- [ ] Write unit tests for each

**Acceptance:** All 16 strategies import and instantiate. Unit tests pass.

### 1b.3 Complete indicator and profile migration

Phase 1a migrated only what the proven strategies needed. Complete the rest:

- [ ] Move remaining indicator files (any not already migrated)
- [ ] Move remaining profile files (any not already migrated)
- [ ] Add metrics emission for indicator and profile calculations
- [ ] Ensure shared code between engine and orchestrator uses same modules

**Acceptance:** All indicator and profile code migrated with no duplication.

### 1b.4 Migrate deterministic modules (38 modules + orchestrator)

- [ ] Move `rockit-framework/orchestrator.py` → `rockit-core/deterministic/orchestrator.py`
- [ ] Move `rockit-framework/modules/` → `rockit-core/deterministic/modules/`
- [ ] Move `rockit-framework/config/schema.json` → `rockit-core/deterministic/schema.json`
- [ ] Deduplicate shared modules (volume_profile, tpo_profile, fvg_detection, ib)
- [ ] Ensure both backtest engine and orchestrator use same indicator/profile code

**Acceptance:** `orchestrator.generate_snapshot()` works with shared modules.

### 1b.5 Migrate reporting (4 files)

- [ ] Move `BookMapOrderFlowStudies/reporting/` → `rockit-core/reporting/`

### 1b.6 Implement entry/stop/target model registry

- [ ] Implement concrete entry models (unicorn_ict, orderflow_cvd, smt_divergence, liquidity_sweep, tpo_rejection, three_drive, double_top, trendline, trendline_backside, tick_divergence, bpr)
- [ ] Implement concrete stop models (1_atr, 2_atr, lvn_hvn, ifvg)
- [ ] Implement concrete target models (1_atr, 2_atr, 2r, 3r, 4h_gap_fill, 1h_gap_fill, time_based_liquidity, trail_be_fvg, trail_be_bpr)
- [ ] Wire into strategy YAML config loader
- [ ] Unit tests for each model

**Acceptance:** Strategies can compose entry/stop/target models via YAML config.

### 1b.7 Full backtest validation

- [ ] Run 259-session backtest with ALL 16 strategies through new `rockit-core`
- [ ] Compare results to original BookMapOrderFlowStudies output
- [ ] Run deterministic orchestrator over test sessions
- [ ] Compare snapshots to original rockit-framework output
- [ ] Update baseline from v0.1.0 to v1.0.0 with full-portfolio metrics

**Acceptance:** Zero diff on backtest results. Zero diff on deterministic snapshots. Baseline v1.0.0 committed.

---

## File Count Summary (Remaining After Phase 1a)

| Component | Files | Source |
|-----------|-------|--------|
| Remaining strategies | 7 | BookMapOrderFlowStudies/strategy/ |
| Remaining indicators | ~2 | BookMapOrderFlowStudies/indicators/ |
| Remaining profile | ~2-3 | BookMapOrderFlowStudies/profile/ |
| Reporting | 4 | BookMapOrderFlowStudies/reporting/ |
| Deterministic modules | 38 | rockit-framework/modules/ |
| Orchestrator + schema | 2 | rockit-framework/ |
| Entry/Stop/Target models | ~25 | New code |
| **Total** | **~78-80 files** | |

---

## Definition of Done

- [ ] All ~92 files migrated from source repos (Phase 1a + 1b combined)
- [ ] ~25 entry/stop/target model files created
- [ ] `make backtest STRATEGY=all` matches original output
- [ ] `make snapshot SESSION=2025-10-15` matches original output
- [ ] Unit test coverage ≥ 90% for rockit-core
- [ ] No imports from old repo paths remain
- [ ] Metrics emitted at strategy, filter, and indicator levels
- [ ] Baseline v1.0.0 committed with full-portfolio metrics
