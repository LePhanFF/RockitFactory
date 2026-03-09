# NWOG / NDOG Online Research

> Compiled 2026-03-09 from ICT community sources, quantitative gap studies, and trading forums.
> This document provides external research to complement our own backtesting study.

---

## Table of Contents

1. [What Is NWOG (ICT Definition)](#1-what-is-nwog-ict-definition)
2. [How NWOG Is Calculated](#2-how-nwog-is-calculated)
3. [What Is NDOG (New Day Opening Gap)](#3-what-is-ndog-new-day-opening-gap)
4. [NWOG vs NDOG -- Key Differences](#4-nwog-vs-ndog----key-differences)
5. [Core ICT Rules for Trading NWOG](#5-core-ict-rules-for-trading-nwog)
6. [Gap Fill Statistics](#6-gap-fill-statistics)
7. [Entry / Exit Frameworks](#7-entry--exit-frameworks)
8. [Common Pitfalls -- When NWOG Gaps Do NOT Fill](#8-common-pitfalls----when-nwog-gaps-do-not-fill)
9. [NWOG Relationship to Other ICT Concepts](#9-nwog-relationship-to-other-ict-concepts)
10. [NWOG + Market Profile / Auction Theory Integration](#10-nwog--market-profile--auction-theory-integration)
11. [Implications for Rockit Framework](#11-implications-for-rockit-framework)
12. [Sources](#12-sources)

---

## 1. What Is NWOG (ICT Definition)

The **New Week Opening Gap (NWOG)** is an ICT (Inner Circle Trader) concept referring to the price gap that forms between the **previous week's closing price** and the **new week's opening price**. In ICT terminology, the NWOG is classified as a **liquidity void** -- a zone where no transactions occurred during the weekend closure, yet order flow, economic news, geopolitical events, and liquidity changes continued to accumulate.

### Why It Matters

- The gap represents a **fair value gap** (FVG) at the weekly level -- a price imbalance that the market tends to revisit.
- Price action seeks liquidity, so it often retraces to fill this gap, making it a natural **draw on liquidity**.
- The NWOG gives a valuable clue about **institutional sentiment** for the upcoming week: gap-up suggests bullish positioning, gap-down suggests bearish positioning.
- NWOGs from previous weeks remain active reference levels until they are filled -- they don't expire after just one week.

### Gap Direction

- **Bullish NWOG**: Sunday open is **above** Friday close (gap up). Suggests bullish sentiment carried over the weekend.
- **Bearish NWOG**: Sunday open is **below** Friday close (gap down). Suggests bearish sentiment carried over the weekend.

---

## 2. How NWOG Is Calculated

### For CME Futures (NQ, ES, YM, etc.)

CME Globex equity index futures trade Sunday through Friday with a daily **60-minute maintenance break** from **5:00 PM to 6:00 PM Eastern Time**. This creates two relevant closing/opening times:

| Boundary | Time (ET) | Notes |
|---|---|---|
| **Friday Close** | 5:00 PM ET (Friday) | End of the weekly session; Globex halts |
| **Sunday Open** | 6:00 PM ET (Sunday) | Globex resumes for the new week |

**The NWOG is the price range between the last traded price at Friday 5:00 PM ET and the first traded price at Sunday 6:00 PM ET.**

Some implementations use slightly different times:
- **4:59 PM EST** for Friday close (ICT's original forex definition)
- **4:15 PM ET** for the RTH (Regular Trading Hours) close on Friday
- The "pure" CME gap isolates the **5:00-6:00 PM ET transition** specifically

### Calculation Steps

1. Record Friday's closing price at 5:00 PM ET (or 4:15 PM for RTH-only analysis)
2. Record Sunday's opening price at 6:00 PM ET
3. The gap range = `[min(Friday_close, Sunday_open), max(Friday_close, Sunday_open)]`
4. Mark the **50% level** (Consequent Encroachment) = `(Friday_close + Sunday_open) / 2`
5. The gap direction = bullish if Sunday open > Friday close, bearish if Sunday open < Friday close

### For Forex Markets

The calculation is the same conceptually but uses the forex market close at **4:59 PM EST Friday** and the forex market open at **6:00 PM EST Sunday** (when Australian/Asian markets begin).

---

## 3. What Is NDOG (New Day Opening Gap)

The **New Day Opening Gap (NDOG)** applies the same concept at the **daily** level. It is the gap between one session's closing price and the next session's opening price.

### For CME Futures

| Boundary | Time (ET) | Notes |
|---|---|---|
| **Session Close** | 5:00 PM ET | End of daily Globex session |
| **Session Open** | 6:00 PM ET | Start of next Globex session |

The NDOG forms during the **daily 60-minute maintenance window** (5:00 PM - 6:00 PM ET), Monday through Thursday. It is typically much smaller than the NWOG because the closure period is only 1 hour versus approximately 43 hours for the weekend.

### Key Properties

- NDOGs form every trading day (Mon-Thu night), while NWOGs form only once per week (Friday-Sunday).
- Both act as **fair value gaps** / liquidity voids.
- Both use the **50% level (Consequent Encroachment)** as the key reactive level.
- NDOGs are more useful for **intraday** and **swing** traders; NWOGs for **weekly** positioning.

---

## 4. NWOG vs NDOG -- Key Differences

| Attribute | NWOG | NDOG |
|---|---|---|
| **Frequency** | Once per week | Once per day (Mon-Thu) |
| **Gap Duration** | ~43 hours (Fri 5pm - Sun 6pm) | ~1 hour (5pm - 6pm daily) |
| **Typical Gap Size** | Larger (weekend news accumulation) | Smaller (1-hour maintenance) |
| **Gap Fill Behavior** | Often fills within the week, but not guaranteed | Frequently fills within the session |
| **Trading Horizon** | Weekly bias, multi-day trades | Intraday, next-day trades |
| **Sensitivity to News** | High (weekend geopolitical, economic events) | Lower (overnight only) |
| **Persistence** | Active until filled (can persist for weeks) | Usually resolved within 1-2 days |
| **ICT Usage** | Weekly bias, draw on liquidity | Daily bias, intraday entries |

Both share the same core principle: the gap is a **liquidity void** that price tends to revisit for **fair value rebalancing**.

---

## 5. Core ICT Rules for Trading NWOG

### Rule 1: Identify the Gap on the Weekly/Daily Chart

Mark Friday 5:00 PM close and Sunday 6:00 PM open. Draw a box/rectangle spanning the full gap range. This is the NWOG zone.

### Rule 2: Mark Consequent Encroachment (50% Level)

The **50% midpoint** of the NWOG is called the **Consequent Encroachment (CE)** and is considered the **most reactive level** within the gap. Use Fibonacci retracement (0, 0.5, 1.0) from gap low to gap high to mark it precisely.

### Rule 3: Determine Gap Direction and Bias

- **Bullish NWOG (gap up)**: Price opened above Friday's close. If price comes back down to the NWOG zone, it may act as **support**. Look for long setups on retests of the gap.
- **Bearish NWOG (gap down)**: Price opened below Friday's close. If price rallies back up to the NWOG zone, it may act as **resistance**. Look for short setups on retests of the gap.

### Rule 4: Use Multi-Timeframe Confirmation

ICT recommends a **top-down approach**:
1. **Weekly chart**: Identify the NWOG and determine the overall weekly bias
2. **Daily / 4-Hour chart**: Confirm price movement toward or away from NWOG; identify nearby order blocks
3. **1-Hour / 15-Minute chart**: Pinpoint entry triggers (market structure shifts, FVGs, order blocks)

### Rule 5: NWOG as Draw on Liquidity

Price is magnetically drawn toward unfilled NWOGs. Old NWOGs from prior weeks remain valid targets until filled. When price approaches an NWOG, watch for:
- A test of the CE (50% level) for a reaction
- A full fill (price traverses the entire gap)
- A rejection at the gap boundary

### Rule 6: Align with Higher Timeframe Bias

NWOG is **not a standalone signal**. It works best when aligned with:
- Daily or weekly trend direction
- PD Array (Premium/Discount zones)
- Nearby order blocks and liquidity pools
- Previous week high/low sweeps

---

## 6. Gap Fill Statistics

### General Futures Gap Fill Data (NQ, 2,791 Trading Days)

From quantitative analysis of NQ futures spanning 2014-2024 (source: TradingStats.net):

| Metric | Value |
|---|---|
| **Overall gap fill rate (100% fill by close)** | **60.3%** |
| **Gaps NOT filled by session close** | 39.7% |

### Fill Rate by Gap Size (Relative to ATR)

| Gap Size | ATR Multiple | Fill Rate |
|---|---|---|
| **Tiny** | < 0.3x ATR | **77.8%** |
| **Small** | 0.3x - 0.7x ATR | **42.0%** |
| **Medium** | 0.7x - 1.2x ATR | **25.6%** |
| **Large** | > 1.2x ATR | **8.2%** |

**Key insight: Gap size is the single strongest predictor of whether a gap will fill.** Tiny gaps fill nearly 4 out of 5 times; large gaps fill less than 1 in 10.

### Fill Rate by Day of Week (NQ)

| Day | Fill Rate | Notes |
|---|---|---|
| **Monday** | **53.9%** | Lowest -- genuine sentiment shifts over the weekend |
| **Tuesday** | **62.8%** | |
| **Wednesday** | **63.5%** | Highest fill rate |
| **Thursday** | **62.4%** | |

**Monday stands out with the lowest gap fill probability**, which is directly relevant to NWOG since Monday is the first full session after the weekly gap forms. This aligns with the ICT view that NWOG fills may take multiple days.

### Drawdown Before Gap Fill (NQ)

How far price moves **against** the gap-fill direction before the gap actually fills:

| Percentile | Adverse Move (NQ points) |
|---|---|
| **Median (50th)** | **44 points** |
| **75th percentile** | **107 points** |
| **90th percentile** | **203 points** |

**1 in 10 gap fade trades will see a 200+ point adverse move on NQ before filling.** This has significant implications for stop placement and position sizing.

### Gap Fill Timing (NQ)

| Time Window | Cumulative Fill Rate |
|---|---|
| First 5-min candle (8:30-8:35 CT) | 34% |
| By 9:00 AM CT | 61% |
| By noon CT | ~52% (of 100% fills) |
| Full session close | 60.3% |
| Afternoon adds only | +8.4 percentage points |

Most gap fills happen in the **first 30-90 minutes** of RTH. If a gap hasn't started filling by noon, the probability drops significantly.

### ES Gap Fill Data

For ES futures: gaps between 0.0-0.19% in size fill at an **89-93% rate** over recent 6-month periods.

### NWOG-Specific Gap Fill Data

**No rigorous academic or quantitative study specifically isolating NWOG (weekly) gap fill rates was found in online sources.** The ICT community states that NWOGs "often" fill, but provides no hard percentages. The general consensus from ICT practitioners is:

- NWOGs tend to fill **within the same week** in ranging/consolidating markets
- In strongly trending markets, NWOGs may persist for **multiple weeks**
- The **50% level (CE)** gets tagged more frequently than full gap fills
- Forex NWOG gaps fill more rapidly than futures NWOG gaps

**This is a gap in the public research -- our own backtesting study should quantify this.**

---

## 7. Entry / Exit Frameworks

### Framework 1: Reversion to Gap (Most Common)

This is the primary ICT approach -- price returns to fill the gap.

**Entry Conditions:**
1. Identify NWOG direction (bullish or bearish gap)
2. Wait for price to **retrace** toward the NWOG zone from outside
3. On the lower timeframe (15m or 5m), look for a **Market Structure Shift (MSS)** confirming reversal direction
4. Enter at or near the **CE (50% level)** of the NWOG
5. Confirmation: Look for a displacement candle, order block, or FVG on the lower TF

**Stop Placement:**
- Beyond the **far side of the NWOG** (opposite side from entry)
- Or below/above the nearest **swing high/low** on the entry timeframe
- Or beyond the nearest **liquidity pool** outside the gap

**Targets:**
- **First target**: The opposite side of the NWOG (full gap fill)
- **Second target**: The next liquidity pool beyond the gap
- **Conservative target**: The CE (50% level) if entering at gap boundary

### Framework 2: Breakout Through Gap

Price breaks out of the NWOG range and continues.

**Entry Conditions:**
1. Price breaks out of the NWOG zone with a **displacement** (strong candle or series of candles)
2. Wait for a **retest** of the broken gap boundary
3. Enter on the retest with confirmation of continuation

**Stop Placement:**
- Inside the NWOG zone (below CE for longs, above CE for shorts)

**Targets:**
- Next significant order block or liquidity pool in the breakout direction

### Framework 3: CE Bounce (50% Reaction Play)

The 50% level alone as a reaction zone.

**Entry Conditions:**
1. Price approaches the CE (50% level) of an unfilled NWOG
2. Look for a reaction (rejection candle, MSS) at the CE level
3. Enter in the direction of the reaction

**Stop Placement:**
- Through the CE level (small buffer beyond 50%)

**Targets:**
- Gap boundary (high or low of NWOG)
- Extended: next weekly/daily level

### Framework 4: Multi-Week NWOG Stacking

When multiple NWOGs from consecutive weeks stack up in the same area:

1. Identify overlapping or adjacent NWOGs from prior weeks
2. The **Event Horizon** -- midpoint between two consecutive NWOGs -- becomes a key level
3. Trade toward the NWOG cluster as a high-probability draw on liquidity
4. These zones act as stronger support/resistance due to layered institutional interest

---

## 8. Common Pitfalls -- When NWOG Gaps Do NOT Fill

### Pitfall 1: Assuming All Gaps Must Fill

> "Contrary to common belief, NWOG has no structural obligation to be fully filled or to return to its origin zone. In many cases, the gap merely acts as a liquidity layer, and after being tapped, the market chooses a different path."
> -- TradingFinder.com

Some gaps represent a genuine **repricing** of the market. Breakaway gaps in particular rarely fill.

### Pitfall 2: Ignoring the Trend

- In a **strong trend**, gaps in the direction of the trend are less likely to fill (runaway/continuation gaps)
- In **consolidating/ranging** markets, gaps fill more frequently
- A weekly NWOG gap aligned with the dominant trend may act as a continuation gap, not a fill-me gap

### Pitfall 3: Ignoring Gap Size

The data is clear: **large gaps (> 1.2x ATR) fill only 8.2% of the time on NQ.** Treating a large NWOG the same as a small one is a recipe for losses. Gap size must be factored into the trading decision.

### Pitfall 4: Fading Monday Gaps Blindly

Monday has the **lowest gap fill rate (53.9%)** of any weekday. Weekend gaps carry genuine sentiment shifts that may not reverse. Fading a Monday gap without additional confirmation is a coin flip at best.

### Pitfall 5: Insufficient Stop Width

The **median adverse excursion before fill is 44 NQ points**, with 10% of trades seeing 200+ points of heat. A tight stop on a gap fade will get stopped out frequently before the fill occurs.

### Pitfall 6: Neglecting Volume Confirmation

Gaps on **low volume** are less reliable. High relative volume indicates institutional participation and increases the probability of a meaningful reaction at the gap.

### Pitfall 7: Not Classifying the Gap Type

Not all gaps are the same:
- **Breakaway gaps** (price separates from a consolidation): Rarely fill quickly, often persist for weeks or months
- **Runaway/Continuation gaps**: Occur mid-trend, signal acceleration -- don't fight these
- **Exhaustion gaps**: Occur at the end of a trend, often fill quickly as the trend reverses
- **Common gaps**: Small, routine gaps that fill frequently -- most NWOGs fall in this category

The NWOG itself doesn't tell you which type of gap it is. Context (trend, prior week's range, volume, news) determines the gap type.

### Pitfall 8: Over-Leveraging

Gap trades are inherently volatile. The 200+ point drawdown at the 90th percentile on NQ means a gap fade trade can easily move against you significantly before (if ever) filling. Position sizing must account for this.

---

## 9. NWOG Relationship to Other ICT Concepts

### Fair Value Gaps (FVG)

The NWOG **is** a fair value gap -- specifically a weekly-level FVG formed by the weekend closure. It shares all properties of FVGs:
- Price tends to retrace to fill the imbalance
- The 50% level (Consequent Encroachment) is the most reactive
- Unfilled FVGs remain active draw-on-liquidity targets

### Order Blocks

Order blocks near or within an NWOG create **confluence**:
- An order block at the boundary of an NWOG strengthens that level as support/resistance
- When price approaches an NWOG and encounters an order block, the probability of a reaction increases
- After a liquidity sweep, the nearest order block within the NWOG zone becomes the optimal entry

### Liquidity Sweeps

The ICT model posits that institutions engineer liquidity sweeps to:
1. **Sweep stops** below/above key levels (previous week high/low, NWOG boundaries)
2. **Fill institutional orders** at favorable prices
3. **Then reverse** toward the intended direction

An NWOG gap fill may begin only **after** a liquidity sweep of a nearby high/low. The sweep provides the liquidity for institutional orders, and the subsequent reversal drives price through the NWOG.

### Premium / Discount Zones

The NWOG fits within the ICT **PD Array** (Premium/Discount Array):
- If price is trading **above** the NWOG (premium territory relative to the gap), look for shorts back into the gap
- If price is trading **below** the NWOG (discount territory), look for longs back into the gap
- The CE (50%) divides the NWOG itself into premium and discount halves

### Breaker Blocks

When an NWOG fails to hold as support/resistance and price breaks through it entirely, the broken level becomes a **breaker block** -- it flips polarity from support to resistance (or vice versa) and can be used for entries on retests.

### Event Horizon (EHPDA)

The **Event Horizon** is the midpoint between two consecutive NWOGs. It acts as a **barrier zone** that influences which NWOG price is drawn toward:
- If price is above the Event Horizon, it tends to be drawn toward the higher NWOG
- If price is below, it tends toward the lower NWOG
- The Event Horizon itself can act as support/resistance

### Killzones

ICT defines specific high-probability trading windows (killzones):
- **London Open (2:00-5:00 AM ET)**: First high-volume session after the Sunday gap opens
- **New York Open (8:30-11:00 AM ET)**: Highest probability gap fill window
- **London Close (10:00 AM-12:00 PM ET)**: Overlap window with reversals

NWOG setups triggered during killzones have higher probability because institutional volume is concentrated in these windows.

---

## 10. NWOG + Market Profile / Auction Theory Integration

While ICT and Dalton Market Profile come from different analytical traditions, the NWOG concept maps naturally to several Auction Market Theory principles.

### NWOG as an Unfair Price / Excess

In Dalton's framework, a gap is a form of **excess** -- price moves that occur outside the normal auction process. The NWOG is excess created by the weekend closure. Auction theory predicts that excess prices tend to be revisited as the market **rotates** to find fair value.

### NWOG and Value Area Gaps

When a weekly gap causes Monday's value area to have **zero overlap** with Friday's value area, it signals strong directional conviction. This is analogous to an NWOG that is large enough to create a complete value area dislocation. These gaps are:
- **Less likely to fill** (breakaway character)
- More likely to represent genuine repricing
- Consistent with our backtest data showing large gaps fill only 8.2% of the time

### NWOG and VPOC/DPOC

The NWOG 50% level (CE) can be viewed as an analogue to the **developing VPOC** -- a fair value reference point that price migrates toward. If the NWOG CE aligns with a prior session's VPOC or the developing POC of the current session, it creates strong confluence.

### NWOG and Opening Type

Monday's open relative to the NWOG maps to Dalton's **opening types**:
- **Open-Drive** through the NWOG: Strong conviction, gap likely a breakaway -- don't fade
- **Open-Test-Drive**: Price tests the NWOG boundary, rejects, then continues -- moderate conviction
- **Open-Rejection-Reverse**: Price opens, tests the NWOG, then reverses back toward fill -- highest probability gap fill setup
- **Open-Auction**: Price auctions around the NWOG boundary -- wait for market structure to develop

### NWOG and Day Type Classification

The NWOG influences the likely **day type** for Monday:
- **Small NWOG + ranging prior week**: Likely a Balance Day or Normal Day -- gap fill probable
- **Large NWOG + trending prior week**: Likely a Trend Day or P-Day -- gap may not fill; price may extend
- **NWOG into prior week's value area**: Higher probability of fill (price returning to accepted value)
- **NWOG beyond prior week's range**: Lower probability of fill (potential breakaway)

### NWOG and 80% Rule

The ICT NWOG fill concept shares DNA with our **80P Rule** strategy:
- Both are based on the principle that price migrates toward fair value
- 80P Rule: If price enters the value area and accepts (2 TPO closes inside), it has an 80% chance of reaching the opposite side
- NWOG: If price enters the gap zone and shows acceptance, it tends to fill to the other side
- The CE (50%) of the NWOG is analogous to the POC within the value area

### NWOG and Initial Balance

If the NWOG overlaps with Monday's developing Initial Balance (IB), it creates a critical confluence zone:
- IB range containing the NWOG boundaries becomes a key decision point
- IB breakout direction tells you whether the gap fill or gap extension is more likely
- This aligns with our existing OR Rev and IB strategies

---

## 11. Implications for Rockit Framework

### Integration Opportunities

Based on this research, here is how NWOG could integrate with the existing Rockit deterministic + strategy pipeline:

#### 11.1. New Deterministic Module: `nwog_analysis.py`

Add to the 38 existing deterministic modules:
- Calculate NWOG for the current week (Friday 5:00 PM close vs Sunday 6:00 PM open)
- Track gap size (absolute points and ATR-relative)
- Classify gap: tiny/small/medium/large
- Calculate CE (50% level)
- Track historical NWOG fill status for prior weeks
- Calculate NDOG for each day
- Identify stacking NWOGs and Event Horizons

#### 11.2. NWOG Strategy: `nwog_gap_fill.py`

A new strategy module that could emit signals:
- **Gap Fill Signal**: When price enters the NWOG zone and shows acceptance (closes within the gap on the 5-min chart), emit a signal targeting the opposite gap boundary
- **CE Bounce Signal**: When price reacts at the CE (50% level), emit a signal in the reaction direction
- **Filter conditions**:
  - Gap size must be "tiny" or "small" (< 0.7x ATR) for gap fill plays
  - Align with daily/weekly trend direction from regime context
  - Require confirmation from at least one existing strategy (OR Rev, 80P, etc.)
  - Reject trades on days with high-impact news at market open
  - VIX regime filter (high VIX = wider gaps, lower fill rates)

#### 11.3. Confluence with Existing Strategies

| Existing Strategy | NWOG Confluence |
|---|---|
| **OR Rev** | If OR reversal aligns with NWOG gap fill direction, both signals confirm each other |
| **80P Rule** | NWOG fill + VA entry acceptance = strong confluence for 80P target |
| **B-Day / Edge Fade** | Balance day classification + small NWOG = high-probability fade setup |
| **Mean Reversion** | NWOG CE as additional mean reversion target |
| **Trend Following** | Large NWOG aligned with trend = don't fade, use as continuation confirmation |

#### 11.4. Regime Context Enhancement

Add NWOG metadata to `regime_context.py`:
- `nwog_size_atr_ratio`: Gap size relative to ATR
- `nwog_direction`: bullish / bearish
- `nwog_filled`: boolean -- has this week's gap been filled yet?
- `nwog_ce_distance`: Current price distance from the CE level
- `nwog_age_days`: How many days since the gap formed (0 = Monday, 1 = Tuesday, etc.)
- `prior_nwog_filled`: Did last week's gap fill?

#### 11.5. Deterministic Snapshot Enhancement

Add to the 5-minute snapshot JSON:
```json
{
  "nwog": {
    "friday_close": 20145.50,
    "sunday_open": 20082.25,
    "gap_size": -63.25,
    "gap_direction": "bearish",
    "gap_size_atr_pct": 0.28,
    "gap_class": "tiny",
    "ce_level": 20113.88,
    "high": 20145.50,
    "low": 20082.25,
    "filled": false,
    "fill_pct": 0.45,
    "prior_week_nwog_filled": true
  },
  "ndog": {
    "prev_close": 20210.75,
    "session_open": 20198.50,
    "gap_size": -12.25,
    "ce_level": 20204.63,
    "filled": true
  }
}
```

#### 11.6. Training Data Enhancement

The NWOG module would enrich training data for the LLM tape reader:
- The LLM can learn to recognize NWOG fill patterns
- CE reaction patterns become part of the evidence loop
- Gap classification (tiny/small/medium/large) informs confidence levels
- "Caution over conviction" principle applies: large unfilled NWOGs are warnings, not trade signals

### Questions for Our Own Backtest Study

Based on the online research gaps, our study should specifically quantify:

1. **Weekly gap fill rate**: What percentage of NQ/ES NWOGs fill within the same week? Within Monday? Within Tuesday?
2. **Fill rate by gap size**: Confirm the ATR-relative classification (tiny/small/medium/large) and fill rates
3. **Which day fills the gap?**: Monday, Tuesday, or later? This was not found in any online source
4. **CE reactivity**: How often does price tag the 50% level? Does it bounce or slice through?
5. **Correlation with day type**: Do Balance Days fill NWOG more often than Trend Days?
6. **Correlation with prior week's range**: Does an NWOG into the prior week's value area fill more than one beyond it?
7. **Correlation with Monday opening type**: Open-Drive vs Open-Rejection-Reverse vs others
8. **London vs NY session**: Does the gap fill during London or NY? (Important for session timing)
9. **Does NWOG fill direction predict the weekly direction?** (Institutional bias signal)
10. **Stacking NWOGs**: When multiple weeks have unfilled NWOGs in the same area, what happens?

---

## 12. Sources

### Primary ICT Sources

- [ICT New Week Opening Gap - NWOG - ICT Trading](https://innercircletrader.net/tutorials/ict-new-week-opening-gap-nwog/) -- Official ICT tutorial on NWOG definition and rules
- [ICT New Day Opening Gap - NDOG - ICT Trading](https://innercircletrader.net/tutorials/ict-new-day-opening-gap-ndog/) -- Official ICT tutorial on NDOG
- [ICT Consequent Encroachment - Mean Threshold](https://innercircletrader.net/tutorials/ict-consequent-encroachment/) -- CE (50% level) explanation
- [ICT PD Array Matrix - Key to Trade Execution](https://innercircletrader.net/tutorials/ict-pd-array-key-to-trade-execution/) -- Premium/Discount zones
- [ICT Breakaway Gap](https://innercircletrader.net/tutorials/ict-breakaway-gap/) -- Gap type classification

### Strategy Guides and Analysis

- [ICT New Week Opening Gap (NWOG): 4 Easy Steps + 2 Examples - Smart Money ICT](https://smartmoneyict.com/ict-new-week-opening-gap-nwog/) -- Step-by-step NWOG trading guide
- [ICT New Week Opening Gap (NWOG) - SMC Gap Trading - WritoFinance](https://www.writofinance.com/ict-new-week-opening-gap-forex/) -- Comprehensive NWOG and SMC integration
- [New Week Opening Gap (NWOG); How to Trade Using NWOG - TradingFinder](https://tradingfinder.com/education/forex/ict-new-week-opening-gap/) -- Multi-timeframe analysis and pitfalls
- [New Day Opening Gap (NDOG) - ICT Trading Concept - WritoFinance](https://www.writofinance.com/new-day-opening-gap-in-forex/) -- NDOG strategy guide
- [NWOG Trading Strategy ICT Liquidity Gap Analysis - Forex Factory](https://www.forexfactory.com/thread/1342928-nwog-trading-strategy-ict-liquidity-gap-analysis-tflab) -- Community discussion and examples
- [Mastering the New Week Opening Gap (NWOG) - Metals Mine / Forex Factory](https://www.metalsmine.com/thread/1345062-mastering-the-new-week-opening-gap-nwog) -- Advanced NWOG analysis
- [ICT NWOG and NDOG for Trading - InvestingBrokers](https://investingbrokers.com/ict-new-week-opening-gap-nwog-and-new-day-opening-gap-ndog-for-trading/) -- Combined NWOG/NDOG guide

### Quantitative Gap Studies

- [Gap Fill Strategy: 2791 Days of NQ Futures Data - TradingStats](https://tradingstats.net/gap-fill-strategy/) -- NQ gap fill rates by size, day of week, drawdown statistics
- [When Do Gaps Fill? ES & NQ Gap Fill Timing Data (5-Min) - TradingStats](https://tradingstats.net/when-do-gaps-fill/) -- Timing analysis of gap fills
- [Gap Fill Probability & Statistics ES/NQ - TradingView Indicator](https://www.tradingview.com/script/32pGGSWx-Gap-Fill-Probability-Statistics-ES-NQ/) -- Real-time gap fill tracking
- [Are Gaps Always Filled? (Statistics Included) - The Robust Trader](https://therobusttrader.com/do-gaps-always-get-filled/) -- Academic perspective on gap fills
- [Gap Trading Strategy (Backtested Examples) - Quantified Strategies](https://www.quantifiedstrategies.com/gap-trading-strategies/) -- Backtested gap strategies
- [Gap Fill Trading Strategies 2025 - Quantified Strategies](https://www.quantifiedstrategies.com/gap-fill-trading-strategies/) -- Gap fill frameworks with statistics
- [Gap Fill Trading Strategy - Edgeful](https://www.edgeful.com/blog/posts/trading-gap-fills) -- Data-driven gap trading

### TradingView Indicators (Pine Script Reference)

- [ICT NWOG/NDOG Gaps - TrueBacktests](https://www.tradingview.com/script/F8miqVDw-ICT-NWOG-NDOG-Gaps/) -- Pine Script indicator with NWOG/NDOG calculation
- [ICT NWOG/NDOG Gaps TradingFinder - TFlab](https://www.tradingview.com/script/EEnbbfQH-ICT-NWOG-NDOG-Gaps-TradingFinder-New-Opening-Gaps/) -- NWOG with 5pm-6pm CME transition logic
- [ICT NWOG/NDOG Source Code - fadi](https://www.tradingview.com/script/XY0niHGg-ICT-NWOG-NDOG-Source-Code-fadi/) -- Open source NWOG/NDOG implementation
- [NWOG & Dynamic Event Horizon - toodegrees](https://www.tradingview.com/script/YPDz5ORF-NWOG-Dynamic-Event-Horizon/) -- Event Horizon calculation between stacked NWOGs
- [ICT NWOG/NDOG & EHPDA - LuxAlgo](https://www.luxalgo.com/library/indicator/ict-nwog-ndog-ehpda/) -- NWOG/NDOG with Event Horizon Price Delivery Algorithm

### Gap Trading Pitfalls and General Theory

- [Gap Trading Strategies - StockCharts ChartSchool](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/gap-trading-strategies) -- Classification of gap types
- [Gap Fill Trading Strategy 2026 Guide - Aron Groups](https://arongroups.co/technical-analyze/gap-fill-trading-strategy/) -- Pitfalls and risk management
- [Gap Trading: Mathematical Approach - Pocket Option](https://pocketoption.com/blog/en/interesting/trading-strategies/gap-trading/) -- Mathematical framework
- [Fair Value Gaps vs Liquidity Voids - FXOpen](https://fxopen.com/blog/en/fair-value-gaps-vs-liquidity-voids-in-trading/) -- FVG relationship

### Market Profile / Auction Theory

- [Value Area Explained: VAH, VAL, and POC - MarketProfile.info](https://marketprofile.info/articles/value-area-explained) -- Value area and POC definitions
- [Market Profile Trading Explained - GrandAlgo](https://grandalgo.com/blog/market-profile-trading-explained) -- TPO charts and day types
- [The Ultimate Guide to Market Profile - EminIMind](https://eminimind.com/the-ultimate-guide-to-market-profile/) -- Comprehensive market profile guide

### CME Session Times

- [CME Group Trading Hours](https://www.cmegroup.com/trading-hours.html) -- Official CME session times
- [Futures Trading Hours 2026: CME & Globex Schedule](https://bullishbears.com/futures-trading-hours/) -- Globex maintenance windows
- [ES & MES Futures Market Hours - QuantVPS](https://www.quantvps.com/blog/es-mes-futures-market-hours) -- Detailed session breakdowns

### Scribd Document

- [Understanding NWOG and NDOG in Trading (2025) - Scribd PDF](https://www.scribd.com/document/883124349/2025-NWOG-NDOG) -- Comprehensive NWOG/NDOG reference document
