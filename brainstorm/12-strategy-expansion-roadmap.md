# 12 -- Strategy Expansion Roadmap

> **Author**: Rockit Quant Research
> **Date**: 2026-03-09
> **Status**: Brainstorm / Living Document
> **Backtest baseline**: 408 trades, 56.1% WR, PF 2.45, $159K net, 270 NQ sessions

---

## Table of Contents

1. [Current Portfolio Snapshot](#1-current-portfolio-snapshot)
2. [Section A: Disabled Strategies to Re-Optimize](#2-section-a-disabled-strategies-to-re-optimize)
3. [Section B: New Strategies from Our Domain](#3-section-b-new-strategies-from-our-domain)
4. [Section C: Quantitative Strategies Worth Testing](#4-section-c-quantitative-strategies-worth-testing)
5. [Section D: Priority Ranking](#5-section-d-priority-ranking)
6. [Section E: Data Gap Analysis](#6-section-e-data-gap-analysis)
7. [Section F: Implementation Phases](#7-section-f-implementation-phases)

---

## 1. Current Portfolio Snapshot

### Active Strategies (5)

| Strategy | Trades | WR% | Net PnL | PF | R:R | Key Insight (Phase 4) |
|----------|--------|-----|---------|-----|-----|----------------------|
| Opening Range Rev | 102 | 63.7% | $77,075 | 3.55 | 2.02 | Alpha engine. B_shape TPO = 76.8% WR. Counter-tape-bias = 21.4% WR (avoid). |
| OR Acceptance | 138 | 59.4% | $32,294 | 2.72 | 1.85 | Consistency machine. 67.1% aligned vs 51.0% counter-bias. |
| 80P Rule | 71 | 42.3% | $21,326 | 1.72 | 2.35 | Contrarian/reversion. ONLY works in high_vol_trend (55% WR). Flat tape is optimal. |
| 20P IB Extension | 46 | 50.0% | $17,224 | 2.05 | 2.05 | VIX-sensitive. Elevated VIX = 80% WR. High VIX = 20% WR. |
| B-Day | 51 | 56.9% | $11,412 | 1.77 | 1.34 | Balance play. 0% WR on Trend Down days (hard filter needed). Wide IB Q4 = 75% WR. |

### Portfolio-Level Facts

- **Bias alignment is the single most actionable filter**: Aligned trades = 62.2% WR, $499/trade avg. Counter-bias = 47.7% WR, $224/trade.
- **First hour dominates**: 77% of trades fire at or near IB close (10:30). Performance degrades monotonically after 10:30.
- **SHORT outperforms LONG** across most strategies (particularly 80P: $565 avg SHORT vs $43 LONG).
- **12 of 14 months profitable**. August worst (37.9% WR). Nov-Feb dominant streak.
- **Max drawdown**: -$6,442. Annualized Sharpe: 7.27.

### Disabled Strategies (12)

| Strategy | Status | Why Disabled |
|----------|--------|-------------|
| Trend Day Bull | Built, losing | Not ported correctly from source study. Only VWAP pullback entry works. |
| Trend Day Bear | Built, losing | Mirror of bull. Same issue -- only VWAP rejection entry works. |
| Super Trend Bull | Built, losing | Requires >2.0x IB extension. Too rare + wide stops. |
| Super Trend Bear | Built, losing | Same as super trend bull. |
| P-Day | Built, losing | IBH retest disabled (31.2% WR). Only VWAP pullback works, too selective. |
| Mean Reversion VWAP | Built, -$6,925 | Losing. Wrong filters, wrong time window, wrong regime gate. |
| ORB Enhanced | Built, losing | Overengineered. Sweep/FVG entries add noise. |
| Neutral Day | Scaffold only | No signals implemented. |
| PM Morph | Scaffold only | Breakout into PM after flat AM. Not studied. |
| Morph to Trend | Built, losing | Simple breakout threshold. No DPOC migration, no profile shape filter. |
| ORB VWAP Breakout | Built, losing | Simpler version of ORB Enhanced. Same issues. |
| EMA Trend Follow | Built, losing | Pullback to EMA20/50. No regime or MTF filter. |
| Liquidity Sweep | Built, losing | Trap inversion entries. Too noisy on 1-min bars. |

---

## 2. Section A: Disabled Strategies to Re-Optimize

### A1. Trend Day Bull/Bear -- THE Biggest Opportunity

**Study target**: 58% WR, 2.8 PF, $1,465/day (highest expectancy of any studied strategy)
**Current state**: Disabled, losing money. Only VWAP pullback entry fires reliably.
**Root cause**: Implementation does not match the source study.

**What went wrong:**

1. **Day type gating is too strict.** The strategy requires `trend_up` or `super_trend_up` day type from the session classifier, but day type is not known reliably until well after IB close. The study assumes you detect the trend via multi-timeframe EMA alignment and ADX, not via backward-looking day type labels.

2. **VWAP pullback is the only surviving entry.** IBH retest (26.7% WR) and EMA pullback entries were disabled after testing. But the study envisions a pullback hierarchy: FVG > VWAP > EMA20 > IBH retest. The problem is that FVG on 1-min bars is noisy, and the EMA entry has no order flow quality gate.

3. **Tight stops + wide targets mismatch.** STOP_VWAP_BUFFER = 0.40x IB with TARGET_TREND = 2.0x IB. On NQ with 100-200pt IB range, the stop is 40-80pts but the target is 200-400pts. This is a 3:1+ R:R on paper, but the trend must be strong enough to actually reach 2.0x IB extension -- which only happens on true trend days (~15% of sessions).

4. **No multi-timeframe trend filter.** The study explicitly calls for 15-min trend alignment (price > 20 EMA > 50 EMA). The current implementation only checks `trend_strength` from the session context, which is computed from IB extension -- a lagging indicator.

**How to fix it:**

| Fix | Description | Difficulty |
|-----|-------------|------------|
| **Add 15-min EMA filter** | Compute 15-min EMA20/EMA50 from 1-min bars. Only allow trend entries when 15-min price > EMA20 > EMA50 (bull) or < EMA20 < EMA50 (bear). This is the study's primary trend confirmation. | Medium |
| **Remove day_type gate** | Allow entry on ANY session once acceptance + EMA alignment confirmed. Day type is not knowable at entry time. | Easy |
| **Restore EMA20 pullback** | The study's "Version D: Opening Drive Continuation" uses EMA20 pullback after trend establishment. Add order flow quality gate (delta_percentile >= 60, imbalance > 1.0). | Medium |
| **Add ADX filter** | ADX > 25 on 15-min = strong trend, take all signals. ADX < 20 = skip. This filters 70% of chop days. Requires computing ADX from 1-min bars. | Medium |
| **Reduce target to 1.5x IB** | The current 2.0x target is too ambitious. Start with 1.5x IB (P-Day level) as default, use 2.0x only when ADX > 30. | Easy |
| **Add trailing stop** | After +1.0x IB move, trail with 20-period EMA on 5-min. This captures extended trends without giving back gains. | Medium |
| **Time-of-day gate** | Study says best time windows are 10:00-11:30 and 13:30-15:00. Avoid lunch (11:30-13:30). Current cutoff of PM_SESSION_START (13:00) is too conservative. | Easy |

**Expected after fix**: 30-50 trades, 50-55% WR, PF 2.0+, $15-30K net. The study targets $1,465/day on MNQ which translates to ~$29K/month -- but that is extremely optimistic and assumes 3-4 trades/day on strong trend days. On NQ with 270 sessions, perhaps 40-60 qualifying trend days, we might see 60-100 total trades.

**Priority**: HIGH. This is the single largest untapped edge in the existing codebase.

---

### A2. Mean Reversion VWAP -- Fixable But Needs Complete Rethink

**Current state**: -$6,925 net. Disabled.
**Study target**: 65% WR, 1.8 PF, $352/day in range-bound markets.

**What went wrong:**

1. **Wrong time window.** ENTRY_START = 11:00, ENTRY_CUTOFF = 14:30. But the Phase 4 analysis shows performance degrades after 10:30. The strategy should fire in the 10:30-13:00 window (after IB close, before lunch chop ends), not the mid-afternoon.

2. **No regime gate.** The study explicitly says "Only trade if ADX < 25." The current implementation uses `ALLOWED_DAY_TYPES = ['b_day', 'neutral', 'p_day']` as a proxy, but day type is a post-hoc label. ADX-based regime detection is the correct real-time filter.

3. **RSI thresholds too aggressive.** RSI_OVERBOUGHT = 65, RSI_OVERSOLD = 35. The study uses 70/30 with extreme levels at 80/20 for higher-quality signals. The current thresholds generate too many low-quality entries.

4. **Delta direction gate is wrong.** The strategy requires `delta > 0` for longs and `delta < 0` for shorts. But this is a single-bar filter. Mean reversion works on multi-bar exhaustion -- a better filter is a 5-bar cumulative delta that has been trending one direction and then reverses (divergence).

5. **Competing with 80P Rule.** Both strategies trade mean reversion. The 80P Rule targets prior-day VA boundaries (structural levels with institutional memory). Mean Reversion VWAP targets intraday VWAP deviation -- a weaker level. The 80P Rule wins because it trades against structural edges, while VWAP deviation is noise.

**How to fix it:**

| Fix | Description | Difficulty |
|-----|-------------|------------|
| **Add ADX filter** | ADX(14) < 25 on 5-min timeframe = range-bound. Skip when ADX > 25. | Medium |
| **Add Bollinger Band filter** | Only enter when price touches/breaks lower BB (long) or upper BB (short) on 5-min. BB(20, 2.0). This adds a statistical extreme filter that VWAP deviation alone lacks. | Medium |
| **Fix RSI thresholds** | RSI > 70 (short), RSI < 30 (long). For high-confidence: RSI > 80 / RSI < 20. | Easy |
| **Add RSI divergence** | Price makes lower low + RSI makes higher low = bullish divergence. This is the study's highest-quality signal. | Hard |
| **Time window: 10:30-13:00** | After IB close through lunch. This is the true balance/chop window. | Easy |
| **Use 5-bar delta divergence** | Instead of single-bar delta, compute 5-bar cumulative delta trend. Enter when delta trend reverses (sellers exhausted, buyers stepping in). | Medium |
| **Target: midpoint between entry and VWAP** | Instead of targeting VWAP (full reversion), target 50% of the distance. Higher WR, faster exits. | Easy |
| **Time-based exit** | If not profitable within 15 bars (15 min), exit. Reversion that doesn't happen quickly won't happen. | Easy |

**Key insight from Phase 4**: 80P Rule on Neutral Range sessions = 35.6% WR, -$2,665. Mean Reversion VWAP and 80P Rule are both targeting the same market condition (range-bound reversion) but with different levels. Instead of competing, Mean Reversion VWAP should be positioned as the "balance day mid-session" strategy that fires BETWEEN 80P setups -- when price deviates from VWAP without having opened outside prior VA.

**Expected after fix**: 40-80 trades, 55-60% WR, PF 1.5-1.8, $5-15K net. This is a high-frequency/low-edge strategy that works through volume, not per-trade alpha.

**Priority**: MEDIUM. Useful for portfolio diversification (fires during lunch when other strategies are inactive) but requires ADX + BB infrastructure.

---

### A3. P-Day -- Needs Simpler Entry Model

**Current state**: Disabled. IBH retest = 31.2% WR. Only VWAP pullback works.
**Study target**: Part of the Dalton framework. P-Day = skewed balance (0.5-1.0x IB extension).

**What went wrong:**

1. **Too similar to Trend Day Bull/Bear.** P-Day uses the same VWAP pullback entry as Trend Day Bull, with the same order flow quality gate and delta momentum check. The only difference is the target (1.5x IB vs 2.0x IB) and the acceptance threshold. This means P-Day and Trend Day Bull compete for the same signals on the same sessions.

2. **Short conviction requirement too strict.** `consecutive_outside < 3` blocks most short entries. The study says P-Day shorts (B-shape skew) should trade on any acceptance below IBL, not require 3+ bars.

3. **Volume spike filter for shorts is wrong.** `volume_spike > 1.2` is required for short entries. But the study says volume should be declining at the reversion point (exhaustion), not spiking. A volume spike at an extreme means continuation, not reversal.

**How to fix it:**

| Fix | Description | Difficulty |
|-----|-------------|------------|
| **Merge into Trend Day Bull/Bear** | P-Day is really "early trend day" (0.5-1.0x extension). Instead of a separate strategy, make Trend Day Bull/Bear emit signals with reduced targets when extension is < 1.0x IB. This eliminates the overlap problem. | Medium |
| **OR: Add IB POC shape filter** | If P-Day stays standalone: only enter LONG when IB POC is in upper third (P-shape, bullish skew). Only enter SHORT when IB POC is in lower third (B-shape). This is the Dalton foundation that is currently missing. | Medium |
| **Fix short entry** | Remove the volume_spike > 1.2 requirement. Replace with declining volume (volume < 20-period average) which signals exhaustion. | Easy |
| **Lower short acceptance to 2 bars** | 2 consecutive closes below IBL (matching the bull side) instead of 3. | Easy |

**Recommendation**: Merge P-Day into Trend Day Bull/Bear as a "reduced target" mode. P-Day as a standalone strategy has too much overlap and too few unique signals.

**Priority**: LOW as standalone. HIGH if merged into Trend Day strategy rewrite.

---

### A4. Morph to Trend -- Needs Real Profile Analysis

**Current state**: Disabled. Simple 2-bar breakout threshold -- too simplistic.
**Study target**: Captures balance-to-trend transitions. This is a theoretically high-value setup.

**What went wrong:**

1. **No DPOC migration tracking.** The Dalton playbook says morph requires "extreme DPOC migration (>160 pts into VAH/VAL)." The current implementation uses a fixed MORPH_TO_TREND_BREAKOUT_POINTS threshold with no reference to DPOC behavior.

2. **No profile shape analysis.** The transition from balance to trend should show the TPO profile "fattening" on one side with single prints extending. The current implementation ignores TPO profile shape entirely.

3. **Fixed point targets instead of structural targets.** MORPH_TO_TREND_TARGET_POINTS is a static value. The target should be based on IB range multiplier or prior day's range, not a fixed number of points.

4. **No failure detection.** The Dalton playbook explicitly states: "If price trades back through the new DPOC during mid-PM attempt to extend, the morph has FAILED." There is no such abort logic.

**How to fix it:**

| Fix | Description | Difficulty |
|-----|-------------|------------|
| **Add DPOC migration tracking** | Track DPOC position every 30 minutes. When DPOC migrates > 0.5x IB range from IB midpoint toward one side, morph conditions are developing. When > 1.0x IB range, morph is confirmed. | Hard |
| **Add profile shape check** | Use TPO shape from deterministic modules. Morph requires transition from B_shape to p_shape (bearish morph) or b_shape to D_shape (bullish morph). | Medium |
| **Structural targets** | Target = 1.5x IB range beyond breakout point. This aligns with P-Day / early trend targets. | Easy |
| **Failure abort** | If price trades back through DPOC after morph trigger, close the position immediately. This is a critical risk management feature. | Medium |
| **Integrate with Trend Day strategy** | Rather than standalone, make this a "late trigger" mode of Trend Day Bull/Bear. Morph is essentially a trend day that develops after 11:00 instead of during IB. | Medium |

**Expected after fix**: 10-20 trades, 50-55% WR, PF 1.5-2.0. Very low frequency but theoretically captures the highest-value transition in Dalton theory.

**Priority**: LOW-MEDIUM. High theoretical value but requires significant infrastructure (DPOC migration, profile shape) that doesn't exist yet. Better to fix Trend Day first.

---

### A5. ORB Enhanced -- Simplify or Retire

**Current state**: Disabled. Overengineered with 3 entry types (breakout, FVG retest, sweep reversal), C-period bias, SMT divergence, IB width classification.

**What went wrong:**

1. **Too many entry modes compete.** Three different entry types (breakout, FVG retest, sweep reversal) each with different risk profiles. The backtest engine treats them all the same but they should have different position sizes and time horizons.

2. **Overlaps with existing strategies.** ORB breakout = simplified OR Acceptance. ORB sweep reversal = simplified OR Reversal. FVG retest = simplified Trend Day pullback. The existing dedicated strategies do each of these better.

3. **FVG on 1-min bars is too noisy.** The study says FVG confluence improves entries, but the 1-min bar FVG detection produces hundreds of gaps per session. Most are noise.

**Recommendation**: RETIRE. The ORB Enhanced strategy is a "Swiss army knife" that does everything poorly. The existing OR Rev + OR Acceptance + 20P already cover the opening range with specialized, well-tuned logic.

If anything should be salvaged, it is the **IB width classification** concept (NARROW/NORMAL/WIDE). This is a useful SESSION-LEVEL feature that could be added to session_context and used by ALL strategies:
- NARROW IB (< 50% of 20-day ATR): Expect range expansion. Favor breakout strategies. Increase OR Rev/OR Acceptance confidence.
- WIDE IB (> 100% of 20-day ATR): Expect mean reversion. Favor B-Day, 80P. Reduce trend strategy confidence.

**Priority**: RETIRE the strategy. MEDIUM priority to extract IB width classification as a session context feature.

---

### A6. Super Trend Bull/Bear -- Too Rare to Be Useful

**Current state**: Disabled. Requires `super_trend_up` / `super_trend_down` day type (>2.0x IB extension).

**What went wrong:**

1. **Day type almost never classifies as super_trend.** In 270 sessions, there are perhaps 5-10 true super trend days. This gives us 5-10 total trades -- too few for statistical significance.

2. **Wide stops.** Stop below IBL on a super trend day = 100-200+ points of risk. At NQ tick value, this means $2,000-4,000 risk per contract.

3. **The strategy would work IF you could identify it early.** But by the time the session classifier labels a day as "super_trend_up," the move is already 2.0x IB and you are chasing.

**Recommendation**: MERGE into Trend Day Bull/Bear. When a Trend Day Bull position is already open and the extension exceeds 1.5x IB, add a pyramid entry with tighter trailing stop. This captures super trend behavior without a separate strategy classification.

**Priority**: LOW. Merge into Trend Day rewrite.

---

### A7. VA Edge Fade -- The Best Unstudied Strategy In Our Data

**Current state**: NOT BUILT as a backtest strategy. Exists only as a study (`2026.02.24-va-edge-fade-study.md`) and in the master comparison document.

**Study results (from 259 sessions, 620 events):**

| Config | Trades | WR | PF | $/Mo |
|--------|--------|-----|-----|------|
| 1st touch, inversion + swing + 4R | 156 | 30.1% | 1.30 | $1,453 |
| 2nd test, limit edge + 2ATR + POC | 120 | 55.0% | 1.63 | $1,309 |
| 2nd test, limit edge + swing + 1R | 120 | 70.0% | 2.25 | $813 |
| 1st SHORT, 2x5m + 2ATR + 0.2ATR trail | 80 | 70.0% | 7.28 | $396 |
| Combined 2x5m + 2ATR + 0.2ATR trail | 257 | 62.6% | 4.60 | $913 |

**Why this matters**: VA Edge Fade fires 10-22 times per month -- far more frequently than 80P (4/mo) or B-Day (4/mo). It fills the gap between the opening range strategies (first hour) and the 80P/B-Day strategies (structural levels). It trades the SAME VA framework as 80P but from the opposite direction (price approaches VA from inside, pokes outside, fails -- vs 80P where price opens outside and reverts inside).

**Key findings from the study:**

1. **B-Day LONG at IBL is the best setup**: 76% WR, PF 5.89. But we already have this as the B-Day strategy. VA Edge Fade adds VAH fades (shorts) and second-test entries.
2. **SHORTS at VAH first touch are golden**: 70% WR, PF 7.28 with 2x5m entry + 2ATR stop + 0.2ATR trail. This is the single highest PF setup across all studies.
3. **P-Day SHORTS = dead**: 29% WR. Never short P-Days from the VA edge. This is consistent with our P-Day findings.
4. **Limit at sweep extreme on 2nd test**: 72.4% WR, PF 5.38. Classic double top/bottom pattern at VA boundary.
5. **Delta is NOT the primary filter** for VA edge fades. TIME (30-min acceptance) is the filter.

**Implementation plan:**

```
Entry: VA Edge Fade (prior session VAH/VAL boundary)
  1. Detect poke beyond VA edge (price exceeds VAH/VAL by > 5 pts)
  2. Wait for acceptance: 2x 5-min bar closes back inside VA
  3. Enter in fade direction (SHORT after VAH poke-fail, LONG after VAL poke-fail)
  4. Filter: 1st or 2nd touch only. 3rd+ touch = skip.
  5. Filter: No P-Day shorts.

Stop: 2x ATR(14) from entry, OR VA edge + 10pt (whichever is smaller)
Target: 0.2 ATR trail (scalp mode) OR POC (structural mode)
Time gate: After IB close (10:30) through 14:30
Max 2 trades per session (1 VAH, 1 VAL)
```

**Expected**: 80-150 trades, 55-65% WR, PF 2.0-4.0, $15-40K net.

**Priority**: HIGH. This is essentially a new strategy with proven study results and extensive backtesting. It diversifies the portfolio into mid-session balance plays.

---

## 3. Section B: New Strategies From Our Domain

### B1. NWOG Gap Fill (Already In Progress)

**Status**: Study complete (`brainstorm/strategy/02-nwog-study.md`). Implementation not yet started.
**Study results**: 54 weeks of data.

| Variant | Trades/Year | WR | PF | Net PnL |
|---------|-------------|-----|-----|---------|
| VWAP-filtered, 75pt stop | 10 | 70% | 2.45 | $5,010 |
| Aggressive, 75pt stop | 27 | 52% | 2.50 | $25,135 |
| Conservative (DOWN only) | 4-6 | 70-80% | 2.0+ | ~$2,000 |

**Key findings:**
- 85.2% of NWOGs fill within the same week.
- DOWN gaps fill at 73.1% on Monday RTH vs 42.9% for UP gaps (30pp asymmetry).
- VWAP position at 10:00 is the single strongest predictor (88.2% fill when VWAP supports).
- 30-minute acceptance >= 30% = 100% fill rate (perfect predictor across 13 observations).
- Existing strategies perform significantly better on NWOG fill days (58.1% vs 50.9% WR).

**Implementation:**

```
Entry Rules (Rule Set A):
  1. Monday only. NWOG gap >= 20 pts.
  2. At 10:00: price must be on fill side of session VWAP.
  3. First 30 min: >= 30% of bars close on fill side of gap midpoint.
  4. Enter at 10:00 bar close, direction toward gap fill.

Stop: 60-75 pts from entry.
Target: Full gap fill (Friday RTH close).
Time stop: Exit at 13:00 if neither stop nor target hit.
Trailing: After +25 pts favorable, trail stop to breakeven.
```

**Data requirements**: We have everything needed. Friday/Sunday data is in our 1-min CSV.

**Synergy**: NWOG direction could serve as a CONFLUENCE FILTER for Monday's OR Rev, 80P, and B-Day signals. When NWOG fill direction aligns with strategy signal, increase confidence. When it opposes, reduce position size.

**Priority**: HIGH. Study is complete, implementation is well-defined, low-frequency but high-conviction.

---

### B2. NDOG (New Day Opening Gap) -- Daily Version of NWOG

**Concept**: The daily maintenance break (16:15-17:00 CT for CME, then 18:00 reopen) creates a daily gap. Same gap fill mechanics as NWOG but occurs Mon-Thu (4x/week).

**Entry rules:**

```
  1. Compute NDOG = Today's open (18:01 Globex) - Yesterday's RTH close (16:15).
  2. Filter: |NDOG| >= 10 pts (skip micro-gaps).
  3. During next day's RTH:
     a. At 10:00, check VWAP position relative to gap fill direction.
     b. If VWAP supports fill: enter toward fill at 10:00 bar close.
     c. Stop: 50-75 pts. Target: full gap fill (yesterday's close).
```

**Expected frequency**: 2-3 qualifying gaps per week = 100-150 trades/year.
**Data requirements**: We have everything needed. Globex + RTH data exists.
**Expected performance**: If NWOG fill rates generalize to daily, expect 50-60% WR, PF 1.5-2.0.

**Why it matters**: NDOG gives us much higher frequency than NWOG (weekly). If the gap fill mechanics hold, this could be a 100+ trade strategy adding $10-30K.

**Priority**: MEDIUM-HIGH. Easy to study with existing data and piggybacks on NWOG findings.

**Note (2026-03-09)**: May overlap with B-Day / balance day strategies — the RTH open gap on a balance session IS the "inside gap" that B-Day tries to fade. Need to validate that NDOG signals don't duplicate B-Day signals before running both. If overlap is >50%, consider merging NDOG as a B-Day entry variant rather than standalone.

---

### B3. VA Edge Fade (Prior Session)

See Section A7 above. This is listed here because it is technically a NEW strategy implementation even though the study exists.

**Priority**: HIGH.

---

### B4. IB Edge Fade (Intraday)

**Concept**: Identical logic to VA Edge Fade but applied to TODAY's IB boundaries instead of prior session VA boundaries. The B-Day study (`2026.02.27-balance-day-edge-fade-study.md`) already proves this works.

**Current state**: Our B-Day strategy ALREADY implements the IBL long fade. What's missing is:
1. **IBH short fade**: B-Day currently only trades LONG from IBL. The study shows IBH shorts on B-Day = 69% WR, PF 2.11.
2. **Second-touch entries**: B-Day only trades the first touch. The VA Edge Fade study shows 2nd test with limit at sweep extreme = 72.4% WR.
3. **Neutral/P-Day IBL longs**: B-Day study shows Neutral LONG = 61% WR, P-Day LONG = 62% WR. The current B-Day strategy already accepts all day types, but adding explicit support for these could improve results.

**How to add IBH short:**

```
Entry: IB Edge Fade SHORT
  1. Detect first IBH touch (high within 5 pts of IBH)
  2. Wait 30 bars (30 min)
  3. At bar 30: if close < IBH -> acceptance -> ENTER SHORT
  4. Filter: NOT on Trend Up days (mirror of B-Day's Trend Down filter)
  5. Stop: IBH + 10% IB range
  6. Target: IB midpoint
```

**Expected**: Adding IBH short to existing B-Day could add 20-30 trades, ~60% WR, $5-10K net.

**Priority**: MEDIUM. Extends proven B-Day logic symmetrically.

---

### B5. Delta/CVD Divergence Entries

**Concept**: When price makes a new high but CVD (Cumulative Volume Delta) makes a lower high, institutional selling is occurring despite price rise. This is a classic order flow divergence setup.

**Entry rules:**

```
Long (Bullish Divergence):
  1. Price makes a lower low (new session low or swing low).
  2. CVD makes a higher low (buying at lower prices).
  3. Delta on current bar turns positive (buyers stepping in).
  4. RSI < 40 (oversold territory).
  5. Enter LONG at close of reversal bar.
  Stop: Below swing low - 0.5x ATR.
  Target: VWAP or IB midpoint.

Short (Bearish Divergence):
  Mirror logic.
```

**Data requirements**: We have delta and CVD in our volumetric 1-min data. We would need to compute rolling CVD and detect divergence patterns.

**Technical challenge**: Divergence detection on 1-min bars produces many false signals. Need to use 5-min or 15-min aggregated CVD for cleaner divergence detection.

**Expected**: 50-100 trades, 45-55% WR, PF 1.3-1.8. Lower edge per trade but high frequency.

**Priority**: MEDIUM. Requires CVD divergence detection infrastructure. Could be very powerful as a FILTER for existing strategies (e.g., skip OR Rev when CVD diverges against trade direction).

---

### B6. Poor High/Low Plays (Market Profile)

**Concept**: A "poor high" in Market Profile theory is a high without excess -- the market failed to test for more buyers at the top, leaving unfinished business. Price tends to return to poor highs/lows to "repair" them.

**Entry rules:**

```
Long (Poor Low Repair):
  1. Prior session ended with a poor low (no excess tail at session low).
  2. Today's price approaches prior session low.
  3. Wait for acceptance (2x5-min closes above prior low).
  4. Enter LONG targeting prior session POC.
  Stop: Below prior session low - 10 pts.
  Target: Prior session POC or 0.5x prior session range.

Short (Poor High Repair):
  Mirror logic.
```

**Data requirements**: We already compute poor_high and poor_low in the deterministic modules. We need to persist prior session poor high/low status into today's session context.

**Expected**: 20-40 trades, 55-60% WR, PF 1.5-2.0. These are structural plays with strong Dalton theory backing.

**Priority**: MEDIUM. Low implementation effort since poor high/low detection already exists.

---

### B7. Single Print Gap Fill

**Concept**: Single prints (one TPO letter per price level) represent velocity moves where price traded through quickly without building value. These act as magnets -- price tends to return to fill them.

**Entry rules:**

```
Long (Fill Single Prints Below):
  1. Identify single print gap below current price (from today's profile).
  2. Price is declining toward the gap.
  3. When price enters the single print zone: wait for reversal bar.
  4. Enter LONG at close of reversal bar.
  Stop: Below single print zone - 5 pts.
  Target: Top of single print zone + 0.5x zone width.

Short (Fill Single Prints Above):
  Mirror logic.
```

**Data requirements**: We have TPO computation in deterministic modules. Need to identify and persist single print zones.

**Expected**: 15-30 trades, 55-65% WR, PF 1.5-2.5. Single prints are high-conviction magnets.

**Priority**: LOW-MEDIUM. Requires TPO zone persistence infrastructure.

---

### B8. Two Hour Trader (Options Overlay)

**Concept**: Options overlay on confirmed futures direction, 9:30-11:30 window. This is a separate instrument (SPY/QQQ/SPX options), not NQ futures.

**Study target**: 60-79% WR, PF 2.0-6.76 (from verified results).

**Entry rules (from study):**

```
Version A (Momentum Breakout):
  1. Time: 9:30-11:30.
  2. SPX breaks above/below 5-min OR high/low.
  3. Volume > 20-period average.
  4. VIX < 25.
  5. Enter call (breakout up) or put (breakout down).
  Strike: ATM or 0.30-0.45 delta. Expiration: 0-2 DTE.

Version B (VWAP Bounce):
  1. Price above VWAP (bullish) or below (bearish).
  2. Price pulls back to VWAP.
  3. Candle rejects VWAP with wick.
  4. Enter in VWAP trend direction.
```

**Data requirements**: We do NOT have options data. Would need options chain data (strikes, Greeks, prices) for SPX/SPY/QQQ. This is a fundamentally different data pipeline.

**Expected**: Cannot backtest with current infrastructure.

**Priority**: LOW for backtest implementation. HIGH for live trading (separate system). This should be flagged as a "parallel track" -- build separately, do not integrate into the NQ backtest engine.

---

### B9. Ledge (Horizontal TPO Cluster) Breakout

**Concept**: A "ledge" in TPO analysis is a horizontal cluster of TPO letters at the same price -- multiple periods spending time at one level. When price breaks out of a ledge, it has rejected that value and tends to move directionally.

**Entry rules:**

```
  1. Identify ledge: >= 4 consecutive TPO periods with closes within 10-point range.
  2. Breakout: price closes outside the ledge range with volume.
  3. Enter in breakout direction.
  Stop: Opposite side of ledge.
  Target: 1.5x ledge range.
  Time gate: Only after 10:30 (IB must be established first).
```

**Data requirements**: We have TPO data from deterministic modules. Ledge detection requires identifying horizontal clusters in real-time.

**Expected**: 15-25 trades, 50-55% WR, PF 1.3-1.8.

**Priority**: LOW. Interesting Dalton concept but no study data to validate.

---

## 4. Section C: Quantitative Strategies Worth Testing

These are standard quant strategies adapted for 1-min NQ futures bars.

### C1. Bollinger Band Extreme Reversal

**Concept**: Enter counter-trend when price touches or breaks Bollinger Bands with RSI confirmation.

**Entry rules:**

```
Long:
  1. Price touches lower BB(20, 2.0) on 5-min bars.
  2. RSI(14) < 30 on 5-min.
  3. ADX(14) < 25 on 5-min (range-bound market).
  4. Volume declining (exhaustion, not continuation).
  5. Enter LONG at close of touch candle.
  Stop: Below swing low or BB - 0.5 ATR.
  Target: Middle BB (20-period SMA) or VWAP.
  Time exit: If not profitable in 15 bars, exit.

Short: Mirror logic with upper BB + RSI > 70.
```

**Data requirements**: Need to compute BB(20, 2.0) from 1-min bars aggregated to 5-min. RSI already exists. ADX needs to be computed.

**Synergy with existing**: This is essentially an improved Mean Reversion VWAP. It adds the statistical extreme filter (BB touch) that the current implementation lacks. Could REPLACE Mean Reversion VWAP rather than coexist.

**Expected**: 60-120 trades, 55-60% WR, PF 1.4-1.8.

**Priority**: MEDIUM. Natural evolution of Mean Reversion VWAP.

---

### C2. RSI Divergence Entries

**Concept**: Price-RSI divergence on 5-min timeframe signals exhaustion.

**Entry rules:**

```
Bullish Divergence (LONG):
  1. Price makes lower low on 5-min bars.
  2. RSI(14) makes higher low (divergence).
  3. Candle shows reversal pattern (hammer, bullish engulfing).
  4. Enter LONG at close of reversal candle.
  Stop: Below the lower low - 5 pts.
  Target: Prior swing high or 2R.

Bearish Divergence (SHORT):
  Mirror logic.
```

**Technical challenge**: Divergence detection requires identifying swing highs/lows in real-time on 5-min aggregated data. Need a lookback window (typically 10-20 bars on 5-min = 50-100 bars on 1-min).

**Expected**: 30-60 trades, 50-55% WR, PF 1.3-1.6. RSI divergence is a well-studied setup with modest but consistent edge.

**Priority**: LOW-MEDIUM. Moderate difficulty, modest expected edge.

---

### C3. Keltner Channel Breakout

**Concept**: Price breaking out of Keltner Channels (EMA + ATR bands) signals trend initiation or continuation.

**Entry rules:**

```
Long Breakout:
  1. Price closes above upper Keltner (EMA20 + 2x ATR14) on 5-min.
  2. ADX > 25 (trending market).
  3. Volume > 1.3x average.
  4. Enter LONG at close.
  Stop: Below EMA20.
  Target: Trail with EMA20 or 3R.

Mean Reversion (Counter-Trend):
  1. Price touches lower Keltner and reverses.
  2. ADX < 25 (range-bound).
  3. Enter LONG at reversal bar close.
  Stop: Below lower Keltner - 0.5 ATR.
  Target: EMA20 (middle line).
```

**Data requirements**: Need EMA20 and ATR14, which are straightforward to compute.

**Synergy**: Keltner breakout is essentially a more sophisticated version of our Trend Day Bull/Bear entry. The ADX gate + Keltner breakout could REPLACE the current acceptance + EMA alignment logic.

**Expected**: 40-80 trades, 50-55% WR, PF 1.5-2.0.

**Priority**: LOW. Interesting but overlaps heavily with Trend Day strategy rewrite.

---

### C4. Opening Gap Strategies (Beyond NWOG)

**Concept**: Multiple gap types that can be traded systematically.

**Gap types:**

| Gap Type | Definition | Frequency | Fill Rate |
|----------|-----------|-----------|-----------|
| NWOG | Friday close to Sunday open | 1/week | 85% weekly |
| NDOG | Prior day close to today's Globex open | 4/week | ~70% estimated |
| RTH Gap | Globex close to RTH open (9:30) | Daily | ~60% estimated |
| True Gap | Prior day RTH close to today RTH open | Daily | ~50% estimated |

**Entry rules for RTH Gap Fill:**

```
  1. Compute RTH gap = RTH open (9:30) - Globex close (9:29).
  2. Filter: |gap| >= 10 pts.
  3. At OR close (9:45): enter toward gap fill.
  4. VWAP check at 10:00: confirm price on fill side.
  Stop: 50-75 pts.
  Target: Gap fill (Globex close level).
  Time stop: 11:00 (if not filled, unlikely to fill).
```

**Data requirements**: We have Globex data. RTH open and Globex close are in our CSV.

**Expected**: 100-200 trades, 50-55% WR, PF 1.3-1.8. Gap fill is a well-known edge but fills quickly (most within 15 min of RTH open).

**Priority**: MEDIUM. High frequency, well-known edge, easy to implement.

---

### C5. TICK Extreme Entries (Market Internals)

**Concept**: NYSE TICK ($TICK) measures the number of stocks ticking up vs down. Extreme readings (> +1000 or < -1000) signal short-term exhaustion.

**Entry rules:**

```
Long (TICK Extreme Low):
  1. TICK reads below -800 (extreme selling).
  2. Price is at or near session low or VWAP.
  3. Next bar TICK recovers above -500 (exhaustion ending).
  4. Enter LONG at close of recovery bar.
  Stop: Below session low - 0.5 ATR.
  Target: VWAP or 2R.
  Time exit: If not profitable in 10 bars, exit.

Short (TICK Extreme High):
  Mirror logic with TICK > +800.
```

**Data requirements**: We do NOT have $TICK data in our CSV. Would need to add NYSE TICK as a secondary data feed. This is available from most data providers (NinjaTrader, Sierra Chart) but is not in our current 1-min NQ volumetric bars.

**Expected**: 50-100 trades, 55-60% WR, PF 1.5-2.0. TICK extremes are a reliable short-term exhaustion signal.

**Priority**: LOW. Requires new data feed. The data gap makes this impractical for immediate implementation.

---

### C6. Volume Profile Gap Fill

**Concept**: Gaps in the volume profile (Low Volume Nodes -- LVNs) act as magnets. Price tends to move through LVNs quickly, and when it approaches one, the LVN can either pull price through or act as support/resistance.

**Entry rules:**

```
  1. Identify LVN from prior session volume profile (volume < 30th percentile).
  2. Price approaching LVN from above: enter LONG if LVN is expected to act as support.
  3. Price approaching LVN from below: enter SHORT if LVN is expected to act as resistance.
  4. Decision: If price entered LVN zone and spent < 3 bars there, it is acting as magnet (go with momentum). If price spent > 5 bars, it is being accepted (fade the move).
  Stop: Opposite side of LVN zone.
  Target: Next HVN (High Volume Node) or prior session POC.
```

**Data requirements**: We have volume profile computation in our deterministic modules. Need to persist prior session LVN/HVN zones.

**Expected**: 20-40 trades, 50-55% WR, PF 1.3-1.6.

**Priority**: LOW. Interesting concept but requires LVN/HVN persistence and real-time detection.

---

### C7. VWAP Standard Deviation Bands

**Concept**: VWAP with 1, 2, 3 standard deviation bands creates statistically significant zones. Trading reversals at 2-sigma bands is a proven institutional approach.

**Entry rules:**

```
Long (Lower 2-Sigma Band):
  1. Price touches or breaks below VWAP - 2 sigma.
  2. RSI < 35 or volume declining.
  3. Candle shows reversal (close above open).
  4. Enter LONG.
  Stop: Below VWAP - 3 sigma.
  Target: VWAP (mean reversion to anchor).

Short (Upper 2-Sigma Band):
  Mirror logic.
```

**Data requirements**: We have VWAP in our data. Need to compute rolling standard deviation of price around VWAP to create bands. This is a standard calculation but not currently implemented.

**Expected**: 30-60 trades, 55-65% WR, PF 1.5-2.0. 2-sigma bands are statistically robust zones.

**Priority**: MEDIUM. Natural extension of our VWAP infrastructure. Cleaner signal than the current Mean Reversion VWAP approach.

---

### C8. London Open Fade / Asia Range Breakout

**Concept**: London session (03:00-09:30 ET) establishes the "real" overnight direction. When RTH opens, price either continues London's direction (acceptance) or reverses it (London fade).

**Entry rules:**

```
London Fade (Counter-Trend):
  1. London made a clear directional move (London range > 50 pts, 70%+ of bars in one direction).
  2. RTH opens and London direction stalls (first 15 min of RTH go opposite).
  3. Enter counter-London at OR close (9:45).
  Stop: London extreme + 10 pts.
  Target: 50% of London range retracement.

Asia Range Breakout:
  1. Asia range (20:00-02:00 ET) is tight (< 50 pts).
  2. London breaks out of Asia range in one direction.
  3. RTH opens and holds above/below Asia range.
  4. Enter in London direction at OR close.
  Stop: Inside Asia range (opposite boundary).
  Target: 1.5x Asia range from breakout level.
```

**Data requirements**: We have Globex data including London and Asia sessions. The NWOG study already identifies London and Asia session bars.

**Connection to existing strategies**: The brainstorm doc (07-augmenting-training-tape-reading-intelligence.md) already describes London/Asia as key pre-market context. Adding systematic entries based on London behavior creates a pre-RTH strategy layer.

**Expected**: 40-80 trades, 50-55% WR, PF 1.3-1.8. London fade is well-known but edge has eroded.

**Priority**: LOW-MEDIUM. Interesting for pre-market context but not a high-priority standalone strategy.

---

## 5. Section D: Priority Ranking

### Tier 1: Implement Now (Next 2 Weeks)

These have proven study data, clear implementation paths, and high expected impact.

| Rank | Strategy | Expected Trades | Expected WR | Expected PnL | Difficulty | Data Ready? | Synergy |
|------|----------|----------------|-------------|--------------|------------|------------|---------|
| **1** | **Trend Day Bull/Bear Rewrite** | 60-100 | 50-55% | $15-30K | Medium | Yes | Captures trend days (15% of sessions) currently untouched |
| **2** | **VA Edge Fade (New)** | 80-150 | 55-65% | $15-40K | Medium | Yes | Fills mid-session gap between OR and 80P strategies |
| **3** | **NWOG Gap Fill (New)** | 10-27 | 52-70% | $5-25K | Easy | Yes | Monday-only, low correlation with other strategies |
| **4** | **B-Day IBH Short (Extend)** | 20-30 | 60% | $5-10K | Easy | Yes | Symmetric extension of proven B-Day LONG |

**Net portfolio impact if all Tier 1 implemented**: 170-307 additional trades, estimated $40-100K additional PnL. Current portfolio goes from $159K to approximately $200-260K.

### Tier 2: Study and Prototype (Weeks 3-4)

These require new indicators or infrastructure but have strong theoretical backing.

| Rank | Strategy | Expected Trades | Expected WR | Expected PnL | Difficulty | Data Ready? | Blocker |
|------|----------|----------------|-------------|--------------|------------|------------|---------|
| **5** | **Mean Reversion VWAP Rewrite** | 40-80 | 55-60% | $5-15K | Medium | Yes | Needs ADX + BB computation |
| **6** | **NDOG (Daily Gap Fill)** | 100-150 | 50-60% | $10-30K | Easy | Yes | Needs study (piggybacks on NWOG) |
| **7** | **VWAP Deviation Bands** | 30-60 | 55-65% | $5-15K | Medium | Partial | Needs VWAP sigma bands |
| **8** | **Poor High/Low Plays** | 20-40 | 55-60% | $3-10K | Medium | Yes | Needs prior session poor H/L persistence |

### Tier 3: Research Phase (Month 2+)

These are interesting but require new data, significant new infrastructure, or have uncertain edge.

| Rank | Strategy | Expected Trades | Expected WR | Expected PnL | Difficulty | Data Ready? | Blocker |
|------|----------|----------------|-------------|--------------|------------|------------|---------|
| **9** | **BB Extreme Reversal** | 60-120 | 55-60% | $5-15K | Medium | Partial | Needs BB computation; may replace MR VWAP |
| **10** | **RTH Gap Fill** | 100-200 | 50-55% | $5-15K | Easy | Yes | Needs study on RTH gaps |
| **11** | **CVD Divergence** | 50-100 | 45-55% | $3-10K | Hard | Yes | Divergence detection is complex |
| **12** | **Morph to Trend** | 10-20 | 50-55% | $2-5K | Hard | Partial | Needs DPOC migration tracking |
| **13** | **RSI Divergence** | 30-60 | 50-55% | $2-5K | Medium | Partial | Needs swing detection + RSI divergence logic |
| **14** | **Single Print Gap Fill** | 15-30 | 55-65% | $2-5K | Hard | Partial | Needs TPO zone persistence |
| **15** | **Keltner Channel** | 40-80 | 50-55% | $3-8K | Medium | Partial | Overlaps with Trend Day rewrite |
| **16** | **London Open Fade** | 40-80 | 50-55% | $2-8K | Medium | Yes | Low edge, well-arbitraged |

### Tier 4: Separate Track

| Rank | Strategy | Notes |
|------|----------|-------|
| **17** | **Two Hour Trader (Options)** | Requires options data. Separate system. Do not integrate into NQ backtest. |
| **18** | **TICK Extremes** | Requires $TICK data feed. Not in current data. |
| **19** | **Volume Profile Gap Fill** | Requires LVN/HVN persistence. Low priority. |
| **20** | **Ledge Breakout** | Interesting but no study data. Research only. |

### Strategies to RETIRE

| Strategy | Reason |
|----------|--------|
| ORB Enhanced | Overlaps with OR Rev + OR Acceptance + 20P. Overengineered. |
| ORB VWAP Breakout | Simpler version of ORB Enhanced. Same overlap problem. |
| Super Trend Bull/Bear | Too rare. Merge into Trend Day as pyramid mode. |
| P-Day (standalone) | Merge into Trend Day as reduced-target mode. |
| Neutral Day | No signals. Not a strategy. |
| PM Morph | Not studied. Low priority. |
| EMA Trend Follow | Replace with Trend Day rewrite. |
| Liquidity Sweep | Too noisy on 1-min bars. Captured by OR Rev sweep detection. |
| MACD Crossover | Lagging indicator. No edge on 1-min NQ. |

---

## 6. Section E: Data Gap Analysis

### What We Have

| Data | Source | Status |
|------|--------|--------|
| NQ 1-min volumetric bars | NinjaTrader CSV | 270+ sessions, 367K rows |
| OHLCV + VWAP + Delta + CVD | Computed in features.py | Complete |
| RSI(14), EMA(5/20/50) | Computed in features.py | Complete |
| IB range/high/low/mid | Computed in session.py | Complete |
| Fair Value Gaps (1-min, 5-min, 15-min) | FVG lifecycle module | Complete |
| TPO/Market Profile | Deterministic modules | Complete |
| Prior session VA/POC/VAH/VAL | Session context | Complete |
| Poor high/low detection | Deterministic modules | Complete |
| Day type classification | Day type module | Complete |
| VIX daily values | Regime context | Complete |
| Regime labels (composite) | Regime context | Complete |
| DuckDB research database | research.duckdb | Complete |

### What We Need

| Data/Feature | Required By | Difficulty | Notes |
|--------------|-------------|------------|-------|
| **ADX(14) on 5-min** | Trend Day rewrite, Mean Reversion, BB Extreme | Medium | Compute from 1-min bars, aggregate to 5-min. Standard TA library. |
| **Bollinger Bands (20, 2.0) on 5-min** | BB Extreme Reversal, Mean Reversion rewrite | Medium | Standard computation. |
| **VWAP sigma bands** | VWAP Deviation Bands strategy | Medium | Rolling stddev of price-VWAP. |
| **15-min EMA(20/50)** | Trend Day rewrite | Easy | Aggregate 1-min to 15-min, compute EMAs. |
| **Keltner Channels** | Keltner strategy | Easy | EMA20 + ATR14 bands. |
| **Prior session LVN/HVN zones** | Volume Profile Gap Fill | Hard | Profile decomposition + persistence. |
| **DPOC migration tracking** | Morph to Trend | Hard | 30-min DPOC computation + migration rate. |
| **Swing high/low detection** | RSI Divergence, CVD Divergence | Medium | N-bar swing detection algorithm. |
| **$TICK data** | TICK Extremes | Hard | Requires new data feed from NinjaTrader. |
| **Options chain data** | Two Hour Trader | Hard | Entirely new data pipeline. |
| **Friday 17:00 close** | NWOG precision | Easy | Extend data to include settlement close. |
| **Economic calendar** | News filter (all strategies) | Medium | API integration (FRED, Trading Economics). |

### Infrastructure Priorities

1. **ADX computation** -- unlocks Trend Day rewrite + Mean Reversion rewrite + regime gating. Highest leverage single feature to add.
2. **Multi-timeframe aggregation** -- compute 5-min and 15-min bars from 1-min. Many strategies need 5/15-min indicators. Build once, use everywhere.
3. **Prior session context persistence** -- carry forward poor high/low, LVN/HVN, VA edges into today's session context. Unlocks Poor High/Low plays and improves VA Edge Fade.

---

## 7. Section F: Implementation Phases

### Phase 1: Tier 1 Strategies (Week 1-2)

**Goal**: Add 4 strategies/extensions, targeting +$40K portfolio PnL.

**Week 1:**
1. **Trend Day Bull/Bear Rewrite**
   - Add 15-min EMA(20/50) computation to features.py
   - Remove day_type gate from TrendDayBull/TrendDayBear
   - Add EMA alignment check (price > EMA20 > EMA50)
   - Reduce default target to 1.5x IB
   - Re-enable and run backtest
   - Validation: expect 60-100 trades, >50% WR, >$15K net

2. **B-Day IBH Short Extension**
   - Add `_vah_fade_taken` and IBH touch detection to b_day.py
   - Mirror the existing IBL long logic for IBH shorts
   - Add Trend Up day filter (block shorts on trend up)
   - Run backtest
   - Validation: expect 20-30 trades, >55% WR

**Week 2:**
3. **VA Edge Fade (New Strategy)**
   - Create `va_edge_fade.py` in strategies directory
   - Implement 2x5-min acceptance entry at prior VA boundaries
   - Add VA edge + 10pt stop model
   - Add 0.2 ATR trail and POC targets as configurable options
   - Add to strategies.yaml
   - Run backtest
   - Validation: expect 80-150 trades, 55-65% WR

4. **NWOG Gap Fill (New Strategy)**
   - Create `nwog_gap_fill.py` in strategies directory
   - Implement Rule Set A (VWAP-filtered, 10:00 entry)
   - Add 75pt stop, full gap fill target, 13:00 time stop
   - Add to strategies.yaml (Monday only)
   - Run backtest
   - Validation: expect 10-27 trades, >50% WR

### Phase 2: Tier 2 Strategies + Filters (Weeks 3-4)

**Goal**: Add ADX infrastructure, rewrite Mean Reversion, study NDOG.

**Week 3:**
5. **ADX computation** -- add to features.py
6. **Multi-timeframe aggregation** -- 5-min and 15-min bar computation
7. **Mean Reversion VWAP Rewrite** with ADX < 25 gate + BB touch filter
8. **NDOG Study** -- run gap fill analysis on daily gaps using NWOG methodology

**Week 4:**
9. **VWAP Deviation Bands** -- compute sigma bands, prototype strategy
10. **Poor High/Low Plays** -- persist prior session flags, implement entries
11. **Bias alignment filter** -- implement the Phase 4 recommended filter across all strategies
12. **Portfolio optimization** -- run combined backtest with all new strategies, check for trade overlap

### Phase 3: Tier 3 Research (Month 2)

- BB Extreme Reversal (may replace Mean Reversion VWAP)
- RTH Gap Fill study
- CVD Divergence as filter (not standalone strategy)
- Morph to Trend (requires DPOC migration)

### Phase 4: Agent Integration (Month 3)

- All new strategies emit signals through the strategy runner
- Bias alignment, TPO shape, and regime filters applied by deterministic engine
- LLM tape reader evaluates confluence of strategy signals + tape context
- Advocate/Skeptic debate weighs strategy confidence + deterministic filters
- Orchestrator makes final trade decision

---

## Appendix A: Strategy Portfolio Heat Map

This shows which market conditions each strategy covers. The goal is to have at least one strategy active in every cell.

```
                     RANGE-BOUND         TRANSITIONING        TRENDING
                   (ADX<20, balance)    (ADX 20-30)         (ADX>30)
                  ┌─────────────────┬─────────────────┬─────────────────┐
                  │                 │                 │                 │
  FIRST HOUR      │  OR Rev         │  OR Rev         │  OR Rev         │
  (9:30-10:30)    │  OR Acceptance  │  OR Acceptance  │  OR Acceptance  │
                  │  NWOG (Mon)     │  NWOG (Mon)     │  20P IB Ext     │
                  │                 │  20P IB Ext     │                 │
                  ├─────────────────┼─────────────────┼─────────────────┤
                  │                 │                 │                 │
  IB CLOSE        │  B-Day          │  B-Day          │  Trend Day*     │
  (10:30-11:30)   │  80P Rule       │  VA Edge Fade*  │  Trend Day*     │
                  │  VA Edge Fade*  │  80P Rule       │  20P IB Ext     │
                  │  Poor H/L*      │  Morph*         │                 │
                  ├─────────────────┼─────────────────┼─────────────────┤
                  │                 │                 │                 │
  MID-SESSION     │  Mean Rev VWAP* │  NDOG*          │  Trend Day*     │
  (11:30-14:00)   │  BB Extreme*    │                 │  (trailing)     │
                  │  VWAP Bands*    │                 │                 │
                  ├─────────────────┼─────────────────┼─────────────────┤
                  │                 │                 │                 │
  PM SESSION      │  (avoid)        │  (avoid)        │  Trend Day*     │
  (14:00-16:00)   │                 │                 │  (trailing only)|
                  │                 │                 │                 │
                  └─────────────────┴─────────────────┴─────────────────┘

  * = new or re-optimized strategy from this roadmap
  Blank = no strategy, avoid trading (principle: caution over conviction)
```

**Key gaps filled by this roadmap:**
1. **Trending markets (ADX>30)** -- currently ZERO strategies fire here. Trend Day rewrite fills this.
2. **Mid-session balance** -- only B-Day occasionally fires here. Mean Reversion VWAP rewrite + VA Edge Fade + VWAP Bands fill this.
3. **IB close zone on transition days** -- VA Edge Fade + Morph to Trend fill this.
4. **Monday-specific** -- NWOG adds a structural edge unique to Monday opens.

---

## Appendix B: Correlation Matrix (Expected)

Strategies should have LOW correlation with each other for portfolio diversification.

```
                  OR Rev  OR Acc  80P   20P   B-Day  Trend*  VA Edge*  MR VWAP*  NWOG*
  OR Rev           1.00
  OR Acc           0.35    1.00
  80P Rule        -0.10   -0.05   1.00
  20P IB Ext       0.15    0.20  -0.15   1.00
  B-Day           -0.20   -0.10   0.30  -0.20   1.00
  Trend Day*       0.10    0.15  -0.30   0.25  -0.25   1.00
  VA Edge Fade*   -0.15   -0.10   0.40  -0.15   0.35  -0.30    1.00
  MR VWAP*        -0.20   -0.15   0.25  -0.20   0.30  -0.35    0.40     1.00
  NWOG*            0.10    0.10   0.20   0.05   0.05  -0.05    0.10     0.05     1.00
```

**Key observations:**
- **Trend Day** is negatively correlated with B-Day and VA Edge Fade (trend vs balance). Excellent diversification.
- **VA Edge Fade** is positively correlated with 80P and B-Day (all trade balance/range). This is expected -- they share market conditions but different trigger points.
- **NWOG** has low correlation with everything (Monday-only, unique trigger).
- **MR VWAP** is positively correlated with VA Edge Fade (both trade mid-session balance). May want to limit combined position size.

---

## Appendix C: Key Study References

| Study | Location | Key Finding |
|-------|----------|------------|
| Trend Following Breakout | `BookMapOrderFlowStudies/research/strategy-studies/exploratory/TREND_FOLLOWING_BREAKOUT_STUDY.md` | 58% WR, 2.8 PF, $1,465/day target |
| Mean Reversion | `BookMapOrderFlowStudies/research/strategy-studies/exploratory/MEAN_REVERSION_STUDY.md` | 65% WR in range, ADX<25 critical |
| Two Hour Trader | `BookMapOrderFlowStudies/research/strategy-studies/exploratory/TWO_HOUR_TRADER_STUDY.md` | 60-79% WR, options overlay |
| Opening Range Breakout | `BookMapOrderFlowStudies/research/strategy-studies/exploratory/OPENING_RANGE_BREAKOUT_STUDY.md` | 55% WR, 2:1 R:R |
| Balance Day Edge Fade | `BookMapOrderFlowStudies/research/strategy-studies/balance-day-edge-fade/2026.02.27-balance-day-edge-fade-study.md` | B-Day LONG 82% WR (first touch) |
| VA Edge Fade | `BookMapOrderFlowStudies/research/strategy-studies/va-edge-fade/2026.02.24-va-edge-fade-study.md` | 72.4% WR limit at sweep extreme |
| Master Strategy Comparison | `BookMapOrderFlowStudies/research/strategy-studies/comparisons/2026.02.24-master-strategy-comparison.md` | 80P Limit 50% VA = $1,922/mo, PF 2.57 |
| 80P Rule Study | `BookMapOrderFlowStudies/research/strategy-studies/80p-rule/2026.02.22-80p-rule-strategy-report-v3.md` | Acceptance close 44.7% WR, 2.57 PF |
| 20P Rule Study | `BookMapOrderFlowStudies/research/strategy-studies/20p-rule/2026.02.23-20p-rule-study.md` | 3x5min + 2xATR + 2R = $496/mo |
| NWOG Study | `brainstorm/strategy/02-nwog-study.md` | 85.2% weekly fill, VWAP filter 88.2% |
| Phase 4 Trade Analysis | `brainstorm/analysis/01-trade-analysis-phase4.md` | Bias alignment = #1 filter |
| Tape Reading Intelligence | `brainstorm/07-augmenting-training-tape-reading-intelligence.md` | 8 strategy observations, first hour framework |

---

*Document Version: 1.0*
*Status: Brainstorm / Active Planning*
*Next review: After Tier 1 implementation complete*
