# Trend Day Bull/Bear Strategy Rewrite - Quant Study

**Date**: 2026-03-12
**Instrument**: NQ futures
**Sessions**: 273
**Configs tested**: 22680
**Configs with trades**: 16700
**Configs with >= 10 trades**: 13005
**Runtime**: 76217s

## Study Target

| Metric | Target | Best Found |
|--------|--------|------------|
| Trades | 40-60 | 357 |
| Win Rate | 50-55% | 44.5% |
| Profit Factor | 2.0+ | 1.41 |
| Net P&L | $15-30K | $63,696 |

## Top 30 Configurations (by Profit Factor)

| # | Trend Detection | Entry | Stop | Target | Window | Dir | Trades | WR% | PF | Net P&L | AvgWin | AvgLoss | MaxDD |
|---|----------------|-------|------|--------|--------|-----|--------|-----|-----|---------|--------|---------|-------|
| 1 | ib_ext_1.5 | acceptance_breakout | ib_mid | 2R | ib_close | BOTH | 13 | 69.2 | 3.75 | $33,717 | $5,110 | $-3,068 | $-9,713 |
| 2 | ib_ext_1.5 | acceptance_breakout | ib_mid | 3R | ib_close | BOTH | 13 | 69.2 | 3.75 | $33,717 | $5,110 | $-3,068 | $-9,713 |
| 3 | ib_ext_1.5 | ema20_pullback | ib_mid | 3R | full | BOTH | 17 | 58.8 | 3.69 | $25,400 | $3,484 | $-1,349 | $-4,917 |
| 4 | ib_ext_1.5 | ema20_pullback | ib_mid | 2R | full | BOTH | 17 | 58.8 | 3.69 | $25,400 | $3,484 | $-1,349 | $-4,917 |
| 5 | ib_ext_1.5 | ema20_pullback | ib_mid | 3R | full | SHORT | 14 | 57.1 | 3.62 | $15,548 | $2,686 | $-990 | $-3,703 |
| 6 | ib_ext_1.5 | ema20_pullback | ib_mid | 2R | full | SHORT | 14 | 57.1 | 3.62 | $15,548 | $2,686 | $-990 | $-3,703 |
| 7 | ib_ext_1.5 | acceptance_breakout | ib_mid | 3R | ib_close | SHORT | 11 | 72.7 | 3.51 | $21,570 | $3,768 | $-2,859 | $-6,019 |
| 8 | ib_ext_1.5 | acceptance_breakout | ib_mid | 2R | ib_close | SHORT | 11 | 72.7 | 3.51 | $21,570 | $3,768 | $-2,859 | $-6,019 |
| 9 | ib_ext_1.0 | acceptance_breakout | ema50 | 3R | afternoon | LONG | 12 | 41.7 | 3.23 | $13,885 | $4,024 | $-891 | $-3,296 |
| 10 | ib_ext_1.5 | ema20_pullback | ib_mid | 2R | afternoon | BOTH | 17 | 52.9 | 3.23 | $21,210 | $3,414 | $-1,189 | $-4,917 |
| 11 | ib_ext_1.5 | ema20_pullback | ib_mid | 3R | afternoon | BOTH | 17 | 52.9 | 3.23 | $21,210 | $3,414 | $-1,189 | $-4,917 |
| 12 | ib_ext_1.5 | ema20_pullback | vwap_buffer | 3R | full | SHORT | 14 | 28.6 | 3.17 | $7,273 | $2,657 | $-336 | $-1,571 |
| 13 | ib_ext_1.0 | acceptance_breakout | ema50 | 2R | afternoon | LONG | 12 | 41.7 | 3.16 | $13,494 | $3,946 | $-891 | $-3,686 |
| 14 | ema+adx20+ib0.5 | fib_50_pullback | vwap_buffer | 2.0x_ib | afternoon | BOTH | 22 | 31.8 | 3.06 | $9,685 | $2,057 | $-314 | $-1,885 |
| 15 | ib_ext_1.5 | ema20_pullback | vwap_buffer | 2R | afternoon | SHORT | 14 | 28.6 | 2.99 | $6,673 | $2,507 | $-336 | $-1,655 |
| 16 | ib_ext_1.5 | ema20_pullback | vwap_buffer | 2R | full | SHORT | 14 | 28.6 | 2.99 | $6,673 | $2,507 | $-336 | $-1,655 |
| 17 | ib_ext_1.0 | ema20_pullback | ema50 | 2R | ib_close | BOTH | 28 | 50.0 | 2.94 | $29,080 | $3,146 | $-1,069 | $-3,946 |
| 18 | ib_ext_1.5 | ema20_pullback | ib_mid | 3R | afternoon | SHORT | 14 | 50.0 | 2.89 | $11,358 | $2,481 | $-858 | $-3,703 |
| 19 | ib_ext_1.5 | ema20_pullback | ib_mid | 2R | afternoon | SHORT | 14 | 50.0 | 2.89 | $11,358 | $2,481 | $-858 | $-3,703 |
| 20 | ib_ext_1.5 | ema20_pullback | ib_mid | trailing_ema20 | full | BOTH | 17 | 41.2 | 2.85 | $7,310 | $1,608 | $-395 | $-2,493 |
| 21 | ib_ext_1.0 | ema20_pullback | ema50 | trailing_ema20 | afternoon | LONG | 10 | 30.0 | 2.74 | $4,169 | $2,188 | $-342 | $-925 |
| 22 | ib_ext_1.0 | ema20_pullback | ema50 | 3R | afternoon | LONG | 10 | 40.0 | 2.68 | $8,906 | $3,555 | $-885 | $-2,941 |
| 23 | ib_ext_1.0 | ema20_pullback | ib_mid | trailing_ema20 | afternoon | LONG | 10 | 30.0 | 2.66 | $3,971 | $2,122 | $-342 | $-1,082 |
| 24 | ib_ext_1.0 | ema20_pullback | ema50 | 2R | afternoon | LONG | 10 | 40.0 | 2.65 | $8,752 | $3,516 | $-885 | $-3,241 |
| 25 | ib_ext_1.5 | ema20_pullback | vwap_buffer | 3R | afternoon | SHORT | 14 | 21.4 | 2.65 | $6,073 | $3,248 | $-334 | $-2,255 |
| 26 | ib_ext_1.5 | ema20_pullback | ema50 | trailing_ema20 | full | BOTH | 17 | 41.2 | 2.6 | $6,307 | $1,465 | $-395 | $-2,493 |
| 27 | ib_ext_1.5 | ema20_pullback | ib_mid | trailing_ema20 | afternoon | BOTH | 17 | 35.3 | 2.58 | $6,257 | $1,703 | $-360 | $-2,551 |
| 28 | ib_ext_1.5 | ema20_pullback | ib_mid | 2.0x_ib | full | SHORT | 12 | 66.7 | 2.53 | $5,161 | $1,067 | $-843 | $-1,598 |
| 29 | ema+ib0.5 | fib_50_pullback | vwap_buffer | 2.0x_ib | afternoon | BOTH | 24 | 25.0 | 2.49 | $8,447 | $2,350 | $-314 | $-2,058 |
| 30 | ib_ext_1.5 | acceptance_breakout | ib_mid | trailing_ema20 | ib_close | BOTH | 13 | 38.5 | 2.48 | $8,800 | $2,951 | $-745 | $-2,433 |

## Trend Detection Analysis

Which trend detection method produces the best results across all configs?

