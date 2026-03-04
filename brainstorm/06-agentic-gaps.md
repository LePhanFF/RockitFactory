# Agentic System Gaps & Training Data Pipeline Status

**Status**: Gap Analysis + Action Plan
**Date**: 2026-03-03
**Related**: `architecture/08-agent-system.md`, `architecture/14-bridge-deterministic-strategies.md`, `brainstorm/04-agent-specialization-and-consensus.md`, `brainstorm/05-training-data-pipeline-for-specialists.md`, `technical-design/12-training-mlops.md`, `architecture/13-backtest-data-pipeline.md`

---

## The Big Picture: What We Have vs What We Need

```
WHAT EXISTS (Solid)                    WHAT'S MISSING (Critical Path)
═══════════════════                    ═════════════════════════════

✅ 38 deterministic modules            ❌ LLM output format spec (thinking steps)
✅ Orchestrator (generates snapshots)  ❌ ROCKIT_SYSTEM_PROMPT (not written)
✅ 5 days of JSONL snapshots           ❌ 180+ days of JSONL snapshots
✅ 8 inference rules (bias/day type)   ❌ Strategy-aware LLM output
✅ Backtest engine (16 strategies)     ❌ Backtest ↔ snapshot enrichment
✅ 266 sessions of 1-min CSV data      ❌ DuckDB trade database
✅ Architecture docs (08, 12, 14)      ❌ rockit-train package (empty stub)
✅ Training stack decided (tools)      ❌ Training pair generator code
✅ Framework chosen (LangGraph)        ❌ LangGraph agent code
✅ Model chosen (Qwen3.5-30B-A3B)     ❌ LoRA fine-tuning run
                                       ❌ Evaluation/benchmark suite
                                       ❌ Agentic replay + self-learning loop
```

---

## Section 1: Agent Framework & Model Architecture

### What's Decided (Documented)

| Decision | Source | Details |
|----------|--------|---------|
| **Framework**: LangGraph | `08-agent-system.md` | Parallel fan-out for observers, state accumulation, conditional routing, streaming, checkpointing |
| **Model**: Qwen3.5-30B-A3B (MoE) | `12-training-mlops.md` | 30B total params, 3B active per token, fits on DGX Spark |
| **One model + one LoRA** | `08-agent-system.md §2` | All agents share the same model. Role differentiation via system prompts, NOT separate adapters |
| **No per-domain LoRA** | `brainstorm/04 §Q3` | Start with prompts. Graduate to per-domain LoRA ONLY if evidence shows prompting isn't enough |
| **Training: Unsloth (dev) + Axolotl (DGX)** | `12-training-mlops.md` | Unsloth for rapid iteration, Axolotl for multi-GPU production training |
| **MoE must use bf16 LoRA** | `12-training-mlops.md §4.4` | QLoRA breaks router/gate weights on MoE models. MUST use bf16, NOT 4-bit quantization during training |
| **Serving: vLLM** | `12-deployment.md` | AWQ + Marlin quantization for inference (741 tok/s on H100). Multi-LoRA for A/B testing adapter versions |
| **Local dev: Ollama** | `12-deployment.md` | GGUF Q4_K_M for Mac Mini / laptop. ~45 tok/s |

### What's NOT Built

1. **No LangGraph code** — The 5-stage pipeline (GATE → OBSERVE → MINE → DEBATE → DECIDE) is designed but not implemented. No StateGraph, no node definitions, no state schema.
2. **No agent prompts written** — Advocate, Skeptic, Orchestrator system prompts are described conceptually but not authored.
3. **No model trained** — No LoRA adapter exists. The base Qwen3.5-30B-A3B hasn't been fine-tuned on Rockit data.
4. **No evaluation suite** — No automated way to measure model quality (day_type accuracy, bias accuracy, etc.)

### Why This Is OK For Now

The agent system (LangGraph + Qwen3.5) is Phase 5 in the roadmap. It depends on:
- Phase 1: Deterministic modules ✅ (complete)
- Phase 4: Training pipeline ❌ (this is what we need to build next)

**You can't train the model until you have training data. You can't build agents until you have a trained model. The critical path is the training data pipeline.**

---

## Section 2: Where We Are With Training Data

### The Training Data Equation

```
TRAINING PAIR = {
    input:  deterministic_snapshot (from orchestrator)
    output: LLM_expected_analysis (this is what we need to define and generate)
}
```

**The input side is SOLID.** The 38 deterministic modules produce rich snapshots with:
- Premarket levels (Asia, London, overnight, prior day H/L)
- IB location (high, low, range, ATR, VWAP)
- Volume profile (current + prior day + 3-day: POC, VAH, VAL, HVN, LVN)
- TPO profile (shape, single prints, fattening, DPOC migration)
- DPOC migration (regime, velocity, compression, direction)
- Wick parade (bullish/bearish trap detection)
- FVG detection (6 timeframes + BPR + engulfed)
- Core confluences (14 precomputed boolean conditions)
- Inference rules (bias, confidence, day type, trend strength)
- CRI readiness (terrain, identity, permission)
- Playbook setup (matched playbook, rationale)
- Strategy module outputs (OR reversal, 80P globex VA, 20P, edge fade, VA edge fade, mean reversion, balance classification)

**The output side is THE GAP.** We need to define what the LLM should produce when given a snapshot.

### What Exists From RockitDataFeed (Legacy)

The RockitDataFeed repo has ~7,500 JSONL training examples across 3 format variants:
- `local-analysis/` — 58 files (original Rockit v5.x analysis)
- `local-analysis-format/` — 4 files (updated format)
- `xai-analysis/` — 43 files (Grok-generated analysis)

These are `{input: snapshot, output: analysis_text}` pairs from the previous rockit-framework system. The output is 11-section analysis (Brief, Logic, Intraday, DPOC, Globex, Profile, TPO, Thinking, Coach, HTF Coach, Rockit Audit).

**Problem:** These legacy outputs:
1. Were generated by different LLMs (Gemini, Grok) with different prompts
2. Don't have structured thinking steps
3. Don't reference our core winning strategies (OR Rev, 80P, B-Day, etc.)
4. Don't ground analysis in backtest-proven edges
5. Format is inconsistent across the 3 variants

**These are useful as a starting point but not sufficient for training a strategy-aware model.**

### What We've Generated In This Repo

- **5 days of deterministic JSONL** (2026-02-25 through 2026-03-03) at `data/json_snapshots/`
- Each day has ~78 RTH snapshots (5-min intervals from 09:30 to 16:00)
- **Input only** — these are raw deterministic snapshots with no LLM output attached

### What We Need: 180+ Days × 78 Snapshots = ~14,000 Training Pairs

```
For each of 180+ sessions:
  For each 5-min RTH interval (09:30 to 16:00):
    1. Run deterministic orchestrator → snapshot (INPUT)
    2. Generate expected LLM analysis (OUTPUT)
    3. Store as training pair in JSONL
```

---

## Section 3: The Missing Piece — LLM Expected Output Format

This is the most critical gap. The deterministic snapshot tells us WHAT the market looks like. The LLM output should tell us:
1. **What it means** (interpretation)
2. **What it sees forming** (pattern recognition)
3. **What strategies are relevant** (strategy awareness)
4. **What the reasoning chain is** (thinking steps)

### Current Inference Engine Output (Deterministic — Already Built)

```json
{
  "day_type": {"type": "P-Day (Bullish)", "timestamp": "2026-03-03 / 10:45"},
  "day_type_morph": "confirmed",
  "trend_strength": "Moderate",
  "bias": "Bullish",
  "value_acceptance": "POC 21450 above VAH 21430",
  "tpo_read": {
    "profile_signals": ["single_prints_below", "fattening_upper"],
    "dpoc_migration": "DPOC migration up 15.5 pts",
    "extreme_or_compression": "none"
  },
  "confidence": 68,
  "day_type_reasoning": [
    "IB accepted above prior VAH with 30-min hold",
    "DPOC migrating up 15.5 pts since 10:30",
    "Price in upper third with fattening"
  ],
  "one_liner": "Bullish P-Day developing with DPOC migration up"
}
```

This is good but insufficient for training. It doesn't:
- Explain WHY in multi-step reasoning
- Reference which strategies are active or relevant
- Provide coaching advice
- Connect observations to historical patterns
- Show a thinking/reasoning process the LLM should learn to mimic

### Proposed LLM Output Format (What We Need to Define)

The LLM output should have these sections (aligned with RockitUI tabs):

```json
{
  "thinking": {
    "step_1_market_context": "Market opened below prior day's value area...",
    "step_2_structure_read": "IB formed narrow (45pts, below average 65pts)...",
    "step_3_flow_assessment": "DPOC migrating down, wick parade 3 bearish...",
    "step_4_level_analysis": "Key resistance: prior POC 21450, prior VAH 21480...",
    "step_5_pattern_match": "This structure resembles a Balance day...",
    "step_6_strategy_check": "Active strategy signals: 80P Rule SHORT triggered at 10:15...",
    "step_7_risk_assessment": "Risk: trend strength is Weak, could morph to Neutral...",
    "step_8_confluence_score": "Confluences: 4 bearish, 1 bullish, 2 neutral...",
    "step_9_synthesis": "Moderate bearish conviction, 80P setup aligns with structure..."
  },

  "brief": "Bearish structure developing. Price opened below prior VA and accepted lower. 80P Rule SHORT triggered — price re-entered VA from above, 30-min close confirmed acceptance. DPOC migrating down supports continuation to opposite VA edge.",

  "day_type": {
    "classification": "Balance → potential P-Day (Bearish)",
    "confidence": 62,
    "reasoning": "Narrow IB (45pts) initially suggested Balance, but extension below IB low with DPOC migration shifts toward P-Day bearish. Monitoring for confirmation above 0.5x IB extension."
  },

  "intraday": {
    "ib_analysis": "IB range 45pts (narrow, suggesting rotational day). IB low tested twice with second test breaking. Current extension 0.3x IB range below.",
    "price_action": "Price opened at 21460, dropped to IB low 21415, bounced to 21445, then broke below 21410. Selling pressure increasing post-IB.",
    "key_observation": "The IB extension is happening on increasing volume — this looks like genuine directional interest, not just a probe."
  },

  "dpoc_analysis": {
    "migration": "DPOC migrated down 12 pts from 21445 to 21433 since 10:30. Regime: trending_fading_momentum — still directional but velocity slowing.",
    "interpretation": "DPOC tracking the selloff confirms it's not just a liquidity sweep. The fading momentum suggests we may see a pause near the next support level before continuation."
  },

  "volume_profile": {
    "current_session": "Developing POC at 21430, value building in lower half. Single prints above 21455 (trapped longs from opening bounce).",
    "prior_reference": "Prior day POC 21450, VAH 21480, VAL 21400. Prior 3-day POC 21440. Current price trading below POC — bearish relative to value.",
    "hvn_lvn": "HVN at 21430 (current acceptance). LVN at 21410 (fast move through, potential magnet if revisited)."
  },

  "tpo_profile": {
    "shape": "Elongated P-shape forming with value building in lower third. Single prints above 21455 from A-period.",
    "fattening": "Lower TPOs fattening — price spending more time at lower levels. Acceptance of lower prices.",
    "dpoc_location": "DPOC in lower 30% of range — bearish positioning."
  },

  "globex_analysis": {
    "overnight": "Overnight range 21430-21490. Current price below overnight low — bearish.",
    "gap_status": "Opened within prior VA but near VAH. Gap-down open relative to overnight range.",
    "va_relationship": "Price opened inside prior VA, now trading near VAL 21400. 80P setup triggered."
  },

  "strategy_commentary": {
    "active_signals": [
      {
        "strategy": "80P Rule",
        "signal": "SHORT",
        "entry": 21445,
        "stop": 21490,
        "target": 21355,
        "status": "TRIGGERED at 10:15",
        "context": "Price opened above prior VAH, re-entered VA with 30-min acceptance close at 21445. This is Model A (acceptance entry). VA width 80pts exceeds 25pt minimum. Stop at VAH + 10pt buffer."
      }
    ],
    "potential_setups": [
      {
        "strategy": "Edge Fade",
        "status": "MONITORING",
        "note": "If IB extension stalls at 0.5x and reverses, could trigger Edge Fade setup after 10:30."
      }
    ],
    "inactive": "OR Reversal: window closed (past 10:15). 20P Rule: no IB extension breakout above. Mean Reversion VWAP: price below VWAP, no reversal signal."
  },

  "coach": {
    "trade_plan": "80P SHORT is the primary setup. Entry at acceptance close 21445. Stop 21490 (45pts risk). Target 21355 (90pts reward, 2R). This aligns with DPOC migration and volume acceptance lower.",
    "risk_management": "This is a 2R trade with VA-edge stop. Do NOT move stop to candle-based level — research shows candle stops destroy WR (5-14% vs 58-66% with VA stops).",
    "what_to_watch": "If price reclaims 21460 (above DPOC), the setup is invalidated — DPOC migrating back up would flip the regime. Also watch for 80P opposite VA target at 21400 (prior VAL) — this is the natural magnet."
  },

  "htf_coach": {
    "weekly_structure": "Weekly in pullback from 21800 high. Current area (21400-21500) is the weekly value area. A sustained break below 21400 would shift weekly structure bearish.",
    "daily_context": "Yesterday was a wide-range trend day down (624pt range). Today's narrow open suggests digestion. The 80P trade is consistent with continuation of the daily bearish theme.",
    "multi_day_thesis": "Until price reclaims 21600, the path of least resistance is lower. Today's 80P SHORT aligns with the multi-day bearish auction."
  },

  "audit": {
    "confidence_check": "Confidence 62% is moderate. Main uncertainty: narrow IB could indicate Balance day, not P-Day. The DPOC migration is the tiebreaker — it confirms directional interest.",
    "what_could_go_wrong": "If this is actually a Balance day, the IB extension will fail and price rotates back to VWAP. This would trigger the Edge Fade setup instead.",
    "data_quality": "All 38 modules returned valid data. Volume profile has 3 TPO periods of data — thin but sufficient. FVG detection shows no major daily/4h gaps nearby."
  }
}
```

### Why Strategy Awareness Matters

The user's critical insight: **the LLM needs to know about our core winning strategies to make useful comments.**

Current inference engine says: "Bullish, 68% confidence, P-Day forming"
What we actually need: "80P Rule SHORT triggered. This has 42% WR in backtest with 2.57 PF under Model B. DPOC migration and VA acceptance support the setup. Stop at VAH + 10pt is the research-validated stop — do NOT use candle-based stops."

**The LLM should be trained to:**
1. Recognize when a strategy's conditions are present in the snapshot
2. Comment on the specific strategy (by name) and its backtest performance
3. Note whether current conditions match the strategy's winning or losing profile
4. Provide coaching advice grounded in the research studies
5. Warn about known failure modes (e.g., "candle-based stops kill 80P WR")

### Strategy Knowledge The LLM Needs

| Strategy | WR | PF | Key Knowledge |
|----------|----|----|---------------|
| Opening Range Reversal | 64.4% | 2.96 | OR_MINUTES=15, dual sweep detection, retest zone = 50% of swept level to VA edge, ATR-based stop |
| OR Acceptance | 59.9% | 1.46 | 3x5-min consecutive close acceptance, entry at acceptance close |
| 80P Rule | 42.3% | 1.74 | Model A (acceptance), Model B (limit 50% VA, best $/mo), Model C (100% retest, 65.7% WR). VA-edge stops ONLY. VA width >= 25pt. No entry after 13:00 |
| B-Day | 46.4% | 1.46 | Balance day fade. IB range narrow. Watch for B-Day → Trend morph (stop trigger) |
| Mean Reversion VWAP | 42.6% | 0.91 | Currently losing (-$6,925). Needs investigation. LLM should flag this as unreliable. |
| 20P IB Extension | disabled | — | Research says cutoff 13:00 (not 14:00). Needs source port. |

---

## Section 4: The Training Data Generation Plan

### Step 1: Generate Deterministic Snapshots for 180+ Days

**What we have:** 5 days (2026-02-25 through 2026-03-03)
**What we need:** 180+ days (minimum for reliable training)
**How:** Run `generate_deterministic_snapshots.py` over all 266 sessions in the CSV data

```bash
# Run for all available sessions (266 sessions × ~78 RTH snapshots = ~20,000+)
uv run python scripts/generate_deterministic_snapshots.py \
    --csv-dir data/sessions/ \
    --output-dir data/json_snapshots/ \
    --rth-only \
    --all-dates
```

**Estimated time:** 266 sessions × 78 snapshots × 1.6s = ~5.8 hours
**Storage:** ~20,000 JSONL entries, ~500MB

### Step 2: Define the LLM Output Schema + ROCKIT_SYSTEM_PROMPT

**This is the critical design task.** We need:

1. **ROCKIT_SYSTEM_PROMPT** — System prompt that tells the LLM:
   - Who it is (Rockit market analyst, Dalton Market Profile expert)
   - What framework it uses (Auction Market Theory, ICT concepts, order flow)
   - What strategies it knows (OR Rev, 80P, B-Day, etc. with backtest stats)
   - How to structure its output (thinking steps → sections → strategy commentary)
   - What NOT to do (don't hallucinate levels, don't trade without strategy signal)

2. **Output JSON schema** — Structured sections matching RockitUI tabs:
   - `thinking` (9-step reasoning chain)
   - `brief`, `day_type`, `intraday`, `dpoc_analysis`, `volume_profile`, `tpo_profile`, `globex_analysis`
   - `strategy_commentary` (NEW — references active strategies)
   - `coach`, `htf_coach`, `audit`

3. **Quality criteria** — What makes a good vs bad output:
   - All levels mentioned must exist in the snapshot (grounded)
   - Strategy comments must match actual backtest results
   - Thinking steps must flow logically from data to conclusion
   - Confidence must be calibrated (not always 70-80%)

### Step 3: Generate LLM Expected Outputs

**The chicken-and-egg problem:** To train the LLM, we need expected outputs. To generate expected outputs, we need... an LLM.

**Solution: Use a frontier model (Opus or Gemini) to generate initial training outputs.**

```
For each deterministic snapshot:
  1. Build prompt: ROCKIT_SYSTEM_PROMPT + snapshot JSON
  2. Send to Opus 4.6 / Gemini with instruction:
     "Given this market snapshot, generate a structured analysis
      following the output schema. Reference relevant strategies
      from the strategy knowledge base."
  3. Validate output against snapshot (are levels grounded? are strategies correct?)
  4. Store validated pair as training example
```

**Cost estimate:** ~20,000 snapshots × ~$0.03/call = ~$600 for Opus-generated training data

**Quality control:**
- Automated validation: schema compliance, level grounding, strategy accuracy
- Manual review: sample 100 outputs, score quality, iterate on prompt
- Cross-validate: compare Opus outputs to legacy RockitDataFeed analysis

### Step 4: Enrich With Backtest Outcomes (Concurrent)

**While generating snapshots and outputs, ALSO run the backtest engine over the same sessions.** At each signal point, capture:

```json
{
  "snapshot": { /* deterministic snapshot at signal time */ },
  "signal": {
    "strategy": "80P Rule",
    "direction": "SHORT",
    "entry": 21445,
    "stop": 21490,
    "target": 21355
  },
  "outcome": {
    "result": "WIN",
    "pnl": 1800,
    "exit_reason": "TARGET",
    "bars_held": 45,
    "mfe": 95,  // max favorable excursion in points
    "mae": 12   // max adverse excursion in points
  }
}
```

**Store in DuckDB** with indexes on strategy, day_type, direction, outcome. This becomes:
- Bayesian calibration data (factor → outcome tables)
- Agent context data (Historian queries)
- Strategy commentary grounding (LLM can reference actual WR under similar conditions)

### Step 5: Validate and Benchmark

**Holdout set:** Reserve 50 sessions (~3,900 snapshots) for evaluation:
- 10 Trend days, 10 P-Days, 10 B-Days, 10 Neutral, 10 edge cases
- NEVER train on these sessions

**Benchmark metrics:**
- `day_type_accuracy` — Does the LLM classify the day type correctly?
- `bias_accuracy` — Does the LLM bias match the deterministic engine?
- `confidence_mae` — How close is the LLM confidence to actual outcome?
- `section_completeness` — Are all 11 sections present and valid?
- `strategy_accuracy` — Does the LLM correctly identify active strategies?
- `level_grounding` — Are all referenced levels actually in the snapshot?
- `deterministic_agreement` — Does the LLM agree with the inference engine?

**LLM-as-judge:** Opus 4.6 scores each output on analysis quality (0-100)

---

## Section 5: What's In the Brainstorm Docs vs What's Not

### Covered By Existing Docs

| Topic | Document | Status |
|-------|----------|--------|
| Agent framework (LangGraph, 5-stage pipeline) | `architecture/08-agent-system.md` | Designed, not built |
| Agent roles (Advocate/Skeptic/Orchestrator) | `architecture/08-agent-system.md` | Designed, not built |
| One model + one LoRA decision | `architecture/08-agent-system.md §2` | Decided |
| Training stack (Unsloth/Axolotl/W&B/vLLM) | `technical-design/12-training-mlops.md` | Decided, not configured |
| MoE LoRA requirements (bf16, no QLoRA) | `technical-design/12-training-mlops.md §4.4` | Documented |
| vLLM multi-LoRA serving | `architecture/03-pipeline-mlops.md` | Documented |
| DGX/Spark deployment | `architecture/12-deployment.md` | Documented |
| Training data pipeline (3-stage) | `brainstorm/05` | Designed, not built |
| Agent specialization approaches (5 options) | `brainstorm/04` | Explored, Approach 1 recommended |
| Bayesian pre-filter | `architecture/14` (newly added) | Designed |
| Signal-triggered agents (Approach E) | `architecture/14` | Designed |
| Trade database + forensics | `architecture/13` | Designed, not built |
| Training pipeline roadmap | `roadmap/05-training-pipeline.md` | 7 tasks, all unchecked |

### NOT Covered (Gaps)

| Gap | Impact | Where It Should Live |
|-----|--------|---------------------|
| **LLM output schema with thinking steps** | Can't generate training data without this | NEW: `technical-design/15-inference-training-format.md` |
| **ROCKIT_SYSTEM_PROMPT** | Can't train or evaluate without the system prompt | NEW: `configs/prompts/rockit_system_v1.md` |
| **Strategy knowledge base for LLM** | LLM won't know about our strategies | Part of system prompt + `strategy_commentary` output section |
| **Enhanced reasoning module (9-step)** | Referenced in `10-deterministic-modules.md` but never built | `rockit-core/deterministic/modules/enhanced_reasoning.py` |
| **Training pair generator code** | Can't create datasets | `rockit-train/dataset.py` |
| **Bulk snapshot generation for 266 sessions** | Only 5 days exist | Run existing script over all CSV data |
| **DuckDB schema for trades + snapshots** | Agents have no historical context to query | `rockit-core/db/schema.sql` or Python schema |
| **Outcome labeling module** | Can't enrich training data with WIN/LOSS | Part of backtest engine modification |
| **Evaluation gates** | No automated quality checks for trained models | `rockit-train/evaluate.py` |
| **Cost estimate for Opus training data generation** | Need budget approval | ~$600 for 20K snapshots |
| **Agentic replay engine** | Can't validate that agents beat mechanical baseline | `rockit-core/replay/agent_replay.py` |
| **Opus session reviewer** | Can't close the self-learning loop | `rockit-core/replay/opus_reviewer.py` |
| **Replay database schema** | Can't store debate logs + outcomes | DuckDB `replay_sessions` table |
| **Training data quality validator** | Can't ensure training data is correct before training | `rockit-train/validate.py` |
| **Model evaluation benchmark suite** | Can't measure if model learned correctly | `rockit-train/evaluate.py` + `configs/evaluation/` |
| **Model version comparison tool** | Can't compare v001 vs v002 objectively | `rockit-train/compare.py` |
| **Strategy knowledge probes** | Can't test if model knows strategy mechanics | `configs/evaluation/strategy_probes.yaml` |
| **Production output monitoring** | Can't detect model quality drift | `rockit-train/daily_review.py` + W&B |

---

## Section 6: Recommended Next Steps (Priority Order)

### 1. Generate 180+ Days of Deterministic Snapshots (Blocking Everything)

Run the existing `generate_deterministic_snapshots.py` over all 266 sessions. This is the input side of training and can run overnight.

**Depends on:** CSV data in `data/sessions/` (need to merge from Google Drive first)
**Produces:** `data/json_snapshots/deterministic_{date}.jsonl` for each session

### 2. Define LLM Output Format + Write System Prompt

Create `technical-design/15-inference-training-format.md` specifying:
- The thinking step structure (9 steps)
- All output sections (aligned with RockitUI tabs)
- Strategy commentary format (NEW section)
- Quality criteria
- ROCKIT_SYSTEM_PROMPT v1

This is a design task — needs your input on what the LLM should say about strategies.

### 3. Generate Training Outputs Using Frontier Model

Use Opus 4.6 to generate expected LLM outputs for each snapshot:
- Build the prompt (system prompt + snapshot → expected analysis)
- Run against 180+ days of snapshots
- Validate schema compliance and level grounding
- Manual review sample for quality

### 4. Concurrent: Enrich Backtest Trades With Snapshots

Modify the backtest engine to capture the deterministic snapshot at each signal point. Store in DuckDB alongside the trade outcome. This runs concurrently with Step 3.

### 5. Build rockit-train Dataset Module

Port `generate_training_data_with_synthetic_output.py` into `rockit-train/dataset.py`:
- Load raw JSONL snapshots + Opus-generated outputs
- Format as HuggingFace chat template
- Temporal split (train/val/test by date)
- Quality filtering
- Output manifest

### 6. First LoRA Training Run

- Configure Unsloth for local dev run (small subset)
- Validate training loop works
- Evaluate against holdout set
- If metrics pass, scale to full dataset on DGX Spark with Axolotl

### 7. Build Agent Pipeline (After Model Exists)

Only after we have a trained model:
- Implement LangGraph StateGraph with 5-stage pipeline
- Write Advocate/Skeptic/Orchestrator prompts
- Wire to vLLM serving

### 8. Agentic Replay + Self-Learning Loop (The Proof)

After agent pipeline is built:
- Replay 266 sessions through full pipeline (strategies → Bayesian → agents → decisions)
- Log every debate with LangGraph checkpointing
- Opus reviews each session, identifies error patterns
- Apply prompt/calibration improvements
- Re-run on holdout set, compare to mechanical baseline
- Iterate 5-10 cycles until convergence
- **Success metric: agents beat 55% WR mechanical baseline on holdout**

---

## Section 7: The Training Loop (End-to-End)

```
CSV Data (266 sessions)
    │
    ├──→ Deterministic Orchestrator ──→ Snapshot JSONL (INPUT)
    │        (38 modules)                    │
    │                                        ▼
    │                              Frontier Model (Opus 4.6)
    │                              + ROCKIT_SYSTEM_PROMPT
    │                              + Strategy Knowledge Base
    │                                        │
    │                                        ▼
    │                              LLM Analysis (OUTPUT)
    │                              - thinking steps (9 step)
    │                              - 11 analysis sections
    │                              - strategy commentary
    │                              - coach / htf coach
    │                                        │
    │                                        ▼
    │                              Training Pair: {input, output}
    │                                        │
    ├──→ Backtest Engine ─────────→ Trade Outcomes ──→ DuckDB
    │    (signals + outcomes)       (enrichment)
    │                                        │
    │                                        ▼
    │                              Enriched Training Data
    │                              {input, output, trade_outcome}
    │                                        │
    │                                        ▼
    │                              DatasetBuilder
    │                              - schema validation
    │                              - quality filtering
    │                              - temporal split
    │                              - chat template format
    │                                        │
    │                                        ▼
    │                              train.jsonl / val.jsonl / test.jsonl
    │                                        │
    │                                        ▼
    │                              LoRA Fine-Tuning
    │                              Unsloth (dev) → Axolotl (DGX)
    │                                        │
    │                                        ▼
    │                              Evaluation Gates
    │                              - day_type_accuracy
    │                              - bias_accuracy
    │                              - strategy_accuracy (NEW)
    │                              - section_completeness
    │                              - LLM-as-judge (Opus)
    │                                        │
    │                              ┌─────────┴──────────┐
    │                              │                     │
    │                           PASS                   FAIL
    │                              │                     │
    │                              ▼                     ▼
    │                        Register Model         Iterate on:
    │                        adapters/v001          - system prompt
    │                                               - training data
    │                                               - quality filters
    │
    └──→ Daily Reflection (Opus) ──→ Recalibrate / Find New Patterns
```

---

## Section 8: Agentic Backtesting + Self-Learning Loop

> **The Vision:** Replay historical markets through the full agent pipeline — strategies fire signals, agents debate them using the trained model, Opus reviews each debate session. Agents learn from their mistakes, improve their prompts and calibration, and ultimately BEAT the mechanical baseline. This is the system's proof-of-value: if agents can't improve on a 55% WR mechanical portfolio, they have no reason to exist.

### Why This Is Possible (Not Just a Dream)

Every component needed either exists or is on the critical path:

| Component | Status | Role in Replay |
|-----------|--------|---------------|
| 1-min CSV data (266 sessions) | ✅ Exists | Market replay feed |
| Backtest engine (bar-by-bar) | ✅ Exists | Drives the 1-min loop |
| Strategy signal detection | ✅ Exists | Fires signals at correct historical moments |
| Deterministic orchestrator | ✅ Exists | Generates snapshot at signal time |
| DuckDB trade database | ❌ Build in Step 4 | Stores outcomes + historical context for Historian queries |
| Trained Qwen3.5 model | ❌ Build in Steps 1-6 | Powers Advocate/Skeptic/Orchestrator |
| LangGraph pipeline | ❌ Build in Step 7 | Orchestrates the debate |
| LangGraph checkpointing | ✅ Built into LangGraph | Saves + replays every agent state transition |
| Opus reviewer | ✅ Available via API | Reviews agent behavior post-session |

**LangGraph checkpointing is the key enabler.** It saves the full state of every node transition — meaning we can:
- Replay any debate from any historical signal
- Inspect what the Advocate said, what the Skeptic challenged, what the Orchestrator decided
- Compare the agent's decision (TAKE/SKIP) to the actual trade outcome
- Build a dataset of (debate, decision, outcome) triples

### How It Works: The Replay Engine

```
Historical Session Replay (one session at a time)
══════════════════════════════════════════════════

Step 1: Load session CSV (1-min bars for date X)
Step 2: Initialize strategies with session context (IB, premarket, VA levels)
Step 3: Run bar-by-bar loop:

    For each 1-min bar:
    ┌─────────────────────────────────────────────────────────────────┐
    │  strategy.on_bar(bar) for each active strategy                  │
    │                                                                 │
    │  if signal emitted:                                             │
    │    ├── Generate deterministic snapshot at this moment            │
    │    ├── Query DuckDB for similar historical sessions              │
    │    ├── Run Bayesian scorer → get probability P                   │
    │    │                                                             │
    │    ├── If P in ambiguous zone (35-70%):                          │
    │    │   ├── Run full agent debate (LangGraph pipeline)            │
    │    │   │   ├── Advocate builds case (with snapshot + history)    │
    │    │   │   ├── Skeptic challenges (with losing-subset data)     │
    │    │   │   └── Orchestrator decides: TAKE / SKIP / REDUCE_SIZE  │
    │    │   │                                                         │
    │    │   └── CHECKPOINT: Save full debate state                    │
    │    │                                                             │
    │    ├── Else: auto-decide (fast path), log reasoning              │
    │    │                                                             │
    │    └── Record: {signal, snapshot, debate_log, decision, P}       │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘

Step 4: After session completes, attach actual outcomes to each decision:
    {signal, snapshot, debate_log, decision, P, outcome: WIN/LOSS, pnl}

Step 5: Store everything in DuckDB (replay_sessions table)
```

### The Self-Learning Loop

```
                    ┌─────────────────────────────────┐
                    │                                   │
                    ▼                                   │
            Replay 266 Sessions                         │
            Through Agent Pipeline                      │
                    │                                   │
                    ▼                                   │
            Log Every Debate                            │
            - Advocate reasoning                        │
            - Skeptic challenges                        │
            - Orchestrator decision                     │
            - Bayesian probability chain                │
            - Actual outcome (WIN/LOSS/PnL)             │
                    │                                   │
                    ▼                                   │
            Opus Reviews Each Session                   │
            ─────────────────────────                   │
            For each session:                           │
            1. Which agent decisions were CORRECT?      │
               (TAKE + WIN, or SKIP + would-have-lost)  │
            2. Which were WRONG?                        │
               (TAKE + LOSS, or SKIP + would-have-won)  │
            3. WHY was the reasoning flawed?            │
               - Did Advocate miss a risk factor?       │
               - Did Skeptic raise a false alarm?       │
               - Did Orchestrator weigh evidence wrong? │
            4. What PATTERN do the errors share?        │
               - "Advocate consistently overweights     │
                  DPOC migration and ignores wick       │
                  parade > 4"                           │
               - "Skeptic too aggressive on HTF         │
                  bearish context — kills 60% of        │
                  valid intraday longs"                 │
               - "Orchestrator takes every signal       │
                  when Bayesian P > 60% — threshold     │
                  should be 65%"                        │
                    │                                   │
                    ▼                                   │
            Generate Improvement Report                 │
            ───────────────────────────                 │
            - Specific prompt adjustments               │
              (e.g., "Add to Skeptic: when wick         │
               parade > 4, weight this as HIGH risk")   │
            - Bayesian threshold adjustments            │
              (e.g., "Move fast-path TAKE from          │
               P>70% to P>65%")                         │
            - Calibration table updates                 │
              (e.g., "OR Rev on Trend days: adjust      │
               base rate from 64% to 58%")              │
                    │                                   │
                    ▼                                   │
            Apply Improvements                          │
            (version-controlled, committed to git)      │
                    │                                   │
                    ▼                                   │
            Re-Run Replay (Holdout Set ONLY)            │
            ──────────────────────────────              │
            Compare metrics:                            │
            - Mechanical baseline (all signals taken)   │
            - Agent v1 (before improvements)            │
            - Agent v2 (after improvements)             │
                    │                                   │
                    ├── v2 beats v1 on holdout?         │
                    │   YES → adopt v2, continue loop ──┘
                    │   NO  → revert, analyze why
                    │
                    └── v2 beats mechanical baseline?
                        YES → agents are adding value
                        NO  → agents need more iteration
                              or the strategy portfolio
                              is already near-optimal
```

### What Opus Reviews (Structured, Not Free-Form)

For each replayed session, Opus receives:

```json
{
  "session_date": "2025-08-15",
  "session_summary": {
    "day_type": "Balance → P-Day morph",
    "signals_fired": 2,
    "agent_decisions": [
      {
        "signal": "80P SHORT @ 21445",
        "bayesian_P": 0.58,
        "debate_summary": {
          "advocate": "VA acceptance confirmed, DPOC migrating down, prior POC as target...",
          "skeptic": "Wick parade = 5 bearish (high), trend strength Weak, could morph to Neutral...",
          "orchestrator_decision": "TAKE with REDUCE_SIZE"
        },
        "actual_outcome": "LOSS, -$1,250, stopped out",
        "failure_mode": "REGIME_SHIFT (B-Day → P-Day morph)"
      },
      {
        "signal": "OR Rev LONG @ 21380",
        "bayesian_P": 0.72,
        "debate_summary": "AUTO-TAKE (fast path, P > 70%)",
        "actual_outcome": "WIN, +$2,800, target hit",
        "failure_mode": null
      }
    ],
    "session_pnl": "+$1,550",
    "mechanical_pnl": "+$1,550"
  }
}
```

Opus produces a structured review:

```json
{
  "session_grade": "B",
  "correct_decisions": [
    "OR Rev LONG auto-take was correct — high Bayesian P + clean outcome"
  ],
  "incorrect_decisions": [
    {
      "signal": "80P SHORT",
      "error_type": "MISSED_WARNING_SIGN",
      "analysis": "Skeptic correctly flagged wick parade = 5 and Weak trend strength. These are the exact conditions that predict 80P losses in backtest (25% WR when wick parade > 4). The Orchestrator should have weighed Skeptic's evidence more heavily.",
      "suggested_fix": "Increase Skeptic's weight when wick parade > 4. Consider adding hard rule: SKIP any 80P signal when wick parade > 4."
    }
  ],
  "pattern_observations": [
    "This is the 3rd session where 80P lost with wick parade > 4. This is a reliable filter."
  ],
  "prompt_adjustments": [
    {
      "agent": "Orchestrator",
      "current": "Weigh Advocate and Skeptic evidence equally",
      "proposed": "When Skeptic cites wick parade > 4 for mean reversion strategies (80P, Edge Fade), elevate Skeptic's weight to 2x"
    }
  ],
  "calibration_adjustments": [
    {
      "strategy": "80P Rule",
      "factor": "wick_parade_bearish > 4",
      "current_adjustment": "-5% WR",
      "proposed_adjustment": "-15% WR",
      "evidence": "3/3 losses in replay when this condition was present"
    }
  ]
}
```

### Guardrails Against Overfitting

This is the most important part. Self-learning without guardrails = curve-fitting to historical data.

**Guardrail 1: Train/Holdout Split**
```
266 sessions split:
  - 210 sessions (80%) → Agent learns on these (replay + review)
  - 56 sessions (20%) → NEVER used for learning, only for validation

  Holdout is balanced: ~11 Trend, ~11 P-Day, ~11 B-Day, ~11 Neutral, ~12 edge cases
  Holdout is date-stratified: mix of recent and older sessions
```

**Guardrail 2: Multi-Metric Gates (Not Just WR)**
```
Agent must beat mechanical baseline on ALL of:
  ✓ Win Rate (higher)
  ✓ Profit Factor (higher)
  ✓ Max Drawdown (lower or equal)
  ✓ Net PnL (higher)
  ✓ Sharpe Ratio (higher)

If agent improves WR but worsens PF → REJECT (skipping winners, not just losers)
If agent improves PF but worsens DD → REJECT (taking bigger risks on fewer trades)
```

**Guardrail 3: Minimum Sample Size**
```
No calibration adjustment accepted with fewer than 10 supporting examples.
"3/3 losses when wick parade > 4" is suggestive but NOT sufficient.
Wait until we have 10+ instances before hard-coding a filter.
```

**Guardrail 4: Version Control + Rollback**
```
Every prompt change, calibration update, and threshold adjustment:
  - Committed to git with the metrics that motivated it
  - Tagged with the replay run that produced it
  - Includes rollback instructions

If holdout performance degrades after N iterations:
  - Auto-revert to last known-good version
  - Flag for human review
```

**Guardrail 5: Accept Losses**
```
The goal is NOT 100% WR. The goal is:
  - Mechanical: 55% WR, 1.91 PF, 548 trades
  - Agents:     60% WR, 2.1+ PF, ~400 trades (fewer but better)

Agents WILL lose trades. A 60% WR means 40% losses.
The improvement comes from WHICH losses are avoided:
  - Skip regime-shift losses (80P on morphing days)
  - Skip counter-trend signals (long on strong bear days)
  - Skip low-confluence signals (only 1 supporting factor)
  - KEEP clean losses (correct setup, correct logic, just lost)

A clean loss with correct reasoning is NOT a bug — it's variance.
Opus reviewer should mark "CLEAN_LOSS" and NOT suggest changes.
```

**Guardrail 6: Convergence Detection**
```
After N iterations, if improvements plateau:
  - WR improvement < 0.5% per iteration for 3 consecutive iterations
  - → STOP iterating. The agent has converged.
  - This is healthy — it means the strategy portfolio is near-optimal
    and agents can't squeeze much more out.
  - Don't keep tweaking prompts chasing 0.1% improvements — that's overfitting.
```

### The Mediocre Strategy Experiment

The most exciting validation test:

```
Take Mean Reversion VWAP (currently -$6,925 net, 42.6% WR, 0.91 PF).

Hypothesis: This strategy has a slight edge in certain conditions
(maybe Balance days with narrow IB). The agents can learn to
SKIP the losing conditions and only TAKE the subset where it works.

Replay:
  1. Run Mean Reversion VWAP through all 266 sessions → ~155 signals
  2. For each signal, run agent debate
  3. Agent decides: TAKE or SKIP for each signal
  4. Compare:
     - Mechanical: 155 trades, 42.6% WR, -$6,925 net
     - Agent-filtered: ??? trades, ???% WR, ??? net

Expected outcomes:
  a) Agents turn it profitable → HUGE validation of the architecture
  b) Agents can't fix it → strategy has no recoverable edge, drop it
  c) Agents improve WR but not PF → agents are too conservative
```

If outcome (a) happens, it proves agents can extract value from mediocre strategies — which means adding more strategies to the portfolio (even imperfect ones) becomes viable because agents will filter them.

### Cost and Compute Estimate

```
Full 266-session replay:
  - Signals per session: ~2 average (1-3 range)
  - Total signals: ~530
  - Bayesian fast-path (70%): ~370 signals → 0 LLM calls
  - Agent debates (30%): ~160 signals × 3 agent calls = ~480 LLM calls
  - Per call: ~500 tokens in, ~300 tokens out @ Qwen3.5 local = FREE (on DGX)
  - Or via vLLM API: ~$0.01/call = ~$5 total

Opus session review:
  - 266 sessions × ~$0.10/review = ~$27
  - Or: batch into 10-session reviews = ~$70 (more context per review)

Total per iteration: ~$30-75 (trivial)
Multiple iterations (5-10 cycles): ~$150-750

Compute time:
  - Replay + debate: ~160 debates × 3s/debate = ~8 minutes
  - Opus review: ~266 sessions × 15s/review = ~1 hour
  - Total per iteration: ~1.5 hours
  - 10 iterations: ~15 hours (can run overnight)
```

### What This Produces (The Gold)

After 5-10 self-learning iterations:

1. **Tuned agent prompts** — Advocate, Skeptic, Orchestrator prompts refined by real performance data
2. **Calibrated Bayesian tables** — Factor → outcome probabilities tuned to actual replay results
3. **Optimal thresholds** — Fast-path TAKE/SKIP boundaries optimized
4. **Strategy-specific insights** — "80P works best when DPOC trending + wick parade < 3 + VA width > 50pt"
5. **Portfolio filter** — Which strategies benefit most from agent overlay vs which are already near-optimal
6. **Confidence** — Quantified proof that agents beat mechanical baseline on holdout data

**This dataset of (debate, decision, outcome, review) also becomes TRAINING DATA for the next LoRA iteration.** The self-learning loop feeds itself:

```
Iteration 1: Base model + prompts → replay → Opus review → better prompts
Iteration 2: Base model + better prompts → replay → Opus review → even better prompts
...
Iteration N: Prompts converge → generate new training data from good debates
             → retrain LoRA on this data → model itself improves
             → repeat from Iteration 1 with better model
```

This is the outer loop: prompt tuning is the inner loop (fast, cheap). Model retraining is the outer loop (slower, more expensive, but compounds gains).

---

## Section 9: LLM Evaluation & Benchmarking Framework

> **The Problem:** After we train the LoRA, how do we know if the model actually learned what we wanted? How do we measure if version v002 is better than v001? How do we benchmark training data quality BEFORE training, and output quality AFTER?

### Three Layers of Evaluation

```
Layer 1: TRAINING DATA QUALITY        (before training — is the data good?)
Layer 2: MODEL CAPABILITY              (after training — did the model learn?)
Layer 3: PRODUCTION OUTPUT QUALITY     (in use — is the output useful?)
```

### Layer 1: Training Data Quality Benchmarks

Before we even train, we need to validate that our training data (deterministic input + Opus-generated output) is high quality.

**Automated Checks (run on every training pair):**

| Check | What It Validates | Pass Criteria |
|-------|-------------------|---------------|
| Schema compliance | All required sections present | 11/11 sections |
| Level grounding | Every price level mentioned exists in snapshot | 100% grounded |
| Strategy accuracy | Strategy references match actual signal status | Correct strategy name, direction, levels |
| Temporal consistency | Analysis matches the time of day (don't reference IB at 09:30) | No future-looking statements |
| Bias consistency | LLM bias aligns with deterministic inference bias | Within 1 level (e.g., Bullish vs Very Bullish OK, Bullish vs Bearish = fail) |
| Thinking step coherence | Each step builds on the previous | No contradictions between steps |
| No hallucination | No invented indicators, fake levels, or made-up history | Zero tolerance |

**Statistical Checks (run on the full dataset):**

| Check | What It Validates | Pass Criteria |
|-------|-------------------|---------------|
| Bias distribution | Outputs aren't all "Bullish" or all "Flat" | Matches historical day-type distribution |
| Confidence calibration | When output says 70% confidence, actual WR should be ~70% | Calibration error < 10% |
| Strategy mention rate | OR Rev mentioned on days it actually fired | Recall > 90% |
| Section length distribution | No sections that are always 1 sentence or always 500 words | Variance within reasonable bounds |
| Day-type coverage | All 6 day types represented with sufficient examples | Min 20 examples per day type |

**LLM-as-Judge (Opus scores a sample):**

Sample 200 training pairs (stratified by day type). For each, Opus rates:
- **Analytical depth** (0-10): Does the analysis go beyond restating numbers?
- **Strategy grounding** (0-10): Are strategy references accurate and insightful?
- **Actionability** (0-10): Could a trader act on this analysis?
- **Thinking quality** (0-10): Do the 9 reasoning steps flow logically?
- **Overall score** (0-100): Composite quality

**Target:** Mean overall score > 75. Any pair scoring < 50 gets regenerated.

### Layer 2: Model Capability Benchmarks (Post-Training)

After LoRA fine-tuning, evaluate the model against a holdout set to measure what it learned.

**Test Suite: 7 Capability Dimensions**

```
1. DAY TYPE CLASSIFICATION
   ─────────────────────────
   Input:  50 holdout snapshots (10 per day type)
   Task:   Model classifies day type
   Metric: Accuracy (% correct)
   Target: > 75% accuracy
   Baseline: Deterministic inference engine accuracy (compare)

2. BIAS DIRECTION
   ────────────────
   Input:  Same 50 holdout snapshots
   Task:   Model determines bias (7-level scale)
   Metric: Accuracy within ±1 level
   Target: > 80% within ±1
   Baseline: Deterministic engine

3. STRATEGY RECOGNITION
   ──────────────────────
   Input:  30 snapshots where specific strategies fired
           + 20 snapshots where NO strategy fired
   Task:   Model identifies which strategies are active/relevant
   Metric: Precision + Recall
   Target: Precision > 85%, Recall > 80%
   Note:   FALSE POSITIVES are worse than false negatives
           (saying "80P triggered" when it didn't = dangerous)

4. LEVEL ACCURACY
   ────────────────
   Input:  50 holdout snapshots
   Task:   Model mentions key levels (POC, VAH, VAL, IB H/L)
   Metric: % of mentioned levels within 2 ticks of actual
   Target: > 95% accuracy (levels must come from snapshot, not hallucinated)

5. CONFIDENCE CALIBRATION
   ────────────────────────
   Input:  All holdout snapshots
   Task:   Model outputs confidence scores
   Metric: Calibration curve — when model says 70%, actual WR should be ~70%
   Target: Mean absolute calibration error < 10%
   Test:   Bucket by confidence (50-60%, 60-70%, 70-80%, 80+%)
           Compare predicted WR to actual (from backtest outcomes)

6. REASONING QUALITY
   ───────────────────
   Input:  20 holdout snapshots (diverse conditions)
   Task:   Model produces full 9-step thinking chain
   Metric: Opus-as-judge scores reasoning (0-100)
   Target: Mean score > 70
   Checks: - Steps reference actual data (not vague)
           - Logic flows forward (step 3 builds on step 2)
           - Contradictions between steps = automatic fail
           - Strategy commentary is grounded in backtest stats

7. STRATEGY-SPECIFIC KNOWLEDGE PROBES
   ────────────────────────────────────
   Targeted questions the model must answer correctly:

   "What is the 80P Rule stop placement?"
   Expected: "VA edge + 10pt buffer. NEVER use candle-based stops."

   "When should you NOT enter a 20P trade?"
   Expected: "After 13:00 ET. WR drops to ~32% after cutoff."

   "What entry model has the highest $/month for 80P?"
   Expected: "Model B (limit 50% VA depth): 44.7% WR, PF 2.57, $1,922/mo"

   "What does wick parade > 4 bearish mean for 80P SHORT?"
   Expected: "High trap risk. Historical WR drops significantly. Consider SKIP."

   Format: 20 probe questions × answer grading (correct/partial/wrong)
   Target: > 80% correct or partial
```

**Comparison Framework: v001 vs v002 vs Baseline**

```
┌──────────────────┬───────────┬───────────┬────────────┐
│ Metric           │ Baseline  │ v001      │ v002       │
│                  │ (determ)  │ (1st LoRA)│ (2nd LoRA) │
├──────────────────┼───────────┼───────────┼────────────┤
│ Day type acc     │ 68%       │ 74%       │ 78%        │
│ Bias accuracy    │ 72%       │ 79%       │ 82%        │
│ Strategy recog   │ N/A       │ 83%       │ 88%        │
│ Level accuracy   │ 100%      │ 96%       │ 98%        │
│ Confidence cal   │ ±15%      │ ±12%      │ ±8%        │
│ Reasoning qual   │ N/A       │ 65/100    │ 74/100     │
│ Strategy probes  │ N/A       │ 70%       │ 85%        │
├──────────────────┼───────────┼───────────┼────────────┤
│ VERDICT          │ baseline  │ ⚠ below   │ ✅ PASS    │
│                  │           │ threshold │ deploy     │
└──────────────────┴───────────┴───────────┴────────────┘
```

**Promotion gate:** Model v(N+1) must match or beat v(N) on ALL 7 dimensions on the holdout set. If ANY dimension regresses, the model is NOT promoted.

### Layer 3: Production Output Quality (Ongoing)

Once the model is deployed (serving via vLLM), we continuously monitor output quality.

**Real-Time Checks (every inference call):**

| Check | Action |
|-------|--------|
| Schema compliance | Reject and retry if missing sections |
| Level grounding | Log warning if levels don't match snapshot |
| Confidence range | Flag if always outputting 65-75% (not calibrated) |
| Response time | Alert if > 3s (performance regression) |

**Daily Review (Opus Tier 2):**

Each evening, Opus reviews all outputs from the day:
- Score each output (0-100)
- Flag any that reference wrong strategies or hallucinate levels
- Identify drift patterns (model getting worse over time?)
- Compare to deterministic engine (are they diverging?)

**Weekly Metrics (W&B Dashboard):**

```
- Average output quality score (Opus-judged)
- Schema compliance rate
- Strategy mention accuracy (vs actual signals fired)
- Confidence calibration curve (updated weekly)
- Agent decision quality (from replay: TAKE accuracy, SKIP accuracy)
```

**Retraining Trigger:**

```
IF (weekly_quality_score < 70 for 2 consecutive weeks)
   OR (strategy_accuracy drops below 80%)
   OR (calibration_error exceeds 15%)
THEN:
   → Generate fresh training data from recent sessions
   → Retrain LoRA (incremental, on new data)
   → Evaluate against holdout
   → If passes gates → promote
   → If fails → investigate what changed (market regime shift? data issue?)
```

### Benchmark Suite: How To Run It

```bash
# Layer 1: Validate training data quality
uv run python -m rockit_train.validate \
    --dataset data/training/v001/train.jsonl \
    --checks schema,grounding,strategy,calibration \
    --report data/training/v001/quality_report.json

# Layer 2: Evaluate trained model
uv run python -m rockit_train.evaluate \
    --model adapters/v001 \
    --holdout data/training/v001/test.jsonl \
    --probes configs/evaluation/strategy_probes.yaml \
    --baseline data/training/v001/deterministic_baseline.json \
    --report data/evaluation/v001_eval.json

# Layer 2: Compare two model versions
uv run python -m rockit_train.compare \
    --model-a adapters/v001 \
    --model-b adapters/v002 \
    --holdout data/training/v001/test.jsonl \
    --report data/evaluation/v001_vs_v002.json

# Layer 3: Opus daily review (runs post-market)
uv run python -m rockit_train.daily_review \
    --date 2026-03-03 \
    --outputs data/production/outputs_2026-03-03.jsonl \
    --reviewer opus \
    --report data/reviews/daily_2026-03-03.json
```

### What We Need To Build

| Component | Purpose | Status |
|-----------|---------|--------|
| `rockit-train/validate.py` | Layer 1: Training data quality checks | NOT BUILT |
| `rockit-train/evaluate.py` | Layer 2: Model capability benchmarks | NOT BUILT |
| `rockit-train/compare.py` | Layer 2: Version comparison | NOT BUILT |
| `rockit-train/daily_review.py` | Layer 3: Opus daily review | NOT BUILT |
| `configs/evaluation/strategy_probes.yaml` | 20 strategy knowledge probe Q&A pairs | NOT WRITTEN |
| `configs/evaluation/holdout_sessions.yaml` | 50-session holdout definition | NOT DEFINED |
| W&B integration | Logging metrics across runs | NOT CONFIGURED |

---

## Open Questions

1. **How many snapshots per day should we use for training?** All 78 RTH? Or subsample to key moments (IB close, first signal, post-signal, EOD)?

2. **Should early-session snapshots (09:30-10:00) be included?** They have very sparse data (IB not formed, no volume profile). Could teach the LLM to say "insufficient data" — which IS a useful skill.

3. **Which frontier model for training data generation?** Opus 4.6 is highest quality but most expensive. Gemini is cheaper. Could we use Gemini for bulk generation and Opus for quality review/scoring?

4. **Strategy commentary: how much detail?** Should the LLM explain the full strategy mechanics (30-min acceptance, VA-edge stop) or just note "80P SHORT triggered at 21445"?

5. **Should the LLM output include a recommended action (TAKE/SKIP)?** Or is that the agent's job? (Architecture/14 says agents decide — but the training output could still include a "preliminary recommendation" that agents override.)

6. **Version the training data alongside the strategy code?** When strategy parameters change (e.g., 20P cutoff 14:00→13:00), old training data has wrong strategy commentary. Regenerate affected pairs?

7. **How do we handle the RockitDataFeed legacy data?** Merge with new format? Use as supplementary? Discard and regenerate?
