# Poor High/Low Repair Strategy -- Quant Study (NQ)
*Generated: 2026-03-12 19:26*
*Sessions analyzed: 273*

## 1. Poor High/Low Frequency Analysis

How often do sessions end with a poor high or poor low?

| Method | Poor High | PH% | Poor Low | PL% | Both | Both% |
|--------|-----------|-----|----------|-----|------|-------|
| A | 114 | 41.9% | 116 | 42.6% | 47 | 17.3% |
| B | 44 | 16.2% | 27 | 9.9% | 0 | 0.0% |
| C | 148 | 54.4% | 115 | 42.3% | 68 | 25.0% |

### Repair Rate (next session reaches the poor level)

| Method | PH Repairs | PH Rate | PL Repairs | PL Rate |
|--------|------------|---------|------------|---------|
| A | 61/114 | 53.5% | 48/116 | 41.4% |
| B | 37/44 | 84.1% | 18/27 | 66.7% |
| C | 91/148 | 61.5% | 47/115 | 40.9% |

### Distance from Open to Poor Level

| Method | Median to PH | Mean to PH | Median to PL | Mean to PL |
|--------|-------------|------------|-------------|------------|
| A | 157.5 pts | 218.3 pts | 201.9 pts | 262.8 pts |
| B | 100.1 pts | 124.7 pts | 149.2 pts | 184.3 pts |
| C | 113.2 pts | 158.9 pts | 178.8 pts | 230.5 pts |

## 2. Poor HIGH vs Poor LOW Head-to-Head

| Metric | Poor HIGH (SHORT) | Poor LOW (LONG) |
|--------|-------------------|-----------------|
| Trades | 51860 | 25380 |
| Win Rate | 28.2% | 32.4% |
| Profit Factor | 0.66 | 0.93 |
| Total PnL | $-5,615,988 | $-649,584 |
| Avg Win | $742 | $1,035 |
| Avg Loss | $-443 | $-533 |
| Expectancy | $-108 | $-26 |

## 3. Detection Method Comparison

| Method | Description | Trades | WR | PF | Total PnL |
|--------|-------------|--------|-----|-----|-----------|
| A | Close position in bar range (no follow-through) | 27880 | 30.4% | 0.86 | $-1,282,299 |
| B | High/low in last 30 min (late, untested) | 12980 | 19.9% | 0.39 | $-3,267,258 |
| C | No excess tail (< 3 pts) | 36380 | 32.5% | 0.85 | $-1,716,014 |

## 4. Full Results Matrix (Top 30 by PF, min 10 trades)

| # | Method | Touch | Accept | Stop | Target | Time | Trades | WR | PF | Total PnL | Exp/Trade |
|---|--------|-------|--------|------|--------|------|--------|-----|-----|-----------|-----------|
| 1 | A | within_10 | accept_3 | stop_10pt | target_1R | morning | 54 | 66.7% | 2.01 | $8,964 | $166 |
| 2 | A | within_10 | accept_3 | stop_half_atr | target_1R | morning | 54 | 61.1% | 1.85 | $7,132 | $132 |
| 3 | A | within_10 | accept_3 | stop_5pt | target_1R | morning | 54 | 63.0% | 1.83 | $6,294 | $117 |
| 4 | A | within_10 | accept_3 | stop_10pt | target_1R | full_day | 60 | 63.3% | 1.77 | $8,154 | $136 |
| 5 | A | within_10 | accept_3 | stop_half_atr | target_1R | full_day | 60 | 58.3% | 1.66 | $6,420 | $107 |
| 6 | A | within_10 | accept_3 | stop_half_atr | target_2R | morning | 54 | 40.7% | 1.65 | $8,936 | $165 |
| 7 | A | within_10 | accept_3 | stop_5pt | target_1R | full_day | 60 | 60.0% | 1.64 | $5,684 | $95 |
| 8 | A | touch_0 | accept_1 | stop_30pt | target_2R | morning | 60 | 43.3% | 1.6 | $15,294 | $255 |
| 9 | A | within_10 | accept_3 | stop_5pt | target_2R | morning | 54 | 42.6% | 1.6 | $7,574 | $140 |
| 10 | A | within_3 | accept_1 | stop_30pt | target_2R | morning | 60 | 43.3% | 1.57 | $15,029 | $250 |
| 11 | A | within_3 | accept_1 | stop_5pt | midpoint | morning | 60 | 15.0% | 1.56 | $7,356 | $123 |
| 12 | A | within_5 | accept_1 | stop_30pt | target_2R | morning | 64 | 42.2% | 1.55 | $16,073 | $251 |
| 13 | A | within_5 | accept_1 | stop_half_atr | target_2R | morning | 64 | 35.9% | 1.55 | $7,092 | $111 |
| 14 | C | touch_0 | accept_1 | stop_half_atr | prior_poc | morning | 84 | 26.2% | 1.55 | $10,602 | $126 |
| 15 | C | touch_0 | accept_1 | stop_5pt | midpoint | morning | 84 | 17.9% | 1.52 | $9,958 | $119 |
| 16 | A | touch_0 | accept_1 | stop_5pt | midpoint | morning | 60 | 13.3% | 1.51 | $6,464 | $108 |
| 17 | A | within_3 | accept_1 | stop_5pt | target_2R | morning | 60 | 35.0% | 1.51 | $5,009 | $83 |
| 18 | A | within_10 | accept_3 | stop_10pt | target_2R | morning | 54 | 42.6% | 1.51 | $8,159 | $151 |
| 19 | C | touch_0 | accept_1 | stop_half_atr | prior_poc | full_day | 90 | 25.6% | 1.49 | $9,770 | $109 |
| 20 | A | within_10 | accept_3 | stop_30pt | target_1R | morning | 54 | 57.4% | 1.48 | $9,404 | $174 |
| 21 | A | within_10 | accept_3 | stop_half_atr | target_2R | full_day | 60 | 38.3% | 1.48 | $7,544 | $126 |
| 22 | C | touch_0 | accept_1 | stop_5pt | prior_poc | morning | 84 | 25.0% | 1.48 | $8,483 | $101 |
| 23 | A | touch_0 | accept_1 | stop_half_atr | prior_poc | morning | 60 | 20.0% | 1.47 | $6,291 | $105 |
| 24 | A | within_5 | accept_1 | stop_5pt | target_2R | morning | 64 | 35.9% | 1.47 | $5,488 | $86 |
| 25 | A | within_10 | accept_1 | stop_30pt | target_1R | morning | 64 | 59.4% | 1.47 | $9,798 | $153 |
| 26 | A | within_5 | accept_3 | stop_10pt | target_1R | morning | 49 | 63.3% | 1.45 | $3,419 | $70 |
| 27 | A | within_10 | accept_3 | stop_5pt | target_2R | full_day | 60 | 40.0% | 1.44 | $6,334 | $106 |
| 28 | B | within_3 | accept_2 | stop_10pt | target_1R | morning | 24 | 58.3% | 1.42 | $1,832 | $76 |
| 29 | C | touch_0 | accept_1 | stop_5pt | midpoint | full_day | 90 | 16.7% | 1.42 | $8,578 | $95 |
| 30 | A | within_10 | accept_1 | stop_30pt | half_range | morning | 64 | 60.9% | 1.41 | $7,848 | $123 |

### Worst 10 Configurations

| # | Method | Touch | Accept | Stop | Target | Time | Trades | WR | PF | Total PnL |
|---|--------|-------|--------|------|--------|------|--------|-----|-----|-----------|
| 1 | B | touch_0 | accept_3 | stop_5pt | prior_poc | morning | 17 | 0.0% | 0.0 | $-5,395 |
| 2 | B | touch_0 | accept_3 | stop_5pt | midpoint | full_day | 21 | 0.0% | 0.0 | $-6,241 |
| 3 | B | touch_0 | accept_3 | stop_5pt | midpoint | morning | 17 | 0.0% | 0.0 | $-5,395 |
| 4 | B | touch_0 | accept_3 | stop_half_atr | prior_poc | morning | 17 | 0.0% | 0.0 | $-6,656 |
| 5 | B | touch_0 | accept_3 | stop_half_atr | midpoint | morning | 17 | 0.0% | 0.0 | $-6,656 |
| 6 | B | within_3 | accept_3 | stop_5pt | prior_poc | morning | 18 | 0.0% | 0.0 | $-6,469 |
| 7 | B | within_3 | accept_3 | stop_5pt | midpoint | full_day | 23 | 0.0% | 0.0 | $-8,224 |
| 8 | B | within_3 | accept_3 | stop_5pt | midpoint | morning | 18 | 0.0% | 0.0 | $-6,469 |
| 9 | B | within_3 | accept_3 | stop_half_atr | prior_poc | morning | 18 | 0.0% | 0.0 | $-7,732 |
| 10 | B | within_3 | accept_3 | stop_half_atr | midpoint | morning | 18 | 0.0% | 0.0 | $-7,732 |

## 5. Day Type Breakdown (all configs combined)

| Day Type | Trades | WR | PF | Total PnL | Avg PnL |
|----------|--------|-----|-----|-----------|---------|
| B_DAY | 19460 | 26.2% | 0.65 | $-2,424,089 | $-125 |
| NEUTRAL | 10720 | 28.5% | 0.81 | $-696,343 | $-65 |
| P_DAY | 43240 | 31.2% | 0.75 | $-3,505,474 | $-81 |
| TREND | 3820 | 32.0% | 1.31 | $360,335 | $94 |

## 6. Exit Reason Breakdown

| Exit Reason | Trades | WR | PF | Total PnL |
|-------------|--------|-----|-----|-----------|
| EOD | 462 | 90.0% | 35.34 | $266,466 |
| STOP | 53319 | 0.0% | 0.0 | $-25,472,944 |
| TARGET | 23459 | 95.7% | 114.92 | $18,940,906 |

## 7. Top 5 Winners / Losers (Best Config)

*Best config: `A|within_10|accept_3|stop_10pt|target_1R|morning`*

### Top 5 Winners

| Date | Dir | Type | Entry | Exit | PnL | Bars |
|------|-----|------|-------|------|-----|------|
| 2026-03-10 | SHORT | HIGH | 24998.25 | 24929.00 | $1,361 | 13 |
| 2025-05-29 | SHORT | HIGH | 22226.50 | 22167.50 | $1,156 | 9 |
| 2025-03-13 | LONG | LOW | 20349.25 | 20400.75 | $1,006 | 10 |
| 2025-06-23 | LONG | LOW | 22294.25 | 22339.00 | $871 | 1 |
| 2025-11-21 | LONG | LOW | 24382.75 | 24420.50 | $731 | 2 |

### Top 5 Losers

| Date | Dir | Type | Entry | Exit | PnL | Bars |
|------|-----|------|-------|------|-----|------|
| 2026-03-06 | LONG | LOW | 24790.25 | 24762.00 | $-589 | 2 |
| 2025-07-18 | SHORT | HIGH | 23755.50 | 23784.25 | $-599 | 9 |
| 2025-07-10 | LONG | LOW | 23435.50 | 23403.25 | $-669 | 4 |
| 2025-05-15 | LONG | LOW | 22006.00 | 21971.75 | $-709 | 7 |
| 2025-10-06 | SHORT | HIGH | 25383.00 | 25435.00 | $-1,064 | 22 |

## 8. Additional Analysis

### Gap Direction Impact

*Note: All trades by definition approach the poor level, so gap direction analysis 
is embedded in the distance-to-level metric. Shorter distances (within_3, touch_0) 
effectively capture gap-toward scenarios.*

- Mean distance from entry to poor level: 11.0 pts
- Median distance: 8.4 pts
- Min / Max: 0.2 / 64.8 pts


## 9. Recommendation

**Best configuration** (by Profit Factor, min 10 trades):

- Detection method: **A** (Close position in bar range (no follow-through))
- Touch tolerance: **within_10**
- Acceptance: **accept_3**
- Stop model: **stop_10pt**
- Target model: **target_1R**
- Time window: **morning**
- Trades: 54, WR: 66.7%, PF: 2.01
- Total PnL: $8,964
- Expectancy: $166/trade

**VERDICT: VIABLE** -- This configuration shows positive expectancy with 
sufficient trade count (54) and profit factor (2.01).
Consider adding to the strategy portfolio.

**Poor LOW repair (LONG) is significantly stronger** than Poor HIGH repair (SHORT). 
Consider trading only the LONG side.
