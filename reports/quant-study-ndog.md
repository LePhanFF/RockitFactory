# NDOG (New Day Opening Gap) Quantitative Study - NQ Futures

**Date**: 2026-03-12
**Instrument**: NQ (E-mini NASDAQ-100)
**Point Value**: $20.0/point
**Data Period**: 2025-02-21 to 2026-03-12
**Total Sessions**: 272
**Configurations Tested**: 736
**Configs with >= 5 trades**: 736

## 1. Gap Fill Frequency Analysis

### Gap Size Distribution
- Mean |NDOG|: 46.8 pts
- Median |NDOG|: 19.8 pts
- Std Dev: 81.1 pts
- Min: 0.0 pts, Max: 727.5 pts
- Direction: UP=136, DOWN=136

### Overall Fill Rates
- Full gap fill within RTH: 72.4% (197/272)
- Full fill by 11:00: 63.2%
- Full fill by 13:00: 67.3%
- Half gap fill within RTH: 74.6%

### Fill Rate by Gap Size

| Gap Size | N | RTH Fill | By 11:00 | By 13:00 | Half RTH |
|----------|---|----------|----------|----------|----------|
| 0-10 | 87 | 75.9% | 69.0% | 71.3% | 77.0% |
| 10-25 | 70 | 84.3% | 75.7% | 81.4% | 87.1% |
| 25-50 | 48 | 68.8% | 62.5% | 62.5% | 68.8% |
| 50-100 | 34 | 61.8% | 58.8% | 58.8% | 64.7% |
| 100+ | 31 | 58.1% | 29.0% | 45.2% | 64.5% |

### Fill Rate by Direction

| Direction | N | RTH Fill | By 11:00 | Half RTH |
|-----------|---|----------|----------|----------|
| UP | 136 | 69.1% | 60.3% | 72.1% |
| DOWN | 136 | 75.7% | 66.2% | 77.2% |

### Fill Rate by Day of Week

| Day | N | RTH Fill | By 11:00 | Avg |NDOG| |
|-----|---|----------|----------|-------------|
| Mon | 55 | 61.8% | 49.1% | 90.2 pts |
| Tue | 55 | 78.2% | 72.7% | 18.1 pts |
| Wed | 55 | 78.2% | 67.3% | 33.2 pts |
| Thu | 53 | 73.6% | 62.3% | 55.1 pts |
| Fri | 54 | 70.4% | 64.8% | 37.2 pts |

### Time-of-Fill Distribution
- Mean fill time: 37 min after RTH open
- Median fill time: 0 min

## 2. Strategy Results Matrix (Top 50 by Profit Factor)

| # | Config | Trades | WR% | PF | Total PnL | Avg PnL | Max DD |
|---|--------|--------|-----|-----|-----------|---------|--------|
| 1 | rth_open|gap>=10|fixed_75|full_fill|ts=1300|+VWAP|+BIAS|noMon | 13 | 100.0% | inf | $24,542 | $1,888 | $0 |
| 2 | rth_open|gap>=10|fixed_75|full_fill|ts=eod|+VWAP|+BIAS|noMon | 13 | 100.0% | inf | $21,137 | $1,626 | $0 |
| 3 | rth_open|gap>=10|fixed_75|half_fill|ts=1300|+VWAP|+BIAS|noMon | 13 | 100.0% | inf | $13,617 | $1,047 | $0 |
| 4 | rth_open|gap>=10|fixed_75|half_fill|ts=eod|+VWAP|+BIAS|noMon | 13 | 100.0% | inf | $13,617 | $1,047 | $0 |
| 5 | rth_open|gap>=20|fixed_50|full_fill|ts=1300|+VWAP|+BIAS|noMon | 9 | 100.0% | inf | $20,478 | $2,275 | $0 |
| 6 | rth_open|gap>=20|fixed_50|full_fill|ts=eod|+VWAP|+BIAS|noMon | 9 | 100.0% | inf | $17,073 | $1,897 | $0 |
| 7 | rth_open|gap>=20|fixed_50|half_fill|ts=1300|+VWAP|+BIAS|noMon | 9 | 100.0% | inf | $11,613 | $1,290 | $0 |
| 8 | rth_open|gap>=20|fixed_50|half_fill|ts=eod|+VWAP|+BIAS|noMon | 9 | 100.0% | inf | $11,613 | $1,290 | $0 |
| 9 | rth_open|gap>=20|fixed_75|full_fill|ts=1300|+VWAP|+BIAS|noMon | 9 | 100.0% | inf | $20,478 | $2,275 | $0 |
| 10 | rth_open|gap>=20|fixed_75|full_fill|ts=eod|+VWAP|+BIAS|noMon | 9 | 100.0% | inf | $17,073 | $1,897 | $0 |
| 11 | rth_open|gap>=20|fixed_75|half_fill|ts=1300|+VWAP|+BIAS|noMon | 9 | 100.0% | inf | $11,613 | $1,290 | $0 |
| 12 | rth_open|gap>=20|fixed_75|half_fill|ts=eod|+VWAP|+BIAS|noMon | 9 | 100.0% | inf | $11,613 | $1,290 | $0 |
| 13 | rth_open|gap>=10|fixed_50|full_fill|ts=1300|+VWAP|+BIAS|noMon | 13 | 92.3% | 23.63 | $22,947 | $1,765 | $-1,014 |
| 14 | rth_open|gap>=10|fixed_75|full_fill|ts=1300|+VWAP|+BIAS | 20 | 95.0% | 21.89 | $31,623 | $1,581 | $-1,514 |
| 15 | rth_open|gap>=10|fixed_50|full_fill|ts=eod|+VWAP|+BIAS|noMon | 13 | 92.3% | 20.27 | $19,542 | $1,503 | $-1,014 |
| 16 | rth_open|gap>=10|fixed_75|full_fill|ts=eod|+VWAP|+BIAS | 20 | 95.0% | 19.64 | $28,218 | $1,411 | $-1,514 |
| 17 | rth_open|gap>=20|fixed_75|full_fill|ts=1300|+VWAP|+BIAS | 15 | 93.3% | 18.21 | $26,064 | $1,738 | $-1,514 |
| 18 | or_close|gap>=10|fixed_75|full_fill|ts=1300|+VWAP|+BIAS | 19 | 94.7% | 17.86 | $25,522 | $1,343 | $-1,514 |
| 19 | or_close|gap>=10|fixed_75|full_fill|ts=eod|+VWAP|+BIAS | 19 | 94.7% | 16.91 | $24,082 | $1,267 | $-1,514 |
| 20 | rth_open|gap>=20|fixed_75|full_fill|ts=eod|+VWAP|+BIAS | 15 | 93.3% | 15.96 | $22,658 | $1,511 | $-1,514 |
| 21 | or_close|gap>=20|fixed_75|full_fill|ts=1300|+VWAP|+BIAS | 14 | 92.9% | 15.23 | $21,548 | $1,539 | $-1,514 |
| 22 | or_close|gap>=20|fixed_75|full_fill|ts=eod|+VWAP|+BIAS | 14 | 92.9% | 14.28 | $20,108 | $1,436 | $-1,514 |
| 23 | rth_open|gap>=10|fixed_50|half_fill|ts=1300|+VWAP|+BIAS|noMon | 13 | 92.3% | 13.15 | $12,319 | $948 | $-1,014 |
| 24 | rth_open|gap>=10|fixed_50|half_fill|ts=eod|+VWAP|+BIAS|noMon | 13 | 92.3% | 13.15 | $12,319 | $948 | $-1,014 |
| 25 | rth_open|gap>=20|fixed_50|full_fill|ts=1300|+VWAP|+BIAS | 15 | 86.7% | 12.92 | $24,178 | $1,612 | $-1,014 |
| 26 | rth_open|gap>=20|fixed_75|full_fill|ts=1300|+VWAP | 42 | 88.1% | 12.08 | $83,853 | $1,996 | $-1,692 |
| 27 | rth_open|gap>=10|fixed_75|half_fill|ts=1300|+VWAP|+BIAS | 20 | 95.0% | 11.8 | $16,358 | $818 | $-1,514 |
| 28 | rth_open|gap>=10|fixed_75|half_fill|ts=eod|+VWAP|+BIAS | 20 | 95.0% | 11.8 | $16,358 | $818 | $-1,514 |
| 29 | rth_open|gap>=20|fixed_50|full_fill|ts=eod|+VWAP|+BIAS | 15 | 86.7% | 11.24 | $20,774 | $1,385 | $-1,014 |
| 30 | rth_open|gap>=10|fixed_75|full_fill|ts=1300|+VWAP | 51 | 88.2% | 11.11 | $91,866 | $1,801 | $-1,692 |
| 31 | rth_open|gap>=20|fixed_75|full_fill|ts=eod|+VWAP | 42 | 85.7% | 10.72 | $80,918 | $1,927 | $-1,692 |
| 32 | or_close|gap>=10|fixed_75|full_fill|ts=1300|+VWAP|+BIAS|noMon | 14 | 92.9% | 10.64 | $14,598 | $1,043 | $-1,514 |
| 33 | or_close|gap>=10|fixed_75|half_fill|ts=1300|+VWAP|+BIAS | 19 | 94.7% | 10.44 | $14,297 | $752 | $-1,514 |
| 34 | or_close|gap>=10|fixed_75|half_fill|ts=eod|+VWAP|+BIAS | 19 | 94.7% | 10.44 | $14,297 | $752 | $-1,514 |
| 35 | rth_open|gap>=10|fixed_50|full_fill|ts=1300|+VWAP|+BIAS | 20 | 85.0% | 10.25 | $28,143 | $1,407 | $-1,014 |
| 36 | rth_open|gap>=10|fixed_75|full_fill|ts=eod|+VWAP | 51 | 86.3% | 10.04 | $88,931 | $1,744 | $-1,692 |
| 37 | rth_open|gap>=20|fixed_75|half_fill|ts=1300|+VWAP|+BIAS | 15 | 93.3% | 9.99 | $13,614 | $908 | $-1,514 |
| 38 | rth_open|gap>=20|fixed_75|half_fill|ts=eod|+VWAP|+BIAS | 15 | 93.3% | 9.99 | $13,614 | $908 | $-1,514 |
| 39 | or_close|gap>=20|fixed_75|half_fill|ts=1300|+VWAP|+BIAS | 14 | 92.9% | 9.15 | $12,345 | $882 | $-1,514 |
| 40 | or_close|gap>=20|fixed_75|half_fill|ts=eod|+VWAP|+BIAS | 14 | 92.9% | 9.15 | $12,345 | $882 | $-1,514 |
| 41 | rth_open|gap>=10|fixed_50|full_fill|ts=eod|+VWAP|+BIAS | 20 | 85.0% | 9.13 | $24,738 | $1,237 | $-1,014 |
| 42 | rth_open|gap>=20|fixed_75|half_fill|ts=1300|+VWAP | 42 | 88.1% | 8.82 | $47,405 | $1,129 | $-1,514 |
| 43 | rth_open|gap>=20|fixed_75|half_fill|ts=eod|+VWAP | 42 | 88.1% | 8.82 | $47,405 | $1,129 | $-1,514 |
| 44 | or_close|gap>=10|fixed_75|full_fill|ts=eod|+VWAP|+BIAS|noMon | 14 | 92.9% | 8.39 | $11,193 | $799 | $-1,514 |
| 45 | or_close|gap>=20|fixed_75|full_fill|ts=1300|+VWAP|+BIAS|noMon | 10 | 90.0% | 8.22 | $10,929 | $1,093 | $-1,514 |
| 46 | rth_open|gap>=10|fixed_75|half_fill|ts=1300|+VWAP | 51 | 88.2% | 7.68 | $50,598 | $992 | $-1,514 |
| 47 | rth_open|gap>=10|fixed_75|half_fill|ts=eod|+VWAP | 51 | 88.2% | 7.68 | $50,598 | $992 | $-1,514 |
| 48 | or_close|gap>=10|fixed_75|full_fill|ts=eod|+VWAP | 44 | 84.1% | 7.31 | $66,845 | $1,519 | $-1,847 |
| 49 | rth_open|gap>=20|fixed_50|full_fill|ts=eod|+VWAP | 42 | 73.8% | 7.29 | $70,148 | $1,670 | $-2,028 |
| 50 | or_close|gap>=10|fixed_75|full_fill|ts=1300|+VWAP | 44 | 84.1% | 7.23 | $66,000 | $1,500 | $-2,657 |

## 3. Best Configuration

**rth_open|gap>=10|fixed_75|full_fill|ts=1300|+VWAP|+BIAS|noMon**

- Trades: 13
- Win Rate: 100.0%
- Profit Factor: inf
- Total PnL: $24,541.70
- Avg PnL/trade: $1,887.82
- Avg Win: $1,887.82
- Avg Loss: $0.00
- Max Drawdown: $0.00

## 4. Direction Analysis (Best Config)

| Direction | N | WR% | PF | Total PnL | Avg PnL |
|-----------|---|-----|-----|-----------|---------|
| LONG | 5 | 100.0% | inf | $4,810 | $962 |
| SHORT | 8 | 100.0% | inf | $19,732 | $2,467 |

## 5. Gap Size Analysis (Best Config)

| Gap Size | N | WR% | PF | Total PnL | Avg PnL |
|----------|---|-----|-----|-----------|---------|
| 10-25 | 6 | 100.0% | inf | $8,355 | $1,393 |
| 25-50 | 3 | 100.0% | inf | $4,068 | $1,356 |
| 50-100 | 1 | 100.0% | inf | $1,061 | $1,061 |
| 100-500 | 3 | 100.0% | inf | $11,058 | $3,686 |

## 6. Day-of-Week Analysis (Best Config)

| Day | N | WR% | PF | Total PnL | Avg PnL |
|-----|---|-----|-----|-----------|---------|
| Tue | 2 | 100.0% | inf | $2,962 | $1,481 |
| Wed | 5 | 100.0% | inf | $6,954 | $1,391 |
| Thu | 4 | 100.0% | inf | $8,484 | $2,121 |
| Fri | 2 | 100.0% | inf | $6,142 | $3,071 |

## 7. Top 5 Winners (Best Config)

| Date | Dir | Gap | Entry | Exit | Reason | PnL |
|------|-----|-----|-------|------|--------|-----|
| 2025-07-31 | SHORT | 222 | 24244.75 | 23977.50 | TARGET | $5,331 |
| 2025-10-31 | SHORT | 280 | 26460.75 | 26206.00 | TIME_STOP | $5,081 |
| 2025-11-12 | SHORT | 22 | 26037.00 | 25903.00 | TARGET | $2,666 |
| 2026-01-28 | SHORT | 35 | 26255.25 | 26140.75 | TIME_STOP | $2,276 |
| 2026-02-03 | SHORT | 20 | 25938.50 | 25856.50 | TARGET | $1,626 |

## 8. Top 5 Losers (Best Config)

| Date | Dir | Gap | Entry | Exit | Reason | PnL |
|------|-----|-----|-------|------|--------|-----|
| 2026-01-23 | LONG | 57 | 25608.00 | 25661.75 | TARGET | $1,061 |
| 2025-04-09 | LONG | 14 | 17902.75 | 17942.75 | TARGET | $786 |
| 2025-03-05 | SHORT | 158 | 21341.50 | 21308.50 | TARGET | $646 |
| 2025-05-28 | SHORT | 14 | 22204.50 | 22174.75 | TARGET | $581 |
| 2025-10-23 | LONG | 28 | 25273.25 | 25296.75 | TARGET | $456 |

## 9. Comparison to NWOG

| Metric | NDOG (Daily) | NWOG (Weekly) |
|--------|-------------|---------------|
| Frequency | ~259/year | ~52/year |
| Avg Gap Size | 46.8 pts | ~100-200 pts (weekend) |
| RTH Fill Rate | 72.4% | ~50% (NWOG study) |
| Mon RTH Fill Rate | 61.8% | N/A |
| Tue-Fri RTH Fill Rate | 75.1% | N/A |

## 10. Entry Type Comparison (gap>=20, fixed_50 stop, full_fill target, eod time stop)

| Entry | N | WR% | PF | Total PnL |
|-------|---|-----|-----|-----------|
| rth_open | 95 | 42.1% | 1.8 | $44,370 |
| or_close | 93 | 37.6% | 1.37 | $21,779 |
| vwap_1000 | 28 | 57.1% | 1.81 | $9,885 |
| acceptance_1000 | 87 | 39.1% | 1.48 | $26,063 |

## 11. Stop Model Comparison (rth_open entry, gap>=20, full_fill target, eod time stop)

| Stop | N | WR% | PF | Total PnL |
|------|---|-----|-----|-----------|
| fixed_50 | 95 | 42.1% | 1.8 | $44,370 |
| fixed_75 | 95 | 53.7% | 1.78 | $51,540 |
| atr14 | 95 | 16.8% | 2.08 | $21,337 |
| or_spike | 95 | 48.4% | 1.42 | $32,596 |

## 12. Target Model Comparison (rth_open entry, gap>=20, fixed_50 stop, eod time stop)

| Target | N | WR% | PF | Total PnL |
|--------|---|-----|-----|-----------|
| full_fill | 95 | 42.1% | 1.8 | $44,370 |
| half_fill | 95 | 50.5% | 1.41 | $19,168 |
| 2R | 135 | 40.7% | 1.33 | $27,006 |

## 13. Time Stop Comparison (rth_open entry, gap>=20, fixed_50 stop, full_fill target)

| Time Stop | N | WR% | PF | Total PnL |
|-----------|---|-----|-----|-----------|
| 1100 | 95 | 44.2% | 1.6 | $32,446 |
| 1300 | 95 | 42.1% | 1.73 | $40,816 |
| eod | 95 | 42.1% | 1.8 | $44,370 |

## 14. Recommendation

**DEPLOY** - The best robust NDOG configuration shows a viable edge:
- 42 trades, 88.1% WR, PF 12.08, $83,853 total PnL
- Config: rth_open|gap>=20|fixed_75|full_fill|ts=1300|+VWAP

Best overall (low sample): 13 trades, 100.0% WR, PF inf, $24,542
- Config: rth_open|gap>=10|fixed_75|full_fill|ts=1300|+VWAP|+BIAS|noMon

Next steps:
1. Implement as a strategy in `rockit_core.strategies`
2. Add to `configs/strategies.yaml`
3. Run through the full filter pipeline (bias, day type, agent)
4. A/B test against existing portfolio
