# 07 — Augmenting Training: Tape Reading Intelligence

> Whiteboard document. Living brainstorm — edit freely.

## Core Insight

**The LLM is an analyst/tape reader, NOT a trader.**

Strategy signals trigger trades (deterministic engine, 1-min data). The LLM reads the tape
using 5-min snapshots and tells the system what the market is doing and why. Agents
(Advocate/Skeptic) consume the LLM's analysis + strategy signals + historical data to
decide whether to act.

```
┌─────────────────────────────────────────────────────────────┐
│                    SEPARATION OF CONCERNS                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Deterministic Engine (1-min)     LLM Tape Reader (5-min)   │
│  ─────────────────────────────    ──────────────────────     │
│  • Fires strategy signals         • Reads market structure   │
│  • Computes IB/VA/DPOC/CRI        • Interprets WHY           │
│  • Triggers 20P/80P/OR/B-Day      • Context + reasoning      │
│  • Binary: signal ON or OFF        • Nuance + edge cases     │
│                                    • "What to watch for"     │
│           │                                 │                │
│           ▼                                 ▼                │
│  ┌─────────────────────────────────────────────────┐        │
│  │              AGENTS (consume both)               │        │
│  │                                                   │        │
│  │  Advocate: "Signal fired + context supports it"   │        │
│  │  Skeptic:  "Context says this is a trap"          │        │
│  │  Orchestrator: weighs both → act / pass / reduce  │        │
│  └─────────────────────────────────────────────────┘        │
│                         │                                    │
│                         ▼                                    │
│                  Trade Decision                              │
│           (entry / pass / size adjustment)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Part 0: The Tape Reader's Session Decision Tree

**This is how a trader reads the tape throughout the session. The LLM must evaluate these
questions at EVERY 5-min snapshot. This is the core of what we're training.**

### Premarket Briefing (Before 9:30) — Set the Stage

**Goal:** Before the bell rings, the LLM must have a complete situational awareness picture.
This is the foundation everything else builds on. Get this wrong, and the first hour is blind.

```
THE PREMARKET CHECKLIST (run at 09:25 snapshot)
│
├── 1. OVERNIGHT NARRATIVE — What happened while we slept?
│   │
│   ├── Asia Session (19:00-03:00 ET):
│   │   • Bias: Did Asia range higher (bullish) or lower (bearish)?
│   │   • Range: Tight (< 50pts) = no conviction, Wide (> 100pts) = directional
│   │   • Key levels: Asia High/Low become first liquidity targets at RTH
│   │
│   ├── London Session (03:00-09:30 ET):
│   │   • Bias: London typically sets the "true" direction for RTH
│   │   • Did London EXPAND beyond Asia range? (directional intent)
│   │   • Did London REJECT Asia levels? (reversal signal)
│   │   • Post-London direction = RTH acceptance direction 81% of the time
│   │   • Compression: London range / Overnight range ≤ 0.35 = TIGHT
│   │     → Expect explosive opening. Like a coiled spring.
│   │
│   └── Overnight Summary:
│       • "London was bearish, broke below Asia Low, overnight range 95pts"
│       • "London compressed inside Asia (ratio 0.31) — explosive open expected"
│       • "Overnight swept PDH by 12pts then reversed — possible Judas setup"
│
├── 2. GAP CLASSIFICATION — Where are we opening vs prior value?
│   │
│   ├── INSIDE prior VA → Normal open. OR plays are primary.
│   │   80P unlikely (no gap to fill). Balance/neutral day probable.
│   │
│   ├── ABOVE prior VAH → Gap UP. Three scenarios:
│   │   a. Gap holds + acceptance above → Trend day developing (bullish)
│   │   b. Gap fails + price returns inside VA → 80P Rule setup (bearish target: POC)
│   │   c. Gap stalls at VAH → Rejection, watch for rotation
│   │
│   ├── BELOW prior VAL → Gap DOWN. Mirror of above:
│   │   a. Gap holds + acceptance below → Trend day developing (bearish)
│   │   b. Gap fails + price returns inside VA → 80P Rule setup (bullish target: POC)
│   │   c. Gap stalls at VAL → Rejection, watch for rotation
│   │
│   └── LARGE GAP (200+ pts) — Historical fill rate drops to 36%. Lower 80P confidence.
│       Say: "Large gap. 80P fill rate only 36% historically. Don't assume fill."
│
├── 3. LEVEL HIERARCHY — What are the magnets and traps?
│   │
│   ├── Rank by PROXIMITY to opening price (nearest = most relevant):
│   │   Priority 1: London High/Low (freshest liquidity)
│   │   Priority 2: Asia High/Low (overnight liquidity)
│   │   Priority 3: PDH/PDL (prior session extremes — thick liquidity)
│   │   Priority 4: Prior POC, VAH, VAL (value levels)
│   │   Priority 5: 3-day/5-day composite POC/VAH/VAL (bigger picture)
│   │
│   ├── SWEEP TARGETS: Which levels are close enough to get swept?
│   │   • Within 0.5x ATR of open = high probability of being tested
│   │   • Multiple levels clustered = "liquidity pool" — strong magnet
│   │
│   └── FVG MAP: What unfilled gaps exist from overnight?
│       • Bullish FVGs below = discount zones (buy if price returns)
│       • Bearish FVGs above = premium zones (sell if price reaches)
│       • Large 1H/4H FVGs = stronger magnets than 5m/15m
│
├── 4. PREMARKET DIRECTIONAL SCORE — Which way is the wind blowing?
│   │
│   ├── Directional premarket + bullish CVD = 59% acceptance probability
│   ├── Directional premarket + bearish CVD = 59% acceptance probability (opposite)
│   ├── Ranged premarket + no CVD bias = no edge, wait for open
│   ├── SMT divergence (NQ vs ES/YM) = smart money positioning signal
│   │
│   └── Compression check:
│       • Compression flag ON (london/overnight ≤ 0.35) = EXPLOSIVE OPEN expected
│       • Normal ratio = standard open, follow the drive
│
└── 5. OPENING PLAYBOOK — What to expect based on premarket
    │
    ├── SCENARIO A: Compressed + Inside VA
    │   → OR Reversal is primary. Judas sweep of tight range, then reverse.
    │   → "Tight overnight, inside value. Classic OR Rev setup territory."
    │
    ├── SCENARIO B: Directional London + Gap
    │   → OR Acceptance is primary. Price likely continues London direction.
    │   → "London drove through Asia High. If RTH holds above, acceptance play."
    │
    ├── SCENARIO C: Gap + Return Inside VA
    │   → 80P Rule is primary. Monitor for 30-min candle acceptance.
    │   → "Opened above VAH, now fading back. 80P conditions developing."
    │
    ├── SCENARIO D: Wide Overnight + No Gap
    │   → Balance day probable. Fade IB edges. Wait for structure.
    │   → "Wide overnight range, no gap. Expect rotation. Patience."
    │
    └── SCENARIO E: Extreme Overnight Move + News
        → Trend day or extreme rotation. Wait for IB classification.
        → "170pt overnight move. Either trend continues or exhaustion fade."
```

**Premarket LLM Output Example:**
> "Opening inside prior VA (VAH 25194, VAL 25017). London compressed inside Asia (ratio 0.31) —
> explosive open expected. Nearest levels: London High 25401 (174pts above, sweep target),
> Prior POC 25068 (31pts below, magnet). Asia Low 25265 untested. SMT neutral. No premarket CVD
> bias. Opening playbook: compressed inside VA → OR Reversal territory. First sweep of London
> High or Asia Low will define the direction. Don't chase the open — wait for the sweep and
> reverse confirmation."

---

### Phase 1: The First Hour (9:30 — 10:30)

**This is where the money is made.** OR Reversal alone (64.4% WR, 2.96 PF, +$78K) fires
in this window. OR Acceptance (59.9% WR) also fires here. A good first hour means you
DON'T NEED TO TRADE AFTER 11:00 AM.

**The LLM must be FAST and PRECISE in this window. No vague language. Every observation
must reference exact prices, levels, and timestamps. The opening auction moves 50-200pts
in minutes — the tape reading must keep pace.**

#### Phase 1A: The Opening Range — First 15 Minutes (9:30 — 9:45)

**Goal:** Identify the opening drive, detect sweeps, classify the open. This is the fastest
section — everything matters.

```
9:30 — BELL RINGS
│
├── OPENING DRIVE CLASSIFICATION (first 5 bars = 5 minutes)
│   │
│   ├── DRIVE UP (5 consecutive higher closes or strong bullish candles)
│   │   → Directional intent to the upside
│   │   → Watch: Is it sweeping a level above? Or genuine acceptance?
│   │   → If sweeping London High/PDH → potential Judas swing (OR Rev SHORT)
│   │   → If holding above key level → OR Acceptance LONG developing
│   │
│   ├── DRIVE DOWN (5 consecutive lower closes or strong bearish candles)
│   │   → Directional intent to the downside
│   │   → Watch: Is it sweeping a level below? Or genuine selling?
│   │   → If sweeping London Low/PDL → potential Judas swing (OR Rev LONG)
│   │   → If holding below key level → OR Acceptance SHORT developing
│   │
│   └── ROTATION (mixed candles, no clear direction)
│       → No trade. Wait. "Opening rotation — no directional intent. Stand aside."
│       → This is the HARDEST discipline: doing nothing when the bell rings
│       → Say: "Choppy open. No edge in the noise. Wait for structure."
│
├── SWEEP DETECTION (continuous — every 5-min bar)
│   │
│   ├── WHAT IS A SWEEP?
│   │   • Price extends BEYOND a premarket level (London H/L, Asia H/L, PDH/PDL)
│   │   • Then REVERSES back through OR mid
│   │   • The "fake-out" that traps traders on the wrong side
│   │   • This IS the Judas swing. This IS the OR Reversal trigger.
│   │
│   ├── SWEEP QUALITY ASSESSMENT:
│   │   • Sweep depth: how far past the level? (deeper = more trapped traders = better)
│   │   • Sweep speed: fast spike + reversal vs slow grind past = different meanings
│   │   • Level swept: PDH/PDL (thick liquidity) > London H/L > Asia H/L
│   │   • Multiple levels swept = stronger signal
│   │   • FVG created during sweep = price moved too fast (institutional)
│   │
│   ├── DUAL SWEEP (both sides swept):
│   │   → "Price swept both London High and London Low in first 15 min.
│   │      This is a BOTH session — messy, no clear direction. OR Acceptance
│   │      filter says SKIP (BOTH filter). Wait for IB."
│   │
│   └── NO SWEEP:
│       → If no premarket level swept by 9:45, OR Reversal is unlikely
│       → Shift focus to OR Acceptance (continuation) or wait for IB plays
│
├── REAL-TIME QUESTIONS (every 5-min bar from 9:30-9:45):
│   │
│   ├── 9:35 snapshot:
│   │   • "What is the opening drive? DRIVE_UP / DRIVE_DOWN / ROTATION?"
│   │   • "Has price already swept a level? Which one? By how much?"
│   │   • "Is there a FVG being created? Bullish or bearish?"
│   │   • "CVD: confirming the drive or DIVERGING?" (crucial for reversal)
│   │
│   ├── 9:40 snapshot:
│   │   • "If sweep occurred: is price reversing through OR mid?"
│   │   • "If no sweep: is a level about to be tested?"
│   │   • "OR range forming: what's the OR high/low so far?"
│   │   • "Wick parade: which side has more rejections?"
│   │
│   └── 9:45 snapshot (OR LOCKED IN):
│       • "OR high and OR low are set. Range = X pts."
│       • "Was there a sweep? → OR Reversal setup developing"
│       • "Was there a clean break? → OR Acceptance setup developing"
│       • "Neither? → Wait for EOR or IB classification"
│
└── OR CLASSIFICATION AT 9:45:
    │
    ├── SWEEP + REVERSING → "OR Reversal territory. Sweep of [level] by [X]pts.
    │   Reversing through OR mid. 64.4% WR, 2.96 PF pattern.
    │   Watch for: 50% retest of sweep + CVD divergence confirmation."
    │
    ├── BREAK + HOLDING → "OR Acceptance developing. Price broke [level] and
    │   holding. Need 2x 5-min closes above/below to confirm. NOT a sweep —
    │   this is continuation, not reversal. 59.9% WR, 1.46 PF."
    │
    ├── BOTH SIDES SWEPT → "BOTH session detected. Messy opening. No OR play.
    │   Stand aside. Wait for IB formation at 10:30."
    │
    └── ROTATION / NO CLEAR SIGNAL → "No opening edge. Wait for EOR (10:00)
        or IB (10:30). Patience is the trade."
```

**Phase 1A LLM Output Example:**
> "DRIVE DOWN into open. Price swept London Low 25343 by 6pts at 9:33 (low: 25337).
> Now reversing — 9:40 candle closed above OR mid 25362. Bearish 5-min FVG at 25340-25348
> created during the sweep (institutional speed). CVD DIVERGING: price made new low but CVD
> didn't — classic Judas swing signature. OR Reversal LONG setup developing. Watch for 50%
> retest at 25350 zone (halfway between sweep low 25337 and reversal high 25362). If retest
> holds with bullish CVD tick, this is the entry zone. 64.4% WR, 2.96 PF."

#### Phase 1B: Extended Opening Range (9:45 — 10:00)

**Goal:** Confirm or deny the OR setup. This is the EXECUTION window — the 50% retest and
CVD confirmation happen here. Also the window for OR Acceptance to develop.

```
9:45 — OR IS LOCKED. Now watching for confirmation.
│
├── IF OR REVERSAL DEVELOPING:
│   │
│   ├── 50% RETEST ZONE:
│   │   • Calculate: midpoint between sweep extreme and reversal extreme
│   │   • Buffer: ±0.5 ATR (±~8-12pts on NQ)
│   │   • "Retest zone: 25348-25362. Waiting for price to return here."
│   │
│   ├── CONFIRMATION CHECKLIST:
│   │   □ Price enters 50% retest zone ✓/✗
│   │   □ Price shows reversal (turning away from retest) ✓/✗
│   │   □ CVD divergence or delta confirmation ✓/✗
│   │   □ Risk is 3%-130% of EOR range ✓/✗
│   │   → ALL four = high-quality OR Rev signal
│   │   → Missing CVD = lower quality, still viable
│   │   → Missing retest = NO SIGNAL (don't chase the reversal)
│   │
│   ├── WHAT TO SAY:
│   │   CONFIRMED: "50% retest at 25355 with bullish CVD tick. All confirmations
│   │   met. OR Reversal LONG is the highest-edge pattern we have: 64.4% WR,
│   │   2.96 PF. Risk is [X]pts (Y% of EOR range). Quality: HIGH."
│   │
│   │   DEVELOPING: "Price approaching retest zone but hasn't turned yet. Wait
│   │   for the rejection candle. Don't anticipate — confirm."
│   │
│   │   FAILED: "Price blew through retest zone without reversing. OR Reversal
│   │   thesis dead. The sweep was real, not a fake-out. Reassess for
│   │   OR Acceptance in the opposite direction."
│   │
│   └── TIME PRESSURE:
│       • OR Rev window closes at 10:15
│       • If no retest by 10:00, urgency increases but DON'T FORCE IT
│       • "10:00 and no retest yet. Window closing. If it doesn't come in
│         next 15 min, abandon OR Rev and shift to IB plays."
│
├── IF OR ACCEPTANCE DEVELOPING:
│   │
│   ├── ACCEPTANCE CRITERIA (strict):
│   │   • 2x CONSECUTIVE 5-min closes beyond the reference level
│   │   • NOT just a spike — sustained closes = genuine acceptance
│   │   • Levels: London H/L, Asia H/L, PDH/PDL (in priority order)
│   │
│   ├── TRACKING:
│   │   • "First 5-min close above London High 25401 at 9:40 (close: 25408)"
│   │   • "Second consecutive close above at 9:45 (close: 25415) — ACCEPTED"
│   │   • "Now wait for pullback to acceptance level for retest entry"
│   │
│   ├── PULLBACK RETEST:
│   │   • After acceptance confirmed, price often retests the acceptance level
│   │   • This IS the entry point (limit order at acceptance level ± buffer)
│   │   • "Acceptance confirmed at London High 25401. Watching for pullback to
│   │     25397-25405 zone for retest entry. Risk ~15pts, Target 2R (~30pts)."
│   │
│   └── BOTH FILTER:
│       • If EOR swept levels on BOTH sides → skip OR Acceptance
│       • "Both London High and Low swept in EOR — conflicting signals. Skip."
│
├── IF NOTHING DEVELOPING:
│   │
│   ├── NO SWEEP + NO ACCEPTANCE = ROTATION OPEN
│   │   → "No edge in the opening auction. Price rotated without conviction.
│   │      Waiting for EOR levels (10:00) and IB classification (10:30).
│   │      The best trade right now is NO trade."
│   │
│   └── THIS IS OK. Most sessions don't produce OR Rev signals.
│       The LLM must normalize "no trade" as a valid, disciplined read.
│
└── EOR LEVELS LOCKED AT 10:00:
    • EOR high and EOR low now set (30 bars of data)
    • EOR range = key reference for risk sizing
    • "EOR range: 82pts. This is [narrow/normal/wide] for the EOR window."
    • If sweep happened, depth as % of EOR = quality metric
```

**Phase 1B LLM Output Example (OR Rev confirmed):**
> "OR Reversal LONG CONFIRMED. Sweep of London Low 25343 by 6pts (low 25337). 50% retest
> at 25355 hit at 9:52 — price turned up from 25353 with bullish delta tick. CVD diverging
> from the sweep low (CVD didn't confirm the 25337 low). All 4 confirmations met. EOR range
> 82pts, risk 18pts (22% of EOR — within 3-130% band). Quality: HIGH. Window remains open
> until 10:15. Stop: 2 ATR below entry."

**Phase 1B LLM Output Example (OR Acceptance confirmed):**
> "OR Acceptance LONG confirmed. Two consecutive 5-min closes above London High 25401
> (9:40: 25408, 9:45: 25415). Price held — this is NOT a sweep-and-reverse. DPOC already
> migrating up 8pts. New HVN forming at 25405-25420. OR Acceptance pattern: 59.9% WR,
> 1.46 PF. Pullback to 25401 = retest entry zone. Risk: ~15pts. Target: 2R (~30pts).
> Key distinction: continuation, not reversal."

#### Phase 1C: IB Formation Window (10:00 — 10:30)

**Goal:** IB is being built. Start reading the structure that will define the rest of the day.
This is the transition from OR speed to IB analysis. Still fast, but more deliberate.

```
10:00 — EOR locked. IB forming. Two reading tracks running simultaneously:
│
├── TRACK 1: ACTIVE OR PLAYS (carry forward from Phase 1A/1B)
│   │
│   ├── OR Reversal still open?
│   │   • Window closes at 10:15 (hard cutoff)
│   │   • If retest hasn't happened yet: "10:10 — OR Rev window closing in 5 min.
│   │     Retest zone 25350 not yet reached. If no retest by 10:15, abandon."
│   │   • At 10:15: "OR Rev window CLOSED. No retest materialized. Moving on."
│   │
│   ├── OR Acceptance developing?
│   │   • Can still develop through 10:30 (IB window)
│   │   • IB window acceptance (43.7% WR) > EOR window (40.7%)
│   │   • "Price has time. IB acceptance window is more reliable."
│   │
│   └── 80P Gap Play developing?
│       • If opened outside VA, watching for return inside
│       • First 30-min candle closes at 10:00 — is it inside VA?
│       • "First 30-min candle closed inside VA at 10:00. 80P conditions
│         developing. Need second candle (10:30) for confirmation."
│
├── TRACK 2: IB STRUCTURE FORMING (new analysis)
│   │
│   ├── IB RANGE BUILDING (every 5-min bar adds resolution):
│   │   • 10:05: "IB range so far: 65pts. On pace for [narrow]."
│   │   • 10:10: "IB range 78pts. Still narrow territory (< 0.7x ATR)."
│   │   • 10:15: "IB range 95pts. Normal range developing (0.5x ATR)."
│   │   • 10:20: "IB expanding — 142pts now. Normal-to-wide (0.75x ATR)."
│   │   • 10:25: "IB range 155pts. This will be a [normal] IB classification."
│   │
│   ├── EARLY TPO SHAPE PROXY:
│   │   • Where is volume concentrating in the first 6 periods?
│   │   • b-shape forming (volume at lows) → buyers absorbing → B-Day LONG likely
│   │   • P-shape forming (volume at highs) → sellers absorbing → SHORT fade likely
│   │   • D-shape (even) → neutral, wait for more data
│   │
│   ├── DPOC INITIAL TRAJECTORY:
│   │   • "DPOC starting at 25120 and migrating up 5pts in first 30 min"
│   │   • "DPOC stuck at 25105 — no directional conviction yet"
│   │   • Early DPOC direction often predicts rest-of-day trend
│   │
│   └── WICK PARADE EARLY COUNT:
│       • Track bullish vs bearish wicks in the first 12 bars
│       • 6+ bull wicks in 60 min = strong bullish underlying flow
│       • Divergence from price = hidden signal
│
├── TRACK 3: OPTIONS CALLOUT — Two Hour Trader (9:30 — 11:30)
│   │
│   ├── THE TWO HOUR TRADER FRAMEWORK:
│   │   • Instruments: SPY, QQQ, or SPX options (0-2 DTE)
│   │   • Time window: 9:30-11:30 ET (HARD EXIT at 11:30)
│   │   • Risk: max $400/trade (premium paid = max loss)
│   │   • Target: Scaled exits — 50% at 2R, 25% at 4R, 25% trails
│   │   • Study data: 60-79% WR, up to 6.76 PF (reported)
│   │
│   ├── THREE ENTRY TYPES:
│   │   │
│   │   ├── A. MOMENTUM BREAKOUT:
│   │   │   Trigger: 5-min OR breakout + volume > 20-period avg + VIX < 25
│   │   │   Strike: ATM or slight OTM (0.30-0.45 delta)
│   │   │   → When LLM sees: "OR break with volume confirmation + low VIX"
│   │   │   → LLM says: "Two Hour Trader MOMENTUM setup. OR broke to upside
│   │   │     with 1.8x average volume. VIX at 18. SPY calls or QQQ calls
│   │   │     viable. ATM 0-DTE for max delta capture. Exit by 11:30."
│   │   │
│   │   ├── B. MEAN REVERSION:
│   │   │   Trigger: Price extended 1.5+ ATR from VWAP + RSI > 70 (short) or < 30 (long)
│   │   │   Strike: OTM 0.30 delta
│   │   │   → When LLM sees: RSI extreme + VWAP extension + declining volume
│   │   │   → LLM says: "Two Hour Trader MR setup. Price extended 1.7x ATR
│   │   │     below VWAP, RSI 27. Volume declining on sell-off = exhaustion.
│   │   │     SPY puts may be overpriced (MR). If range-bound conditions
│   │   │     hold, calls targeting VWAP bounce."
│   │   │
│   │   └── C. VWAP BOUNCE:
│   │       Trigger: Price rejects VWAP with wick + pullback to VWAP
│   │       Strike: ATM, 0-2 DTE
│   │       → When LLM sees: Clean VWAP rejection with candle wick
│   │       → LLM says: "Two Hour Trader VWAP bounce. Price pulled back
│   │         to VWAP 25120 and rejected with 8pt lower wick. Trend is
│   │         bullish (DPOC migrating up). SPY/QQQ calls on VWAP hold."
│   │
│   ├── WHEN TO CALL OUT (LLM decision):
│   │   • Only when tape reading ALREADY supports the direction
│   │   • The options play CONFIRMS the futures tape read — it's not separate
│   │   • "Our tape reading says bullish + OR break confirmed → options play aligns"
│   │   • Never call out options into chop/rotation ("No options play in rotation")
│   │
│   ├── RISK RULES THE LLM MUST STATE:
│   │   • Max $400 per trade (premium = max loss, no margin risk)
│   │   • Max 2 losers per day → done ($800 daily max loss)
│   │   • Hard exit at 11:30 regardless of P&L
│   │   • 0-DTE theta decay is ruthless — only enter with conviction
│   │   • VIX > 30 = sit out (IV crush destroys premiums)
│   │
│   └── EXAMPLE LLM OPTIONS CALLOUT:
│       > "Two Hour Trader opportunity. OR Reversal LONG confirmed at 9:52.
│       > Tape reads bullish: swept London Low, CVD diverging, reversing through
│       > OR mid. Futures play active via strategy runner. Options overlay:
│       > SPY calls, ATM 0-DTE, entry on retest. Premium risk capped at $400.
│       > Target: 2R scaled exits. Hard close by 11:30. VIX at 19 — acceptable.
│       > This is a HIGH-CONVICTION overlay — tape + strategy + options aligned."
│
└── 10:25 — FINAL PRE-IB ASSESSMENT:
    │
    ├── "IB about to close. Range: [X]pts ([classification])."
    ├── "OR plays status: [active/confirmed/failed/none]"
    ├── "TPO shape proxy: [b/P/D] — implications for post-IB."
    ├── "DPOC trajectory: [migrating up/down/stable]"
    ├── "CVD summary: [confirming/diverging from price]"
    ├── "Open trades: [none/OR Rev at 25355/OR Accept at 25401]"
    │
    └── TRANSITION TO PHASE 2:
        "IB locks in 5 minutes. Preparing full day type classification.
        Current read: [e.g., Narrow IB with bullish DPOC — watch for 20P
        extension above IBH. If C-period closes above IBH, 70-75%
        continuation probability.]"
```

**Phase 1C LLM Output Example (IB forming + options callout):**
> "10:15 — IB range building: 112pts (0.6x ATR — NARROW). Bullish profile forming
> with b-shape (volume concentrated at lows). DPOC migrating up 9pts since open. OR
> Reversal LONG was confirmed at 9:52 — still active. Early wick parade: 5 bull vs 2
> bear. Strong bullish undertone developing.
>
> Two Hour Trader overlay: momentum breakout type. OR broke to upside with volume 1.6x
> average. VIX 19. SPY/QQQ calls align with bullish tape. 0-DTE ATM. Max $400 premium.
> Exit by 11:30 regardless.
>
> Narrow IB means compression — if IBH breaks at 10:30, expect sustained extension
> (20P territory). B-shape at 10:30 would confirm buyers absorbing. Pre-loading context
> for Phase 2: this looks like 20P or trend day setup, not balance."

#### Phase 1D: IB Close — The Pivot Point (10:30)

**Goal:** IB locks in. This is the SINGLE MOST IMPORTANT moment of the day. The classification
here determines which playbook dominates the rest of the session.

```
10:30 — IB COMPLETE. IBH and IBL are LOCKED.
│
├── INSTANT CLASSIFICATION (no delay — this must be FAST):
│   │
│   ├── IB Range: [X] pts
│   ├── IB ATR Ratio: [X] (narrow < 0.7 / normal 0.7-1.3 / wide 1.3-2.0 / extreme > 2.0)
│   ├── IB vs Prior VA: [inside / outside / spanning]
│   ├── TPO Shape: [b / P / D]
│   ├── DPOC at 10:30: [price] — [migrating up/down/stable]
│   ├── NR4/NR7 flag: [yes/no]
│   │
│   └── ONE-LINE IB VERDICT:
│       Narrow: "85pt IB (0.45x ATR). NARROW. Coiled spring. 20P extension imminent."
│       Normal: "155pt IB (0.82x ATR). NORMAL. All playbooks viable. Read the flow."
│       Wide:   "280pt IB (1.5x ATR). WIDE. Most of the move is done. Fade edges."
│       Extreme:"420pt IB (2.2x ATR). EXTREME. Exhaustion. Rotation to IB mid."
│
├── WHAT ACTIVATES AT 10:30:
│   │
│   ├── ✅ Full day_type_call (classification + evidence + skew + morph_watch)
│   ├── ✅ value_area_play (80P/20P/rotation assessment)
│   ├── ✅ tpo_remarks (full profile interpretation)
│   ├── ✅ All 7 thinking steps active
│   ├── ✅ B-Day / Edge Fade observation (if balance conditions)
│   ├── ✅ 20P observation (if narrow IB with extension)
│   ├── ✅ Trend Following observation (if narrow IB + initiative)
│   │
│   └── The Phase 3 Continuous Evidence Loop BEGINS here
│       (dual bull/bear columns start accumulating)
│
└── THE 10:30 VERDICT — What the LLM delivers:
    │
    ├── Example (Narrow IB, bullish):
    │   "IB: 85pts (0.45x ATR) — NARROW. NR4 detected (tightest in 4 sessions).
    │   b-shape POC at lower third — buyers absorbing. DPOC migrating up 12pts.
    │   Inside prior VA. Compression energy stored. First IB extension will likely
    │   be sustained. Watch: C-period close above IBH 25380 = 70-75% continuation.
    │   Primary playbook: 20P extension LONG. Secondary: Trend day developing if
    │   extension reaches 1.0x IB (85pts above IBH = 25465)."
    │
    ├── Example (Wide IB, balance):
    │   "IB: 280pts (1.5x ATR) — WIDE. Most directional move done. D-shape POC
    │   (centered). DPOC stabilizing at 25120. Inside prior VA. Balance day probable.
    │   Primary playbook: B-Day edge fade. Watch for first touch of IBL — 82% WR
    │   if conditions met (b-shape POC, VWAP > IB mid, 30-min acceptance).
    │   DO NOT expect extension from this wide IB. Fade the edges."
    │
    └── Example (Normal IB, gap down):
        "IB: 155pts (0.82x ATR) — NORMAL. Opened below prior VAL 25017. Price
        returned inside VA — 80P conditions developing. First 30-min candle closed
        inside VA at 10:00. Second candle at 10:30: also inside. 80P CONFIRMED.
        VA depth target: prior POC 25068 (51pts from IBL). Watching 30-min candle
        acceptance quality and TPO fattening zone for confidence."
```

### Phase 2: IB Established (10:30)

**Goal:** Classify the IB range and determine the day's probable structure.

```
10:30 — IB complete (IBH/IBL locked in)
│
├── IB Classification:
│   • Narrow (< 0.7x ATR) → compression, expect breakout (20P territory)
│   • Normal (0.7-1.3x ATR) → standard, any day type possible
│   • Wide (1.3-2.0x ATR) → most move done, balance/rotation likely
│   • Extreme (> 2.0x ATR) → exhaustion, fade extremes back to mid
│
├── Where is IB relative to prior value?
│   • IB INSIDE prior session VA → normal auction, balance/neutral likely
│   • IB OUTSIDE prior session VA → potential trend, 80P, or failed breakout
│   • IB spans across prior VA boundary → look for acceptance direction
│
├── TPO shape at IB close (real-time day type proxy):
│   • b-shape (POC lower third) → buyers absorbing → B-Day LONG likely
│   • P-shape (POC upper third) → sellers absorbing → check for SHORT fade
│   • D-shape (POC center) → neutral, dual-sided auction
│
├── What is the bias?
│   • Deterministic engine gives us bias + confidence
│   • Trend strength: Weak/Moderate/Strong/Super
│   • Do we BUY the pullback (P-structure) and go for IB high retest?
│   • Or do we SELL the rally and go for IB low retest?
│
└── DPOC status:
    • Migrating with price → initiative, trend developing
    • Stabilizing → balance, fade the extremes
    • Against price → contrarian signal, fade has edge
```

### Phase 3: Post-IB Continuous Tape Reading Loop (10:30 — 13:00)

**Goal:** Build a living evidence sheet for both bullish AND bearish scenarios. The LLM
is NOT picking a side — it accumulates evidence and presents both cases. Agents decide.

**CORE PRINCIPLE: CAUTION OVER CONVICTION.** The LLM should never be uber-bullish at the
high or super-bearish at the low. At extremes, the LLM looks for RETRACEMENT STRUCTURE
to get onboard — not chasing. On balance days, it warns against shorting the low and
buying the high. The best tape reader is the one who says "wait for the pullback" instead
of "chase this move."

#### 3A. The C-Period Gate (10:30-11:00)

```
C-Period close (first 30-min candle after IB) — sets the tone:
│
├── ABOVE IBH → 70-75% continuation UP
│   But DON'T chase. Say: "C-period accepted above IBH. Probability favors
│   upside continuation. WAIT for pullback to IBH zone for retracement entry.
│   Chasing here risks buying the high of a balance probe."
│
├── BELOW IBL → 70-75% continuation DOWN
│   But DON'T chase. Say: "C-period closed below IBL. Bearish continuation
│   probable. Look for retracement back toward IBL for entry. Shorting here
│   at the low risks catching a B-Day bounce."
│
└── INSIDE IB → 70-75% reversal to opposite extreme
    Say: "C-period stayed inside IB — balance confirmed. Expect rotation.
    Fade the next IB edge test, especially first touch."
```

#### 3B. Continuous Evidence Loop (runs every 5-min snapshot)

At each snapshot, the LLM builds two evidence columns — **bullish case** and **bearish case**.
This dual-track analysis is what feeds the Advocate and Skeptic agents.

```
┌─────────────────────────────────────────────────────────────────┐
│                    EVIDENCE ACCUMULATION LOOP                    │
│                    (every 5-min snapshot)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  For each snapshot, evaluate ALL of the following and assign     │
│  each observation to BULLISH, BEARISH, or NEUTRAL evidence:     │
│                                                                  │
│  ┌──────────────────┐          ┌──────────────────┐             │
│  │  BULLISH EVIDENCE │          │  BEARISH EVIDENCE │             │
│  │  (Advocate uses)  │          │  (Skeptic uses)   │             │
│  └──────────────────┘          └──────────────────┘             │
│                                                                  │
│  1. PRICE STRUCTURE (ICT)                                       │
│  ────────────────────────                                        │
│  • Higher highs + higher lows?          → BULLISH               │
│  • Lower highs + lower lows?           → BEARISH               │
│  • Structure BREAK (HH then LL)?       → BEARISH SHIFT         │
│  • Structure BREAK (LL then HH)?       → BULLISH SHIFT         │
│  • Clean swings or messy?              → Conviction gauge       │
│  • Are swings getting SHORTER?         → Momentum fading        │
│  • Are swings getting LONGER?          → Momentum building      │
│                                                                  │
│  CAUTION: At the high of a move with shortening swings,         │
│  DON'T say "bullish." Say "momentum fading, look for retrace."  │
│                                                                  │
│  2. VOLUME PROFILE (Auction Theory)                             │
│  ──────────────────────────────────                              │
│  • Price rotating around HVN?          → Acceptance (fair value)│
│  • Price pushing through LVN?          → Initiative (new value) │
│  • New HVN forming at higher levels?   → BULLISH value migration│
│  • New HVN forming at lower levels?    → BEARISH value migration│
│  • HVN/LVN DISTRIBUTION shape:                                  │
│    - Single peak (normal) → balanced, range expected             │
│    - Bimodal (two peaks) → value contested, breakout coming     │
│    - Flat/wide → no consensus, choppy                           │
│  • Volume concentrated at extremes?    → Distribution (topping) │
│  • Volume concentrated at lows?        → Accumulation (bottoming)│
│                                                                  │
│  3. TPO ANALYSIS (Market Profile)                               │
│  ────────────────────────────────                                │
│  a) Acceptance vs Rejection:                                     │
│     • Fattening upper 1/3             → BULLISH acceptance      │
│     • Fattening lower 1/3             → BEARISH acceptance      │
│     • Fattening middle                → NEUTRAL, balanced       │
│     • Fattening OUTSIDE IB            → Day type MORPHING       │
│                                                                  │
│  b) Structural Tells:                                            │
│     • Poor high (weak/effective)      → Unfinished business UP  │
│     • Poor low (weak/effective)       → Unfinished business DOWN│
│     • Single prints above             → REJECTION at high       │
│     • Single prints below             → REJECTION at low        │
│     • Excess (long tail) at high      → STRONG rejection        │
│     • Excess (long tail) at low       → STRONG rejection        │
│                                                                  │
│  c) Profile Shape Evolution:                                     │
│     • b-shape → p-shape               → Bearish morph           │
│     • p-shape → b-shape               → Bullish morph           │
│     • D-shape stable                  → Range day confirmed     │
│     • Shape widening symmetrically    → Balance strengthening   │
│                                                                  │
│  CAUTION: "Upper fattening at 14:00 near session high"          │
│  → DON'T say "uber bullish." Say "acceptance at high BUT late   │
│  in session — chasing risk. If bullish, wait for pullback to    │
│  POC or fattening zone for retracement entry."                  │
│                                                                  │
│  4. DPOC MIGRATION (Developing Point of Control)                │
│  ───────────────────────────────────────────────                  │
│  • Migrating UP with price            → BULLISH (initiative)    │
│  • Migrating DOWN with price          → BEARISH (initiative)    │
│  • STABILIZING (not moving)           → Balance/rotation        │
│  • Migrating AGAINST price            → Contrarian signal       │
│  • Velocity: fast (>10pts/30min)      → Strong conviction       │
│  • Velocity: slow (2-5pts/30min)      → Tentative, could stall │
│  • Velocity: DECELERATING             → Momentum fading         │
│  • Retention < 40% of peak            → EXHAUSTION (skip trade) │
│                                                                  │
│  CAUTION: "DPOC migrating up 30pts but decelerating"            │
│  → DON'T say "bullish." Say "DPOC losing steam — initial drive  │
│  was strong but velocity dropping. If buyers can't sustain,     │
│  expect reversion to DPOC. Wait for re-acceleration or retrace."│
│                                                                  │
│  5. CVD / ORDER FLOW DIVERGENCE                                 │
│  ──────────────────────────────                                  │
│  • Price UP + CVD UP                  → CONFIRMED move          │
│  • Price UP + CVD FLAT/DOWN           → DIVERGENCE (bearish)    │
│  • Price DOWN + CVD DOWN              → CONFIRMED move          │
│  • Price DOWN + CVD FLAT/UP           → DIVERGENCE (bullish)    │
│  • Wick parade: bull > bear by 6+     → Long override (Rule 14) │
│  • Wick parade: bear > bull by 6+     → Short override          │
│                                                                  │
│  CVD divergence is one of the strongest reversal signals:       │
│  "Price making new high but CVD not confirming — sellers are    │
│  absorbing at this level. This rally is running on fumes.       │
│  DO NOT chase long here. Wait for structure break (lower low)   │
│  to confirm reversal."                                          │
│                                                                  │
│  6. ICT / FVG / BPR FRAMEWORK                                  │
│  ────────────────────────────                                    │
│  a) FVG Behavior (5-min and 15-min most actionable):            │
│     • Bullish FVG RESPECTED (price bounces off)                 │
│       → Buyers defending, trend continuation BULLISH            │
│     • Bullish FVG DISRESPECTED (price drives through)           │
│       → Sellers stronger than gap implies → BEARISH             │
│     • Bearish FVG RESPECTED (price rejected from below)         │
│       → Sellers defending, trend continuation BEARISH           │
│     • Bearish FVG DISRESPECTED (price drives up through)        │
│       → Buyers stronger → BULLISH                               │
│     • UNFILLED FVGs = liquidity targets (price gravitates to)   │
│                                                                  │
│  b) BPR (Balanced Price Range):                                  │
│     • BPR HOLDING → range-bound zone, expect rotation           │
│     • BPR FAILED (price breaks through) → directional move      │
│     • New BPR forming → consolidation, breakout pending         │
│     • 5-min BPR = short-term rotation zone                      │
│     • 15-min BPR = significant structural zone                  │
│                                                                  │
│  c) Liquidity Targets (where price is likely drawn to):         │
│     • Unfilled 1H FVG above → upside magnet                    │
│     • Unfilled 4H FVG below → downside magnet                  │
│     • PDH / PDL untested → liquidity resting there              │
│     • Equal highs/lows → engineered liquidity (ICT concept)     │
│     • London/Asia highs/lows untested → sweep targets           │
│                                                                  │
│  7. IB EXTENSION / ACCEPTANCE TRACKING                          │
│  ─────────────────────────────────────                           │
│  • Extension < 20% IB → probe (may fail back)                  │
│  • Extension 20-50% IB → developing (watch acceptance)          │
│  • Extension 50-100% IB → strong (trend day developing)         │
│  • Extension > 100% IB → extreme (don't fade, ride it)          │
│  • 2x 5-min acceptance outside IB → early trend signal          │
│  • 30-min acceptance outside IB → CONFIRMED trend               │
│  • Quick rejection (< 15 min) → false breakout, balance day    │
│                                                                  │
│  CAUTION at extremes:                                            │
│  "Extension is 85% of IB range with single prints left behind   │
│  — this is initiative activity, DO NOT fade. But if you missed  │
│  the move, DON'T chase at the extension extreme. Wait for       │
│  pullback to single-print zone or VWAP for retracement entry."  │
│                                                                  │
│  8. BALANCE DAY TRAP DETECTION                                  │
│  ────────────────────────────                                    │
│  The hardest scenario. Balance days trap traders at the edges.  │
│                                                                  │
│  • Price at IBH after rallying from IBL?                        │
│    → DON'T say "bullish breakout." Say "at resistance after     │
│    full IB traverse. If this is a balance day, this is where    │
│    the fade entry lives, not the breakout."                     │
│                                                                  │
│  • Price at IBL after selling from IBH?                         │
│    → DON'T say "bearish breakdown." Say "at support after full  │
│    IB traverse. B-Day first touch IBL = 82% fade WR. Look for  │
│    30-min acceptance for confirmation."                          │
│                                                                  │
│  • Balance day selling the low:                                  │
│    → WARN: "Price is at IBL 24885 which is the session low.     │
│    Shorting here risks catching the bounce. If balance day is   │
│    confirmed (DPOC stabilizing, D-shape TPO), this is a LONG   │
│    entry zone, not a short."                                    │
│                                                                  │
│  • Balance day buying the high:                                  │
│    → WARN: "Price is at IBH 25356 which is the session high.   │
│    Buying here risks catching the rejection. If balance, this   │
│    is a fade zone. Wait for clear IB extension acceptance."     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 3C. Evidence Summary Format (What the LLM Outputs)

At each snapshot, the tape reading should produce evidence that looks like:

```json
{
  "evidence_bull": [
    "HH+HL sequence since 10:30 — 3 clean swings, structure intact",
    "DPOC migrating up 18pts, velocity 8pts/30min — moderate initiative",
    "15-min bullish FVG at 25309-25318 RESPECTED twice — buyers defending",
    "Upper-third fattening — acceptance developing at highs"
  ],
  "evidence_bear": [
    "CVD DIVERGENCE — price at new high but CVD flat since 11:00",
    "DPOC velocity decelerating (was 12, now 4pts/30min) — momentum fading",
    "Approaching 1H bearish FVG at 25380-25395 — likely resistance",
    "Swing length shortening (45pts → 30pts → 18pts) — rally losing steam"
  ],
  "net_read": "Bullish structure intact but MOMENTUM FADING. DO NOT chase long at 25370. If bullish thesis holds, wait for retrace to DPOC 25320 or 15-min FVG zone 25309-25318 for retracement entry. If CVD divergence resolves with new CVD high, trend resumes. If price breaks below 25300 (last HL), bullish structure invalidated.",
  "trap_warning": "At session high with fading momentum — this is where balance day longs get trapped. Confirm IB extension acceptance (30-min close above IBH) before going long here."
}
```

**This is what makes the tape reader useful: it doesn't just say "bullish" — it says
"bullish BUT fading, here's where to get on board safely, and here's what kills it."**

#### 3D. Retracement Entry Framework

The LLM should ALWAYS recommend retracement structure over chasing:

```
WRONG (chasing):
  "Strong bullish move, price at 25370, buy now."

RIGHT (retracement):
  "Bullish structure confirmed (HH+HL). Current price 25370 is at the extension.
  Optimal retracement levels for long entry:
  1. IBH 25356 (acceptance level — if it holds as support)
  2. DPOC 25320 (developing fair value)
  3. 15-min FVG 25309-25318 (discount zone, confluence with prior HVN)
  Wait for structure to pull back and hold one of these levels.
  Confirmation: higher low forms above the retracement level."

WRONG (fading at edge on balance day):
  "Price at IBL, bearish momentum, short here."

RIGHT (balance day awareness):
  "Price at IBL 24885 after selling from IBH. If DPOC is stabilizing and
  TPO shows D-shape, this is likely a balance day — IBL is the BUY zone,
  not the sell zone. First touch = 82% WR for B-Day LONG. Look for 30-min
  acceptance close above IBL for confirmation. ONLY short if IB extension
  ACCEPTS below IBL (30-min close below)."
```

#### 3E. CVD Deep Read (Price/Volume Divergence)

CVD is the key "lie detector" for price action. The LLM should call out divergences
explicitly as they're the strongest evidence for impending reversals.

```
CVD DIVERGENCE PATTERNS:

1. BEARISH DIVERGENCE (most common trap):
   Price: making new highs (HH)
   CVD: flat or declining
   → "Price is rising but buying pressure is NOT increasing. Passive sellers
   absorbing at this level. This move is not sustainable. Look for:
   - Structure break (lower low) to confirm reversal
   - Bearish wick parade increase (>6 in 60min)
   - FVG disrespect (bullish FVG driven through from above)"

2. BULLISH DIVERGENCE:
   Price: making new lows (LL)
   CVD: flat or rising
   → "Price dropping but selling pressure is NOT increasing. Passive buyers
   absorbing. The sell-off is losing conviction. Look for:
   - Structure break (higher high) to confirm reversal
   - Bullish wick parade increase (>6 in 60min)
   - Bearish FVG disrespect (driven through from below)"

3. CONFIRMED TREND (no divergence):
   Price UP + CVD UP → "Move confirmed by order flow. Trend is genuine."
   Price DOWN + CVD DOWN → "Selling confirmed. Don't buy the dip yet."

4. EXHAUSTION DIVERGENCE (advanced):
   Price: making new highs with DECREASING volume per swing
   CVD: positive but with diminishing increments
   → "Each new high requires less volume = thinner buying. This is late-stage
   momentum. The next pullback may not recover. Tighten stops, don't add."
```

### Phase 4: Afternoon Session (13:00 — 15:55)

**Goal:** No new entries for most strategies. Manage existing positions. Read the close.

```
After 13:00:
│
├── NO new entries for: 80P, B-Day, Edge Fade (strategy cutoff)
├── Trend following may still be active if trend is strong
├── Mean reversion window: 13:00-15:00 (if range-bound conditions)
│
├── What is the close telling us?
│   • Closing in upper 1/3 of range → bullish for next session
│   • Closing in lower 1/3 → bearish
│   • Closing at POC → balanced, no edge carry-over
│   • Closing outside IB → extended move, watch for gap implications tomorrow
│
└── Post-session review prep:
    • Final day type classification
    • Was the morning thesis correct?
    • What invalidation conditions were hit?
    • DuckDB: write session summary for next day's context
```

### What the LLM CONSTANTLY Evaluates (Every 5-Min Snapshot)

These questions build the dual evidence columns (bull/bear) at EVERY snapshot:

**PRICE STRUCTURE (ICT)**
| Question | Data Source | Bullish | Bearish |
|----------|-----------|---------|---------|
| HH/HL or LH/LL? | swing detection | "HH+HL since 10:30 — structure intact" | "LL+LH — downtrend confirmed" |
| Structure break? | swing detection | "LL then HH — bullish shift" | "HH then LL — bearish shift" |
| Swing length trend? | swing detection | "Swings lengthening — momentum building" | "Swings shortening — momentum fading, DON'T chase" |
| Are we at an extreme? | price vs IB/VA | "At IBL with fading selling — look for long retrace" | "At IBH with fading buying — look for short retrace" |

**VOLUME PROFILE (Auction Theory)**
| Question | Data Source | Bullish | Bearish |
|----------|-----------|---------|---------|
| HVN/LVN rotation? | `volume_profile` | "New HVN forming above IB mid — value migrating up" | "New HVN forming below — value migrating down" |
| Volume distribution? | `volume_profile` | "Accumulation at lows (high vol at bottom)" | "Distribution at highs (high vol at top)" |
| Pushing through LVN? | `volume_profile` | "Broke up through LVN 25104 — initiative" | "Broke down through LVN — initiative selling" |
| Profile shape? | `volume_profile` | "Bimodal — contested, breakout pending" | "Single peak — balanced, range expected" |

**TPO ANALYSIS (Market Profile)**
| Question | Data Source | Bullish | Bearish |
|----------|-----------|---------|---------|
| Fattening zone? | `tpo_profile.fattening_zone` | "Upper-third = acceptance at highs" | "Lower-third = acceptance at lows" |
| Poor high/low? | `tpo_profile` | "Poor high — unfinished, likely re-test UP" | "Poor low — unfinished, re-test DOWN" |
| Single prints? | `tpo_profile` | "Below = initiative buying, rejection of lows" | "Above = initiative selling, rejection of highs" |
| Profile shape? | `tpo_profile.tpo_shape` | "b→P morph = bullish shift" | "P→b morph = bearish shift" |
| Acceptance outside IB? | `balance_classification` | "30-min close above IBH = confirmed extension" | "30-min close below IBL = confirmed" |

**DPOC + ORDER FLOW**
| Question | Data Source | Bullish | Bearish |
|----------|-----------|---------|---------|
| DPOC direction? | `dpoc_migration` | "Migrating up — initiative buying" | "Migrating down — initiative selling" |
| DPOC velocity? | `dpoc_migration` | "Accelerating — conviction building" | "Decelerating — momentum fading, DON'T chase" |
| DPOC retention? | `dpoc_migration` | "High retention — buyers holding ground" | "<40% retention — EXHAUSTION, skip trade" |
| CVD vs price? | `wick_parade` / CVD | "Price UP + CVD UP = confirmed" | "Price UP + CVD FLAT = DIVERGENCE — rally on fumes" |
| Wick parade? | `wick_parade` | "Bull > bear by 6+ = long override" | "Bear > bull by 6+ = short override" |

**ICT / FVG / BPR**
| Question | Data Source | Bullish | Bearish |
|----------|-----------|---------|---------|
| FVG respected? | `fvg_detection` | "Bullish FVG held — buyers defending" | "Bearish FVG held — sellers defending" |
| FVG disrespected? | `fvg_detection` | "Bearish FVG broken UP — buyers dominate" | "Bullish FVG broken DOWN — sellers dominate" |
| BPR status? | `fvg_detection` BPR | "BPR break to upside — directional" | "BPR break to downside" |
| Liquidity targets? | FVG + levels | "Unfilled 1H FVG above = magnet UP" | "Unfilled 4H FVG below = magnet DOWN" |
| PDH/PDL tested? | `premarket` levels | "PDH untested = liquidity above" | "PDL untested = liquidity below" |

**BALANCE DAY TRAP CHECK**
| Situation | WRONG Response | RIGHT Response |
|-----------|---------------|---------------|
| Price at IBH after rally | "Bullish breakout!" | "At resistance. If balance, this is fade zone. Confirm extension acceptance first." |
| Price at IBL after selloff | "Bearish breakdown!" | "At support. B-Day first touch = 82% WR LONG. Look for 30-min acceptance." |
| New high with CVD divergence | "Strong bullish!" | "Momentum fading, CVD not confirming. Wait for retrace. DON'T chase." |
| New low with CVD divergence | "Strong bearish!" | "Selling losing conviction. Look for structure break (HH) to go long." |

### Missing Deterministic Data for This Decision Tree

| What LLM Needs | Currently Available? | Gap |
|----------------|---------------------|-----|
| Higher high / higher low tracking | **NO** | **ADD**: swing point detection, HH/HL/LL/LH sequence |
| FVG respect/disrespect classification | **NO** — FVGs listed but not tracked | **ADD**: was each FVG tested? Result: respected/disrespected/untested |
| BPR status (holding/failing/balanced) | **NO** — BPRs listed but static | **ADD**: BPR test result tracking |
| HVN/LVN as profile distribution | **PARTIAL** — top 3 nodes only | **ENRICH**: full volume distribution curve, rotation zone identification |
| IB edge touch count | **NO** | **ADD**: touch_count_ibh, touch_count_ibl, first_touch_time (critical for B-Day 82% vs 20% edge) |
| C-Period close location | **NO** — can be derived from time + price | **ADD**: pre-compute c_period_close_vs_ib |
| Price structure (HH/HL/LH/LL) | **NO** | **ADD**: swing detection + structure classification |
| 5-day composite VA (not just 1-day) | **YES** — `volume_profile.previous_5_days` | Good |
| Poor high / poor low detection | **YES** — `tpo_profile.poor_high/poor_low` | Good but enhance with effective_poor flags |

---

## Part 1: What the LLM Should Be Great At

### 1.1 Tape Reading Skills (the LLM's core competency)

The LLM must be trained to read and interpret:

| Domain | What It Reads | What It Says |
|--------|--------------|-------------|
| **ICT** | FVGs (5m/15m/1h/90m/4h), BPRs, sweeps, Judas swings | "15-min bullish FVG at 25309-25318 from London session still unfilled — discount zone if price returns" |
| **Dalton Market Profile** | Day type, IB range, extensions, responsive vs initiative | "Extreme IB (471pts) = responsive two-sided. Not a trend day. Expect mean reversion to IB mid" |
| **TPO** | Shape, fattening, single prints, poor highs/lows, naked levels | "B-shape with upper rejection + lower fattening = buyers absorbing at lows. Prior POC 25068 still naked — magnet" |
| **Acceptance/Rejection** | Price vs IB, price vs VA, TPO prints, DPOC acceptance | "Price accepted below prior VAL for 3 TPO periods — this is genuine value migration, not a fake-out" |
| **Volume Profile** | HVN/LVN, POC, VA, multi-day composite | "Current session HVN at 25259 aligns with 3-day composite POC 25016 — strong confluence zone" |
| **DPOC Migration** | Regime, velocity, net migration, stall points | "DPOC migrating up 12pts/30min but decelerating — momentum fading, watch for stall at 25150" |
| **Overnight/Premarket** | Asia/London ranges, overnight sentiment, compression | "London sold into Asia lows. Overnight range 73pts compressed (0.8x prior day). Expect expansion at RTH open" |
| **CRI** | Terrain, traps, reclaim quality, permission | "CRI PROBE_ONLY: terrain A2, bear trap detected, hesitant reclaim. Size down to 1 MNQ" |

### 1.2 What the LLM Should NOT Do

- Generate specific entry/stop/target prices (engine does this)
- Override deterministic day_type or bias classification
- Make trading decisions (agents do this)
- Compute anything — only interpret pre-computed data

---

## Part 2: Premarket / Overnight Data Assessment

### 2.1 What We Have Now

```
premarket:
  ├── asia_high / asia_low                     ✅ Session boundaries
  ├── london_high / london_low / london_range  ✅ Session boundaries
  ├── overnight_high / overnight_low / range   ✅ Full Globex range
  ├── previous_day_high / previous_day_low     ✅ Prior session
  ├── compression_flag / compression_ratio     ✅ Expansion/compression signal
  └── smt_preopen                              ✅ Smart Money divergence

FVGs (premarket):
  ├── 5min_fvg   ✅ (has timestamps in Globex hours)
  ├── 15min_fvg  ✅
  ├── 1h_fvg     ✅
  ├── 90min_fvg  ✅
  └── 4h_fvg     ✅

volume_profile:
  ├── previous_day (POC/VAH/VAL/HVN/LVN)      ✅
  ├── previous_3_days composite                 ✅
  └── previous_5_days composite                 ✅

market_structure:
  └── prior_va_analysis (gap_status, 80P setup, OR context)  ✅
```

### 2.2 What We're Missing (Gaps)

| Missing Data | Why It Matters | Priority |
|-------------|---------------|----------|
| **Asia/London session bias** (bullish/bearish/range) | "London drove price to ONH then rejected" vs "London ranged" tells you opening drive direction | HIGH |
| **Overnight VWAP** | Where is overnight fair value? If RTH opens below Globex VWAP = sellers in control | MEDIUM |
| **Overnight volume distribution** | Was volume concentrated at highs (distribution) or lows (accumulation)? | MEDIUM |
| **Pre-RTH delta** (buy vs sell volume) | Net overnight order flow direction | MEDIUM |
| **Key level tests overnight** | Did price test/reject prior day POC, VAH, VAL during Globex? | HIGH |
| **Asia/London range classification** | Tight/Normal/Wide vs recent sessions → expansion probability | LOW |
| **Globex sweep of prior day levels** | If London swept prior day high and reversed = possible Judas swing | HIGH |

### 2.3 Decision: Do We Need 30-Min Overnight Slices?

**Probably not for V1.** Here's why:

The LLM doesn't need tick-by-tick overnight data. It needs a **narrative summary** of what happened overnight. We can derive this from existing data:

```python
# Overnight narrative the LLM can reason about (derivable from current premarket data):
overnight_narrative = {
    "asia_bias": "bullish" if asia_high > london_low else "bearish",  # simplified
    "london_bias": "bearish" if london_high < overnight_high else "bullish",
    "overnight_sweep": "prior_day_high" if overnight_high > previous_day_high else "none",
    "compression": "tight" if compression_ratio < 0.5 else "normal",
    "opening_context": "above_value" | "inside_value" | "below_value",
}
```

**However**, if we want the LLM to understand intraday-style overnight flow (DPOC, TPO, acceptance), then yes, 30-min Globex slices would help. But that's Phase 2.

**Recommendation for V1:**
- Add 3-4 derived fields to the `premarket` module (asia_bias, london_bias, overnight_sweep, key_level_tests)
- Train the LLM to reason about these
- Defer 30-min overnight slices to V2

---

## Part 3: Reworking Strategy Assessment → Tape Observations

### 3.1 Current Problem

The current `strategy_assessment` field lists all 7 strategies with "take this trade" language.
This is wrong — the LLM is the analyst, not the trader.

### 3.2 New Approach: Observation-Based

Instead of: `"eighty_percent": "80P triggered. Entry at 25100, stop at 25200, target 24950"`

Write: `"We're trading outside previous session VA to the downside. Price opened below VAL 24861.75 and has been accepted for 3 TPO periods. If 80P Rule conditions develop (30-min candle acceptance), the VA depth offers a clean target zone. Watch for rejection at prior POC 25068 as first sign of failure."`

### 3.3 Winning Strategies → Tape Observations

Only train on profitable strategies. Map each to the tape-reading observation it produces:

#### Opening Range Reversal (64.4% WR, 2.96 PF)
**What the LLM observes:**
- Did price sweep a premarket level (Asia/London high or low)?
- Is there a Judas swing (drive one direction then reverse)?
- Where is price relative to OR mid?
- Any FVG created during the sweep?
- CVD divergence during the sweep?

**Example output:**
> "Price swept London High 25401 by 8pts in A-period, now reversing through OR mid 25340.
> Bearish 15-min FVG at 25356-25367 created during the sweep. This is textbook OR Reversal
> setup territory — sweeps followed by reversal through OR mid are the highest-edge pattern
> we track (64.4% WR, 2.96 PF). Watch for confirmation: sustained trade below OR mid with
> rising bearish wick parade count."

#### Opening Range Acceptance (59.9% WR, 1.46 PF / Study: 55.4% WR, 1.87 PF)
**How it works (from strategy):**
- Price BREAKS a key level at the open and HOLDS — not a fake sweep
- Opposite of OR Reversal: enters continuation AT the acceptance level on retest
- Acceptance = 2x consecutive 5-min closes beyond the level
- Entry = limit order at acceptance level on pullback retest
- Levels monitored: London High/Low, Asia High/Low, PDH/PDL
- Filter: skip BOTH sessions (sweep on both sides = no clear direction)
- Risk: ~15pts (0.5x ATR buffer), Target: 2R (~30pts)

**What the LLM observes:**
- Did price break and HOLD a key premarket level? (not a sweep-and-reverse)
- 2x consecutive 5-min closes beyond the level = acceptance confirmed?
- Volume confirming (HVN forming at acceptance zone)?
- DPOC migrating toward acceptance direction?
- Is this a clean one-directional drive or a messy BOTH session?
- Pullback to acceptance level = retest opportunity?

**Example output:**
> "Price broke above London High 25401 at 09:38 and held — two consecutive 5-min closes
> above (25408, 25415). This is acceptance, not a sweep. DPOC migrating up 8pts since open.
> Volume concentrating at 25405-25420 (new HVN forming). Pullback toward 25401 would be a
> retest of the acceptance level — OR Acceptance pattern (59.9% WR, 1.46 PF). Key
> distinction from OR Rev: price held the level instead of reversing through it. This is
> continuation, not reversal."

**Invalidation:**
> "Price drops back below London High 25401 and closes 2x below it = acceptance failed,
> potential reversal setup instead."

#### 80P Rule (42.3% WR, 1.74 PF)
**What the LLM observes:**
- Where did we open relative to prior VA?
- Has price been accepted back inside VA?
- 30-min candle acceptance confirmation?
- VA width sufficient (≥25pts)?
- TPO fattening zone confirming?

**Example output:**
> "Opened above prior VAH 25194, now trading back inside VA at 25150. First 30-min
> candle closed inside VA — watching for second candle confirmation. Prior VA width
> 177pts provides clean target depth. TPO fattening zone at VAH suggests acceptance
> developing. If 30-min acceptance confirms, the 80P read is: value migration back
> toward POC 25068."

#### 20P IB Extension
**What the LLM observes:**
- Is IB narrow (high breakout probability)?
- Which side is extending?
- Volume supporting the extension?
- Single prints being left behind (initiative)?
- DPOC following the extension?

**Example output:**
> "Narrow IB 85pts (0.45x ATR). Extension developing above IBH — currently 12pts above.
> Single prints being left below 25380, indicating initiative buying. DPOC already shifted
> above IB mid. If extension reaches 20% of IB (17pts), the drive is likely sustained.
> Fattening at IBH confirms this isn't a false breakout."

#### B-Day / Balance Day (46.4% WR, 1.47 PF)
**What the LLM observes:**
- IB location relative to prior VA?
- Price probing and returning to mid?
- Dual-sided auction developing?
- DPOC stable (not migrating)?
- Skew developing (P-skew or b-skew)?

**Example output:**
> "IB formed inside prior VA with 30-min acceptance. Price probed IBH, rejected back to
> mid — classic balance day probe-and-return behavior. DPOC stable at 25120 (no migration).
> Neutral skew, dual-sided auction. If price probes IBL next and returns, this confirms
> the balance classification. Fade the extremes, target mid."

#### Edge Fade / Balance Day IBL Fade (Study: 76% WR, 5.89 PF)
**Key study findings:**
- **B-day IBL LONG is king**: 76% WR, 5.89 PF, $1,352/month. First-touch IBL = 82% WR, 9.35 PF
- **"Fade the first test" principle**: 1st touch 82% WR → 2nd touch 20% → 3rd touch 13%. Quality degrades fast
- **30-min acceptance** naturally excludes trend days (self-correcting filter)
- **IB POC shape as real-time proxy** (identifiable at 10:30, before EOD day type known):
  - b-shape (POC lower third) → 79% WR for LONG
  - P-shape (POC upper third) → 65% WR for LONG only
  - D-shape (POC center) → neutral, both directions work
- **VWAP above IB mid + IBL LONG = 46% raw** (3x baseline 17%)
- **DPOC migration AGAINST fade direction outperforms** (contrarian signal)
- **Stabilizing DPOC confirms balance** → +9pp to 71% WR
- **VWAP oscillation on balance days is noise** — don't use sweep-fail patterns (45% WR)
- **P-Day shorts = structural failure** (29% WR, skip entirely)

**What the LLM observes:**
- Is this a B-day (b-shaped POC at 10:30)?
- Is this the FIRST touch of IBL?
- 30-min close inside IB after touch = acceptance?
- VWAP above or below IB mid?
- DPOC regime: stabilizing (good for fade) vs trending (skip)?
- DPOC retention: high retention = conviction, low (<40%) = exhaustion → skip

**Example output:**
> "B-shaped POC at 10:30 — volume concentrated in lower IB third. First touch of IBL
> 24885 at 11:15. VWAP at 25145 sits above IB mid 25120 — structural support for longs.
> DPOC stabilizing at 25100 (not trending down). This is textbook B-Day IBL fade territory
> (76% WR, 5.89 PF in study). First touch is the highest-quality entry — subsequent
> touches degrade rapidly (2nd: 20% WR). Watch for 30-min acceptance close above IBL."

**Invalidation:**
> "Price accepts below IBL for 2+ TPO periods. Or DPOC retention drops below 40% — exhaustion."

#### Trend Following / Breakout (Study: 58% WR, 2.8 PF target)
**Key study findings:**
- Best in strong trends (ADX > 30) with volume > 150% average
- Multi-timeframe alignment required: 15-min trend = 5-min trend
- Entry types: 20-period breakouts, prior day extreme breaks, VWAP band penetrations, OR drive continuation
- C-Period rule: close above IBH = 70-75% continuation probability
- Daily expectancy: $1,465/day target (highest of all strategies)
- Worst in chop/range/high VIX — must identify trending conditions first

**What the LLM observes:**
- Is IB narrow (compression = breakout potential)?
- Is price extending beyond IB with initiative (single prints left behind)?
- DPOC migrating with the extension (not stalling)?
- Multi-timeframe alignment: 15-min and 5-min trend match?
- C-Period (10:30-11:00) close location: above IBH/below IBL?
- ADX / trend strength reading?
- Volume above average (initiative) or below (no conviction)?

**Example output:**
> "Narrow IB 95pts (0.5x ATR) with C-period closing above IBH at 10:45 — 70-75%
> continuation probability per Dalton. Extension currently 28pts above IBH with single
> prints forming below 25380. DPOC migrating up 15pts since 10:30 — initiative activity.
> Trend strength: Moderate. This has trend day characteristics developing. If extension
> reaches 1.0x IB (95pts above IBH), this is a confirmed trend day — don't fade it."

**Invalidation:**
> "Extension stalls, DPOC stops migrating, price returns inside IB within 30 min."

#### Mean Reversion (Study: 65% WR in range-bound, 35% in trending)
**Key study findings:**
- **Regime-dependent**: 65-70% WR in range-bound markets, 35-40% in trending = LOSING
- Entry conditions: Bollinger Band touch + RSI extreme (<30 or >70), VWAP extension >1.5 ATR
- Best windows: 10:30-11:30 and 13:00-15:00
- Tight stops (2-5pts) and fast exits (5-min time stops if no profit)
- **NOT a standalone strategy** — only works when market is clearly range-bound
- The LLM must identify the REGIME first, then determine if MR is viable

**What the LLM observes:**
- Is the market range-bound (no trend, ADX < 20, DPOC stabilizing)?
- RSI at extreme (<30 or >70)?
- Price at Bollinger Band touch with volume divergence?
- VWAP extended >1.5 ATR from current price?
- Is this the right time window (10:30-11:30 or 13:00-15:00)?
- **CRITICAL**: If trending conditions exist (ADX > 30, DPOC trending), DO NOT consider MR

**Example output:**
> "Balance day confirmed. DPOC stabilizing, ADX 18 (no trend). RSI at 28 (extreme oversold)
> with price touching lower Bollinger Band at 24900. VWAP at 25050, price extended 150pts
> below (>1.5x ATR). Mean reversion conditions present — but our backtest shows this strategy
> is regime-sensitive (65% WR range-bound vs 35% trending). Current regime: range-bound.
> VWAP at 25050 is the natural MR target if conditions hold. Tight stop required."

**Invalidation:**
> "Trend develops (ADX crosses 30, DPOC starts trending). Or price breaks below Bollinger
> Band lower by >1 ATR — capitulation, not mean reversion."

#### Two Hour Trader — Options Overlay (Study: 60-79% WR, up to 6.76 PF)
**Key study findings:**
- **Time window**: 9:30-11:30 ET (hard exit at 11:30, no afternoon holds)
- **Instruments**: SPY, QQQ, or SPX options (0-2 DTE for max gamma/delta)
- **Three entry types**: Momentum Breakout, Mean Reversion, VWAP Bounce
- **Risk**: Max $400/trade (premium = max loss, no margin blow-up risk)
- **Exits**: Scaled — 50% at 2R, 25% at 4R, 25% trailing
- **Daily limits**: Max 2 losers ($800 daily cap), max 5 trades
- **Greeks awareness**: 0-DTE theta is ruthless, avoid VIX > 30 (IV crush)
- **Advantage over futures**: Defined risk, no overnight exposure, no margin calls
- **Best combined with**: Futures tape reading (options overlay on confirmed direction)

**What the LLM observes:**
- Is the tape reading HIGH conviction in one direction?
- Is there a confirmed strategy signal (OR Rev, OR Accept, Trend) backing it?
- Is VIX below 25 (acceptable) or above 30 (sit out)?
- Which entry type fits? (Breakout for drives, MR for extremes, VWAP for pullbacks)
- Is this the first 2 hours? (hard cutoff at 11:30)
- How many options trades today already? (max 5)

**Example output:**
> "Two Hour Trader opportunity aligns with tape. OR Reversal LONG confirmed at 9:52
> with all 4 confirmations. Bullish tape: CVD divergence, DPOC migrating up, b-shape
> developing. Momentum Breakout type — OR broke to upside with 1.6x volume. VIX 19
> (acceptable). Options: SPY/QQQ calls, ATM 0-DTE for max delta capture. Premium
> risk $300-400. Scaled exits: 50% at 2R ($600-800), 25% at 4R, 25% trails.
> HARD EXIT by 11:30 regardless. This is conviction overlay — tape + strategy aligned."

**Invalidation:**
> "Direction reverses — price breaks back below OR mid and holds. Or VIX spikes above 25
> intraday. Close options immediately if futures thesis invalidates."

**When NOT to call out:**
> "Rotation open, no confirmed signal, VIX > 25, already 2 losers today, or after 10:30
> with no clear direction. Options in chop = theta burn. Say: 'No options play — no edge.'"

### 3.4 Strategies We Do NOT Train On

| Strategy | WR | PF | Why Skip |
|----------|----|----|----------|
| P-Day SHORT | 29% | — | Structural failure — NQ long bias kills shorts on P-days |
| ORB Enhanced | — | — | Broken implementation |
| Super Trend | — | — | Losing in backtest |
| VWAP Sweep-Fail | 45% | — | "VWAP oscillation on balance days is noise" (335 trades, -$1,624/mo) |

### 3.5 Key Study-Derived Observations the LLM Must Learn

These are the "tape reading callouts" from the strategy studies — patterns the LLM should
recognize and articulate:

| Observation | Source Study | What LLM Says |
|------------|-------------|---------------|
| 100% of accepted 80P setups fill the gap | 80P Report | "Gap fill is near-certain once acceptance confirmed — the question is timing and target depth" |
| Losers enter at 23% VA depth, winners at 45% | 80P Report | "Shallow entry — price barely inside VA. Higher risk of re-test and quick stop" |
| B-day IBL first touch = 82% WR | Balance Day Study | "FIRST touch of IBL on B-day — this is the highest-quality fade entry we have" |
| DPOC against fade direction outperforms | Balance Day Study | "DPOC moving against our fade — contrarian confirmation, actually higher edge" |
| Post-London direction = acceptance direction 81% | Premarket Study | "London was bearish, overnight direction aligns — if acceptance develops, it's likely to the downside" |
| Directional premarket + bullish CVD = 59% acceptance | Premarket Study | "Premarket is directional with bullish CVD — acceptance session probable (59%)" |
| 30-min acceptance naturally excludes trend days | Balance Day Study | "30-min close back inside IB = this isn't a trend day. Self-correcting filter" |
| C-period close above IBH = 70-75% continuation | IB Width Study | "C-period broke above IBH — 70-75% probability this continues up" |
| NR4/NR7 = compression → breakout imminent | IB Width Study | "Narrowest IB in 4/7 sessions — compression energy stored, expect range expansion" |
| 80P larger gaps (200+pts) fill only 36% | 80P Report | "Large gap — 200+ pts. Historical fill rate drops to 36%. Lower confidence for 80P" |
| MR only works range-bound (65%) vs trending (35%) | Mean Reversion Study | "Regime check first — MR is only viable if DPOC stabilizing and ADX < 20" |
| OR Acceptance: IB window > EOR window | OR Acceptance Study | "IB window acceptance (43.7% WR) outperforms EOR (40.7%) — price needs time" |

---

## Part 4: Adding Invalidation

### 4.1 What Is Invalidation?

Every tape reading observation should have a clear "this thesis breaks if..." condition.

### 4.2 Format

```json
{
  "invalidation": {
    "condition": "Price accepts above 25200 for 2+ TPO periods",
    "what_it_means": "Sellers failed to defend prior VAH — bullish reclaim in progress",
    "action": "Abandon bearish thesis, reassess for long-side setups"
  }
}
```

### 4.3 Invalidation Per Setup Type

| Setup Context | Invalidation |
|--------------|-------------|
| OR Reversal (short after sweep) | "Price reclaims swept level and holds above for 2 candles" |
| OR Acceptance (long after hold) | "Price drops back below acceptance level with 2x 5-min closes = acceptance failed" |
| 80P (value migration) | "Price breaks back out of VA in the entry direction" |
| B-Day (balance fade) | "IB extension exceeds 50% of IB range — no longer balanced" |
| 20P extension | "Extension stalls and price returns inside IB within 15 min" |
| Bearish thesis | "DPOC reverses up + bullish wick parade ≥6 in 60 min" |
| Bullish thesis | "Price loses VWAP + poor low forms at current level" |

---

## Part 5: Revised Output Schema (Tape Reader)

### 5.1 Fields

```json
{
  "thinking": {
    "step_1_context": "Where are we? (overnight, relative to prior value, gap status)",
    "step_2_structure": "IB read (range, width class, extension, implications)",
    "step_3_flow": "Order flow (DPOC regime, TPO shape, wick parade, acceptance/rejection)",
    "step_4_levels": "Key levels with distance + significance",
    "step_5_day_type": "Day type evidence chain (why this classification)",
    "step_6_tape_read": "What is the tape saying RIGHT NOW? (renamed from setups)",
    "step_7_risk": "CRI + invalidation + what could go wrong"
  },

  "premarket_read": "Overnight narrative: Asia/London bias, sweeps, compression, opening context",

  "or_play": "Opening range observations: sweeps, drives, FVG creation, Judas swing potential",

  "ib_read": "IB interpretation: width implications, extension potential, responsive vs initiative",

  "day_type_call": {
    "classification": "FROM DETERMINISTIC (match inference.day_type.type)",
    "evidence": ["3-4 bullets grounded in snapshot data"],
    "confidence_breakdown": "How confidence was built (what supports, what caps it)",
    "skew": "P-skew/b-skew with evidence, or NA for trend days",
    "morph_watch": "What to watch for that would change the classification"
  },

  "tape_observations": {
    "or_reversal": "Sweep + reverse observation (or NA if outside 9:30-10:15 window)",
    "or_acceptance": "Level break + hold observation (not sweep — continuation, not reversal)",
    "eighty_percent": "VA open/fail/acceptance observation (gap fill context, entry depth)",
    "twenty_percent": "IB extension observation (narrow IB = compression, single prints, DPOC follow-through)",
    "b_day_edge_fade": "Balance day fade observation (POC shape, first touch, DPOC regime, VWAP vs IB mid)",
    "trend_following": "Trend development observation (IB width, C-period, multi-TF alignment, initiative activity)",
    "mean_reversion": "Regime-dependent MR observation (ONLY if range-bound: RSI, BB, VWAP extension)",
    "two_hour_trader": "Options overlay callout (SPY/QQQ/SPX, entry type, VIX check, conviction level — ONLY when futures tape confirms direction, NA in chop/rotation)"
  },

  "value_area_play": "VA context: inside/outside, acceptance direction, target if migrating",

  "tpo_remarks": "Profile shape, fattening meaning, single prints, naked levels, DPOC narrative",

  "evolution": "How has bias/structure changed? DPOC trend, wick parade shifts, acceptance progression",

  "invalidation": {
    "condition": "Specific price + behavior that kills the current thesis",
    "what_it_means": "Why that invalidation matters",
    "action": "What to do if invalidated"
  },

  "evidence": ["1-5 specific observations with exact numbers"],

  "what_could_go_wrong": ["1-3 failure scenarios with triggers"],

  "one_liner": "Max 140 chars. What the market IS DOING, not what to trade.",

  "discipline": "CRI permission, position sizing, emotional check, time-of-day rules"
}
```

### 5.2 Key Changes from V1

| V1 (Current) | V2 (Tape Reader) | Why |
|-------------|-----------------|-----|
| `strategy_assessment` (7 strategies, trade language) | `tape_observations` (7 strategies, observation language) | LLM reads tape, doesn't trade |
| No invalidation | `invalidation` (condition/meaning/action) | Every thesis needs a kill switch |
| `step_6_setups` | `step_6_tape_read` | Renamed to reflect analyst role |
| Mean Reversion always active | Mean Reversion regime-gated | Only observe MR when range-bound (65% WR), skip in trends (35%) |
| Trend following disabled | Trend following added back | Study shows 58% WR, 2.8 PF — LLM observes trend development conditions |
| Edge fade generic | B-Day Edge Fade with study data | 76% WR first-touch IBL, POC shape filter, DPOC regime filter |
| Generic strategy stats | Study-derived callouts with exact numbers | "First touch IBL on B-day = 82% WR" not "consider fading" |
| No options awareness | `two_hour_trader` observation added | Options overlay when futures tape confirms direction (SPY/QQQ/SPX 0-DTE) |
| Basic Phase 1 tree | Comprehensive first-hour framework | Premarket Briefing + 4 sub-phases (1A/1B/1C/1D) with precision examples |

---

## Part 6: How Tape Reading Feeds the Agent Pipeline

### 6.1 Flow

```
                    ┌──────────────────────┐
                    │   Deterministic       │
                    │   Engine (1-min)      │
                    │                       │
                    │  Signal: "OR_REV      │
                    │  triggered at 09:42"  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   LLM Tape Reader    │
                    │   (5-min snapshots)  │
                    │                       │
                    │  "Swept London High   │
                    │  by 8pts, reversing   │
                    │  through OR mid.      │
                    │  Bearish FVG formed.  │
                    │  Invalidation: hold   │
                    │  above London High"   │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                │                 ▼
   ┌──────────────────┐       │      ┌──────────────────┐
   │    ADVOCATE       │       │      │    SKEPTIC        │
   │                   │       │      │                   │
   │  Inputs:          │       │      │  Inputs:          │
   │  • LLM analysis   │       │      │  • LLM analysis   │
   │  • Strategy signal │       │      │  • Strategy signal │
   │  • DuckDB history  │       │      │  • DuckDB history  │
   │                   │       │      │                   │
   │  "Signal + context │       │      │  "London High was  │
   │  align. Sweep is   │       │      │  re-tested 3x in   │
   │  clean, FVG        │       │      │  Globex. This isn't │
   │  confirms. Take    │       │      │  a clean sweep —    │
   │  the short."       │       │      │  it's a range break.│
   │                   │       │      │  CRI is PROBE_ONLY. │
   │  Confidence: 78%  │       │      │  Pass or reduce."   │
   └────────┬─────────┘       │      └────────┬──────────┘
            │                  │               │
            └──────────────────┼───────────────┘
                               ▼
                    ┌──────────────────────┐
                    │    ORCHESTRATOR       │
                    │                       │
                    │  Inputs:              │
                    │  • Advocate case      │
                    │  • Skeptic case       │
                    │  • CRI permission     │
                    │  • LLM invalidation   │
                    │  • Risk budget        │
                    │                       │
                    │  Decision:            │
                    │  "Take short, but     │
                    │  half size (CRI       │
                    │  PROBE_ONLY). Stop    │
                    │  above London High.   │
                    │  If invalidation hits,│
                    │  auto-exit."          │
                    └──────────────────────┘
```

### 6.2 What Each Agent Gets

#### Advocate (System Prompt Persona: "Find the edge")
- Receives: LLM tape reading + strategy signal + DuckDB query results
- Job: Build the bull/bear case for taking the trade
- Looks for: Confluence, historical pattern match, signal quality
- DuckDB query: "Last 20 times OR Rev fired with IB < 100pts, what was the win rate?"
- Output: Structured argument with confidence score

#### Skeptic (System Prompt Persona: "Find the flaw")
- Receives: Same inputs as Advocate
- Job: Find reasons NOT to take the trade
- Looks for: Invalidation triggers, CRI concerns, conflicting signals, poor timing
- DuckDB query: "Last 10 times OR Rev fired on a day with CRI STAND_DOWN, results?"
- Output: Counter-argument with risk factors

#### Orchestrator (System Prompt Persona: "Make the call")
- Receives: Advocate argument + Skeptic argument + CRI gate + risk budget
- Job: Weigh both sides, decide act/pass/reduce
- Rules:
  - CRI STAND_DOWN = always pass (hard gate)
  - Skeptic confidence > 80% = pass
  - Advocate confidence > 70% AND Skeptic < 50% = full size
  - Otherwise = reduced size or pass
- Output: Final decision with reasoning

### 6.3 Key Principle

**All three agents use the SAME LoRA model** with different system prompts. The fine-tuned
Qwen3.5 learns tape reading and market reasoning. The Advocate/Skeptic/Orchestrator
personas are defined by their system prompts, not separate models.

```
Same LoRA
├── Advocate system prompt: "You argue FOR taking the trade. Build the case..."
├── Skeptic system prompt:  "You argue AGAINST. Find flaws, traps, timing issues..."
└── Orchestrator prompt:    "You weigh both arguments. CRI is a hard gate..."
```

---

## Part 7: Inference Pipeline (How It Runs)

### 7.1 Real-Time Flow (Every 5 Minutes During RTH)

```
09:30 snapshot arrives
    │
    ├── 1. LLM Tape Reader generates analysis (~2-3s)
    │      Input: snapshot
    │      Output: tape reading JSON with thinking
    │
    ├── 2. Check: any strategy signals active?
    │      If NO  → publish analysis to dashboard, done
    │      If YES → trigger agent debate
    │
    ├── 3. Advocate generates case (~2s)
    │      Input: tape reading + signal + DuckDB context
    │      Output: {argument, confidence, historical_support}
    │
    ├── 4. Skeptic generates counter (~2s)
    │      Input: same inputs
    │      Output: {counter_argument, risk_factors, confidence}
    │
    │      (3 and 4 run in PARALLEL — same model, different prompts)
    │
    └── 5. Orchestrator decides (~1s)
           Input: advocate + skeptic + CRI + risk budget
           Output: {decision: "TAKE|PASS|REDUCE", size, reasoning}
```

### 7.2 When No Signal Fires

Most 5-min snapshots will have no strategy signal. The LLM still runs and produces its
tape reading — this goes to the dashboard for the trader to see. The agent debate only
triggers when a strategy signal fires.

```
78 snapshots/day × 5 strategies = up to 390 potential signals
Reality: ~2-5 signals per day → 2-5 agent debates per day
Other 73-76 snapshots: tape reading only (dashboard display)
```

### 7.3 Dashboard Integration

The tape reading feeds directly into the RockitUI dashboard tabs:
- **Brief tab** → `one_liner` + `premarket_read`
- **Logic tab** → `thinking` (7 steps)
- **Intraday tab** → `ib_read` + `or_play`
- **DPOC tab** → `tpo_remarks` + `evolution`
- **Coach tab** → `discipline` + `invalidation`
- **Trade Idea tab** → `tape_observations` (when signal fires, show agent debate)

---

## Part 8: Missing Deterministic Data (Based on Strategy Studies)

The studies reference indicators/conditions that the LLM needs but may not be in the
current deterministic snapshot. Audit:

| Data Needed | Study Source | Currently In Snapshot? | Action |
|------------|-------------|----------------------|--------|
| IB POC shape (b/P/D) | Balance Day Study | **YES** — `tpo_profile.tpo_shape` | Needs cleaner classification → b_shape/P_shape/D_shape |
| VWAP vs IB mid comparison | Balance Day Study | **YES** — `ib.current_vwap` + `ib.ib_mid` | LLM can derive, but could pre-compute |
| First touch of IBH/IBL tracking | Balance Day Study | **NO** | **ADD**: touch count per IB edge, touch timestamps |
| DPOC retention percentage | Balance Day Study | **NO** | **ADD**: % of peak migration preserved |
| ADX (Average Directional Index) | Trend + MR Studies | **NO** | **ADD**: ADX 14 for trend strength quantification |
| Bollinger Band position | Mean Reversion Study | **NO** | **ADD**: BB(20,2) upper/lower/position |
| CVD (Cumulative Volume Delta) | Premarket Study | **PARTIAL** — `wick_parade` is proxy | **ADD**: actual CVD value if available in data |
| Premarket directional score | Premarket Study | **PARTIAL** — `smt_preopen` | **ADD**: directional score (0-1), bullish/bearish CVD premarket |
| Session classification (Acceptance/Judas/Chop/Both) | Premarket Study | **NO** | **ADD**: classify open type by 10:00 |
| Entry depth % into VA (for 80P) | 80P Report | **NO** | **ADD**: how deep price penetrated into VA |
| Gap fill progress % | 80P Report | **NO** | **ADD**: % of gap already filled |
| Touch count per IB edge per session | Balance Day Study | **NO** | **ADD**: essential for "first touch" filter |
| 30-min candle acceptance tracking | Balance Day + 80P | **PARTIAL** — `balance_classification` | Verify it tracks per-edge acceptance |
| Multi-TF trend alignment (15m vs 5m) | Trend Study | **NO** | **ADD**: trend direction per timeframe |

### Priority for V1 (high-impact, easy to add)

1. **Touch count per IB edge** — critical for B-Day first-touch filter (82% vs 20% WR)
2. **ADX** — needed for regime classification (trend vs range-bound)
3. **Session open type classification** (Acceptance/Judas/Chop/Both)
4. **Entry depth % into VA** (for 80P quality assessment)
5. **DPOC retention %** (exhaustion signal)

### Defer to V2

- Bollinger Bands (MR is regime-gated, less critical)
- Full CVD (wick parade is decent proxy)
- Multi-TF trend alignment (complex, need 15-min data)
- 30-min overnight slices

---

## Part 9: Open Questions / TODO

### Training Data & Schema
- [ ] Review existing training pairs — do thinking steps match the tape reading quality in the studies?
- [ ] Rename `strategy_assessment` → `tape_observations` in output schema + system prompt
- [ ] Add `invalidation` field to output schema
- [ ] Add trend_following and mean_reversion to tape_observations
- [ ] Expand edge_fade with B-Day study findings (POC shape, first touch, DPOC regime)
- [ ] Update OR Acceptance with study data (IB window, level hierarchy, BOTH filter)
- [ ] Regenerate training pairs with V2 schema (164 pairs need redo)

### Deterministic Engine Additions (Part 8 priorities)
- [ ] Add IB edge touch counter (touch_count_ibh, touch_count_ibl, first_touch_time)
- [ ] Add ADX(14) to snapshot for regime classification
- [ ] Add session open type classification (Acceptance/Judas/Chop/Both)
- [ ] Add VA entry depth percentage for 80P quality
- [ ] Add DPOC retention percentage for exhaustion detection
- [ ] Add premarket directional score + bias classification
- [ ] Add `asia_bias` / `london_bias` / `overnight_sweep` derived fields

### Agent Architecture
- [ ] Prototype Advocate/Skeptic system prompts using study knowledge
- [ ] Define DuckDB schema (see Appendix D) and implement
- [ ] Build strategy runner → DuckDB → agent pipeline event flow
- [ ] How does orchestrator handle conflicting signals (e.g., 80P and OR Rev both active)?
- [ ] Define risk budget rules (max trades/day, max exposure, daily loss limit)
- [ ] Decide: do we need overnight 30-min slices for V2?

### Study Integration
- [ ] Port key study findings into system prompt (strategy stats, edge conditions, anti-patterns)
- [ ] Create "observation library" — reference examples the LLM can learn from
- [ ] Validate: do current deterministic modules capture enough for each study's key observations?
- [ ] Add study-derived anti-patterns (P-Day shorts, VWAP sweep-fail, 2nd/3rd touch degradation)

### Two Hour Trader (Options)
- [ ] Add `two_hour_trader` to output schema and system prompt
- [ ] Define when LLM should call out options vs stay silent (conviction threshold)
- [ ] VIX data source — do we have VIX in our data feed? If not, add to deterministic snapshot
- [ ] RSI computation — needed for MR entry type (currently not in snapshot)
- [ ] Bollinger Band computation — needed for MR entry type
- [ ] Options P&L tracking in DuckDB (separate from futures trades)
- [ ] Train LLM on options risk rules ($400 max, 11:30 hard exit, VIX > 30 = sit out)

---

## Appendix A: Current Deterministic Premarket Data

```json
{
  "premarket": {
    "asia_high": 25364.75,
    "asia_low": 25264.75,
    "london_high": 25401.5,
    "london_low": 25343.25,
    "london_range": 58.25,
    "overnight_high": 25415.25,
    "overnight_low": 25342.25,
    "overnight_range": 73.0,
    "previous_day_high": 25494.75,
    "previous_day_low": 24992.0,
    "compression_flag": false,
    "compression_ratio": 0.798,
    "smt_preopen": "neutral"
  }
}
```

**What we CAN derive without new data:**
- `asia_bias`: Compare asia range position relative to prior close
- `london_bias`: Did London expand above/below Asia range?
- `overnight_sweep`: Did ONH/ONL exceed prior day high/low?
- `key_level_tests`: Which prior session levels were touched overnight?

**What would need new 30-min overnight slices:**
- Overnight DPOC migration and acceptance zones
- Overnight volume distribution (accumulation vs distribution)
- Intra-session momentum shifts (Asia bullish → London reversal)
- Overnight VWAP and delta (buy vs sell volume)

## Appendix B: Available FVG Data (Premarket)

FVGs are already captured across 5 timeframes during Globex hours:

```json
{
  "1h_fvg": [{"type": "bullish", "top": 25326.25, "bottom": 25309.5, "time": "02:00"}],
  "90min_fvg": [{"type": "bullish", "top": 25343.25, "bottom": 25333.5, "time": "03:00"}],
  "15min_fvg": [
    {"type": "bullish", "top": 25307.0, "bottom": 25300.0, "time": "01:00"},
    {"type": "bearish", "top": 25367.0, "bottom": 25356.0, "time": "09:30"}
  ],
  "5min_fvg": [
    {"type": "bullish", "top": 25307.25, "bottom": 25306.75, "time": "01:00"},
    {"type": "bearish", "top": 25360.25, "bottom": 25356.0, "time": "09:30"}
  ]
}
```

This is good overnight ICT data — the LLM can reference unfilled FVGs as liquidity targets
and discount/premium zones.

---

## Appendix C: IB Range Classification & Extension Probability

### C.1 IB Width Classification (Dalton Framework — Primary)

The deterministic engine classifies IB width using ATR ratio (`ib_range / ATR14`):

| Classification | ATR Ratio | NQ Typical Range | Interpretation | Extension Probability |
|---------------|-----------|-----------------|---------------|----------------------|
| **Narrow** | < 0.7 | < ~130pts | Compressed. High trend potential. Expect breakout. | **HIGH** — narrow = coiled spring |
| **Normal** | 0.7 - 1.3 | ~130-240pts | Standard auction. Any day type possible. | MODERATE — depends on context |
| **Wide** | 1.3 - 2.0 | ~240-370pts | Most directional move may be done. Balance/neutral skew. | **LOW** — extending a wide IB is hard |
| **Extreme** | >= 2.0 | > ~370pts | Massive move already happened. Rotation expected. | **VERY LOW** — exhaustion, fade the extremes |

**Source:** `packages/rockit-core/src/rockit_core/deterministic/modules/ib_location.py` (lines 68-82)

### C.2 Why IB Width Matters for Extension

From Dalton Market Profile theory:
- **Narrow IB = compression** → Energy is stored. When price breaks IBH or IBL, the move
  tends to be sustained because there's no "work" done in the middle. Single prints get left
  behind (initiative), DPOC migrates with the extension.
- **Wide IB = expansion already happened** → The auction has already explored both sides.
  Extending further requires NEW initiative activity. Most of the day's range is done.
  Balance/rotation is the higher-probability outcome.

**C-Period Rule (70-75% edge):**
- C-period (10:30-11:00) close ABOVE IBH → 70-75% probability of continuation up
- C-period close BELOW IBL → 70-75% probability of continuation down
- C-period close INSIDE IB → 70-75% probability of reversal to opposite IB extreme

**Source:** `packages/rockit-core/src/rockit_core/indicators/ib_width.py` (lines 167-209)

### C.3 NR4/NR7 — Narrow Range Days

Special compression signals:
- **NR4**: Today's IB range <= minimum of last 3 sessions → extreme compression, breakout imminent
- **NR7**: Today's IB range <= minimum of last 6 sessions → even rarer, even stronger breakout signal

**What the LLM should say:**
> "NR4 detected — IB range 85pts is the tightest in 4 sessions. This compression typically
> precedes a strong directional move. The first IB extension will likely be sustained. Watch
> which side breaks first and whether single prints form behind the move."

### C.4 Mean Reversion IB Classification (Absolute Points)

Used by the mean reversion module for rejection analysis:

| Classification | IB Range (pts) | Interpretation |
|---------------|----------------|---------------|
| Tight | < 200 | Expansion potential, breakout likely |
| Normal | 200-250 | Typical session range |
| Wide | > 250 | Rotation/reversion potential |

**Source:** `packages/rockit-core/src/rockit_core/deterministic/modules/mean_reversion_engine.py` (lines 96-103)

### C.5 Extension Targets (Dalton Multiples)

When IB does extend, the deterministic engine tracks targets at standard multiples:

| Extension | Formula | Meaning |
|-----------|---------|---------|
| 0.5x | IBH + 0.5 × IB range | Minor extension — probe |
| 1.0x | IBH + 1.0 × IB range | Full extension — trend day territory |
| 1.5x | IBH + 1.5 × IB range | Strong trend — don't fight it |
| 2.0x | IBH + 2.0 × IB range | Extreme — super trend day |
| 3.0x | IBH + 3.0 × IB range | Rare — capitulation / liquidation event |

**Tape reading for 20P:**
> "Narrow IB 85pts. Extension above IBH currently at 17pts (20% of IB). If this holds as
> 3 consecutive 5-min closes above IBH, it's a 20P trigger. With narrow IB, the 1.0x
> extension target is IBH + 85pts = 25441 — achievable on a trend day. Single prints
> forming below 25375 confirm initiative buying."

### C.6 How IB Classification Feeds Tape Reading

| IB Classification | LLM Tape Reading Focus |
|------------------|----------------------|
| **Narrow** | "Coiled spring. Watch for 20P extension trigger. First breakout likely sustained. NR4/NR7?" |
| **Normal** | "Standard auction. All playbooks viable. Context-dependent — read flow, DPOC, acceptance." |
| **Wide** | "Most of move done. Fade IB extremes toward mid. 80P and B-Day more likely than trend." |
| **Extreme** | "Exhaustion. DPOC likely stabilizing. Rotation trade — fade extensions back to IB mid." |

---

## Appendix D: DuckDB Schema & Runtime Architecture

### D.1 Why DuckDB

- Already planned for Historian agent (historical context queries)
- Doubles as signal log + trade journal — single source of truth
- In-process (no external service to manage)
- SQL interface = agents can query with natural language → SQL
- Replay capability: re-run any historical signal through agent pipeline

### D.2 Schema

```sql
-- Strategy signals fired by the 1-min engine
CREATE TABLE signals (
    id              INTEGER PRIMARY KEY,
    session_date    DATE NOT NULL,
    signal_time     TIMESTAMP NOT NULL,
    strategy        VARCHAR NOT NULL,       -- 'or_reversal', 'or_acceptance', 'eighty_percent', 'twenty_percent', 'b_day'
    direction       VARCHAR NOT NULL,       -- 'LONG', 'SHORT'
    entry_price     DOUBLE NOT NULL,
    stop_price      DOUBLE NOT NULL,
    target_price    DOUBLE NOT NULL,
    signal_metadata JSON,                   -- strategy-specific: {acceptance_level, sweep_depth, ib_range, ...}
    snapshot_time   VARCHAR,                -- latest 5-min snapshot time when signal fired
    status          VARCHAR DEFAULT 'pending'  -- 'pending', 'debated', 'taken', 'passed', 'expired'
);

-- Agent debate decisions
CREATE TABLE decisions (
    id              INTEGER PRIMARY KEY,
    signal_id       INTEGER REFERENCES signals(id),
    session_date    DATE NOT NULL,
    decision_time   TIMESTAMP NOT NULL,
    decision        VARCHAR NOT NULL,       -- 'TAKE', 'PASS', 'REDUCE'
    size            INTEGER,                -- number of contracts
    advocate_conf   DOUBLE,                 -- 0-100
    skeptic_conf    DOUBLE,                 -- 0-100
    advocate_arg    TEXT,                    -- advocate's full argument
    skeptic_arg     TEXT,                    -- skeptic's counter-argument
    orchestrator_reasoning TEXT,             -- orchestrator's final reasoning
    cri_status      VARCHAR,                -- 'READY', 'PROBE_ONLY', 'STAND_DOWN'
    tape_reading    JSON,                   -- LLM tape reading at decision time
    invalidation    JSON                    -- {condition, what_it_means, action}
);

-- Actual trade executions and outcomes
CREATE TABLE trades (
    id              INTEGER PRIMARY KEY,
    signal_id       INTEGER REFERENCES signals(id),
    decision_id     INTEGER REFERENCES decisions(id),
    session_date    DATE NOT NULL,
    entry_time      TIMESTAMP NOT NULL,
    exit_time       TIMESTAMP,
    direction       VARCHAR NOT NULL,
    entry_price     DOUBLE NOT NULL,
    exit_price      DOUBLE,
    stop_price      DOUBLE NOT NULL,
    target_price    DOUBLE NOT NULL,
    contracts       INTEGER NOT NULL,
    pnl_pts         DOUBLE,
    pnl_dollars     DOUBLE,
    exit_reason     VARCHAR,                -- 'target', 'stop', 'invalidation', 'eod', 'manual'
    strategy        VARCHAR NOT NULL,
    status          VARCHAR DEFAULT 'open'  -- 'open', 'closed', 'cancelled'
);

-- 5-min market structure snapshots (for Historian queries)
CREATE TABLE snapshots (
    session_date    DATE NOT NULL,
    snapshot_time   VARCHAR NOT NULL,       -- 'HH:MM'
    day_type        VARCHAR,
    bias            VARCHAR,
    confidence      INTEGER,
    ib_range        DOUBLE,
    ib_width_class  VARCHAR,
    dpoc_regime     VARCHAR,
    cri_status      VARCHAR,
    balance_type    VARCHAR,
    skew            VARCHAR,
    price           DOUBLE,
    vwap            DOUBLE,
    ibh             DOUBLE,
    ibl             DOUBLE,
    full_snapshot   JSON,                   -- complete snapshot for deep queries
    PRIMARY KEY (session_date, snapshot_time)
);

-- Daily session summaries (for pattern matching)
CREATE TABLE sessions (
    session_date    DATE PRIMARY KEY,
    day_type_final  VARCHAR,                -- final day type classification
    ib_range        DOUBLE,
    ib_width_class  VARCHAR,
    session_range   DOUBLE,
    max_extension   DOUBLE,                 -- max IB extension achieved
    extension_dir   VARCHAR,                -- 'up', 'down', 'both', 'none'
    signals_fired   INTEGER,
    trades_taken    INTEGER,
    trades_won      INTEGER,
    daily_pnl       DOUBLE,
    gap_status      VARCHAR,                -- 'above_va', 'inside_va', 'below_va'
    overnight_range DOUBLE,
    compression     DOUBLE                  -- compression_ratio
);
```

### D.3 Example Agent Queries

**Advocate building a case:**
```sql
-- "Last 20 times OR Rev fired with narrow IB, what was the outcome?"
SELECT t.pnl_pts, t.exit_reason, s.ib_range, s.ib_width_class
FROM trades t
JOIN signals sig ON t.signal_id = sig.id
JOIN snapshots s ON sig.session_date = s.session_date
    AND sig.snapshot_time = s.snapshot_time
WHERE sig.strategy = 'or_reversal'
    AND s.ib_width_class = 'narrow'
ORDER BY sig.session_date DESC
LIMIT 20;
```

**Skeptic finding flaws:**
```sql
-- "What happens when OR Rev fires but CRI is STAND_DOWN?"
SELECT d.decision, t.pnl_pts, t.exit_reason
FROM decisions d
LEFT JOIN trades t ON d.signal_id = t.signal_id
JOIN signals sig ON d.signal_id = sig.id
WHERE sig.strategy = 'or_reversal'
    AND d.cri_status = 'STAND_DOWN'
ORDER BY sig.session_date DESC;
```

**Historian providing context:**
```sql
-- "Days with similar IB range and gap status — what day type developed?"
SELECT session_date, day_type_final, ib_range, max_extension, daily_pnl
FROM sessions
WHERE ib_width_class = 'narrow'
    AND gap_status = 'below_va'
ORDER BY session_date DESC
LIMIT 10;
```

### D.4 Runtime Architecture (Single Process)

```
┌──────────────────────────────────────────────────────────────┐
│                    ROCKIT Runtime (Single Process)            │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │  Data Feed (1-min bars from NinjaTrader or replay)  │     │
│  └──────────────┬──────────────────────────────────────┘     │
│                 │                                             │
│       ┌─────────┴──────────┐                                 │
│       │                    │                                  │
│       ▼                    ▼                                  │
│  ┌──────────┐     ┌──────────────┐                           │
│  │ Strategy │     │ Orchestrator │   Every 5 min:            │
│  │ Runner   │     │ (38 modules) │   Generate snapshot       │
│  │          │     │              │   → LLM tape reading      │
│  │ Every    │     │ Every 5 min  │   → Publish to dashboard  │
│  │ 1-min    │     │              │                           │
│  │ bar:     │     └──────┬───────┘                           │
│  │ check    │            │                                   │
│  │ signals  │            │ snapshot                          │
│  └────┬─────┘            │                                   │
│       │                  ▼                                   │
│       │           ┌─────────────┐                            │
│       │           │  DuckDB     │  ← snapshots table         │
│       │ signal    │             │  ← signals table           │
│       ├──────────►│  In-Process │  ← decisions table         │
│       │ write     │  Database   │  ← trades table            │
│       │           │             │  ← sessions table          │
│       │           └──────┬──────┘                            │
│       │                  │                                   │
│       │           signal event                               │
│       │                  │                                   │
│       ▼                  ▼                                   │
│  ┌──────────────────────────────┐                            │
│  │       Agent Pipeline         │                            │
│  │                              │                            │
│  │  1. Load latest tape reading │                            │
│  │  2. Load signal details      │                            │
│  │  3. Query DuckDB (Historian) │                            │
│  │                              │                            │
│  │  ┌──────────┐ ┌──────────┐  │                            │
│  │  │ Advocate  │ │ Skeptic  │  │  ← PARALLEL (same LoRA)   │
│  │  └────┬─────┘ └────┬─────┘  │                            │
│  │       └──────┬──────┘        │                            │
│  │              ▼               │                            │
│  │       ┌──────────────┐       │                            │
│  │       │ Orchestrator │       │                            │
│  │       └──────┬───────┘       │                            │
│  │              │               │                            │
│  │         decision             │                            │
│  └──────────────┼───────────────┘                            │
│                 │                                            │
│                 ▼                                            │
│  ┌──────────────────────┐    ┌──────────────────┐           │
│  │  DuckDB              │    │  Dashboard        │           │
│  │  (write decision +   │    │  (WebSocket push) │           │
│  │   trade if TAKE)     │    │                   │           │
│  └──────────────────────┘    └──────────────────┘           │
│                                                              │
│  No external message queue. No Redis. No Kafka.              │
│  Just Python asyncio events + DuckDB in-process.             │
│  ~2-5 agent debates per day. Most snapshots = tape read only.│
└──────────────────────────────────────────────────────────────┘
```

### D.5 Signal Lifecycle

```
1. Strategy runner checks 1-min bar
2. Signal condition met → write to DuckDB signals table (status: 'pending')
3. Emit asyncio event → agent pipeline picks up
4. Agent pipeline:
   a. Fetch latest 5-min snapshot (tape reading)
   b. Query DuckDB for historical context
   c. Run Advocate + Skeptic in parallel
   d. Run Orchestrator
   e. Write decision to DuckDB (status: 'debated')
5. If decision = TAKE:
   a. Write trade to DuckDB (status: 'open')
   b. Strategy runner manages the trade on 1-min bars
   c. On exit → update trade (status: 'closed', pnl)
6. If decision = PASS:
   a. Update signal (status: 'passed')
   b. Log reasoning for post-market review
7. End of day:
   a. Write session summary to sessions table
   b. Close any open trades (EOD exit)
```

### D.6 How Strategy Runner and Orchestrator Coexist

They share the same 1-min data feed but operate on different cadences:

```python
# Pseudocode for the main loop
async def main_loop(data_feed):
    duckdb = connect_duckdb("data/rockit.duckdb")
    strategy_runner = StrategyRunner(strategies=[...])
    orchestrator = DeterministicOrchestrator()
    llm = VLLMClient("http://localhost:8000")
    agent_pipeline = AgentPipeline(llm, duckdb)

    bar_count = 0
    latest_snapshot = None

    async for bar in data_feed:
        bar_count += 1

        # EVERY 1-min bar: check strategy signals
        signal = strategy_runner.check(bar)
        if signal:
            signal_id = duckdb.insert_signal(signal)
            # Trigger agent debate using latest snapshot
            asyncio.create_task(
                agent_pipeline.debate(signal_id, latest_snapshot)
            )

        # EVERY 5th bar: run full orchestrator + LLM
        if bar_count % 5 == 0:
            latest_snapshot = orchestrator.run(bar)
            tape_reading = await llm.analyze(latest_snapshot)
            duckdb.insert_snapshot(latest_snapshot)
            dashboard.push(tape_reading)

        # Manage open trades (every bar)
        strategy_runner.manage_trades(bar)
```
