# 14 — Strategy ↔ Orchestrator Integration Architecture

> **Cross-references:**
> - [technical-design/14-strategy-agent-lifecycle.md](../technical-design/14-strategy-agent-lifecycle.md) — Strategy lifecycle stages (research → implement → backtest → walk-forward → shadow → promote → live)
> - [technical-design/04-strategy-framework.md](../technical-design/04-strategy-framework.md) — StrategyBase interface, Signal model, YAML config, registry
> - [technical-design/10-deterministic-modules.md](../technical-design/10-deterministic-modules.md) — Orchestrator, 38 modules, dependency chain, module interface

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

### Phase 2: Agent Pipeline Integration

1. Create `rockit_core/agent_trigger.py` — receives a Signal + builds `agent_context`:
   - Grabs latest cached orchestrator snapshot
   - Queries DuckDB for similar sessions and strategy track record
   - Includes signal metadata and strategy baseline
2. Wire agent trigger → LangGraph agent pipeline (Advocate/Skeptic/Orchestrator)
3. Agent pipeline returns: TAKE / SKIP / REDUCE_SIZE + reasoning
4. Dashboard alert or client execution based on decision

### Phase 3: Orchestrator Cleanup (Approach D internal)

1. Remove strategy detection modules from orchestrator Phase 3 (or_reversal, globex_va_analysis 80P detection, twenty_percent_rule, edge_fade, va_edge_fade)
2. Split hybrid modules: `globex_va_analysis.py` → pure VA data (stays) + 80P signal (now lives only in strategy)
3. Orchestrator becomes purely market structure data
4. Orchestrator publishes snapshots to cache/store for agent consumption

### Phase 4: Strategy Versioning & A/B Testing

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
         │        Agent Pipeline (on-demand)
     (do nothing)  ─────────────────────────
                   Reads latest snapshot from cache.
                   Queries DuckDB for history.
                   Advocate/Skeptic/Orchestrator debate.
                   ~2-5s total.
                           │
                           ▼
                   Decision: TAKE / SKIP / REDUCE_SIZE
                           │
                   ┌───────┴────────┐
                   │                │
                   ▼                ▼
              Dashboard          Client
              Alert              Execution
              (all modes)        (live mode only)
```

**Why this is more scalable:**
- Adding strategy #11 adds ~1ms to the 1-min loop, not ~1.6s to the orchestrator
- Agent compute scales with signals, not with time — quiet sessions = no agent work
- Orchestrator snapshot generation and strategy detection are independent processes
- LLM inference (Tier 1 Qwen3.5) is only used for signals that have a real trade setup
- The orchestrator + LLM continue to interpret market data for training and dashboard — this doesn't change

---

## Out of Scope

- Building new backtest strategies for Edge Fade / VA Edge Fade (separate task)
- Agent ownership of strategies (Phase 2+ of agent system, see `08-agent-system.md`)
- Holiday/early-close calendar awareness
- Cross-instrument strategy coordination
- Client-side execution protocol (NinjaTrader/TradingView — see `04-platform-abstraction.md`)
