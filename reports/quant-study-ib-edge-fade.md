# IB Edge Fade Quant Study -- NQ Futures

**Date**: 2026-03-12
**Sessions**: 260
**Configs tested**: 567 (567 with >= 5 trades)
**Instrument**: NQ ($20/pt, 1 tick slippage/side, $2.50 commission/side)
**IB Range**: min=31, median=170, max=1688
**Day types**: {'neutral': 59, 'trend_down': 36, 'p_day': 80, 'b_day': 51, 'trend_up': 34}

## Executive Summary

**Best IBH SHORT (unfiltered)**: SHORT poke a1 0.5ATR 1R
  - 137 trades, 58.4% WR, PF 1.39, $7,509

**Best IBL LONG (unfiltered)**: LONG 3pts a2 10%IB 2R
  - 122 trades, 42.6% WR, PF 1.56, $27,968

**Best IBH SHORT (filtered)**: SHORT 5pts a2 0.5ATR IBmid [full]
  - 80 trades, 30.0% WR, PF 1.43, $9,329

## Top 20 Configurations by Profit Factor (min 5 trades)

| Rank | ID | Description | Trades | WR% | PF | P&L | AvgW | AvgL | Expect |
|------|------|-------------|--------|-----|-----|-----|------|------|--------|
| 1 | L2T567 | LONG 2nd-touch 5pts a2 0.5ATR IBmid | 95 | 37.9 | 1.67 | $20,630 | $1,422 | $-518 | $217 |
| 2 | L2T563 | LONG 2nd-touch 5pts a2 10%IB IBmid | 95 | 43.2 | 1.65 | $23,554 | $1,462 | $-674 | $248 |
| 3 | L279 | LONG 3pts a2 10%IB 2R | 122 | 42.6 | 1.56 | $27,968 | $1,503 | $-717 | $229 |
| 4 | L2T565 | LONG 2nd-touch 5pts a3 10%IB IBmid | 92 | 46.7 | 1.54 | $19,646 | $1,309 | $-747 | $214 |
| 5 | L281 | LONG 3pts a2 0.5ATR IBmid | 122 | 38.5 | 1.51 | $20,575 | $1,301 | $-541 | $169 |
| 6 | L345 | LONG 5pts a2 0.5ATR IBmid | 124 | 38.7 | 1.50 | $20,783 | $1,298 | $-547 | $168 |
| 7 | L277 | LONG 3pts a2 10%IB IBmid | 122 | 43.4 | 1.49 | $23,608 | $1,352 | $-696 | $194 |
| 8 | L379 | LONG 5pts a5 0.5ATR 2R | 115 | 38.3 | 1.47 | $23,516 | $1,665 | $-701 | $204 |
| 9 | L283 | LONG 3pts a2 0.5ATR 2R | 122 | 40.2 | 1.46 | $19,028 | $1,238 | $-570 | $156 |
| 10 | L315 | LONG 3pts a5 0.5ATR 2R | 112 | 39.3 | 1.45 | $22,166 | $1,631 | $-729 | $198 |
| 11 | L263 | LONG 3pts a1 10%IB 2R | 125 | 40.8 | 1.43 | $19,504 | $1,280 | $-618 | $156 |
| 12 | L455 | LONG poke a1 10%IB 2R | 121 | 40.5 | 1.43 | $19,587 | $1,319 | $-626 | $162 |
| 13 | SF533 | SHORT 5pts a2 0.5ATR IBmid [full] | 80 | 30.0 | 1.43 | $9,329 | $1,287 | $-385 | $117 |
| 14 | L377 | LONG 5pts a5 0.5ATR IBmid | 114 | 45.6 | 1.42 | $16,900 | $1,101 | $-651 | $148 |
| 15 | L261 | LONG 3pts a1 10%IB IBmid | 125 | 35.2 | 1.41 | $19,275 | $1,509 | $-582 | $154 |
| 16 | S204 | SHORT poke a1 0.5ATR 1R | 137 | 58.4 | 1.39 | $7,509 | $334 | $-337 | $55 |
| 17 | L259 | LONG 3pts a1 +5pt 2R | 125 | 40.8 | 1.38 | $10,045 | $720 | $-360 | $80 |
| 18 | L265 | LONG 3pts a1 0.5ATR IBmid | 125 | 29.6 | 1.38 | $14,182 | $1,405 | $-430 | $113 |
| 19 | L293 | LONG 3pts a3 10%IB IBmid | 119 | 46.2 | 1.38 | $18,048 | $1,185 | $-737 | $152 |
| 20 | L313 | LONG 3pts a5 0.5ATR IBmid | 111 | 45.9 | 1.38 | $15,093 | $1,067 | $-656 | $136 |

## IBH SHORT -- Top 20 Unfiltered

| # | ID | Config | Trades | WR% | PF | P&L | MaxW | MaxL |
|---|------|--------|--------|-----|-----|-----|------|------|
| 1 | S204 | SHORT poke a1 0.5ATR 1R | 137 | 58.4 | 1.39 | $7,509 | $1,047 | $-1,003 |
| 2 | S164 | SHORT 10pts a3 +5pt 1R | 150 | 56.7 | 1.35 | $9,505 | $1,110 | $-1,505 |
| 3 | S172 | SHORT 10pts a3 0.5ATR 1R | 150 | 58.0 | 1.30 | $10,204 | $1,348 | $-1,787 |
| 4 | S200 | SHORT poke a1 10%IB 1R | 137 | 56.9 | 1.25 | $7,610 | $1,374 | $-1,068 |
| 5 | S193 | SHORT poke a1 +5pt IBmid | 137 | 18.2 | 1.22 | $6,290 | $2,772 | $-795 |
| 6 | S044 | SHORT 3pts a3 0.5ATR 1R | 132 | 59.1 | 1.19 | $5,527 | $1,348 | $-1,787 |
| 7 | S194 | SHORT poke a1 +5pt OppEdge | 137 | 10.2 | 1.19 | $6,185 | $5,030 | $-950 |
| 8 | S234 | SHORT poke a3 0.5ATR OppEdge | 128 | 18.8 | 1.19 | $9,835 | $4,920 | $-1,787 |
| 9 | S236 | SHORT poke a3 0.5ATR 1R | 128 | 58.6 | 1.19 | $5,478 | $1,348 | $-1,787 |
| 10 | S122 | SHORT 5pts a5 0.5ATR OppEdge | 129 | 21.7 | 1.18 | $10,798 | $4,685 | $-1,975 |
| 11 | S170 | SHORT 10pts a3 0.5ATR OppEdge | 150 | 19.3 | 1.18 | $11,244 | $5,030 | $-1,787 |
| 12 | S218 | SHORT poke a2 0.5ATR OppEdge | 133 | 15.0 | 1.18 | $8,979 | $5,010 | $-1,557 |
| 13 | S228 | SHORT poke a3 +5pt 1R | 128 | 55.5 | 1.18 | $4,105 | $1,110 | $-1,505 |
| 14 | S090 | SHORT 5pts a2 0.5ATR OppEdge | 142 | 16.2 | 1.17 | $8,923 | $5,010 | $-1,557 |
| 15 | S106 | SHORT 5pts a3 0.5ATR OppEdge | 136 | 18.4 | 1.17 | $9,283 | $4,920 | $-1,787 |
| 16 | S012 | SHORT 3pts a1 0.5ATR 1R | 142 | 57.0 | 1.15 | $3,485 | $1,047 | $-1,003 |
| 17 | S195 | SHORT poke a1 +5pt 2R | 137 | 38.0 | 1.15 | $3,210 | $1,545 | $-950 |
| 18 | S154 | SHORT 10pts a2 0.5ATR OppEdge | 155 | 17.4 | 1.14 | $8,724 | $5,010 | $-2,111 |
| 19 | S042 | SHORT 3pts a3 0.5ATR OppEdge | 132 | 18.2 | 1.13 | $7,008 | $4,920 | $-1,787 |
| 20 | S058 | SHORT 3pts a5 0.5ATR OppEdge | 127 | 21.3 | 1.13 | $7,243 | $4,685 | $-1,975 |

## IBL LONG -- Top 20 Unfiltered

| # | ID | Config | Trades | WR% | PF | P&L | MaxW | MaxL |
|---|------|--------|--------|-----|-----|-----|------|------|
| 1 | L279 | LONG 3pts a2 10%IB 2R | 122 | 42.6 | 1.56 | $27,968 | $4,642 | $-1,754 |
| 2 | L281 | LONG 3pts a2 0.5ATR IBmid | 122 | 38.5 | 1.51 | $20,575 | $3,658 | $-1,551 |
| 3 | L345 | LONG 5pts a2 0.5ATR IBmid | 124 | 38.7 | 1.50 | $20,783 | $3,738 | $-1,551 |
| 4 | L277 | LONG 3pts a2 10%IB IBmid | 122 | 43.4 | 1.49 | $23,608 | $3,658 | $-1,754 |
| 5 | L379 | LONG 5pts a5 0.5ATR 2R | 115 | 38.3 | 1.47 | $23,516 | $7,187 | $-1,708 |
| 6 | L283 | LONG 3pts a2 0.5ATR 2R | 122 | 40.2 | 1.46 | $19,028 | $4,237 | $-1,551 |
| 7 | L315 | LONG 3pts a5 0.5ATR 2R | 112 | 39.3 | 1.45 | $22,166 | $7,187 | $-1,708 |
| 8 | L263 | LONG 3pts a1 10%IB 2R | 125 | 40.8 | 1.43 | $19,504 | $5,382 | $-1,808 |
| 9 | L455 | LONG poke a1 10%IB 2R | 121 | 40.5 | 1.43 | $19,587 | $5,382 | $-1,808 |
| 10 | L377 | LONG 5pts a5 0.5ATR IBmid | 114 | 45.6 | 1.42 | $16,900 | $3,960 | $-1,535 |
| 11 | L261 | LONG 3pts a1 10%IB IBmid | 125 | 35.2 | 1.41 | $19,275 | $4,135 | $-1,606 |
| 12 | L259 | LONG 3pts a1 +5pt 2R | 125 | 40.8 | 1.38 | $10,045 | $4,095 | $-1,640 |
| 13 | L265 | LONG 3pts a1 0.5ATR IBmid | 125 | 29.6 | 1.38 | $14,182 | $4,135 | $-1,501 |
| 14 | L293 | LONG 3pts a3 10%IB IBmid | 119 | 46.2 | 1.38 | $18,048 | $3,570 | $-1,654 |
| 15 | L313 | LONG 3pts a5 0.5ATR IBmid | 111 | 45.9 | 1.38 | $15,093 | $3,960 | $-1,535 |
| 16 | L341 | LONG 5pts a2 10%IB IBmid | 124 | 41.9 | 1.38 | $19,328 | $3,738 | $-1,754 |
| 17 | L343 | LONG 5pts a2 10%IB 2R | 124 | 39.5 | 1.37 | $20,090 | $4,642 | $-1,754 |
| 18 | L347 | LONG 5pts a2 0.5ATR 2R | 124 | 38.7 | 1.37 | $15,984 | $4,237 | $-1,551 |
| 19 | L371 | LONG 5pts a5 +5pt 2R | 115 | 34.8 | 1.37 | $16,725 | $6,305 | $-1,520 |
| 20 | L469 | LONG poke a2 10%IB IBmid | 118 | 40.7 | 1.37 | $17,537 | $3,630 | $-1,754 |

## IBH SHORT with Filters -- Top 20

| # | ID | Config | Trades | WR% | PF | P&L |
|---|------|--------|--------|-----|-----|-----|
| 1 | SF533 | SHORT 5pts a2 0.5ATR IBmid [full] | 80 | 30.0 | 1.43 | $9,329 |
| 2 | SF537 | SHORT 10pts a3 10%IB IBmid [dt+AM] | 101 | 39.6 | 1.34 | $12,676 |
| 3 | SF531 | SHORT 5pts a2 0.5ATR IBmid [dt+bias] | 104 | 27.9 | 1.28 | $8,232 |
| 4 | SF530 | SHORT 5pts a2 0.5ATR IBmid [dt+AM] | 93 | 26.9 | 1.24 | $6,766 |
| 5 | SF535 | SHORT 10pts a3 10%IB IBmid [dt+ib80] | 112 | 41.1 | 1.24 | $10,795 |
| 6 | SF534 | SHORT 10pts a3 10%IB IBmid [dt] | 119 | 39.5 | 1.20 | $9,184 |
| 7 | SF536 | SHORT 10pts a3 10%IB IBmid [dt+ib100] | 102 | 39.2 | 1.20 | $8,662 |
| 8 | SF523 | SHORT 5pts a3 10%IB IBmid [dt+AM] | 89 | 34.8 | 1.19 | $6,772 |
| 9 | SF540 | SHORT 10pts a3 10%IB IBmid [full] | 88 | 39.8 | 1.19 | $6,635 |
| 10 | SF519 | SHORT 5pts a2 10%IB IBmid [full] | 80 | 33.8 | 1.18 | $5,258 |
| 11 | SF539 | SHORT 10pts a3 10%IB IBmid [dt+vwap] | 116 | 38.8 | 1.18 | $8,658 |
| 12 | SF544 | SHORT poke a2 10%IB IBmid [dt+AM] | 80 | 31.2 | 1.18 | $5,603 |
| 13 | SF552 | SHORT 5pts a2 10%IB 1R [dt+bias] | 104 | 53.8 | 1.18 | $4,765 |
| 14 | SF558 | SHORT 5pts a5 10%IB IBmid [dt+AM] | 83 | 41.0 | 1.18 | $6,000 |
| 15 | SF517 | SHORT 5pts a2 10%IB IBmid [dt+bias] | 104 | 34.6 | 1.16 | $6,260 |
| 16 | SF528 | SHORT 5pts a2 0.5ATR IBmid [dt+ib80] | 105 | 27.6 | 1.16 | $5,101 |
| 17 | SF529 | SHORT 5pts a2 0.5ATR IBmid [dt+ib100] | 97 | 26.8 | 1.14 | $4,396 |
| 18 | SF516 | SHORT 5pts a2 10%IB IBmid [dt+AM] | 93 | 31.2 | 1.12 | $4,582 |
| 19 | SF527 | SHORT 5pts a2 0.5ATR IBmid [dt] | 110 | 26.4 | 1.12 | $4,016 |
| 20 | SF532 | SHORT 5pts a2 0.5ATR IBmid [dt+vwap] | 109 | 26.6 | 1.12 | $4,194 |

## Second-Touch Analysis

| ID | Config | Trades | WR% | PF | P&L |
|------|--------|--------|-----|-----|-----|
| L2T567 | LONG 2nd-touch 5pts a2 0.5ATR IBmid | 95 | 37.9 | 1.67 | $20,630 |
| L2T563 | LONG 2nd-touch 5pts a2 10%IB IBmid | 95 | 43.2 | 1.65 | $23,554 |
| L2T565 | LONG 2nd-touch 5pts a3 10%IB IBmid | 92 | 46.7 | 1.54 | $19,646 |
| S2T566 | SHORT 2nd-touch 5pts a2 0.5ATR IBmid | 108 | 25.9 | 1.07 | $2,363 |
| S2T562 | SHORT 2nd-touch 5pts a2 10%IB IBmid | 108 | 32.4 | 1.03 | $1,205 |
| S2T564 | SHORT 2nd-touch 5pts a3 10%IB IBmid | 104 | 34.6 | 1.00 | $-6 |

## Day Type Breakdown -- Best SHORT: SHORT poke a1 0.5ATR 1R

| Day Type | Trades | WR% | PF | P&L |
|----------|--------|-----|-----|-----|
| b_day | 20 | 75.0 | 2.65 | $2,753 |
| neutral | 28 | 67.9 | 1.96 | $3,346 |
| p_day | 49 | 51.0 | 1.10 | $782 |
| trend_down | 9 | 55.6 | 1.01 | $19 |
| trend_up | 31 | 51.6 | 1.12 | $609 |

## Day Type Breakdown -- Best LONG: LONG 3pts a2 10%IB 2R

| Day Type | Trades | WR% | PF | P&L |
|----------|--------|-----|-----|-----|
| b_day | 26 | 61.5 | 4.00 | $17,636 |
| neutral | 36 | 55.6 | 2.54 | $16,522 |
| p_day | 31 | 25.8 | 1.04 | $746 |
| trend_down | 23 | 21.7 | 0.36 | $-9,444 |
| trend_up | 6 | 50.0 | 2.31 | $2,508 |

## IB Range Impact -- Best SHORT

| IB Range | Trades | WR% | PF | P&L | Avg IB |
|----------|--------|-----|-----|-----|--------|
| <100 | 21 | 28.6 | 0.41 | $-1,759 | 82 |
| 100-150 | 40 | 65.0 | 1.19 | $1,065 | 122 |
| 150-200 | 38 | 60.5 | 1.62 | $2,826 | 176 |
| 200-300 | 27 | 66.7 | 1.86 | $3,393 | 249 |
| 300+ | 11 | 63.6 | 1.90 | $1,984 | 364 |

## Time-of-Day -- Best SHORT

| Time | Trades | WR% | PF | P&L |
|------|--------|-----|-----|-----|
| 10:30-11:00 | 75 | 45.3 | 0.77 | $-3,402 |
| 11:00-11:30 | 21 | 76.2 | 2.03 | $2,227 |
| 11:30-12:00 | 11 | 72.7 | 3.16 | $1,513 |
| 12:00-13:00 | 18 | 61.1 | 2.92 | $2,962 |
| 13:00-14:00 | 12 | 91.7 | 23.69 | $4,209 |

## IBH SHORT vs IBL LONG -- Head-to-Head

Top 20 matching configs (same params, different direction):

| Config | S.Trades | S.WR | S.PF | S.P&L | L.Trades | L.WR | L.PF | L.P&L |
|--------|----------|------|------|-------|----------|------|------|-------|
| poke a1 0.5ATR 1R | 137 | 58.4 | 1.39 | $7,509 | 121 | 52.9 | 1.03 | $856 |
| 10pts a3 +5pt 1R | 150 | 56.7 | 1.35 | $9,505 | 132 | 48.5 | 0.94 | $-2,200 |
| 10pts a3 0.5ATR 1R | 150 | 58.0 | 1.30 | $10,204 | 132 | 50.8 | 1.10 | $4,253 |
| poke a1 10%IB 1R | 137 | 56.9 | 1.25 | $7,610 | 121 | 56.2 | 1.17 | $5,868 |
| poke a1 +5pt IBmid | 137 | 18.2 | 1.22 | $6,290 | 121 | 21.5 | 1.03 | $1,005 |
| 3pts a3 0.5ATR 1R | 132 | 59.1 | 1.19 | $5,527 | 119 | 52.9 | 1.28 | $9,848 |
| poke a3 0.5ATR 1R | 128 | 58.6 | 1.19 | $5,478 | 115 | 50.4 | 1.16 | $5,597 |
| poke a3 0.5ATR OppEdge | 128 | 18.8 | 1.19 | $9,835 | 115 | 20.9 | 0.93 | $-3,711 |
| poke a1 +5pt OppEdge | 137 | 10.2 | 1.19 | $6,185 | 121 | 12.4 | 0.93 | $-2,530 |
| 10pts a3 0.5ATR OppEdge | 150 | 19.3 | 1.18 | $11,244 | 132 | 22.0 | 0.91 | $-5,883 |
| poke a2 0.5ATR OppEdge | 133 | 15.0 | 1.18 | $8,979 | 118 | 20.3 | 1.06 | $3,110 |
| poke a3 +5pt 1R | 128 | 55.5 | 1.18 | $4,105 | 115 | 50.4 | 1.10 | $3,145 |
| 5pts a5 0.5ATR OppEdge | 129 | 21.7 | 1.18 | $10,798 | 115 | 27.8 | 1.23 | $13,019 |
| 5pts a3 0.5ATR OppEdge | 136 | 18.4 | 1.17 | $9,283 | 122 | 23.8 | 1.13 | $7,306 |
| 5pts a2 0.5ATR OppEdge | 142 | 16.2 | 1.17 | $8,923 | 124 | 23.4 | 1.30 | $15,787 |
| 3pts a1 0.5ATR 1R | 142 | 57.0 | 1.15 | $3,485 | 125 | 56.0 | 1.16 | $4,400 |
| poke a1 +5pt 2R | 137 | 38.0 | 1.15 | $3,210 | 121 | 38.8 | 1.30 | $8,035 |
| 10pts a2 0.5ATR OppEdge | 155 | 17.4 | 1.14 | $8,724 | 134 | 21.6 | 0.97 | $-2,070 |
| poke a1 0.5ATR OppEdge | 137 | 12.4 | 1.13 | $5,460 | 121 | 15.7 | 1.05 | $2,390 |
| 3pts a5 0.5ATR OppEdge | 127 | 21.3 | 1.13 | $7,243 | 112 | 27.7 | 1.18 | $10,037 |

## Comparison to Existing B-Day Strategy

**Existing B-Day** (memory): 26 trades, 57.7% WR, PF 1.76, +$5,767

B-Day uses quality gates (FVG + delta + multi-touch + volume spike), quality >= 2, delta > 0.
This study uses simpler acceptance-based entries.

- Best SHORT: 137 unique sessions
- Best LONG: 122 unique sessions
- Overlap: 35 (both sides same session)
- Complement: 102 SHORT-only, 87 LONG-only

## Top 5 Winners/Losers -- Best SHORT

**Winners:**

| Date | Entry | Exit | Reason | PnL | IB Range | Day Type | Touch# |
|------|-------|------|--------|-----|----------|----------|--------|
| 2025-03-04 00:00:00 | 21308.00 | 21254.92 | TARGET | $1,047 | 355 | neutral | 1 |
| 2025-11-21 00:00:00 | 24529.25 | 24476.51 | TARGET | $1,040 | 271 | p_day | 69 |
| 2026-02-13 00:00:00 | 24840.00 | 24790.87 | TARGET | $968 | 288 | neutral | 9 |
| 2025-03-20 00:00:00 | 20769.25 | 20732.98 | TARGET | $710 | 331 | b_day | 8 |
| 2025-04-02 00:00:00 | 20310.00 | 20278.39 | TARGET | $617 | 304 | p_day | 1 |

**Losers:**

| Date | Entry | Exit | Reason | PnL | IB Range | Day Type | Touch# |
|------|-------|------|--------|-----|----------|----------|--------|
| 2025-11-14 00:00:00 | 25272.75 | 25304.41 | STOP | $-648 | 402 | p_day | 1 |
| 2025-10-14 00:00:00 | 24956.50 | 24989.78 | STOP | $-681 | 301 | p_day | 1 |
| 2025-04-01 00:00:00 | 20152.00 | 20185.31 | STOP | $-681 | 201 | trend_up | 1 |
| 2026-02-06 00:00:00 | 24970.75 | 25005.50 | STOP | $-710 | 283 | trend_up | 1 |
| 2026-01-07 00:00:00 | 25838.25 | 25887.63 | STOP | $-1,003 | 109 | b_day | 6 |

## Touch Number Analysis -- Best SHORT

| Touch# | Trades | WR% | PF | P&L |
|--------|--------|-----|-----|-----|
| 1 | 65 | 55.4 | 1.04 | $460 |
| 2 | 12 | 25.0 | 0.35 | $-1,359 |
| 3 | 6 | 83.3 | 4.77 | $1,265 |
| 4 | 6 | 50.0 | 0.60 | $-347 |
| 5 | 8 | 50.0 | 1.62 | $691 |
| 6 | 7 | 42.9 | 0.35 | $-1,079 |
| 7 | 4 | 75.0 | 8.44 | $1,106 |
| 8 | 1 | 100.0 | inf | $710 |
| 9 | 2 | 50.0 | 2.03 | $491 |
| 11 | 1 | 0.0 | 0.00 | $-243 |
| 12 | 2 | 50.0 | 0.36 | $-225 |
| 13 | 1 | 100.0 | inf | $357 |
| 14 | 4 | 75.0 | 2.17 | $467 |
| 16 | 1 | 100.0 | inf | $172 |
| 17 | 2 | 100.0 | inf | $775 |
| 21 | 2 | 50.0 | 1.74 | $58 |
| 27 | 1 | 100.0 | inf | $364 |
| 40 | 1 | 100.0 | inf | $154 |
| 48 | 1 | 100.0 | inf | $200 |
| 57 | 1 | 100.0 | inf | $601 |
| 64 | 1 | 100.0 | inf | $236 |
| 66 | 1 | 100.0 | inf | $220 |
| 67 | 1 | 100.0 | inf | $392 |
| 69 | 1 | 100.0 | inf | $1,040 |
| 74 | 1 | 0.0 | 0.00 | $-168 |
| 89 | 1 | 100.0 | inf | $391 |
| 94 | 1 | 100.0 | inf | $315 |
| 126 | 1 | 100.0 | inf | $266 |
| 139 | 1 | 100.0 | inf | $199 |

## Parameter Sensitivity (SHORT unfiltered)

### By Touch Tolerance

| Value | Configs | Avg Trades | Avg WR% | Avg PF | Median P&L |
|-------|---------|------------|---------|--------|------------|
| 10pts | 64 | 151 | 34.5 | 0.95 | $-2,466 |
| 3pts | 64 | 135 | 32.6 | 0.88 | $-6,806 |
| 5pts | 64 | 138 | 32.1 | 0.89 | $-5,874 |
| poke | 64 | 130 | 33.0 | 0.95 | $-3,279 |

### By Acceptance Bars

| Value | Configs | Avg Trades | Avg WR% | Avg PF | Median P&L |
|-------|---------|------------|---------|--------|------------|
| a1 | 64 | 146 | 32.3 | 0.98 | $-1,498 |
| a2 | 64 | 142 | 32.0 | 0.91 | $-4,866 |
| a3 | 64 | 136 | 33.3 | 0.93 | $-5,165 |
| a5 | 64 | 131 | 34.4 | 0.84 | $-9,318 |

### By Stop Model

| Value | Configs | Avg Trades | Avg WR% | Avg PF | Median P&L |
|-------|---------|------------|---------|--------|------------|
| +5pt | 64 | 139 | 29.9 | 0.93 | $-2,942 |
| 0.5ATR | 64 | 139 | 32.6 | 0.97 | $-2,801 |
| 10%IB | 64 | 139 | 34.4 | 0.94 | $-3,895 |
| 30pt | 64 | 139 | 35.2 | 0.82 | $-14,830 |

### By Target Model

| Value | Configs | Avg Trades | Avg WR% | Avg PF | Median P&L |
|-------|---------|------------|---------|--------|------------|
| 1R | 64 | 139 | 50.3 | 0.93 | $-3,222 |
| 2R | 64 | 139 | 32.5 | 0.85 | $-7,646 |
| IBmid | 64 | 139 | 29.8 | 0.89 | $-6,610 |
| OppEdge | 64 | 139 | 19.6 | 1.00 | $-281 |

## Recommendation

**MARGINAL**: IBH SHORT slightly positive but needs work.
Best: SHORT poke a1 0.5ATR 1R -- 137 trades, 58.4% WR, PF 1.39

Consider: tighter filters, order flow confirmation, or cross-instrument test (ES/YM).
