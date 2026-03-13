# Quant Study: Trend Day Bull/Bear Strategy Fix

**Date**: 2026-03-12
**Instrument**: NQ (273 sessions)
**Study target**: 58% WR, 2.8 PF, $1,465/day
**Result**: Strategy cannot be made profitable with VWAP pullback entry model. Recommend keeping DISABLED.

## Problem Statement

Trend Day Bull/Bear was the #1 priority disabled strategy. Root causes identified in roadmap:
1. Day type gate required `trend_up`/`trend_down` label -- not available until late in session
2. Only VWAP pullback entry worked (IBH retest had 26.7% WR)
3. Tiny 0.4x IB stops got hit constantly; ambitious 2.0x IB targets never reached
4. No multi-timeframe trend filter to confirm actual trend days

## Methodology

Three iterations of the strategy were tested across 14+ configurations each, totaling 40+ unique backtests on 273 NQ sessions.

## Iteration History

| Version | Approach | Configs | Key Result |
|---------|----------|---------|------------|
| v4a | 15-min ADX+EMA from IB bars only | 7 configs | 0-5 trades total. Only 4 x 15-min bars from IB = useless for EMA20/50 |
| v4b | 1-min EMA20/EMA50 from data | 7 configs | 129 trades at 9.3% WR, 92% stopped. EMA alignment too noisy, fires on b_day |
| v4b-G | 1-min EMA, no other filters | 1 config | **Bear: 71t, 15.5% WR, PF 1.57, +$11.8K.** Bull: 58t, 1.7% WR, -$16K |
| v4c | Extension-based (0.25x-0.75x IB) + VWAP pullback | 14 configs | 2-57 trades per config, all negative or marginal |

## v4c Detailed Results (Extension-Based, Final Iteration)

### Comparison Table

| Config | Trades | WR | PF | Net PnL | Notes |
|--------|--------|-----|------|---------|-------|
| B: Strict (ext+delta+IBH) | 2 | 50.0% | 3.02 | +$1,498 | Too few trades |
| D: No IBH check, 1.5x IB | 17 | 11.8% | 0.95 | -$287 | Near breakeven |
| G: No IBH + No delta, 1.5x IB | 20 | 10.0% | 0.81 | -$1,357 | |
| J: Ext 0.25x, relaxed, 1.5x IB | 57 | 14.0% | 0.67 | -$6,162 | More trades = more losses |
| K: Ext 0.75x, relaxed, 1.5x IB | 8 | 12.5% | 0.67 | -$1,094 | Bull PF 2.17 (+$1,206) |
| **L: Relaxed, wide 1.0 ATR, 1.5x IB** | **25** | **16.0%** | **0.99** | **-$52** | **Near breakeven. Bear +$3,133** |
| M: Relaxed, wide 1.0 ATR, 2R | 25 | 24.0% | 0.81 | -$1,450 | |

### Direction Split (Key Configs)

| Config | LONG # | LONG WR | LONG PnL | SHORT # | SHORT WR | SHORT PnL |
|--------|--------|---------|----------|---------|----------|-----------|
| D: NoIBH, 1.5xIB | 7 | 14.3% | -$130 | 10 | 10.0% | -$157 |
| K: Ext0.75 | 3 | 33.3% | +$1,206 | 5 | 0.0% | -$2,300 |
| L: Wide 1.0 ATR | 9 | 0.0% | -$3,185 | 16 | 25.0% | +$3,133 |

### Exit Reason Distribution (Config L)

- STOP: 24 (96.0%)
- TARGET: 1 (4.0%)

### Day Type Distribution (Config L)

| Day Type | Trades | WR | Net PnL |
|----------|--------|-----|---------|
| b_day | 19 | 21.1% | +$1,954 |
| p_day | 6 | 0.0% | -$2,007 |

## Root Cause Analysis

### Why VWAP Pullback Fails for Trend Days

The fundamental issue is a **structural conflict between trend confirmation and VWAP proximity**:

1. **At extension time (0.5x IB above IBH), price is 9.9 ATR away from VWAP on average.** Only 1/117 sessions had price within 0.5 ATR of VWAP at extension confirmation.

2. **Price does return to VWAP later (64% of sessions)**, but by then the trend structure has often broken down. The price > IBH requirement blocks 7/8 potential VWAP pullback entries because price has fallen back into the IB range.

3. **Removing the price > IBH requirement** unlocks more trades (17-25) but degrades quality because we're now entering on mean-reversion-like pullbacks on balance days, not trend continuations.

4. **The 1-min EMA alignment filter is too noisy.** EMA20 > EMA50 on 1-min bars is true for much of any session and doesn't discriminate trend vs balance days. This caused v4b to fire on b_day sessions 95% of the time.

5. **15-min indicators from IB bars are inadequate.** Only 4 x 15-min bars from the 60-min IB period -- far too few for meaningful EMA20/50 computation.

### Why Bear > Bull Consistently

Across all iterations, the bear side outperformed bull:
- v4b Config G: Bear +$11,788 vs Bull -$15,994
- v4c Config L: Bear +$3,133 vs Bull -$3,185

This is likely because:
1. **NQ has a structural long bias** -- 1-min EMA20 > EMA50 is the default state, making long entries ubiquitous and low-quality
2. **Short squeezes are sharper than selloffs** on NQ, meaning shorts that work tend to produce larger winners
3. **VWAP rejection on downside** (sellers pushing price below VWAP) is a cleaner signal than VWAP bounce on upside

## What Was Tried and Eliminated

| Filter | Impact | Conclusion |
|--------|--------|------------|
| Day type gate (original) | ~0 trades | Eliminated -- label not available at signal time |
| 15-min EMA from IB | 0-5 trades | Eliminated -- too few bars |
| 1-min EMA alignment | 129 trades, 9.3% WR | Eliminated -- too noisy |
| ADX(14) on 15-min | 5 trades | Eliminated -- too few bars |
| Extension 0.5x IB | 2-25 trades | Partially works but insufficient trade count |
| Extension 0.25x IB | 57 trades, 14% WR | Too loose -- fires on balance days |
| Extension 0.75x IB | 8 trades | Too strict -- too few trades |
| VWAP slope (rising/falling) | No incremental value | Eliminated |
| Price > IBH / < IBL | Blocks 87.5% of valid pullbacks | Eliminated |
| Delta confirmation | Blocks 75% of entries | Marginal value |
| VWAP proximity 0.5 ATR | 20 trades | Too tight |
| VWAP proximity 1.0 ATR | 25 trades | Nearly breakeven |

## Verdict

**The Trend Day Bull/Bear VWAP pullback strategy cannot be made profitable** with the current entry model on NQ. The study target of 58% WR, 2.8 PF is unachievable.

The closest we got: Config L with 25 trades, 16% WR, PF 0.99, -$52 net. This is essentially a coin flip after costs.

### Why the Study Target Was Unreachable

The 58% WR / 2.8 PF / $1,465/day target from the strategy studies appears to be based on:
- **Hindsight day type classification** -- knowing it's a trend day AFTER the session ends
- **Optimal entry timing** -- entering at the best possible pullback, not the first one
- **Manual trade management** -- discretionary exits, not mechanical stops

In a mechanical backtest where day type must be inferred in real-time, these numbers are not achievable.

## Recommendations

### 1. Keep Trend Day Bull/Bear DISABLED

No configuration justifies enabling. The strategy loses money or breaks even across all tested parameters.

### 2. Consider Bear-Only as a Research Strategy

The bear side showed consistent edge:
- v4b Bear-only (EMA filter, no other gates): 71 trades, 15.5% WR, PF 1.57, +$11,788
- v4c Config L Bear: 16 trades, 25% WR, PF 1.62, +$3,133

A standalone "Trend Bear VWAP Rejection" strategy might be worth exploring with additional study.

### 3. Alternative Entry Models to Investigate

If revisiting this strategy later:
- **EMA pullback entry** (not VWAP): Enter when price touches EMA20 from above after extension
- **FVG entry**: Enter at unfilled Fair Value Gap after extension
- **Time-based**: Use fixed time windows (e.g., 11:30-12:30) when trends typically consolidate
- **Higher-timeframe confirmation**: Use daily EMA200/50 alignment as the trend filter, not intraday

### 4. Prioritize Other Strategies

The enabled portfolio (OR Rev, OR Accept, 80P, B-Day) already produces $125K+ over 259 sessions. Engineering effort is better spent improving those strategies than trying to fix Trend Day.

## Files Modified

- `packages/rockit-core/src/rockit_core/strategies/trend_bull.py` -- v4c rewrite (extension-based)
- `packages/rockit-core/src/rockit_core/strategies/trend_bear.py` -- v4c rewrite (extension-based)
- `scripts/_study_trend_day.py` -- study script with 14+ configurations
- `data/results/trend_day_study_*.json` -- raw results

## Data

- 273 NQ sessions (2025-02 through 2026-03)
- 372,039 total bars
- 87 computed feature columns
- 40+ backtest configurations tested
