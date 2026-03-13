# VWAP Sigma Band Reversal Study — NQ Futures

**Date**: 2026-03-12
**Sessions**: 273
**Configs tested**: 119
**Runtime**: 1952s

## 1. Frequency Analysis — How Often Does Price Touch Each Sigma Band?

| Sigma | Upper Touches | Lower Touches | Sessions w/ Upper | Sessions w/ Lower |
|-------|--------------|--------------|-------------------|-------------------|
| 1σ | 35,782 bars | 25,351 bars | 227 (83.2%) | 218 (79.9%) |
| 2σ | 3,957 bars | 4,719 bars | 149 (54.6%) | 149 (54.6%) |
| 3σ | 100 bars | 279 bars | 18 (6.6%) | 50 (18.3%) |

**Interpretation**: 1σ touches are common (most sessions). 2σ is the standard institutional level — frequent enough for a tradeable edge. 3σ is rare (extreme).

## 2. Top 30 Configurations (by Profit Factor, min 15 trades)

| # | Sigma | Confirm | ADX | Stop | Target | Window | Dir | TimeExit | Trades | WR% | PF | PnL$ |
|---|-------|---------|-----|------|--------|--------|-----|----------|--------|-----|----|------|
| 1 | sigma_2 | reversal_bar | adx_lt_25 | fixed_30pt | vwap | morning | BOTH | 30_bars | 101 | 44.6 | 1.75 | $21,987 |
| 2 | sigma_3 | immediate | no_adx | fixed_30pt | vwap | morning | BOTH | 30_bars | 36 | 44.4 | 1.62 | $6,998 |
| 3 | sigma_2 | reversal_bar | adx_lt_20 | fixed_30pt | vwap | morning | BOTH | 30_bars | 64 | 45.3 | 1.57 | $10,577 |
| 4 | sigma_3 | reversal_bar | no_adx | fixed_30pt | vwap | morning | BOTH | no_time_exit | 24 | 25.0 | 1.4 | $4,414 |
| 5 | sigma_2 | reversal_bar | adx_lt_25 | fixed_30pt | vwap | full | BOTH | 30_bars | 191 | 41.4 | 1.34 | $21,123 |
| 6 | sigma_3 | reversal_bar | no_adx | fixed_30pt | vwap | morning | BOTH | 30_bars | 24 | 41.7 | 1.28 | $2,422 |
| 7 | sigma_3 | reversal_bar | no_adx | fixed_30pt | vwap | morning | BOTH | 15_bars | 24 | 45.8 | 1.28 | $2,245 |
| 8 | sigma_2 | reversal_bar | adx_lt_20 | fixed_30pt | vwap | full | BOTH | 30_bars | 122 | 42.6 | 1.26 | $10,099 |
| 9 | sigma_2 | reversal_bar | no_adx | fixed_30pt | vwap | morning | SHORT | 15_bars | 186 | 46.8 | 1.24 | $9,996 |
| 10 | sigma_2_break | immediate | no_adx | sigma_next | vwap | morning | BOTH | 30_bars | 411 | 17.8 | 1.24 | $18,354 |
| 11 | sigma_2_break | reversal_bar | no_adx | sigma_next | vwap | morning | BOTH | 30_bars | 396 | 18.2 | 1.23 | $17,197 |
| 12 | sigma_2 | reversal_bar | adx_lt_25 | fixed_30pt | vwap | midday | BOTH | 30_bars | 119 | 37.8 | 1.21 | $8,193 |
| 13 | sigma_2 | reversal_bar | no_adx | fixed_30pt | vwap | morning | BOTH | 15_bars | 393 | 41.5 | 1.16 | $18,523 |
| 14 | sigma_2 | reversal_bar | adx_lt_20 | fixed_30pt | vwap | midday | BOTH | 30_bars | 81 | 39.5 | 1.13 | $3,503 |
| 15 | sigma_2 | reversal_bar | adx_lt_25 | fixed_30pt | vwap | after_ib | BOTH | 30_bars | 145 | 38.6 | 1.12 | $5,662 |
| 16 | sigma_2 | reversal_bar | no_adx | atr_1x | sigma_1 | morning | BOTH | 30_bars | 398 | 31.7 | 1.11 | $12,295 |
| 17 | sigma_2 | reversal_bar | no_adx | atr_1x | half_reversion | morning | BOTH | 30_bars | 398 | 31.7 | 1.11 | $12,295 |
| 18 | sigma_2 | rsi_confirm | no_adx | fixed_30pt | vwap | morning | BOTH | 30_bars | 366 | 36.9 | 1.1 | $12,916 |
| 19 | sigma_3 | rsi_confirm | no_adx | fixed_30pt | vwap | morning | BOTH | 30_bars | 33 | 39.4 | 1.1 | $1,192 |
| 20 | sigma_2 | reversal_bar | no_adx | fixed_20pt | vwap | morning | BOTH | 30_bars | 393 | 29.0 | 1.1 | $11,546 |
| 21 | sigma_2 | reversal_bar | no_adx | atr_1x | vwap | morning | BOTH | 30_bars | 397 | 27.2 | 1.1 | $12,662 |
| 22 | sigma_2 | reversal_bar | no_adx | fixed_30pt | vwap | morning | LONG | 15_bars | 215 | 36.3 | 1.1 | $7,395 |
| 23 | sigma_2 | reversal_bar | no_adx | fixed_30pt | vwap | morning | SHORT | 30_bars | 180 | 41.1 | 1.1 | $5,452 |
| 24 | sigma_2_break | immediate | no_adx | fixed_20pt | vwap | morning | BOTH | 30_bars | 406 | 29.6 | 1.1 | $11,348 |
| 25 | sigma_2 | reversal_bar | no_adx | fixed_30pt | vwap | morning | BOTH | 30_bars | 387 | 36.2 | 1.09 | $11,679 |
| 26 | sigma_2 | reversal_bar | adx_any | fixed_30pt | vwap | morning | BOTH | 30_bars | 387 | 36.2 | 1.09 | $11,679 |
| 27 | sigma_2 | immediate | no_adx | fixed_30pt | vwap | morning | BOTH | 30_bars | 418 | 35.4 | 1.08 | $12,218 |
| 28 | sigma_2 | reversal_bar | no_adx | sigma_next | 1R | morning | BOTH | 30_bars | 359 | 49.6 | 1.08 | $11,709 |
| 29 | sigma_2 | reversal_bar | no_adx | sigma_next | 2R | morning | BOTH | 30_bars | 355 | 43.1 | 1.08 | $12,459 |
| 30 | sigma_3 | reversal_bar | no_adx | fixed_30pt | vwap | morning | LONG | no_time_exit | 21 | 19.0 | 1.08 | $803 |

## 3. Sigma Level Analysis (1σ vs 2σ vs 3σ)

| Sigma Level | Configs | Avg Trades | Median WR% | Median PF | Avg PnL$ |
|-------------|---------|-----------|------------|-----------|----------|
| sigma_1 | 4 | 788 | 36.7 | 0.89 | $-30,648 |
| sigma_2 | 51 | 322 | 38.6 | 1.06 | $5,248 |
| sigma_3 | 29 | 15 | 20.0 | 1.10 | $1,080 |
| sigma_2_break | 32 | 392 | 35.2 | 0.99 | $-673 |

## 4. Confirmation Method Comparison

*Fixed: sigma_2, fixed_30pt stop, VWAP target, morning window, BOTH directions*

| Confirmation | Trades | WR% | PF | PnL$ | Avg Bars |
|-------------|--------|-----|----|------|----------|
| immediate | 418 | 35.4 | 1.08 | $12,218 | 16.8 |
| reversal_bar | 387 | 36.2 | 1.09 | $11,679 | 16.9 |
| rsi_confirm | 366 | 36.9 | 1.1 | $12,916 | 17.3 |
| volume_exhaustion | 361 | 34.1 | 0.86 | $-18,493 | 16.4 |

## 5. ADX Gate Impact

*Fixed: sigma_2, reversal_bar, fixed_30pt, VWAP target, BOTH*

| ADX Gate | Window | Trades | WR% | PF | PnL$ |
|----------|--------|--------|-----|----|------|
| no_adx | morning | 387 | 36.2 | 1.09 | $11,679 |
| no_adx | midday | 291 | 37.5 | 1.04 | $4,089 |
| no_adx | full | 543 | 34.6 | 1.01 | $1,004 |
| no_adx | after_ib | 387 | 35.9 | 0.99 | $-1,127 |
| adx_lt_20 | morning | 64 | 45.3 | 1.57 | $10,577 |
| adx_lt_20 | midday | 81 | 39.5 | 1.13 | $3,503 |
| adx_lt_20 | full | 122 | 42.6 | 1.26 | $10,099 |
| adx_lt_20 | after_ib | 97 | 39.2 | 0.98 | $-683 |
| adx_lt_25 | morning | 101 | 44.6 | 1.75 | $21,987 |
| adx_lt_25 | midday | 119 | 37.8 | 1.21 | $8,193 |
| adx_lt_25 | full | 191 | 41.4 | 1.34 | $21,123 |
| adx_lt_25 | after_ib | 145 | 38.6 | 1.12 | $5,662 |
| adx_any | morning | 387 | 36.2 | 1.09 | $11,679 |
| adx_any | midday | 291 | 37.5 | 1.04 | $4,089 |
| adx_any | full | 543 | 34.6 | 1.01 | $1,004 |
| adx_any | after_ib | 387 | 35.9 | 0.99 | $-1,127 |

### ADX Bucket Performance (Best Config)

| ADX Range | Trades | Avg PnL$ |
|-----------|--------|----------|
| <20 | 55 | $188 |
| 20-25 | 46 | $254 |
| 25-30 | 0 | $0 |
| >30 | 0 | $0 |
| NA | 0 | $0 |

## 6. Stop / Target Optimization

*Fixed: sigma_2, reversal_bar, no_adx, morning, BOTH, 30_bars*

### Stop Model (target=VWAP)

| Stop | Trades | WR% | PF | PnL$ | Avg Win | Avg Loss |
|------|--------|-----|----|------|---------|----------|
| sigma_next | 355 | 42.8 | 1.06 | $9,712 | $1,104 | $-779 |
| fixed_20pt | 393 | 29.0 | 1.1 | $11,546 | $1,071 | $-396 |
| fixed_30pt | 387 | 36.2 | 1.09 | $11,679 | $1,061 | $-554 |
| fixed_40pt | 371 | 40.4 | 1.06 | $8,775 | $1,043 | $-668 |
| atr_1x | 397 | 27.2 | 1.1 | $12,662 | $1,240 | $-420 |

### Target Model (stop=fixed_30pt)

| Target | Trades | WR% | PF | PnL$ | Avg Win | Avg Loss |
|--------|--------|-----|----|------|---------|----------|
| vwap | 387 | 36.2 | 1.09 | $11,679 | $1,061 | $-554 |
| sigma_1 | 388 | 40.2 | 1.06 | $8,347 | $884 | $-558 |
| 1R | 389 | 49.1 | 0.94 | $-7,145 | $545 | $-562 |
| 2R | 388 | 38.9 | 0.99 | $-1,916 | $857 | $-554 |
| half_reversion | 388 | 40.2 | 1.06 | $8,347 | $884 | $-558 |

## 7. Direction Analysis (LONG vs SHORT asymmetry)

*sigma_2, reversal_bar, no_adx, fixed_30pt, VWAP target, morning, 30_bars*

| Direction | Trades | WR% | PF | PnL$ |
|-----------|--------|-----|----|------|
| LONG | 214 | 31.8 | 1.07 | $6,263 |
| SHORT | 180 | 41.1 | 1.1 | $5,452 |
| BOTH | 387 | 36.2 | 1.09 | $11,679 |

### LONG vs SHORT within BOTH configs (top 10)

| Config | Long Trades | Long WR% | Long PnL$ | Short Trades | Short WR% | Short PnL$ |
|--------|------------|----------|-----------|-------------|-----------|------------|
| sigma_2/reversal_bar/fixed_30pt | 45 | 42.2 | $12,421 | 56 | 46.4 | $9,566 |
| sigma_3/immediate/fixed_30pt | 29 | 37.9 | $3,329 | 7 | 71.4 | $3,670 |
| sigma_2/reversal_bar/fixed_30pt | 23 | 30.4 | $1,796 | 41 | 53.7 | $8,782 |
| sigma_3/reversal_bar/fixed_30pt | 21 | 19.0 | $803 | 3 | 66.7 | $3,611 |
| sigma_2/reversal_bar/fixed_30pt | 103 | 36.9 | $12,141 | 88 | 46.6 | $8,982 |
| sigma_3/reversal_bar/fixed_30pt | 21 | 38.1 | $-850 | 3 | 66.7 | $3,272 |
| sigma_3/reversal_bar/fixed_30pt | 21 | 42.9 | $-531 | 3 | 66.7 | $2,777 |
| sigma_2/reversal_bar/fixed_30pt | 56 | 26.8 | $-1,586 | 66 | 56.1 | $11,685 |
| sigma_2_break/immediate/sigma_next | 219 | 20.1 | $18,006 | 192 | 15.1 | $348 |
| sigma_2_break/reversal_bar/sigma_next | 215 | 20.0 | $14,242 | 181 | 16.0 | $2,955 |

## 8. Comparison to BB Extreme Reversal

| Metric | VWAP Sigma (Best) | BB Extreme Rev |
|--------|-------------------|----------------|
| trades | 101 | 1899 |
| win_rate | 44.6 | 61.0 |
| pf | 1.75 | 1.02 |
| total_pnl | $21,987 | $8,303 |
| avg_win | $1,143 | $362 |
| avg_loss | $-526 | $-556 |

**Note**: Both strategies are mean reversion at statistical extremes. VWAP sigma bands reset per-session (anchored VWAP) while BB uses rolling 20-bar lookback. VWAP bands are more institutionally relevant for intraday futures.

## 9. VERDICT

**MARGINAL — Needs further optimization before production**

### Recommended Configuration

- **Sigma Level**: sigma_2
- **Confirmation**: reversal_bar
- **ADX Gate**: adx_lt_25
- **Stop Model**: fixed_30pt
- **Target Model**: vwap
- **Time Window**: morning
- **Direction**: BOTH
- **Time Exit**: 30_bars

- **Trades**: 101
- **Win Rate**: 44.6%
- **Profit Factor**: 1.75
- **Total PnL**: $21,987
- **Avg Win**: $1,143
- **Avg Loss**: $-526

### Runner-Up Configurations

2. **sigma_3/immediate/fixed_30pt/vwap** — 36 trades, 44.4% WR, 1.62 PF, $6,998
3. **sigma_2/reversal_bar/fixed_30pt/vwap** — 64 trades, 45.3% WR, 1.57 PF, $10,577
4. **sigma_3/reversal_bar/fixed_30pt/vwap** — 24 trades, 25.0% WR, 1.4 PF, $4,414
5. **sigma_2/reversal_bar/fixed_30pt/vwap** — 191 trades, 41.4% WR, 1.34 PF, $21,123

### Key Observations

- **Best sigma level**: sigma_3 (median PF 1.10)
- **Balanced**: Both directions contribute roughly equally
- VWAP sigma bands provide statistically anchored levels that reset daily
- 2σ band is the institutional standard for mean-reversion setups
- Reversal bar confirmation reduces false signals vs immediate entry
