# Quant Study: Single Print Gap Fill Strategy (NQ)

**Date**: 2026-03-12
**Sessions analyzed**: 273
**Total configs tested**: 440
**Total trades simulated**: 77960

## 1. Frequency Analysis

- Sessions with **any** single print zones: 273 / 273 (100.0%)
- Total single print zones found: 691
- Average zones per session (when present): 2.5
- Average zone size: 141.2 ticks (35.31 pts)
- Median zone size: 65 ticks

### Zone Size Distribution

| Size Bucket | Count | % |
|-------------|-------|---|
| 1-4 ticks | 24 | 3.5% |
| 5-9 ticks | 42 | 6.1% |
| 10-19 ticks | 64 | 9.3% |
| 20+ ticks | 561 | 81.2% |

### Zone Location Distribution

| Location | Count | % |
|----------|-------|---|
| above_vah | 292 | 42.3% |
| below_val | 311 | 45.0% |
| inside_va | 88 | 12.7% |

## 2. Fill Rate Analysis

- Prior-session zones tested next session: 351 / 689 (50.9%)
- Prior-session zones **fully filled** next session: 301 / 689 (43.7%)
- Prior-session zones **partially filled** (>50%): 24 (3.5%)

### Fill Rate by Zone Location

| Location | Zones | Tested | % Tested | Filled | % Filled |
|----------|-------|--------|----------|--------|----------|
| above_vah | 291 | 155 | 53.3% | 136 | 46.7% |
| below_val | 310 | 146 | 47.1% | 123 | 39.7% |
| inside_va | 88 | 50 | 56.8% | 42 | 47.7% |

### Fill Rate by Zone Size

| Size Bucket | Zones | Tested | % Tested | Filled | % Filled |
|-------------|-------|--------|----------|--------|----------|
| 1-4 ticks | 24 | 13 | 54.2% | 13 | 54.2% |
| 5-9 ticks | 42 | 20 | 47.6% | 20 | 47.6% |
| 10-19 ticks | 64 | 33 | 51.6% | 33 | 51.6% |
| 20+ ticks | 559 | 285 | 51.0% | 235 | 42.0% |

## 3. Top 30 Configs by Profit Factor

*(filtered to configs with >= 10 trades)*

| # | Config | Trades | WR% | PF | Total Pts | Total $ | Avg Pts |
|---|--------|--------|-----|------|-----------|---------|---------|
| 1 | `min_10|above_vah|immediate|atr_1x|2R|morning|BOTH` | 117 | 69.2 | 4.49 | 1126.2 | $22,525 | 9.63 |
| 2 | `min_10|above_vah|immediate|atr_1x|2R|full|BOTH` | 136 | 67.6 | 3.81 | 1247.6 | $24,952 | 9.17 |
| 3 | `min_5|above_vah|immediate|atr_1x|2R|morning|BOTH` | 127 | 66.1 | 3.74 | 1085.0 | $21,701 | 8.54 |
| 4 | `min_10|any|immediate|atr_1x|2R|morning|BOTH` | 268 | 64.9 | 3.71 | 2539.3 | $50,786 | 9.47 |
| 5 | `min_5|any|immediate|fixed_20pt|zone_fill|full|BOTH` | 338 | 77.8 | 3.6 | 3881.9 | $77,638 | 11.48 |
| 6 | `min_5|any|immediate|opposite_zone|1R|full|BOTH` | 338 | 68.3 | 3.56 | 4534.0 | $90,680 | 13.41 |
| 7 | `min_10|any|immediate|atr_1x|2R|full|BOTH` | 318 | 64.2 | 3.45 | 2948.3 | $58,965 | 9.27 |
| 8 | `min_5|any|immediate|atr_1x|2R|morning|BOTH` | 285 | 63.2 | 3.39 | 2507.6 | $50,153 | 8.8 |
| 9 | `min_10|below_val|immediate|atr_1x|2R|full|BOTH` | 143 | 60.8 | 3.32 | 1367.8 | $27,356 | 9.57 |
| 10 | `min_5|below_val|immediate|atr_1x|2R|full|BOTH` | 146 | 60.3 | 3.27 | 1380.9 | $27,618 | 9.46 |
| 11 | `min_5|above_vah|immediate|atr_1x|2R|full|BOTH` | 147 | 64.6 | 3.24 | 1191.2 | $23,825 | 8.1 |
| 12 | `min_5|any|immediate|atr_1x|2R|full|BOTH` | 338 | 62.7 | 3.23 | 2962.6 | $59,251 | 8.76 |
| 13 | `min_10|above_vah|immediate|atr_1x|2R|morning|SHORT` | 111 | 61.3 | 2.95 | 783.0 | $15,660 | 7.05 |
| 14 | `min_5|below_val|immediate|atr_1x|2R|full|SHORT` | 127 | 59.8 | 2.92 | 1106.3 | $22,126 | 8.71 |
| 15 | `min_5|any|immediate|fixed_20pt|1R|after_ib|BOTH` | 273 | 74.4 | 2.92 | 2668.5 | $53,370 | 9.77 |
| 16 | `min_10|below_val|immediate|atr_1x|2R|morning|BOTH` | 121 | 58.7 | 2.91 | 1040.3 | $20,807 | 8.6 |
| 17 | `min_10|any|immediate|atr_1x|2R|morning|SHORT` | 239 | 59.8 | 2.9 | 1841.9 | $36,839 | 7.71 |
| 18 | `min_10|below_val|immediate|atr_1x|2R|morning|SHORT` | 102 | 59.8 | 2.9 | 893.5 | $17,871 | 8.76 |
| 19 | `min_5|below_val|immediate|atr_1x|2R|morning|SHORT` | 104 | 59.6 | 2.88 | 904.0 | $18,080 | 8.69 |
| 20 | `min_10|below_val|immediate|atr_1x|2R|full|SHORT` | 124 | 59.7 | 2.88 | 1064.5 | $21,290 | 8.58 |
| 21 | `min_10|above_vah|immediate|atr_1x|2R|full|SHORT` | 130 | 61.5 | 2.83 | 932.5 | $18,649 | 7.17 |
| 22 | `min_5|below_val|immediate|atr_1x|2R|morning|BOTH` | 123 | 57.7 | 2.82 | 1022.1 | $20,442 | 8.31 |
| 23 | `min_5|inside_va|immediate|fixed_20pt|1R|full|BOTH` | 45 | 73.3 | 2.75 | 420.0 | $8,400 | 9.33 |
| 24 | `min_10|above_vah|immediate|atr_1x|1R|morning|BOTH` | 117 | 73.5 | 2.74 | 486.6 | $9,732 | 4.16 |
| 25 | `min_5|any|immediate|atr_1x|2R|morning|SHORT` | 256 | 58.2 | 2.69 | 1822.7 | $36,455 | 7.12 |
| 26 | `min_10|above_vah|immediate|fixed_20pt|1R|morning|BOTH` | 117 | 72.6 | 2.66 | 1060.0 | $21,200 | 9.06 |
| 27 | `min_10|above_vah|immediate|fixed_20pt|1R|full|BOTH` | 136 | 72.1 | 2.61 | 1208.5 | $24,170 | 8.89 |
| 28 | `min_10|any|immediate|atr_1x|2R|full|SHORT` | 290 | 58.6 | 2.58 | 2070.2 | $41,405 | 7.14 |
| 29 | `min_5|above_vah|immediate|atr_1x|2R|morning|SHORT` | 121 | 58.7 | 2.57 | 741.8 | $14,835 | 6.13 |
| 30 | `min_20|any|immediate|fixed_20pt|1R|full|BOTH` | 285 | 71.9 | 2.56 | 2500.0 | $50,000 | 8.77 |

## 4. Analysis by Parameter Axis

### Zone Size (min_ticks)

| min_ticks | Trades | WR% | PF | Total Pts | Avg Pts |
|------------------------------|--------|-----|------|-----------|---------|
| 3.0 | 340.0 | 68.2 | 2.16 | 2488.5 | 7.32 |
| 5.0 | 40513.0 | 49.2 | 1.31 | 152374.4 | 3.76 |
| 10.0 | 36822.0 | 49.2 | 1.34 | 150502.9 | 4.09 |
| 20.0 | 285.0 | 71.9 | 2.56 | 2500.0 | 8.77 |

### Zone Location

| zone_location | Trades | WR% | PF | Total Pts | Avg Pts |
|------------------------------|--------|-----|------|-----------|---------|
| above_vah | 17826 | 46.7 | 1.18 | 38904.6 | 2.18 |
| any | 42527 | 49.8 | 1.33 | 169913.6 | 4.0 |
| below_val | 17562 | 50.9 | 1.49 | 98627.6 | 5.62 |
| inside_va | 45 | 73.3 | 2.75 | 420.0 | 9.33 |

### Entry Model

| entry_model | Trades | WR% | PF | Total Pts | Avg Pts |
|------------------------------|--------|-----|------|-----------|---------|
| acceptance_2 | 235 | 54.5 | 1.2 | 420.0 | 1.79 |
| immediate | 40555 | 57.2 | 1.7 | 299365.7 | 7.38 |
| reversal_bar | 37170 | 40.8 | 1.02 | 8080.1 | 0.22 |

### Stop Model

| stop_model | Trades | WR% | PF | Total Pts | Avg Pts |
|------------------------------|--------|-----|------|-----------|---------|
| atr_1x | 25256 | 50.2 | 1.46 | 59043.7 | 2.34 |
| fixed_20pt | 27110 | 49.4 | 1.32 | 90467.2 | 3.34 |
| fixed_40pt | 25256 | 48.2 | 1.3 | 153820.9 | 6.09 |
| opposite_zone | 338 | 68.3 | 3.56 | 4534.0 | 13.41 |

### Target Model

| target_model | Trades | WR% | PF | Total Pts | Avg Pts |
|------------------------------|--------|-----|------|-----------|---------|
| 1R | 39400 | 56.0 | 1.29 | 115141.0 | 2.92 |
| 2R | 37884 | 42.4 | 1.38 | 198345.0 | 5.24 |
| prior_poc | 338 | 19.2 | 0.41 | -9502.1 | -28.11 |
| zone_fill | 338 | 77.8 | 3.6 | 3881.9 | 11.48 |

### Time Window

| time_window | Trades | WR% | PF | Total Pts | Avg Pts |
|------------------------------|--------|-----|------|-----------|---------|
| after_ib | 273 | 74.4 | 2.92 | 2668.5 | 9.77 |
| full | 43271 | 49.6 | 1.33 | 171995.7 | 3.97 |
| morning | 34416 | 48.8 | 1.32 | 133201.6 | 3.87 |

### Direction

| direction | Trades | WR% | PF | Total Pts | Avg Pts |
|------------------------------|--------|-----|------|-----------|---------|
| BOTH | 29132 | 51.8 | 1.41 | 138114.9 | 4.74 |
| LONG | 24684 | 45.7 | 1.15 | 46469.5 | 1.88 |
| SHORT | 24144 | 50.2 | 1.45 | 123281.4 | 5.11 |

## 5. VERDICT

**VIABLE** — Best config: `min_10|above_vah|immediate|atr_1x|2R|morning|BOTH`
  - 117 trades, 69.2% WR, 4.49 PF, $22,525

**Recommended configuration:**
  - Min zone size: 10 ticks
  - Zone location: above_vah
  - Entry model: immediate
  - Stop: atr_1x
  - Target: 2R
  - Time window: morning
  - Direction: BOTH
