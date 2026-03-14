# 15 — Daily Trading Plan: NQ Futures

> **Purpose**: Structured playbook for each trading day — when to watch, what to expect, how to execute.
> Based on 274 sessions, 734 trades, 12 strategies, PF 3.28, +$539K backtested.
>
> **Date**: 2026-03-14
> **Benchmark run**: `NQ_20260314_111555_3d383b`

---

## 1. Session Timeline — When Strategies Fire

The trading day has 4 distinct phases. Each phase has specific strategies active and specific things to watch for.

```
 PRE-MARKET     PHASE 1: FIRST HOUR        PHASE 2: MID-SESSION      PHASE 3: PM
 ─────────── ────────────────────────────── ──────────────────────── ────────────
 before 9:30  9:30 ──── 10:00 ──── 10:30    10:30 ────── 12:00      12:00 ── 15:00
    |            |          |          |        |            |          |        |
  Briefing    OR forms   EOR/IB    IB Close   Main Window   Lunch     PM/Wind Down
    |            |          |          |        |            |          |        |
  NDOG fires  PDH/PDL   PDH/PDL   OR Rev     80P Rule     B-Day      (most     EOD
  NWOG fires  starts    continues  OR Accept  20P IB Ext   VA Edge    done by   exits
              looking             IB Edge Fade Trend Bull   Fade       13:00)
                                  B-Day starts Trend Bear
```

### Phase 0: Pre-Market (before 9:30)

**Active strategies**: NDOG Gap Fill, NWOG Gap Fill (pre-IB entry)

| Action | Details |
|--------|---------|
| Check overnight gap | NDOG fires at 9:30 on gaps ≥ 20pts (57.1% WR, PF 1.96, 70 trades) |
| Check weekly gap | NWOG fires Mondays only on gaps ≥ 20pts (65.0% WR, PF 5.02, 20 trades) |
| Set bias | Load prior session bias from DuckDB. Bias alignment = #1 predictor |
| Review levels | PDH, PDL, prior VAH, prior VAL, prior POC — rank by proximity to current price |
| Note overnight structure | London expansion? Asia rejection? Compression ratio? |

**Key rule**: Gap fill strategies fire automatically. Don't override — they have the highest WR and PF in the portfolio.

### Phase 1: The First Hour (9:30 — 10:30)

This is where **60% of total PnL** is generated. OR Rev + OR Accept alone account for $279K of $539K total.

#### Phase 1A: Opening Range (9:30 — 9:45)

**Watch for**: Opening drive direction, sweep of London/Asia levels, OR high/low forming.

**No strategies fire yet** — this is reconnaissance. The engine is building the OR.

**Checklist**:
- [ ] Which direction is the opening drive? (Up vs down vs flat)
- [ ] Did price sweep a key overnight level? (Judas swing setup for OR Rev)
- [ ] Is delta confirming the drive or diverging?

#### Phase 1B: Extended Opening Range (9:45 — 10:00)

**Watch for**: OR reversal confirmation, OR acceptance continuation, PDH/PDL touch.

**PDH/PDL Reaction** starts looking for entries here (52.9% WR, PF 3.59, $47.5K). If price touches PDH or PDL with a failed auction + rejection, the signal fires.

#### Phase 1C: IB Formation (10:00 — 10:30)

**Watch for**: IB range building (narrow < 100pt = compression, wide > 200pt = directional), TPO shape forming, VA position vs prior day.

**PDH/PDL Reaction** continues active. Most PDH/PDL entries are 10:00-10:30 (41 of 51 trades in the 10:xx bucket, 53.7% WR).

#### Phase 1D: IB Close (10:30) — THE PIVOT POINT

**THIS IS THE SINGLE BIGGEST MOMENT.** At 10:30, IB locks in and multiple strategies fire simultaneously:

| Strategy | What It Looks For | When It Fires | Trail? |
|----------|-------------------|---------------|--------|
| **Opening Range Rev** | OR sweep + reversal confirmed | Immediately at 10:30 | YES (1.5x ATR activate, 0.5x trail) |
| **OR Acceptance** | Level break + acceptance confirmed | Immediately at 10:30 | YES (1.5x ATR activate, 0.5x trail) |
| **IB Edge Fade** | IBL poke + rejection back inside (LONG only) | 10:30-10:45 typically | NO |
| **80P Rule** | Open above VA + 30-bar acceptance back inside (SHORT only) | 10:30-11:00 | NO |
| **Trend Day Bear** | IBL acceptance + EMA alignment + ADX≥35 + bearish bias | 10:30-11:30 | NO |

**Decision tree at 10:30**:
```
IB closes → Classify day type
  │
  ├── Narrow IB (< 100pt) + initiative → Compression. Watch for 20P extension.
  │
  ├── Wide IB (> 200pt) + directional → Trend developing. Trend Bull/Bear territory.
  │
  ├── IB balanced + open inside prior VA → Balance day. B-Day + IB Edge Fade.
  │
  ├── IB extension above → Check OR Rev (if sweep happened), OR Accept (if continuation)
  │
  └── Price returning inside prior VA → 80P Rule territory (SHORT if opened above)
```

### Phase 2: Mid-Session (10:30 — 12:00)

**The main trading window.** Most strategies that fire in the first 90 min after IB close.

| Strategy | Active Window | Best Hour | Trades/Hour WR |
|----------|---------------|-----------|---------------|
| OR Rev | 10:30 only | 10:xx | 77.9% |
| OR Accept | 10:30 only | 10:xx | 59.4% |
| 80P Rule | 10:30-11:00 | 10:xx (44%) / 11:xx (62.5%) | 11:xx is best |
| IB Edge Fade | 10:30-13:00 | 10:xx (50%) / 12:xx (60%) | Morning slightly better |
| Trend Bull | 10:30-12:00 | 11:xx (50%) | Needs time to confirm trend |
| Trend Bear | 10:30-11:30 | 10:xx (69.2%) | Early fires are best |
| B-Day | 11:00-13:00 | 11:xx (53.7%) | Waits for IB to establish range |
| PDH/PDL | 10:00-11:30 | 10:xx (53.7%) | Morning entries dominate |
| 20P IB Extension | 10:30-12:30 | 12:xx (60%) | Extensions develop later |
| VA Edge Fade | 10:30-13:00 | 10-12 (50%) each | Evenly spread |

**Key rules**:
- If OR Rev or OR Accept fired with trailing → **let the trail manage the exit**. Don't intervene.
- If Trend Bear fires at 10:30 with 69.2% WR → high confidence. If it fires at 11:30+ → WR drops to 30%.
- B-Day doesn't typically fire until 11:00 — don't force it earlier.

### Phase 3: Afternoon (12:00 — 15:00)

**Wind-down.** Most strategies have fired or won't fire. Main activity:

- **Manage open positions** — trail stops ratcheting on OR Rev/Accept winners
- **20P IB Extension** may still fire (12:xx has 60% WR but only 5 trades)
- **VA Edge Fade** can still fire (12:xx 50% WR, 13:xx 42.9% — marginal)
- **EOD exits** at 15:00 for any remaining positions

**Key rule**: After 13:00, be very selective. Most strategy edges degrade in the afternoon.

---

## 2. Strategy Interaction Rules

### Conflicting Signals

Multiple strategies can fire on the same session. Rules for managing overlap:

| Scenario | Resolution |
|----------|------------|
| OR Rev LONG + Trend Bear SHORT same session | Take OR Rev (fires first, higher PF). Trend Bear blocked by bias check. |
| 80P SHORT + OR Accept LONG | Contradictory. Bias alignment filter resolves — one is counter-bias and blocked. |
| PDH/PDL + IB Edge Fade same level | Both can fire — they target different setups at the same level. OK to take both. |
| NDOG gap fill + OR Rev same session | NDOG fires at 9:30, OR Rev at 10:30. Sequential, no conflict. |
| Trend Bull + B-Day same session | Trend Bull fires on IBH acceptance (directional), B-Day fires on mean reversion. Mutually exclusive by market structure. |

### Position Limits

- **Max 2 concurrent positions** (risk management)
- **Max 1 position per strategy per session**
- **Max daily loss**: $4,000 (2 NQ full stops)
- After 2 consecutive losses in a session → stop trading that session

### Profit Taking by Strategy Type

| Type | Strategies | Exit Method | Trail? |
|------|-----------|-------------|--------|
| **Reversal** | OR Rev, OR Accept | ATR trailing (1.5x activate, 0.5x trail) | YES |
| **Zone fill** | NDOG, NWOG, 80P | Fixed target (gap close, POC, VA) | NO — must reach target |
| **Edge fade** | VA Edge Fade, IB Edge Fade | Fixed R-multiple (3R, 2R) | NO — outsized winners need room |
| **Trend** | Trend Bull, Trend Bear | Fixed target (100pt, 125pt) | NO — trend days need patience |
| **Level reaction** | PDH/PDL | Fixed R-multiple (2R) with spike stop | NO — outsized winners ($2,508 avg) |
| **Extension** | 20P IB Extension | Fixed R-multiple (2R) | NO — extension plays need to run |
| **Mean reversion** | B-Day | Fixed target (IB opposite) | NO — reversion needs room to oscillate |

---

## 3. Day Type Playbook

The day type classification at 10:30 determines which strategies are primary.

### Trend Day (Up or Down)

**Characteristics**: Wide IB (>150pt), strong initiative, one-directional TPO, ADX > 25

| Priority | Strategy | Direction | Notes |
|----------|----------|-----------|-------|
| 1 | OR Rev / OR Accept | With trend | Highest PF, trailing captures extended move |
| 2 | Trend Bull or Trend Bear | With trend | 100-125pt target, needs EMA alignment |
| 3 | 20P IB Extension | With trend | Extension beyond IB |
| AVOID | B-Day, 80P, IB Edge Fade | — | Mean reversion loses on trend days |

### Balance Day / Neutral Range

**Characteristics**: Balanced IB, no strong initiative, B-shape TPO, price inside prior VA

| Priority | Strategy | Direction | Notes |
|----------|----------|-----------|-------|
| 1 | B-Day | Both | Mean reversion to IB boundaries (53.8% WR) |
| 2 | IB Edge Fade | LONG only | IBL rejection fade (47.7% WR, min IB 150pt) |
| 3 | 80P Rule | SHORT only | If opened above VA + 30-bar acceptance |
| 4 | VA Edge Fade | SHORT only | VAH rejection with 3 accept bars + bearish bias |
| AVOID | Trend Bull, Trend Bear | — | No directional conviction on balance days |

### P-Day (Up or Down)

**Characteristics**: Moderate IB extension (0.5-1.0x), skewed structure

| Priority | Strategy | Direction | Notes |
|----------|----------|-----------|-------|
| 1 | OR Rev / OR Accept | Either | Still fire well on P-days |
| 2 | PDH/PDL Reaction | Counter to extension | Failed auction at PDH/PDL |
| 3 | 20P IB Extension | With extension | If 3 consecutive 5-min closes beyond IB |
| 4 | Trend Bear (on P-Day Down) | SHORT | 77.8% WR on P-Day Down — high confidence |

### Gap Day (NDOG / NWOG)

**Characteristics**: Opening gap ≥ 20pts from prior close

| Priority | Strategy | Direction | Notes |
|----------|----------|-----------|-------|
| 1 | NDOG Gap Fill | Gap fill direction | Fires at 9:30 (57.1% WR) |
| 2 | NWOG Gap Fill (Mondays) | Gap fill direction | Monday weekly gaps (65.0% WR) |
| 3 | Normal strategies | After gap resolution | Once gap fills or holds, proceed with regular playbook |

---

## 4. Risk Management Framework

### Position Sizing

| Confluence Level | Size | When |
|-----------------|------|------|
| **Full (100%)** | 1 contract MNQ or NQ | Signal + bias aligned + day type favorable |
| **Reduced (50%)** | 1 MNQ | Signal fires but weak confluence (e.g., neutral bias) |
| **Skip** | 0 | Counter-bias trade, or daily loss limit hit |

### Stop Loss Rules

- **Never move a stop AWAY from price** — only tighten or hold
- **ATR trailing** (OR Rev, OR Accept): automatic, engine-managed
- **Fixed stops**: strategy-specific, defined at signal time
- **Daily stop**: $4,000 max daily loss → flat for the day

### The "Don't Chase" Rule

From brainstorm doc 07: **"Caution over conviction. Don't chase. Recommend retracement entry. Warn about balance day traps."**

- If OR Rev fires and you missed it → do NOT enter late. Wait for the next signal.
- If price gaps beyond your entry → do NOT chase the gap. NDOG/NWOG will handle gap fills.
- If the market is at an extreme (RSI>75 or <25) → be cautious, don't add to positions.

---

## 5. Backtesting the Daily Trading Plan

### Current Backtest Coverage

The 12 strategies + trailing stops + bias filters are already backtested:

| Component | Backtested? | Run ID |
|-----------|-------------|--------|
| All 12 strategies | YES | `NQ_20260314_111555_3d383b` |
| Bias alignment filter | YES | Built into engine |
| ATR trailing (OR Rev, OR Accept) | YES | Trailing study 2026-03-14 |
| VWAP breach PM exemption | YES | Applied engine-wide |
| Day type gating | PARTIAL | Engine classifies in real-time but session-level types differ |

### What We Can Backtest

1. **Position limits**: Add max concurrent position enforcement to engine
   - Currently: unlimited concurrent positions
   - Proposed: max 2 concurrent, FIFO priority
   - Backtest: compare unlimited vs max-2

2. **Session stop-loss**: Add daily loss limit cutoff
   - Currently: `daily_loss_exceeded()` exists in PositionManager
   - Verify: is $4K cutoff applied consistently?

3. **Time-of-day filtering**: Tighten entry windows per strategy
   - Data shows: Trend Bear 10:xx = 69.2% WR vs 11:xx+ = 30%
   - Proposed: Trend Bear cutoff at 11:00 instead of 14:00
   - Backtest: compare current vs tighter windows

4. **Sequencing rules**: When conflicting signals fire, which takes priority?
   - Currently: all strategies fire independently
   - Proposed: priority queue (OR Rev > OR Accept > PDH/PDL > others)
   - Backtest: compare unordered vs priority execution

5. **Day type routing**: Only run specific strategies on specific day types
   - Currently: strategies self-filter via `applicable_day_types` (mostly empty)
   - Proposed: engine-level day type routing
   - Challenge: day type at 10:30 vs final session type can differ

### What We Cannot Backtest (Yet)

| Component | Why | Path Forward |
|-----------|-----|-------------|
| Premarket briefing quality | No LLM inference in backtest | Phase 4c LLM debate |
| Trader psychology (revenge trading, FOMO) | Not modeled | Journal + /review-session |
| Execution quality (real slippage, partial fills) | Using fixed 1-tick slippage | Forward test with paper account |
| Options overlay (Two Hour Trader) | Separate system, no data | Future phase |

### Backtestable Trading Plan Rules — Implementation Guide

These rules from the daily trading plan CAN be backtested with engine changes. Another Claude session can implement and A/B test these.

#### Rule 1: Max 2 Concurrent Positions
- **Where**: `BacktestEngine._execute_signal()` — add check before opening position
- **Logic**: `if self.position_mgr.get_open_contracts() >= 2: skip`
- **Current state**: No limit (unlimited concurrent)
- **Expected impact**: Reduces risk exposure, may slightly reduce PnL but improves risk-adjusted returns
- **A/B test**: Run A (unlimited) vs Run B (max 2) on 274 sessions

#### Rule 2: Daily Loss Cutoff ($4K)
- **Where**: `PositionManager.daily_loss_exceeded()` already exists
- **Logic**: Check `realized_pnl_today <= -4000` → stop trading for session
- **Current state**: Exists in code, verify it's wired to correct threshold
- **A/B test**: Run with $4K vs $6K vs $10K cutoff

#### Rule 3: Strategy Priority Queue
- **Where**: `BacktestEngine` bar loop — when multiple signals fire on same bar
- **Logic**: Sort signals by strategy PF rank: OR Rev (3.34) > OR Accept (2.74) > PDH/PDL (3.59) > etc.
- **Implementation**: Collect all signals per bar, sort by priority, execute top N within position limit
- **Current state**: First strategy in list wins (arbitrary order)
- **A/B test**: Run ordered vs unordered

#### Rule 4: Per-Strategy Time Cutoffs
- **Where**: Each strategy's `on_bar()` method — `ENTRY_CUTOFF` constant
- **Current cutoffs vs data-optimized**:

| Strategy | Current Cutoff | Proposed | Data Basis |
|----------|---------------|----------|-----------|
| Trend Bear | 14:00 | **11:30** | 10:xx=69.2% WR, 11:xx+=30% WR |
| VA Edge Fade | 14:00 | **13:00** | 13:xx=42.9% WR, marginal |
| IB Edge Fade | 14:00 | **13:00** | 13:xx=42.9% WR |
| Others | Various | Keep | Edge doesn't degrade by hour |

#### Rule 5: 2 Consecutive Losses → Stop for Session
- **Where**: `PositionManager` — add `session_loss_streak` counter
- **Logic**: After 2 consecutive losses in same session, block new signals
- **Expected impact**: Prevents tilt/revenge trades on bad days, protects capital
- **A/B test**: Run with vs without streak cutoff

#### Rule 6: Train/Test Split (Forward Walk)
- **Where**: `run_backtest.py` — add `--split` flag
- **Logic**: Train on sessions 1-137, test on 138-274 (chronological split)
- **Purpose**: Validate that strategy parameters hold out-of-sample
- **Critical**: This is the most important experiment — if strategies don't hold OOS, we're overfitting

### Proposed Backtest Experiments

| # | Experiment | Hypothesis | Method | Priority |
|---|------------|-----------|--------|----------|
| 1 | **Forward walk (train/test split)** | Strategies hold out-of-sample | 50/50 chronological split | **HIGH** |
| 2 | **Max 2 concurrent positions** | Reduces risk without much PnL loss | Engine change + A/B | HIGH |
| 3 | **Strategy priority queue** | Higher-PF strategies should take priority | Engine routing + A/B | MEDIUM |
| 4 | **Trend Bear cutoff 11:30** | Morning entries carry the edge | Parameter change | MEDIUM |
| 5 | **Session loss streak cutoff** | 2 consecutive losses → stop | PositionManager change | MEDIUM |
| 6 | **Session risk budget** | After $2K profit, reduce size | Position manager change | LOW |

---

## 6. Daily Routine Checklist

### Pre-Market (8:30 — 9:25)

- [ ] Check overnight gap size + direction
- [ ] Note London session bias (expansion or rejection?)
- [ ] Load session bias from DuckDB / prior day analysis
- [ ] Review active strategy list — which are enabled today?
- [ ] Set alerts at PDH, PDL, prior VAH, prior VAL, London H/L
- [ ] Check if Monday (NWOG potential)
- [ ] Check VIX level — elevated VIX = wider stops needed

### The Bell (9:30)

- [ ] NDOG/NWOG fires or doesn't — no action needed, automatic
- [ ] Watch opening drive direction — up, down, or flat?
- [ ] Note any sweep of London/Asia levels (OR Rev setup forming?)

### First Hour (9:30 — 10:30)

- [ ] 9:45 — OR formed. Any sweep + reversal? (OR Rev candidate)
- [ ] 10:00 — PDH/PDL touched? Failed auction developing?
- [ ] 10:15 — IB forming. Narrow or wide? What shape?
- [ ] 10:30 — **IB CLOSE. Classify day type. Execute signals.**

### Main Session (10:30 — 12:00)

- [ ] Manage open positions (trailing stops auto-adjust for OR Rev/Accept)
- [ ] Watch for 80P acceptance, 20P IB extension, VA Edge Fade setups
- [ ] Monitor: is the day morphing? (Balance → Trend? → adjust expectations)

### Afternoon (12:00 — 15:00)

- [ ] After 13:00 — be very selective. Most edges degrade.
- [ ] Manage remaining positions to EOD
- [ ] **Post-market**: Run `/review-session` for today's trades
- [ ] **Post-market**: Update DuckDB observations if any new patterns noticed

---

## 7. Performance Benchmarks

### Per-Session Targets (based on 274 session backtest)

| Metric | Target | Basis |
|--------|--------|-------|
| Trades per session | 2-3 | 734 trades / 274 sessions = 2.7 avg |
| Win rate | > 50% | Portfolio: 56.1% |
| Expectancy per trade | > $500 | Portfolio: $735 |
| Daily PnL target | $1,500 | $539K / 274 sessions = $1,967 avg (conservative target) |
| Max daily loss | -$4,000 | 2 full NQ stops |
| Max drawdown | -$10,000 | 6.5% of $150K starting capital |

### Strategy Contribution (expected monthly)

| Strategy | Monthly PnL | Monthly Trades | Role |
|----------|------------|----------------|------|
| OR Acceptance (+ trail) | $13,700 | 10 | **Primary alpha engine** |
| Opening Range Rev (+ trail) | $6,300 | 7 | **Primary alpha engine** |
| PDH/PDL Reaction | $3,400 | 4 | High-PF outlier |
| NDOG Gap Fill | $2,900 | 5 | Consistent gap filler |
| NWOG Gap Fill | $2,800 | 1-2 | Monday specialist |
| VA Edge Fade | $2,300 | 2 | VAH rejection SHORT |
| Trend Day Bull | $1,400 | 5 | Trend continuation |
| Trend Day Bear | $1,300 | 3 | Trend continuation |
| 80P Rule | $1,400 | 2 | VA return SHORT |
| 20P IB Extension | $1,200 | 3 | IB extension |
| IB Edge Fade | $1,100 | 5 | IBL rejection LONG |
| B-Day | $900 | 4 | Mean reversion |

---

*Document Version: 1.0*
*Date: 2026-03-14*
*Branch: claude/bridge-implementation*
*Based on: NQ_20260314_111555_3d383b (734 trades, PF 3.28, +$539K)*
