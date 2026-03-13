# NWOG (New Week Opening Gap) — Comprehensive Quant Study

**Instrument**: NQ Futures ($20.0/point)
**Dataset**: 54 weeks identified from 273 sessions (Feb 2025 – Mar 2026)
**Slippage**: 1 tick/side (0.25 pts)
**Commission**: $5.0/RT
**Generated**: 2026-03-12 18:08

## 1. NWOG Frequency and Size Distribution

- **Total NWOGs identified**: 54
- **UP gaps**: 31 (57.4%)
- **DOWN gaps**: 23 (42.6%)
- **Mean gap size**: 181.7 pts
- **Median gap size**: 138.1 pts
- **Min / Max**: 3.2 / 789.5 pts
- **Std dev**: 160.7 pts

### Gap Size Distribution

| Size Bucket | Count | % | Avg Gap (pts) |
|-------------|-------|---|---------------|
| <10pts | 4 | 7.4% | 5.1 |
| 10-20pts | 1 | 1.9% | 15.0 |
| 20-30pts | 4 | 7.4% | 24.4 |
| 30-50pts | 5 | 9.3% | 43.0 |
| 50-100pts | 7 | 13.0% | 79.2 |
| 100+pts | 33 | 61.1% | 270.1 |

## 2. Gap Fill Rate Analysis

- **Monday RTH fill rate**: 29/54 (53.7%)
- **Full week fill rate**: 43/54 (79.6%)

### Fill Rate by Direction

| Direction | Count | Monday Fill % | Week Fill % | Avg Partial Fill % |
|-----------|-------|---------------|-------------|-------------------|
| UP | 31 | 35.5% (11/31) | 71.0% (22/31) | 55.8% |
| DOWN | 23 | 78.3% (18/23) | 91.3% (21/23) | 89.7% |

### Fill Rate by Gap Size

| Size Bucket | Count | Monday Fill % | Avg Partial % | Avg Fill Time (min) |
|-------------|-------|---------------|---------------|---------------------|
| <10pts | 4 | 100.0% | 100.0% | 0 |
| 10-20pts | 1 | 100.0% | 100.0% | 2 |
| 20-30pts | 4 | 75.0% | 77.6% | 2 |
| 30-50pts | 5 | 60.0% | 91.7% | 9 |
| 50-100pts | 7 | 71.4% | 76.6% | 27 |
| 100+pts | 33 | 39.4% | 60.3% | 145 |

### Monday Fill Time Distribution

- **Mean fill time**: 71 min from RTH open
- **Median fill time**: 19 min
- **Within first hour (60 min)**: 21/29 (72.4%)
- **Within 2 hours (120 min)**: 22/29 (75.9%)
- **After lunch (>210 min)**: 4/29

## 3. VWAP Confirmation Analysis (at 10:00)

Total with VWAP data: 54

| VWAP Confirms | Count | Monday Fill % | Avg Partial % |
|---------------|-------|---------------|---------------|
| Yes | 24 | 91.7% (22/24) | 98.6% |
| No | 30 | 23.3% (7/30) | 47.6% |

### VWAP Confirmation by Direction

| Direction | VWAP Confirms | Count | Monday Fill % |
|-----------|---------------|-------|---------------|
| UP | Yes | 9 | 77.8% (7/9) |
| UP | No | 22 | 18.2% (4/22) |
| DOWN | Yes | 15 | 100.0% (15/15) |
| DOWN | No | 8 | 37.5% (3/8) |

## 4. 30-Min Acceptance Analysis (>= 30% threshold)

| Acceptance >= 30% | Count | Monday Fill % | Avg Partial % |
|-------------------|-------|---------------|---------------|
| Yes | 19 | 94.7% (18/19) | 98.5% |
| No | 35 | 31.4% (11/35) | 54.9% |

### Combined VWAP + Acceptance

| VWAP | Acceptance | Count | Monday Fill % | Avg Partial % |
|------|------------|-------|---------------|---------------|
| Yes | Yes | 13 | 100.0% (13/13) | 100.0% |
| Yes | No | 11 | 81.8% (9/11) | 96.9% |
| No | Yes | 6 | 83.3% (5/6) | 95.4% |
| No | No | 24 | 8.3% (2/24) | 35.6% |

## 5. Trading Configuration Results

Tested 5400 configurations, 4890 with >= 3 trades.

### Top 20 by Profit Factor

| # | Config | Trades | WR% | PF | Net PnL | Avg Win | Avg Loss | Expectancy |
|---|--------|--------|-----|----|---------|---------|---------:|-----------:|
| 1 | C_VWAP_1000|g10|or_extreme_5|50pct_fill|t1300|UP_ONLY | 4 | 100.0% | inf | $1,615 | $404 | $0 | $404 |
| 2 | C_VWAP_1000|g10|or_extreme_5|50pct_fill|tEOD|UP_ONLY | 4 | 100.0% | inf | $1,615 | $404 | $0 | $404 |
| 3 | C_VWAP_1000|g20|or_extreme_5|50pct_fill|t1300|UP_ONLY | 4 | 100.0% | inf | $1,615 | $404 | $0 | $404 |
| 4 | C_VWAP_1000|g20|or_extreme_5|50pct_fill|tEOD|UP_ONLY | 4 | 100.0% | inf | $1,615 | $404 | $0 | $404 |
| 5 | C_VWAP_1000|g30|or_extreme_5|50pct_fill|t1300|UP_ONLY | 4 | 100.0% | inf | $1,615 | $404 | $0 | $404 |
| 6 | C_VWAP_1000|g30|or_extreme_5|50pct_fill|tEOD|UP_ONLY | 4 | 100.0% | inf | $1,615 | $404 | $0 | $404 |
| 7 | C_VWAP_1000|g50|or_extreme_5|50pct_fill|t1300|UP_ONLY | 3 | 100.0% | inf | $1,255 | $418 | $0 | $418 |
| 8 | C_VWAP_1000|g50|or_extreme_5|50pct_fill|tEOD|UP_ONLY | 3 | 100.0% | inf | $1,255 | $418 | $0 | $418 |
| 9 | D_ACCEPTANCE|g30|atr_1x|2R|t1100|UP_ONLY | 3 | 100.0% | inf | $3,696 | $1,232 | $0 | $1,232 |
| 10 | D_ACCEPTANCE|g30|atr_1x|2R|t1300|UP_ONLY | 3 | 100.0% | inf | $3,696 | $1,232 | $0 | $1,232 |
| 11 | D_ACCEPTANCE|g30|atr_1x|2R|tEOD|UP_ONLY | 3 | 100.0% | inf | $3,696 | $1,232 | $0 | $1,232 |
| 12 | D_ACCEPTANCE|g30|or_extreme_5|2R|tEOD|UP_ONLY | 3 | 100.0% | inf | $12,305 | $4,102 | $0 | $4,102 |
| 13 | D_ACCEPTANCE|g30|or_extreme_5|3R|tEOD|UP_ONLY | 3 | 100.0% | inf | $12,305 | $4,102 | $0 | $4,102 |
| 14 | D_ACCEPTANCE|g50|atr_1x|2R|t1100|UP_ONLY | 3 | 100.0% | inf | $3,696 | $1,232 | $0 | $1,232 |
| 15 | D_ACCEPTANCE|g50|atr_1x|2R|t1300|UP_ONLY | 3 | 100.0% | inf | $3,696 | $1,232 | $0 | $1,232 |
| 16 | D_ACCEPTANCE|g50|atr_1x|2R|tEOD|UP_ONLY | 3 | 100.0% | inf | $3,696 | $1,232 | $0 | $1,232 |
| 17 | D_ACCEPTANCE|g50|or_extreme_5|2R|tEOD|UP_ONLY | 3 | 100.0% | inf | $12,305 | $4,102 | $0 | $4,102 |
| 18 | D_ACCEPTANCE|g50|or_extreme_5|3R|tEOD|UP_ONLY | 3 | 100.0% | inf | $12,305 | $4,102 | $0 | $4,102 |
| 19 | E_VWAP_ACCEPT|g30|atr_1x|2R|t1100|UP_ONLY | 3 | 100.0% | inf | $3,696 | $1,232 | $0 | $1,232 |
| 20 | E_VWAP_ACCEPT|g30|atr_1x|2R|t1300|UP_ONLY | 3 | 100.0% | inf | $3,696 | $1,232 | $0 | $1,232 |

### Top 20 by Total PnL

| # | Config | Trades | WR% | PF | Net PnL | Expectancy |
|---|--------|--------|-----|----|---------|-----------:|
| 1 | B_OR_CLOSE|g10|fixed_75|full_fill|tEOD|DOWN_ONLY | 17 | 82.4% | 12.20 | $50,755 | $2,986 |
| 2 | B_OR_CLOSE|g20|fixed_75|full_fill|tEOD|DOWN_ONLY | 17 | 82.4% | 12.20 | $50,755 | $2,986 |
| 3 | B_OR_CLOSE|g20|fixed_75|3R|tEOD|BOTH | 49 | 57.1% | 2.55 | $49,055 | $1,001 |
| 4 | B_OR_CLOSE|g30|fixed_75|full_fill|tEOD|DOWN_ONLY | 16 | 81.2% | 11.76 | $48,735 | $3,046 |
| 5 | B_OR_CLOSE|g10|fixed_75|3R|tEOD|BOTH | 50 | 56.0% | 2.43 | $47,545 | $951 |
| 6 | B_OR_CLOSE|g50|fixed_75|full_fill|tEOD|DOWN_ONLY | 13 | 76.9% | 11.48 | $47,465 | $3,651 |
| 7 | A_RTH_OPEN|g30|fixed_75|3R|tEOD|BOTH | 45 | 51.1% | 2.56 | $46,070 | $1,024 |
| 8 | A_RTH_OPEN|g20|fixed_75|3R|tEOD|BOTH | 49 | 49.0% | 2.35 | $46,030 | $939 |
| 9 | B_OR_CLOSE|g10|fixed_75|full_fill|t1300|DOWN_ONLY | 17 | 82.4% | 10.85 | $44,630 | $2,625 |
| 10 | B_OR_CLOSE|g20|fixed_75|full_fill|t1300|DOWN_ONLY | 17 | 82.4% | 10.85 | $44,630 | $2,625 |
| 11 | A_RTH_OPEN|g10|fixed_75|3R|tEOD|BOTH | 50 | 48.0% | 2.25 | $44,520 | $890 |
| 12 | B_OR_CLOSE|g30|fixed_75|3R|tEOD|BOTH | 45 | 57.8% | 2.53 | $43,830 | $974 |
| 13 | B_OR_CLOSE|g10|fixed_75|3R|tEOD|DOWN_ONLY | 21 | 76.2% | 6.70 | $43,050 | $2,050 |
| 14 | B_OR_CLOSE|g20|fixed_75|3R|tEOD|DOWN_ONLY | 21 | 76.2% | 6.70 | $43,050 | $2,050 |
| 15 | B_OR_CLOSE|g20|fixed_75|3R|t1300|BOTH | 49 | 53.1% | 2.38 | $42,620 | $870 |
| 16 | B_OR_CLOSE|g30|fixed_75|full_fill|t1300|DOWN_ONLY | 16 | 81.2% | 10.41 | $42,610 | $2,663 |
| 17 | B_OR_CLOSE|g10|fixed_75|3R|t1300|DOWN_ONLY | 21 | 71.4% | 6.04 | $42,305 | $2,015 |
| 18 | B_OR_CLOSE|g20|fixed_75|3R|t1300|DOWN_ONLY | 21 | 71.4% | 6.04 | $42,305 | $2,015 |
| 19 | B_OR_CLOSE|g10|fixed_60|full_fill|tEOD|DOWN_ONLY | 17 | 76.5% | 9.67 | $41,980 | $2,469 |
| 20 | B_OR_CLOSE|g20|fixed_60|full_fill|tEOD|DOWN_ONLY | 17 | 76.5% | 9.67 | $41,980 | $2,469 |

### Bottom 10 (Worst Performers)

| Config | Trades | WR% | PF | Net PnL |
|--------|--------|-----|----|---------:|
| B_OR_CLOSE|g10|fixed_60|50pct_fill|t1300|UP_ONLY | 25 | 36.0% | 0.32 | -$12,370 |
| B_OR_CLOSE|g20|fixed_60|50pct_fill|t1300|UP_ONLY | 25 | 36.0% | 0.32 | -$12,370 |
| B_OR_CLOSE|g50|fixed_60|50pct_fill|t1300|UP_ONLY | 20 | 30.0% | 0.22 | -$12,412 |
| B_OR_CLOSE|g10|fixed_60|75pct_fill|t1300|UP_ONLY | 29 | 37.9% | 0.37 | -$12,635 |
| B_OR_CLOSE|g10|fixed_60|50pct_fill|tEOD|UP_ONLY | 25 | 36.0% | 0.35 | -$12,635 |
| B_OR_CLOSE|g20|fixed_60|50pct_fill|tEOD|UP_ONLY | 25 | 36.0% | 0.35 | -$12,635 |
| B_OR_CLOSE|g10|fixed_75|full_fill|t1300|UP_ONLY | 29 | 41.4% | 0.43 | -$12,655 |
| B_OR_CLOSE|g20|fixed_60|75pct_fill|t1300|UP_ONLY | 28 | 35.7% | 0.37 | -$12,665 |
| B_OR_CLOSE|g50|fixed_60|50pct_fill|tEOD|UP_ONLY | 20 | 30.0% | 0.25 | -$12,678 |
| B_OR_CLOSE|g20|fixed_75|full_fill|t1300|UP_ONLY | 28 | 39.3% | 0.43 | -$12,760 |

## 6. Entry Timing Comparison

Comparing entry variants using fixed parameters: gap>=20, fixed_60 stop, full_fill target, 1300 time stop, BOTH directions.

| Entry | Trades | WR% | PF | Net PnL | Expectancy |
|-------|--------|-----|----|---------|-----------:|
| A_RTH_OPEN | 49 | 51.0% | 2.05 | $28,765 | $587 |
| B_OR_CLOSE | 45 | 51.1% | 2.04 | $25,830 | $574 |
| C_VWAP_1000 | 16 | 56.2% | 2.24 | $8,325 | $520 |
| D_ACCEPTANCE | 9 | 55.6% | 1.13 | $645 | $72 |
| E_VWAP_ACCEPT | 5 | 60.0% | 1.53 | $1,280 | $256 |
| F_IB_CLOSE | 40 | 55.0% | 2.42 | $22,230 | $556 |

## 7. DOWN vs UP Gap Head-to-Head

Using E_VWAP_ACCEPT entry, gap>=20, fixed_60 stop, full_fill target, 1300 time stop.

- **DOWN_ONLY**: 4 trades, 50.0% WR, PF 1.43, $1,040
- **UP_ONLY**: 1 trades, 100.0% WR, PF inf, $240
- **BOTH**: 5 trades, 60.0% WR, PF 1.53, $1,280

## 8. Stop Model Comparison

Using E_VWAP_ACCEPT entry, gap>=20, full_fill target, 1300 time stop, BOTH directions.

| Stop Model | Trades | WR% | PF | Net PnL | Avg Loss |
|------------|--------|-----|----|---------|---------:|
| fixed_50 | 5 | 60.0% | 1.83 | $1,680 | -$1,010 |
| fixed_60 | 5 | 60.0% | 1.53 | $1,280 | -$1,210 |
| fixed_75 | 5 | 80.0% | 4.25 | $4,905 | -$1,510 |
| atr_1x | 5 | 40.0% | 1.68 | $1,240 | -$610 |
| or_extreme_5 | 5 | 80.0% | 7.37 | $5,545 | -$870 |

## 9. Target Model Comparison

Using E_VWAP_ACCEPT entry, gap>=20, fixed_60 stop, 1300 time stop, BOTH directions.

| Target Model | Trades | WR% | PF | Net PnL | Avg Win |
|-------------|--------|-----|----|---------|---------:|
| full_fill | 5 | 60.0% | 1.53 | $1,280 | $1,233 |
| 75pct_fill | 3 | 33.3% | 0.59 | -$998 | $1,422 |
| 50pct_fill | 1 | 0.0% | 0.00 | -$1,210 | $0 |
| 2R | 11 | 54.5% | 2.20 | $7,230 | $2,213 |
| 3R | 11 | 45.5% | 1.88 | $6,355 | $2,723 |

## 10. Time Stop Comparison

Using E_VWAP_ACCEPT entry, gap>=20, fixed_60 stop, full_fill target, BOTH directions.

| Time Stop | Trades | WR% | PF | Net PnL |
|-----------|--------|-----|----|---------:|
| 1100 | 5 | 60.0% | 0.67 | -$810 |
| 1300 | 5 | 60.0% | 1.53 | $1,280 |
| EOD | 5 | 60.0% | 1.59 | $1,420 |

## 11. Gap Size Filter Comparison

Using E_VWAP_ACCEPT entry, fixed_60 stop, full_fill target, 1300 time stop, BOTH directions.

| Gap Min | Trades | WR% | PF | Net PnL | Expectancy |
|---------|--------|-----|----|---------|-----------:|
| >=10pts | 5 | 60.0% | 1.53 | $1,280 | $256 |
| >=20pts | 5 | 60.0% | 1.53 | $1,280 | $256 |
| >=30pts | 5 | 60.0% | 1.53 | $1,280 | $256 |
| >=50pts | 5 | 60.0% | 1.53 | $1,280 | $256 |

## 12. Top 5 Winners and Losers

Using best config: **B_OR_CLOSE|g10|fixed_75|full_fill|tEOD|DOWN_ONLY** (17 trades, PF 12.20)

### Top 5 Winners

| Date | Dir | Gap | Entry | Exit | Reason | Net PnL |
|------|-----|-----|-------|------|--------|--------:|
| 2025-04-07 | LONG | DOWN 617pts | 17464.25 | 18243.00 | TARGET | $15,570 |
| 2026-03-09 | LONG | DOWN 391pts | 24383.75 | 24807.25 | TARGET | $8,465 |
| 2025-03-31 | LONG | DOWN 293pts | 19713.00 | 20074.75 | TIME_STOP | $7,230 |
| 2025-12-01 | LONG | DOWN 226pts | 25503.00 | 25740.75 | TARGET | $4,750 |
| 2025-05-19 | LONG | DOWN 310pts | 22041.50 | 22213.75 | TARGET | $3,440 |

### Top 5 Losers

| Date | Dir | Gap | Entry | Exit | Reason | Net PnL |
|------|-----|-----|-------|------|--------|--------:|
| 2026-02-16 | LONG | DOWN 43pts | 24723.50 | 24747.00 | EOD | $465 |
| 2025-09-22 | LONG | DOWN 40pts | 25104.25 | 25116.00 | TARGET | $230 |
| 2025-03-10 | LONG | DOWN 345pts | 20794.00 | 20718.75 | STOP | -$1,510 |
| 2025-12-29 | LONG | DOWN 167pts | 25793.50 | 25718.25 | STOP | -$1,510 |
| 2026-02-23 | LONG | DOWN 101pts | 24882.00 | 24806.75 | STOP | -$1,510 |

## 13. Monthly/Seasonal Patterns

| Month | Gaps | Avg Size | Monday Fill % | DOWN Gap % |
|-------|------|----------|---------------|------------|
| 2025-02 | 1 | 75.5 | 100.0% | 0.0% |
| 2025-03 | 5 | 219.2 | 60.0% | 60.0% |
| 2025-04 | 3 | 353.9 | 100.0% | 33.3% |
| 2025-05 | 4 | 387.9 | 50.0% | 50.0% |
| 2025-06 | 5 | 81.0 | 60.0% | 20.0% |
| 2025-07 | 4 | 34.2 | 50.0% | 25.0% |
| 2025-08 | 4 | 81.4 | 75.0% | 75.0% |
| 2025-09 | 5 | 68.8 | 40.0% | 20.0% |
| 2025-10 | 4 | 273.9 | 0.0% | 0.0% |
| 2025-11 | 4 | 230.7 | 25.0% | 25.0% |
| 2025-12 | 5 | 170.2 | 60.0% | 40.0% |
| 2026-01 | 4 | 208.4 | 50.0% | 50.0% |
| 2026-02 | 4 | 91.3 | 50.0% | 100.0% |
| 2026-03 | 2 | 374.6 | 100.0% | 100.0% |

## 14. Comparison to Prior Study Results

| Metric | Prior Study | This Study |
|--------|-------------|------------|
| Dataset | 54 weeks | 54 weeks |
| Monday fill rate | — | 53.7% |
| Week fill rate | 85.2% | 79.6% |
| DOWN gap Monday fill | 73.1% | 78.3% |
| UP gap Monday fill | 42.9% | 35.5% |
| VWAP confirms fill % | 88.2% | 91.7% |
| VWAP+Accept fill % | 100% (13/13) | 100.0% (13/13) |

**VWAP-filtered variant (E_VWAP_ACCEPT, >=20pts, fixed_75, full_fill, 1300)**:
- Trades: 5 (prior study: ~10/year)
- WR: 80.0% (prior study: 70%)
- PF: 4.25 (prior study: 2.45)
- Net PnL: $4,905

## 15. Recommendation

### Key Findings

1. **DOWN gaps are the edge**: 78.3% Monday fill rate vs 35.5% for UP gaps. DOWN-only configs dominate the top PnL rankings.
2. **VWAP confirmation is the strongest predictor**: 91.7% fill rate when VWAP confirms vs 23.3% when it does not.
3. **VWAP + Acceptance = 100% fill**: 13/13 weeks where both confirm resulted in Monday fill. Exactly matches prior study.
4. **Early entry wins**: Entry A (RTH open) and B (OR close) produce higher PnL than filtered entries because they capture more trades.
5. **Large gaps dominate**: 61% of gaps are 100+ pts, but only 39.4% fill on Monday. Small gaps (<30 pts) fill reliably but produce smaller PnL per trade.

### Verdict: DEPLOY

#### Primary Config (DOWN gaps only — highest edge)
**B_OR_CLOSE|g10|fixed_75|full_fill|tEOD|DOWN_ONLY**
- 17 trades, 82.4% WR, PF 12.20
- Net PnL: $50,755, Expectancy: $2,986/trade

#### Secondary Config (Both directions, more trades)
**B_OR_CLOSE|g20|fixed_75|3R|tEOD|BOTH**
- 49 trades, 57.1% WR, PF 2.55
- Net PnL: $49,055, Expectancy: $1,001/trade

#### Selective Config (Filtered, highest WR)
**C_VWAP_1000|g10|or_extreme_5|75pct_fill|tEOD|UP_ONLY**
- 5 trades, 80.0% WR, PF 4546.00
- Net PnL: $5,681, Expectancy: $1,136/trade

**Deployment conditions**:
1. Start with DOWN-only gaps (73-78% fill rate)
2. Entry at OR close (9:45) or IB close (10:30) — early entries capture more upside
3. Fixed 75 pt stop — wide enough to survive noise, tight enough to limit losses
4. Full gap fill target — let winners run to the gap level
5. EOD or 13:00 time stop — avoid holding losers through afternoon chop
6. Gap >= 20 pts minimum (filters out noise)
7. Start with 1 contract, scale after 10+ live trades confirm

## Appendix A: All NWOG Weeks

| # | Monday | Friday Close | Mon Open | Gap | Dir | Size | Mon Fill | Fill Min | Partial % | VWAP | Accept |
|---|--------|-------------|----------|-----|-----|------|----------|----------|-----------|------|--------|
| 1 | 2025-02-24 | 22593.75 | 22669.25 | +75.5 | UP | 75.5 | Y | 20 | 100% | Y | Y |
| 2 | 2025-03-03 | 21831.75 | 21969.25 | +137.5 | UP | 137.5 | Y | 22 | 100% | Y | Y |
| 3 | 2025-03-10 | 21137.00 | 20791.75 | -345.2 | DOWN | 345.2 | N | — | 7% | N | N |
| 4 | 2025-03-17 | 20617.75 | 20609.75 | -8.0 | DOWN | 8.0 | Y | 0 | 100% | Y | Y |
| 5 | 2025-03-24 | 20659.00 | 20970.75 | +311.8 | UP | 311.8 | N | — | 11% | N | N |
| 6 | 2025-03-31 | 20169.25 | 19876.00 | -293.2 | DOWN | 293.2 | Y | 373 | 100% | N | N |
| 7 | 2025-04-07 | 18243.25 | 17626.25 | -617.0 | DOWN | 617.0 | Y | 41 | 100% | Y | N |
| 8 | 2025-04-14 | 19518.00 | 19940.50 | +422.5 | UP | 422.5 | Y | 142 | 100% | Y | N |
| 9 | 2025-04-28 | 20238.75 | 20261.00 | +22.2 | UP | 22.2 | Y | 4 | 100% | Y | Y |
| 10 | 2025-05-05 | 20894.50 | 20723.75 | -170.8 | DOWN | 170.8 | Y | 311 | 100% | Y | N |
| 11 | 2025-05-12 | 20844.75 | 21634.25 | +789.5 | UP | 789.5 | N | — | 30% | N | N |
| 12 | 2025-05-19 | 22214.00 | 21904.50 | -309.5 | DOWN | 309.5 | Y | 212 | 100% | Y | Y |
| 13 | 2025-05-26 | 21687.00 | 21969.00 | +282.0 | UP | 282.0 | N | — | 16% | N | N |
| 14 | 2025-06-02 | 22077.75 | 21988.75 | -89.0 | DOWN | 89.0 | Y | 3 | 100% | Y | Y |
| 15 | 2025-06-09 | 22497.75 | 22512.75 | +15.0 | UP | 15.0 | Y | 2 | 100% | N | Y |
| 16 | 2025-06-16 | 22360.75 | 22511.50 | +150.8 | UP | 150.8 | N | — | 4% | N | N |
| 17 | 2025-06-23 | 22335.75 | 22363.75 | +28.0 | UP | 28.0 | Y | 1 | 100% | N | Y |
| 18 | 2025-06-30 | 23246.00 | 23368.25 | +122.2 | UP | 122.2 | N | — | 76% | Y | N |
| 19 | 2025-07-07 | 23400.75 | 23440.75 | +40.0 | UP | 40.0 | Y | 5 | 100% | Y | N |
| 20 | 2025-07-14 | 23449.50 | 23428.00 | -21.5 | DOWN | 21.5 | Y | 1 | 100% | Y | N |
| 21 | 2025-07-21 | 23720.50 | 23746.50 | +26.0 | UP | 26.0 | N | — | 11% | N | N |
| 22 | 2025-07-28 | 23916.50 | 23966.00 | +49.5 | UP | 49.5 | N | — | 71% | N | N |
| 23 | 2025-08-04 | 23375.00 | 23582.75 | +207.8 | UP | 207.8 | N | — | 1% | N | N |
| 24 | 2025-08-11 | 24208.00 | 24202.50 | -5.5 | DOWN | 5.5 | Y | 0 | 100% | Y | Y |
| 25 | 2025-08-18 | 24300.00 | 24257.50 | -42.5 | DOWN | 42.5 | Y | 2 | 100% | N | Y |
| 26 | 2025-08-25 | 24062.00 | 23992.00 | -70.0 | DOWN | 70.0 | Y | 80 | 100% | Y | N |
| 27 | 2025-09-01 | 23966.75 | 23970.00 | +3.2 | UP | 3.2 | Y | 1 | 100% | N | Y |
| 28 | 2025-09-08 | 24184.75 | 24280.25 | +95.5 | UP | 95.5 | N | — | 27% | N | N |
| 29 | 2025-09-15 | 24603.75 | 24675.75 | +72.0 | UP | 72.0 | N | — | 9% | N | N |
| 30 | 2025-09-22 | 25116.25 | 25076.25 | -40.0 | DOWN | 40.0 | Y | 19 | 100% | Y | Y |
| 31 | 2025-09-29 | 24982.00 | 25115.00 | +133.0 | UP | 133.0 | N | — | 59% | N | N |
| 32 | 2025-10-06 | 25252.75 | 25468.75 | +216.0 | UP | 216.0 | N | — | 48% | N | N |
| 33 | 2025-10-13 | 24658.25 | 25084.00 | +425.8 | UP | 425.8 | N | — | 24% | N | N |
| 34 | 2025-10-20 | 25244.00 | 25379.75 | +135.8 | UP | 135.8 | N | — | 6% | N | N |
| 35 | 2025-10-27 | 25765.00 | 26083.25 | +318.2 | UP | 318.2 | N | — | 10% | N | N |
| 36 | 2025-11-03 | 26249.50 | 26478.25 | +228.8 | UP | 228.8 | N | — | 90% | Y | N |
| 37 | 2025-11-10 | 25420.75 | 25796.25 | +375.5 | UP | 375.5 | N | — | 23% | N | N |
| 38 | 2025-11-17 | 25362.75 | 25252.75 | -110.0 | DOWN | 110.0 | Y | 6 | 100% | Y | Y |
| 39 | 2025-11-24 | 24570.75 | 24779.25 | +208.5 | UP | 208.5 | N | — | 3% | N | N |
| 40 | 2025-12-01 | 25741.00 | 25515.25 | -225.8 | DOWN | 225.8 | Y | 196 | 100% | Y | N |
| 41 | 2025-12-08 | 25983.00 | 26052.25 | +69.2 | UP | 69.2 | Y | 20 | 100% | Y | N |
| 42 | 2025-12-15 | 25466.75 | 25655.50 | +188.8 | UP | 188.8 | Y | 31 | 100% | Y | Y |
| 43 | 2025-12-22 | 25581.25 | 25781.75 | +200.5 | UP | 200.5 | N | — | 77% | N | N |
| 44 | 2025-12-29 | 25865.50 | 25698.50 | -167.0 | DOWN | 167.0 | N | — | 72% | N | Y |
| 45 | 2026-01-05 | 25385.00 | 25621.25 | +236.2 | UP | 236.2 | N | — | 35% | N | N |
| 46 | 2026-01-12 | 25933.00 | 25736.50 | -196.5 | DOWN | 196.5 | Y | 56 | 100% | Y | Y |
| 47 | 2026-01-19 | 25684.25 | 25287.00 | -397.2 | DOWN | 397.2 | N | — | 33% | N | N |
| 48 | 2026-01-26 | 25734.50 | 25738.25 | +3.8 | UP | 3.8 | Y | 0 | 100% | N | N |
| 49 | 2026-02-02 | 25671.50 | 25532.75 | -138.8 | DOWN | 138.8 | Y | 6 | 100% | Y | Y |
| 50 | 2026-02-09 | 25147.00 | 25064.00 | -83.0 | DOWN | 83.0 | Y | 12 | 100% | N | Y |
| 51 | 2026-02-16 | 24803.00 | 24760.25 | -42.8 | DOWN | 42.8 | N | — | 87% | N | N |
| 52 | 2026-02-23 | 25076.25 | 24975.50 | -100.8 | DOWN | 100.8 | N | — | 64% | N | N |
| 53 | 2026-03-02 | 24998.50 | 24640.25 | -358.2 | DOWN | 358.2 | Y | 132 | 100% | Y | Y |
| 54 | 2026-03-09 | 24807.50 | 24416.50 | -391.0 | DOWN | 391.0 | Y | 351 | 100% | Y | N |
