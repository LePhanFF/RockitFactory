# Phase 4 Trade Analysis: 408 Trades Deep Dive

**Run ID**: NQ_20260308_215525
**Date**: 2026-03-09
**Data**: 408 trades across 237 sessions, 270 sessions of deterministic tape (21,060 rows)

---

## Executive Summary

1. **Bias alignment is the single most actionable filter**: Trades aligned with session bias win 62.2% at $499/trade avg; counter-bias trades win only 47.7% at $224/trade. Removing counter-bias trades lifts PF from 2.45 to 3.07 while keeping 63% of PnL.

2. **Opening Range Rev at IB close (10:30) is the alpha engine**: 102 trades, 63.7% WR, $77K PnL, 2.02 R:R. When tape TPO is B_shape at entry, WR jumps to 76.8%. Counter-tape-bias trades drop to 21.4% WR and should be filtered.

3. **80P Rule on Neutral Range sessions is a net drag**: 45 trades at 35.6% WR, -$2,665. The strategy only works on Trend Down (66.7% WR, +$19K) and Balance (75%, +$4.5K) days. LONG 80P with Bullish tape wins only 12.5% (chasing overbought).

4. **First hour dominates**: 77% of trades fire at or near IB close (10:30). These trades produce 68.7% of PnL at 61.3% WR vs 52.4% WR for later entries. After 11:00, performance degrades sharply.

5. **B-Day on Trend Down = 0% WR**: All 4 B-Day trades on Trend Down sessions lost (-$3,796). B-Day should be gated to only fire when session day type is NOT Trend.

---

## 1. Portfolio-Level Analysis

### 1.1 Portfolio Overview

| Metric | Value |
|--------|-------|
| Total Trades | 408 |
| Wins / Losses | 229 / 179 |
| Win Rate | 56.1% |
| Total Net PnL | $159,332 |
| Avg Trade | $391 |
| Profit Factor | 2.45 |
| Max Drawdown | -$6,442 |
| Annualized Sharpe | 7.27 |
| Trading Days | 237 / 270 (87.8%) |
| Avg Daily PnL | $672 |

### 1.2 Win Rate by Strategy

| Strategy | Trades | Wins | WR% | Net PnL | PF | Avg Win | Avg Loss | R:R |
|----------|--------|------|-----|---------|-----|---------|----------|-----|
| Opening Range Rev | 102 | 65 | 63.7% | $77,075 | 3.55 | $1,651 | $817 | 2.02 |
| OR Acceptance | 138 | 82 | 59.4% | $32,294 | 2.72 | $623 | $336 | 1.85 |
| 80P Rule | 71 | 30 | 42.3% | $21,326 | 1.72 | $1,694 | $719 | 2.35 |
| 20P IB Extension | 46 | 23 | 50.0% | $17,224 | 2.05 | $1,465 | $716 | 2.05 |
| B-Day | 51 | 29 | 56.9% | $11,412 | 1.77 | $907 | $677 | 1.34 |

### 1.3 Win Rate by Day Type (trade-level)

| Day Type | Trades | WR% | Net PnL |
|----------|--------|-----|---------|
| neutral | 240 | 61.3% | $109,369 |
| b_day | 92 | 50.0% | $22,412 |
| p_day | 65 | 46.2% | $16,349 |
| trend_down | 7 | 71.4% | $11,599 |
| trend_up | 3 | 33.3% | -$378 |

### 1.4 Win Rate by Composite Regime

| Regime | Trades | WR% | Net PnL |
|--------|--------|-----|---------|
| low_vol_trend | 245 | 56.3% | $74,310 |
| high_vol_trend | 94 | 55.3% | $52,796 |
| low_vol_balance | 39 | 53.8% | $10,320 |
| unknown | 21 | 71.4% | $21,752 |
| high_vol_range | 9 | 33.3% | $154 |

### 1.5 Win Rate by VIX Regime

| VIX Regime | Trades | WR% | Net PnL |
|------------|--------|-----|---------|
| moderate | 249 | 57.8% | $91,243 |
| elevated | 87 | 57.5% | $50,823 |
| low | 43 | 48.8% | $4,019 |
| high | 22 | 45.5% | $4,262 |
| extreme | 7 | 57.1% | $8,984 |

**Finding**: Low VIX underperforms (48.8% WR). Moderate and elevated VIX are the sweet spot. The system works best in "normal to slightly fearful" markets.

### 1.6 Win Rate by Entry Time

| Signal Time | Trades | WR% | Total PnL | Avg PnL |
|------------|--------|-----|-----------|---------|
| 10:30 (IB close) | 240 | 61.3% | $109,369 | $456 |
| 10:31-10:59 | 74 | 44.6% | $25,026 | $338 |
| 11:00-11:59 | 73 | 52.1% | $20,952 | $287 |
| 12:00+ | 21 | 52.4% | $3,985 | $190 |

**Finding**: Performance degrades monotonically after 10:30. The IB close signal captures the best edge. Average PnL drops from $456 at 10:30 to $190 after noon.

### 1.7 P&L by Day of Week

| Day | Trades | WR% | Total PnL | Avg PnL |
|-----|--------|-----|-----------|---------|
| Monday | 78 | 59.0% | $30,281 | $388 |
| Tuesday | 85 | 56.5% | $29,750 | $350 |
| Wednesday | 72 | 50.0% | $17,701 | $246 |
| Thursday | 88 | 58.0% | $37,988 | $432 |
| Friday | 85 | 56.5% | $43,611 | $513 |

**Finding**: Wednesday is the weakest day (50% WR, $246 avg). Friday is the strongest ($513 avg) -- potentially weekend positioning creates cleaner directional moves.

### 1.8 Exit Reason Distribution

| Exit Reason | Trades | WR% | Net PnL |
|-------------|--------|-----|---------|
| TARGET | 203 | 99.0% | $238,959 |
| STOP | 164 | 0.0% | -$98,484 |
| EOD | 22 | 77.3% | $17,890 |
| VWAP_BREACH_PM | 19 | 57.9% | $967 |

**Finding**: EOD exits are quite profitable (77.3% WR, $17.9K) -- these are trades that never hit stop or target but were in the green at close. VWAP_BREACH_PM exits are modestly positive.

### 1.9 Average Bars Held: Winners vs Losers

| Strategy | Win Bars | Loss Bars | All Bars | Interpretation |
|----------|----------|-----------|----------|----------------|
| OR Acceptance | 1.2 | 1.2 | 1.2 | Fastest resolution -- 1 bar decisions |
| Opening Range Rev | 8.6 | 18.5 | 12.2 | Winners resolve 2x faster than losers |
| B-Day | 44.2 | 28.9 | 37.6 | Losers stop out faster (tight stops) |
| 20P IB Extension | 84.5 | 32.1 | 58.3 | Winners need patience, losers stop quickly |
| 80P Rule | 130.5 | 91.2 | 107.8 | Slowest strategy -- long holds |

**Finding**: OR Rev losers take 2x as many bars as winners. This is a classic sign of "cut losers faster" -- a time-based exit at ~12 bars could reduce losing trade damage.

### 1.10 Monthly P&L

| Month | Trades | Wins | WR% | PnL |
|-------|--------|------|-----|-----|
| 2025-02 | 8 | 6 | 75.0% | $10,633 |
| 2025-03 | 37 | 18 | 48.6% | $11,870 |
| 2025-04 | 27 | 13 | 48.1% | $13,077 |
| 2025-05 | 35 | 19 | 54.3% | $8,268 |
| 2025-06 | 30 | 19 | 63.3% | $9,533 |
| 2025-07 | 31 | 17 | 54.8% | $5,424 |
| 2025-08 | 29 | 11 | 37.9% | $1,837 |
| 2025-09 | 24 | 16 | 66.7% | $8,606 |
| 2025-10 | 44 | 24 | 54.5% | $10,839 |
| 2025-11 | 34 | 22 | 64.7% | $26,324 |
| 2025-12 | 39 | 23 | 59.0% | $14,479 |
| 2026-01 | 35 | 21 | 60.0% | $17,601 |
| 2026-02 | 29 | 19 | 65.5% | $22,770 |
| 2026-03 | 6 | 1 | 16.7% | -$1,931 |

**Finding**: August was the worst month (37.9% WR). Nov 2025 through Feb 2026 was a dominant streak. System is consistently profitable (12/14 months positive).

### 1.11 Max Consecutive Streaks

| Strategy | Max Win Streak | Max Loss Streak |
|----------|---------------|-----------------|
| Opening Range Rev | 9 | 6 |
| OR Acceptance | 8 | 6 |
| B-Day | 9 | 7 |
| 80P Rule | 7 | 9 |
| 20P IB Extension | 5 | 4 |

**Finding**: 80P Rule has the worst max losing streak (9 in a row). Combined with 42.3% WR, this demands the most psychological discipline.

---

## 2. Deterministic Context Analysis

### 2.1 Session Bias Alignment (Most Important Finding)

| Alignment | Trades | WR% | Total PnL | Avg PnL |
|-----------|--------|-----|-----------|---------|
| ALIGNED (direction matches session bias) | 251 | 62.2% | $125,314 | $499 |
| COUNTER (direction opposes session bias) | 149 | 47.7% | $33,447 | $224 |
| NEUTRAL | 8 | 25.0% | $571 | $71 |

**Key Insight**: Aligned trades win 14.5 percentage points more often and produce 2.2x the average PnL. This is the strongest single predictor in the dataset.

### 2.2 Bias Alignment by Strategy

| Strategy | Alignment | Trades | WR% | PnL | Avg PnL |
|----------|-----------|--------|-----|-----|---------|
| Opening Range Rev | ALIGNED | 53 | 75.5% | $50,593 | $955 |
| Opening Range Rev | COUNTER | 47 | 48.9% | $22,445 | $478 |
| OR Acceptance | ALIGNED | 85 | 67.1% | $26,188 | $308 |
| OR Acceptance | COUNTER | 49 | 51.0% | $7,456 | $152 |
| 80P Rule | ALIGNED | 53 | 49.1% | $27,528 | $519 |
| 80P Rule | COUNTER | 17 | 23.5% | -$4,520 | -$266 |
| B-Day | ALIGNED | 25 | 60.0% | $6,201 | $248 |
| B-Day | COUNTER | 25 | 56.0% | $5,646 | $226 |
| 20P IB Extension | ALIGNED | 35 | 51.4% | $14,804 | $423 |
| 20P IB Extension | COUNTER | 11 | 45.5% | $2,421 | $220 |

**Findings**:
- **OR Rev**: Aligned = 75.5% WR (elite). Counter = 48.9% (coin flip). Difference: 26.6 pp.
- **OR Acceptance**: Aligned = 67.1% vs Counter = 51.0%. Difference: 16.1 pp.
- **80P Rule**: Counter-bias = 23.5% WR, net negative. Only works when aligned.
- **B-Day**: Surprisingly, bias alignment barely matters (60% vs 56%). B-Day is more structural than directional.

### 2.3 Tape Bias at Entry (Real-Time Signal)

Using the deterministic tape snapshot closest to entry time:

| Strategy | Tape Alignment | Trades | WR% | PnL | Avg PnL |
|----------|---------------|--------|-----|-----|---------|
| Opening Range Rev | ALIGNED | 25 | 72.0% | $19,055 | $762 |
| Opening Range Rev | NEUTRAL/FLAT | 63 | 69.8% | $59,995 | $952 |
| Opening Range Rev | COUNTER | 14 | 21.4% | -$1,975 | -$141 |
| OR Acceptance | ALIGNED | 42 | 76.2% | $15,625 | $372 |
| OR Acceptance | NEUTRAL/FLAT | 66 | 54.5% | $14,387 | $218 |
| OR Acceptance | COUNTER | 30 | 46.7% | $2,282 | $76 |
| 80P Rule | NEUTRAL/FLAT | 40 | 52.5% | $21,159 | $529 |
| 80P Rule | ALIGNED | 19 | 26.3% | -$1,778 | -$94 |
| 80P Rule | COUNTER | 12 | 33.3% | $1,946 | $162 |

**Critical Discovery for 80P Rule**: The 80P Rule performs BEST when tape bias is Flat/Neutral (52.5% WR, $529 avg) and WORST when aligned (26.3% WR). This is the opposite of every other strategy. Explanation: 80P is a reversion strategy -- it works when the market is not yet committed to a direction. When tape already shows a bias matching the trade, the move is likely already priced in (entry is too late).

**Critical Discovery for OR Rev**: Counter-tape-bias OR Rev trades win only 21.4%. This is a hard filter: do NOT take OR Rev when tape bias contradicts trade direction at the time of entry.

### 2.4 TPO Shape at Entry

| TPO Shape | Trades | WR% | Net PnL |
|-----------|--------|-----|---------|
| B_shape | 274 | 59.9% | $130,935 |
| p_shape | 52 | 51.9% | $18,911 |
| b_shape | 36 | 38.9% | $1,932 |
| D_shape | 24 | 58.3% | $7,530 |
| neutral | 8 | 50.0% | $1,248 |

**Finding**: B_shape (balanced, bell curve) is the dominant TPO shape and performs well. b_shape (lowercase -- elongated bottom) is a warning sign at 38.9% WR.

### 2.5 TPO Shape at Entry by Strategy (OR Rev)

| TPO at Tape Entry | Trades | WR% | PnL |
|-------------------|--------|-----|-----|
| B_shape | 56 | 76.8% | $60,250 |
| neutral | 13 | 61.5% | $6,847 |
| p_shape | 11 | 36.4% | $1,227 |
| D_shape | 11 | 36.4% | $1,985 |
| b_shape | 8 | 50.0% | $4,780 |

**Finding**: OR Rev + B_shape at entry = 76.8% WR. This is the highest-confidence setup in the dataset. p_shape and D_shape at entry both drop to 36.4%.

### 2.6 OR Rev: Combined Bias + TPO Filter

| Alignment | TPO | Trades | WR% | PnL |
|-----------|-----|--------|-----|-----|
| ALIGNED | B_shape | 9 | 88.9% | $10,301 |
| ALIGNED | neutral | 6 | 83.3% | $5,035 |
| NEUTRAL/FLAT | B_shape | 42 | 78.6% | $47,409 |
| COUNTER | B_shape | 5 | 40.0% | $2,540 |
| COUNTER | neutral | 5 | 20.0% | -$1,681 |
| NEUTRAL/FLAT | p_shape | 9 | 44.4% | $2,836 |
| NEUTRAL/FLAT | D_shape | 8 | 37.5% | $1,276 |

**Elite Setup**: OR Rev + ALIGNED bias + B_shape TPO = 88.9% WR (9 trades). Even with neutral bias + B_shape = 78.6% WR (42 trades, much larger sample).

**Avoid**: OR Rev + COUNTER bias + non-B_shape TPO is deeply negative.

### 2.7 Session Day Type vs Strategy

| Strategy | Session Day Type | Trades | WR% | PnL |
|----------|-----------------|--------|-----|-----|
| 80P Rule | Neutral Range | 45 | 35.6% | -$2,665 |
| 80P Rule | Trend Down | 9 | 66.7% | $19,176 |
| 80P Rule | Balance | 8 | 75.0% | $4,520 |
| 80P Rule | P-Day Down | 5 | 20.0% | -$820 |
| B-Day | Neutral Range | 38 | 63.2% | $14,811 |
| B-Day | Trend Down | 4 | 0.0% | -$3,796 |
| OR Acceptance | Trend Down | 5 | 100.0% | $2,937 |
| OR Acceptance | Trend Up | 9 | 77.8% | $3,574 |
| Opening Range Rev | Balance | 9 | 77.8% | $11,062 |
| Opening Range Rev | Trend Down | 5 | 80.0% | $5,135 |

**Findings**:
- 80P Rule loses on Neutral Range (-$2.7K) and P-Day Down. Only profitable on Trend Down and Balance.
- B-Day loses 100% on Trend Down days. Hard filter needed.
- OR Rev excels on Balance days (77.8% WR, $11K).
- OR Acceptance is remarkable on trend days (77.8-100% WR).

### 2.8 VIX Regime by Strategy

| Strategy | VIX | Trades | WR% | PnL |
|----------|-----|--------|-----|-----|
| 20P IB Extension | elevated | 10 | 80.0% | $11,665 |
| 20P IB Extension | high | 5 | 20.0% | -$2,394 |
| Opening Range Rev | moderate | 64 | 71.9% | $57,518 |
| Opening Range Rev | low | 11 | 45.5% | $1,831 |
| 80P Rule | low | 8 | 25.0% | -$1,918 |
| 80P Rule | elevated | 16 | 43.8% | $5,319 |

**Findings**:
- 20P IB Extension is phenomenal in elevated VIX (80% WR) but collapses in high VIX (20%).
- OR Rev drops from 71.9% in moderate VIX to 45.5% in low VIX. Low-vol chop kills reversals.
- 80P Rule is worst in low VIX (25% WR). Needs volatility to work.

### 2.9 Composite Regime by Strategy

| Strategy | Regime | Trades | WR% | PnL |
|----------|--------|--------|-----|-----|
| 80P Rule | high_vol_trend | 20 | 55.0% | $19,646 |
| 80P Rule | low_vol_trend | 38 | 39.5% | -$886 |
| 80P Rule | low_vol_balance | 9 | 22.2% | -$3,619 |
| Opening Range Rev | low_vol_balance | 13 | 76.9% | $11,773 |
| Opening Range Rev | low_vol_trend | 59 | 64.4% | $42,875 |

**Finding**: 80P Rule only works in high_vol_trend regime. In low_vol environments it is a net loser. OR Rev is the opposite -- it thrives in low_vol_balance.

### 2.10 Prior Day Type

| Prior Day Type | Trades | WR% | PnL |
|----------------|--------|-----|-----|
| normal_down | 64 | 68.8% | $39,307 |
| trend | 74 | 63.5% | $44,438 |
| p_day_up | 60 | 60.0% | $27,687 |
| balance | 14 | 57.1% | $8,076 |
| neutral | 80 | 51.3% | $21,370 |
| normal_up | 73 | 49.3% | $16,659 |
| p_day_down | 43 | 39.5% | $1,794 |

**Finding**: Trading after a normal_down or trend day has the highest WR. After a p_day_down, WR drops to 39.5%. The system benefits from prior-day directional clarity.

### 2.11 Day Type at Entry vs Session End

| Entry Day Type | Session End | Trades | WR% | PnL |
|----------------|-------------|--------|-----|-----|
| Neutral Range | Neutral Range | 267 | 53.9% | $88,438 |
| Neutral Range | Balance | 36 | 66.7% | $21,465 |
| Neutral Range | Trend Down | 26 | 65.4% | $27,694 |
| Neutral Range | P-Day Up | 33 | 60.6% | $15,047 |
| Neutral Range | Trend Up | 20 | 60.0% | $5,318 |
| Neutral Range | P-Day Down | 26 | 46.2% | $1,370 |

**Finding**: All trades enter during "Neutral Range" (first hour is always classified neutral). Sessions that evolve into Balance or Trend Down perform best. P-Day Down sessions are the weakest.

---

## 3. Pre-Signal Tape Analysis

### 3.1 Top Winners: Tape Conditions Before Entry

**Winner 1: 80P Rule, 2025-04-10, SHORT, +$5,941 (signal 10:59)**
- Tape 10:30-10:55: Price dropping steadily from 19,352 to 19,371 while VWAP at 19,574-19,592
- Bias shifting from Flat to Bearish by 10:40
- TPO shape: b_shape -> D_shape (selling pressure building)
- Price hugging lower third of IB consistently
- **Pattern**: Strong bearish structure building before entry, price well below VWAP

**Winner 2: 80P Rule, 2025-02-21, SHORT, +$5,646 (signal 10:59)**
- Tape 10:30-10:55: Price at 22,854-22,918 vs VWAP 23,016-23,041 (~120 points below)
- Bias: Flat -> Bearish by 10:35, consistently Bearish afterward
- IB extension starting at 10:45 (0.24x), price hugging lower third
- **Pattern**: Persistent VWAP discount + bearish bias + IB extension = strong short setup

**Winner 3: OR Rev, 2025-11-21, SHORT, +$4,619 (signal 10:30)**
- Tape 10:00-10:30: Price oscillating 24,302-24,430, close to VWAP (~24,407)
- Bias: Flat throughout (conf=40-50), TPO shifting neutral -> D_shape -> p_shape
- **Pattern**: OR Rev fires into a Flat/undecided market with price near VWAP. The reversal from OR high catches a move when no one is committed yet.

**Winner 4: OR Rev, 2026-02-20, LONG, +$3,699 (signal 10:30)**
- Tape: Bearish bias at 10:15-10:30 (conf=55-65), but price above VWAP
- TPO: B_shape throughout
- **Pattern**: Counter-bias win -- bias said Bearish but B_shape + price above VWAP showed underlying strength. Exception, not rule.

### 3.2 Top Losers: Tape Conditions Before Entry

**Loser 1: 80P Rule, 2025-03-27, LONG, -$2,827 (signal 10:59)**
- Tape 10:30-10:55: Price rising 20,829 -> 20,894, Bullish bias, p_shape -> B_shape
- Price above VWAP, upper_third_hug, extension building to 0.50x
- Day type shifted to P-Day Up by 10:55
- **Diagnosis**: Already overbought. 80P LONG chased a move that was already extended 0.50x IB. Classic "late to the party" setup.

**Loser 2: 20P IB Extension, 2025-11-21, SHORT, -$2,346 (signal 10:44)**
- Tape: Flat -> Bearish by 10:35, but price breaking lower aggressively
- Session bias was Bullish (counter-bias trade)
- **Diagnosis**: Counter-bias SHORT on a Bullish session day. The bearish tape reading was temporary.

**Loser 3: OR Rev, 2025-04-11, LONG, -$2,211 (signal 10:30)**
- Tape: Price collapsing from 19,270 to 19,013 during IB formation
- Bias: Flat throughout, TPO: p_shape (selling pressure)
- Price in lower_third_hug
- **Diagnosis**: OR Rev LONG fired while price was in aggressive decline. p_shape TPO was a warning sign. This is exactly the "chase into a falling knife" pattern.

**Loser 4: 80P Rule, 2026-02-20, LONG, -$1,869 (signal 10:59)**
- Tape: Bearish at 10:30-10:35, then shifting to Flat, then Bullish by 10:55
- Price above VWAP, upper_third_hug
- **Diagnosis**: Bearish session bias + late bullish tape flip. The tape bias changed too late -- session context was already bearish. Mixed signals = stay out.

**Loser 5: B-Day, 2026-02-26, LONG, -$1,814 (signal 11:05)**
- Tape: Bearish bias (55 conf) throughout, lower_third_hug
- Final tape before entry: "Very Bearish" (75 conf), Trend Down day type
- **Diagnosis**: LONG B-Day on a Very Bearish/Trend Down session. Every tape indicator screamed bearish. This is a clear avoidable loss.

### 3.3 Pre-Signal Tape Patterns Summary

| Pattern | Outcome | Frequency |
|---------|---------|-----------|
| Winners: price below VWAP + bearish tape for SHORT | Profitable | Common in 80P/OR Rev winners |
| Winners: Flat/neutral tape at IB close for OR Rev | Profitable | 63 trades, 69.8% WR |
| Losers: Already extended 0.3x+ IB for 80P LONG | Losing | Common trap |
| Losers: Counter-session-bias with temporary tape shift | Losing | 80P and 20P vulnerable |
| Losers: p_shape or D_shape TPO for OR Rev entries | Losing | 36.4% WR |

---

## 4. Pattern Discovery

### 4.1 Patterns Ranked by Confidence and Actionability

| # | Pattern | Trades | WR% | Impact | Confidence |
|---|---------|--------|-----|--------|------------|
| 1 | OR Rev + ALIGNED bias + B_shape TPO | 9 | 88.9% | +$10,301 | Medium (small n) |
| 2 | OR Rev + B_shape TPO at tape entry | 56 | 76.8% | +$60,250 | HIGH (n=56) |
| 3 | OR Rev + COUNTER tape bias = avoid | 14 | 21.4% | -$1,975 | HIGH (n=14) |
| 4 | 80P LONG + Bullish tape = avoid | 8 | 12.5% | -$4,215 | HIGH (clear anti-pattern) |
| 5 | 80P on Neutral Range sessions | 45 | 35.6% | -$2,665 | HIGH (n=45) |
| 6 | 80P on high_vol_trend regime | 20 | 55.0% | +$19,646 | HIGH (n=20) |
| 7 | B-Day on Trend Down = 0% WR | 4 | 0.0% | -$3,796 | Medium (small n) |
| 8 | OR Acceptance + ALIGNED bias | 85 | 67.1% | +$26,188 | HIGH (n=85) |
| 9 | Portfolio: ALIGNED bias overall | 251 | 62.2% | +$125,314 | VERY HIGH (n=251) |
| 10 | Portfolio: COUNTER bias overall | 149 | 47.7% | +$33,447 | VERY HIGH (n=149) |
| 11 | B-Day + Q4 (wide) IB range | 12 | 75.0% | +$10,565 | Medium (n=12) |
| 12 | 20P + elevated VIX | 10 | 80.0% | +$11,665 | Medium (n=10) |
| 13 | 80P + Flat tape bias | 40 | 52.5% | +$21,159 | HIGH (n=40) |
| 14 | After prior normal_down day | 64 | 68.8% | +$39,307 | HIGH (n=64) |
| 15 | 80P on low_vol_balance = avoid | 9 | 22.2% | -$3,619 | Medium (n=9) |

### 4.2 Detailed Pattern Descriptions

**Pattern 1-3: Opening Range Rev Tape Filters**
- When tape TPO is B_shape (balanced bell curve) at entry, OR Rev wins 76.8%. This is the single highest-confidence setup with large sample size.
- When tape bias COUNTERS trade direction, OR Rev drops to 21.4%. Hard filter: skip these.
- Combined: OR Rev + non-counter bias + B_shape = consistently 75-89% WR territory.

**Pattern 4-6: 80P Rule Regime Gating**
- 80P LONG with Bullish tape is chasing overbought (12.5% WR). The 80P Rule is a reversion play -- it works when the market is NOT yet committed.
- 80P on Neutral Range sessions (35.6% WR) is below breakeven. It only works when the session becomes Trend Down (66.7%) or Balance (75%).
- 80P on high_vol_trend: 55% WR, +$19.6K. The strategy needs volatility to create the price discovery that makes targets reachable.

**Pattern 7: B-Day Trend Filter**
- B-Day + Trend Down = 0% WR, -$3,796. All 4 were LONG trades into a bearish trend. B-Day is a balance play and should never fire on trend days.

**Pattern 11: B-Day IB Width**
- B-Day in Q4 (wide, 240-471 pt) IB sessions: 75% WR, +$10.6K. Wide IB on a balance day means more room for mean reversion within the range.

**Pattern 12: 20P Elevated VIX**
- 20P IB Extension in elevated VIX: 80% WR, +$11.7K. But in high VIX (above elevated): 20% WR. There's a sweet spot of "moderate fear" where IB extensions are reliable.

**Pattern 14: Prior Day Context**
- After a normal_down day: 68.8% WR. After a p_day_down: 39.5% WR. The system trades better when the prior day showed clean selling (not P-Day exhaustion).

---

## 5. Strategy-Specific Recommendations

### 5.1 Opening Range Rev (102 trades, 63.7% WR, $77K)

**Status**: Best strategy. Room to improve by filtering low-quality setups.

**Recommendations**:
1. **Hard filter**: Skip when tape bias at entry counters trade direction. Saves 11 losing trades (-$7,634 in avoidable losses), only misses 3 winners (+$5,659 in missed profit). Net improvement: ~$2K and higher WR.
2. **Preference filter**: Favor entries when tape TPO is B_shape (76.8% WR vs 43% for p/D_shape).
3. **Caution in low VIX**: WR drops from 71.9% (moderate) to 45.5% (low). Consider reducing size or requiring stronger confirmation in low-vol.
4. **Time-based exit**: Winners resolve in avg 8.6 bars, losers in 18.5. Consider a time-stop at ~15 bars for trades that haven't hit target.

### 5.2 OR Acceptance (138 trades, 59.4% WR, $32K)

**Status**: High-frequency, solid performer. Consistency machine.

**Recommendations**:
1. **Bias filter**: Aligned bias = 67.1% WR vs Counter = 51.0%. Consider a softer filter (reduce size on counter-bias, not hard block).
2. **Excellent on trend days**: 77.8-100% WR on Trend Up/Down sessions. These are the highest-conviction signals.
3. **Neutral sessions: be selective**: 55.1% WR on Neutral Range is the floor. Look for additional tape confirmation on neutral days.
4. **Low VIX is still fine**: 57.1% WR in low VIX. This strategy is VIX-resilient.

### 5.3 80P Rule (71 trades, 42.3% WR, $21K)

**Status**: Low WR but high R:R (2.35) makes it profitable. Very regime-dependent.

**Recommendations**:
1. **Hard filter: block on Neutral Range sessions**: 35.6% WR, net negative. Only allow on Trend Down, Balance, or high_vol_trend.
2. **Hard filter: block LONG when tape bias is Bullish**: 12.5% WR. This is chasing. 80P LONG should only fire on Flat or Bearish tape.
3. **Best regime**: high_vol_trend (55% WR, +$19.6K). Consider this the primary qualifying condition.
4. **Flat tape is optimal**: 52.5% WR when tape is Flat vs 26.3% when aligned. 80P works as a contrarian/reversion play -- commit only when the market hasn't decided yet.
5. **low_vol_balance = kill zone**: 22.2% WR, -$3.6K. Never trade 80P in low_vol_balance.

### 5.4 20P IB Extension (46 trades, 50.0% WR, $17K)

**Status**: Moderate frequency, solid R:R (2.05). VIX-sensitive.

**Recommendations**:
1. **Sweet spot: elevated VIX**: 80% WR, +$11.7K. Increase size or confidence.
2. **Avoid high VIX**: 20% WR, -$2.4K. The extension targets get overrun in extreme volatility.
3. **Counter-bias can work**: 71.4% WR on counter-bias (7 trades). Small sample but suggests 20P catches genuine IB extensions that override bias.
4. **high_vol_trend is good**: 61.5% WR, +$9.8K.

### 5.5 B-Day (51 trades, 56.9% WR, $11K)

**Status**: Moderate performer. Strong on balance days, catastrophic on trend.

**Recommendations**:
1. **Hard filter: block on Trend Down sessions**: 0% WR, -$3.8K. B-Day is a balance play -- it should never fire when session evolves into trend.
2. **Wide IB is best**: Q4 (240-471 pt) IB = 75% WR, +$10.6K. The wider the IB, the more room for balance day mean reversion.
3. **Bias alignment barely matters**: 60% vs 56%. B-Day is structural, not directional. Don't filter on bias.
4. **b_shape TPO is a warning**: 20% WR (5 trades). b_shape (elongated bottom) suggests one-sided selling, not balance.
5. **Neutral Range sessions are best**: 63.2% WR, +$14.8K. This is where B-Day logic aligns perfectly.

---

## 6. Avoidable Losses

### 6.1 Summary of Avoidable Loss Categories

| Category | Losing Trades | Lost PnL | Filter |
|----------|---------------|----------|--------|
| Counter-bias (session) losses | 78 | -$49,196 | Block trades opposing session bias |
| 80P on Neutral Range losses | 29 | -$23,704 | Block 80P on neutral sessions |
| B-Day on Trend Down | 4 | -$3,796 | Block B-Day on trend sessions |
| OR Rev counter-tape-bias | 11 | -$7,634 | Block OR Rev when tape opposes |
| 80P LONG + Bullish tape | 7 | -$5,743 | Block 80P LONG when tape is Bullish |

**Note**: These categories overlap. The counter-bias filter alone would catch many of the 80P and OR Rev specific patterns.

### 6.2 What-If Filter Impact

| Scenario | Trades | WR% | Net PnL | PF |
|----------|--------|-----|---------|-----|
| **Current (no filter)** | 408 | 56.1% | $159,332 | 2.45 |
| Remove counter-bias | 259 | 61.0% | $125,885 | 3.07 |
| Remove counter-bias + 80P neutral + B-Day trend | 229 | 63.3% | $122,498 | 3.61 |
| OR Rev tape-bias filter only | 394 | 57.4% | $161,307 | 2.58 |

**Trade-off**: The aggressive combo filter reduces trades from 408 to 229 (-44%) but lifts PF from 2.45 to 3.61 (+47%). Total PnL drops from $159K to $122K (-23%), but on 44% fewer trades -- the per-trade expectancy goes from $391 to $535 (+37%).

**Recommendation**: Start with the combo filter. The lost $37K in PnL is from low-edge counter-bias trades. The freed-up capital and mental bandwidth can be redeployed into higher-confidence setups. Over time, the better discipline compounds.

### 6.3 Top 30 Avoidable Losses (Counter-Bias, Sorted by PnL)

| Strategy | Date | Direction | PnL | Session Bias | TPO | Exit |
|----------|------|-----------|-----|-------------|-----|------|
| 20P IB Extension | 2025-11-21 | SHORT | -$2,346 | Bullish | B_shape | STOP |
| 80P Rule | 2025-05-16 | SHORT | -$1,562 | Bullish | B_shape | STOP |
| Opening Range Rev | 2025-03-11 | LONG | -$1,551 | Bearish | D_shape | STOP |
| Opening Range Rev | 2025-04-14 | LONG | -$1,431 | Bearish | D_shape | STOP |
| B-Day | 2025-04-08 | LONG | -$1,405 | Bearish | B_shape | STOP |
| 80P Rule | 2025-07-10 | SHORT | -$1,364 | Bullish | B_shape | EOD |
| Opening Range Rev | 2025-11-17 | LONG | -$1,328 | Bearish | B_shape | STOP |
| 80P Rule | 2025-11-12 | SHORT | -$1,299 | Bullish | B_shape | EOD |
| 80P Rule | 2025-07-23 | SHORT | -$1,287 | Bullish | wide_value | STOP |
| Opening Range Rev | 2026-01-02 | LONG | -$1,249 | Bearish | B_shape | STOP |
| Opening Range Rev | 2026-03-05 | LONG | -$1,082 | Bearish | b_shape | STOP |
| Opening Range Rev | 2025-12-16 | SHORT | -$1,082 | Bullish | developing | STOP |
| B-Day | 2025-10-22 | LONG | -$1,071 | Bearish | b_shape | STOP |
| 20P IB Extension | 2026-01-14 | SHORT | -$1,053 | Bullish | b_shape | STOP |
| 80P Rule | 2026-02-19 | LONG | -$1,052 | Bearish | b_shape | STOP |
| B-Day | 2025-10-15 | LONG | -$1,044 | Bearish | B_shape | VWAP_BREACH_PM |
| 20P IB Extension | 2025-10-16 | LONG | -$1,004 | Bearish | b_shape | STOP |
| B-Day | 2026-01-30 | LONG | -$997 | Bearish | b_shape | STOP |
| Opening Range Rev | 2025-03-28 | LONG | -$823 | Bearish | B_shape | STOP |
| 20P IB Extension | 2026-01-05 | LONG | -$756 | Bearish | b_shape | STOP |
| Opening Range Rev | 2025-05-02 | SHORT | -$742 | Bullish | p_shape | STOP |
| B-Day | 2025-02-21 | LONG | -$730 | Bearish | B_shape | STOP |
| Opening Range Rev | 2025-09-04 | SHORT | -$716 | Bullish | B_shape | STOP |
| Opening Range Rev | 2025-10-21 | SHORT | -$703 | Bullish | p_shape | STOP |
| 80P Rule | 2026-02-11 | SHORT | -$694 | Bullish | p_shape | EOD |
| 80P Rule | 2026-01-22 | SHORT | -$677 | Bullish | p_shape | STOP |
| B-Day | 2025-09-23 | LONG | -$665 | Bearish | B_shape | STOP |
| Opening Range Rev | 2025-08-12 | SHORT | -$664 | Bullish | B_shape | STOP |
| Opening Range Rev | 2026-01-28 | LONG | -$646 | Bearish | B_shape | STOP |
| Opening Range Rev | 2025-08-05 | LONG | -$636 | Bearish | B_shape | STOP |

---

## 7. Direction Analysis

### 7.1 Strategy x Direction

| Strategy | Direction | Trades | WR% | PnL | Avg PnL |
|----------|-----------|--------|-----|-----|---------|
| Opening Range Rev | SHORT | 46 | 65.2% | $42,172 | $917 |
| Opening Range Rev | LONG | 56 | 62.5% | $34,903 | $623 |
| OR Acceptance | SHORT | 57 | 59.6% | $13,474 | $236 |
| OR Acceptance | LONG | 81 | 59.3% | $18,820 | $232 |
| 80P Rule | SHORT | 35 | 45.7% | $19,771 | $565 |
| 80P Rule | LONG | 36 | 38.9% | $1,555 | $43 |
| 20P IB Extension | SHORT | 13 | 53.8% | $7,861 | $605 |
| 20P IB Extension | LONG | 33 | 48.5% | $9,363 | $284 |
| B-Day | LONG | 51 | 56.9% | $11,412 | $224 |

**Finding**: SHORT trades consistently outperform LONG across most strategies, particularly 80P ($565 avg SHORT vs $43 LONG) and OR Rev ($917 vs $623). This may reflect market microstructure (faster drops = wider swings for target) or systematic bias in the NQ dataset.

---

## 8. Key Takeaways for Implementation

### 8.1 Immediate Filters (High Confidence, Implement Now)

1. **Bias alignment gate**: Require trade direction to align with (or be neutral to) session bias. This alone lifts PF from 2.45 to 3.07.
2. **80P regime gate**: Block 80P Rule on Neutral Range sessions and low_vol_balance regime.
3. **B-Day trend gate**: Block B-Day when session day type is Trend (Up or Down).
4. **80P anti-chase**: Block 80P LONG when tape bias is Bullish.

### 8.2 Soft Filters (Medium Confidence, Use for Sizing/Ranking)

5. **OR Rev TPO preference**: Increase confidence/size when tape TPO is B_shape; reduce when p_shape or D_shape.
6. **VIX regime sizing**: Increase 20P size in elevated VIX, reduce in high VIX. Reduce OR Rev size in low VIX.
7. **Prior day context**: Increase confidence after normal_down or trend days, reduce after p_day_down.
8. **Wednesday caution**: Reduce overall position sizing on Wednesdays.

### 8.3 Agent Pipeline Integration

For the LLM tape reading agent:
- Feed bias alignment as a first-class feature in the deterministic snapshot
- Include "avoidable loss" flags when counter-bias is detected
- The Advocate/Skeptic debate should weight TPO shape and bias alignment heavily
- 80P Rule should be treated as "conditional" -- require explicit regime qualification before the Advocate can propose it
