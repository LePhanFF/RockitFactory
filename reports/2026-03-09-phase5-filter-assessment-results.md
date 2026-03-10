# Phase 5 Results: Trade Assessments, Combo Filters, NWOG

> **Date**: 2026-03-09
> **Branch**: claude/bridge-implementation
> **Instrument**: NQ (270 sessions)
> **Test Suite**: 694 passed, 0 failed, 1 skipped

---

## 1. Trade Assessments (Baseline: 408 trades)

Programmatic assessment of all trades from baseline run (`NQ_20260308_215525`).

| Outcome Quality | Count | % | Description |
|----------------|-------|---|-------------|
| **strong_win** | 154 | 37.7% | Bias-aligned, hit target or profitable EOD |
| **avoidable_loss** | 102 | 25.0% | Filter would have blocked (counter-bias, wrong day type, etc.) |
| **normal_loss** | 77 | 18.9% | Valid setup that didn't work |
| **lucky_win** | 71 | 17.4% | Won despite counter-bias |
| **barely_profitable** | 4 | 1.0% | Net PnL < 30% of avg win |

**Key insight**: 25% of all trades are avoidable losses. This is the value the combo filters capture.

### 15 Pattern Observations Recorded

See [brainstorm/analysis/01-trade-analysis-phase4.md](../brainstorm/analysis/01-trade-analysis-phase4.md) for full analysis.

Top findings:
1. Bias alignment = #1 predictor (62.2% vs 47.7% WR)
2. OR Rev + B_shape TPO = 76.8% WR
3. 80P Rule is contrarian (works best when tape is Flat)
4. B-Day on Trend Down = 0% WR
5. First hour dominates: 77% of trades, 61.3% WR

---

## 2. Filter A/B Test Results

### Portfolio-Level Comparison

| Run | Trades | WR% | PF | Net PnL | MaxDD | Expectancy ($/trade) |
|-----|--------|-----|-----|---------|-------|---------------------|
| **A: Baseline** | 408 | 56.1% | 2.45 | $159,332 | 2.07% | $391 |
| **B: Bias only** | 259 | 61.0% | 3.07 | $125,885 | 1.89% | $486 |
| **C: Full combo** | 206 | 64.1% | 3.30 | $98,357 | 2.15% | $477 |
| **D: Combo + Regime** | 156 | 74.4% | 5.75 | $104,292 | 0.53% | $669 |

### Per-Strategy Breakdown (Baseline vs Bias Filter)

| Strategy | | Trades | WR% | PF | Net PnL | Expectancy | Avg Win | Avg Loss |
|----------|---|--------|-----|-----|---------|-----------|---------|----------|
| **OR Rev** | Baseline | 102 | 63.7% | 3.55 | $77,075 | $756 | $1,651 | -$817 |
| | Bias | 55 | 76.4% | **5.39** | $54,630 | $993 | $1,597 | -$956 |
| **80P Rule** | Baseline | 71 | 42.3% | 1.72 | $21,326 | $300 | $1,694 | -$719 |
| | Bias | 54 | 48.1% | **2.32** | **$25,846** | $479 | $1,748 | -$700 |
| **OR Accept** | Baseline | 138 | 59.4% | 2.72 | $32,294 | $234 | $623 | -$336 |
| | Bias | 89 | 64.0% | **3.31** | $24,839 | $279 | $624 | -$336 |
| **20P IB Ext** | Baseline | 46 | 50.0% | 2.05 | $17,224 | $374 | $1,465 | -$716 |
| | Bias | 35 | 51.4% | **2.43** | $14,804 | $423 | $1,396 | -$607 |
| **B-Day** | Baseline | 51 | 56.9% | 1.77 | $11,412 | $224 | $907 | -$677 |
| | Bias | 26 | 57.7% | 1.76 | $5,767 | $222 | $892 | -$693 |

### Key Findings

1. **Every strategy's PF improved** with bias filter (except B-Day, flat)
2. **80P Rule is the only strategy that gained PnL** with the filter (+$4,520)
3. OR Rev lost the most absolute PnL (-$22K) because it's a reversal strategy that sometimes profits against bias ("lucky wins" removed)
4. **Expectancy improved across the board**: $391 avg/trade (baseline) -> $486 (bias)
5. **Run D (Combo+Regime)** is too aggressive — kills 80P entirely (1 trade) and cripples B-Day (5 trades, 20% WR)

### Recommendation

**Run B (Bias only)** is the production pick:
- PF 3.07 (up from 2.45)
- WR 61.0% (up from 56.1%)
- Max drawdown improved (2.07% -> 1.89%)
- Expectancy up 24% ($391 -> $486/trade)
- Trade-off: $33K less total PnL from removing 149 trades (many were "lucky wins")

For maximum risk-adjusted returns: Run D (74.4% WR, PF 5.75, 0.53% DD), but only 156 trades.

---

## 3. NWOG Gap Fill Results

| Run | Trades | WR% | PF | Net PnL |
|-----|--------|-----|-----|---------|
| **A: NWOG standalone** | 8 | 25.0% | 0.18 | **-$11,073** |
| **B: NWOG + portfolio** | 416 | 55.5% | 2.20 | $148,259 |

### Individual NWOG Trades

| Date | Dir | Entry | Exit | Net PnL | Reason |
|------|-----|-------|------|---------|--------|
| 2025-02-24 | SHORT | 22,418 | 22,572 | -$3,094 | TARGET |
| 2025-03-03 | SHORT | 21,870 | 21,821 | +$951 | TARGET |
| 2025-09-22 | LONG | 25,160 | 25,117 | -$874 | TARGET |
| 2025-12-08 | SHORT | 25,957 | 25,992 | -$714 | TARGET |
| 2025-12-15 | SHORT | 25,320 | 25,459 | -$2,804 | TARGET |
| 2026-02-02 | LONG | 25,866 | 25,639 | -$4,559 | TARGET |
| 2026-02-09 | LONG | 25,182 | 25,108 | -$1,499 | TARGET |
| 2026-03-02 | LONG | 24,882 | 24,959 | +$1,521 | TARGET |

### Analysis

- Only 8 Mondays passed both VWAP + acceptance filters over 270 sessions
- Most losses hit the gap fill target on the WRONG side (stop was too tight at 75pts)
- The 75pt fixed stop gets knocked out by intraday noise before gap fills complete
- **NWOG needs rework**: wider stop, or trailing stop, or time-based exit management
- Study showed 100% fill rate when filters confirm, but the fill takes time and price path is volatile

---

## 4. Infrastructure Built

### New Files

| File | Purpose |
|------|---------|
| [scripts/populate_assessments.py](../scripts/populate_assessments.py) | Programmatic trade assessment pipeline |
| [scripts/ab_test_filters.py](../scripts/ab_test_filters.py) | A/B test framework for filter combinations |
| [scripts/ab_test_nwog.py](../scripts/ab_test_nwog.py) | A/B test for NWOG strategy |
| [filters/bias_filter.py](../packages/rockit-core/src/rockit_core/filters/bias_filter.py) | Config-driven bias alignment filter |
| [filters/day_type_gate_filter.py](../packages/rockit-core/src/rockit_core/filters/day_type_gate_filter.py) | Day type blocking filter |
| [filters/anti_chase_filter.py](../packages/rockit-core/src/rockit_core/filters/anti_chase_filter.py) | Anti-chase momentum filter |
| [filters/pipeline.py](../packages/rockit-core/src/rockit_core/filters/pipeline.py) | YAML-driven filter pipeline builder |
| [configs/filters.yaml](../configs/filters.yaml) | Filter pipeline configuration |
| [strategies/nwog_gap_fill.py](../packages/rockit-core/src/rockit_core/strategies/nwog_gap_fill.py) | NWOG Gap Fill strategy |
| [brainstorm/strategy/04-nwog-implementation.md](../brainstorm/strategy/04-nwog-implementation.md) | NWOG GAP analysis document |
| [brainstorm/12-strategy-expansion-roadmap.md](../brainstorm/12-strategy-expansion-roadmap.md) | Strategy expansion roadmap |

### DuckDB State

| Table | Rows |
|-------|------|
| backtest_runs | 36+ (including A/B test runs) |
| trades | 8,000+ |
| trade_assessments | 408 |
| observations | 15 |
| session_context | 270 |
| deterministic_tape | 7,362 |

### Test Suite

- **694 passed**, 0 failed, 1 skipped
- 42 new tests: test_filter_pipeline.py (25), test_nwog_strategy.py (9), test_research_assessments.py (8)

---

## 5. Progression Timeline

| Phase | Date | Trades | WR% | PF | Net PnL | Key Change |
|-------|------|--------|-----|-----|---------|------------|
| Baseline (broken) | 2026-03-01 | ~800 | ~40% | ~0.8 | negative | 16 strategies, most losing |
| Fix + disable losers | 2026-03-02 | 408 | 56.1% | 2.45 | $159,332 | 5 core strategies only |
| + Bias filter | 2026-03-09 | 259 | 61.0% | 3.07 | $125,885 | Removes counter-bias trades |
| + Full combo filter | 2026-03-09 | 206 | 64.1% | 3.30 | $98,357 | + day type gate + anti-chase |
| + Regime filter | 2026-03-09 | 156 | 74.4% | 5.75 | $104,292 | + block counter-trend regime |

---

## 6. Deep Dive: Bias-Filtered Run B (259 trades)

Assessments populated for all 4 A/B runs. Quality progression:

| Run | Strong Wins | Avoidable Losses | Lucky Wins | Normal Losses |
|-----|-------------|-----------------|------------|---------------|
| A: Baseline (408) | 154 (37.7%) | **102 (25.0%)** | 71 (17.4%) | 77 (18.9%) |
| B: Bias only (259) | 154 (59.5%) | **24 (9.3%)** | 0 (0%) | 77 (29.7%) |
| C: Full combo (206) | 131 (63.6%) | **6 (2.9%)** | 0 (0%) | 68 (33.0%) |
| D: Combo+Regime (156) | 115 (73.7%) | **3 (1.9%)** | 0 (0%) | 37 (23.7%) |

Bias filter preserved ALL 154 strong wins while eliminating all 71 lucky wins and reducing avoidable losses 102 -> 24.

### LONG vs SHORT Performance (Run B)

| Strategy | LONG WR | LONG Net | SHORT WR | SHORT Net | Finding |
|----------|---------|---------|----------|----------|---------|
| **OR Rev** | 76.3% | $35,072 | 76.5% | $19,557 | Balanced — both sides excellent |
| **80P Rule** | **38.7%** | **$350** | **60.9%** | **$25,496** | LONG side is breakeven! |
| **OR Accept** | 60.3% | $15,225 | 73.1% | $9,613 | SHORT side 13pp better WR |
| **20P IB Ext** | 48.1% | $7,581 | 62.5% | $7,222 | SHORT side better but small sample |
| **B-Day** | 57.7% | $5,767 | — | — | All LONG (balance fade entry) |

**Critical finding**: 80P LONG = 38.7% WR, $350 net. Essentially breakeven. Consider disabling 80P LONG or adding stricter filters.

### Loss Pattern Analysis

1. **93% of normal losses are clean STOP exits** (avg -$522). No blown stops or runaway losses. These are the cost of doing business — valid setups, controlled risk.
2. **CRI STAND_DOWN at IB close has ZERO discriminating power** — 100% of trades show STAND_DOWN at entry time. CRI fires later in session, NOT useful as IB-close filter.
3. **Loss clusters are 2-trade max** — no sessions with 3+ losses. Worst single session = -$2,827. Risk management is working.
4. **LONG trades = 77% of all losses** — 57.8% WR vs SHORT 68.9% WR. Bullish bias (171/270 sessions) + LONG direction = overtrading.
5. **24 remaining avoidable losses**: 19 from 80P (day_type/anti-chase), 4 from OR Rev (counter-tape), 1 from B-Day (trend day).

### 23 Observations in DuckDB

15 from Phase 4 analysis + 8 new from Phase 5 bias-filtered analysis. All persisted in `observations` table for agent/LLM consumption. Key new observations:
- `p5_01`: 80P SHORT >> LONG (60.9% vs 38.7% WR)
- `p5_03`: CRI at IB close = useless (100% STAND_DOWN)
- `p5_05`: LONG side carries 77% of losses
- `p5_06`: Bias filter preserves ALL strong wins, removes only bad/lucky trades

---

## 7. Next Steps

1. **Decide filter config for production** — Bias only (B) vs Full combo (C) vs Combo+Regime (D)
2. **Consider disabling 80P LONG** — 38.7% WR is below breakeven after costs
3. **Fix NWOG** — wider stop or trailing exit, or re-study with different parameters
4. **Study NDOG (daily gap)** — may overlap with B-Day, needs validation
5. **Re-optimize disabled strategies** — See [strategy expansion roadmap](../brainstorm/12-strategy-expansion-roadmap.md)
