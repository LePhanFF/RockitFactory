# 08 — Systematic Observations: Strategy Patterns, Entry Models & Execution Architecture

> **Purpose**: Exhaustive catalog of ALL strategy patterns (OR, IB, 80P, 20P, B-Day, Mean Reversion), reusable entry/stop/target models, and the architecture for decoupling signal detection from execution. Ensures the LLM's tape reading covers every scenario AND that the backtest engine can test any entry model against any strategy signal.
>
> **Status**: Design document / training reference / architecture proposal
> **Date**: 2026-03-05

---

## Part 1: OR Taxonomy — Four Strategies, One Decision Tree

The Opening Range (OR) is the 9:30–9:45 ET price range. The Extended Opening Range (EOR) extends through 10:00. All OR-based strategies fire in the first hour — this is where the money is made.

### Strategy Overview

| Strategy | WR | PF | Trades | Window | Core Logic |
|----------|----|----|--------|--------|------------|
| OR Reversal (Judas Swing) | 64.4% | 2.96 | 101 | 9:30–10:15 | Sweep premarket level → reverse through OR mid → 50% retest entry |
| OR Acceptance | 59.9% | 1.46 | 137 | 9:30–11:00 | 2×5-min close acceptance above/below level, limit at acceptance level |
| IB Breakout | 74.56% | 2.51 | 114 | 10:30+ | IB breakout with VWAP confirmation + volume spike. Failure → Balance Day |
| IB Breakout Enhanced | — | — | — | 10:30+ | C-period + FVG + SMT confluence confirmations |

### Premarket Context — Asia & London as OR Predictors

Asia and London sessions are critical in printing data for how the OR trade will pan out. Key observations:

- **Key levels to watch**: Asia High/Low, London High/Low, Previous Day High/Low
- **Liquidity channel detection**: Is premarket building HH/HL (bullish) or LH/LL (bearish)? When liquidity builds in a channel, stops accumulate along swing points in lower timeframes. Any price push at the open triggers stops and causes price to flip the opposite direction (Judas)
- **Tight London → Wide IB**: A compressed London range often triggers a wide-ranging IB at the open (energy release)
- **Asia/London overlap**: When Asia and London ranges overlap (e.g., London Low sweeps Asia Low), the combined liquidity creates stronger levels

**TODO — Premarket Deterministic Filter**: Study successful vs failed OR trades and correlate with premarket conditions. What Asia/London patterns (TPO distribution, value area, range width, channel structure) predict OR success? This could become a premarket conviction score.

#### Recent Session Examples

- **March 5, 2026**: Asia and London overlap — London Low swept Asia Low. Open gapped up to London High. Touched London High and failed, came back under IBL. OR trade worked both sides: catch move up to London High, then short rejection back to IBL.
- **March 4, 2026**: NQ opened above London and rejected, but never did CISD down — never formed 5-min gap away from the up candle. The up green candle got swept low and price went to accept London High and went higher. Messy acceptance — but that up candle got reclaimed.
- **March 3, 2026**: Clean sweep of London Low and reversed. Textbook Judas.
- **Clean break pattern**: A solid 15-min candle sometimes forms a FVG/BPR combo on 5-min for continuation entry. The 5-min FVG has to react for continuation until a level is taken.

### Decision Tree (9:30–10:30)

```
Prior 9:30 — Premarket Analysis
  │ Deep dive into Asia/London price action:
  │ - Liquidity channels (HH/HL or LH/LL)?
  │ - Tight London range (wide IB incoming)?
  │ - Asia/London overlap levels?
  │ - Premarket conviction score
  │
9:30 — OR Forming
  │
  ├─ 9:35-9:45: OR Locked (15-min range established)
  │   │
  │   ├─ Sweep detected? (price swept premarket level then reversed)
  │   │   ├─ YES → OR Reversal candidate
  │   │   │   ├─ Reversed through OR mid? → CONFIRMED Judas Swing
  │   │   │   └─ Held above/below swept level? → Failed Judas → becomes OR Acceptance
  │   │   │
  │   │   └─ NO sweep → Check acceptance
  │   │       ├─ 2×5-min close above/below level? → OR Acceptance candidate
  │   │       └─ No clear direction → ROTATION (wait for EOR)
  │   │
  │   └─ Both sides swept? → BOTH SESSION → No OR play. Wait for IB.
  │
  ├─ 9:45-10:00: EOR Confirmation
  │   ├─ OR Rev confirmed? → Execute (50% retest entry)
  │   ├─ OR Accept confirmed? → Execute (limit at acceptance level)
  │   └─ Neither? → Shift to IB strategies
  │
  └─ 10:00-10:30: IB Formation
      ├─ IB Breakout developing? (extension with volume) → Trend potential
      ├─ OR Rev still live? (last chance entry by 10:15)
      └─ 10:30: IB Complete → OR is historical context only
          ├─ Extension holds → IB Breakout (trend day)
          └─ Extension fails or no extension → Balance Day (B-Day/Edge Fade)
```

---

## Part 2: Opening Drive Classification

The first 5 minutes (9:30–9:35) establish the opening drive — critical for all OR strategies.

### Drive Types

| Drive | Formula | Meaning | Implication |
|-------|---------|---------|-------------|
| **DRIVE_UP** | (close - open) / range > 40% | Strong buying at open | Favor longs unless Judas detected |
| **DRIVE_DOWN** | (open - close) / range > 40% | Strong selling at open | Favor shorts unless Judas detected |
| **ROTATION** | Neither condition met | Two-sided, no conviction | Wait for EOR at 9:45–10:00 |

### How Drive Interacts with OR Strategies

- **DRIVE_UP + Sweep of overhead level** → Classic Judas UP → SHORT (sweep + reverse)
- **DRIVE_UP + No sweep, acceptance above level** → OR Acceptance LONG
- **DRIVE_DOWN + Sweep of low level** → Classic Judas DOWN → LONG (sweep + reverse)
- **DRIVE_DOWN + No sweep, acceptance below level** → OR Acceptance SHORT
- **ROTATION** → No immediate OR play — wait for 9:45 EOR resolution

---

## Part 3: Sweep Detection Deep Dive

Sweep detection is the foundation of OR Reversal. The quality of the sweep determines conviction level.

### Level Hierarchy (Priority Order)

1. **London High/Low** — Strongest institutional levels (European session)
2. **Asia High/Low** — Secondary institutional levels (Asian session)
3. **Overnight High/Low** — Composite of Asia + London
4. **PDH/PDL** — Previous Day High/Low (strong but not always relevant to OR)

Higher priority levels produce higher conviction OR Reversal signals.

### Closest-Match Logic

The OR Reversal module uses a **17% threshold** for level proximity:
- Distance to level / EOR range < 17% → "at level" (strong match)
- Distance > 17% → level not swept (could be acceptance instead)
- If multiple levels within threshold → use the **closest** match

### Sweep Depth as Quality Signal

| Depth (% of EOR) | Quality | Interpretation |
|-------------------|---------|----------------|
| > 2.0% | Deep sweep | Highest conviction — institutional liquidation run |
| 1.0–2.0% | Normal sweep | Standard Judas pattern |
| 0.5–1.0% | Shallow sweep | Moderate conviction — could be noise |
| < 0.5% | Marginal | Possible noise — wait for EOR confirmation |

### Dual-Sweep → BOTH Session

If price sweeps **both** a high and a low level during the OR/EOR:
- Classification: **BOTH** session
- Action: **NO OR PLAY** — sit out
- Rationale: Both bull and bear traps fired → highly unpredictable
- Transition: Wait for IB formation, shift to IB-based strategies

### Edge Cases in Sweep Detection

1. **Sweep within 2pts of level**: Could be noise (NQ typical tick noise). Require at least 3pts of penetration for conviction.

2. **Gap open beyond level**: If market opens above London High (gap up), there is no "sweep" — price was already there. This is NOT an OR Reversal setup. Check for OR Acceptance instead (acceptance above the level).

3. **Sweep during premarket (before 9:30)**: Not counted as OR sweep. OR sweep must occur within the 9:30–10:00 window. Premarket sweeps are premarket context only.

4. **Multiple level sweep in same direction**: If price sweeps London High AND Overnight High → strongest conviction OR Reversal (multiple stops hit).

5. **Sweep with immediate reclaim**: Sweep low → instant V-recovery within same bar → ambiguous. Wait for next bar confirmation.

### Sweep Failure Classification (How Levels Fail)

A "sweep" is not just one pattern — there are multiple ways a level can fail. Each has different conviction levels:

| Failure Type | Timeframe | Description | Conviction |
|-------------|-----------|-------------|------------|
| **Touch & Reject** | 1-min | Price touches level, immediate 1-min rejection wick | Moderate |
| **Close & Invert** | 5-min | 5-min bar closes above/below level, next bar inverts (closes opposite side) | High |
| **IFVG Confirmed** | 5-min | Inversion Fair Value Gap forms at the rejection — institutional speed rejection | Highest |
| **2×5-min Fail** | 5-min | 2×5-min prints close beyond level but 3rd bar fails to hold — false acceptance | High (anti-pattern) |
| **Retest & Fail** | 5-min | Level retested after initial rejection, fails again | High (double rejection) |

**Key confirmation**: Failure with **CISD** (Change In State of Delivery) — i.e., gap formation away from the level — is the strongest confirmation that the sweep/failure is real. A 5-min FVG forming away from the level = institutional commitment to the reversal.

---

## Part 4: OR Reversal (Judas Swing) — All Use Cases

The OR Reversal is the highest-expectancy first-hour pattern: 64.4% WR, 2.96 PF, $78,157 net profit over 266 sessions.

### Use Case 1: Classic Judas UP → SHORT

**Setup**: Market drives up in opening minutes, sweeps a premarket high (London/Asia/ON), then reverses below OR mid.

**Sequence** (matches `or_reversal.py` backtest):
1. 9:30–9:40: Price drives up, sweeps London High by 6-12pts (17% EOR threshold)
2. 9:40–9:45: Reversal begins — price falls back through OR mid
3. 9:45–10:00: EOR confirms — price continues lower, CVD declining
4. Entry: 50% retest level = `reversal_low + (eor_high - reversal_low) * 0.50`, tolerance band ±0.5×ATR
5. Stop: `entry + 2×ATR14` (actual backtest, NOT swept level + buffer)
6. Target: `entry - 2×risk` (2R)

**What LLM should say**:
> "Judas! Swept London High 21401 by 8pts at 9:38. Rejection type: 5-min close above and invert candle, IFVG confirmed. Reversing through OR mid 21385. OR Rev SHORT — 64.4% WR, 2.96 PF."

**Entry models available** (strategy suggests signal, multiple entry models may apply):
1. **50% retest** — Standard: wait for OR mid retest (21393)
2. **ICT Unicorn** — FVG + breaker block confluence at rejection zone
3. **5-min inversion candle** — Close beyond level then invert = immediate entry
4. **5-min IFVG** — Inversion FVG at sweep point = highest conviction entry
5. **BPR** — Balanced Price Range (overlapping FVGs) at sweep zone
6. **Trendline backside** — If sweep broke a trendline, backside retest = entry

The LLM should identify which rejection type occurred AND which entry models are viable. The backtest engine supports all of these as pluggable entry models (`models/entry_models.py`).

### Use Case 2: Classic Judas DOWN → LONG

**Setup**: Mirror of Case 1. Market drives down, sweeps a premarket low, reverses above OR mid.

**What LLM should say**:
> "Judas! Swept Asia Low 21298 by 5pts at 9:36. Rejection type: touch & reject with CISD gap away. Reversing through OR mid 21315. OR Rev LONG — 64.4% WR, 2.96 PF."

Same entry models apply (50% retest, ICT Unicorn, inversion candle, IFVG, BPR, trendline backside). LLM identifies rejection type and viable entries.

### Use Case 3: Deep Sweep (>2% of EOR Range)

Deep sweeps indicate aggressive institutional liquidation runs. These are the highest conviction setups.

**Example**: EOR range = 50pts, sweep depth = 12pts (2.4% of EOR)

**LLM observation**: "Deep Judas — swept London High by 12pts (2.4% EOR). Multiple stop clusters hit. Highest conviction OR Rev setup."

### Use Case 4: Shallow Sweep (<0.5% of EOR Range)

Shallow sweeps are ambiguous — could be genuine Judas or just noise.

**LLM observation**: "Marginal sweep — London High swept by 2pts only (0.4% EOR). Below conviction threshold. Wait for EOR confirmation before committing."

### Use Case 5: Failed Judas (Sweep but No Reversal)

Price sweeps a level but does NOT reverse through OR mid. Instead, it holds above (or below) the swept level.

**Transition**: Failed Judas → check for OR Acceptance on the breakout side.

**LLM observation**: "London High swept at 9:37, but no reversal — holding above 21401. Failed Judas. Flipping to OR Acceptance LONG — watching for 2×5-min acceptance above 21401."

### Use Case 6: Multiple Level Sweep (2+ Levels)

Price sweeps through 2 or more premarket levels in the same direction. This is the strongest Judas signal.

**Example**: Sweeps London High (21401) and Overnight High (21415) in same drive.

**LLM observation**: "Double sweep — both London High and ON High taken. Maximum stop liquidation. Strongest OR Rev SHORT conviction. 64.4% WR, 2.96 PF."

### Use Case 7: CVD Divergence Confirmation

If CVD (Cumulative Volume Delta) diverges from price at the sweep point, conviction increases.

**Example**: Price makes new high (sweeping London High), but CVD is declining → bearish divergence.

**LLM observation**: "CVD divergence at sweep — price swept London High but delta is declining. Smart money selling into the sweep. OR Rev SHORT confirmed with flow divergence."

### Use Case 8: FVG During Sweep (Institutional Speed)

A Fair Value Gap (FVG) forming during the sweep indicates institutional urgency — too fast for normal two-sided auction.

**LLM observation**: "FVG formed during London High sweep (5-min gap at 21398-21403). Institutional speed displacement. If reversed, expect strong continuation — OR Rev SHORT."

### Use Case 9: 50% Retest Entry Mechanics

The 50% retest is the standard entry method for OR Reversal:
- Calculate OR mid (50% of OR high-low range)
- Wait for price to retrace back to OR mid after reversing
- Entry at OR mid, stop above/below swept level
- If no retest within 30 bars → window closing, reduce conviction

**LLM observation**: "OR Rev SHORT confirmed. Waiting for 50% retest at 21393 (OR mid). 30-bar window from reversal. If no retest by 10:10, window expiring."

---

## Part 5: OR Acceptance — All Use Cases

OR Acceptance is the second-highest first-hour strategy: 59.9% WR, 1.46 PF, 137 trades.

### Use Case 1: Clean Acceptance LONG

**Setup**: Price breaks above a premarket level and holds with 2×5-min consecutive closes above it. No sweep detected.

**Sequence**:
1. Price breaks above London High 21401
2. First 5-min bar closes above 21401 (e.g., at 21408)
3. Second consecutive 5-min bar closes above 21401 (e.g., at 21412)
4. Acceptance confirmed → LONG
5. Entry: Limit at acceptance level (21401)
6. Target: 2R

**LLM observation**: "OR Acceptance LONG — 2×5-min close above London High 21401 (21408, 21412). Not a sweep — clean directional break. 59.9% WR, 1.46 PF. Limit entry at 21401."

### Use Case 2: Clean Acceptance SHORT

Mirror of Case 1 — 2×5-min close below a premarket level.

**LLM observation**: "OR Acceptance SHORT — 2×5-min close below Asia Low 21298 (21293, 21290). Clean breakdown. 59.9% WR, 1.46 PF."

### Use Case 3: Acceptance After Failed Judas

When a Judas sweep fails (no reversal), price may then accept above/below the swept level → becomes OR Acceptance.

**LLM observation**: "Failed Judas at London High — swept but no reversal. Now accepting above 21401 with 2×5-min holds. Transition: OR Acceptance LONG. 59.9% WR."

### Use Case 4: Multiple Level Acceptance

Price accepts through 2+ levels without sweeping any of them → strongest continuation signal.

**LLM observation**: "Multiple level acceptance — broke London High 21401 AND Overnight High 21415 with clean 5-min holds. Strong directional acceptance. OR Acceptance LONG."

### Use Case 5: BOTH Session — NO TRADE

If price swept both a high and a low level during the OR window → BOTH session.

**Critical rule**: NO OR PLAY. The session has whipsawed both sides.

**LLM observation**: "BOTH session detected — swept London High 21401 at 9:36 AND Asia Low 21298 at 9:42. Both bull and bear traps fired. No OR play. Wait for IB formation at 10:30."

### Use Case 6: Limit Retest Fill (30-Bar Window)

After acceptance is confirmed, enter on a limit order at the acceptance level:
- 30-bar window for the limit to fill (retest of level)
- If no fill within 30 bars → acceptance is strong (might chase, lower conviction)
- If immediate retest → standard fill, highest conviction

**LLM observation**: "OR Acceptance LONG confirmed at 21401. Limit set at 21401. 30-bar fill window. If no retest by 10:05, acceptance is very strong but entry is stale."

### Use Case 7: Level Hierarchy for Acceptance

Not all acceptances are equal. Level hierarchy matters:
- London High/Low acceptance → highest conviction
- Asia High/Low acceptance → high conviction
- Overnight High/Low acceptance → moderate conviction
- Random level → lowest conviction

**LLM observation**: "Accepting above London High 21401 (Tier 1 level) — highest conviction OR Acceptance. London levels represent institutional order flow."

---

## Part 6: IB Breakout — All Use Cases

IB Breakout fires after 10:30 when price extends beyond the Initial Balance with volume confirmation. Study stats: 74.56% WR, 2.51 PF, 114 trades.

**Key insight**: IB Breakout success → Trend Day. IB Breakout failure → Balance Day (B-Day/Edge Fade).

### Use Case 1: IB Breakout with Volume Spike

**Setup**: Price breaks above IBH (or below IBL) with volume > 1.5x average.

**LLM observation**: "IB Breakout LONG — price above IBH 21420 with 1.8x average volume spike. 74.56% WR, 2.51 PF. VWAP at 21405 (below price — confirming)."

### Use Case 2: Narrow IB Breakout (Highest Conviction)

Narrow IB (< 0.7x ATR) → compressed energy. When it breaks, the move is typically large.

**LLM observation**: "Narrow IB breakout — IB range 28pts (0.55x ATR). Compressed energy releasing. Highest conviction IB Breakout. Expect extended move."

### Use Case 3: Wide IB Breakout (Lower Conviction)

Wide IB (> 1.3x ATR) → most of the day's move may already be done.

**LLM observation**: "Wide IB breakout — IB range 85pts (1.7x ATR). Most of the move likely done. Lower conviction — scale down or wait for confirmation."

### Use Case 4: VWAP Position Filter

VWAP above/below price is a directional filter:
- VWAP below price for LONG breakouts → confirming
- VWAP above price for SHORT breakouts → confirming
- VWAP against direction → lower conviction

### Use Case 5: Delta Confirmation

Positive delta on upside breakout, negative delta on downside breakout → aligned.
Delta diverging from breakout direction → caution.

### Use Case 6: IB Breakout Failure → Balance Day

Extension attempt fails — price rejects back inside IB range.

**LLM observation**: "IB Breakout failed — extended 8pts above IBH but rejected back inside. Extension failure = Balance Day developing. Shift to B-Day/Edge Fade plays (46.4% WR, 1.47 PF). Fade IB edges, first touch only."

---

## Part 7: Edge Cases & Anti-Patterns

### 1. Pre-9:30 Gap Beyond All Levels

If the market gaps above ALL premarket highs (or below all lows):
- No sweep is possible — levels already behind price
- OR Reversal is NOT applicable
- Check for OR Acceptance or IB Breakout instead
- LLM: "Gap open above all premarket levels. No sweep possible. OR Rev N/A. Watching for OR Acceptance or IB Breakout."

### 2. Holiday / FOMC / CPI Volatility

High-impact events produce:
- Wider OR (often 2-3x normal)
- Unreliable sweep signals (fake moves pre-announcement)
- Best practice: Wait for event to pass, then assess
- LLM: "FOMC day — OR likely unreliable until announcement. Standing aside for OR strategies. Will re-assess at 14:30."

### 3. Overnight Range > 200pts

Extremely wide overnight range → premarket levels are very far from open:
- Sweep unlikely (levels too distant)
- If levels are > 50pts away, OR Rev probability drops significantly
- LLM: "ON range 245pts — premarket levels too far for OR sweep (London High 65pts away). OR Rev unlikely. Focus on IB Breakout plays."

### 4. False Acceptance (2× Close Then Immediate Reversal)

Price gets 2×5-min close above level, then immediately reverses:
- This is the acceptance FAILING — not a true acceptance
- The 2× close threshold is met, but the 3rd bar reverses hard
- LLM should track this: "Acceptance at 21401 appeared valid (2×5-min close) but 3rd bar reversed sharply. False acceptance — pattern invalidated."

### 5. Late OR (Sweep at 9:55–10:00)

Sweep occurring in the last 5 minutes of the EOR window:
- Reduced time for reversal to develop
- Lower conviction — the standard reversal window (9:45-10:15) is compressed
- LLM: "Late sweep at 9:57 — only 18 minutes of reversal window remaining. Reduced conviction OR Rev. Consider smaller size."

### 6. OR Reversal vs 80P Rule Conflict

If OR Rev fires SHORT but 80P Rule fires LONG (open below VA, accepting back in):
- **Time priority**: OR Rev fires first (9:30-10:15), 80P fires later (10:30+)
- If both active simultaneously: OR Rev takes priority during its window
- After OR Rev window closes (10:15): 80P takes over
- LLM: "OR Rev SHORT active (9:30-10:15) conflicts with developing 80P LONG. OR Rev has priority in its window. If OR Rev expires without entry, 80P becomes the play."

### 7. Narrow OR (<15pts for NQ)

Very narrow OR range (< 15pts):
- Insufficient range for meaningful entry/stop
- 50% retest is only ~7pts — easily hit by noise
- LLM: "OR range only 12pts — too narrow for reliable entry. 50% retest at 6pts is within noise. Stand aside for OR, wait for IB expansion."

---

## Part 8: Time-Phase Decision Tree

### 9:30–9:35: Opening Drive Developing

- Classify drive: DRIVE_UP / DRIVE_DOWN / ROTATION
- No decisions yet — just observe the initial move
- LLM: "Opening drive developing — currently DRIVE_UP, +18pts from open."

### 9:35–9:45: OR Locked, Sweep/Acceptance Classification

- OR range is established (high/low of 9:30-9:45)
- Check if any premarket levels were swept
- Check if any levels were cleanly broken (acceptance developing)
- LLM options:
  - "OR locked: 21375-21403. London High 21401 swept by 4pts. Monitoring for reversal."
  - "OR locked: 21375-21403. No sweep. Watching for 2×5-min acceptance above London High."
  - "OR locked: 21375-21403. ROTATION — no directional conviction yet."

### 9:45–10:00: EOR, Confirm/Deny OR Setup

- EOR extends the range (9:45-10:00)
- OR Rev: Has reversal confirmed? (price through OR mid)
- OR Accept: Has 2×5-min close confirmed?
- If neither: OR strategies likely dead for this session
- LLM: "EOR confirms OR Rev SHORT — reversed through OR mid 21389. 50% retest entry at 21393."

### 10:00–10:15: Last Chance for OR Reversal Entry

- OR Rev window closing at 10:15
- If no entry by 10:15, OR Rev is done
- 50% retest must occur within 30-bar window from reversal
- LLM: "10:05 — OR Rev SHORT confirmed but 50% retest hasn't occurred yet. 10 bars remaining in fill window."

### 10:15–10:30: OR Window Closing, Transition to IB

- OR Rev window CLOSED at 10:15
- OR Accept can still fire through 11:00
- IB formation becoming the primary context
- LLM: "10:20 — OR Rev window closed (no entry). OR Accept still possible through 11:00. IB forming: 28pts range (narrow)."

### 10:30: IB Complete — OR Is Historical Context Only

- IB is now the primary reference
- OR data becomes context for IB analysis (e.g., "OR sweep preceded this IB extension")
- All IB-based strategies now active: 80P, 20P, B-Day, Trend Following, Mean Reversion
- LLM: "IB complete at 10:30: range 45pts (0.9x ATR, normal). OR Rev SHORT was active — adds bearish context to IB read."

---

## Part 9: What the LLM Should Say — Example Outputs

### Pre-Sweep (9:35, Level Approaching)

```
"Watching London High 21401 — 12pts away. If swept and reversed, OR Rev SHORT.
Drive is UP so far (+22pts from open). Monitoring for Judas."
```

### Sweep Detected (9:38)

```
"Judas! Swept London High 21401 by 8pts at 9:38. Highest volume bar of the session.
If reversal through OR mid 21389, OR Rev SHORT fires. 64.4% WR, 2.96 PF.
Entry target: 50% retest at 21393. Stop above 21410."
```

### Acceptance Developing (9:40)

```
"NOT a sweep — clean break. First 5-min close above London High 21401 (closed 21408).
Need one more 5-min close above 21401 for OR Acceptance LONG confirmation.
If confirmed: 59.9% WR, 1.46 PF. Limit entry at 21401."
```

### BOTH Session (9:42)

```
"BOTH session — swept London High 21401 at 9:36 AND Asia Low 21298 at 9:42.
Both bull and bear traps fired. Messy auction — no OR play.
Wait for IB completion at 10:30 before taking any position."
```

### Failed OR (9:50)

```
"No sweep detected by 9:50. OR range: 21375-21403 (28pts).
OR Reversal unlikely at this point. Checking OR Acceptance — no 2×5-min holds either.
Shifting focus to IB Breakout and IB formation. Session open type: ROTATION."
```

### Late Session OR Context (11:00)

```
"OR context for IB analysis: Judas SHORT at 9:38 (swept London High, reversed).
OR Rev SHORT entered at 21393. This bearish OR context supports the developing
Trend Down day type. IB extension down confirms OR thesis."
```

### LLM Should Also Reference 20P/80P VA Context

When observing the OR and IB, the LLM should always mention how price relates to the **prior Value Area** and IB range — these frame the 80P and 20P strategies:

- **80P context**: "Open outside prior VA (below VAL 21350). If price accepts back inside VA, 80P LONG develops. IB range will confirm — narrow IB + VA acceptance = highest conviction."
- **20P context**: "IB extending above IBH. If 3×5-min acceptance holds above IBH, 20P extension LONG in play. Extension aligns with prior VA breakout."
- **IB as confirmation**: IB range width and direction confirm or deny VA plays. Narrow IB inside VA = balance. IB extending beyond VA = directional.

The LLM should weave these observations into the tape read even during the OR window — e.g., "OR Rev SHORT aligns with 80P setup (opening above VA, accepting back in)."

---

## Part 10: Deterministic Data Required for Each Pattern

### OR Reversal Module (`or_reversal`)

Currently provides:
- `or_high`, `or_low`, `or_mid` — OR range boundaries
- `eor_high`, `eor_low` — Extended OR boundaries
- `sweep_direction` — UP / DOWN / NONE / BOTH
- `closest_level` — which premarket level was swept
- `closest_level_distance` — how far from level
- `signal` — NONE / LONG / SHORT

### Tape Context Module (`tape_context.session_open_type`)

Currently provides:
- `classification` — acceptance / judas / rotation / both
- Based on first 15 minutes of price action vs premarket levels
- Confirms or adds context to `or_reversal.signal`

### What's Currently Missing (Future Enhancements)

1. **OR Acceptance detection in deterministic module** — Currently only in strategy code. Need:
   - `or_acceptance.signal`: NONE / LONG / SHORT
   - `or_acceptance.acceptance_level`: which level was accepted
   - `or_acceptance.acceptance_count`: number of consecutive 5-min closes
   - `or_acceptance.both_session`: true/false

2. **Sweep depth percentage** — `or_reversal` has distance but not as % of EOR range. Easy to compute:
   - `sweep_depth_pct` = closest_level_distance / eor_range

3. **Drive classification** — Not computed in deterministic module:
   - `opening_drive.type`: DRIVE_UP / DRIVE_DOWN / ROTATION
   - `opening_drive.magnitude`: (close - open) / range of first 5 minutes

4. **CVD at sweep point** — Not available (requires tick data, not in 1-min CSV)

5. **FVG during sweep** — Available from `fvg_detection` module but not cross-referenced with OR timing

6. **IB Breakout detection** — Not computed in deterministic module:
   - `ib_breakout.signal`: NONE / LONG / SHORT
   - `ib_breakout.volume_ratio`: volume vs average
   - `ib_breakout.vwap_confirming`: true/false
   - `ib_breakout.failed`: true/false (extension rejected back inside IB)

### Priority for Implementation

| Enhancement | Priority | Complexity | Impact |
|-------------|----------|------------|--------|
| OR Acceptance detection | HIGH | Medium | Enables OR Accept in tape_observations |
| Opening drive classification | HIGH | Low | 5-line computation |
| Sweep depth percentage | MEDIUM | Low | 1-line computation |
| IB Breakout detection | MEDIUM | Medium | New strategy module needed |
| FVG cross-reference at sweep | LOW | Medium | Requires timing alignment |
| CVD at sweep | LOW | High | Needs tick data source |

---

## Appendix A: Quick Reference Card

```
OR STRATEGIES — DECISION FLOW
==============================

1. DID PRICE SWEEP A PREMARKET LEVEL?
   ├─ YES → OR Reversal candidate
   │   ├─ Reversed through OR mid? → CONFIRMED (64.4% WR, 2.96 PF)
   │   └─ Held beyond level? → FAILED → check OR Acceptance
   │
   ├─ NO → Check acceptance
   │   ├─ 2×5-min close above/below? → OR Acceptance (59.9% WR, 1.46 PF)
   │   └─ No clear direction → ROTATION (wait)
   │
   └─ BOTH SIDES SWEPT → No OR play. Wait for IB.

2. TIME WINDOWS
   9:30-9:45   OR forming (observe only)
   9:35-9:45   Sweep/acceptance classification
   9:45-10:00  EOR confirmation
   10:00-10:15 Last OR Rev entry window
   10:15-10:30 OR closing, IB forming
   10:30+      IB is law, OR is context

3. CONVICTION MODIFIERS
   Deep sweep (>2% EOR)     → +conviction
   Multiple levels swept     → +conviction
   CVD divergence at sweep   → +conviction
   FVG during sweep          → +conviction
   Shallow sweep (<0.5%)     → -conviction
   Late sweep (>9:55)        → -conviction
   Narrow OR (<15pts)        → -conviction
   Gap beyond all levels     → OR Rev N/A
```

## Appendix B: Training Pair Examples — Key Snapshots

### What Makes a Good OR Training Pair

For each session date with OR activity, we need training pairs at these critical times:
- **9:35** — OR forming, drive classification
- **9:45** — OR locked, sweep/acceptance detected or not
- **10:00** — EOR complete, OR strategies confirmed/denied
- **10:15** — OR Rev window closing, final status
- **10:30** — IB complete, OR becomes context

Each pair should show the LLM observing the tape (not making trade decisions) and citing specific numbers from the snapshot.

### Anti-Pattern Training Examples

These are important "what NOT to do" examples:
1. **Don't chase**: "London High swept → immediately short" (wrong — wait for reversal confirmation)
2. **Don't ignore BOTH**: "Swept high and low → pick the stronger one" (wrong — sit out BOTH sessions)
3. **Don't override time windows**: "10:20 OR Rev SHORT" (wrong — window closed at 10:15)
4. **Don't ignore PF**: "Mean Reversion at BB extreme" (need to warn about 0.91 PF)
5. **Don't be uber-bullish at highs**: "Strong DRIVE_UP → max long" (wrong — could be Judas setup)

---

## Part 11: Post-IB Strategy Observations (80P, 20P, B-Day, Mean Reversion)

All of these activate at 10:30+ once IB is complete. The LLM should weave them together — they're not isolated plays.

### 80P Rule (Return to Balance) — 42.3% WR, 1.74 PF, 71 trades

**What the backtest actually does** (`eighty_percent_rule.py`):
- **Detection**: Open outside prior VA (above VAH or below VAL). VA width ≥ 25pts required
- **Entry model**: 30-bar (30-min) candle acceptance back inside VA. Entry at acceptance candle close
- **Alternative entry**: 100% retest (double top/bottom after acceptance)
- **Stop**: VA edge ± 10pts fixed buffer (LONG: `prior_val - 10`, SHORT: `prior_vah + 10`)
- **Target**: Configurable — 2R (default), 4R, opposite VA edge, or POC
- **Cutoff**: No new entries after 13:00 ET

**LLM observation pattern**: "Open below VAL 21350 (outside VA). 30-min candle at 10:45 closed at 21358 (inside VA). 80P LONG acceptance confirmed. 42.3% WR, 1.74 PF. Entry 21358, stop 21340, target 2R at 21394."

### 20P IB Extension — Disabled (needs port from study)

**What the backtest actually does** (`twenty_percent_rule.py`):
- **Detection**: Price extends > 20% of IB range beyond IBH or IBL
- **Entry model**: 3×5-min consecutive closes beyond IB boundary + delta confirmation
- **Stop**: `entry ± 2×ATR14`
- **Target**: 2R
- **Cutoff**: No new entries after 14:00 ET
- **Filter**: Requires moderate+ trend strength

**LLM observation pattern**: "IB extension UP — 35pts beyond IBH (28% of IB range). 2 of 3 required 5-min acceptances above IBH. Watching for 3rd close. Delta positive — confirming."

### B-Day (Balance Day IBL Fade) — 46.4% WR, 1.47 PF, 84 trades

**What the backtest actually does** (`b_day.py`):
- **Detection**: Balance/neutral/P-Day type classification. First IBL touch (within 5pts tolerance)
- **Entry model**: Wait 30 bars (30 min) after first touch. If close > IBL at bar 30 → LONG
- **Critical rule**: First touch ONLY. 2nd/3rd touches degrade to ~35% WR
- **Stop**: `IBL - (IB_range × 0.10)` (10% of IB range below IBL)
- **Target**: IB midpoint (mean reversion to POC/VWAP area)
- **Confidence boost**: VWAP > IB mid = high confidence
- **R:R filter**: Skip if risk/reward > 2.5

**LLM observation pattern**: "Balance Day — first IBL touch at 11:15. VWAP at 21410 > IB mid 21405 (high confidence). Waiting 30 bars for acceptance. If close > IBL at 11:45 → B-Day LONG. 46.4% WR, 1.47 PF. First touch only — do NOT take 2nd touch."

### Mean Reversion VWAP — 42.6% WR, 0.91 PF, 155 trades (LOSING)

**What the backtest actually does** (`mean_reversion_vwap.py`):
- **Detection**: Price deviates ≥ 0.6× IB range from VWAP on balance/neutral/P-Day
- **Entry model**: RSI exhaustion (>65 short, <35 long) + delta reversal + declining volume + reversal candle
- **Stop**: Beyond deviation extreme + 0.25× IB range (min 12pts)
- **Target**: VWAP (the mean)
- **Cutoff**: 11:00–14:30 only. Max 2 entries/session. 15-bar cooldown between entries
- **REGIME-GATED**: Only on range-bound days. ADX < 20 or balance/neutral day type

**LLM observation pattern**: "WARNING: Mean Reversion VWAP — 42.6% WR, 0.91 PF. LOSING strategy. Price 45pts above VWAP (0.9× IB range). RSI 72 (overbought). If this is a balance day with ADX < 20, MR SHORT is in play but use minimum size. If trending (ADX > 25), MR is disabled."

### Edge Case: March 4 "Sweep-Reclaim" Pattern

Unique pattern: price sweeps a level, fails to reverse (failed Judas), but then the sweep candle itself gets reclaimed from below. Price eventually accepts the level from the opposite direction.

This is a **transition pattern**: Failed Judas → messy intermediate → eventual OR Acceptance. The LLM should not force a classification — just describe what's happening: "Sweep at 9:37 failed to reverse. The green candle that swept high got its low taken at 9:41. Now reclaiming — watching for acceptance. Messy, but price is showing intention to accept London High."

---

## Part 12: Reusable Entry Model Architecture

### The Problem

Currently each strategy **hardcodes** its entry/stop/target logic. OR Reversal always uses 50% retest + 2×ATR stop + 2R target. 80P always uses 30-bar acceptance + 10pt buffer stop.

But a strategy might be **right about the signal** while using a **suboptimal entry model**. If we decouple signal detection from execution, we can backtest every combination and find the best pairings.

### The Architecture

```
STRATEGY (signal detection)     ──→  Signal(direction, setup_type, metadata)
                                          │
ENTRY MODEL (how to get in)     ←─────────┤
                                          │
STOP MODEL (where to protect)   ←─────────┤
                                          │
TARGET MODEL (where to exit)    ←─────────┘
```

A strategy detects the pattern and emits a signal. The entry model determines HOW to enter. The stop and target models determine WHERE to protect and exit. All three are interchangeable.

### Entry Models Catalog

These are the reusable entry models. Each can be paired with ANY strategy signal.

| # | Entry Model | Description | Inputs Required | Current Usage | Confidence |
|---|------------|-------------|-----------------|---------------|------------|
| 1 | **50% Retest** | Wait for 50% pullback to entry zone | Swing high/low, tolerance band | OR Reversal (hardcoded) | 0.70 |
| 2 | **N-Bar Acceptance** | N consecutive closes beyond level (configurable: 2×5-min, 3×5-min, 30×1-min) | Level, bar count, timeframe | OR Accept (2×5m), 20P (3×5m), 80P (30×1m) | 0.65 |
| 3 | **Limit at Level** | Limit order at acceptance/rejection level, fill within N-bar window | Level, window size | OR Acceptance (hardcoded) | 0.65 |
| 4 | **100% Retest (Double Top/Bottom)** | After acceptance, wait for full retest of extreme | Acceptance candle extreme | 80P (alternative, `entry_models.py:249`) | 0.60 |
| 5 | **ICT Unicorn** | FVG + breaker block overlap zone | Nearest FVG, nearest breaker | Exists in `entry_models.py:166` (unused) | 0.75 |
| 6 | **5-min Inversion Candle** | Bar closes beyond level, next bar inverts = entry on inversion close | Level, 5-min bars | Not implemented | 0.70 |
| 7 | **IFVG (Inversion FVG)** | Inversion Fair Value Gap at rejection point = institutional speed entry | FVG detection at level | Exists in `stop_models.py:64` (stop only) | 0.75 |
| 8 | **BPR (Balanced Price Range)** | Overlapping FVGs form re-entry zone | BPR zones from `fvg_detection` | Exists in `entry_models.py:384` (unused) | 0.70 |
| 9 | **Trendline Backside** | Breakout, then retest broken trendline from other side | Trendline data | Exists in `entry_models.py:313` (unused) | 0.65 |
| 10 | **OrderFlow CVD** | Delta > 70% + price vs VWAP alignment | CVD, VWAP | Exists in `entry_models.py:16` (unused) | 0.70 |
| 11 | **TPO Rejection** | Single print rejection from IB edge | IB high/low, TPO data | Exists in `entry_models.py:56` (unused) | 0.65 |
| 12 | **Liquidity Sweep** | Sweep prior session high/low then reverse with delta | Prior session H/L, delta | Exists in `entry_models.py:91` (unused) | 0.70 |
| 13 | **RSI + BB Exhaustion** | RSI extreme + Bollinger Band touch + reversal candle | RSI14, BB(20,2), candle pattern | Mean Reversion (hardcoded) | 0.55 |
| 14 | **FVG Pullback** | Retest of bullish/bearish FVG zone after breakout | FVG zones from detection module | Trend Bull (hardcoded) | 0.65 |
| 15 | **VWAP Pullback** | Touch VWAP after breakout, bounce = continuation entry | VWAP, breakout direction | Trend Bull (hardcoded) | 0.60 |
| 16 | **EMA Pullback** | Touch EMA20/50 after breakout, hold = continuation entry | EMA20/50, breakout direction | Trend Bull (hardcoded) | 0.60 |
| 17 | **IBH/IBL Retest** | Retest of IB edge as support/resistance after breakout | IB high/low | Trend Bull (hardcoded) | 0.65 |

### Stop Models Catalog

| # | Stop Model | Description | Formula | Current Usage |
|---|-----------|-------------|---------|---------------|
| 1 | **N×ATR** | ATR-scaled stop | `entry ± N×ATR14` | OR Rev (2×), OR Accept (0.5×), 20P (2×) |
| 2 | **Fixed Buffer** | Fixed points beyond structure | `level ± N pts` | 80P (10pts beyond VA edge) |
| 3 | **IB Range %** | Percentage of IB range | `IB_edge ± (IB_range × N%)` | B-Day (10% below IBL) |
| 4 | **LVN/HVN** | Below/above IB edge with buffer | `IB_edge ± (IB_range × 0.10)` | Exists in `stop_models.py:37` |
| 5 | **IFVG** | Beyond nearest inverse FVG | `entry ± 1.5×ATR` (fallback) | Exists in `stop_models.py:64` |
| 6 | **Deviation Extreme** | Beyond price extreme + buffer | `extreme ± (IB_range × 0.25)` | Mean Reversion |
| 7 | **Structure (FVG/VWAP/EMA)** | Below key structure with % buffer | `structure - (IB_range × 0.25-0.50)` | Trend Bull (4-tier hierarchy) |
| 8 | **Minimum Floor** | Hard minimum stop distance | `max(computed_stop, entry ± MIN_PTS)` | Mean Rev (12pts), Trend (15pts) |

### Target Models Catalog

| # | Target Model | Description | Formula | Current Usage |
|---|-------------|-------------|---------|---------------|
| 1 | **N×R Multiple** | Fixed risk multiple | `entry ± N×risk` | OR Rev (2R), OR Accept (2R), 80P (2R/4R) |
| 2 | **N×ATR** | ATR-based target | `entry ± N×ATR14` | Exists in `target_models.py:45` |
| 3 | **Opposite Structure** | Target opposite VA edge or IB edge | `prior_vah` or `prior_val` | 80P (configurable) |
| 4 | **POC/VWAP** | Target the mean | `prior_poc` or `vwap` | 80P (POC mode), B-Day (IB mid), Mean Rev (VWAP) |
| 5 | **IB Multiple** | Target N× IB range | `entry ± N×IB_range` | Trend Bull (1.5-2.5×), `target_models.py:132` |
| 6 | **Trail to BE + FVG** | Trail stop to breakeven at 1R, then by FVG zones | Activation at 1R | Exists in `target_models.py:75` |
| 7 | **Trail to BE + BPR** | Trail stop to breakeven at 1R, then by BPR zones | Activation at 1R, 3R initial | Exists in `target_models.py:104` |

### Backtest Combination Matrix

The goal: test every entry model × stop model × target model combination for each strategy signal.

```
Strategy Signal    × Entry Model      × Stop Model    × Target Model
─────────────────────────────────────────────────────────────────────
OR Reversal          50% Retest         2×ATR           2R          ← current
OR Reversal          ICT Unicorn        2×ATR           2R          ← test
OR Reversal          IFVG               1×ATR           3R          ← test
OR Reversal          BPR                LVN/HVN         Trail BE+FVG ← test
...
80P Rule             30-bar Accept      Fixed 10pt      2R          ← current
80P Rule             30-bar Accept      1×ATR           Opposite VA ← test
80P Rule             100% Retest        Fixed 10pt      4R          ← test
...
```

**Key hypothesis**: A strategy like OR Reversal with 64.4% WR and 2.96 PF might go to 70%+ WR with a better entry model (e.g., IFVG confirmation instead of 50% retest). Or a wider stop (2.5×ATR) might reduce stopped-out-then-right trades.

### Implementation Plan

1. **Refactor entry/stop/target into truly pluggable components** — Each strategy's `on_bar()` emits a raw Signal (direction + setup context). The engine pairs it with the configured entry/stop/target models
2. **Config-driven model selection** in `strategies.yaml`:
   ```yaml
   or_reversal:
     enabled: true
     entry_model: "50pct_retest"  # or "ict_unicorn", "ifvg", "bpr"
     stop_model: "2_atr"          # or "1_atr", "lvn_hvn", "fixed_10"
     target_model: "2r"           # or "3r", "trail_be_fvg", "opposite_va"
   ```
3. **Grid search runner** — Backtest all combinations for each strategy, output comparison CSV
4. **New entry models to implement**:
   - `5min_inversion_candle` — Close & invert pattern
   - `ifvg_entry` — Entry at IFVG formation (currently only stop model)
   - `n_bar_acceptance` — Generalized acceptance (parameterized bar count + timeframe)
   - `50pct_retest` — Extract from OR Reversal into reusable model

### LLM Role in Entry Model Selection

The LLM reads the tape and identifies which entry models are viable for the current signal. It does NOT choose — the strategy runner + agent pipeline decides. But the LLM provides context:

> "OR Rev SHORT confirmed. Rejection type: Close & Invert with IFVG forming at 21403. Viable entry models: (1) 50% retest at 21393 — standard, (2) IFVG entry at 21403 — highest conviction, (3) BPR zone if overlapping FVGs form. Strategy runner selects entry model."

---

## Part 13: Accuracy Check — Backtest vs Brainstorm

This section ensures the brainstorm does NOT deviate from what the backtest actually computes.

### OR Reversal — Verified Against `or_reversal.py`

| Parameter | Brainstorm Says | Backtest Actually Does | Match? |
|-----------|----------------|----------------------|--------|
| Sweep threshold | 17% of EOR range | `SWEEP_THRESHOLD_RATIO = 0.17` | Yes |
| Entry | 50% retest of OR mid | `fifty_pct = reversal_low + (eor_high - reversal_low) * 0.50` with ±0.5×ATR tolerance | Yes |
| Stop | 2×ATR | `entry ± ATR_STOP_MULT × atr14` where `ATR_STOP_MULT = 2.0` | Yes |
| Target | 2R | `entry ± 2×risk` | Yes |
| Window | 9:30-10:15 | OR_BARS=15, EOR_BARS=30, processes during IB | Yes |
| Drive threshold | 40% | `DRIVE_THRESHOLD = 0.4` | Yes |

### OR Acceptance — Verified Against `or_acceptance.py`

| Parameter | Brainstorm Says | Backtest Actually Does | Match? |
|-----------|----------------|----------------------|--------|
| Acceptance bars | 2×5-min | `ACCEPT_5M_BARS = 2` | Yes |
| Entry | Limit at acceptance level | `entry_price = level` (limit order sim) | Yes |
| Stop | 0.5×ATR | `ATR_STOP_MULT = 0.5`, min 3pts, max 40pts | Yes |
| Target | 2R | `level ± 2×risk` | Yes |
| Fill window | 30 bars | `RETEST_WINDOW = 30` | Yes |
| BOTH filter | Skip dual-sweep sessions | Implemented lines 162-194 | Yes |

### 80P Rule — Verified Against `eighty_percent_rule.py`

| Parameter | Brainstorm Says | Backtest Actually Does | Match? |
|-----------|----------------|----------------------|--------|
| Acceptance | 30-bar candle | `ACCEPT_30M_BARS = 30` (30×1-min) | Yes |
| Stop | VA edge ± 10pts | `STOP_BUFFER_PTS = 10.0` | Yes |
| Target | 2R (default) | `TARGET_MODE = '2R'`, also supports 4R/POC/opposite_va | Yes |
| Min VA width | 25pts | `MIN_VA_WIDTH = 25.0` | Yes |
| Cutoff | 13:00 | `ENTRY_CUTOFF = time(13, 0)` | Yes |

### B-Day — Verified Against `b_day.py`

| Parameter | Brainstorm Says | Backtest Actually Does | Match? |
|-----------|----------------|----------------------|--------|
| Touch tolerance | 5pts | `BDAY_TOUCH_TOLERANCE = 5` | Yes |
| Acceptance | 30 bars after first touch | `BDAY_ACCEPTANCE_BARS = 30` | Yes |
| Stop | IBL - 10% IB range | `BDAY_STOP_IB_BUFFER = 0.1` | Yes |
| Target | IB midpoint | `ib_mid` | Yes |
| First touch only | Yes | Implemented (resets after failed, but doesn't re-trigger) | Yes |
| R:R filter | Skip if > 2.5 | Lines 118-122 | Yes |

### Mean Reversion — Verified Against `mean_reversion_vwap.py`

| Parameter | Brainstorm Says | Backtest Actually Does | Match? |
|-----------|----------------|----------------------|--------|
| Deviation | ≥ 0.6× IB range from VWAP | `MIN_DEVIATION_MULT = 0.60` | Yes |
| RSI thresholds | >65 short, <35 long | `RSI_OVERBOUGHT = 65.0`, `RSI_OVERSOLD = 35.0` | Yes |
| Stop | Extreme + 0.25× IB range | `STOP_BUFFER_MULT = 0.25`, min 12pts | Yes |
| Target | VWAP | `vwap` | Yes |
| Window | 11:00-14:30 | `ENTRY_START = time(11, 0)`, `ENTRY_CUTOFF = time(14, 30)` | Yes |
| Max entries | 2/session | `MAX_ENTRIES_PER_SESSION = 2` | Yes |
| Cooldown | 15 bars | `COOLDOWN_BARS = 15` | Yes |
| Day types | Balance/neutral/P-Day | `ALLOWED_DAY_TYPES = ['b_day', 'neutral', 'p_day']` | Yes |

All brainstorm parameters verified against actual backtest code. No deviations found.

---

## Part 14: Missing Deterministic Data (Updated)

Adding to the Part 10 priority table based on new observations:

| Enhancement | Priority | Complexity | Impact |
|-------------|----------|------------|--------|
| OR Acceptance detection | HIGH | Medium | Enables OR Accept in tape_observations |
| Opening drive classification | HIGH | Low | 5-line computation |
| Sweep failure type classification | HIGH | Medium | Enables rejection type in LLM output |
| Premarket conviction score | HIGH | Medium | London range %, liquidity channel, overlap % |
| Sweep depth percentage | MEDIUM | Low | 1-line computation |
| IB Breakout detection + failure | MEDIUM | Medium | New deterministic module |
| CISD detection at sweep | MEDIUM | Medium | Cross-reference FVG timing with OR timing |
| Entry model viability flags | LOW | High | Which entry models are available for current signal |
| CVD at sweep point | LOW | High | Needs tick data source |



TODO FOR TRADER:
1. go through premarket reasoning, what are you looking for
2. go through 9:30-10:30, reasoning what are you looking for, as advocate and skeptic
3. 10:30 to 11:00 why important - reasoning, what are you looking for
4. 12:30 to 13:00 why important  - london closing
5. 13:00 pm trading hard to reverse

I want to go through and teach llm how to pull in deterministic data along with the strategy observations