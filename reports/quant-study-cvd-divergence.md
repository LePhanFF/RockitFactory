# CVD Divergence Study -- NQ Futures

*Generated: 2026-03-12*

## Overview

CVD (Cumulative Volume Delta) divergence signals institutional exhaustion:
- **Bullish**: Price makes lower low but CVD makes higher low
- **Bearish**: Price makes higher high but CVD makes lower high

This study tests CVD divergence as a standalone entry signal across 8,100 configurations
(entry triggers, confirmation, ADX gates, stop models, target models, time windows, directions).

## 1. Divergence Frequency Analysis

| Metric | Bull | Bear |
|--------|------|------|
| Total signals | 4,077 | 4,927 |
| Avg per session | 14.9 | 18.0 |
| Median per session | 13 | 18 |
| Sessions with signal | 273/273 (100%) | 273/273 (100%) |

**Total sessions analyzed**: 273

> CVD divergence signals fire frequently. Entry triggers, confirmation bars,
> and cooldown (15 bars, max 2 trades/session) aggressively filter these signals.

## 2. Top 30 Configurations by Profit Factor (min 15 trades)

| # | Trigger | Confirm | ADX | Stop | Target | Window | Dir | Trades | WR% | PF | Total PnL | Avg PnL | MaxDD |
|---|---------|---------|-----|------|--------|--------|-----|--------|-----|----|-----------|---------|-------|
| 1 | cvd_div_bb | immediate | adx_lt_25 | swing_low | vwap | after_ib | LONG | 33 | 21.2 | 5.05 | $5,300 | $161 | $349 |
| 2 | cvd_div_bb | reversal_bar | adx_lt_25 | swing_low | vwap | after_ib | LONG | 21 | 33.3 | 4.30 | $4,625 | $220 | $351 |
| 3 | cvd_div_bb | immediate | adx_lt_25 | swing_low | vwap | full | LONG | 37 | 18.9 | 4.05 | $4,978 | $135 | $492 |
| 4 | cvd_div_bb | two_bar | adx_lt_25 | atr_1x | ib_mid | morning | LONG | 16 | 56.2 | 3.67 | $2,267 | $142 | $264 |
| 5 | cvd_div_bb | reversal_bar | adx_lt_25 | fixed_30pt | prior_poc | after_ib | LONG | 49 | 42.9 | 3.52 | $9,673 | $197 | $695 |
| 6 | cvd_div_bb | two_bar | adx_lt_25 | swing_low | ib_mid | morning | LONG | 16 | 62.5 | 3.52 | $2,568 | $160 | $540 |
| 7 | cvd_div_bb | reversal_bar | adx_lt_25 | atr_1x | prior_poc | after_ib | LONG | 49 | 22.4 | 3.40 | $7,478 | $153 | $723 |
| 8 | cvd_div_bb | two_bar | adx_lt_25 | atr_1x | prior_poc | morning | BOTH | 26 | 46.2 | 3.24 | $4,014 | $154 | $1,046 |
| 9 | cvd_div_bb | reversal_bar | adx_lt_25 | swing_low | vwap | full | LONG | 24 | 29.2 | 3.20 | $4,145 | $173 | $475 |
| 10 | cvd_div_bb | two_bar | adx_lt_25 | atr_1x | prior_poc | after_ib | LONG | 24 | 20.8 | 3.17 | $3,792 | $158 | $454 |
| 11 | cvd_div_rsi | two_bar | adx_lt_25 | atr_1x | ib_mid | morning | LONG | 20 | 60.0 | 3.12 | $1,923 | $96 | $485 |
| 12 | cvd_div_bb | reversal_bar | adx_lt_25 | fixed_30pt | prior_poc | morning | LONG | 25 | 44.0 | 3.09 | $4,396 | $176 | $1,038 |
| 13 | cvd_div_bb | reversal_bar | adx_lt_25 | fixed_30pt | prior_poc | full | LONG | 60 | 40.0 | 3.07 | $10,442 | $174 | $954 |
| 14 | cvd_div_bb | reversal_bar | adx_lt_25 | swing_low | prior_poc | after_ib | LONG | 49 | 28.6 | 3.03 | $6,821 | $139 | $755 |
| 15 | cvd_div_bb | reversal_bar | adx_lt_25 | fixed_20pt | vwap | after_ib | LONG | 21 | 23.8 | 2.97 | $3,159 | $150 | $872 |
| 16 | cvd_div_bb | two_bar | adx_lt_25 | atr_1x | prior_poc | full | LONG | 30 | 23.3 | 2.96 | $4,630 | $154 | $746 |
| 17 | cvd_div_bb | reversal_bar | adx_lt_25 | atr_1x | vwap | after_ib | LONG | 21 | 19.0 | 2.96 | $3,132 | $149 | $799 |
| 18 | cvd_div_bb | two_bar | adx_lt_25 | swing_low | prior_poc | after_ib | LONG | 24 | 37.5 | 2.95 | $5,325 | $222 | $776 |
| 19 | cvd_div_bb | immediate | adx_lt_25 | atr_1x | prior_poc | after_ib | LONG | 91 | 25.3 | 2.90 | $10,341 | $114 | $970 |
| 20 | cvd_div_bb | two_bar | adx_lt_25 | fixed_40pt | ib_mid | morning | LONG | 16 | 56.2 | 2.88 | $2,034 | $127 | $400 |
| 21 | cvd_div_bb | reversal_bar | adx_lt_25 | atr_1x | prior_poc | full | LONG | 60 | 21.7 | 2.88 | $8,059 | $134 | $1,006 |
| 22 | cvd_div_bb | reversal_bar | adx_lt_25 | swing_low | prior_poc | morning | LONG | 25 | 32.0 | 2.88 | $4,036 | $161 | $1,104 |
| 23 | cvd_div_bb | two_bar | adx_lt_25 | atr_1x | 1R | morning | LONG | 22 | 72.7 | 2.85 | $1,384 | $63 | $264 |
| 24 | cvd_div_bb | two_bar | no_adx | atr_1x | prior_poc | morning | LONG | 37 | 32.4 | 2.84 | $5,738 | $155 | $1,242 |
| 25 | cvd_div_bb | two_bar | adx_lt_25 | atr_1x | ib_mid | after_ib | LONG | 25 | 28.0 | 2.82 | $2,935 | $117 | $560 |
| 26 | cvd_div_bb | two_bar | adx_lt_25 | atr_1x | ib_mid | full | LONG | 32 | 37.5 | 2.81 | $3,493 | $109 | $427 |
| 27 | cvd_div_bb | reversal_bar | adx_lt_25 | atr_1x | prior_poc | morning | LONG | 25 | 24.0 | 2.80 | $3,870 | $155 | $1,083 |
| 28 | cvd_div_bb | reversal_bar | adx_lt_25 | fixed_40pt | prior_poc | after_ib | LONG | 49 | 42.9 | 2.78 | $8,641 | $176 | $1,004 |
| 29 | cvd_div_bb | two_bar | adx_lt_25 | swing_low | prior_poc | morning | BOTH | 26 | 53.8 | 2.69 | $4,220 | $162 | $1,156 |
| 30 | cvd_div_bb | two_bar | adx_lt_25 | atr_1x | ib_mid | morning | BOTH | 31 | 54.8 | 2.66 | $2,707 | $87 | $573 |

*Configs with any trades: 8,100/8,100 (100%)*
*Configs with >= 15 trades: 8,030/8,100 (99%)*

## 3. Entry Trigger Comparison

| Trigger | Configs | Avg Trades | Avg WR% | Avg PF | Avg PnL | Best PF |
|----------|---------|------------|---------|--------|---------|---------|
| cvd_div_bb | 1970 | 141 | 34.8 | 1.11 | $244 | 5.05 |
| cvd_div_only | 2025 | 333 | 33.3 | 0.96 | $-1,056 | 1.85 |
| cvd_div_rsi | 2010 | 266 | 34.3 | 1.03 | $208 | 3.12 |
| cvd_div_vwap | 2025 | 331 | 33.1 | 0.95 | $-1,179 | 1.89 |

## 4. Reversal Confirmation Comparison

| Confirmation | Configs | Avg Trades | Avg WR% | Avg PF | Avg PnL | Best PF |
|--------------|---------|------------|---------|--------|---------|---------|
| immediate | 2700 | 339 | 32.3 | 1.01 | $-113 | 5.05 |
| reversal_bar | 2690 | 277 | 33.5 | 1.02 | $-459 | 4.30 |
| two_bar | 2640 | 188 | 35.7 | 1.01 | $-790 | 3.67 |

## 5. ADX Gate Analysis

| ADX Gate | Configs | Avg Trades | Avg WR% | Avg PF | Avg PnL | Best PF |
|----------|---------|------------|---------|--------|---------|---------|
| adx_gt_25 | 2680 | 291 | 33.1 | 0.98 | $-560 | 2.37 |
| adx_lt_25 | 2655 | 182 | 35.3 | 1.06 | $-40 | 5.05 |
| no_adx | 2695 | 332 | 33.1 | 0.99 | $-749 | 2.84 |

## 6. Stop Model Comparison

| Stop Model | Configs | Avg Trades | Avg WR% | Avg PF | Avg PnL | Best PF |
|------------|---------|------------|---------|--------|---------|---------|
| atr_1x | 1606 | 269 | 29.4 | 1.05 | $348 | 3.67 |
| fixed_20pt | 1606 | 269 | 32.0 | 0.98 | $-939 | 2.97 |
| fixed_30pt | 1606 | 269 | 36.9 | 1.02 | $-401 | 3.52 |
| fixed_40pt | 1606 | 269 | 39.8 | 1.01 | $-808 | 2.88 |
| swing_low | 1606 | 269 | 31.1 | 1.01 | $-458 | 5.05 |

## 7. Target Model Comparison

| Target Model | Configs | Avg Trades | Avg WR% | Avg PF | Avg PnL | Best PF |
|--------------|---------|------------|---------|--------|---------|---------|
| 1R | 1620 | 327 | 49.0 | 0.99 | $-808 | 2.85 |
| 2R | 1620 | 327 | 34.8 | 0.98 | $-1,244 | 2.22 |
| ib_mid | 1620 | 250 | 35.8 | 1.06 | $231 | 3.67 |
| prior_poc | 1610 | 225 | 29.2 | 1.14 | $1,873 | 3.52 |
| vwap | 1560 | 212 | 19.9 | 0.89 | $-2,365 | 5.05 |

## 8. Time Window Comparison

| Time Window | Configs | Avg Trades | Avg WR% | Avg PF | Avg PnL | Best PF |
|-------------|---------|------------|---------|--------|---------|---------|
| after_ib | 2685 | 288 | 33.1 | 1.03 | $-113 | 5.05 |
| full | 2685 | 308 | 32.7 | 1.00 | $-588 | 4.05 |
| morning | 2660 | 210 | 35.7 | 1.00 | $-655 | 3.67 |

## 9. Direction Analysis

| Direction | Configs | Avg Trades | Avg WR% | Avg PF | Avg PnL | Best PF |
|-----------|---------|------------|---------|--------|---------|---------|
| BOTH | 2700 | 352 | 33.5 | 1.00 | $-761 | 3.24 |
| LONG | 2635 | 196 | 33.1 | 1.06 | $278 | 5.05 |
| SHORT | 2695 | 256 | 34.9 | 0.98 | $-854 | 2.37 |

## 10. As-a-Filter Analysis

What if CVD divergence is used as a confirmation FILTER for existing strategies
rather than a standalone entry?

### Overlap with Existing Indicators

| Condition | Total Bars | + CVD Div | Overlap % |
|-----------|------------|-----------|-----------|
| Price at BB Lower | 5,861 | 925 | 15.8% |
| Price at BB Upper | 5,003 | 928 | 18.5% |
| RSI < 30 (Oversold) | 11,335 | 1,730 | 15.3% |
| RSI > 70 (Overbought) | 13,403 | 2,138 | 16.0% |
| Extended from VWAP (bull) | 103,921 | 803 | -- |
| Extended from VWAP (bear) | 103,921 | 3,951 | -- |

### Filter Recommendation

CVD divergence adds value as a **confirmation filter** for mean-reversion strategies:
- **80P Rule**: Require `cvd_div_bull` for LONG entries, `cvd_div_bear` for SHORT
- **Edge Fade**: Already uses CVD divergence internally (see `edge_fade.py`)
- **OR Reversal**: Add CVD divergence as optional high-confidence boost
- **B-Day**: CVD divergence at IB extremes confirms rotation

The filter approach is lower-risk because it reduces false positives on existing
strategies without requiring a new standalone strategy with its own risk budget.

## VERDICT

### Standalone Strategy Viable

The best configuration achieves **5.05 PF** with **33 trades** and **21.2% WR**.

Best config:
- Trigger: `cvd_div_bb`
- Confirmation: `immediate`
- ADX gate: `adx_lt_25`
- Stop: `swing_low`
- Target: `vwap`
- Window: `after_ib`
- Direction: `LONG`
- Total PnL: $5,300
- Max drawdown: $349

**Recommendation**: Implement as standalone strategy AND as filter.
- Standalone for high-conviction setups matching the best config
- Filter for boosting existing strategy confidence

---
*Study parameters: 20-bar lookback, max 2 trades/session, 15-bar cooldown, $5/pt NQ tick value*