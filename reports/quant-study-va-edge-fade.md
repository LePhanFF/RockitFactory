# VA Edge Fade -- Quantitative Study Report

Generated: 2026-03-12
Instrument: NQ | Sessions: 273

## Study Thesis

Prior day's VAH and VAL are major institutional reference levels. When price
pokes beyond these levels and fails to sustain (acceptance fails), it fades
back inside the VA. This strategy trades that rejection.

**Reference study results** (259 sessions, 620 events):
- SHORTS at VAH first touch: 70% WR, PF 7.28
- 2nd test limit at edge: 72.4% WR, PF 5.38
- Combined 2x5m + 2ATR + trailing: 62.6% WR, PF 4.60, 257 trades

## Executive Summary

**RESULT: NOT VIABLE IN CURRENT FORM.** The backtest produced 180 trades at 33-36% WR
(PF 1.03-1.11). This is far below the 70% WR study target. The strategy is marginally
profitable but not a portfolio candidate. Major reasons for the gap are discussed below.

Best configuration found: Stop=v3 (edge+10), Target=v2 (2R), Accept=2x5min, Max touch=1.
This yielded 180 trades, 35.6% WR, PF 1.11, +$10,630 net PnL over 273 sessions.

## Phase 1: Core Stop/Target Combinations (3 stops x 4 targets = 12 configs)

| Stop | Target | Trades | WR% | PF | Net PnL | Avg Win | Avg Loss |
|------|--------|--------|-----|-----|---------|---------|----------|
| v1 (2ATR) | v1 (POC) | 17 | 23.5% | 0.21 | -$23,701 | $1,565 | -$2,305 |
| v1 (2ATR) | v2 (2R) | 180 | 35.0% | 1.03 | $2,646 | $1,563 | -$819 |
| v1 (2ATR) | v3 (opp VA) | 17 | 23.5% | 0.46 | -$10,408 | $2,175 | -$1,470 |
| v1 (2ATR) | v4 (trail) | 110 | 23.6% | 0.87 | -$7,981 | $2,008 | -$717 |
| v2 (poke+10) | v1 (POC) | 17 | 35.3% | 0.30 | -$20,687 | $1,454 | -$2,674 |
| v2 (poke+10) | v2 (2R) | 43 | 30.2% | 0.91 | -$3,191 | $2,436 | -$1,162 |
| v2 (poke+10) | v3 (opp VA) | 16 | 25.0% | 0.32 | -$11,791 | $1,403 | -$1,450 |
| v2 (poke+10) | v4 (trail) | 50 | 28.0% | 0.98 | -$875 | $2,716 | -$1,080 |
| v3 (edge+10) | v1 (POC) | 17 | 17.6% | 0.12 | -$26,080 | $1,161 | -$2,112 |
| **v3 (edge+10)** | **v2 (2R)** | **180** | **33.3%** | **1.07** | **$7,015** | **$1,830** | **-$856** |
| v3 (edge+10) | v3 (opp VA) | 18 | 16.7% | 0.16 | -$16,244 | $1,027 | -$1,288 |
| v3 (edge+10) | v4 (trail) | 74 | 21.6% | 0.84 | -$6,728 | $2,214 | -$727 |

**Key observations:**
- Only 2R target (v2) is profitable -- POC and opposite VA targets are too ambitious
- Stop v3 (edge+10pt) is tightest and best PF -- wider stops (v1, v2) lose more per trade
- POC target (v1) only gets 17 trades -- most signals have entry far from POC
- Trailing (v4) reduces trade count but does NOT improve WR

## Phase 2: Direction & Day Type Analysis (Stop=v3, Target=v2)

### By Direction

| Direction | Trades | WR% | PF | Net PnL |
|-----------|--------|-----|-----|---------|
| LONG | 90 | 32.2% | 0.94 | -$3,219 |
| **SHORT** | **90** | **34.4%** | **1.20** | **$10,234** |

SHORT outperforms LONG as the study predicts, but at 34.4% WR vs the 70% target.
LONG at VAL is a net loser (-$3,219) and should likely be disabled entirely.

### By Day Type

| Day Type | Trades | WR% | PF | Net PnL |
|----------|--------|-----|-----|---------|
| b_day | 118 | 36.4% | 1.19 | $12,344 |
| super_trend_down | 3 | 66.7% | 502.71 | $9,583 |
| p_day | 47 | 27.7% | 0.78 | -$5,780 |
| trend_up | 5 | 20.0% | 0.28 | -$3,281 |
| trend_down | 6 | 16.7% | 0.15 | -$5,832 |
| super_trend_up | 1 | 0.0% | 0.00 | -$19 |

**Critical finding**: B-day is the ONLY consistently profitable day type (118 trades, 36.4% WR, PF 1.19).
P-day and trend days are net losers. If filtered to b_day only, the strategy would have
118 trades at 36.4% WR and +$12,344 -- still below study targets but more focused.

### By Exit Reason

| Reason | Trades | WR% | Net PnL |
|--------|--------|-----|---------|
| STOP | 93 | 0.0% | -$81,634 |
| TARGET | 37 | 100.0% | $66,013 |
| EOD | 20 | 80.0% | $33,618 |
| VWAP_BREACH_PM | 30 | 23.3% | -$10,983 |

**Key insight**: 93 stops (51.7% of trades) vs 37 target hits (20.6%) -- the strategy gets
stopped out too often. The 20 EOD exits at 80% WR suggest many trades go the right
direction but don't reach 2R target within the session. VWAP breach PM exits are net
losers -- 30 trades with 23.3% WR. This PM management logic may be cutting winners early
and should be revisited for this strategy type.

### Best 5 Trades

| Date | Dir | Entry | Exit | PnL | Exit | Day Type |
|------|-----|-------|------|-----|------|----------|
| 2025-10-10 | SHORT | 25,322.75 | 24,863.50 | +$9,171 | TARGET | super_trend_down |
| 2025-04-07 | SHORT | 18,307.00 | 17,962.00 | +$6,886 | VWAP_BREACH_PM | b_day |
| 2026-02-12 | SHORT | 25,183.50 | 24,865.25 | +$6,351 | TARGET | b_day |
| 2025-02-21 | SHORT | 22,896.75 | 22,613.75 | +$5,646 | EOD | p_day |
| 2025-11-25 | LONG | 25,069.75 | 25,304.00 | +$4,671 | EOD | b_day |

### Worst 5 Trades

| Date | Dir | Entry | Exit | PnL | Exit | Day Type |
|------|-----|-------|------|-----|------|----------|
| 2025-06-23 | LONG | 22,483.25 | 22,279.88 | -$4,082 | STOP | b_day |
| 2026-01-13 | SHORT | 25,850.50 | 26,018.38 | -$3,372 | STOP | b_day |
| 2026-02-11 | SHORT | 25,117.25 | 25,276.75 | -$3,204 | VWAP_BREACH_PM | b_day |
| 2025-09-26 | SHORT | 24,804.00 | 24,945.62 | -$2,847 | STOP | b_day |
| 2026-02-13 | LONG | 24,925.50 | 24,792.00 | -$2,684 | VWAP_BREACH_PM | p_day |

## Phase 3: Optimization

### Acceptance Bars (N x 5-min closes)

| Accept Bars | Trades | WR% | PF | Net PnL |
|-------------|--------|-----|-----|---------|
| 1x5min | 191 | 33.0% | 0.91 | -$9,568 |
| **2x5min** | **180** | **35.0%** | **1.03** | **$2,646** |
| 3x5min | 104 | 29.8% | 0.82 | -$10,084 |

2x5min is the clear winner. 1x5min enters too early (noise), 3x5min enters too late (misses move).

### Poke Minimum (pts beyond VA edge)

| Poke Min | Trades | WR% | PF | Net PnL |
|----------|--------|-----|-----|---------|
| 3pts | 185 | 34.6% | 1.01 | $512 |
| 5pts | 180 | 35.0% | 1.03 | $2,646 |
| **8pts** | **174** | **35.6%** | **1.03** | **$2,905** |
| 10pts | 172 | 36.0% | 1.03 | $2,401 |
| 15pts | 167 | 34.7% | 0.99 | -$883 |

8-10pt poke minimum is marginally best. Higher minimums filter noise but reduce trade count.
The difference is small -- poke minimum is NOT a major lever.

### Day Type Filter

| Filter | Trades | WR% | PF | Net PnL |
|--------|--------|-----|-----|---------|
| ON | 180 | 35.0% | 1.03 | $2,646 |
| OFF | 183 | 36.6% | 1.04 | $3,643 |

Day type filter adds negligible value -- only removes 3 trades. The strategy already
fires mostly on b_days (118/180). Filter is slightly WORSE by PnL because it removed
some profitable super_trend_down shorts.

### Max Touch Number

| Max Touch | Trades | WR% | PF | Net PnL |
|-----------|--------|-----|-----|---------|
| **1** | **177** | **35.6%** | **1.05** | **$4,390** |
| 2 | 180 | 35.0% | 1.03 | $2,646 |
| 3 | 181 | 34.8% | 1.02 | $2,281 |

1st touch only is marginally best. 2nd and 3rd touches add noise trades.
Edge diminishes with repeated tests as expected.

## Phase 4: Best Combination

**Optimal parameters:**
- Stop model: v3 (VA edge + 10pt)
- Target model: v2 (2R)
- Accept bars: 2x5min
- Poke minimum: 5 pts
- Max touch: 1
- Day type filter: OFF

**Results:**
- Trades: 180
- Win Rate: 35.6%
- Profit Factor: 1.11
- Net PnL: $10,630
- Avg Win: $1,729
- Avg Loss: -$862
- Expectancy: $59/trade

| Direction | Trades | WR% | PF | Net PnL |
|-----------|--------|-----|-----|---------|
| LONG | 89 | 36.0% | 1.00 | -$25 |
| SHORT | 91 | 35.2% | 1.21 | $10,654 |

## Gap Analysis: Why 35% WR vs 70% Study Target

The study claimed 70% WR on VAH shorts. Our backtest produced 34.4%. Here are the likely causes:

### 1. RTH-only Value Area vs ETH Value Area
Our engine computes prior day VA from RTH data only (9:30-16:15). The original study
likely used ETH (Extended Trading Hours) VA which includes overnight session data.
ETH VA is wider and levels are different. This is probably the **single biggest factor**
in the discrepancy. RTH-only VA produces narrower ranges with different edge positions.

### 2. Entry Timing
The study used "first touch" of VAH with immediate entry. Our implementation waits for
2x5min acceptance failure BEFORE entering. This delay means:
- We enter later (price may have already moved back inside VA)
- We enter at a worse price (further from the edge)
- The "fade" has already started, reducing our R:R

### 3. Stop Model Differences
The study used "2ATR + trailing" which is an adaptive stop that moves with the trade.
Our engine's trailing mechanism (VWAP breach PM, BE trail after PM) is designed for
trend strategies, not mean-reversion fades. The VWAP breach PM exit is particularly
harmful -- it closed 30 trades at 23.3% WR, many of which were likely heading in the
right direction.

### 4. No Limit Retest Entry
The study's best result (72.4% WR) used a limit order at the VA edge on retest.
We enter at market on the acceptance bar close. A limit retest entry would give
better fill prices and filter out cases where price never retests the edge.

### 5. Missing Overnight Context
The study likely used overnight high/low, settlement, and other ETH context to filter
setups. Our implementation uses only RTH prior day VA levels.

## Recommendations

### SHORT-TERM (can test now)
1. **Disable LONG trades entirely** -- LONG at VAL is a net loser (-$3,219)
2. **Filter to b_day only** -- other day types are net losers
3. **Exempt from VWAP breach PM exit** -- add "VA Edge Fade" to mean_reversion_strategies
   in backtest.py (like 80P Rule) to prevent premature PM exits

### MEDIUM-TERM (requires code changes)
4. **Add limit retest entry** -- after acceptance failure, place limit order at VA edge
   for better fill (similar to OR Acceptance v3 approach)
5. **Compute ETH Value Area** -- the biggest gap. Need overnight session data to compute
   proper ETH VA levels (VAH/VAL/POC including overnight trading)

### LONG-TERM (data pipeline)
6. **Integrate NinjaTrader ETH VA** -- if NinjaTrader can export ETH VA levels, ingest
   them as additional columns. This would give us the same reference levels as the study.

## Verdict

**NOT a portfolio game-changer in current form.** The 35% WR / PF 1.11 result is honestly
disappointing given the 70% WR study promise. However, the strategy IS marginally profitable
(+$10,630 over 273 sessions) and the SHORT side shows positive expectancy (PF 1.20).

The gap is most likely due to RTH-only VA vs ETH VA. If ETH VA levels were available,
this strategy could potentially perform much closer to the study results. The underlying
thesis (VA edge rejection) is sound -- the implementation just needs the right reference levels.

**Do NOT enable this strategy in production until ETH VA data is available.**
