# 14 — Strategy ↔ Orchestrator Integration Architecture

> **Cross-references:**
> - [technical-design/14-strategy-agent-lifecycle.md](../technical-design/14-strategy-agent-lifecycle.md) — Strategy lifecycle stages (research → implement → backtest → walk-forward → shadow → promote → live)
> - [technical-design/04-strategy-framework.md](../technical-design/04-strategy-framework.md) — StrategyBase interface, Signal model, YAML config, registry
> - [technical-design/10-deterministic-modules.md](../technical-design/10-deterministic-modules.md) — Orchestrator, 38 modules, dependency chain, module interface
> - [brainstorm/01-agent-consensus-architecture.md](../brainstorm/01-agent-consensus-architecture.md) — Original autonomous trading desk vision (8 strategy specialists, continuous analysis)
> - [brainstorm/04-agent-specialization-and-consensus.md](../brainstorm/04-agent-specialization-and-consensus.md) — 5 approaches to agent specialization: Strategy Specialists, Domain Specialists, Hybrid, Bayesian Chain, Bayesian + Debate
> - [brainstorm/05-training-data-pipeline-for-specialists.md](../brainstorm/05-training-data-pipeline-for-specialists.md) — Three-stage pipeline: Bulk Snapshot → Backtest Enrichment → Evidence Extraction

## Mission

Define the architecture for how strategies and the deterministic orchestrator relate — how a strategy gets promoted into the orchestrator's JSON output, how they share logic without creating fragile coupling, and how the system stays agile during strategy iteration without breaking production snapshots.

---

## The Strategy Lifecycle (Summary)

Full lifecycle is documented in [technical-design/14-strategy-agent-lifecycle.md](../technical-design/14-strategy-agent-lifecycle.md). The relevant phases for this architecture doc are:

```
  RESEARCH → DEVELOP → VALIDATE → PROMOTE → MONITOR
                │                     │
                │                     ▼
                │              Activate strategy
                │              into orchestrator
                │              JSON output
                ▼
          May create new
          indicators, modules,
          or helpers along the way
```

**Key tension:** During the develop/validate loop, the quant + Claude iterate rapidly — trying entry models, tweaking constants, adding indicators. These changes must NOT break the orchestrator's production snapshot output. But once promoted, the strategy's detection logic needs to appear in both:
1. The **backtest** (emitting `Signal` objects for the engine)
2. The **orchestrator snapshot** (emitting JSON dicts for UI, training data, agents)

---

## Current State: Parallel Implementations

Today, strategies that exist in both systems are implemented independently:

| Strategy | Backtest File | Deterministic Module | Shared Logic? |
|----------|--------------|---------------------|---------------|
| OR Reversal | `strategies/or_reversal.py` | `deterministic/modules/or_reversal.py` | No — independent copies |
| 80P Rule | `strategies/eighty_percent_rule.py` | `deterministic/modules/globex_va_analysis.py` | No — independent copies |
| 20P Rule | `strategies/twenty_percent_rule.py` | `deterministic/modules/twenty_percent_rule.py` | No — independent copies |
| Edge Fade | (none) | `deterministic/modules/edge_fade.py` | N/A — module only |
| VA Edge Fade | (none) | `deterministic/modules/va_edge_fade.py` | N/A — module only |
| Mean Reversion | `strategies/mean_reversion_vwap.py` | `deterministic/modules/mean_reversion_engine.py` | No — independent copies |

**Problems this creates:**
1. **Parameter drift** — OR module uses `OR_BARS=3` (5-min bars = 15 min), strategy uses `OR_BARS=15` (1-min bars = 15 min). Same intent, no shared constant.
2. **Bug fix doesn't propagate** — A fix in one doesn't update the other.
3. **Promotion is reimplementation** — Promoting a new strategy means writing a whole new module from scratch.
4. **Inconsistent analysis** — The JSON snapshot and the backtest can disagree on whether a setup triggered for the same session.

---

## Architectural Approaches

### Approach A: Shared Core Libraries

Extract pure-function core logic into `strategies/setups/` that both backtest strategies and deterministic modules import.

```
strategies/setups/or_reversal_core.py  ──→ pure functions
    ↑                     ↑
    │                     │
deterministic/modules/    strategies/
or_reversal.py            or_reversal.py
(formats JSON snapshot)   (emits Signal)
```

**Promotion:** Write a thin deterministic module that imports from the same core and formats JSON output.

| Pros | Cons |
|------|------|
| Single source of truth for constants and math | **Heavy coupling** — any tweak during strategy iteration can break orchestrator |
| Bug fix propagates automatically | Requires running both test suites after every change |
| Natural place for versioning | Shared functions accumulate complexity as strategies diverge |

**Mitigation:** Pin function signatures. Contract tests in `test_setups_core.py`. CI blocks if deterministic tests fail.

---

### Approach B: Self-Contained Strategy Packages

Each strategy is a self-contained package with its own detection logic, constants, and helpers. No shared imports between strategies.

```
strategies/
  or_reversal/
    __init__.py
    strategy.py          # StrategyBase subclass (backtest)
    module.py            # Deterministic module (orchestrator JSON)
    core.py              # Shared within this package only
    config.yaml          # Entry/risk/target model, version, constants
    tests/
```

**Promotion:** The package already contains `module.py`. Promotion = registering it in orchestrator config.

| Pros | Cons |
|------|------|
| **Zero cross-strategy coupling** | Code duplication across strategies (e.g., `compute_atr` in each) |
| Strategy iteration is fully isolated | More files to maintain per strategy |
| Each package independently versioned | Universal utility functions still need a common home or get duplicated |
| Everything for one strategy in one folder | |

**Mitigation:** Small `strategies/common/` package for truly universal functions (ATR, basic math), but strategy-specific logic stays isolated.

---

### Approach C: Decoupled Signal Runner

Strategies generate trade signals completely independently of the deterministic data pipeline. A **signal runner** module in the orchestrator runs all activated strategies and appends results to the snapshot.

```
Orchestrator (market data)              Signal Runner (trade signals)
────────────────────────                ──────────────────────────────
premarket                               Reads activated strategies
ib_location                             from config. Runs each against
volume_profile                          current DataFrame + intraday_data.
tpo_profile              ──→ snapshot   Each strategy returns:
dpoc_migration                ──→       {signal, entry, stop, target,
wick_parade                              confidence, metadata}
fvg_detection
core_confluences                        Appended to snapshot as:
                                        snapshot["active_signals"] = [...]
```

**Config-driven activation:**

```yaml
# configs/active_strategies.yaml
strategies:
  - name: or_reversal
    version: "2.1"
    entry_model: retest_50pct
    enabled: true
  - name: eighty_percent_rule
    version: "1.3"
    entry_model: model_b
    enabled: true
  - name: twenty_percent_rule
    version: "1.0"
    entry_model: acceptance_3x5min
    enabled: false  # disabled, underperforming
```

**In the orchestrator:**

```python
from rockit_core.deterministic.signal_runner import run_active_strategies

# After building all market data modules...
snapshot["active_signals"] = run_active_strategies(
    df_current=df_current,
    df_extended=df_extended,
    intraday_data=intraday_data,
    config=config,
)
```

**Promotion:** Add strategy name to config. No new module to write. Signal runner discovers and runs it.

| Pros | Cons |
|------|------|
| **True decoupling** — strategies don't know about orchestrator | Strategies may need orchestrator data (IB levels, premarket, VA) — need context passed in |
| Strategy iteration cannot break orchestrator | Existing modules that are BOTH data AND signal (e.g., `globex_va_analysis`) would exist separately |
| Easy enable/disable via config (no code changes) | Two places where "80P analysis" appears: module (data) + strategy (signal) |
| Agents could own their own strategies independently | |
| Clean promotion: just add to config | |

**Mitigation:** Signal runner passes `intraday_data` (IB, premarket, VA, etc.) to each strategy. Strategies consume what they need. Over time, split hybrid modules.

---

### Approach D: Layered Architecture (Long-Term Target)

Clean separation into layers. The orchestrator focuses on **market structure data** (objectively observable). All **trade setup detection** moves to a strategy layer.

```
Layer 1: Deterministic Market Data (orchestrator)
  premarket, ib_location, volume_profile, tpo_profile,
  dpoc_migration, wick_parade, fvg_detection, core_confluences
  → Pure market structure. No trade signals. No "should I buy/sell?"

Layer 2: Strategy Signals (signal runner)
  or_reversal, eighty_percent_rule, twenty_percent_rule,
  edge_fade, va_edge_fade, mean_reversion, ...
  → Consumes Layer 1 data. Produces trade signals with entry/stop/target.
  → Each strategy reads from the snapshot, adds its own section.

Layer 3: Inference & Playbook (existing)
  inference_engine, cri_readiness, playbook_engine
  → Consumes Layer 1 + Layer 2. Produces final recommendations.
```

**How the orchestrator changes:**

```python
# Current: orchestrator directly calls strategy modules inline
snapshot["or_reversal"] = get_or_reversal_setup(...)
snapshot["globex_va_analysis"] = get_globex_va_analysis(...)
snapshot["twenty_percent_rule"] = get_twenty_percent_rule(...)

# Proposed: orchestrator builds market data, then signal runner adds strategies
snapshot = build_market_data(config)                    # Layer 1
snapshot["strategies"] = run_active_strategies(snapshot) # Layer 2
snapshot = apply_inference_and_playbook(snapshot)        # Layer 3
```

| Pros | Cons |
|------|------|
| **Cleanest separation of concerns** | Existing hybrid modules (globex_va_analysis, or_reversal module) need splitting |
| Orchestrator becomes simpler | Migration effort — split "data" vs "signal" in each module |
| Training data naturally separates market context from trade decisions | Some modules like edge_fade are purely strategy — move entirely |
| Inference/playbook can reason over ALL active strategy signals as a portfolio | |
| New strategies follow pattern natively | |

---

### Approach E: Event-Driven — Signal-Triggered Agents (Alternative)

Approaches C and D assume the orchestrator and strategies run on the same timeframe. But there's a fundamental mismatch:

- **Strategies** run on **1-min bars** (backtest engine, high resolution, stateful bar-by-bar)
- **Orchestrator** runs on **5-min bars** (LLM inference is too slow for 1-min; snapshot generation takes ~1.6s)

Running the full orchestrator + agents every minute is impractical. But strategies don't need agents or orchestrator data to detect a setup — they just need price data. The expensive work (agent debate, LLM inference, historical context lookup) only matters **when there's actually something to debate.**

**Core insight: Don't force orchestrator cadence on strategies. Run strategies at 1-min. Only fire agents when a signal triggers.**

```
1-min bar loop (fast, deterministic, <10ms)
──────────────────────────────────────────────
  strategy_1.on_bar(bar)  → None
  strategy_2.on_bar(bar)  → None             No signal → no work.
  strategy_3.on_bar(bar)  → None             Strategies are Tier 0 (~µs).
  ...
  strategy_1.on_bar(bar)  → Signal! ──────────────────────────────┐
                                                                   ▼
                                                    Agent Pipeline (on-demand)
                                                    ─────────────────────────
                                                    1. Grab latest orchestrator
                                                       snapshot (5-min, cached)
                                                    2. Query DuckDB for similar
                                                       sessions, historical WR
                                                    3. Advocate builds case
                                                    4. Skeptic challenges
                                                    5. Orchestrator decides:
                                                       TAKE / SKIP / REDUCE_SIZE
                                                    6. If TAKE → emit to client
```

**What each layer does:**

| Layer | Timeframe | Latency | Purpose |
|-------|-----------|---------|---------|
| Strategy (Tier 0) | 1-min bars | <10ms | Detect setups. Pure Python. No LLM. |
| Orchestrator (Tier 0) | 5-min bars | ~1.6s | Publish market structure snapshots. Runs on its own schedule. |
| Agent Pipeline (Tier 1) | On signal | ~2-5s | Debate the signal. Only fires when a strategy emits. |
| Reflection (Tier 2) | Daily/multi-day | Minutes | Meta-review. Post-market only. |

**What agents have access to when a signal fires:**

```python
# When strategy emits a Signal, the agent pipeline receives:
agent_context = {
    # The signal itself
    "signal": signal,                          # entry, stop, target, direction, metadata

    # Latest orchestrator snapshot (cached, 5-min cadence)
    "snapshot": latest_snapshot,               # premarket, IB, VA, volume profile, TPO, etc.

    # Historical context (DuckDB queries)
    "similar_sessions": historian.query(        # Sessions with same day_type + setup_type
        day_type=signal.day_type,
        setup_type=signal.setup_type,
        lookback_days=60
    ),
    "strategy_track_record": historian.query(   # This strategy's recent WR, PF, avg R
        strategy=signal.strategy_name,
        lookback_days=30
    ),

    # Backtest baseline
    "baseline": strategy_config.baseline,       # Expected WR, PF from backtest

    # Current market regime
    "regime": snapshot.get("inference", {}).get("day_type", {}),
}
```

**How the orchestrator and strategies relate:**

```
Orchestrator (5-min)          Strategies (1-min)           Agents (on-demand)
─────────────────             ──────────────────           ──────────────────
Publishes snapshots           Run independently.           Only fire when a
every 5 min to a              Don't read from              strategy emits a
cache/store.                  orchestrator.                Signal.
                              Don't wait for it.
Snapshot contains:                                         Read the latest
  premarket levels            Read raw 1-min bars.         cached snapshot.
  IB, VA, POC                 Emit Signal or None.         Query DuckDB.
  volume profile                                           Run Advocate/
  TPO, DPOC                   Signal contains enough       Skeptic/Orchestrator
  core confluences            info for agents to           debate.
                              evaluate: entry, stop,
No trade signals.             target, direction,           Return: TAKE / SKIP
No "should I trade?"          confidence, metadata.        / REDUCE_SIZE
```

**How promotion works:** Same as Approach C — add to `configs/active_strategies.yaml`. The signal runner is now a 1-min loop that calls `strategy.on_bar()` for each activated strategy.

**Config:**

```yaml
# configs/active_strategies.yaml
strategies:
  - name: or_reversal
    version: "2.1"
    entry_model: retest_50pct
    enabled: true
    agent_review: true          # Signal triggers agent debate before execution
  - name: eighty_percent_rule
    version: "1.3"
    entry_model: model_b
    enabled: true
    agent_review: true
  - name: twenty_percent_rule
    version: "1.0"
    enabled: false
    agent_review: false         # When re-enabled, could skip agents for fast signals
```

| Pros | Cons |
|------|------|
| **Strategies run at native 1-min resolution** — no downsampling | Agent latency (~2-5s) means the entry price may drift from signal |
| **Agents only fire when needed** — no wasted compute on quiet bars | Need a cached snapshot store (orchestrator publishes, agents read) |
| **Clean separation** — strategies don't import from orchestrator, orchestrator doesn't import from strategies | Two independent loops to manage (1-min strategy loop + 5-min orchestrator loop) |
| **Matches the three-tier model** — Tier 0 (strategies) < 10ms, Tier 1 (agents) on-demand, Tier 2 (reflection) daily | Strategies can't benefit from orchestrator data at detection time (only agents see it) |
| **No timeframe conflict** — each system runs at its natural cadence | |
| **Agent debate adds conviction** — signal is the hypothesis, agents are the jury | |

**Mitigation for entry price drift:** The Signal includes the entry price at detection time. The agent debate takes ~2-5s. If the agent returns TAKE, execution uses a limit order at the signal's entry price (or current price if better). This is how it would work in live trading anyway — detection and execution are always separated by some latency.

**Mitigation for strategies needing orchestrator data:** Some strategies (like 80P Rule) need prior session VA levels. These are **session-level constants** that don't change during RTH. They can be pre-loaded into `session_context` at session start from the orchestrator's first snapshot, or computed independently by the strategy from the raw DataFrame. They don't need real-time orchestrator updates.

#### Downsides & Mitigations

**1. Blind spots — what if the market screams "trade" but no strategy fires?**

The orchestrator might see a perfect B-Day setup forming with all confluences aligned, but if no activated strategy has detection logic for that exact pattern, nothing happens. The "feel" goes unused.

*Mitigation: This is the right behavior.* The whole purpose of the strategy lifecycle is to study edges over 250+ sessions, validate profitability, and only then add to the repertoire. We currently have 4-5 proven strategies. If the market presents a pattern none of them cover, that's a **research opportunity**, not a missed trade. The daily Qwen3.5 reflection can flag sessions where strong confluences existed but no strategy fired — feeding the research pipeline for new strategies. But the system should never trade a pattern it hasn't proven.

**2. Strategy fires without market context**

A strategy detects a textbook OR reversal, but the orchestrator data shows it's a high-conviction trend day (80%+ confidence). The strategy doesn't know that — it only sees 1-min bars. The agents catch it during debate, but there's a wasted agent cycle.

*Mitigation: This is actually fine.* A 2-5s debate that returns SKIP is cheap. The agent's job IS to apply market context to the signal. Embedding orchestrator awareness into strategies would re-couple the systems. The strategy says "I see a setup," the agent says "yes, but the market says otherwise" — that's the architecture working correctly.

**3. Simultaneous conflicting signals**

Multiple strategies can fire on the same session (OR reversal says SHORT, 80P says LONG on a gap day). Agents debating each independently could produce contradictory decisions.

*Mitigation: The agent Orchestrator (capital O) should see ALL pending signals as a portfolio, not one at a time.* When multiple signals queue within a short window, batch them into a single debate: "OR reversal says SHORT, 80P says LONG — which has more evidence given today's market structure?" This is a Phase 2 agent pipeline design decision.

**4. Novel market regimes go untraded**

The orchestrator detects something unprecedented (VIX spike, market structure break, unusual volume profile) but no strategy is designed for it. The system sits idle while the LLM "feels" something big.

*Mitigation: This is correct behavior.* Trading what you've proven > trading what feels interesting. Novel regimes are research fodder, not live signals. The LLM's job in this architecture is NOT to generate trade ideas — it's to **observe, interpret, and provide context** for the agents when they evaluate proven strategy signals. We don't want the LLM deciding to trade. We want it reading the chart, reading market action, making observations — and handing that context to agents who evaluate signals from strategies with 250+ session track records.

**5. Why not just let the LLM trade directly from orchestrator snapshots?**

The orchestrator publishes 78 snapshots per RTH day. An LLM reviewing each one could find "something worth trading" in most of them — that's what LLMs do, they find patterns everywhere. This leads to:
- **Overtrading** — Finding setups that aren't there because the model is always looking
- **Unproven edges** — The LLM might identify real patterns, but without 250+ session backtest validation, we don't know if they're profitable
- **Overhead** — Running agent debate 78 times per day instead of 1-3 times

The strategy-as-trigger architecture prevents all of this. The proven strategies are the **quality gate**. The LLM + orchestrator provide the **market awareness**. The agents provide the **final judgment**. Each does one job.

---

## Comparison Matrix

| Criteria | A: Shared Core | B: Self-Contained | C: Signal Runner | D: Layered | **E: Event-Driven** |
|----------|---------------|-------------------|-----------------|-----------|-------------------|
| Strategy iteration speed | Medium | Fast | Fast | Fast | **Fast** |
| Orchestrator stability | Low (coupled) | High | High | High | **High** |
| Code duplication | None | Some | Some | Minimal | Some |
| Promotion effort | Medium (write module) | Low (bundled) | Low (add to config) | Low (register) | **Low (add to config)** |
| Breaking change risk | **High** | None | Low | Low | **None** |
| Migration effort from today | Low | Medium | Medium | High | **Medium** |
| Long-term maintainability | Medium | Medium | Good | Best | **Best** |
| Timeframe flexibility | Locked to orchestrator | Locked | Locked | Locked | **Each runs at native cadence** |
| Scalability (add strategies) | Low | Good | Good | Good | **Best** |
| Agent integration | Bolted on | Bolted on | Bolted on | Planned | **Native** |

---

## Recommendation

**Approach E (Event-Driven)** as the primary architecture, with **D (Layered)** applied to the orchestrator's internal cleanup.

### Design Philosophy: Three Roles, One System

```
ORCHESTRATOR + LLM          STRATEGIES              AGENTS
═══════════════════         ═══════════             ══════
The Eyes                    The Trigger             The Brain
─────────────────           ───────────             ─────────
Observe the market.         Detect proven edges.    Make the final call.
Read the chart.             Backtested over 250+    Debate the signal
Read market action.         sessions. Only edges    using orchestrator
Make observations.          with positive           context, historical
Collect data.               expectancy make the     data, and strategy
                            repertoire.             track record.
Does NOT decide
to trade.                   Currently 4-5 proven    Returns TAKE / SKIP /
Does NOT generate           strategies. We can      REDUCE_SIZE.
trade signals.              always add more —
                            but why add losers?     Fires ONLY when a
Publishes snapshots                                 strategy signals.
for context.                Fires independently     No signal = no work.
                            at 1-min resolution.
Feeds training data.        <10ms per bar.
```

The LLM is NOT trained to trade. It's trained to **read and interpret market structure** — the same way a trader reads a chart before even thinking about a setup. The strategies carry the proven edges. The agents apply judgment.

### Why E?

1. **Resolves the timeframe mismatch** — Strategies run at 1-min (their native resolution). Orchestrator runs at 5-min (practical for LLM inference). Neither compromises for the other.
2. **Strategies and orchestrator are fully independent** — No shared code, no shared imports, no coupling. A strategy tweak cannot break the orchestrator. The orchestrator's snapshot schedule doesn't gate strategy detection.
3. **Prevents overtrading** — The orchestrator publishes 78 snapshots per RTH day. An LLM reviewing each one could talk itself into a trade on most of them. With strategy-as-trigger, only 1-3 signals per day reach the agents. The proven strategies are the quality gate.
4. **Agents are event-driven, not scheduled** — The expensive work (LLM debate, DuckDB queries, historical analysis) only happens when there's something to debate. On a quiet day with 0 signals, agents do 0 work. On a busy day with 5 signals, agents debate 5 times.
5. **Matches the three-tier model perfectly** — Tier 0 (strategies) is fast deterministic Python (<10ms). Tier 1 (agents) fires on-demand with Qwen3.5 (~2-5s). Tier 2 (Opus reflection) runs daily. Each tier at its natural cadence.
6. **Scalable** — Adding a new strategy means adding a fast Python function to the 1-min loop. It doesn't add 1.6s of orchestrator overhead per strategy. Ten strategies still take <100ms per bar.
7. **The orchestrator still does its job** — It still publishes 5-min snapshots for the UI dashboard, training data generation, and agent context. It just doesn't own strategy logic anymore. Agents read the latest cached snapshot when they need market context for debate.
8. **Natural path to live trading** — In live mode, the 1-min strategy loop is the signal generator, the agent pipeline is the conviction filter, and the client (NinjaTrader/TradingView) receives the final TAKE/SKIP decision. This is exactly the live architecture.

### How D fits in:

Approach D (Layered) still applies as an **internal cleanup of the orchestrator**:
- Remove strategy modules (or_reversal, globex_va_analysis 80P detection, twenty_percent_rule) from the orchestrator's Phase 3 "Setup Generation"
- Split hybrid modules: `globex_va_analysis.py` → pure VA data (stays) + 80P signal detection (moves to strategy)
- Orchestrator becomes purely market structure data (Layer 1)
- This is a cleanup step, not a prerequisite for E

### What NOT to do:

- **Don't embed strategies inside the orchestrator (A, C)** — This forces them onto 5-min cadence and couples their lifecycle
- **Don't restructure into per-strategy packages (B)** — Too much file churn for current codebase size

---

## Agent Pipeline Architecture (Incorporating Brainstorm Insights)

> This section synthesizes insights from three prior brainstorm docs into Approach E's agent pipeline. The brainstorms explored agent specialization, consensus mechanisms, and training data pipelines. Here we evaluate what fits within the Event-Driven architecture and what should be adapted or deferred.

### How Brainstorm Docs Map to Approach E

| Brainstorm Concept | Original Assumption | Under Approach E | Verdict |
|---|---|---|---|
| **01: 8 strategy specialists + sub-agents (Advocate/Skeptic/Historian)** | Every specialist processes every snapshot continuously | Specialists ARE the deterministic strategies; sub-agents fire only on signal | **Adapt** — role structure useful, trigger model changes |
| **01: Chief Strategist + Risk Manager orchestrators** | Synthesize all specialist reports every cycle | Only active signals reach agents; Orchestrator sees 1-3 signals/day, not 78 | **Keep** — but scope shrinks dramatically |
| **01: TimescaleDB + Redis Streams real-time infra** | Continuous data flow between agents | Event-driven = simpler infra (DuckDB + cached snapshots sufficient for Phase 1) | **Defer** — overkill for signal-triggered model |
| **04: Approach 1 (Strategy Specialists)** | LLM agents that reason about each strategy | Strategies are Tier 0 code, not LLM. Agents add judgment AFTER signal. | **Adapt** — specialist knowledge goes into agent prompts, not detection |
| **04: Approach 4/5 (Bayesian + Debate)** | Bayesian probability chain before LLM debate | Fits perfectly as a fast-path filter between signal and agents | **Incorporate** — see below |
| **04: Approach 2/3 (Domain Advisors)** | LLM agents for VWAP, HTF, ICT, Dalton, Order Flow | Orchestrator already does this deterministically (38 modules) | **Already built** — snapshot IS the domain analysis |
| **05: Three-stage training pipeline** | Generates DuckDB tables for specialist training | Feeds Bayesian calibration tables AND agent context queries | **Incorporate** — foundational infrastructure |
| **05: Per-strategy evidence extraction** | Build training pairs per strategy per domain | Directly supports strategy track records and historical context in agent_context | **Incorporate** — Phase 2 dependency |

### Key Insight: Bayesian Pre-Filter Before Agent Debate

Brainstorm/04's Approach 5 (Bayesian + Debate on conflicts) is the most valuable addition to Approach E. Currently, architecture/14 sends every signal to a full Advocate/Skeptic/Orchestrator debate (~2-5s). But most signals are either clearly good or clearly bad — the LLM debate is wasted on them.

**Proposed: Add a Bayesian probability layer between strategy signal and agent debate.**

```
Strategy emits Signal
         │
         ▼
  Bayesian Scorer (Tier 0, <10ms)
  ─────────────────────────────────
  Start: strategy base rate (from backtest, e.g., 64.4% WR for OR Rev)
  Update: check each calibrated factor against current conditions
    - IB range relative to ATR? (+/- WR adjustment)
    - Day type match? (+/- WR adjustment)
    - Wick parade count? (+/- WR adjustment)
    - DPOC direction? (+/- WR adjustment)
    - HTF alignment? (+/- WR adjustment)
  Result: adjusted probability P
         │
         ├──── P > 70%  ──→  AUTO-TAKE (no debate, log reasoning)
         │
         ├──── P < 35%  ──→  AUTO-SKIP (no debate, log reasoning)
         │
         └──── 35-70%   ──→  AGENT DEBATE (ambiguous → invoke full pipeline)
                              Advocate: "Why take despite uncertainty?"
                              Skeptic:  "What's driving the ambiguity?"
                              Orchestrator: resolves with historical context
```

**Why this works with Approach E:**
- Bayesian scorer is Tier 0 (pure Python, <10ms) — same tier as strategies
- Reduces LLM calls from ~100% of signals to ~30% (only ambiguous zone)
- Clear signals get faster execution (no 2-5s debate latency)
- Ambiguous signals get MORE attention (full debate resources focused where they matter)
- Calibration tables come from brainstorm/05's training pipeline (Stage 3)
- All decisions (auto and debated) log their probability chain for daily review

**What we need to build this:**
1. **Calibration tables** — Run all strategies through 266+ sessions, for each signal record: conditions at signal time → outcome. Compute per-factor hit rates. This is brainstorm/05's Stage 2 + Stage 3.
2. **Bayesian update engine** — Lightweight Python module. Likelihood ratios per factor, updated as new trades complete. No LLM needed.
3. **Threshold tuning** — Backtest different ambiguous-zone boundaries (35-70% vs 40-65% vs 45-60%). Optimize for: "what % of signals go to fast-path AND fast-path accuracy stays above 60%?"

**Data concern:** 266 sessions may be thin for conditional probabilities (e.g., "OR reversal + wick parade > 4 + Trend day" might have only 5 instances). Mitigations:
- Start with unconditional base rates (just the strategy's overall WR)
- Add factors one at a time as data supports them
- Use wider ambiguous zones initially, narrow as data accumulates
- Pool similar strategies (OR reversal + OR acceptance share an "opening range" cluster)

### Agent Roles Under Approach E

Brainstorm/01 designed 8 strategy specialists, each with Advocate/Skeptic/Historian sub-agents. Under Approach E, the roles simplify because:

1. **Strategy specialists don't need to be LLM agents** — The deterministic strategy code IS the specialist. It detects the setup in <10ms. The LLM doesn't need to learn setup detection.

2. **Advocate/Skeptic/Orchestrator still make sense** — But they reason about WHETHER to take the signal, not WHETHER the setup exists. The setup already exists (strategy fired). The debate is about context, timing, and conviction.

3. **Historian becomes a DuckDB query, not an agent** — "Show me the last 15 times OR reversal fired on a Trend day with wick parade > 3" is a SQL query, not an LLM task.

**Revised agent roles for Approach E:**

```
Signal fires → Bayesian scorer → [if ambiguous] → Agent Debate
                                                      │
                                                      ▼
                                               ┌─────────────┐
                                               │  Advocate    │
                                               │              │
                                               │  Builds case │
                                               │  FOR taking  │
                                               │  the signal. │
                                               │  Uses:       │
                                               │  - Snapshot   │  (orchestrator context)
                                               │  - DuckDB     │  (similar sessions)
                                               │  - Bayesian P │  (quantitative base)
                                               └──────┬───────┘
                                                      │
                                               ┌──────▼───────┐
                                               │  Skeptic     │
                                               │              │
                                               │  Challenges  │
                                               │  the case.   │
                                               │  Asks:       │
                                               │  - What's    │  driving the ambiguity?
                                               │  - What does │  the losing subset look like?
                                               │  - Any novel │  risk factors today?
                                               └──────┬───────┘
                                                      │
                                               ┌──────▼───────┐
                                               │ Orchestrator │
                                               │              │
                                               │ Resolves.    │
                                               │ Sees:        │
                                               │ - Advocate + │  Skeptic reasoning
                                               │ - ALL pending│  signals (portfolio view)
                                               │ - Daily P&L  │  and risk limits
                                               │              │
                                               │ Returns:     │
                                               │ TAKE / SKIP  │
                                               │ / REDUCE_SIZE│
                                               └──────────────┘
```

**What changes from brainstorm/01:**
- No per-strategy sub-agents — one Advocate/Skeptic pair debates ANY signal (prompt includes strategy-specific context from DuckDB)
- Historian is a query function, not an agent
- Orchestrator sees portfolio-level risk (max simultaneous positions, daily P&L limit)
- The Advocate/Skeptic use ONE model + ONE LoRA with strategy-specific system prompts (not per-strategy LoRA)

### Training Data Pipeline Connection

Brainstorm/05's three-stage pipeline is the foundational infrastructure for both the Bayesian scorer and agent context:

```
Stage 1: Bulk Snapshot Generation          ──→  Orchestrator snapshots in DuckDB
  (Already exists: generate_deterministic_snapshots.py)

Stage 2: Backtest Enrichment               ──→  Per-signal snapshot + outcome
  (Run backtest, at each signal capture:
   strategy, direction, entry/stop/target,
   WIN/LOSS, PnL, AND the orchestrator
   snapshot at that moment)

Stage 3: Evidence Extraction               ──→  Calibration tables + context DB
  (Per strategy: factor → outcome tables
   for Bayesian scorer.
   Per signal: similar-session lookup
   for agent context.)
```

**What this enables:**
- **Bayesian scorer** reads Stage 3 calibration tables at startup, updates incrementally after each completed trade
- **Advocate** queries Stage 2 for "last N signals from this strategy with similar conditions → what happened?"
- **Skeptic** queries Stage 2 for "last N LOSING signals from this strategy → what were the conditions?"
- **Daily reflection** (Tier 2, Opus) reviews Stage 2 for "sessions where Bayesian said TAKE but outcome was LOSS → recalibrate?"

### Agentic Backtesting: Validating That Agents Add Alpha

The ultimate test (brainstorm/04's Open Question #5): **Does agent consensus improve outcomes beyond what the mechanical strategy already produces?**

To answer this, we need to backtest the full agent pipeline:

```
For each historical session (266+ sessions):
  1. Run strategy signal loop → collect all signals
  2. For each signal, run Bayesian scorer + agent debate
  3. Record: signal + agent decision (TAKE/SKIP/REDUCE_SIZE)
  4. Compare:
     a. Mechanical-only: all signals taken (current backtest)
     b. Bayesian-only:   auto-take P>70%, auto-skip P<35%, skip ambiguous
     c. Full pipeline:   auto-take P>70%, auto-skip P<35%, debate ambiguous
  5. Measure: WR, PF, net PnL, max DD for each approach
```

**Expected outcome:** Agent consensus should:
- Improve WR by filtering low-confidence signals (SKIP the losers)
- Slightly reduce total trades (fewer signals taken)
- Meaningfully reduce drawdown (catching regime-inappropriate signals)
- Possibly hurt PF if agents are too conservative (skip some winners too)

**The exciting experiment** (user's idea): Take a mediocre strategy (e.g., Mean Reversion VWAP, currently -$6,925 net) and run it through the agent pipeline. If agents can turn a slightly-losing strategy into a breakeven or winning one by SKIPing the bad signals, that validates the entire architecture.

**Infrastructure needed:**
- Backtest engine needs a "replay mode" that calls the agent pipeline at each signal
- Need to mock or actually run LLM inference for 266+ sessions × 1-3 signals/session ≈ 500-800 LLM calls
- Results stored in DuckDB for comparison analysis
- This is a Phase 2 validation exercise (after Bayesian scorer and agent pipeline are built)

### What NOT to Incorporate

Some brainstorm concepts are deferred because they don't fit Approach E yet:

1. **Per-strategy LoRA adapters** (brainstorm/04, Open Question #3) — Start with one LoRA + prompt-driven specialization. Only split if evidence shows prompting is insufficient.

2. **Domain specialist agents as LLM agents** (brainstorm/04, Approach 2) — The 38 deterministic modules already produce domain analysis faster and more reliably than LLM agents would. Domain knowledge lives in the snapshot, not in an agent.

3. **Continuous agent processing** (brainstorm/01) — The entire point of Approach E is event-driven. Running agents continuously contradicts the signal-triggered model and leads to overtrading.

4. **Redis Streams / TimescaleDB** (brainstorm/01) — Overkill for Phase 1. DuckDB + file cache handles 1-3 signals/day. Revisit if signal volume or multi-instrument trading requires real-time streaming.

5. **8 specialist sub-agent teams** (brainstorm/01) — Too much infra for current signal volume. One Advocate/Skeptic/Orchestrator trio with strategy-specific prompts is sufficient. Scale to per-strategy agents only if one trio can't handle the reasoning quality.

---

## Skills Needed

| Skill | Purpose | Status |
|-------|---------|--------|
| `/add-strategy` | Scaffold new strategy, run initial backtest, begin iteration loop | Exists (basic) |
| `/promote-strategy` | Activate a validated strategy into orchestrator output via config | **New — needs creation** |
| `/regression-check` | Full pipeline: tests + lint + backtest + baseline comparison | Exists |

### `/promote-strategy` Workflow

```
1. Verify strategy has passing tests and a locked baseline
2. Add entry to configs/active_strategies.yaml
3. If strategy needs new indicators/helpers, verify they're importable
4. Run orchestrator integration tests (snapshot generation with new strategy)
5. Generate a sample snapshot and validate JSON schema
6. Commit config change on current branch
```

---

## Versioning & Configuration

Regardless of approach, strategies need versioned configuration:

```yaml
# Per strategy — either in configs/active_strategies.yaml or per-strategy config
strategy: or_reversal
version: "2.1"
entry_model: retest_50pct      # Which entry model is active
risk_model: atr_2x             # Stop = 2x ATR
target_model: 2R               # Target = 2R
timeframe: 1min                # Bar size for backtest
constants:
  OR_MINUTES: 15
  EOR_MINUTES: 30
  SWEEP_THRESHOLD_RATIO: 0.17
baseline:
  win_rate: 0.609
  profit_factor: 2.96
  total_trades: 65
  baseline_date: "2026-03-02"
```

This config serves:
- **Reproducibility** — Reconstruct any past version
- **A/B testing** — Run two versions side by side in backtest
- **Rollback** — Revert to previous config if promoted version regresses
- **Agent consumption** — Agents read configs to understand what's active
- **Promotion audit trail** — Who promoted what, when, with what parameters

---

## Handling New Indicators/Modules During Strategy Development

During the develop/validate loop, a strategy may need new indicators or helper modules:

**Example:** A new "Volume Imbalance" strategy needs a `volume_imbalance_detector` that doesn't exist yet.

### Options:

1. **Inline in strategy** (simplest) — Helper function lives inside the strategy file. Works for backtest. If promoted, the signal runner calls it as part of the strategy. No orchestrator changes needed.

2. **Separate utility module** — `strategies/indicators/volume_imbalance.py`. Strategy imports it. If promoted, the signal runner passes it context, strategy calls indicator internally.

3. **New orchestrator module** (only if the indicator has standalone value for training data/UI) — `deterministic/modules/volume_imbalance.py`. Added to orchestrator separately. Strategy can then read its output from `intraday_data` at signal-runner time.

**Decision rule:** Start with option 1 (inline). Move to 2 if reused across strategies. Move to 3 only if the data itself (not just the signal) needs to appear in training data or UI.

---

## Known Bugs to Fix (Any Approach)

| Bug | Location | Fix |
|-----|----------|-----|
| OR module/strategy bar constants not linked | `OR_BARS=3` (module) vs `OR_BARS=15` (strategy) | Shared `OR_MINUTES=15` constant, derive bar count from timeframe |
| 20P strategy cutoff too late | `strategies/twenty_percent_rule.py:43` `ENTRY_CUTOFF = _time(14, 0)` | Change to `_time(13, 0)` per research (WR drops to ~32% after 13:00) |
| 80P strategy missing Model B | `strategies/eighty_percent_rule.py` only has Model A + C | Add Model B (limit at 50% VA depth — best $/mo: $1,922, PF 2.57) |

These can be fixed independently of the architecture choice.

---

## Implementation Phases

### Phase 1: Strategy Signal Loop + Config (Approach E foundation)

1. Create `configs/active_strategies.yaml` listing currently activated strategies
2. Create `rockit_core/signal_loop.py` — 1-min bar loop that:
   - Loads activated strategies from config
   - Calls `strategy.on_bar()` for each bar
   - When a Signal is emitted, packages it with context and fires the agent pipeline (or queues for agent review)
   - Catches errors per-strategy (one strategy crash doesn't stop others)
3. Create `/promote-strategy` skill
4. Fix the 3 known bugs (20P cutoff, 80P Model B, OR constants)
5. Add tests for signal loop + config loading

### Phase 2: Training Data Pipeline + Bayesian Scorer

1. **Backtest enrichment** (brainstorm/05 Stage 2): Modify backtest engine to capture the orchestrator snapshot at each signal point. Store in DuckDB: strategy, signal, snapshot_hash, conditions, outcome.
2. **Evidence extraction** (brainstorm/05 Stage 3): For each strategy, compute per-factor hit rates (e.g., "OR reversal on Trend day: 72% WR" vs "OR reversal on Balance day: 54% WR"). Build calibration tables.
3. **Bayesian scorer module** (`rockit_core/bayesian_scorer.py`): Loads calibration tables at startup. Given a Signal + current conditions, outputs adjusted probability. Pure Python, <10ms.
4. **Threshold tuning**: Backtest different ambiguous zones (35-70%, 40-65%, etc.). Optimize for fast-path accuracy + coverage.
5. Tests for scorer accuracy against historical data.

### Phase 3: Agent Pipeline Integration

1. Create `rockit_core/agent_trigger.py` — receives a Signal + Bayesian score + builds `agent_context`:
   - Only fires for signals in the ambiguous zone (35-70%)
   - Auto-TAKE for P > 70%, auto-SKIP for P < 35%
   - Grabs latest cached orchestrator snapshot
   - Queries DuckDB for similar sessions and strategy track record
   - Includes Bayesian probability chain (what shifted P and by how much)
2. Wire agent trigger → LangGraph agent pipeline (Advocate/Skeptic/Orchestrator)
3. Advocate and Skeptic receive: signal + snapshot + DuckDB results + Bayesian breakdown
4. Agent pipeline returns: TAKE / SKIP / REDUCE_SIZE + reasoning
5. Dashboard alert or client execution based on decision

### Phase 4: Agentic Backtesting (Validation)

1. **Replay mode** in backtest engine: for each historical signal, run Bayesian scorer + agent debate
2. Compare three approaches across 266+ sessions:
   - Mechanical-only (all signals taken — current baseline)
   - Bayesian-only (auto-take/skip, discard ambiguous)
   - Full pipeline (auto-take/skip, debate ambiguous)
3. **Mediocre strategy experiment**: Run Mean Reversion VWAP (currently -$6,925) through the full pipeline. If agents turn it breakeven or positive, that's strong validation.
4. Store all decisions + reasoning in DuckDB for analysis
5. Success metric: full pipeline WR and PF exceed mechanical-only with lower drawdown

### Phase 5: Orchestrator Cleanup (Approach D internal)

1. Remove strategy detection modules from orchestrator Phase 3 (or_reversal, globex_va_analysis 80P detection, twenty_percent_rule, edge_fade, va_edge_fade)
2. Split hybrid modules: `globex_va_analysis.py` → pure VA data (stays) + 80P signal (now lives only in strategy)
3. Orchestrator becomes purely market structure data
4. Orchestrator publishes snapshots to cache/store for agent consumption

### Phase 6: Strategy Versioning & A/B Testing

1. Per-strategy config with entry/risk/target model + constants
2. Baseline snapshot in config (WR, PF, trade count, date)
3. A/B testing support: run two versions of same strategy in parallel backtest
4. Auto-rollback guard: if promoted version regresses below baseline, alert

---

## Live Trading Data Flow (How This Works End-to-End)

```
Market Data Feed (1-min bars)
         │
         ├──────────────────────────────────────────────┐
         │                                               │
         ▼                                               ▼
  Strategy Signal Loop (1-min)                Orchestrator (5-min)
  ────────────────────────                    ──────────────────
  Runs activated strategies                   Publishes market structure
  bar-by-bar. Pure Python.                    snapshots to cache.
  <10ms per bar.                              ~1.6s per snapshot.
                                              UI dashboard reads these.
  Signal emitted? ──YES──┐                    Training pipeline reads these.
         │               │
         NO              ▼
         │        Bayesian Scorer (Tier 0, <10ms)
     (do nothing)  ────────────────────────────────
                   Loads calibration tables from DuckDB.
                   Computes adjusted probability P.
                           │
                   ┌───────┼────────┐
                   │       │        │
                 P>70%   35-70%   P<35%
                   │       │        │
                   ▼       ▼        ▼
               AUTO-TAKE  DEBATE  AUTO-SKIP
               (log it)    │     (log it)
                   │       │        │
                   │       ▼        │
                   │  Agent Pipeline│
                   │  (on-demand)   │
                   │  ─────────     │
                   │  Read snapshot  │
                   │  Query DuckDB   │
                   │  Advocate/      │
                   │  Skeptic/       │
                   │  Orchestrator   │
                   │  ~2-5s          │
                   │       │        │
                   │       ▼        │
                   │  TAKE/SKIP/    │
                   │  REDUCE_SIZE   │
                   │       │        │
                   └───────┼────────┘
                           │
                   ┌───────┴────────┐
                   │                │
                   ▼                ▼
              Dashboard          Client
              Alert              Execution
              (all modes)        (live mode only)
                                     │
                                     ▼
                              Daily Reflection (Tier 2)
                              ─────────────────────────
                              Opus reviews all decisions.
                              Recalibrates Bayesian tables.
                              Flags blind spots for research.
```

**Why this is more scalable:**
- Adding strategy #11 adds ~1ms to the 1-min loop, not ~1.6s to the orchestrator
- Agent compute scales with signals, not with time — quiet sessions = no agent work
- Bayesian fast-path handles ~70% of signals without any LLM call
- LLM debate focuses on the ~30% of ambiguous signals where it matters most
- Orchestrator snapshot generation and strategy detection are independent processes
- LLM inference (Tier 1 Qwen3.5) is only used for ambiguous signals
- The orchestrator + LLM continue to interpret market data for training and dashboard — this doesn't change
- Daily reflection loop feeds back into both Bayesian calibration AND research pipeline

---

## Out of Scope

- Building new backtest strategies for Edge Fade / VA Edge Fade (separate task)
- Agent ownership of strategies (Phase 2+ of agent system, see `08-agent-system.md`)
- Holiday/early-close calendar awareness
- Cross-instrument strategy coordination
- Client-side execution protocol (NinjaTrader/TradingView — see `04-platform-abstraction.md`)
- Per-strategy LoRA adapters (brainstorm/04 Open Question #3 — start with one LoRA + prompts)
- Domain specialist agents as LLM agents (brainstorm/04 Approach 2 — the 38 deterministic modules already do this faster)
- Continuous agent processing (brainstorm/01 — contradicts signal-triggered model)
- Redis Streams / TimescaleDB real-time infra (brainstorm/01 — overkill for 1-3 signals/day)
- 8 specialist sub-agent teams (brainstorm/01 — one Advocate/Skeptic/Orchestrator trio is sufficient for current signal volume)
