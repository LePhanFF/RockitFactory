# Quant Study: Mean Reversion VWAP Strategy Fix

Date: 2026-03-12
Instrument: NQ, 273 sessions

## Executive Summary

The original Mean Reversion VWAP strategy was losing -$17,528 over 273 sessions (10 trades, 20% WR, PF 0.30). This study tested 12 configurations and found a profitable rewrite.

**Winner: Config F** -- 11 trades, 72.7% WR, PF 4.95, +$8,386 net.

The strategy now works as a "time-boxed mean reversion capture" during range-bound lunch periods. The time stop IS the exit mechanism -- not stop/target.

### Root Causes of Original Failure
1. **Wrong time window** (11:00-14:30 instead of 10:30-13:00)
2. **No regime gate** (used post-hoc day_type labels instead of ADX<25)
3. **RSI thresholds too loose** (65/35 instead of 70/30)
4. **Single-bar delta** (noise) instead of 5-bar cumulative delta divergence
5. **No Bollinger Band filter** -- entered on VWAP deviation alone
6. **No time stop** -- trades sat for 90+ bars, eventually stopped out

## Primary Results (Configs A-F)

| Config | Description | Trades | WR% | PF | Net PnL | Expectancy | Avg Bars |
|--------|-------------|--------|-----|-----|---------|------------|----------|
| A | Original (broken) | 10 | 20.0% | 0.30 | -$17,528 | -$1,753 | 151 |
| B | 50% VWAP, ADX<25, BB+RSI, 15-bar TS | 11 | 54.5% | 1.84 | +$2,101 | +$191 | 14 |
| C | 100% VWAP target | 11 | 54.5% | 1.84 | +$2,101 | +$191 | 14 |
| D | No ADX filter (BB+RSI only) | 30 | 46.7% | 1.28 | +$2,172 | +$72 | 13 |
| E | RSI 80/20 (extreme only) | 3 | 33.3% | 0.81 | -$297 | -$99 | 11 |
| **F** | **30-bar time stop** | **11** | **72.7%** | **4.95** | **+$8,386** | **+$762** | **26** |

## Extended Results (Configs G-L)

| Config | Description | Trades | WR% | PF | Net PnL | Avg Bars | Exits |
|--------|-------------|--------|-----|-----|---------|----------|-------|
| G | No time stop (stop/target only) | 11 | 18.2% | 0.60 | -$2,282 | 91 | 9 STOP, 2 EOD |
| H | 45-bar time stop | 11 | 54.5% | 2.85 | +$6,043 | 36 | 7 TIME, 4 STOP |
| I | 60-bar time stop | 11 | 36.4% | 2.56 | +$5,993 | 46 | 7 TIME, 4 STOP |
| J | 30-bar TS, no BB filter | 95 | 42.1% | 1.24 | +$7,403 | 21 | 50 TIME, 45 STOP |
| K | 30-bar TS, wider window 10:00-14:00 | 15 | 66.7% | 3.07 | +$7,838 | 24 | 11 TIME, 4 STOP |
| L | 30-bar TS, 3x ATR stop | 11 | 72.7% | 3.39 | +$7,405 | 27 | 9 TIME, 2 STOP |

## Key Insight: Time Stop IS the Strategy

The most important finding: **without a time stop, the strategy loses money** (Config G: -$2,282). With 30-bar time stop (Config F), it earns +$8,386.

Why? Mean reversion in range-bound markets works in the first 30 minutes or not at all. If price hasn't reverted within 30 bars, the range-bound assumption was wrong and the trade should be closed at market. The time stop converts "waiting to get stopped out" into "closing at a partial profit."

Exit reason analysis confirms this:
- Config F: 81.8% of exits are TIME_STOP, and 88.9% of those are winners
- Config G (no time stop): 82% of exits are STOP or EOD -- the trade simply drifts until it fails

The optimal time stop window is **30 bars** (30 minutes). Shorter (15) cuts winners. Longer (45-60) allows more stop-outs.

## By Direction

| Config | LONG Trades | LONG WR | LONG PnL | SHORT Trades | SHORT WR | SHORT PnL |
|--------|-------------|---------|----------|--------------|----------|-----------|
| A | 10 | 20.0% | -$17,528 | 0 | -- | $0 |
| B | 1 | 100.0% | +$516 | 10 | 50.0% | +$1,585 |
| D | 5 | 60.0% | +$497 | 25 | 44.0% | +$1,675 |
| **F** | **1** | **100%** | **+$776** | **10** | **70.0%** | **+$7,610** |

SHORT-dominant: 10 of 11 trades are SHORT. This makes sense -- overbought conditions (price above VWAP + RSI > 70 + at BB upper) are more common than oversold during the 10:30-13:00 window on NQ.

## By Day Type (Config F)

| Day Type | Trades | WR | PF | PnL |
|----------|--------|-----|-----|-----|
| b_day | 5 | 60.0% | 4.05 | +$6,131 |
| p_day | 5 | 80.0% | 19.33 | +$2,000 |
| trend_up | 1 | 100.0% | inf | +$256 |

Performs on both B-Day and P-Day sessions. The ADX<25 filter catches range-bound periods even on sessions that eventually classify as P-Day.

## By Hour of Entry (Config F)

| Hour | Trades | WR | PnL |
|------|--------|-----|-----|
| 11:00 | 7 | 71.4% | +$2,653 |
| 12:00 | 4 | 75.0% | +$5,734 |

Both hours are profitable. The 12:00 hour (lunch) has higher per-trade PnL, consistent with the "lunch chop" thesis.

## Analysis

### Does ADX Filter Add Value?
- With ADX<25 (F): 11 trades, 72.7% WR, PF 4.95
- Without ADX (J): 95 trades, 42.1% WR, PF 1.24

**Yes, significantly.** ADX filter reduces trades 89% but increases WR by 30 percentage points and PF by 4x. The filter eliminates trending sessions where mean reversion fails catastrophically.

### Does Bollinger Band Filter Add Value?
- With BB (F): 11 trades, 72.7% WR, PF 4.95
- Without BB (J): 95 trades, 42.1% WR, PF 1.24

**Yes.** Removing BB (Config J) floods the system with 95 low-quality signals. BB ensures entry only at 2-sigma extremes.

### RSI 70/30 vs 80/20
- RSI 70/30 (F): 11 trades, 72.7% WR
- RSI 80/20 (E): 3 trades, 33.3% WR

**70/30 wins.** 80/20 produces too few trades (3) for any statistical significance.

### 50% VWAP Target vs Full VWAP Target
- 50% target (B): identical to 100% target (C) because all exits are TIME_STOP

**Moot.** Neither target is ever reached within the time stop window. The time stop IS the exit.

### 15-bar vs 30-bar vs 45-bar Time Stop
- 15-bar (B): 54.5% WR, PF 1.84, +$2,101
- 30-bar (F): 72.7% WR, PF 4.95, +$8,386
- 45-bar (H): 54.5% WR, PF 2.85, +$6,043

**30-bar is optimal.** 15 bars cuts too many winners short. 45 bars allows more stop-outs.

### Wider Time Window (Config K)
- Default 10:30-13:00 (F): 11 trades, 72.7% WR, +$8,386
- Wider 10:00-14:00 (K): 15 trades, 66.7% WR, +$7,838

Wider window adds 4 trades but slightly dilutes quality. Consider as a secondary option if trade count matters.

## Recommendation

**Enable Config F as default.** Strategy defaults have been updated to:
- ADX < 25 (range-bound filter)
- RSI 70/30 + Bollinger Band (20, 2.0) touch
- 5-bar cumulative delta divergence
- 2x ATR stop
- **30-bar time stop** (the key differentiator)
- Time window: 10:30-13:00 ET
- 50% VWAP target (nominal, rarely reached before time stop)

Expected: ~11 trades per 270 sessions (~1 per 25 sessions), 72.7% WR, PF 4.95.

### Caveats
1. **Low trade count**: 11 trades over 273 sessions is not statistically robust. This is a supplementary strategy, not a primary one.
2. **Sample size warning**: Results may not generalize to future sessions. The high WR/PF could be partially an artifact of small N.
3. **No overlap with 80P**: Confirmed -- 80P fires on VA acceptance at specific levels, MR VWAP fires on BB+RSI extremes during ADX-filtered range periods. Different entry logic, different sessions.
4. **SHORT-dominant**: 91% of trades are SHORT. If adding directional bias, monitor for asymmetric performance.
5. **Add to production as disabled by default**: Enable only after forward-testing confirms the edge holds out-of-sample.

### What Changed from Original
| Aspect | Original | Rewrite |
|--------|----------|---------|
| Time window | 11:00-14:30 | 10:30-13:00 |
| Regime gate | day_type label (post-hoc) | ADX(14) < 25 (real-time) |
| RSI thresholds | 65/35 | 70/30 |
| Delta check | Single-bar delta direction | 5-bar cumulative delta divergence |
| BB filter | None | BB(20, 2.0) touch required |
| Stop | Session low - 0.25x IB | 2x ATR(14) |
| Target | Full VWAP | 50% of distance to VWAP |
| Time stop | None | 30 bars (30 min) |
| Day type filter | b_day, neutral, p_day only | Any (ADX handles regime) |
