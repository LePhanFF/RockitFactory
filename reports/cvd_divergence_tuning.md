# CVD Divergence Strategy Tuning Report

**Date**: 2026-03-14
**Instrument**: NQ
**Sessions**: 274 (2025-02-20 to 2026-03-13)
**Branch**: claude/bridge-implementation

## Executive Summary

CVD Divergence does not meet standalone benchmark (PF > 1.5). Best config achieves PF 1.42 (B-Day LONG-only, 2R target). Monthly consistency is poor (8 of 14 months negative). **Recommendation: KEEP DISABLED as standalone; pivot to confirmation filter on 80P Rule and OR Reversal.**

---

## Parameter Sweep Results

### Round 1: Filter Combinations

| Config | Trades | WR% | PF | Net P&L | R:R | Exp/Trade |
|--------|--------|-----|-----|---------|-----|-----------|
| A: Day-type filter only | 238 | 34.0% | 1.13 | $16,190 | 2.19 | $68 |
| B: Day-type + Edge(10pt) | 130 | 34.6% | 0.94 | -$3,566 | 1.77 | -$27 |
| C: Day-type + Edge + POC target | 172 | 37.8% | 0.99 | -$1,039 | 1.62 | -$6 |
| D: C + Reversal bar confirmation | 62 | 32.3% | 0.55 | -$12,645 | 1.16 | -$204 |
| E: No filters (baseline) | 239 | 34.3% | 1.13 | $16,510 | 2.17 | $69 |
| F: Edge filter only | 43 | 32.6% | 0.87 | -$3,592 | 1.80 | -$84 |
| G: Day-type + Edge + 2R + Rev bar | 27 | 18.5% | 0.32 | -$13,665 | 1.43 | -$506 |
| H: Day-type + Edge + VWAP target | 44 | 40.9% | 0.70 | -$6,822 | 1.00 | -$155 |

### Round 2: Direction & Day-Type Isolation

| Config | Trades | WR% | PF | Net P&L | R:R | Exp/Trade |
|--------|--------|-----|-----|---------|-----|-----------|
| REF: Day-type, 2R, both | 238 | 34.0% | 1.13 | $16,190 | 2.19 | $68 |
| LONG-only, day-type, 2R | 119 | 37.8% | 1.34 | $21,012 | 2.20 | $177 |
| SHORT-only, day-type, 2R | 136 | 32.4% | 0.99 | -$732 | 2.07 | -$5 |
| B-Day only, both, 2R | 219 | 33.8% | 1.17 | $18,666 | 2.29 | $85 |
| B-Day only + edge, both | 202 | 34.7% | 0.99 | -$1,030 | 1.86 | -$5 |
| Day-type + Edge(20pt), 2R | 158 | 34.2% | 0.96 | -$2,917 | 1.85 | -$18 |
| Day-type + Edge(30pt), 2R | 47 | 29.8% | 0.98 | -$771 | 2.30 | -$16 |
| **B-Day LONG-only, 2R** | **118** | **36.4%** | **1.42** | **$24,316** | **2.47** | **$206** |

---

## Best Config Analysis: B-Day LONG-only

**Parameters**: day_type_filter=True (b_day only), edge_filter=False, target=2R, direction=LONG only

### Performance
- **118 trades** across 274 sessions (0.43 trades/session)
- **36.4% WR**, PF 1.42, $206/trade expectancy
- R:R actual: 2.47 (avg win $1,925 vs avg loss $780)
- Max drawdown: 7.5% ($13,173)

### Monthly Breakdown

| Month | Trades | WR% | P&L |
|-------|--------|-----|-----|
| 2025-02 | 4 | 0.0% | -$4,332 |
| 2025-03 | 10 | 30.0% | $2,136 |
| 2025-04 | 6 | 50.0% | $12,634 |
| 2025-05 | 10 | 80.0% | $7,473 |
| 2025-06 | 5 | 40.0% | $19 |
| 2025-07 | 14 | 28.6% | -$1,970 |
| 2025-08 | 7 | 14.3% | -$848 |
| 2025-09 | 9 | 22.2% | -$2,321 |
| 2025-10 | 11 | 36.4% | $831 |
| 2025-11 | 13 | 15.4% | -$4,112 |
| 2025-12 | 9 | 33.3% | -$572 |
| 2026-01 | 7 | 28.6% | -$304 |
| 2026-02 | 10 | 70.0% | $12,447 |
| 2026-03 | 3 | 66.7% | $3,236 |

**Profitable months**: 6 of 14 (43%) -- poor consistency

### Exit Breakdown
- TARGET: 39 trades (33%), 100% WR, +$79,971
- STOP: 72 trades (61%), 0% WR, -$57,451
- VWAP_BREACH_PM: 7 trades (6%), 57% WR, +$1,796

---

## Key Findings

### 1. Edge filter hurts performance
The 10pt edge proximity filter cuts trades by ~45% but removes many winners. The edge concept is valid (CVD divergence at extremes), but the implementation is too restrictive -- by the time price makes a new high/low to trigger divergence, it has often already moved away from the edge.

### 2. Day-type filter provides minimal benefit
Only 3 trades in the entire dataset occurred on trend/super-trend days. The dynamic day-type reclassification means bars are classified as b_day/neutral even on eventual trend days (early session when extension hasn't developed yet). The filter is theoretically correct but practically irrelevant.

### 3. NQ has strong LONG bias
LONG: 37.8% WR, PF 1.34, +$21K vs SHORT: 32.4% WR, PF 0.99, -$732. NQ's structural long bias (index composition) makes SHORT divergence plays unprofitable.

### 4. Reversal bar confirmation is destructive
Adding reversal bar requirement drops WR from 34.6% to 18.5% and PF from 0.94 to 0.32. The extra bar of delay costs the entry advantage -- by the time the reversal bar forms, the move has often already happened.

### 5. POC/VWAP targets underperform 2R
POC target: PF 0.99 (vs 1.13 for 2R). VWAP target: PF 0.70. Fixed R:R targets outperform structural targets because mean-reversion targets (POC, VWAP) are often too far, causing more timeouts/stops.

---

## Standalone vs Filter Recommendation

### Standalone: NOT RECOMMENDED
- PF 1.42 < 1.5 benchmark (close but doesn't clear)
- Only 6 of 14 months profitable (poor consistency)
- 118 trades is reasonable sample but edge is marginal
- High variance: best month +$12.6K, worst month -$4.3K

### Filter Role: RECOMMENDED

CVD divergence is better suited as a **confirmation filter** on existing strategies that already trade at structural edges:

#### Integration with 80P Rule
- **When**: 80P acceptance signal fires (price re-enters VA from outside)
- **CVD check**: Is there CVD divergence at the VA edge? (price pushing against VA boundary but CVD not confirming)
- **Effect**: Would filter out 80P entries where momentum is still strong (no exhaustion), keeping only entries where buyers/sellers are genuinely exhausted at the edge
- **Implementation**: In `EightyPercentRule._check_30m_acceptance()`, after acceptance confirmed, check if cumulative delta shows divergence from the price extreme at the VA boundary

#### Integration with OR Reversal
- **When**: OR Reversal detects a Judas swing + reversal
- **CVD check**: This is **already implemented** -- OR Reversal checks `cvd_declining` / `cvd_rising` as a gate
- **Status**: No additional work needed; OR Rev already uses CVD divergence as a filter

#### Filter API Design
```python
def check_cvd_divergence(
    bars: pd.DataFrame,
    lookback: int = 20,
    direction: str = 'LONG',  # Direction of the potential trade
) -> bool:
    """
    Check if CVD divergence exists in the recent price action.

    For LONG entries: returns True if price made new low but CVD
    made higher low (bearish exhaustion = bullish divergence).

    For SHORT entries: returns True if price made new high but CVD
    made lower high (bullish exhaustion = bearish divergence).
    """
```

This function could be added to `rockit_core/filters/order_flow_filter.py` and called by any strategy that wants CVD confirmation at its entry point.

---

## Final Decision

| Option | Recommendation |
|--------|---------------|
| ENABLE standalone | NO -- PF 1.42 < 1.5, inconsistent monthly P&L |
| ENABLE as filter on 80P | YES -- CVD divergence at VA edges is the core thesis |
| ENABLE as filter on OR Rev | ALREADY DONE -- OR Rev already checks CVD divergence |
| KEEP DISABLED | YES for standalone strategy |

**Action**: Keep `cvd_divergence` strategy disabled in `strategies.yaml`. The CVD divergence concept is valuable as a filter/confirmation signal, not as a standalone entry trigger. The best application is adding CVD divergence confirmation to the 80P Rule's acceptance check, which would be a future enhancement to the 80P strategy itself.
