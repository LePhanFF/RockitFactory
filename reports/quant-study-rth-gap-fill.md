# RTH Gap Fill Strategy — Quant Study

**Date**: 2026-03-12
**Instrument**: NQ futures
**Sessions**: 272
**Slippage**: 0.5 pts round-trip (2 ticks)

## 1. Gap Frequency Distribution

- **Total sessions**: 272
- **Mean gap**: 136.3 pts
- **Median gap**: 92.8 pts
- **Std dev**: 135.5 pts
- **Min/Max**: 0.0 / 835.5 pts
- **UP gaps**: 150 (55%)
- **DOWN gaps**: 122 (45%)

### Gap Size Distribution

| Min Gap (pts) | Sessions | % of Total |
|---:|---:|---:|
| >= 0 | 272 | 100.0% |
| >= 5 | 265 | 97.4% |
| >= 10 | 256 | 94.1% |
| >= 15 | 252 | 92.6% |
| >= 20 | 246 | 90.4% |
| >= 30 | 227 | 83.5% |
| >= 50 | 183 | 67.3% |
| >= 75 | 153 | 56.2% |
| >= 100 | 127 | 46.7% |
| >= 150 | 90 | 33.1% |

## 2. Fill Rate Analysis

- **Overall fill rate**: 58.8%
- **UP gap fill rate**: 58.7%
- **DOWN gap fill rate**: 59.0%
- **Median fill time**: 18 minutes
- **Fill within 15 min**: 48.8%
- **Fill within 30 min**: 61.9%
- **Fill within 60 min**: 74.4%
- **Fill within 120 min**: 83.8%

### Fill Rate by Gap Size

| Min Gap | Count | Fill Rate | UP Fill | DOWN Fill |
|---:|---:|---:|---:|---:|
| >= 5 | 265 | 57.7% | 57.5% | 58.0% |
| >= 10 | 256 | 56.2% | 56.0% | 56.5% |
| >= 15 | 252 | 55.6% | 55.4% | 55.8% |
| >= 20 | 246 | 54.5% | 53.7% | 55.4% |
| >= 30 | 227 | 51.5% | 50.4% | 52.9% |
| >= 50 | 183 | 48.1% | 45.4% | 51.2% |

## 3. Top 30 Configurations by Profit Factor

Minimum 10 trades required.

| # | Gap | Dir | Entry | VWAP | Stop | Target | TimeStp | Trades | WR | PF | PnL ($) | MaxDD |
|---|-----|-----|-------|------|------|--------|---------|-----:|---:|---:|--------:|------:|
| 1 | gap_50 | up_only | rth_open | vwap_confirm | fixed_50pt | half_fill | ts_1100 | 10 | 100.0% | 99.99+ | $12,512 | $0 |
| 2 | gap_50 | up_only | rth_open | vwap_confirm | fixed_50pt | half_fill | ts_1200 | 10 | 100.0% | 99.99+ | $12,512 | $0 |
| 3 | gap_50 | up_only | rth_open | vwap_confirm | fixed_50pt | half_fill | ts_1300 | 10 | 100.0% | 99.99+ | $12,512 | $0 |
| 4 | gap_50 | up_only | rth_open | vwap_confirm | fixed_50pt | half_fill | no_ts | 10 | 100.0% | 99.99+ | $12,512 | $0 |
| 5 | gap_50 | up_only | rth_open | vwap_confirm | fixed_50pt | 1R | ts_1100 | 10 | 100.0% | 99.99+ | $9,900 | $0 |
| 6 | gap_50 | up_only | rth_open | vwap_confirm | fixed_50pt | 1R | ts_1200 | 10 | 100.0% | 99.99+ | $9,900 | $0 |
| 7 | gap_50 | up_only | rth_open | vwap_confirm | fixed_50pt | 1R | ts_1300 | 10 | 100.0% | 99.99+ | $9,900 | $0 |
| 8 | gap_50 | up_only | rth_open | vwap_confirm | fixed_50pt | 1R | no_ts | 10 | 100.0% | 99.99+ | $9,900 | $0 |
| 9 | gap_50 | up_only | rth_open | vwap_confirm | fixed_75pt | half_fill | ts_1100 | 10 | 100.0% | 99.99+ | $12,512 | $0 |
| 10 | gap_50 | up_only | rth_open | vwap_confirm | fixed_75pt | half_fill | ts_1200 | 10 | 100.0% | 99.99+ | $12,512 | $0 |
| 11 | gap_50 | up_only | rth_open | vwap_confirm | fixed_75pt | half_fill | ts_1300 | 10 | 100.0% | 99.99+ | $12,512 | $0 |
| 12 | gap_50 | up_only | rth_open | vwap_confirm | fixed_75pt | half_fill | no_ts | 10 | 100.0% | 99.99+ | $12,512 | $0 |
| 13 | gap_50 | up_only | rth_open | vwap_confirm | gap_1.5x | half_fill | ts_1100 | 10 | 100.0% | 99.99+ | $12,512 | $0 |
| 14 | gap_50 | up_only | rth_open | vwap_confirm | gap_1.5x | half_fill | ts_1200 | 10 | 100.0% | 99.99+ | $12,512 | $0 |
| 15 | gap_50 | up_only | rth_open | vwap_confirm | gap_1.5x | half_fill | ts_1300 | 10 | 100.0% | 99.99+ | $12,512 | $0 |
| 16 | gap_50 | up_only | rth_open | vwap_confirm | gap_1.5x | half_fill | no_ts | 10 | 100.0% | 99.99+ | $12,512 | $0 |
| 17 | gap_50 | up_only | rth_open | vwap_confirm | gap_2x | full_fill | no_ts | 10 | 100.0% | 99.99+ | $23,660 | $0 |
| 18 | gap_50 | up_only | rth_open | vwap_confirm | gap_2x | half_fill | ts_1100 | 10 | 100.0% | 99.99+ | $12,512 | $0 |
| 19 | gap_50 | up_only | rth_open | vwap_confirm | gap_2x | half_fill | ts_1200 | 10 | 100.0% | 99.99+ | $12,512 | $0 |
| 20 | gap_50 | up_only | rth_open | vwap_confirm | gap_2x | half_fill | ts_1300 | 10 | 100.0% | 99.99+ | $12,512 | $0 |
| 21 | gap_50 | up_only | rth_open | vwap_confirm | gap_2x | half_fill | no_ts | 10 | 100.0% | 99.99+ | $12,512 | $0 |
| 22 | gap_50 | up_only | rth_open | vwap_confirm | gap_2x | full_fill | ts_1300 | 10 | 90.0% | 99.99+ | $21,850 | $-180 |
| 23 | gap_50 | up_only | rth_open | vwap_confirm | fixed_50pt | full_fill | ts_1200 | 10 | 90.0% | 22.29 | $21,500 | $-1,010 |
| 24 | gap_50 | up_only | rth_open | vwap_confirm | fixed_50pt | full_fill | ts_1300 | 10 | 90.0% | 21.81 | $21,020 | $-1,010 |
| 25 | gap_50 | up_only | rth_open | vwap_confirm | fixed_50pt | full_fill | no_ts | 10 | 90.0% | 21.64 | $20,850 | $-1,010 |
| 26 | gap_50 | up_only | rth_open | vwap_confirm | fixed_50pt | full_fill | ts_1100 | 10 | 90.0% | 17.38 | $16,545 | $-1,010 |
| 27 | gap_50 | both | rth_open | vwap_confirm | gap_2x | half_fill | no_ts | 22 | 95.5% | 15.81 | $31,998 | $-2,160 |
| 28 | gap_50 | up_only | rth_open | vwap_confirm | fixed_75pt | full_fill | ts_1200 | 10 | 90.0% | 14.91 | $21,000 | $-1,510 |
| 29 | gap_50 | up_only | rth_open | vwap_confirm | fixed_75pt | full_fill | ts_1300 | 10 | 90.0% | 14.59 | $20,520 | $-1,510 |
| 30 | gap_50 | up_only | rth_open | vwap_confirm | fixed_75pt | full_fill | no_ts | 10 | 90.0% | 14.48 | $20,350 | $-1,510 |

## 4. Top 15 Configurations by Total PnL

| # | Gap | Dir | Entry | VWAP | Stop | Target | TimeStp | Trades | WR | PF | PnL ($) | MaxDD |
|---|-----|-----|-------|------|------|--------|---------|-----:|---:|---:|--------:|------:|
| 1 | gap_50 | both | rth_open | no_vwap | gap_2x | 1R | no_ts | 183 | 57.4% | 1.66 | $155,045 | $-22,410 |
| 2 | gap_20 | both | rth_open | no_vwap | gap_2x | 1R | no_ts | 246 | 54.5% | 1.50 | $143,645 | $-24,475 |
| 3 | gap_50 | both | rth_open | no_vwap | gap_2x | 2R | no_ts | 183 | 53.6% | 1.57 | $142,360 | $-27,130 |
| 4 | gap_15 | both | rth_open | no_vwap | gap_2x | 1R | no_ts | 252 | 54.0% | 1.49 | $142,185 | $-24,475 |
| 5 | gap_10 | both | rth_open | no_vwap | gap_2x | 1R | no_ts | 256 | 53.9% | 1.49 | $142,135 | $-24,475 |
| 6 | gap_5 | both | rth_open | no_vwap | gap_2x | 1R | no_ts | 265 | 53.6% | 1.49 | $141,685 | $-24,165 |
| 7 | gap_30 | both | rth_open | no_vwap | gap_2x | 1R | no_ts | 227 | 54.2% | 1.51 | $141,135 | $-24,475 |
| 8 | gap_30 | both | rth_open | no_vwap | gap_2x | 2R | no_ts | 227 | 49.8% | 1.46 | $135,850 | $-27,865 |
| 9 | gap_20 | both | rth_open | no_vwap | gap_2x | 2R | no_ts | 246 | 48.0% | 1.43 | $131,910 | $-27,865 |
| 10 | gap_10 | both | rth_open | no_vwap | gap_2x | 2R | no_ts | 256 | 47.3% | 1.42 | $130,950 | $-27,865 |
| 11 | gap_15 | both | rth_open | no_vwap | gap_2x | 2R | no_ts | 252 | 47.2% | 1.42 | $129,990 | $-27,865 |
| 12 | gap_5 | both | rth_open | no_vwap | gap_2x | 2R | no_ts | 265 | 46.0% | 1.41 | $128,980 | $-27,235 |
| 13 | gap_50 | both | rth_open | no_vwap | gap_2x | 1R | ts_1300 | 183 | 58.5% | 1.60 | $128,690 | $-17,890 |
| 14 | gap_50 | both | rth_open | no_vwap | gap_2x | 1R | ts_1200 | 183 | 60.7% | 1.64 | $127,455 | $-17,345 |
| 15 | gap_50 | both | rth_open | no_vwap | gap_1.5x | 1R | no_ts | 183 | 56.8% | 1.50 | $121,885 | $-27,065 |

## 5. Gap Size Analysis

| Gap Min | Configs | Best PF | Best WR | Best PnL | Avg PF | Median PF |
|---------|--------:|--------:|--------:|---------:|-------:|----------:|
| gap_10 | 1920 | 4.01 | 84.0% | $12,100 | 1.51 | 1.36 |
| gap_15 | 1920 | 4.01 | 84.0% | $12,100 | 1.50 | 1.35 |
| gap_20 | 1920 | 4.59 | 87.0% | $12,465 | 1.51 | 1.36 |
| gap_30 | 1920 | 5.54 | 88.9% | $12,168 | 1.54 | 1.36 |
| gap_5 | 1920 | 3.94 | 85.2% | $11,882 | 1.49 | 1.35 |
| gap_50 | 1920 | inf | 100.0% | $12,512 | 1.90 | 1.43 |

## 6. Direction Analysis

| Direction | Configs | Best PF | Best WR | Best PnL | Avg PF |
|-----------|--------:|--------:|--------:|---------:|-------:|
| both | 3840 | 15.81 | 95.5% | $31,998 | 1.54 |
| down_only | 3840 | 10.02 | 91.7% | $19,485 | 1.47 |
| up_only | 3840 | inf | 100.0% | $12,512 | 1.72 |

## 7. Entry Timing Comparison

| Entry | Configs | Best PF | Best WR | Best PnL | Avg PF |
|-------|--------:|--------:|--------:|---------:|-------:|
| ib_close | 2880 | 2.82 | 66.7% | $23,638 | 1.40 |
| or_close | 2880 | 3.32 | 58.3% | $55,130 | 1.43 |
| rth_open | 2880 | inf | 100.0% | $12,512 | 1.97 |
| ten_oclock | 2880 | 3.90 | 62.9% | $52,060 | 1.50 |

## 8. VWAP Confirmation Impact

| VWAP | Configs | Best PF | Best WR | Best PnL | Avg PF |
|------|--------:|--------:|--------:|---------:|-------:|
| no_vwap | 5760 | 2.16 | 63.9% | $45,280 | 1.26 |
| vwap_confirm | 5760 | inf | 100.0% | $12,512 | 1.90 |

## 9. Stop Optimization

| Stop | Configs | Best PF | Best WR | Best PnL | Avg PF |
|------|--------:|--------:|--------:|---------:|-------:|
| fixed_30pt | 2304 | 9.97 | 70.0% | $16,420 | 1.31 |
| fixed_50pt | 2304 | inf | 100.0% | $12,512 | 1.48 |
| fixed_75pt | 2304 | inf | 100.0% | $12,512 | 1.62 |
| gap_1.5x | 2304 | inf | 100.0% | $12,512 | 1.70 |
| gap_2x | 2304 | inf | 100.0% | $23,660 | 1.78 |

## 10. Target Optimization

| Target | Configs | Best PF | Best WR | Best PnL | Avg PF |
|--------|--------:|--------:|--------:|---------:|-------:|
| 1R | 2880 | inf | 100.0% | $9,900 | 1.52 |
| 2R | 2880 | 7.60 | 70.0% | $27,205 | 1.49 |
| full_fill | 2880 | inf | 100.0% | $23,660 | 1.66 |
| half_fill | 2880 | inf | 100.0% | $12,512 | 1.63 |

## 11. Time Stop Analysis

| Time Stop | Configs | Best PF | Best WR | Best PnL | Avg PF |
|-----------|--------:|--------:|--------:|---------:|-------:|
| no_ts | 2880 | inf | 100.0% | $12,512 | 1.60 |
| ts_1100 | 2880 | inf | 100.0% | $12,512 | 1.54 |
| ts_1200 | 2880 | inf | 100.0% | $12,512 | 1.56 |
| ts_1300 | 2880 | inf | 100.0% | $12,512 | 1.59 |

## 12. Verdict

### VIABLE

**Recommended Configuration:**
- Gap minimum: gap_50
- Direction: up_only
- Entry: rth_open
- VWAP: vwap_confirm
- Stop: fixed_50pt
- Target: half_fill
- Time stop: ts_1100

**Performance:**
- Trades: 10
- Win Rate: 100.0%
- Profit Factor: 99.99+
- Total PnL: $12,512
- Max Drawdown: $0
- Avg Win: $1,251
- Avg Loss: $0

**Highest PnL Configuration:**
- Config: gap_50, both, rth_open, no_vwap, gap_2x, 1R, no_ts
- Trades: 183, WR: 57.4%, PF: 1.66, PnL: $155,045

## 13. Comparison to NDOG Study

| Metric | NDOG (Overnight Gap) | RTH Gap Fill |
|--------|---------------------:|-------------:|
| Best PF | 12.08 | 99.99+ |
| Best WR | — | 100.0% |
| Total PnL | — | $12,512 |
| Mean gap size | Overnight (larger) | 136.3 pts |
| Fill rate (overall) | — | 58.8% |
| VWAP confirmation | Strongest predictor | See section 8 |
| Sessions available | Weekly (Mon only) | Daily (272) |

## 14. Key Observations

- **Gap size**: gap_50 has the highest average PF (1.90) across all configs.
- **Direction**: up_only has the highest average PF (1.72).
- **Entry timing**: rth_open has the highest average PF (1.97).
- **VWAP confirmation**: Improves average PF from 1.26 to 1.90 (+51%).
- **Stop**: gap_2x has the highest average PF (1.78).
- **Target**: full_fill has the highest average PF (1.66).
- **Fill rate**: 58.8% of all RTH gaps fill within RTH session.
- **Speed**: 48.8% of fills complete within 15 minutes, 74.4% within 60 minutes.
