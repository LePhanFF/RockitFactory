# 16 — Live Dashboard Prototype: From Backtest to Real-Time Trading System

> **Purpose**: Design a live trading dashboard that connects our deterministic engine, strategy runner, domain experts, and agent pipeline into a usable real-time system. Replace the legacy RockitUI (GCS-polling, Gemini-only) with an integrated dashboard powered by our own infrastructure.
>
> **Status**: Design / Brainstorm
> **Date**: 2026-03-14
> **Depends on**: Docs 07 (tape reading), 11 (testing), 12 (deployment), 14 (bridge), 15 (daily trading plan)

---

## 1. What We Have vs What We Need

### Built and Proven

| Component | Status | Location |
|-----------|--------|----------|
| **12 strategies** | Backtested, 734 trades, PF 2.49, +$370K | `rockit-core/strategies/` |
| **38 deterministic modules** | Production-ready, <10ms/snapshot | `rockit-core/deterministic/` |
| **8 domain experts** | Built, 25+ evidence cards per signal | `rockit-core/agents/experts/` |
| **Advocate/Skeptic/Orchestrator** | LangGraph debate pipeline | `rockit-core/agents/` |
| **DuckDB research DB** | 80+ runs, 16K+ trades, 270 sessions | `data/research.duckdb` |
| **Strategy runner** | 1-min bar loop, all strategies, filter chain | `rockit-core/backtest/` |
| **Deterministic orchestrator** | 5-min snapshots, regime context, validation | `rockit-core/deterministic/` |
| **Self-learning loop** | /review-session, /meta-review, observations | Skills + DuckDB |
| **Daily trading plan** | 4-phase timeline, strategy-phase mapping | Doc 15 |
| **Snapshot generator** | JSONL output for training | `scripts/generate_*.py` |
| **Legacy RockitUI** | 12 tabs, Gemini chat, GCS polling, journal | `LePhanFF-RockitUI/` |

### What's Missing for Live

| Gap | Why It Matters |
|-----|----------------|
| **No real-time data feed into rockit-core** | Backtest engine reads CSVs. Need live 1-min bars. |
| **No WebSocket/SSE from rockit-serve** | Legacy UI polls GCS every 10s. Need push updates. |
| **No strategy status dashboard** | Can't see which strategies are active, armed, fired, or blocked. |
| **No structured trade plan view** | Doc 15 exists as markdown. Need it as a live, updating dashboard. |
| **No trade idea generation** | Experts + playbooks exist but aren't consulted proactively. |
| **No position/P&L tracking** | Backtest tracks positions. Live system needs real-time tracking. |
| **Dashboard doesn't consume our agents** | Legacy uses Gemini. We have Qwen3.5 + domain experts + debate. |

---

## 2. Architecture: How It All Connects

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DATA LAYER                                       │
│                                                                             │
│  NinjaTrader → 1-min CSV (G:\My Drive\future_data\1min\)                   │
│       │                                                                     │
│       ▼                                                                     │
│  File Watcher (rockit-ingest)         ← watches for new bars               │
│       │                                                                     │
│       ▼                                                                     │
│  Bar Buffer (in-memory ring buffer)   ← holds current session bars         │
└───────┬─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          COMPUTE LAYER (rockit-serve)                        │
│                                                                             │
│  ┌──────────────┐    ┌─────────────────────┐    ┌──────────────────────┐   │
│  │ Strategy      │    │ Deterministic        │    │ Agent Pipeline       │   │
│  │ Runner        │    │ Orchestrator         │    │                      │   │
│  │ (every 1 min) │    │ (every 5 min)        │    │ Experts → Debate     │   │
│  │               │    │                      │    │ → Orchestrator       │   │
│  │ 12 strategies │    │ 38 modules           │    │ → Trade Decision     │   │
│  │ filter chain  │    │ regime context       │    │                      │   │
│  │ signal emit   │    │ validation           │    │ Qwen3.5 (Ollama)    │   │
│  └──────┬───────┘    └──────────┬───────────┘    └──────────┬───────────┘   │
│         │                       │                            │               │
│         ▼                       ▼                            ▼               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      Session State Store                             │   │
│  │  - current bars[]           - deterministic snapshot (latest)        │   │
│  │  - strategy states{}        - evidence cards[]                       │   │
│  │  - active signals[]         - agent decisions[]                      │   │
│  │  - positions[]              - trade plan phase                       │   │
│  │  - session P&L              - day type classification                │   │
│  └──────────────────────────────────┬───────────────────────────────────┘   │
│                                     │                                       │
│                                     ▼                                       │
│                            WebSocket Hub                                    │
│                     (push to all connected clients)                         │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DASHBOARD (rockit-dashboard)                          │
│                                                                             │
│  React 19 + Vite + Tailwind + Recharts                                     │
│                                                                             │
│  ┌─────────────┐ ┌───────────────┐ ┌──────────────┐ ┌──────────────────┐  │
│  │ Trade Plan   │ │ Strategy      │ │ Market        │ │ Agent            │  │
│  │ (Doc 15 live)│ │ Board         │ │ Context       │ │ Intelligence     │  │
│  └─────────────┘ └───────────────┘ └──────────────┘ └──────────────────┘  │
│  ┌─────────────┐ ┌───────────────┐ ┌──────────────┐ ┌──────────────────┐  │
│  │ Positions    │ │ Evidence      │ │ Trade Ideas   │ │ Journal          │  │
│  │ & P&L        │ │ Cards         │ │ (proactive)   │ │ (legacy port)    │  │
│  └─────────────┘ └───────────────┘ └──────────────┘ └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Architecture Decisions

1. **File watcher, not API push**: NinjaTrader writes 1-min CSVs to Google Drive. We watch the local sync folder. No NinjaTrader plugin needed. Same data path as backtest — zero code divergence between backtest and live.

2. **Single process**: Strategy runner + orchestrator + agents all in `rockit-serve`. No microservices. Doc 12 design: one process, one GPU, asyncio event loop.

3. **WebSocket push, not polling**: Legacy UI polls GCS every 10s. New dashboard gets pushed every update via WebSocket. Sub-second latency for strategy fires.

4. **Session state store**: In-memory Python dict holding the entire current session state. Every WebSocket message is a delta or full snapshot of this state. No external cache (Redis, etc).

5. **Same code for backtest and live**: Strategy runner consumes bars from either a CSV (backtest) or the live buffer (live mode). `BarSource` abstraction — strategies don't know the difference.

---

## 3. Dashboard Views

### 3.1 Trade Plan View (PRIMARY — always visible)

The daily trading plan from Doc 15, rendered as a **live, updating timeline**.

```
┌─────────────────────────────────────────────────────────────────────┐
│  TRADE PLAN — NQ — Friday March 14, 2026                    10:42  │
│  Day Type: BALANCE (evolving)  │  Bias: LONG  │  Phase: 2          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  TIMELINE                                                           │
│  ═══════                                                            │
│  PRE ──── PHASE 1 ──────────── PHASE 2 ──────── PHASE 3 ────       │
│  9:30    10:00    10:30        12:00              15:00              │
│                     ▲                                                │
│                     │ YOU ARE HERE                                   │
│                                                                     │
│  ┌─────────┐  ┌─────────────────────────────────────┐               │
│  │ PHASE 1 │  │ PHASE 2 (ACTIVE)                    │               │
│  │ ✓ Done  │  │                                      │               │
│  │         │  │  WATCHING:                           │               │
│  │ OR Rev  │  │  ● 80P Rule — 30-bar timer at 22/30 │               │
│  │  → LONG │  │  ● Trend Bull — ADX rising (31→33)  │               │
│  │  FIRED  │  │  ● B-Day — IB range holding         │               │
│  │  +$850  │  │                                      │               │
│  │         │  │  NOT IN PLAY:                        │               │
│  │ OR Acc  │  │  ○ Trend Bear — bias LONG, blocked   │               │
│  │  SKIP   │  │  ○ IB Edge Fade — no IBL poke       │               │
│  │  (bias) │  │  ○ VA Edge — outside VA acceptance   │               │
│  └─────────┘  └─────────────────────────────────────┘               │
│                                                                     │
│  RULES IN EFFECT                                                    │
│  ───────────────                                                    │
│  ✓ Max 2 positions (1/2 used)                                       │
│  ✓ Daily loss limit: $0 / -$4,000                                   │
│  ✓ Consecutive losses: 0 / 2                                        │
│  ○ Session loss streak cutoff: not triggered                        │
│                                                                     │
│  DECISION TREE (from IB close)                                      │
│  ──────────────────────────────                                     │
│  IB: 21,450 — 21,580 (130pt) → NORMAL                              │
│  Open inside prior VA → Balance day likely                          │
│  → B-Day + 80P are primary. Trend needs ADX ≥ 28.                  │
└─────────────────────────────────────────────────────────────────────┘
```

**What updates in real-time**:
- Current phase highlight (PRE → 1 → 2 → 3)
- Day type classification (can morph: Balance → P-Day)
- Strategy statuses (WATCHING → ARMED → FIRED → DONE / BLOCKED)
- Risk rule counters (position count, daily P&L, loss streak)
- Decision tree re-evaluates as IB forms and price develops

**Data sources**:
- Strategy runner → strategy states, signals, positions
- Deterministic orchestrator → day type, IB metrics, VA position
- Doc 15 rules → phase definitions, time windows, priority queue

### 3.2 Strategy Board

A **12-card grid** showing every strategy's current status. Each card is a mini dashboard.

```
┌──────────────────────────────────────────────────────────────────┐
│  STRATEGY BOARD                                                   │
├──────────────────┬──────────────────┬──────────────────┬─────────┤
│  OR REVERSAL     │  OR ACCEPTANCE   │  80P RULE        │ 20P EXT │
│  ▓▓▓▓▓▓ FIRED    │  ░░░░░░ BLOCKED  │  ▒▒▒▒▒▒ ARMED    │ ░ WATCH │
│  LONG @ 21,520   │  Bias mismatch   │  Timer: 22/30    │ No ext  │
│  Stop: 21,490    │                  │  Short setup     │ yet     │
│  Target: 21,580  │                  │  Entry: ~21,560  │         │
│  P&L: +$850      │                  │                  │         │
│  Trail: 21,508 ↑ │                  │                  │         │
│  WR: 64% PF: 2.9 │  WR: 60% PF: 2.1│  WR: 42% PF: 2.8│ 50% 1.9 │
├──────────────────┼──────────────────┼──────────────────┼─────────┤
│  TREND BULL      │  TREND BEAR      │  B-DAY           │ IB EDGE │
│  ▒▒▒▒▒▒ WATCHING │  ░░░░░░ BLOCKED  │  ▒▒▒▒▒▒ WATCHING │ ░ INACT │
│  ADX: 33 (≥28?)  │  Bias: LONG      │  IB range hold   │ No poke │
│  EMA aligned: Y  │  → blocked       │  Mean rev setup  │         │
│  Needs IBH break │                  │  forming...      │         │
│  WR: 56% PF: 2.3 │  WR: 44% PF: 2.5│  WR: 46% PF: 2.1│ 48% 1.8 │
├──────────────────┼──────────────────┼──────────────────┼─────────┤
│  PDH/PDL REACT   │  VA EDGE FADE    │  NDOG GAP FILL   │ NWOG    │
│  ▓▓▓▓▓▓ DONE     │  ░░░░░░ N/A      │  ▓▓▓▓▓▓ DONE     │ ░ N/A   │
│  No PDH/PDL hit  │  Outside VA req  │  Gap filled ✓    │ Not Mon │
│  Window: closed   │  not met         │  +$420           │         │
│  WR: 53% PF: 3.6 │  WR: 60% PF: 1.8│  WR: 57% PF: 2.0│ 65% 5.0 │
└──────────────────┴──────────────────┴──────────────────┴─────────┘
```

**Strategy lifecycle states**:

| State | Color | Meaning |
|-------|-------|---------|
| `INACTIVE` | Gray | Not applicable today (e.g., NWOG on non-Monday) |
| `WATCHING` | Blue | Window open, conditions not yet met |
| `ARMED` | Yellow | Conditions building, close to firing (e.g., 80P timer running) |
| `FIRED` | Green | Signal emitted, position open |
| `DONE` | Dim green | Completed (position closed with result) |
| `BLOCKED` | Red | Filtered out (bias mismatch, position limit, loss cutoff) |
| `SKIPPED` | Orange | Passed on by agent debate (take/skip decision) |

**Each card shows**:
- Strategy name + lifecycle state
- Key condition progress (what's met, what's pending)
- Entry/stop/target if ARMED or FIRED
- Running P&L if FIRED
- Historical WR and PF (from DuckDB baseline)
- Block reason if BLOCKED

### 3.3 Market Context Panel (replaces Legacy Brief/Logic/Intraday tabs)

Consolidates the best of legacy RockitUI's 6 data tabs into a **single dense panel**.

```
┌──────────────────────────────────────────────────────────────────┐
│  MARKET CONTEXT — NQ — 10:42 ET                                  │
├─────────────────────────────────┬────────────────────────────────┤
│  STRUCTURE                      │  LEVELS                        │
│  ─────────                      │  ──────                        │
│  IB: 21,450 — 21,580 (130pt)   │  PDH: 21,620  (38pt away)     │
│  VA: 21,480 — 21,560            │  PDL: 21,380  (138pt away)    │
│  POC: 21,525                    │  Prior POC: 21,510            │
│  DPOC: 21,530 (migrating ↑)    │  VAH: 21,560  VAL: 21,480     │
│  VWAP: 21,518                   │  O/N High: 21,600             │
│  Price: 21,558                  │  O/N Low: 21,420              │
│                                 │  NDOG: filled ✓                │
│  Day Type: BALANCE (evolving)   │  FVG 1h: 21,490-21,500 (open) │
│  Regime: low_vol_balance        │  FVG 15m: 21,540-21,545 (fill)│
│  ATR(14): 185pt                 │                                │
├─────────────────────────────────┼────────────────────────────────┤
│  INDICATORS                     │  ORDER FLOW                    │
│  ──────────                     │  ──────────                    │
│  EMA(20): 21,535 ↑              │  CVD: +1,240 (bullish)        │
│  EMA(50): 21,510 ↑              │  Delta: +85 (last bar)        │
│  EMA(200): 21,480 ↑             │  Wick parade: 2 bull / 0 bear │
│  RSI(14): 58 (neutral)          │  TPO shape: b (fat bottom)    │
│  ADX(14): 33 (trending)         │  Single prints: above VAH     │
│  Compression: No                │  Poor high: YES               │
│                                 │  Fattening: upper half         │
└─────────────────────────────────┴────────────────────────────────┘
```

**Key improvement over legacy**: One screen, not 6 tabs. Trader glances at this once and has full context. Levels are sorted by proximity to current price — the closest level is most actionable.

### 3.4 Trade Ideas Panel (NEW — Proactive Agent Consultation)

This is the new capability. Instead of the trader asking "what should I do?", the system **proactively scans playbooks and tells the trader what's setting up**.

```
┌──────────────────────────────────────────────────────────────────┐
│  TRADE IDEAS — What's Setting Up                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  🟢 HIGH CONFIDENCE                                               │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  80P SHORT Setup Developing                                │  │
│  │  ──────────────────────────────                            │  │
│  │  WHAT: Price opened above VA, now accepting back inside.   │  │
│  │        30-bar acceptance timer at 22/30.                   │  │
│  │  WHY:  80P rule — when price opens above VA and returns    │  │
│  │        inside, 80% of the time it migrates to POC.         │  │
│  │  ENTRY: ~21,560 (once 30-bar timer completes)              │  │
│  │  STOP:  21,590 (above re-entry into prior VA)              │  │
│  │  TARGET: 21,525 (POC)                                      │  │
│  │  R:R:   1:1.2                                              │  │
│  │                                                            │  │
│  │  EVIDENCE (4 supporting / 1 opposing):                     │  │
│  │  ✓ TPO Expert: b-shape profile, fat bottom = downside magn │  │
│  │  ✓ VWAP Expert: price below VWAP, mean reversion target    │  │
│  │  ✓ ICT Expert: FVG at 21,490 unfilled — magnet below      │  │
│  │  ✓ Order Flow: CVD diverging from price (bearish)          │  │
│  │  ✗ EMA Expert: EMAs still aligned bullish (caution)        │  │
│  │                                                            │  │
│  │  AGENT VERDICT: TAKE — 4:1 evidence ratio, strategy       │  │
│  │  has 42% WR but 2.8 PF. Acceptable risk.                  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  🟡 DEVELOPING                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Trend Bull — Needs IBH Break                              │  │
│  │  ADX at 33 (≥28 ✓), EMAs aligned ✓, but no IBH acceptance │  │
│  │  yet. If price breaks 21,580 and holds 2 bars → fires.    │  │
│  │  Watching...                                               │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ⚪ PASSED                                                        │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  OR Acceptance — Blocked (bias mismatch)                   │  │
│  │  Agent debate: SKIP. Trend against acceptance direction.   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

**How trade ideas are generated**:

```
Every 1-min bar:
  1. Strategy runner evaluates all 12 strategies
  2. Any strategy in WATCHING or ARMED state → candidate

Every 5-min snapshot:
  3. Deterministic orchestrator produces full context
  4. For each ARMED candidate:
     a. Collect evidence cards from 8 domain experts
     b. Run ConflictDetector for cross-domain conflicts
     c. If signal fires → run Advocate/Skeptic debate (Qwen3.5)
     d. Orchestrator renders verdict: TAKE / SKIP / REDUCE_SIZE
  5. Package as TradeIdea with entry/stop/target/evidence/verdict
  6. Push to dashboard via WebSocket

Proactive scan (every 5 min):
  7. For strategies in WATCHING state:
     a. How close are they to ARMED? (e.g., "ADX at 26/28")
     b. What would need to happen for them to fire?
     c. Package as "Developing" idea with conditions remaining
```

**Key principle**: The system does the scanning. The trader reviews and decides. No manual "what if" queries needed — though the trader CAN ask ad-hoc questions (the `consult()` API from Doc 13).

### 3.5 Evidence & Agent Debate View

When a trade idea fires or the trader wants to drill in, show the full debate.

```
┌──────────────────────────────────────────────────────────────────┐
│  DEBATE — 80P SHORT @ 10:42                                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ADVOCATE (for taking the trade):                                │
│  ─────────────────────────────────                               │
│  "Classic 80% rule setup. Price opened above VA at 21,590,      │
│  now 22 bars inside VA. POC magnet at 21,525 is 35 points       │
│  away. CVD diverging bearish despite price holding. TPO          │
│  b-shape confirms distribution. The unfilled 1h FVG at          │
│  21,490 provides additional downside magnet. Risk is only        │
│  30 points to re-enter above VA."                                │
│                                                                   │
│  SKEPTIC (against taking the trade):                             │
│  ───────────────────────────────────                             │
│  "EMAs still aligned bullish — this is counter-trend.            │
│  ADX at 33 suggests trend strength, not mean reversion.          │
│  42% WR means majority of these lose. The balance day            │
│  classification is uncertain — could morph to P-Day up.          │
│  Wait for EMA(20) to flatten before shorting against trend."     │
│                                                                   │
│  ORCHESTRATOR DECISION: TAKE                                     │
│  ────────────────────────────                                    │
│  "Evidence weight favors the trade 4:1. The 80P rule is          │
│  specifically designed for this scenario — high PF (2.8)         │
│  compensates for sub-50% WR. EMA concern is noted but            │
│  secondary to profile structure. Proceed with standard size."    │
│                                                                   │
│  EVIDENCE CARDS (5):                                             │
│  ┌──────────┬───────────┬───────┬────────────────────────────┐  │
│  │ Source   │ Direction │ Str   │ Signal                      │  │
│  ├──────────┼───────────┼───────┼────────────────────────────┤  │
│  │ TPO      │ SHORT     │ 0.85  │ b-shape, fat bottom        │  │
│  │ VWAP     │ SHORT     │ 0.70  │ below VWAP, reverting      │  │
│  │ ICT      │ SHORT     │ 0.60  │ unfilled FVG below         │  │
│  │ OrdFlow  │ SHORT     │ 0.75  │ CVD divergence             │  │
│  │ EMA      │ LONG      │ 0.65  │ all EMAs aligned up        │  │
│  └──────────┴───────────┴───────┴────────────────────────────┘  │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### 3.6 Position & P&L Tracker

```
┌──────────────────────────────────────────────────────────────────┐
│  POSITIONS & P&L                                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  SESSION: +$850 (1W / 0L)    Daily Limit: $850 / -$4,000        │
│                                                                   │
│  OPEN POSITIONS (1/2 max)                                        │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  OR Rev LONG │ Entry: 21,520 │ Current: 21,558 │ +$760    │  │
│  │  Stop: 21,490 (trailing → 21,508) │ Target: 21,580        │  │
│  │  ████████████████████░░░░░░  73% to target                 │  │
│  │  MAE: -8pt (21,512)  MFE: +42pt (21,562)  R: +1.27        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  CLOSED TODAY                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  NDOG Gap Fill │ LONG │ 9:30→9:48 │ +$420 │ TARGET HIT    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  EQUITY CURVE (intraday)                                         │
│  $1000 ┤                                          ╭──           │
│   $500 ┤                    ╭────────────────────╯              │
│     $0 ┼────────────────────╯                                   │
│         9:30  10:00  10:30  11:00  11:30                        │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### 3.7 Chart View (Simplified from Legacy)

Keep the price chart from legacy but strip the complexity. Add strategy annotations.

**Keep from legacy**:
- Recharts price chart (OHLCV)
- VWAP, EMA overlays
- IB range shading
- FVG zones

**Add new**:
- Strategy fire markers (arrows on chart at signal bar with strategy name)
- Entry/stop/target lines for active positions
- Trailing stop progression line
- Phase boundary vertical lines (9:30, 10:00, 10:30, 12:00)

**Remove from legacy**:
- Drawing tools (unnecessary for automated system)
- Globex overlay (moved to Market Context panel)
- Composite profile overlay (too noisy)

### 3.8 Journal & Review (Port from Legacy)

Port the journal from legacy RockitUI. Same API (`/journal/{date}`), same data model. But integrate with our agent system:

- **Pre-fill journal remarks** from agent decisions ("OR Rev fired LONG at 10:30. Advocate cited Judas sweep. Skeptic cautioned on ADX. Orchestrator: TAKE.")
- **Post-session review** auto-populated by `/review-session` skill
- **Time-slice remarks** keyed to strategy fires, not just clock time

---

## 4. Data Flow: What Gets Pushed When

| Event | Frequency | What's Pushed | Dashboard Update |
|-------|-----------|---------------|------------------|
| New 1-min bar | Every 60s | Bar data + strategy states | Chart + Strategy Board + Positions |
| Strategy state change | On event | Strategy ID + new state + details | Strategy Board card |
| Signal fired | On event | Full signal (entry/stop/target) | Strategy Board + Trade Ideas + Chart |
| Deterministic snapshot | Every 5 min | Full 38-module output | Market Context panel |
| Agent debate complete | On signal fire | Evidence cards + debate text + verdict | Trade Ideas + Evidence view |
| Position update | Every 60s | Position P&L, MAE/MFE, trail level | Position tracker |
| Position close | On event | Final P&L, exit type, duration | Position tracker + journal pre-fill |
| Day type reclassification | On change | New day type + rationale | Trade Plan + Decision Tree |
| Risk rule triggered | On event | Rule ID + current state | Trade Plan rules section |
| Trade idea (developing) | Every 5 min | Strategy + conditions + proximity | Trade Ideas panel |

### WebSocket Message Format

```json
{
  "type": "strategy_state_change",
  "timestamp": "2026-03-14T10:42:15-04:00",
  "payload": {
    "strategy_id": "80p_rule",
    "prev_state": "WATCHING",
    "new_state": "ARMED",
    "details": {
      "timer_bars": 22,
      "timer_required": 30,
      "direction": "SHORT",
      "projected_entry": 21560,
      "projected_stop": 21590,
      "projected_target": 21525
    }
  }
}
```

```json
{
  "type": "trade_idea",
  "timestamp": "2026-03-14T10:42:15-04:00",
  "payload": {
    "strategy_id": "80p_rule",
    "confidence": "high",
    "direction": "SHORT",
    "entry": 21560,
    "stop": 21590,
    "target": 21525,
    "r_reward": 1.17,
    "evidence_cards": [...],
    "debate": {
      "advocate": "Classic 80% rule setup...",
      "skeptic": "EMAs still aligned bullish...",
      "verdict": "TAKE",
      "reasoning": "Evidence weight favors 4:1..."
    },
    "historical": {
      "win_rate": 0.423,
      "profit_factor": 2.83,
      "avg_r": 1.45,
      "sample_size": 52
    }
  }
}
```

```json
{
  "type": "full_snapshot",
  "timestamp": "2026-03-14T10:45:00-04:00",
  "payload": {
    "phase": 2,
    "day_type": "BALANCE",
    "day_type_confidence": 0.72,
    "bias": "LONG",
    "market_context": { ... },
    "strategy_states": { ... },
    "positions": [ ... ],
    "session_pnl": 850,
    "risk_rules": { ... },
    "trade_ideas": [ ... ]
  }
}
```

---

## 5. Tech Stack Decisions

### What to Keep from Legacy RockitUI

| Component | Keep? | Why |
|-----------|-------|-----|
| React 19 | YES | Works, team knows it, no reason to switch |
| Vite | YES | Fast dev server, good DX |
| Tailwind CSS | YES | Rapid UI development, consistent styling |
| Recharts | YES | Good enough for price charts + equity curves |
| 3-theme system | YES | Dark/light/metal — nice to have |
| Express proxy | NO | Replace with direct WebSocket to rockit-serve |
| GCS polling | NO | Replace with WebSocket push |
| Gemini AI | NO | Replace with Qwen3.5 via rockit-serve |
| @google/genai SDK | NO | No more Gemini dependency |
| 12 separate tabs | NO | Consolidate to 4-5 focused views |

### What to Add

| Component | Why |
|-----------|-----|
| WebSocket client (`useWebSocket` hook) | Real-time push from rockit-serve |
| Zustand (state management) | Legacy uses prop drilling. Dashboard is more complex → need store |
| React Router | Proper URL routing (legacy uses activeTab state) |
| Sonner (toast notifications) | Strategy fire alerts, risk rule warnings |
| TanStack Table | Evidence cards, trade history — needs sorting/filtering |

### Backend (rockit-serve additions)

| Component | Purpose |
|-----------|---------|
| `LiveSessionManager` | Manages bar buffer, orchestrates strategy runner + deterministic + agents |
| `WebSocketHub` | FastAPI WebSocket endpoint, broadcasts to connected clients |
| `BarSource` ABC | Abstraction over CSV (backtest) vs file-watcher (live) |
| `FileWatcher` | Watches `G:\My Drive\future_data\1min\` for new bars |
| `StrategyStateTracker` | Tracks lifecycle state for each strategy per session |
| `TradeIdeaGenerator` | Proactive scan: ARMED strategies → evidence → debate → idea |
| `/ws/live` endpoint | WebSocket connection for dashboard |
| `/api/consult` endpoint | Ad-hoc expert consultation (from Doc 13) |

---

## 6. Dashboard Layout

### Desktop Layout (Primary)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  HEADER: NQ │ 10:42 ET │ Phase 2 │ BALANCE │ LONG │ +$850 │ 1/2 pos   │
├───────────────────────────────┬──────────────────────────────────────────┤
│                               │                                          │
│   LEFT PANEL (60%)            │   RIGHT PANEL (40%)                      │
│                               │                                          │
│   ┌─────────────────────┐    │   ┌──────────────────────────────────┐   │
│   │                     │    │   │  TRADE PLAN                      │   │
│   │   PRICE CHART       │    │   │  (Phase timeline + rules)        │   │
│   │   + Strategy markers│    │   │                                  │   │
│   │   + Position lines  │    │   │  [Section 3.1]                   │   │
│   │                     │    │   │                                  │   │
│   └─────────────────────┘    │   └──────────────────────────────────┘   │
│                               │                                          │
│   ┌─────────────────────┐    │   ┌──────────────────────────────────┐   │
│   │  STRATEGY BOARD     │    │   │  TRADE IDEAS                     │   │
│   │  (12 cards grid)    │    │   │  (Proactive setups)              │   │
│   │                     │    │   │                                  │   │
│   │  [Section 3.2]      │    │   │  [Section 3.4]                   │   │
│   └─────────────────────┘    │   │                                  │   │
│                               │   └──────────────────────────────────┘   │
│   ┌─────────────────────┐    │                                          │
│   │  MARKET CONTEXT     │    │   ┌──────────────────────────────────┐   │
│   │  (Structure/Levels/ │    │   │  POSITIONS & P&L                 │   │
│   │   Indicators/Flow)  │    │   │  [Section 3.6]                   │   │
│   │  [Section 3.3]      │    │   │                                  │   │
│   └─────────────────────┘    │   └──────────────────────────────────┘   │
│                               │                                          │
└───────────────────────────────┴──────────────────────────────────────────┘
```

**Navigation**: No tabs. Everything visible at once. Scroll within panels. Click a strategy card → expands to show full evidence/debate view (Section 3.5). Click a trade idea → same expansion.

**Header bar** is always visible: instrument, time, phase, day type, bias, session P&L, position count. This is the "glanceable" layer — trader should be able to read it in 2 seconds.

### Interaction Patterns

| Action | Result |
|--------|--------|
| Click strategy card | Expand to full evidence + debate view |
| Click trade idea | Expand to full setup with entry/stop/target chart overlay |
| Click position | Show MAE/MFE chart, trail history, exit options |
| Hover level (in Market Context) | Highlight on price chart |
| Click phase (in Trade Plan) | Filter strategy board to that phase's strategies |
| Type in consult bar | Ad-hoc question → routed to domain experts → answer |

### Alert System

| Alert | Trigger | Style |
|-------|---------|-------|
| Strategy FIRED | Signal emitted | Full-width green banner + sound |
| Strategy ARMED | Approaching fire conditions | Subtle yellow pulse on card |
| Risk rule warning | 1 loss away from cutoff, 75% of daily limit | Orange banner |
| Risk rule triggered | 2 consecutive losses, daily limit hit | Red banner, blocks new ideas |
| Day type morph | Classification changed | Blue notification |
| Agent SKIP | Debate resulted in skip | Muted notification (informational) |

---

## 7. Implementation Phases

### Phase A: Backend Foundation (3-5 days)

Build the real-time data pipeline. No dashboard yet — validate with terminal output.

**Tasks**:
1. `BarSource` ABC with `CsvBarSource` (existing backtest) and `LiveBarSource` (file watcher)
2. `FileWatcher` for `G:\My Drive\future_data\1min\` — detect new rows, emit bars
3. `LiveSessionManager` — orchestrates bar consumption, strategy runner, deterministic orchestrator
4. `StrategyStateTracker` — lifecycle state machine per strategy (INACTIVE → WATCHING → ARMED → FIRED → DONE | BLOCKED)
5. Run against today's data. Verify strategy fires match what backtest would produce.

**Validation**: Feed today's CSV through `LiveBarSource` bar-by-bar. Compare strategy fires to backtest. Should be identical.

### Phase B: WebSocket API (2-3 days)

Connect the compute layer to the frontend.

**Tasks**:
1. FastAPI WebSocket endpoint at `/ws/live`
2. `WebSocketHub` — manages connections, broadcasts state changes
3. Message serialization for all event types (Section 4)
4. Full snapshot on connect (client gets current state immediately)
5. Delta updates on events (only changed fields)
6. `/api/consult` REST endpoint for ad-hoc expert queries

**Validation**: Connect with `wscat` or simple test client. Verify all message types arrive.

### Phase C: Dashboard Shell (3-5 days)

Scaffold the new dashboard. Get data flowing to screen.

**Tasks**:
1. Vite + React 19 + Tailwind + Zustand scaffold in `packages/rockit-dashboard/`
2. `useWebSocket` hook — connects to `/ws/live`, updates Zustand store
3. Header bar (instrument, time, phase, day type, bias, P&L)
4. Strategy Board (12 cards, lifecycle states, static data first)
5. Market Context panel (structure, levels, indicators, order flow)
6. Price chart (port from legacy ChartSection.tsx, strip drawing tools)

**Validation**: Dashboard connects, shows live data, strategy cards update as bars arrive.

### Phase D: Trade Plan + Ideas (3-5 days)

The new intelligence layer.

**Tasks**:
1. Trade Plan view — phase timeline, decision tree, risk rules
2. Trade Ideas panel — display ARMED strategies with projected entry/stop/target
3. `TradeIdeaGenerator` backend — proactive scan every 5 min
4. Evidence cards display (table + summary)
5. Agent debate integration — show Advocate/Skeptic/Orchestrator on demand
6. Alert system (strategy fire banners, risk warnings)

**Validation**: Trade ideas appear proactively. Click through to evidence. Debate text renders.

### Phase E: Positions + Journal (2-3 days)

Complete the trading loop.

**Tasks**:
1. Position tracker — live P&L, MAE/MFE, trail level, progress bar
2. Equity curve (intraday Recharts line chart)
3. Port journal from legacy (API calls, data model, pre-fill from agent decisions)
4. Post-session review integration

**Validation**: Full trading session end-to-end. Positions track, journal pre-fills, review generates.

### Phase F: Polish + Backtest Replay (2-3 days)

**Tasks**:
1. Theme system (port 3 themes from legacy)
2. Responsive layout polish
3. **Backtest replay mode**: Feed historical CSV through LiveBarSource at 10x speed. Dashboard replays the session exactly as it would have played live. This is the killer dev/review tool.
4. Sound alerts (port sine wave chirp from legacy)
5. Deep linking (share a specific moment via URL)

**Validation**: Replay a known session. Verify strategy fires, trade ideas, and P&L match backtest.

---

## 8. Backtest Replay Mode — The Bridge to Live

This deserves its own section because it's how we **validate the live system without risking money**.

```
BACKTEST REPLAY = Feed historical bars one at a time through the live pipeline.
                  Dashboard renders exactly what you'd see in real-time.
                  Compare every decision to known backtest outcomes.
```

**How it works**:
1. Select a session date from DuckDB
2. `CsvBarSource` loads that session's bars
3. `LiveSessionManager` processes them one per second (configurable speed: 1x, 5x, 10x, 60x)
4. Dashboard renders in real-time — strategy fires, trade ideas, evidence, debates
5. At end, compare: did every strategy fire match the backtest? Did P&L match?

**Why this matters**:
- Zero-risk validation of the entire pipeline
- See exactly what the dashboard would show at any historical moment
- Review agent debates for past sessions — "would the agent have taken this trade?"
- Train yourself to read the dashboard before going live
- QA the entire system end-to-end without any production risk

**Speed controls**: 1x (real-time), 5x (1 hour = 12 min), 10x (1 hour = 6 min), 60x (full session in ~6 min). Pause/step for detailed review.

---

## 9. What We're NOT Building (Scope Boundaries)

| Feature | Why Not |
|---------|---------|
| Mobile responsive | Desktop-only tool for focused trading. Phone = distraction. |
| Multi-instrument | NQ first. Add ES/YM later if needed. Single instrument simplifies. |
| Order execution | Dashboard SHOWS trades. NinjaTrader EXECUTES them. No broker integration. |
| Chat interface | Legacy has Gemini chat. We replace it with structured Trade Ideas. Chat is lazy UX — the system should proactively tell you, not wait to be asked. |
| User accounts / multi-user | Single user system. Auth optional for local use. |
| Historical analytics | DuckDB + `/analyze-trades` handles this. Dashboard is for LIVE. |
| Backtesting UI | CLI backtesting works. Don't duplicate in dashboard. |
| Complex drawing tools | Legacy has them. Live dashboard shows strategy annotations, not manual drawings. |

---

## 10. Migration from Legacy RockitUI

### What Ports Over

| Legacy Component | New Location | Changes |
|-----------------|--------------|---------|
| `ChartSection.tsx` (16 KB) | `PriceChart.tsx` | Strip drawing tools, add strategy markers |
| `tabs/BriefTab.tsx` | Merged into Market Context | Combined with Logic + Intraday |
| `tabs/LogicTab.tsx` | Merged into Market Context | Combined with Brief + Intraday |
| `tabs/IntradayTab.tsx` | Merged into Market Context | Combined with Brief + Logic |
| `tabs/TPOTab.tsx` | Market Context (mini view) | Simplified, no full analyzer |
| `JournalModal.tsx` (54 KB) | `Journal.tsx` | Slimmed down, pre-filled by agents |
| `types.ts` | Extended with strategy/agent types | Add StrategyState, TradeIdea, etc |
| `dataHelpers.ts` | Replaced by WebSocket hook | No more GCS polling |
| Theme system (CSS vars) | Ported directly | Same 3 themes |

### What Gets Dropped

| Legacy Component | Why |
|-----------------|-----|
| `ChatPanel.tsx` (44 KB) | Gemini chat replaced by structured Trade Ideas |
| `GeminiAudit.tsx` (23 KB) | Replaced by Agent Intelligence view |
| `HTFCoach.tsx` (22 KB) | HTF context in Market Context panel |
| `RockitAudit.tsx` (20 KB) | Health check → simple status indicator in header |
| `TradeIdea.tsx` (73 KB) | Completely redesigned as proactive Trade Ideas panel |
| `MigrationChart.tsx` (30 KB) | DPOC migration → single line in Market Context |
| `Sidebar.tsx` (7.9 KB) | No file browser — live data only (replay mode has session picker) |
| `LoginScreen.tsx` (7.1 KB) | Local-first, no auth needed |
| `ProfileVisualizer.tsx` | Merged into Market Context mini view |

**Net effect**: Legacy is 536 KB of TypeScript across 37 files. New dashboard targets ~200 KB across ~20 files. Less code, more signal.

---

## 11. Success Criteria

### MVP (Phases A-D complete)

- [ ] Dashboard connects to live data via WebSocket
- [ ] Strategy board shows all 12 strategies with correct lifecycle states
- [ ] Trade plan timeline shows current phase with "you are here" indicator
- [ ] At least 1 trade idea appears proactively when a strategy is ARMED
- [ ] Market context shows IB, VA, levels, indicators in a single panel
- [ ] Price chart shows strategy fire annotations
- [ ] Backtest replay mode works for any historical session
- [ ] Strategy fires in live mode match backtest output for same data

### Full System (All phases complete)

- [ ] Position P&L tracking with MAE/MFE and trailing stop visualization
- [ ] Agent debate view with evidence cards
- [ ] Journal pre-filled from agent decisions
- [ ] Alert system (sound + visual for strategy fires)
- [ ] Risk rules enforced (position limits, daily loss, loss streak)
- [ ] Ad-hoc expert consultation via text input
- [ ] Replay any of 274 historical sessions at variable speed
- [ ] Full session end-to-end: market opens → strategies fire → ideas generated → positions tracked → session review → journal saved

---

## 12. Open Questions

1. **NinjaTrader data latency**: How fast does NinjaTrader write to Google Drive? If there's a 30-60s delay, our "live" system is 30-60s behind. Is this acceptable? Alternative: NinjaTrader writes to local folder directly (faster but harder to sync across machines).

2. **Qwen3.5 latency for debates**: Agent debate requires LLM inference. On Spark DGX with Qwen3.5-35B, how long does a full Advocate/Skeptic/Orchestrator cycle take? If >30s, we may need to pre-compute debates for ARMED strategies before they fire, or run debates async and show "Debate pending..." while processing.

3. **Which instrument first?**: NQ is our primary with all 274 sessions of backtest data. Start with NQ-only and add ES/YM later.

4. **Position sizing integration**: Current backtest uses fixed 1 NQ contract. Live trading may use MNQ (micro) for position sizing. Dashboard should show both the strategy signal (always in NQ points) and the actual position (user-configured: NQ, MNQ, size).

5. **Alerting beyond the dashboard**: Should strategy fires also push to phone (Pushover/Telegram)? Useful if trader steps away from screen. Keep simple — single webhook to notification service.

6. **Session boundaries**: NinjaTrader futures session is 6:00 PM - 5:00 PM next day. Our strategies fire RTH only (9:30-16:00). Pre-market data (overnight) is needed for context but no strategy fires. FileWatcher needs to handle session rollover cleanly.
