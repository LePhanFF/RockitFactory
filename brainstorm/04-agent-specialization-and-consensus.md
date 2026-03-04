# Agent Specialization & Consensus Building

**Status**: Brainstorm / Exploration
**Date**: 2026-03-03
**Context**: Extends `08-agent-system.md` (Revision 3) and `brainstorm/01-agent-consensus-architecture.md`

---

## The Core Question

The current architecture uses **role-based agents** (Advocate/Skeptic/Orchestrator) sharing one model + one LoRA. The debate is about *evidence quality*, not *domain expertise*.

But we have distinct analytical domains — VWAP, HTF, ICT, Dalton TPO, Order Flow — and 16 specific strategies built on those domains. Should the agents be domain experts rather than (or in addition to) debate roles? How do domain-specialist agents build consensus?

This document explores **five approaches** to agent specialization and consensus, with pros/cons and what each would take to build.

---

## Starting Point: What We Already Have

Before exploring new ideas, grounding in what's proven:

- **16 strategies** across 259 sessions, 283 trades, 55.5% WR, 1.58 PF
- **Core portfolio**: TrendBull, PDay, BDay, EdgeFade, IBHSweep, BearAccept, ORReversal, IBRetest
- **38 deterministic modules** producing rich snapshots (<10ms)
- **~7,500 JSONL training examples** from rockit-framework output
- **Backtest data** with entry/stop/target/outcome for every trade

The strategies are already profitable and mechanical. Whatever agent architecture we build should amplify this, not replace it.

---

## Approach 1: Strategy-Specialist Agents (Start Here)

### Concept

Instead of generic Advocate/Skeptic, train agents that are deeply expert at **specific strategies**. Each agent understands one strategy's entry conditions, edge cases, when it works, when it fails, and why.

```
┌──────────────────────────────────────────────────────────────┐
│                    STRATEGY SPECIALISTS                       │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ 20P Agent│ │ 80P Agent│ │ BDay     │ │ EdgeFade     │   │
│  │          │ │          │ │ Agent    │ │ Agent        │   │
│  │ Knows:   │ │ Knows:   │ │ Knows:  │ │ Knows:       │   │
│  │ - When   │ │ - Mean   │ │ - B-Day │ │ - IB edge    │   │
│  │   20P    │ │   rev    │ │   shape │ │   rejection  │   │
│  │   works  │ │   into   │ │ - Init  │ │ - Delta/CVD  │   │
│  │ - When   │ │   value  │ │   bal   │ │   diverg     │   │
│  │   it     │ │ - VA     │ │ - Ext   │ │ - FVG conf   │   │
│  │   fails  │ │   target │ │   break │ │ - Backtest   │   │
│  │ - Hist   │ │ - Mid vs │ │ - What  │ │   edge cases │   │
│  │   perf   │ │   opp VA │ │   kills │ │              │   │
│  └────┬─────┘ └────┬─────┘ └────┬────┘ └──────┬───────┘   │
│       │             │            │              │            │
│       └─────────────┴─────┬──────┴──────────────┘            │
│                           │                                  │
│                    ┌──────▼───────┐                          │
│                    │ Orchestrator │  Sees all specialist     │
│                    │              │  reports + backtest       │
│                    │              │  data → consensus         │
│                    └──────────────┘                          │
└──────────────────────────────────────────────────────────────┘
```

### How It Works

1. **Snapshot arrives** — all 38 deterministic modules run
2. **Each strategy specialist** receives the snapshot and analyzes from their strategy's perspective:
   - "Is my strategy's setup present? What's my confidence?"
   - "What does my historical data say about this exact condition set?"
   - "What are the risk factors specific to my strategy right now?"
3. **Specialists report** — structured output per agent (not free-form debate):
   ```json
   {
     "agent": "20p_specialist",
     "setup_present": true,
     "direction": "long",
     "confidence": 0.78,
     "supporting_evidence": ["IB accepted above prior VAH", "DPOC trending"],
     "risk_factors": ["Wick parade bearish count = 4", "HTF supply overhead"],
     "historical_context": "Last 15 similar conditions: 11W/4L (73%), avg PnL +2.1R",
     "recommendation": "TAKE with reduced size due to wick parade"
   }
   ```
4. **Orchestrator** receives all specialist reports, resolves conflicts, builds consensus

### Consensus Mechanism

When specialists **agree** (3 out of 4 active specialists say long):
- High conviction → TAKE full size
- Cross-reference: if 20P says long AND EdgeFade says long, that's strong confluence

When specialists **disagree** (20P says long, 80P says short):
- This is actually expected — trend strategies and mean reversion strategies SHOULD disagree in certain regimes
- Orchestrator knows the market regime (trending vs rotational) and weighs accordingly
- Day type classification resolves most disagreements deterministically

When specialists are **mixed** (some active, some inactive):
- Only strategies with active setups contribute
- A strategy saying "no setup present" is informative but doesn't vote

### Pros
- Directly leverages our existing 16 strategies and 259-session backtest data
- Each agent becomes deeply expert at its specific edge
- Consensus is grounded in proven strategies, not abstract reasoning
- Easy to measure: each specialist has a trackable win rate
- Natural alignment with how traders actually think ("what do my setups say?")
- Backtest replay is natural — run historical data, compare agent decisions to actual outcomes
- New strategies join the system the same way: build specialist, train on backtest, add to consensus

### Cons
- Need enough backtest data per strategy to train meaningful specialists (some strategies may have <20 trades)
- Doesn't capture cross-domain analysis that no single strategy covers
- Could miss emerging patterns that don't fit any existing strategy
- Each specialist needs its own prompt engineering and calibration

### What It Would Take
- **Prompt engineering**: 8-10 deeply specialized prompts (one per core portfolio strategy), each grounded in that strategy's backtest data
- **Backtest enrichment**: Each historical trade tagged with full snapshot + outcome, stored in DuckDB per strategy
- **Calibration runs**: Run each specialist through historical data, measure accuracy, tune prompts
- **Orchestrator design**: Logic for handling agreement/disagreement/mixed specialist reports
- **Estimated effort**: Medium. Uses existing data, existing infrastructure. Main work is prompt engineering + calibration.

---

## Approach 2: Domain-Specialist Agents

### Concept

Instead of strategy-specific agents, organize by **analytical domain**. Each agent reasons deeply about one style of analysis.

```
┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐
│   VWAP    │ │   HTF     │ │   ICT     │ │  Dalton   │ │  Order    │
│  Agent    │ │  Agent    │ │  Agent    │ │  TPO      │ │  Flow     │
│           │ │           │ │           │ │  Agent    │ │  Agent    │
│ - Dev     │ │ - Weekly  │ │ - FVGs    │ │ - Day     │ │ - Delta   │
│   VWAP    │ │   struct  │ │ - Liq     │ │   type    │ │ - CVD     │
│   slope   │ │ - Swing   │ │   sweeps  │ │ - IB      │ │ - Absorp  │
│ - Devia-  │ │   points  │ │ - Order   │ │ - Value   │ │ - Imbal   │
│   tion    │ │ - Trend   │ │   blocks  │ │ - Single  │ │ - Trap    │
│   bands   │ │   cont vs │ │ - Breaker │ │   prints  │ │   detect  │
│ - TWAP    │ │   rever   │ │ - Judas   │ │ - DPOC    │ │ - Exhaus  │
│ - Buyer/  │ │ - Supply/ │ │   swing   │ │   migr    │ │   tion    │
│   seller  │ │   demand  │ │ - BPR     │ │ - Auction │ │ - Stacked │
│   aggr    │ │   zones   │ │           │ │   quality │ │   levels  │
└─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
      │             │             │             │             │
      └─────────────┴──────┬──────┴─────────────┴─────────────┘
                           │
                    ┌──────▼───────┐
                    │ Orchestrator │  Synthesizes domain
                    │              │  perspectives into
                    │              │  trading decision
                    └──────────────┘
```

### How It Works

1. **Snapshot arrives** — deterministic modules run
2. **Each domain specialist** receives the full snapshot but analyzes ONLY from their domain:
   - VWAP Agent only reasons about volume-weighted levels, developing slope, deviation
   - Dalton Agent only reasons about TPO shapes, IB, value areas, single prints
   - ICT Agent only reasons about FVGs, liquidity sweeps, order blocks, BPRs
   - HTF Agent only reasons about daily/weekly structure, swing points, trend
   - Order Flow Agent only reasons about delta, CVD, absorption, imbalances
3. **Each domain specialist produces** a domain-specific analysis with directional bias + confidence
4. **Orchestrator synthesizes** domain perspectives into a trading decision

### Example: Disagreement Reveals Timeframe Conflict

```
VWAP Agent:    "Price reclaimed VWAP with slope turning up. Bullish bias. Confidence: 0.72"
Dalton Agent:  "IB accepted above prior VAH, DPOC migrating up. P-Day forming. Bullish. Conf: 0.80"
Order Flow:    "Delta positive but CVD diverging — passive sellers absorbing. Caution. Conf: 0.45"
ICT Agent:     "Daily FVG below unfilled. Could be liquidity sweep before fill. Bearish. Conf: 0.55"
HTF Agent:     "Weekly structure bearish. This rally is into supply zone. Bearish. Conf: 0.65"

Orchestrator:  "3 intraday domains bullish, 2 structural domains bearish.
               Intraday confluence is strong (VWAP + Dalton agree).
               But Order Flow absorption is a warning AND HTF supply overhead.
               DECISION: TAKE long, REDUCE_SIZE, tight stop, Target 1 only."
```

### Pros
- Mirrors how professional trading desks work (different analysts covering different domains)
- Captures cross-strategy insights that strategy-specific agents miss
- Disagreements between domains often reveal the most important information (timeframe conflicts, hidden risk)
- Domains are more stable than strategies — even if strategies change, VWAP analysis is VWAP analysis
- Can discover new strategy ideas where domain signals converge in unexpected ways
- Scales naturally — add a Sentiment agent, a Volatility agent, a Correlation agent later

### Cons
- Requires domain-specific training data (need to label/segment existing data by domain)
- Some domains overlap significantly (Dalton TPO and Order Flow both care about volume)
- Domain agents may not know about specific strategy edges (they analyze the domain, not the trade)
- More LLM calls per cycle (5 domain agents vs 3 role agents in current design)
- Harder to ground in backtest data — strategies have win rates, but "VWAP analysis" doesn't have a win rate on its own

### What It Would Take
- **Domain-specific prompts**: 5 deep prompts, each constraining the agent to reason only from its domain
- **Domain-filtered training data**: Label existing 7,500 JSONL examples by which domain observations were most relevant to each trade outcome
- **Domain calibration**: Run each domain agent through historical data, measure how often their directional call was correct
- **Cross-domain weighting**: Build a system that learns "when the Dalton agent is bullish AND Order Flow is cautious, the hit rate is X%"
- **Estimated effort**: Medium-High. Significant prompt engineering + need to build domain-specific evaluation framework.

---

## Approach 3: Hybrid — Strategy Specialists + Domain Advisors

### Concept

Strategy specialists own the trading decisions (Approach 1). Domain specialists serve as **advisors** that enrich the context — they don't vote, they provide analysis.

```
┌───────────────────────────────────────────────────────────────┐
│                     DOMAIN ADVISORS (Context)                  │
│                                                               │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐          │
│  │ VWAP │  │ HTF  │  │ ICT  │  │Dalton│  │ OFlo │          │
│  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘          │
│     │         │         │         │         │               │
│     └─────────┴────┬────┴─────────┴─────────┘               │
│                    │ domain context cards                     │
│                    ▼                                          │
│  ┌───────────────────────────────────────────────────────┐   │
│  │              STRATEGY SPECIALISTS (Decisions)          │   │
│  │                                                       │   │
│  │  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐             │   │
│  │  │ 20P  │  │ 80P  │  │ BDay │  │ Edge │  ... more    │   │
│  │  │      │  │      │  │      │  │ Fade │              │   │
│  │  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘             │   │
│  │     │         │         │         │                   │   │
│  │     └─────────┴────┬────┴─────────┘                   │   │
│  │                    │ strategy votes                    │   │
│  └────────────────────┼──────────────────────────────────┘   │
│                       ▼                                      │
│               ┌──────────────┐                               │
│               │ Orchestrator │                               │
│               └──────────────┘                               │
└───────────────────────────────────────────────────────────────┘
```

### How It Works

1. **Domain advisors run first** (can be deterministic or LLM). Produce "context cards":
   - `HTF_CONTEXT: "Weekly bearish, daily in pullback. Supply zone overhead at 21450."`
   - `VWAP_CONTEXT: "Price above VWAP, slope turning up, +1 dev band at 21480."`
2. **Strategy specialists run second**, receiving snapshot + domain context cards:
   - 20P Agent sees the HTF context and knows this breakout is into weekly supply → lowers confidence
   - EdgeFade Agent sees the Order Flow context about absorption → increases confidence in fade
3. **Strategy specialists vote** with confidence scores informed by domain context
4. **Orchestrator** resolves consensus from strategy votes

### Pros
- Strategies own decisions (grounded in backtest data), domains provide context (grounded in theory)
- Domain advisors can be mostly deterministic (Tier 0) — only edge cases need LLM
- Each strategy specialist is richer because it sees domain context, not just raw snapshot
- Natural separation: "what to trade" (strategies) vs "what's the environment" (domains)
- Phased build: start with strategy specialists only, add domain advisors later

### Cons
- Two layers of agents = more complexity, more calls, more latency
- Need to define the interface between domain context and strategy specialists
- Risk of information overload — strategy specialists might get confused by too much context
- Still need to build and calibrate both sets of agents

### What It Would Take
- **Phase 1**: Build strategy specialists (Approach 1) — works without domain advisors
- **Phase 2**: Add domain advisor prompts, define context card format
- **Phase 3**: Retrain strategy specialists to incorporate domain context
- **Estimated effort**: High, but phased. Phase 1 is medium, each subsequent phase is incremental.

---

## Approach 4: Bayesian Evidence Chain

### Concept

No debate. No voting. Each specialist (domain or strategy) **updates a running probability** based on their calibrated historical accuracy.

```
Start: Prior probability from base rate
       (e.g., 20P long base rate from backtest = 55% WR)

       55.0%  ──────────────────────────────────── Starting point
         │
         │  Dalton Agent: IB accepted, DPOC migrating up
         │  (Historical calibration: when Dalton says bullish, 68% accurate)
         │
       68.2%  ──────────────────────────────────── Shifted up
         │
         │  VWAP Agent: Reclaimed with slope turning
         │  (Calibration: when VWAP agrees with Dalton, 74% accurate)
         │
       73.8%  ──────────────────────────────────── Shifted up
         │
         │  Order Flow Agent: CVD diverging, passive absorption
         │  (Calibration: when OFlow cautious after bull signals, -8% hit)
         │
       65.1%  ──────────────────────────────────── Pulled back
         │
         │  ICT Agent: Daily FVG unfilled below
         │  (Calibration: unfilled FVGs have 62% fill rate within session)
         │
       59.3%  ──────────────────────────────────── Pulled back
         │
         │  HTF Agent: Weekly bearish, price at supply
         │  (Calibration: HTF bearish + intraday bull = 45% WR)
         │
       49.1%  ──────────────────────────────────── Below threshold
         │
       DECISION: SKIP (below 55% threshold)
```

### How It Works

1. **Calibration phase** (one-time, from backtest):
   - For each specialist, run through all 259 sessions
   - When Dalton agent said "bullish", what was the actual WR? → store as calibration
   - When Dalton said "bullish" AND VWAP said "bullish", WR? → conditional calibration
   - Build a Bayesian update table for each specialist + combinations
2. **Live inference**:
   - Start with strategy base rate (from backtest)
   - Each specialist updates the probability using their calibrated likelihood ratio
   - Final probability determines TAKE/SKIP/REDUCE_SIZE
3. **Self-calibration**: As new trades complete, update the calibration tables

### Pros
- Mathematically rigorous — grounded in Bayesian statistics, not vibes
- Self-correcting — calibration improves as data accumulates
- Transparent — you can see exactly which specialist shifted the probability and by how much
- Fast — no LLM debate needed, just lookups + math (could be fully deterministic)
- Easy to A/B test — change one specialist's calibration and measure the impact
- No "one model overriding another" — contributions are additive and auditable
- Can start with few specialists and add more without restructuring

### Cons
- Requires sufficient historical data per specialist per condition (259 sessions may be thin for conditional probabilities)
- Loses the "why" — a probability shift of -8% doesn't explain WHY the Order Flow is concerning
- Can't capture novel situations (if the model hasn't seen this combination before, calibration is undefined)
- Assumes independence between specialist observations (they're often correlated)
- Cold start: need to run all specialists through full backtest to get initial calibrations
- Missing narrative — the dashboard shows numbers, not reasoning

### What It Would Take
- **Calibration pipeline**: Run every specialist through all 259 sessions, compute per-specialist accuracy
- **Conditional probability tables**: Compute pairwise and triple-wise specialist accuracy (combinatorial)
- **Bayesian update engine**: Lightweight Python module — no LLM needed
- **Data requirements**: Might need 500+ sessions to get reliable conditional probabilities
- **Estimated effort**: Medium for the engine. High for getting enough calibrated data.

---

## Approach 5: Hybrid — Bayesian Base + LLM Debate on Conflicts

### Concept

Use Bayesian evidence chain (Approach 4) as the **default fast path**. Only invoke LLM debate when specialists **disagree strongly** (probability is in the ambiguous zone, e.g., 45-60%).

```
                    ┌──────────────┐
                    │   Snapshot    │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Specialists │  (domain or strategy)
                    │  each update │  (probability chain)
                    │  probability │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
              ┌─────│  P = 73%?    │─────┐
              │     │  Clear?      │     │
              │     └──────────────┘     │
        P > 65%                    45% < P < 65%
        or P < 35%                 (ambiguous zone)
              │                          │
       ┌──────▼──────┐          ┌────────▼────────┐
       │  FAST PATH  │          │  LLM DEBATE     │
       │  Auto-decide│          │  Advocate builds │
       │  (no LLM)   │          │  case for action │
       │             │          │  Skeptic asks    │
       │  TAKE/SKIP  │          │  what's causing  │
       │  based on P │          │  the ambiguity   │
       └─────────────┘          │  Orchestrator    │
                                │  resolves        │
                                └─────────────────┘
```

### How It Works

1. **Bayesian chain runs** (fast, no LLM) → produces a probability
2. **If probability is clear** (>65% or <35%) → auto-decide, no debate needed
3. **If probability is ambiguous** (45-65%) → invoke LLM debate:
   - Advocate explains WHY the bull case exists despite the ambiguity
   - Skeptic explains WHY the ambiguity should mean SKIP
   - Orchestrator resolves — is this ambiguity from genuine uncertainty or from conflicting timeframes?
4. **All decisions logged** → feeds back into calibration

### Pros
- Best of both worlds: speed when clear, depth when ambiguous
- Most time slices will be clear (SKIP or obvious TAKE) — saves LLM calls
- LLM debate focuses on the hard cases where it matters most
- The Bayesian base provides a quantitative grounding for the debate
- Preserves narrative/reasoning for the ambiguous cases (dashboard can show it)
- Naturally cost-efficient — maybe 70% of decisions are fast path, 30% need debate

### Cons
- Two systems to maintain (Bayesian engine + LLM debate pipeline)
- Threshold tuning: where is the "ambiguous zone"? Too narrow = never debates, too wide = always debates
- Hybrid complexity: need to merge Bayesian outputs with debate outputs cleanly
- Risk of the LLM overriding good Bayesian math with hallucinated reasoning

### What It Would Take
- **Everything from Approach 4** (Bayesian engine + calibration)
- **Debate pipeline from current 08-agent-system.md** (already designed)
- **Routing logic**: When to go fast path vs debate
- **Threshold tuning**: Backtest the ambiguous zone thresholds
- **Estimated effort**: High. Combines two approaches. But phased: build Bayesian first, add debate later.

---

## Comparison Matrix

| Dimension | 1. Strategy Specialists | 2. Domain Specialists | 3. Hybrid (Strat+Domain) | 4. Bayesian Chain | 5. Bayesian + Debate |
|---|---|---|---|---|---|
| **Grounded in our data?** | YES — directly uses 16 strategies + backtest | Partially — domains don't have win rates | YES — strategies have data, domains add context | YES — calibrated from backtest | YES — Bayesian from data, debate for edge cases |
| **Explains WHY?** | YES — each specialist explains their strategy's view | YES — domain perspective gives rich reasoning | YES — both layers contribute reasoning | NO — just numbers | YES for ambiguous cases, NO for clear ones |
| **LLM calls per cycle** | ~5-10 (active specialists + orchestrator) | ~6 (5 domains + orchestrator) | ~10-15 (domains + strategies + orchestrator) | **0** (fully deterministic) | 0-3 (most cycles = 0, ambiguous = 3) |
| **Latency** | Medium | Medium | Higher | **Lowest** | Low (usually), Medium (when debating) |
| **Data needed to start** | Medium — need per-strategy backtest data | High — need domain-labeled data | High | High — need calibration tables | Very high |
| **Complexity** | Medium | Medium | High | Medium | High |
| **Captures novel patterns?** | NO — limited to known strategies | YES — domains can spot new patterns | YES — domain advisors see beyond strategies | NO — only calibrated patterns | Somewhat — debate can reason about novel cases |
| **Self-improving?** | YES — per-strategy scorecard | Harder — domain accuracy is indirect | YES — both layers improve | YES — recalibrate as data grows | YES — both calibration and prompts improve |
| **Phase 1 viable?** | **YES — can start immediately** | Needs domain labeling first | Phase 1 = just strategies | Needs calibration pipeline first | Needs both systems |

---

## Phased Recommendation (Not a Decision — A Discussion)

Based on "start with what's profitable and proven, scale intelligence later":

### Phase 1: Strategy Specialists (Approach 1)

**Why start here**: We have 16 strategies with backtest data. The agents become expert at those strategies. Consensus is "which strategy specialists see their setup, and do they agree on direction?" This is the most directly measurable approach.

**Build**:
- 8 strategy-specialist prompts (core portfolio)
- DuckDB enrichment per strategy (historical conditions → outcomes)
- Specialist → Orchestrator consensus pipeline
- Backtest replay framework to measure specialist accuracy

**Success metric**: Run specialists through 259 sessions. Do they match or beat the existing backtest WR/PF?

### Phase 2: Add Bayesian Calibration (Approach 4 as an overlay)

**Why second**: Once we have specialist accuracy data from Phase 1 replays, we can compute calibration tables. This makes the system self-quantifying.

**Build**:
- Per-specialist accuracy tables from Phase 1 replay
- Conditional accuracy (specialist A agrees with specialist B → outcome)
- Bayesian update engine
- Fast-path routing (clear probability → no LLM needed)

**Success metric**: Bayesian fast-path handles 60%+ of decisions correctly without LLM.

### Phase 3: Add Domain Advisors (Approach 3)

**Why third**: Once strategy specialists are working and calibrated, domain advisors add richness to the context. VWAP context helps the 20P specialist make better calls. HTF context helps all specialists understand structural risk.

**Build**:
- Domain advisor prompts (can start deterministic, upgrade to LLM if needed)
- Context card interface between domain advisors and strategy specialists
- Retrain/recalibrate strategy specialists with domain context

**Success metric**: Strategy specialist accuracy improves with domain context vs without.

### Phase 4: Full Hybrid (Approach 5)

**Why last**: This is the most complex but most capable. By now we have:
- Strategy specialists that know their edge
- Bayesian calibration that quantifies confidence
- Domain advisors that provide rich context
- LLM debate reserved for the genuinely hard calls

**Build**:
- Ambiguous-zone routing (Bayesian → debate when uncertain)
- Full narrative generation for debated decisions
- Dashboard shows both the probability chain and the debate reasoning

---

## Open Questions to Ponder

### 1. Should specialists be LLM-powered or deterministic?

Many strategy specialists COULD be fully deterministic. The 20P specialist just checks: IB accepted? DPOC trending? Extension target viable? That's all Boolean/numeric.

Where LLM adds value: "I've seen 15 similar sessions. 11 won. But the 4 that lost all had wick parade > 4. Current wick parade is 5. That's a yellow flag." This kind of reasoning connects patterns that rules don't encode.

**Possible answer**: Deterministic specialists for entry condition checking, LLM specialists for contextual reasoning about whether THIS instance of the setup is strong or weak.

### 2. How do we handle strategies with thin data?

Core portfolio (20P, 80P, BDay, EdgeFade) has decent sample sizes. But newer or rarer strategies may have <15 historical trades. Options:
- Cluster similar strategies and share data (EdgeFade + IBRetest = "IB edge cluster")
- Use domain-level calibration as prior until strategy has enough data
- Start with wider confidence intervals, narrow as data accumulates

### 3. One LoRA or multiple LoRA?

| Approach | Pros | Cons |
|---|---|---|
| **One LoRA, prompt-driven specialization** | Simple, all data in one model, one adapter to maintain | May not develop deep strategy-specific reasoning |
| **Per-strategy LoRA** | True specialization, each adapter trained on strategy-specific data | 8-16 adapters to maintain, fragmented data, vLLM multi-LoRA adds complexity |
| **Per-domain LoRA** | 5 adapters, each sees more data than per-strategy | Domain boundaries may be arbitrary |
| **One LoRA for now, re-evaluate after calibration data** | De-risks, start simple | May plateau in capability |

The "start with prompts, graduate to LoRA" approach is likely safest. We train one LoRA on ALL our data, use prompts to specialize, and only split into per-domain/per-strategy LoRA when we have evidence that prompting isn't enough.

### 4. What does the Orchestrator actually see?

If 8 strategy specialists + 5 domain advisors all report in, that's 13 structured reports. The Orchestrator LLM needs to synthesize all of them. Questions:
- Is 13 reports too much context for one LLM call?
- Should we pre-aggregate (e.g., "4 specialists say long, 1 says short, 3 inactive") before Orchestrator sees it?
- Or does the Orchestrator need the raw reasoning to make a good call?

### 5. How do we backtest this?

The current backtest engine runs strategies deterministically. To backtest agent consensus:
1. Replay historical snapshots through the full specialist pipeline
2. Compare agent consensus decisions to actual outcomes
3. Measure: did the consensus TAKE/SKIP better than any individual strategy?

This is the ultimate test: **does consensus add alpha beyond what individual strategies already produce?**

### 6. What about emerging patterns?

All approaches above are grounded in KNOWN strategies. But markets evolve. A new pattern might emerge that doesn't fit any existing strategy. Options:
- Domain advisors (Approach 2/3) can spot anomalies that don't match known strategies
- Pattern Miner can surface "hidden confluence" — conditions that correlate with wins but aren't in any strategy logic
- Periodic Opus 4.6 meta-review can analyze missed opportunities and suggest new strategy hypotheses

### 7. How do we prevent groupthink?

If all specialists are trained on the same data with the same model, they might all converge on the same wrong answer. Mitigations:
- Each specialist is constrained to its domain/strategy lens — forced diversity of perspective
- Bayesian calibration penalizes overconfident specialists
- Reserve a "Devil's Advocate" role that explicitly looks for reasons NOT to trade
- Opus 4.6 meta-review every 1-3 days checks for systematic blind spots

### 8. Cost and latency budget

```
Approach 1 (Strategy Specialists):
  8 specialist LLM calls + 1 orchestrator = 9 calls
  At ~200ms per Qwen3.5 call = ~1.8 seconds (parallel specialists → ~400ms)

Approach 4 (Bayesian):
  0 LLM calls, pure math
  ~5ms total

Approach 5 (Bayesian + Debate on ambiguous):
  70% of the time: 0 calls, ~5ms
  30% of the time: 3 calls, ~600ms
  Average: ~180ms

Current design (Advocate/Skeptic/Orchestrator):
  3 LLM calls sequential = ~600ms
```

Bayesian approaches are dramatically faster. Strategy specialist approach is slower but parallelizable. Consider: does intraday trading need sub-second decisions, or is 1-2 seconds acceptable?

---

## What This Means for 08-agent-system.md

This brainstorm does NOT replace the current architecture design. The five-stage pipeline (GATE → OBSERVE → MINE → DEBATE → DECIDE) is still valid. The question is **what fills those stages**:

| Stage | Current Design | Strategy Specialists | Domain + Strategy Hybrid |
|---|---|---|---|
| GATE | CRI check | CRI check (same) | CRI check (same) |
| OBSERVE | 4 generic observers | 8 strategy specialists | 5 domain advisors + 8 strategy specialists |
| MINE | Pattern Miner (DuckDB) | Pattern Miner (DuckDB) + per-strategy history | Pattern Miner (DuckDB) + per-strategy + per-domain |
| DEBATE | Advocate + Skeptic | Specialist reports + conflicts | Domain context + specialist votes + conflicts |
| DECIDE | Orchestrator | Orchestrator with strategy consensus | Orchestrator with Bayesian + debate if ambiguous |

The pipeline structure stays. The intelligence inside each stage evolves.

---

*This is a living brainstorm. The goal is to understand what's possible, pick the most grounded starting point, and build toward the full vision incrementally. Every approach above can be validated through backtest replay before going live.*
