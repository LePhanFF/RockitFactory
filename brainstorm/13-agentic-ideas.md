# 13 — Domain Expert Agents: Extending the Agentic Framework

> Brainstorm document. Living whiteboard — edit freely.

---

## Original User Ideas

Since now we have a framework to add multiple strategy and do quant studies to improve them.
We have a deterministic layer.
We have an agentic layer for review (advocate vs skeptic).
Now I think we need a domain agent such as:

- ICT
- TPO
- Scalper
- VWAP
- EMA
- price-divergence
- mean-reversion
- orderflow like bookmap
- cvd

Each of these expert becomes "DOMAIN" expertise (not necessarily strategy) - they do the
analysis at the domain level using our datawarehouse, which means we need each agent to
study and create data and observations for specific domain. I would assume they have a
scorecard for each of these agent.

So when a question from user comes, or from a signal of a strategy, it goes through rigorous
domain evaluations and feed to "advocate" input. Meanwhile skeptic for each domain would do
the opposite.

Would this break down help?

In particular if a scalper system is running macd for example LTF, in theory scalper can give
us a scorecard. It has to be fast. But if we want a good scalping signal, we consult the
entire stack of domain experts - which might take 5 min to generate a 30 min swing idea.

Or is this overkill?

- what are new requirements
- what new data and analysis needs to be done
- do we need to train llm, or will they be strictly recalling data and summary of data (is this RAG?)

---

## Brainstorm Response

### The Honest Answer: Yes Overkill Today, But the Right Scalable Bet

Let's be direct about this. The current 2-observer system is **already working**. Adding 8
domain experts is engineering effort that may not move the needle immediately. But it builds
the **plug-in architecture** that makes adding a "Dalton Expert" or "Wyckoff Expert" next
month trivial instead of a refactor.

The key insight: **domain experts don't need LLM**. Most of this is deterministic analysis
over DuckDB + the 38 existing modules. The LLM only enters at the Advocate/Skeptic synthesis
layer where it needs to *reason* about conflicting domain opinions.

---

## Head-to-Head: Current Architecture vs Domain Experts

### What We Have Now

```
CRI Gate → ProfileObserver (4 cards) → MomentumObserver (5 cards) → [Debate] → Orchestrator
```

**ProfileObserver** covers:
1. TPO shape (b/p/d) — bullish/bearish/neutral
2. VA position (price vs VAH/VAL) — momentum or fading
3. POC position (entry vs POC) — value play detection
4. Poor extremes — weak resistance/support

**MomentumObserver** covers:
1. DPOC regime (trending/rotating/migrating)
2. Trend strength (strong_bull/bear/weak/neutral)
3. Wick traps (bear/bull wick counts)
4. IB extension multiple (overextension warning)
5. Bias alignment (session bias vs signal direction)

**Total: up to 9 evidence cards per signal. Gate card makes 10.**

### What's Good About the Current System

| Strength | Why It Matters |
|----------|----------------|
| **Simple** | 2 observers, easy to debug, easy to test (60 tests) |
| **Fast** | <10ms for all observers combined |
| **Already backtested** | Run C/D/E results exist — we know the baseline |
| **Covers the big hitters** | Bias alignment (#1 predictor), TPO shape, DPOC, trend — these are the top signals from our Phase 5 observations |
| **LLM debate adds nuance** | Advocate/Skeptic can reason about the 9 cards with historical context |

### What's Missing From the Current System

| Gap | Impact | Example |
|-----|--------|---------|
| **No VWAP awareness** | Misses mean-reversion signals at VWAP bands | LONG at -2σ VWAP band is high-probability, but observers can't see it |
| **No EMA structure** | Can't tell if all EMAs are stacked bullish | A LONG with all EMAs aligned is much stronger than one fighting the 50 EMA |
| **No ICT imbalance context** | FVG data exists in deterministic modules but never reaches the evidence pool | Unfilled FVG below entry = strong support, currently invisible to debate |
| **No order flow / CVD** | Wick count is a crude proxy; real CVD divergence is much richer | Price up + CVD divergence = distribution — 65% reversal rate in studies |
| **No cross-instrument** | Can't see NQ/ES divergence in real-time | SMT divergence is a high-quality ICT signal, completely blind to it |
| **No scalper fast-path** | Full pipeline (~140s with debate) is too slow for LTF | 1-min scalp signals need sub-100ms feedback |
| **Observers are generalists** | ProfileObserver mixes TPO + VA + POC — no deep domain logic | A TPO Expert would know about opening type, value migration, composite profiles |
| **No historical enrichment per domain** | DuckDB queries are strategy-level, not domain-level | "When VWAP slope was negative + LONG, what happened?" — can't ask this |

### Concrete Example: CRI STAND_DOWN on 2026-03-10

**What happened with 2 observers**:
- CRI STAND_DOWN fired (bear trap false positive: 26 bear / 26 bull wicks = 50/50)
- ProfileObserver: b-shape → bullish 0.7, entry below POC → bullish 0.65
- MomentumObserver: strong_bull trend → bullish 0.8, bias Bullish → bullish 0.75
- CRI bearish 0.7 card competed with 4 bullish cards
- Result: bullish evidence won. Both signals got through. OR Accept was a +$505 winner.

**What would have happened with 8 domain experts**:
- Same CRI bearish 0.7 card
- TPO Expert: b-shape 0.7 + value migrating up 0.65 + Open-Test-Drive 0.6 = 3 bullish cards
- EMA Expert: all EMAs stacked bullish 0.75 + price above EMA21 0.6 = 2 bullish cards
- VWAP Expert: price above VWAP 0.6 + VWAP slope positive 0.65 = 2 bullish cards
- ICT Expert: unfilled FVG below at 21,400 0.65 = 1 bullish card
- Order Flow Expert: CVD trending with price 0.7 = 1 bullish card
- Scalper Expert: MACD expanding 0.6 = 1 bullish card
- **Total: ~10 bullish cards vs 1 bearish CRI card**
- CRI false positive gets **completely overwhelmed** by domain consensus
- Advocate's case becomes much stronger with domain-specific evidence
- Skeptic has less room to challenge when 6 independent domains agree

**The difference**: With 2 observers, the right decision happened but on thin margin.
With 8 experts, the right decision happens with overwhelming consensus. The LLM debate
becomes richer because it has domain-specific reasoning to work with.

### The Honest Tradeoffs

| Factor | 2 Observers (Current) | 8 Domain Experts (Proposed) |
|--------|----------------------|----------------------------|
| **Evidence cards** | ~10 per signal | ~25 per signal |
| **Observer speed** | <10ms | <50ms (still fast) |
| **Debate quality** | Good — covers top predictors | Better — domain-specific arguments |
| **False positive resistance** | Moderate — 4 cards vs 1 CRI | Strong — 10+ cards can overwhelm 1 false signal |
| **Build effort** | Done | 6-8 new modules + refactor (~2 weeks) |
| **Test surface** | 60 tests | ~120 tests (more to maintain) |
| **LLM token cost** | ~800 tokens for evidence section | ~1,500 tokens (still under context limit) |
| **Debug complexity** | Easy — 2 observers to trace | Moderate — more sources to trace |
| **Data requirements** | All existing | Need VWAP, delta columns (some NinjaTrader export changes) |
| **Risk of noise** | Low — only high-signal cards | Medium — more cards = potential noise if poorly tuned |
| **Marginal value of each new expert** | N/A | Diminishing — first 3 add a lot, last 3 add less |

### Where Experts Win vs Where They Don't

**Experts clearly win when**:
- Multiple domains agree → high-conviction decision (overwhelming consensus)
- Domains disagree → debate has specific contradictions to reason about
- Edge cases where one domain sees what others miss (FVG support, CVD divergence)
- User queries ("what does the tape say?") — richer narrative from 8 perspectives

**Experts don't help much when**:
- Signal is obviously good/bad — 2 observers already catch it
- Data is thin (early session, missing fields) — more experts with no data = more None returns
- LLM debate already makes the right call — adding cards just makes it more verbose
- The bottleneck is strategy logic, not evidence quality

### The Scalability Argument

This is the real win. Today you want 8 domains. Next month you realize:

> "I need a **Dalton Expert** that specifically knows about day type transitions,
> initiative vs responsive activity, and TPO count building patterns."

With the current 2-observer system, that means **modifying MomentumObserver** or
**ProfileObserver** — adding more methods to an already-mixed class, or creating a third
observer with no clear base class pattern.

With the DomainExpert base class:

```python
class DaltonExpert(DomainExpert):
    domain = "dalton"

    def scorecard(self, context: dict) -> list[EvidenceCard]:
        cards = []
        cards.append(self._day_type_transition_card(context))    # Is today's type shifting?
        cards.append(self._initiative_responsive_card(context))   # Who's in control?
        cards.append(self._tpo_count_building_card(context))      # Where is value building?
        cards.append(self._auction_completion_card(context))       # Is the auction finishing?
        return [c for c in cards if c is not None]

    def historical_query(self, conn, signal):
        return query(conn, """
            SELECT outcome, COUNT(*), AVG(net_pnl)
            FROM trades t JOIN deterministic_tape d ...
            WHERE d.day_type = ? AND d.tpo_shape = ?
        """, [day_type, tpo_shape])
```

**That's it.** Drop it into `agents/experts/dalton.py`, add it to the pipeline's expert
list, write 10 tests. No refactoring, no touching existing code.

Same pattern for **Wyckoff Expert**, **Elliott Wave Expert**, **Fibonacci Expert**,
**Volume Spread Analysis Expert** — any methodology becomes a pluggable module.

```
Adding a new domain expert:
  1. Create experts/{domain}.py (extends DomainExpert)     — 100-200 lines
  2. Define scorecard() → list[EvidenceCard]                — 3-5 cards
  3. Optional: historical_query() for DuckDB enrichment     — 1 SQL query
  4. Register in pipeline's expert list                     — 1 line
  5. Write tests                                            — 10-15 tests
  Total: ~half a day per expert
```

Versus today, where adding a new analysis domain means modifying an existing observer,
potentially breaking existing card IDs, and muddying the source attribution in evidence cards.

---

## Verdict: Build the Base Class Now, Add Experts Incrementally

The **DomainExpert base class + refactor of existing observers** is not overkill.
It's a ~1 day refactor that gives us the plug-in architecture forever.

**Building all 8 experts at once** before we have A/B test data proving the current
system's gaps? That's premature. Instead:

```
Week 1: DomainExpert base class + refactor ProfileObserver → TpoExpert,
         MomentumObserver → split into pieces. Run backtest. Verify no regression.

Week 2: Add VWAP Expert + EMA Expert (highest signal-to-noise).
         Run A/B test. Measure: do more cards improve debate quality?

Week 3: If yes → add ICT Expert + Order Flow Expert.
         If no → stop. The base class is there for later.

Later:  Dalton Expert, Scalper Expert, etc. — plug in as needed.
```

The scalability isn't the goal. It's the **insurance policy** — when you inevitably want
a new domain, the cost of adding it is half a day instead of a refactor.

---

## Architecture: Domain Expert Layer

```
                                Signal fires (OR Rev LONG)
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
            ┌──────────┐     ┌───────────────┐    ┌──────────────┐
            │ ICT Expert│     │  TPO Expert   │    │ VWAP Expert  │  ... (8 domains)
            │           │     │               │    │              │
            │ FVGs      │     │ Shape         │    │ Trend bands  │
            │ OBs       │     │ POC migration │    │ Anchored VWAP│
            │ SMT       │     │ Poor extremes │    │ Std dev touch│
            │ Liquidity │     │ Single prints │    │ Mean revert  │
            │ Judas     │     │ B/P/D/Neutral │    │ Slope + accel│
            └─────┬─────┘     └──────┬────────┘    └──────┬───────┘
                  │                   │                     │
                  ▼                   ▼                     ▼
            ┌──────────┐     ┌───────────────┐    ┌──────────────┐
            │ Scorecard │     │  Scorecard    │    │  Scorecard   │
            │ 3 cards   │     │  4 cards      │    │  3 cards     │
            │ ICT_bull  │     │  TPO_bull     │    │  VWAP_bull   │
            │ ICT_bear  │     │  TPO_bear     │    │  VWAP_bear   │
            │ ICT_conf  │     │  TPO_conf     │    │  VWAP_bias   │
            └─────┬─────┘     └──────┬────────┘    └──────┬───────┘
                  │                   │                     │
                  └───────────┬───────┴─────────────────────┘
                              ▼
                    ┌───────────────────┐
                    │  Evidence Pool    │  (20-30 cards total)
                    │  from all domains │
                    └────────┬──────────┘
                             │
                  ┌──────────┴──────────┐
                  ▼                     ▼
           ┌────────────┐       ┌─────────────┐
           │  Advocate   │       │   Skeptic   │
           │  (LLM)      │       │   (LLM)     │
           │ Sees ALL     │       │ Challenges  │
           │ domain cards │       │ weak cards  │
           └──────┬───────┘       └──────┬──────┘
                  │                      │
                  └──────────┬───────────┘
                             ▼
                    ┌─────────────────┐
                    │  Orchestrator   │
                    │  TAKE/SKIP/     │
                    │  REDUCE_SIZE    │
                    └─────────────────┘
```

### Key Design Decision: Domain Experts Are Deterministic, Not LLM

| Layer | Speed | Method | Example |
|-------|-------|--------|---------|
| Domain Expert | <50ms | Deterministic code + DuckDB queries | TPO Expert reads shape, POC, VA → produces 4 cards |
| Pattern Miner | <200ms | DuckDB aggregate queries | "80P LONG when VWAP slope negative: 38% WR" |
| Advocate/Skeptic | ~70s each | LLM (Qwen3.5) | "TPO b-shape + ICT FVG below = strong LONG case" |

**Why not LLM per domain?** Speed. 8 domain experts × 70s = 9+ minutes per signal. Instead,
each domain expert is a fast deterministic observer that queries the datawarehouse and
produces evidence cards. The LLM *synthesizes* across domains at the Advocate/Skeptic layer.

---

## The 8 Domain Experts

### 1. ICT Expert (`IctObserver`)

**Domain**: Inner Circle Trader concepts — FVGs, order blocks, liquidity sweeps, SMT divergence

**Data Sources** (existing deterministic modules):
- `fvg_detection.py` — Fair Value Gaps (unfilled, filled, BPR clusters)
- `premarket.py` — SMT divergence flag, overnight levels
- `or_reversal.py` — Judas swing / sweep detection

**New Data Needed**:
- Order Block detection (last bullish/bearish candle before FVG)
- Liquidity pool mapping (equal highs/lows, trendline stops)
- Breaker block detection (broken OB becomes support/resistance)

**Scorecard (3-4 cards)**:
| Card | Logic | Direction | Strength |
|------|-------|-----------|----------|
| `ict_fvg_support` | Unfilled bullish FVG below price + LONG | bullish | 0.6-0.8 |
| `ict_liquidity_sweep` | Stop hunt below EQL + reversal candle | bullish | 0.7 |
| `ict_smt_divergence` | ES makes new low, NQ doesn't | bullish | 0.65 |
| `ict_order_block` | Price in bullish OB zone + LONG | bullish | 0.55 |

**Historical DuckDB Query**:
```sql
-- How do trades perform when FVG is present below entry?
SELECT outcome, COUNT(*), AVG(net_pnl)
FROM trades t
JOIN deterministic_tape d ON t.session_date = d.session_date
WHERE JSON_EXTRACT(d.snapshot_json, '$.fvg_detection.unfilled_fvgs') IS NOT NULL
  AND t.direction = 'LONG'
GROUP BY outcome
```

---

### 2. TPO Expert (`TpoObserver`) — **Upgrade of ProfileObserver**

**Domain**: Market Profile / TPO analysis — shape, distribution, single prints, poor extremes

**Data Sources** (existing):
- `tpo_profile.py` — Shape, single prints, poor highs/lows, fattening, naked levels
- `volume_profile.py` — POC, VAH, VAL, HVN/LVN
- `ib_location.py` — IB range, width class, extensions

**New Data Needed**:
- TPO count per period (A through M) — identifies which periods are building value
- Composite profile (multi-day TPO) for context
- Range extension count (how many periods extend beyond IB)
- Opening type classification (Open-Drive, Open-Test-Drive, Open-Rejection-Reverse, Open-Auction)

**Scorecard (5 cards)**:
| Card | Logic | Example |
|------|-------|---------|
| `tpo_shape_bias` | b-shape → bullish, p-shape → bearish, D → neutral | str 0.7 |
| `tpo_poor_extreme` | Poor high → revisit likely (bearish for shorts at high) | str 0.5 |
| `tpo_single_prints` | Unfilled single prints = magnet targets | str 0.6 |
| `tpo_value_migration` | Value area shifting up vs prior day | str 0.65 |
| `tpo_opening_type` | Open-Drive = trending, Open-Auction = balance | str 0.7 |

**Historical DuckDB Pattern**:
```sql
-- When b-shape develops by C period, what's the OR Rev LONG WR?
SELECT outcome, COUNT(*), AVG(net_pnl)
FROM trades t
JOIN deterministic_tape d ON t.session_date = d.session_date
WHERE JSON_EXTRACT(d.snapshot_json, '$.tpo_profile.tpo_shape') = 'b_shape'
  AND d.period <= 'C'
  AND t.strategy_name = 'OR Rev' AND t.direction = 'LONG'
GROUP BY outcome
```

---

### 3. VWAP Expert (`VwapObserver`)

**Domain**: Volume-Weighted Average Price — trend, mean reversion, standard deviation bands

**Data Sources** (existing):
- `inference_engine.py` — Uses VWAP internally for bias
- Bar data with VWAP column (from NinjaTrader export)

**New Data Needed**:
- Anchored VWAP (anchored to session open, OR high/low, IB extreme)
- VWAP standard deviation bands (1σ, 2σ, 3σ)
- VWAP slope and acceleration (trending vs flat)
- Price touches of VWAP (support/resistance count)
- Time-weighted VWAP reversion rate (how fast price returns)

**New Deterministic Module**: `vwap_analysis.py`
```python
def analyze(session_data: pd.DataFrame) -> dict:
    vwap = session_data['VWAP']
    price = session_data['Close']
    return {
        'vwap_slope': slope_of_last_n_bars(vwap, 12),  # 1-hour slope
        'vwap_acceleration': second_derivative(vwap, 12),
        'price_vs_vwap': 'above' if price.iloc[-1] > vwap.iloc[-1] else 'below',
        'vwap_distance_pct': (price.iloc[-1] - vwap.iloc[-1]) / vwap.iloc[-1] * 100,
        'std_band_position': which_band(price.iloc[-1], vwap, session_data),
        'vwap_touch_count': count_crosses(price, vwap),
        'anchored_vwaps': {
            'session_open': anchored_vwap(session_data, anchor='open'),
            'or_high': anchored_vwap(session_data, anchor='or_high'),
            'or_low': anchored_vwap(session_data, anchor='or_low'),
        },
    }
```

**Scorecard (3 cards)**:
| Card | Logic | Example |
|------|-------|---------|
| `vwap_trend` | Slope positive + price above = bullish | str 0.7 |
| `vwap_mean_revert` | Price at 2σ band + decelerating = reversion likely | str 0.6 |
| `vwap_reclaim` | Price crosses back above VWAP from below | str 0.65 |

---

### 4. EMA Expert (`EmaObserver`)

**Domain**: Exponential Moving Average structure — trend, crossovers, dynamic support/resistance

**Data Sources** (existing):
- `inference_engine.py` — Uses EMA20/EMA50 for bias vote
- `regime_context.py` — EMA cross direction

**New Data Needed**:
- Multi-timeframe EMA stack (8, 21, 50, 200)
- EMA fan (all EMAs aligned = strong trend)
- EMA compression (all EMAs within X points = breakout imminent)
- EMA slope (rate of change for each EMA)
- Price distance from key EMA (stretched → reversion, hugging → continuation)

**New Deterministic Module**: `ema_structure.py`
```python
def analyze(session_data: pd.DataFrame) -> dict:
    emas = {8: ema(8), 21: ema(21), 50: ema(50), 200: ema(200)}
    return {
        'ema_alignment': 'bullish' if emas[8] > emas[21] > emas[50] else ...,
        'ema_fan_width': max(emas.values()) - min(emas.values()),
        'ema_compression': fan_width < threshold,
        'ema_slopes': {k: slope(v) for k, v in emas.items()},
        'price_vs_ema21': price / emas[21] - 1,
        'recent_cross': detect_cross(emas[8], emas[21], lookback=5),
    }
```

**Scorecard (3 cards)**:
| Card | Logic | Example |
|------|-------|---------|
| `ema_alignment` | All EMAs bullish stacked + LONG signal | str 0.75 |
| `ema_compression` | Fan width < 10pts = pending breakout | str 0.5 |
| `ema_dynamic_sr` | Price bouncing off EMA21 as support | str 0.6 |

---

### 5. Scalper Expert (`ScalperObserver`)

**Domain**: Ultra-short-term momentum — MACD, RSI, tick-level momentum, micro-structure

**Data Sources** (existing):
- Bar data with MACD columns (if available from NinjaTrader)
- 1-min candle data (already in pipeline)

**New Data Needed**:
- MACD histogram direction + zero-line cross
- RSI(14) with overbought/oversold
- Tick momentum (uptick/downtick ratio over last 5 bars)
- Micro-channel detection (last 10-20 bars)
- Speed-of-move metric (ATR ratio current vs average)

**Key Constraint: MUST BE FAST** (<10ms). This is the only domain expert that a scalper
system might call in isolation without the full stack.

**New Deterministic Module**: `scalper_momentum.py`
```python
def analyze(session_data: pd.DataFrame, lookback: int = 20) -> dict:
    recent = session_data.tail(lookback)
    return {
        'macd_histogram': recent['MACD_Hist'].iloc[-1],
        'macd_direction': 'expanding' if abs(recent['MACD_Hist'].iloc[-1]) > abs(recent['MACD_Hist'].iloc[-2]) else 'contracting',
        'macd_zero_cross': detect_zero_cross(recent['MACD_Hist']),
        'rsi': compute_rsi(recent['Close'], 14),
        'tick_momentum': uptick_ratio(recent),
        'speed_of_move': current_atr / avg_atr,
        'micro_channel': detect_channel(recent, max_bars=15),
    }
```

**Scorecard (3 cards)**:
| Card | Logic | Example |
|------|-------|---------|
| `scalper_momentum` | MACD expanding + RSI not OB + LONG | str 0.6 |
| `scalper_exhaustion` | MACD contracting + RSI OB = reversal warning | str 0.5 |
| `scalper_micro_trend` | Micro-channel intact + aligned | str 0.55 |

**Speed tier**: This expert can give a fast scorecard in <10ms for LTF scalping decisions.
For swing-quality decisions, the full domain stack runs (5-min cycle).

---

### 6. Order Flow Expert (`OrderFlowObserver`)

**Domain**: BookMap-style order flow — CVD, delta, absorption, iceberg detection

**Data Sources** (existing):
- `wick_parade.py` — Wick trap counts (proxy for absorption)
- Delta columns in session data (from NinjaTrader export)

**New Data Needed**:
- CVD (Cumulative Volume Delta) — running cumulative of (ask volume - bid volume)
- CVD divergence detection (price up + CVD down = distribution)
- Delta bars (per-bar ask-bid volume)
- Absorption detection (high volume at level + price doesn't move)
- Volume cluster analysis (high-volume nodes on LTF)

**New Deterministic Module**: `order_flow.py`
```python
def analyze(session_data: pd.DataFrame) -> dict:
    # CVD from delta data
    if 'AskVolume' in session_data.columns and 'BidVolume' in session_data.columns:
        delta = session_data['AskVolume'] - session_data['BidVolume']
        cvd = delta.cumsum()
    else:
        # Fallback: estimate from Up/Down volume
        delta = session_data.get('UpVolume', 0) - session_data.get('DownVolume', 0)
        cvd = delta.cumsum()

    return {
        'cvd_trend': 'bullish' if cvd.iloc[-1] > cvd.iloc[-12] else 'bearish',
        'cvd_divergence': detect_divergence(session_data['Close'], cvd, lookback=20),
        'delta_bars': {
            'last_5_avg': delta.tail(5).mean(),
            'last_20_avg': delta.tail(20).mean(),
            'ratio': delta.tail(5).mean() / delta.tail(20).mean() if delta.tail(20).mean() != 0 else 0,
        },
        'absorption_events': detect_absorption(session_data, cvd),
        'volume_climax': detect_climax(session_data['Volume'], threshold=3.0),
    }
```

**Scorecard (3 cards)**:
| Card | Logic | Example |
|------|-------|---------|
| `flow_cvd_trend` | CVD trending with price = confirmation | str 0.7 |
| `flow_cvd_divergence` | Price up + CVD down = distribution warning | str 0.65 |
| `flow_absorption` | Heavy selling absorbed at level = support | str 0.6 |

---

### 7. Price Divergence Expert (`DivergenceObserver`)

**Domain**: Multi-instrument divergence — ES vs NQ, NQ vs YM, correlated instruments

**Data Sources** (existing):
- `premarket.py` — SMT divergence flag (ES vs NQ)
- Multi-instrument session data (already in `data/sessions/`)

**New Data Needed**:
- Real-time NQ/ES ratio tracking (leading indicator)
- Inter-market divergence scoring (NQ makes new high but ES doesn't)
- Sector rotation proxy (NQ vs YM = tech vs industrial)
- VIX term structure (front-month vs back-month)
- Correlation regime (normal vs decorrelated)

**New Deterministic Module**: `cross_market.py`
```python
def analyze(nq_data, es_data, ym_data) -> dict:
    return {
        'nq_es_ratio': nq_data['Close'].iloc[-1] / es_data['Close'].iloc[-1],
        'nq_es_divergence': detect_divergence(nq_data['Close'], es_data['Close']),
        'nq_ym_divergence': detect_divergence(nq_data['Close'], ym_data['Close']),
        'leader': identify_leader(nq_data, es_data),  # Which instrument leads
        'correlation_regime': rolling_correlation(nq_data, es_data, window=20),
    }
```

**Scorecard (2-3 cards)**:
| Card | Logic | Example |
|------|-------|---------|
| `divergence_smt` | NQ new low, ES holds = bullish NQ | str 0.65 |
| `divergence_leader` | ES leading up, NQ lagging = NQ catch-up expected | str 0.5 |
| `divergence_decorrelated` | Correlation broken = caution | str 0.4 (warning) |

**Constraint**: Requires multi-instrument data loaded simultaneously. Currently we backtest
one instrument at a time — this expert may need a multi-instrument data loader.

---

### 8. Mean Reversion Expert (`MeanReversionObserver`)

**Domain**: Statistical mean reversion signals — Bollinger Bands, z-score, Keltner channels, regime detection

**Data Sources** (existing):
- `regime_context.py` — Consecutive balance days, daily ATR
- `inference_engine.py` — Day type classification
- `ib_location.py` — Extension multiple

**New Data Needed**:
- Bollinger Band position (upper, middle, lower, squeeze)
- Z-score of price relative to rolling mean
- Keltner channel position
- Balance/trend regime classifier (statistical, not just day type)
- Reversion target calculation (where does price revert to?)

**New Deterministic Module**: `mean_reversion.py`
```python
def analyze(session_data: pd.DataFrame) -> dict:
    close = session_data['Close']
    bb_upper, bb_mid, bb_lower = bollinger_bands(close, 20, 2)
    kc_upper, kc_mid, kc_lower = keltner_channels(session_data, 20, 1.5)

    return {
        'bb_position': bb_percentile(close.iloc[-1], bb_upper.iloc[-1], bb_lower.iloc[-1]),
        'bb_squeeze': bb_bandwidth(close) < kc_bandwidth(session_data),
        'z_score': (close.iloc[-1] - close.rolling(20).mean().iloc[-1]) / close.rolling(20).std().iloc[-1],
        'regime': 'mean_reverting' if abs(z_score) > 2.0 else 'trending' if abs(z_score) < 0.5 else 'neutral',
        'reversion_target': close.rolling(20).mean().iloc[-1],
        'overextension_pct': (close.iloc[-1] - bb_mid.iloc[-1]) / (bb_upper.iloc[-1] - bb_mid.iloc[-1]) * 100,
    }
```

**Scorecard (3 cards)**:
| Card | Logic | Example |
|------|-------|---------|
| `mr_z_score` | Z > 2.0 + SHORT signal = reversion support | str 0.65 |
| `mr_bb_squeeze` | BB inside Keltner = breakout imminent | str 0.5 |
| `mr_regime` | Balance regime + contrarian strategy = aligned | str 0.6 |

---

## Two-Tier Execution Model

Your intuition about speed tiers is exactly right:

### Tier 1: Fast Scorecard (<100ms)

For scalper/LTF signals that need immediate feedback:

```
Signal → [Scalper Expert only] → Quick score → trade/pass
```

- Only the relevant domain expert fires
- No LLM debate
- Deterministic scoring only
- Use case: MACD crossover scalp on 1-min chart

### Tier 2: Full Domain Stack (~5 min)

For swing signals that benefit from comprehensive analysis:

```
Signal → [All 8 Domain Experts] → Evidence Pool → Advocate/Skeptic → Orchestrator
```

- All domain experts produce cards in parallel (<500ms total)
- Pattern Miner enriches with historical data (<200ms)
- LLM debate synthesizes (~140s for Advocate + Skeptic)
- Use case: OR Rev LONG at 9:45 — should we take this swing?

### Tier 3: User Query (on demand)

For interactive analysis without a strategy signal:

```
User: "What does the tape say right now?"
→ [All 8 Domain Experts] → Evidence Pool → Summary generation (LLM)
```

- No signal needed
- Domain experts produce their scorecards
- LLM generates a narrative synthesis
- Use case: Dashboard "Ask the Experts" button after 10:30

```
┌────────────────────────────────────────────────────┐
│                 EXECUTION TIERS                      │
├────────────────────────────────────────────────────┤
│                                                      │
│  Tier 1: FAST (<100ms)                              │
│  ┌─────────┐                                        │
│  │ Scalper  │ → Quick score → trade                 │
│  └─────────┘                                        │
│                                                      │
│  Tier 2: FULL (~5min)                               │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐│
│  │ ICT │ TPO │ VWAP│ EMA │Scalp│ OF  │ Div │ MR  ││
│  └──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┘│
│     └─────┴─────┴─────┴─────┴─────┴─────┴─────┘    │
│                        │                             │
│              ┌─────────┴─────────┐                   │
│              │  Advocate/Skeptic  │ (~140s)           │
│              └────────┬──────────┘                   │
│                       ▼                              │
│              ┌──────────────┐                        │
│              │ Orchestrator │ → TAKE/SKIP/REDUCE     │
│              └──────────────┘                        │
│                                                      │
│  Tier 3: ON-DEMAND (user query)                     │
│  Same as Tier 2 but with narrative generation       │
│  instead of trade decision                          │
│                                                      │
└────────────────────────────────────────────────────┘
```

---

## Scorecard vs Bayesian: What Are We Actually Doing?

### Current Scoring: Additive Weighted Sum (Not Bayesian)

The orchestrator right now does this:

```python
for card in cards:
    weighted = card.strength * LAYER_WEIGHTS[card.layer]   # e.g. 0.8 * 1.0 = 0.8
    if card.direction == "bullish":
        bull_score += weighted
    elif card.direction == "bearish":
        bear_score += weighted

conviction = abs(bull_score - bear_score) / (bull_score + bear_score)
```

This is **additive accumulation**. Each card adds to the pile. Two weak bullish cards (0.3
each) add up the same as one strong bullish card (0.6). There's no concept of "this evidence
should multiply my confidence" vs "this evidence should barely move the needle."

**Problems with additive scoring**:
1. **No base rate**: We ignore that OR Rev LONG has 76% WR historically. The prior matters.
2. **Independence assumption**: We treat every card as equally independent. But TPO b-shape
   and DPOC trending_up are highly correlated — counting both double-counts the same signal.
3. **No diminishing returns**: The 5th bullish card adds the same weight as the 1st. But in
   reality, after 4 domains agree, the 5th agreeing adds almost no new information.
4. **No likelihood ratios**: A "bias alignment" card with 0.75 strength doesn't mean "75%
   likely." It means "I feel 0.75 confident." There's no calibration against historical data.

### True Bayesian Updating: What It Would Look Like

Bayesian scoring starts with a **prior** (base rate from DuckDB) and **updates** with each
evidence card as a **likelihood ratio**:

```
Prior: P(win | OR Rev LONG) = 0.764  (from 55 trades, 76.4% WR)

Evidence 1: TPO b-shape
  P(b_shape | win) = 0.82    (82% of winning OR Rev LONGs had b-shape)
  P(b_shape | lose) = 0.54   (54% of losing OR Rev LONGs had b-shape)
  Likelihood ratio = 0.82 / 0.54 = 1.52

Update: posterior_odds = prior_odds × 1.52
  prior_odds = 0.764 / 0.236 = 3.24
  posterior_odds = 3.24 × 1.52 = 4.92
  P(win | evidence) = 4.92 / (1 + 4.92) = 0.831   → 83.1%

Evidence 2: Bias alignment = Bullish
  P(bullish_bias | win) = 0.90
  P(bullish_bias | lose) = 0.38
  Likelihood ratio = 0.90 / 0.38 = 2.37

Update: posterior_odds = 4.92 × 2.37 = 11.66
  P(win | evidence) = 11.66 / (1 + 11.66) = 0.921   → 92.1%

Evidence 3: CRI STAND_DOWN
  P(standdown | win) = 0.12
  P(standdown | lose) = 0.45
  Likelihood ratio = 0.12 / 0.45 = 0.27 (< 1.0 → reduces confidence)

Update: posterior_odds = 11.66 × 0.27 = 3.15
  P(win | evidence) = 3.15 / (1 + 3.15) = 0.759   → 75.9%
```

**What Bayesian gives us**:
- **Calibrated probabilities**: "83.1% win probability" means something testable
- **Base rates matter**: OR Rev starts at 76% WR — it takes strong counter-evidence to SKIP it
- **Likelihood ratios from real data**: Each domain expert queries DuckDB for conditional
  frequencies, not arbitrary 0.0-1.0 strengths
- **Correlated evidence handled**: If two cards have high joint probability (TPO + DPOC both
  trending), the second card's likelihood ratio is lower — naturally diminishing returns
- **CRI false positives quantified**: STAND_DOWN drops confidence from 92% → 76%, not from
  "winning" to "hard block." The data says how much CRI matters.

### Hybrid Approach: Bayesian Backbone + Scorecard Simplicity

Full Bayesian requires computing conditional frequencies for every card × strategy × direction
combo from DuckDB. That's a **lot of SQL queries**. Pragmatic path:

```
Phase A (now):     Additive scorecard — what we have, works, fast
Phase B (next):    Add base rate prior from DuckDB (P(win | strategy, direction))
Phase C (later):   Convert top 3-4 cards to likelihood ratios from historical data
Phase D (future):  Full Bayesian updating for all domain expert cards
```

**Phase B is the biggest bang for buck**: Just adding the prior changes everything.
An OR Rev LONG (76% WR) should need strong counter-evidence to SKIP. A Mean Reversion
LONG (38% WR) should need strong support to TAKE. Currently both start at 0.

```python
# Phase B: Add prior to orchestrator
def decide(self, signal_dict, evidence_cards, gate_passed):
    prior_wr = self._get_base_rate(signal_dict)  # DuckDB: historical WR
    prior_odds = prior_wr / (1 - prior_wr) if prior_wr < 1.0 else 10.0

    # Existing scoring still runs
    confluence = self._build_confluence(evidence_cards, signal_dir)

    # But decision thresholds adjust based on prior
    # High-WR strategy: harder to SKIP (need stronger counter-evidence)
    # Low-WR strategy: harder to TAKE (need stronger supporting evidence)
    adjusted_take_threshold = self.take_threshold * (1.0 - prior_wr)
    ...
```

### Is the Scorecard Already Bayesian?

**No, but it's doing something similar in spirit.** The scorecard is closer to a
**Dempster-Shafer belief function** — accumulating evidence for and against, then measuring
the gap. The key differences from Bayesian:

| Aspect | Current Scorecard | True Bayesian |
|--------|-------------------|---------------|
| Starting point | 0 (no opinion) | Base rate from data |
| Evidence weight | Arbitrary 0.0-1.0 | Likelihood ratio from conditional frequencies |
| Combination | Additive sum | Multiplicative odds update |
| Correlation | Ignored | Handled by joint probability |
| Output | "conviction" (0.0-1.0, uncalibrated) | P(win) (calibrated, testable) |
| Data requirement | None — hardcoded strengths | Historical conditional frequencies |

**The scorecard works** because the hardcoded strengths were calibrated by human intuition
(bias alignment at 0.75 is "about right"). But it can't improve itself. Bayesian updating
with DuckDB data **gets better as we accumulate more trades**.

---

## Domain Expert Debate: When Experts Conflict

### The Problem With Silent Scorecards

Right now, domain experts produce cards and walk away. If TPO Expert says "bullish 0.7"
and VWAP Expert says "bearish 0.65", those two cards go into the pool silently. The
Advocate/Skeptic LLM sees them as two disconnected data points and has to figure out the
conflict.

But the **experts themselves** know WHY they disagree. TPO sees value building at the bottom
(bullish). VWAP sees price at -2σ band with negative slope (bearish mean reversion). These
aren't random disagreements — they're structural conflicts with domain-specific reasoning
that should be surfaced explicitly.

### Three Levels of Debate

```
Level 0 (current): Silent scorecards → pool → Advocate/Skeptic (LLM)
Level 1 (proposed): Conflict detection → domain-level resolution → enriched pool → Adv/Skp
Level 2 (advanced): Domain experts debate each other via LLM → resolved cards → Adv/Skp
```

#### Level 0: What We Have (Silent Scorecards)

```
TPO Expert:  [bullish 0.7]  ──┐
VWAP Expert: [bearish 0.65] ──┼──→ Evidence Pool → Advocate/Skeptic → Orchestrator
EMA Expert:  [bullish 0.75] ──┘
```

Advocate sees 3 disconnected cards. Must figure out the conflict on its own.

#### Level 1: Deterministic Conflict Resolution (Recommended Next Step)

```
TPO Expert:  [bullish 0.7]  ──┐
VWAP Expert: [bearish 0.65] ──┼──→ Conflict Detector ──→ Enriched Pool → Adv/Skp
EMA Expert:  [bullish 0.75] ──┘        │
                                        ▼
                               "TPO vs VWAP conflict:
                                TPO bullish (b-shape, value at bottom)
                                VWAP bearish (price at -2σ, slope negative)
                                Historical resolution: when TPO bullish + VWAP bearish,
                                LONG WR = 58% (n=31) — TPO wins slightly
                                → Conflict card: bullish 0.55 (reduced confidence)"
```

**How it works**: After all domain experts produce scorecards, a **ConflictDetector**
scans for opposing cards between domains. For each conflict pair, it:

1. Identifies the two opposing domains and their reasoning
2. Queries DuckDB for historical resolution: "When TPO said X and VWAP said Y, what happened?"
3. Produces a **conflict resolution card** with:
   - Both sides stated
   - Historical win rate under this specific conflict
   - Adjusted direction based on which domain was historically right
   - Reduced strength (conflict = lower confidence)

```python
class ConflictDetector:
    """Detects and resolves conflicts between domain expert scorecards."""

    def detect_conflicts(self, cards: list[EvidenceCard]) -> list[ConflictPair]:
        """Find card pairs where domains disagree on direction."""
        bullish = [c for c in cards if c.direction == "bullish"]
        bearish = [c for c in cards if c.direction == "bearish"]
        conflicts = []
        for b in bullish:
            for s in bearish:
                if b.source != s.source:  # Different domains
                    conflicts.append(ConflictPair(bull_card=b, bear_card=s))
        return conflicts

    def resolve(self, pair: ConflictPair, conn) -> EvidenceCard:
        """Query DuckDB for historical resolution of this conflict."""
        # "When tpo_shape was b_shape AND vwap_slope was negative, WR was ..."
        historical_wr = self._query_conflict_resolution(pair, conn)

        if historical_wr > 0.55:
            direction = pair.bull_card.direction  # Bull domain wins
            strength = min(pair.bull_card.strength, historical_wr - 0.5)
        elif historical_wr < 0.45:
            direction = pair.bear_card.direction  # Bear domain wins
            strength = min(pair.bear_card.strength, 0.5 - historical_wr)
        else:
            direction = "neutral"  # True toss-up
            strength = 0.3

        return EvidenceCard(
            card_id=f"conflict_{pair.bull_card.source}_vs_{pair.bear_card.source}",
            source="conflict_resolution",
            layer="probabilistic",
            observation=f"Conflict: {pair.bull_card.source} (bullish) vs "
                       f"{pair.bear_card.source} (bearish). "
                       f"Historical WR={historical_wr:.0%} (n={n}). "
                       f"Resolved: {direction}.",
            direction=direction,
            strength=strength,
            data_points=n,
            historical_support=f"{historical_wr:.0%} WR when these domains conflict (n={n})",
        )
```

**This is still deterministic and fast** (<200ms including DuckDB query). It doesn't need
LLM. It gives the Advocate/Skeptic debate a **pre-digested conflict analysis** instead of
making the LLM figure out why TPO and VWAP disagree.

#### Level 2: LLM Domain Debate (Advanced, Maybe Overkill)

```
TPO Expert:  [bullish 0.7]  ──┐
VWAP Expert: [bearish 0.65] ──┼──→ Conflict Detector ──→ LLM Domain Debate ──→ Adv/Skp
                                         │
                                         ▼
                               LLM call: "You are a TPO/VWAP mediator.
                               TPO says bullish because b-shape + value building at bottom.
                               VWAP says bearish because -2σ + negative slope.
                               Historical data: TPO wins 58% of the time (n=31).
                               Who is more likely right? Why?"
```

**Cost**: Each conflict adds ~70s LLM call. 3 conflicts = 3.5 more minutes per signal.

**When this is worth it**: When the deterministic conflict resolution consistently makes
the wrong call — meaning the domain interaction is too nuanced for SQL. For example:
"b-shape is usually bullish, but when VWAP is deeply negative AND it's after 12:00, the
b-shape is actually a distribution pattern." That requires reasoning, not just WR lookup.

**Recommendation**: Start with Level 1 (deterministic). Track how often conflict resolution
cards align with actual outcomes. If accuracy < 55%, upgrade specific conflict pairs to
Level 2 LLM debate. Don't LLM-debate every conflict — only the ones where data alone
isn't sufficient.

### When Domain Debate Matters Most

Not all conflicts are equal. Some conflicts are noise, some are critical:

| Conflict | Frequency | Impact | Resolution Method |
|----------|-----------|--------|-------------------|
| TPO vs VWAP | Common (~30% of signals) | High — opposite structural reads | **Level 1**: DuckDB WR lookup |
| EMA vs Mean Reversion | Common (~25%) | Medium — trend vs reversion is the eternal question | **Level 1**: Regime-gated (trending regime → EMA wins, balance → MR wins) |
| ICT vs TPO | Rare (~10%) | Low — usually agree | Level 0 (no resolution needed) |
| Order Flow vs EMA | Occasional (~15%) | **Very High** — CVD divergence opposing trend is a major warning | **Level 2**: LLM needed, this is nuanced |
| Scalper vs Swing domains | Always | N/A — different timeframes | **Not a conflict** — separate tier execution |

### Pipeline With Conflict Resolution

```
Signal fires
    │
    ├──→ [8 Domain Experts in parallel] ──→ ~25 evidence cards (~50ms)
    │
    ├──→ [ConflictDetector] ──→ identify conflict pairs (~1ms)
    │         │
    │         ├──→ [DuckDB resolution per pair] ──→ conflict cards (~100ms)
    │         │
    │         └──→ [Optional: LLM debate for high-impact conflicts] (~70s each)
    │
    ├──→ Enriched evidence pool (original cards + conflict resolution cards)
    │
    ├──→ [Advocate / Skeptic] ──→ LLM debate on full pool (~140s)
    │
    └──→ [Orchestrator] ──→ TAKE / SKIP / REDUCE_SIZE
```

---

## A/B Test Plan: Measuring Domain Expert + Debate Impact

### The Core Question

> Does richer domain evidence + conflict resolution actually improve WR, PF, and net PnL
> compared to our current 2-observer system?

More evidence cards could help (better debate input) or hurt (noise, conflicting signals
confuse the LLM, over-filtering good trades). **Only a backtest answers this.**

### Test Matrix

| Run | Observers | Conflict Resolution | Debate | Scoring | Purpose |
|-----|-----------|---------------------|--------|---------|---------|
| A | None | None | None | N/A | **Baseline**: raw strategy signals |
| B | 2 (current) | None | Off | Additive | **Current deterministic agents** |
| C | 2 (current) | None | On (LLM) | Additive | **Current with debate** |
| D | 8 (domain experts) | None | Off | Additive | **More cards, same scoring** |
| E | 8 (domain experts) | Level 1 (DuckDB) | Off | Additive | **Conflict resolution, no debate** |
| F | 8 (domain experts) | Level 1 (DuckDB) | On (LLM) | Additive | **Full domain + debate** |
| G | 8 (domain experts) | Level 1 (DuckDB) | On (LLM) | **Bayesian** | **Full domain + debate + Bayesian** |

### What Each Comparison Tells Us

| Comparison | Question Answered |
|------------|-------------------|
| **D vs B** | Do more domain cards improve decisions WITHOUT debate? (Measures: does richer deterministic evidence help the scoring formula?) |
| **E vs D** | Does conflict resolution add value beyond raw card accumulation? (Measures: is resolving TPO vs VWAP better than just adding both to the pool?) |
| **F vs C** | Does domain expertise improve LLM debate quality? (Measures: does Advocate/Skeptic make better arguments with 25 cards vs 10?) |
| **F vs E** | Does LLM debate add value ON TOP of domain experts + conflict resolution? (Measures: after experts debate deterministically, does LLM synthesis still help?) |
| **G vs F** | Does Bayesian scoring outperform additive scoring? (Measures: does calibrating strengths to historical frequencies beat human-intuition weights?) |
| **C vs B** | Does LLM debate add value with current observers? (We have this data from the running backtest) |

### Key Metrics Per Run

| Metric | What It Measures | Why It Matters |
|--------|-----------------|----------------|
| **Win Rate** | % of taken trades that win | Core quality metric |
| **Profit Factor** | Gross profit / gross loss | Risk-adjusted returns |
| **Net PnL** | Total dollars | Bottom line |
| **Trades Taken** | How many signals passed all filters | Are we over-filtering? |
| **False Positive Rate** | TAKE signals that lost | Are domain experts reducing bad trades? |
| **False Negative Rate** | SKIP signals that would have won | Are domain experts blocking good trades? |
| **Conflict Resolution Accuracy** | When conflict card said bullish, was it right? | Is Level 1 resolution working? |
| **Debate Override Rate** | How often does LLM debate change the deterministic decision? | Is debate adding signal or noise? |
| **Per-Strategy Breakdown** | WR/PF per strategy per run | Which strategies benefit most from domain experts? |

### Implementation Plan

```bash
# Phase 1: Current system baseline (already running)
uv run python scripts/ab_test_agents.py --no-merge --enable-debate
# → Runs A, B, C (and D with agent, E with debate)

# Phase 2: After domain experts built
uv run python scripts/ab_test_domain_experts.py --no-merge
# → Runs D, E (domain experts without and with conflict resolution)

# Phase 3: Full comparison
uv run python scripts/ab_test_domain_experts.py --no-merge --enable-debate
# → Adds Run F (domain + conflict + debate)

# Phase 4: Bayesian scoring
uv run python scripts/ab_test_domain_experts.py --no-merge --enable-debate --bayesian
# → Adds Run G (full pipeline with Bayesian scoring)
```

### Success Criteria

| Threshold | Meaning |
|-----------|---------|
| Run F WR > Run C WR by **2%+** | Domain experts meaningfully improve debate quality |
| Run F PF > Run C PF by **0.2+** | Domain experts improve risk-adjusted returns |
| Run E WR > Run D WR by **1%+** | Conflict resolution adds value beyond raw cards |
| Run G WR > Run F WR by **1%+** | Bayesian scoring beats additive scoring |
| Trades Taken (F) within **90%** of Trades Taken (C) | Not over-filtering |
| False Negative Rate (F) < False Negative Rate (C) | Not blocking more good trades |

**If domain experts don't beat the 2% WR threshold**, the extra complexity isn't worth it.
Keep the DomainExpert base class for future scalability, but don't build all 8 experts.

**If conflict resolution doesn't beat 1% WR**, it's noise. The Advocate/Skeptic LLM is
already handling conflicts fine.

**If Bayesian doesn't beat additive by 1% WR**, the hardcoded strengths are "close enough."
Iterate on Bayesian only when we have 500+ trades per strategy for stable frequency estimates.

### Timeline

```
Week 1: CRI demotion + current system A/B test (Runs A-E)        ← IN PROGRESS
Week 2: Build DomainExpert base class + 2-3 experts               ← Next
Week 3: Run D, E comparison (domain experts vs current)
Week 4: Run F comparison (domain + debate)
Week 5: Bayesian Phase B (add prior) + Run G
         Analyze all results → decide: invest more or stop here
```

---

## Pluggable LLM Layer: Right Model for the Right Job

### The Problem With One Model Fits All

Today every LLM call — Advocate, Skeptic, Trade Reviewer, conflict mediator — goes through
the same `OllamaClient` pointing at the same Qwen3.5 on the same machine. This works for
the intraday pipeline where speed matters and 4K context is enough.

But consider what breaks as complexity grows:

| Scenario | Context Needed | Thinking Depth | Qwen3.5 (4K out, 128K ctx) |
|----------|---------------|----------------|---------------------------|
| OR Rev debate at 9:45 | ~2K tokens (9 cards + signal) | Moderate — fast decision needed | Works fine |
| HTF weekly study | ~30K tokens (5 days of snapshots, 50+ trades, composite profile) | Deep — multi-day pattern synthesis | **Chokes** — can't fit the context, reasoning too shallow |
| Domain conflict mediation (Level 2) | ~5K tokens (2 domain arguments + historical data) | Moderate-deep | Usually fine, sometimes truncates JSON |
| Meta-review (multi-week) | ~50K+ tokens (100+ observations, trend data, strategy stats) | Very deep — strategic thinking | **Can't do this** — needs Opus/Gemini tier |
| Strategy development brainstorm | ~20K tokens (backtest results, study notes, domain knowledge) | Creative + analytical | Lacks the reasoning depth |

**The running backtest proves this**: Qwen3.5 is producing JSON parse errors on ~30% of
debate responses because 4K max_tokens truncates its reasoning. Increasing to 8K helps but
costs more latency. The real issue is the model sometimes isn't smart enough for nuanced
arguments — it falls back to template responses.

### The Architecture: LLMProvider Interface

Replace the direct `OllamaClient` coupling with a **provider abstraction** that any agent
can use, and let each agent (or even each call) route to the right model.

```python
from abc import ABC, abstractmethod
from typing import Any

class LLMProvider(ABC):
    """Abstract interface for any LLM backend."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier for logging/metrics."""
        ...

    @property
    @abstractmethod
    def max_context(self) -> int:
        """Maximum context window in tokens."""
        ...

    @abstractmethod
    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        response_format: dict | None = None,   # {"type": "json_object"} if supported
    ) -> dict[str, Any]:
        """Send a chat completion. Returns {content, reasoning, usage, error}."""
        ...

    def is_available(self) -> bool:
        """Health check."""
        return True


class OllamaProvider(LLMProvider):
    """Local Ollama/vLLM — fast, free, private. Current OllamaClient becomes this."""

    def __init__(self, base_url="http://spark-ai:11434/v1", model="qwen3.5:35b-a3b", timeout=180):
        self._client = OllamaClient(base_url, model, timeout)

    @property
    def name(self) -> str:
        return f"ollama/{self._client.model}"

    @property
    def max_context(self) -> int:
        return 128_000

    def chat(self, system_prompt, user_prompt, max_tokens=4000, **kwargs):
        return self._client.chat(system_prompt, user_prompt, max_tokens)


class GeminiProvider(LLMProvider):
    """Google Gemini — 1M+ context window, good for HTF analysis."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-pro"):
        self.api_key = api_key
        self.model = model

    @property
    def name(self) -> str:
        return f"gemini/{self.model}"

    @property
    def max_context(self) -> int:
        return 1_000_000  # Gemini 2.5 Pro

    def chat(self, system_prompt, user_prompt, max_tokens=8000, **kwargs):
        # google.generativeai or REST API
        ...


class GrokProvider(LLMProvider):
    """xAI Grok — deep reasoning, real-time market awareness."""

    @property
    def name(self) -> str:
        return f"grok/{self.model}"

    @property
    def max_context(self) -> int:
        return 131_072

    def chat(self, system_prompt, user_prompt, max_tokens=8000, **kwargs):
        # OpenAI-compatible API at api.x.ai
        ...


class AnthropicProvider(LLMProvider):
    """Anthropic Claude — strongest reasoning, used for meta-reviews."""

    @property
    def name(self) -> str:
        return f"anthropic/{self.model}"

    @property
    def max_context(self) -> int:
        return 200_000  # Opus 4.6

    def chat(self, system_prompt, user_prompt, max_tokens=8000, **kwargs):
        # anthropic SDK
        ...
```

### Per-Agent Model Routing

Each agent declares what it needs. The pipeline routes it to the right provider.

```python
class AdvocateAgent(AgentBase):
    def __init__(self, llm: LLMProvider, max_tokens: int = 4000):
        self._llm = llm  # Was OllamaClient, now LLMProvider
        ...

class SkepticAgent(AgentBase):
    def __init__(self, llm: LLMProvider, max_tokens: int = 4000):
        self._llm = llm
        ...
```

The pipeline configures which provider each agent gets:

```python
# configs/agents.yaml
agents:
  advocate:
    provider: ollama          # Fast, local — intraday debates
    model: qwen3.5:35b-a3b
    max_tokens: 4000

  skeptic:
    provider: ollama
    model: qwen3.5:35b-a3b
    max_tokens: 4000

  conflict_mediator:
    provider: ollama          # Most conflicts are simple enough
    model: qwen3.5:35b-a3b
    max_tokens: 4000
    # Override for high-impact conflicts:
    override:
      orderflow_vs_ema:
        provider: gemini      # CVD divergence reasoning needs depth
        model: gemini-2.5-pro

  htf_analyst:
    provider: gemini          # Weekly analysis needs 1M context
    model: gemini-2.5-pro
    max_tokens: 16000

  meta_reviewer:
    provider: anthropic       # Strategic thinking, multi-week patterns
    model: claude-opus-4-6
    max_tokens: 8000

  strategy_developer:
    provider: grok            # Brainstorming, real-time market awareness
    model: grok-3
    max_tokens: 8000

  trade_reviewer:
    provider: ollama          # Single-trade analysis, speed matters
    model: qwen3.5:35b-a3b
    max_tokens: 4000
```

### LLM Tier System

This naturally creates a tiered model strategy that matches what CLAUDE.md already calls for
(Tier 0/1/2), but extended to more providers:

```
┌────────────────────────────────────────────────────────────────────┐
│                     LLM TIER SYSTEM                                 │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Tier 0: DETERMINISTIC (no LLM)                                     │
│  ┌───────────────────────────────────────────────────────┐          │
│  │ Domain experts, conflict detector, scoring, filters    │          │
│  │ Speed: <50ms  |  Cost: $0  |  Always available        │          │
│  └───────────────────────────────────────────────────────┘          │
│                                                                      │
│  Tier 1: LOCAL LLM (Qwen3.5 via Ollama)                            │
│  ┌───────────────────────────────────────────────────────┐          │
│  │ Advocate/Skeptic debate, trade review, fast analysis   │          │
│  │ Speed: ~70s  |  Cost: $0 (local)  |  128K context     │          │
│  │ Best for: intraday signals, simple debates             │          │
│  └───────────────────────────────────────────────────────┘          │
│                                                                      │
│  Tier 2: CLOUD LLM — DEEP CONTEXT (Gemini 2.5 Pro)                 │
│  ┌───────────────────────────────────────────────────────┐          │
│  │ HTF analysis, weekly studies, multi-day pattern mining  │          │
│  │ Speed: ~15s  |  Cost: ~$0.01/call  |  1M context      │          │
│  │ Best for: feed it 5 days of snapshots + all trades     │          │
│  │ and ask "what's the weekly structure telling us?"       │          │
│  └───────────────────────────────────────────────────────┘          │
│                                                                      │
│  Tier 3: CLOUD LLM — DEEP REASONING (Opus 4.6 / Grok 3)           │
│  ┌───────────────────────────────────────────────────────┐          │
│  │ Meta-reviews, strategy development, architecture       │          │
│  │ Speed: ~30s  |  Cost: ~$0.05/call  |  200K context    │          │
│  │ Best for: "review 3 weeks of observations and find     │          │
│  │ the strategic pattern we're all missing"               │          │
│  └───────────────────────────────────────────────────────┘          │
│                                                                      │
└────────────────────────────────────────────────────────────────────┘
```

### Why This Matters for HTF / Bigger Picture Thinking

The current pipeline is optimized for **intraday, single-signal evaluation**. The context
is one signal + 9 evidence cards + session context = maybe 2K tokens. Qwen3.5 handles this.

But as strategies get more complex, the inputs grow:

| Analysis Type | Input Size | Why It's Big |
|---------------|-----------|--------------|
| **HTF Weekly Study** | ~30K tokens | 5 days of deterministic snapshots, 50+ trades, composite profile, weekly VWAP structure, monthly levels |
| **Strategy Cross-Study** | ~20K tokens | Compare OR Rev + OR Accept + 80P performance under same conditions across 270 sessions |
| **Regime Transition Analysis** | ~40K tokens | "We've been in balance for 3 days. Historical data shows balance-to-trend transitions. What's the playbook?" Feed it all 3 days of tape data |
| **Options Overlay (Two Hour Trader)** | ~15K tokens | Futures signals + VIX term structure + Greeks + SPX/SPY correlation + timing windows |
| **Post-Week Meta Review** | ~50K tokens | All observations from the week, all agent decisions, all trade outcomes, strategy-level stats |

Qwen3.5 with 128K context can theoretically fit these, but its **reasoning quality degrades
with long inputs**. Gemini 2.5 Pro with 1M context handles 50K token inputs with ease.
Opus 4.6 with 200K context reasons more deeply about complex patterns.

### Concrete Example: HTF Analyst Agent

```python
class HTFAnalyst:
    """Higher-timeframe analysis agent — needs large context + deep reasoning."""

    def __init__(self, llm: LLMProvider):
        self._llm = llm  # Should be Gemini or Opus, not Qwen3.5

    def weekly_study(self, week_data: dict) -> dict:
        """Analyze a full week of trading data.

        Input: 5 days of snapshots, all trades, composite profile, regime data.
        Output: Weekly bias, key levels, strategy recommendations, regime forecast.
        """
        # This prompt is ~30K tokens — needs large context window
        prompt = self._build_weekly_prompt(week_data)

        if len(prompt) > self._llm.max_context * 0.8:
            logger.warning("Weekly study exceeds 80%% of context window")

        result = self._llm.chat(
            system_prompt=HTF_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=16000,  # Long analysis output
            temperature=0.5,   # More focused than debate
        )
        return self._parse_weekly_result(result)

    def regime_transition(self, multi_day_data: dict) -> dict:
        """Analyze potential regime change (balance → trend, trend exhaustion, etc.)."""
        ...
```

### Provider Fallback Chain

If the primary provider is unavailable, fall back gracefully:

```python
class ProviderChain(LLMProvider):
    """Try providers in order until one works."""

    def __init__(self, providers: list[LLMProvider]):
        self._providers = providers

    def chat(self, system_prompt, user_prompt, **kwargs):
        for provider in self._providers:
            if provider.is_available():
                result = provider.chat(system_prompt, user_prompt, **kwargs)
                if not result.get("error"):
                    return result
                logger.warning("%s failed: %s", provider.name, result["error"])
        return {"content": "", "error": "All providers failed"}

# Usage:
htf_llm = ProviderChain([
    GeminiProvider(api_key=GEMINI_KEY),      # Primary: 1M context
    AnthropicProvider(api_key=ANTHROPIC_KEY), # Fallback: 200K context
    OllamaProvider(),                         # Last resort: local Qwen3.5
])
```

### Cost Model

| Provider | Cost/1K input | Cost/1K output | Typical Call | Monthly (100 signals/day) |
|----------|--------------|----------------|-------------|--------------------------|
| Ollama (Qwen3.5) | $0 | $0 | $0 | $0 |
| Gemini 2.5 Pro | ~$0.0025 | ~$0.01 | ~$0.05 | ~$100 (HTF only, not every signal) |
| Grok 3 | ~$0.003 | ~$0.015 | ~$0.08 | ~$50 (meta-reviews only) |
| Opus 4.6 | ~$0.015 | ~$0.075 | ~$0.40 | ~$25 (weekly meta-review only) |

**Key insight**: Intraday debate stays local and free (Qwen3.5). Cloud LLMs are only for
HTF analysis, meta-reviews, and strategy development — maybe 5-10 calls per day, not 200.
Monthly cost stays under $200 even with aggressive HTF analysis usage.

### Implementation: Minimal Change to Existing Code

The beauty of OpenAI-compatible APIs is that Gemini, Grok, and many others already speak
the same protocol. The refactor is small:

```
Step 1: Rename OllamaClient → make it implement LLMProvider interface       (1 hour)
Step 2: Update AdvocateAgent/SkepticAgent to accept LLMProvider             (30 min)
Step 3: Add GeminiProvider, AnthropicProvider (thin wrappers)               (2 hours)
Step 4: Add agents.yaml config for per-agent provider routing               (1 hour)
Step 5: Update AgentPipeline to read config and wire providers              (1 hour)
Total: ~1 day refactor, backward compatible
```

The existing `OllamaClient` already uses the OpenAI chat completions format. Gemini and
Grok both have OpenAI-compatible endpoints. So `OllamaProvider` just wraps the existing
client, and `GeminiProvider`/`GrokProvider` use the same HTTP format with a different
base_url and auth header. Anthropic has its own SDK but the wrapper is trivial.

**No agent logic changes.** Advocate still builds its case the same way. Skeptic still
challenges. The only difference is which brain is doing the thinking.

---

## Answer: Do We Need LLM or Is This RAG?

**Neither, mostly.** This is structured retrieval + deterministic scoring.

| Component | Method | Why |
|-----------|--------|-----|
| Domain Experts | **Deterministic Python** | Fast, testable, reproducible. Read data, apply rules, emit cards |
| Pattern Miner | **DuckDB SQL** | "When this evidence combo appeared historically, WR was X%" |
| Historical Context | **DuckDB queries** (structured retrieval, not RAG) | Exact SQL queries, not embedding similarity |
| Advocate/Skeptic | **LLM (Qwen3.5)** | Cross-domain synthesis requires reasoning — this is where LLM shines |
| Trade Reviewer | **LLM (Qwen3.5)** | Post-hoc analysis requires nuanced interpretation |
| Meta Review | **LLM (Opus 4.6)** | Strategic pattern recognition across many sessions |

**Why not RAG?** Our data is structured (tables, JSON, JSONL). RAG works for unstructured
documents. We have:
- `trades` table (8,000+ rows with exact fields)
- `deterministic_tape` table (7,362+ rows with exact JSON)
- `observations` table (exact schema)

A DuckDB query `SELECT ... WHERE strategy='OR Rev' AND day_type='Trend Up'` is faster and
more precise than embedding similarity search. Add embeddings later only if we need
"sessions that *feel like* today" matching (Phase 2, maybe never).

**Do we need to train the LLM for domain experts?** No. Domain experts are Python code.
The LLM training (Qwen3.5 LoRA) enhances the Advocate/Skeptic layer with Rockit-specific
reasoning patterns, but the domain data itself is deterministic.

---

## New Data Requirements

### Existing Data That's Sufficient
- TPO shape, POC, VA, IB — already in 38 modules
- Wick traps, FVGs — already computed
- Bias/trend/DPOC — already computed
- Premarket levels — already computed

### New Deterministic Modules Needed

| Module | Domain Expert | Priority | Effort |
|--------|---------------|----------|--------|
| `vwap_analysis.py` | VWAP Expert | **HIGH** | Medium — need VWAP column in data |
| `ema_structure.py` | EMA Expert | **HIGH** | Low — EMAs easy to compute |
| `scalper_momentum.py` | Scalper Expert | **MEDIUM** | Low — MACD/RSI from bar data |
| `order_flow.py` | Order Flow Expert | **HIGH** | Medium — need delta/CVD columns |
| `mean_reversion.py` | Mean Reversion Expert | **MEDIUM** | Low — BB/z-score from price |
| `cross_market.py` | Divergence Expert | **LOW** | High — multi-instrument loader needed |
| `opening_type.py` | TPO Expert (upgrade) | **HIGH** | Medium — classify first 3 bars |

### New Data Columns Needed in Session CSVs

| Column | Source | Domain |
|--------|--------|--------|
| `VWAP` | NinjaTrader export | VWAP Expert |
| `AskVolume`, `BidVolume` | NinjaTrader Level 2 | Order Flow Expert |
| `MACD`, `MACD_Signal`, `MACD_Hist` | Computed or NinjaTrader | Scalper Expert |

Most of these can be computed from existing OHLCV data. Only AskVolume/BidVolume requires
NinjaTrader Level 2 export changes.

---

## Implementation Roadmap

### Phase 1: Upgrade Existing Observers → Domain Experts (1-2 days)

**Convert ProfileObserver and MomentumObserver to TPO Expert and base framework:**

1. Create `DomainExpert` base class extending `AgentBase`:
   ```python
   class DomainExpert(AgentBase):
       """Base class for domain expert observers."""
       domain: str  # "tpo", "ict", "vwap", etc.

       @abstractmethod
       def scorecard(self, context: dict) -> list[EvidenceCard]:
           """Produce domain-specific evidence cards."""

       def evaluate(self, context: dict) -> list[EvidenceCard]:
           """Standard evaluate delegates to scorecard."""
           return self.scorecard(context)

       def historical_query(self, conn, signal: dict) -> dict:
           """Domain-specific DuckDB query for historical context."""
           return {}
   ```

2. Refactor `ProfileObserver` → `TpoExpert`
3. Refactor `MomentumObserver` → split into `EmaExpert` + `OrderFlowExpert` (partial)
4. Update `AgentPipeline` to accept `list[DomainExpert]`

### Phase 2: Add New Domain Experts (3-5 days)

Priority order:
1. **VWAP Expert** — high value, needs `vwap_analysis.py` module
2. **EMA Expert** — easy, `ema_structure.py` module
3. **Scalper Expert** — fast path for LTF signals
4. **ICT Expert** — FVG/OB/liquidity (partially exists in `fvg_detection.py`)

### Phase 3: Pattern Miner Integration (2-3 days)

Each domain expert gets a `historical_query()` method that runs domain-specific
DuckDB queries before producing cards. Example:

```python
class TpoExpert(DomainExpert):
    def historical_query(self, conn, signal):
        # "When b-shape + OR Rev LONG, historical WR?"
        return query(conn, """
            SELECT outcome, COUNT(*), AVG(net_pnl)
            FROM trades t JOIN deterministic_tape d ...
            WHERE tpo_shape = 'b_shape' AND strategy = ? AND direction = ?
        """, [signal['strategy_name'], signal['direction']])
```

### Phase 4: Two-Tier Execution (1-2 days)

Add `execution_tier` parameter to `AgentPipeline.evaluate_signal()`:
```python
def evaluate_signal(self, signal_dict, tier="full"):
    if tier == "fast":
        # Only relevant domain expert, no debate
        expert = self._select_expert(signal_dict)
        cards = expert.scorecard(context)
        return self.orchestrator.decide(signal_dict, cards, True)
    elif tier == "full":
        # All experts + debate (current behavior)
        ...
```

### Phase 5: Domain-Specific Skeptics (optional, advanced)

Instead of one general Skeptic, each domain expert could have a counter-expert:
- ICT Expert says "FVG below = support" → ICT Skeptic says "FVG already 3 hours old, weakened"
- TPO Expert says "b-shape = bullish" → TPO Skeptic says "p-shape was developing 15 min ago, unstable"

**This is probably overkill for now.** The general Advocate/Skeptic can handle this with
domain cards as input. Revisit only if the LLM debate consistently misinterprets specific
domain signals.

---

## Cost-Benefit Analysis

### What We Gain

1. **Richer evidence pool**: 20-30 cards instead of 8-10 → better Advocate/Skeptic debates
2. **Domain-specific historical queries**: "VWAP slope was negative in 85% of losing LONG trades" — currently invisible
3. **Fast scalper path**: Sub-100ms for LTF without sacrificing swing quality
4. **User query support**: "Ask the experts" without needing a strategy signal
5. **Testable domain knowledge**: Each expert is a Python class with unit tests, not prompt engineering

### What It Costs

1. **6-8 new deterministic modules** (the actual work)
2. **Refactor observer layer** to DomainExpert base class (mechanical)
3. **Some new data columns** in NinjaTrader export (VWAP, delta)
4. **More evidence cards** → slightly more tokens in LLM prompt (~200 extra tokens, negligible)

### Is It Worth It?

**Yes, but prioritize.** Start with VWAP + EMA (most bang for buck, easiest data), then ICT
(FVG data already exists), then Order Flow (needs delta data). Scalper Expert is valuable
but only if you're actually scalping.

**Don't build all 8 at once.** Build 2-3, run a backtest, measure if the additional evidence
cards improve Advocate/Skeptic debate quality. If the debate already makes good decisions
with 8-10 cards, adding 20 more cards may just add noise.

---

## Framework Evaluation: From POC to Production

### The Honesty Check: Where We Are

What we have today is a **proof-of-concept**. It works, it's tested, it produces results.
But it's held together by hand-wired Python classes with no standard patterns for:

- Agent lifecycle management (start, stop, retry, timeout)
- Parallel execution of domain experts (we loop sequentially)
- State management across pipeline stages (we pass dicts around)
- Observability (logging, tracing, metrics per agent)
- Dynamic routing (all signals take the same path regardless of complexity)
- Multi-LLM orchestration (one client hardcoded everywhere)
- Error recovery (one agent fails → entire pipeline falls back)

As we add 8 domain experts, conflict resolution, pluggable LLMs, Bayesian scoring, HTF
analysts, and tiered execution, the hand-wired approach will **buckle under its own weight**.
We need to evaluate frameworks seriously — not to adopt one tomorrow, but to know what to
adopt when the POC outgrows itself.

### Framework Comparison

#### LangGraph (LangChain)

**What it is**: Graph-based agent orchestration with nodes, edges, conditional routing,
and shared state. Part of the LangChain ecosystem.

**What it gives us**:
- Each domain expert = a node. Run 8 nodes in parallel natively
- Conditional edges: "if conflict detected → route to conflict resolution node"
- Shared state object accumulates evidence cards across nodes
- Built-in streaming (cards appear in UI as each expert finishes)
- Checkpoint/resume (save pipeline state, replay for debugging)
- Human-in-the-loop at any node (dashboard "approve this debate?")
- Native support for multi-model routing per node

**What it costs**:
- LangChain dependency (large, opinionated, fast-moving API)
- Graph definition adds complexity for simple linear pipelines
- Debugging graph execution is harder than stepping through Python
- Lock-in to LangChain's abstractions

**Fit for us**: **Strong.** Our pipeline IS a graph:
```
Gate → [Expert₁, Expert₂, ..., Expert₈] → ConflictDetector → [Advocate, Skeptic] → Orchestrator
         ↑ (parallel fan-out)                    ↓ (conditional: conflict? → Level 2 LLM)
```

LangGraph was literally designed for this pattern. The parallel fan-out for domain experts,
conditional routing for conflict resolution tiers, and multi-model support per node maps
exactly to what we need.

**Verdict**: **Adopt when we hit 4+ domain experts.** Below that, hand-wired is simpler.

#### CrewAI

**What it is**: Multi-agent framework where agents have roles, goals, and can delegate
tasks to each other. Agents communicate via natural language.

**What it gives us**:
- Role-based agents with goals ("You are the TPO Expert, your goal is...")
- Inter-agent delegation ("TPO Expert, ask VWAP Expert about mean reversion risk")
- Built-in memory per agent (agent remembers past interactions)
- Tool integration (agents can query DuckDB, read files, call APIs)

**What it costs**:
- Every agent interaction goes through LLM → expensive, slow
- Agents "talking" to each other is nondeterministic — hard to test
- Overhead of agent communication protocol
- Not designed for deterministic pipeline stages

**Fit for us**: **Weak for the core pipeline.** Our domain experts are deterministic code,
not LLM agents that need to chat. CrewAI's strength is autonomous agents — our strength is
structured evidence accumulation. But it could fit for the Level 2 domain debate scenario
where TPO and VWAP actually argue with each other via LLM.

**Verdict**: **Skip for now.** Our pipeline is structured, not conversational.

#### AutoGen (Microsoft)

**What it is**: Framework for building multi-agent conversations. Agents take turns in a
conversation, can call tools, and collaborate to solve problems.

**What it gives us**:
- GroupChat for multi-agent debate (TPO, VWAP, ICT argue in a thread)
- Tool-calling agents (domain expert calls DuckDB, returns data, argues about it)
- Nested conversations (Advocate calls TPO Expert as a sub-agent)
- Code execution agents (useful for ad-hoc analysis)

**What it costs**:
- Conversation-based model — every interaction is an LLM call
- Hard to make deterministic/testable
- Complex configuration for agent roles and handoff rules
- Microsoft ecosystem, moving fast with breaking changes

**Fit for us**: **Interesting for domain debate (Level 2) only.** The GroupChat pattern
where TPO, VWAP, and EMA debate each other with data is compelling. But for the core
pipeline, it's too slow and unpredictable.

**Verdict**: **Watch for domain debate, don't use for the pipeline.**

#### Semantic Kernel (Microsoft)

**What it is**: Plugin-based LLM orchestration. Functions (plugins) are registered and
the LLM decides which to call. Supports multiple LLM providers natively.

**What it gives us**:
- Each domain expert = a plugin with typed input/output
- Native multi-provider support (OpenAI, Anthropic, Gemini, local)
- Planner that can compose plugins dynamically
- Memory integration (long-term recall)

**What it costs**:
- .NET-first (Python SDK is secondary)
- Plugin model assumes LLM drives the workflow — our pipeline is deterministic
- Less community traction for Python

**Fit for us**: **Plugin pattern is good, framework is wrong ecosystem.**

**Verdict**: **Steal the plugin pattern, don't adopt the framework.**

#### Pydantic AI / Instructor

**What it is**: Lightweight structured output from LLMs. Not a full agent framework —
just ensures LLM responses match a Pydantic model.

**What it gives us**:
- Structured JSON output guaranteed (no more parse errors in debate)
- Validation of LLM responses against schemas
- Retry with error context when output is malformed
- Multi-provider support via litellm

**What it costs**:
- Small dependency, not opinionated about pipeline structure
- Doesn't solve orchestration, state, or routing

**Fit for us**: **High for fixing the JSON parse issue today.** The running backtest has
~30% Skeptic JSON parse failures. Pydantic AI / Instructor would catch these and retry.

**Verdict**: **Adopt immediately** for LLM response parsing. Orthogonal to pipeline framework.

#### LiteLLM

**What it is**: Unified interface to 100+ LLM providers. OpenAI-compatible API that routes
to Ollama, Gemini, Anthropic, Grok, etc.

**What it gives us**:
- Single `completion()` call → routes to any provider
- Built-in fallback chains (try Ollama → fall back to Gemini)
- Rate limiting, caching, cost tracking per provider
- Supports all the providers we want (Ollama, Gemini, Grok, Anthropic)

**What it costs**:
- One more dependency
- Slight abstraction overhead

**Fit for us**: **High.** This IS the pluggable LLM layer we designed in the previous
section, but already built. Instead of writing `OllamaProvider`, `GeminiProvider`, etc.,
use LiteLLM and get all of them for free.

**Verdict**: **Adopt for the pluggable LLM layer.** Replaces our hand-rolled provider
abstraction.

### Recommendation: Phased Framework Adoption

```
Phase 0 (now):     Hand-wired pipeline. It works. Ship it.

Phase 1 (next):    + LiteLLM (pluggable LLM providers, replaces OllamaClient)
                   + Pydantic AI or Instructor (structured output, fixes JSON parse errors)
                   Effort: ~1 day. Immediate improvement to reliability + multi-model.

Phase 2 (month 2): + LangGraph (when we hit 4+ domain experts)
                   Pipeline becomes a graph with parallel fan-out for experts,
                   conditional routing for conflict resolution, streaming to UI.
                   Effort: ~3 days to port existing pipeline to LangGraph graph.

Phase 3 (month 3): + AutoGen GroupChat (for Level 2 domain debates only)
                   When two domains conflict and DuckDB resolution isn't enough,
                   spin up a GroupChat where TPO and VWAP argue with data.
                   Effort: ~2 days for the debate adapter.

Never:             CrewAI, Semantic Kernel. Don't fit our architecture.
```

### Why LangGraph Is the Endgame

Here's what the full LangGraph pipeline looks like:

```python
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import TypedDict

class PipelineState(TypedDict):
    signal: dict
    context: dict
    evidence_cards: list[EvidenceCard]
    conflicts: list[ConflictPair]
    debate_result: dict
    decision: AgentDecision

# Build the graph
graph = StateGraph(PipelineState)

# Nodes
graph.add_node("gate", cri_gate_node)
graph.add_node("tpo_expert", tpo_expert_node)
graph.add_node("vwap_expert", vwap_expert_node)
graph.add_node("ema_expert", ema_expert_node)
graph.add_node("ict_expert", ict_expert_node)
graph.add_node("orderflow_expert", orderflow_expert_node)
# ... more experts
graph.add_node("conflict_detector", conflict_detector_node)
graph.add_node("conflict_resolver", conflict_resolver_node)    # Level 1 (DuckDB)
graph.add_node("conflict_debate", conflict_debate_node)        # Level 2 (LLM)
graph.add_node("advocate", advocate_node)                       # LLM — configurable provider
graph.add_node("skeptic", skeptic_node)                         # LLM — configurable provider
graph.add_node("orchestrator", orchestrator_node)

# Edges
graph.add_edge(START, "gate")
graph.add_edge("gate", ["tpo_expert", "vwap_expert", "ema_expert", ...])  # Parallel fan-out
graph.add_edge(["tpo_expert", "vwap_expert", ...], "conflict_detector")   # Fan-in
graph.add_conditional_edges("conflict_detector", route_conflicts)          # Level 1 or 2?
graph.add_edge("conflict_resolver", "advocate")
graph.add_edge("conflict_debate", "advocate")
graph.add_edge("advocate", "skeptic")
graph.add_edge("skeptic", "orchestrator")
graph.add_edge("orchestrator", END)

# Compile with per-node LLM configuration
pipeline = graph.compile()

# Each node can use a different LLM provider via config
config = {
    "advocate": {"llm": litellm.completion, "model": "ollama/qwen3.5:35b-a3b"},
    "skeptic": {"llm": litellm.completion, "model": "ollama/qwen3.5:35b-a3b"},
    "conflict_debate": {"llm": litellm.completion, "model": "gemini/gemini-2.5-pro"},
    "htf_analyst": {"llm": litellm.completion, "model": "anthropic/claude-opus-4-6"},
}
```

**This is where we're heading.** Not today, not next week, but when the pipeline has enough
moving parts that hand-wiring becomes the bottleneck. The key is designing the domain experts,
conflict resolution, and LLM provider interface NOW so that the LangGraph migration is a
**port** (move existing logic into graph nodes), not a **rewrite**.

---

## Summary: The Pragmatic Path

```
Today's architecture:
  CRI Gate → ProfileObserver → MomentumObserver → [Debate] → Orchestrator
  (1 gate + 2 observers = ~10 cards, 1 LLM, hand-wired)

Target architecture:
  CRI Gate → [8 Domain Experts ∥] → ConflictDetector → [Debate] → Orchestrator
  (1 gate + 8 experts = ~25 cards, pluggable LLMs, LangGraph orchestration)

Build order:
  1. LiteLLM + Pydantic AI (pluggable LLMs, structured output)     ← Week 1
  2. DomainExpert base class + refactor existing observers           ← Week 1
  3. VWAP Expert + EMA Expert (highest value)                        ← Week 2
  4. ICT Expert (FVG data exists)                                    ← Week 2
  5. ConflictDetector + Level 1 DuckDB resolution                    ← Week 3
  6. A/B test: 2 observers vs domain experts vs domain + conflict    ← Week 3
  7. Bayesian scoring (add prior from DuckDB)                        ← Week 4
  8. Port pipeline to LangGraph (parallel experts, conditional routing) ← Week 5
  9. Scalper Expert + fast tier                                      ← Week 6
  10. Order Flow Expert (needs delta data)                           ← Week 6
  11. Level 2 LLM conflict debate for high-impact pairs             ← Week 7
  12. HTF Analyst agent (Gemini for weekly studies)                   ← Week 8
```

**Start small. Measure. Iterate. Adopt frameworks when the POC outgrows hand-wiring.**
