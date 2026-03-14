# 14 — Where We Are: March 13, 2026

> **Purpose**: Consolidated status of all brainstorm docs, what's been built, what's persisted, what's outstanding.
>
> **Supersedes**: 10-Next-steps.md (Phases 1-5), 10A-Next-steps-domain-experts.md, 13-agentic-ideas.md — all DONE or absorbed.
>
> **Date**: 2026-03-13

---

## 1. What Has Been Built

### Phase 1: Foundation — COMPLETE (2026-03-08)

| Item | Status | Evidence |
|------|--------|----------|
| MAE/MFE per-trade tracking | DONE | `Trade` dataclass tracks mae_price, mfe_price, mae_bar, mfe_bar |
| 25 extended metrics | DONE | edge_ratio, kelly, serial_correlation, recovery_factor, etc. |
| FVG lifecycle tracking | DONE | Filled FVGs retained with status/fill_pct/filled_time |
| Data validation pipeline | DONE | `data_validator.py` — POC/VA/IB/ATR/NaN checks, integrated into orchestrator |
| Regime context module | DONE | `regime_context.py` — daily ATR, VIX, prior day type, consecutive balance days, 7 composite labels |
| Deterministic tape generator | DONE | `scripts/generate_deterministic_tape.py` — all sessions, JSONL output, validation reporting |

### Phase 2: Retrofit Strategies — COMPLETE (2026-03-08)

| Item | Status | Evidence |
|------|--------|----------|
| Pluggable stop/target models | DONE | 19 stop models, 14 target models in registry |
| All 5 active strategies retrofitted | DONE | OR Rev, OR Accept, 80P, 20P, B-Day use injected models |
| Baseline JSON persistence | DONE | `data/results/baselines/baseline_NQ.json` |
| 20P IB Extension fixed | DONE | Removed 4 extra filters not in source study |
| 80P Rule rewritten | DONE | Matched source — 30-bar acceptance, acceptance close entry, 2R target |

### Phase 3: Research DB — COMPLETE (2026-03-08)

| Item | Status | Evidence |
|------|--------|----------|
| DuckDB schema + init | DONE | `data/research.duckdb` with 8 tables + 4 views |
| Auto-persist backtest runs | DONE | `run_backtest.py` hooks into DuckDB |
| Deterministic tape persistence | DONE | 7,362 tape rows across 270 sessions |
| Session context persistence | DONE | 270 session rows |
| Trade persistence | DONE | 8,000+ trades across 36+ runs |
| Correlation views | DONE | `v_trade_context`, `v_trade_tape` |

### Phase 4: Agent Framework — COMPLETE (2026-03-09 through 2026-03-13)

| Item | Status | Evidence |
|------|--------|----------|
| Evidence card system | DONE | `EvidenceCard` with card_id, source, layer, direction, strength |
| CRI Gate Agent | DONE | Soft gate — CRI is evidence, not a block |
| ProfileObserver (4 cards) | DONE | TPO shape, VA position, POC position, poor extremes |
| MomentumObserver (5 cards) | DONE | DPOC regime, trend, wicks, extension, bias |
| DeterministicOrchestrator | DONE | Rule-based scorecard → TAKE/SKIP/REDUCE_SIZE |
| AgentPipeline | DONE | Gate → Observers → [ConflictDetector] → [Debate] → Orchestrator |
| AgentFilter (FilterBase) | DONE | Plugs agents into CompositeFilter chain |
| API endpoints | DONE | POST /agents/evaluate, GET /agents/status |
| LLM Advocate/Skeptic debate | DONE | Qwen3.5 via Ollama, ~70s/call, fallback to deterministic |
| DuckDB enrichment in debate | DONE | Strategy stats + recent observations fed to Advocate/Skeptic |
| Debate log persistence | DONE | `data/debate_log.json` |
| A/B test scripts | DONE | `scripts/ab_test_agents.py` — 4-5 runs (A-E) |
| **8 Domain Experts** | DONE | TpoExpert, VwapExpert, EmaExpert, IctExpert, ScalperExpert, OrderFlowExpert, DivergenceExpert, MeanReversionExpert |
| **DomainExpert base class** | DONE | `agents/experts/base.py` — pluggable architecture |
| **ConflictDetector (Level 1)** | DONE | Deterministic cross-domain conflict resolution |
| **LLMProvider interface** | DONE | Abstract class + OllamaProvider wrapper |
| **Pipeline preset system** | DONE | `AgentPipeline()` = legacy 2-observer, `AgentPipeline(preset="experts")` = full 9 experts + ConflictDetector |

### Phase 5: Trade Assessments & Filters — COMPLETE (2026-03-09)

| Item | Status | Evidence |
|------|--------|----------|
| Trade assessments | DONE | `scripts/populate_assessments.py` — programmatic assessment |
| 15 pattern observations | DONE | Bias alignment, OR Rev + B_shape, 80P contrarian, etc. |
| Bias in backtest engine | DONE | `session_bias_lookup` + `regime_bias` 3-vote system |
| Filter pipeline (YAML) | DONE | `configs/filters.yaml` — BiasAlignment, DayTypeGate, AntiChase |
| NWOG Gap Fill strategy | DONE | Monday-only, VWAP filter, 75pt stop, 13:00 time stop |
| A/B test: mechanical filters | DONE | Run B = 259 trades, 61.0% WR, 3.07 PF |

### Self-Learning Feedback Loop — COMPLETE (2026-03-10)

| Item | Status | Evidence |
|------|--------|----------|
| session_reviews table | DONE | Persists per-session review + alignment analysis |
| TradeReviewer (LLM) | DONE | Qwen3.5 post-trade analysis → structured reviews |
| `review_and_persist()` | DONE | Reviews → trade_assessments + observations |
| `scripts/review_trades.py` | DONE | Batch LLM trade review |
| `/review-session` skill | DONE | Interactive session review, persists to DuckDB |
| `/meta-review` skill | DONE | Periodic review of observations + strategy trends |
| `/backtest-report` skill | DONE | Post-backtest analysis and report generation |

### Training Data Pipeline — COMPLETE (2026-03-04)

| Item | Status | Evidence |
|------|--------|----------|
| System prompt | DONE | `configs/prompts/rockit_system_prompt.md` |
| Output schema | DONE | `configs/prompts/output_schema.json` (13 fields) |
| Training pairs | DONE | 164 pairs, 4 days, `data/training_pairs/` |
| ChatML conversion | DONE | `convert_to_chatml.py`, 75/25 think ratio |
| LoRA training script | DONE | `train_lora.py` (Unsloth, BF16, r=64) |

---

## 2. Current Backtest Results (2026-03-09, NQ, 270 sessions)

### Baseline (No Filters)
- **408 trades, 56.1% WR, PF 2.45, +$159,332**

### Production Pick: Bias-Filtered (Run B)
- **259 trades, 61.0% WR, PF 3.07, +$125,885**

| Strategy | Trades | WR | PF | Net PnL | Key Insight |
|----------|--------|-----|-----|---------|-------------|
| OR Rev | 55 | 76.4% | 5.39 | +$54,630 | Alpha engine. B_shape TPO = best. |
| OR Accept | 89 | 64.0% | 3.31 | +$24,839 | Consistency machine. |
| 80P Rule | 54 | 48.1% | 2.32 | +$25,846 | SHORT=60.9%, LONG=38.7%. |
| 20P IB Ext | 35 | 51.4% | 2.43 | +$14,804 | VIX-sensitive. |
| B-Day | 26 | 57.7% | 1.76 | +$5,767 | Block on trend days. |

### Agent A/B Test Results (270 sessions)

| Run | Config | Trades | WR | PF | Net PnL |
|-----|--------|--------|-----|-----|---------|
| A | No filters | 408 | 56.1% | 2.45 | $159K |
| B | Mechanical only | 206 | 64.1% | 3.30 | $98K |
| C | Mechanical + Agent (2-observer) | 205 | 64.4% | 3.33 | $99K |
| D | Agent only (2-observer) | 353 | 58.4% | 2.70 | $155K |
| E | Agent + LLM debate (5-session) | 3 | 100% | — | $3,117 |

**Finding**: Deterministic agents add marginal value over mechanical filters (same data, similar logic). LLM debate shows promise but needs full 270-session backtest (Run E) to validate.

---

## 3. What's Persisted in DuckDB

| Table | Rows | Purpose |
|-------|------|---------|
| `backtest_runs` | 36+ | Run-level metadata and aggregate metrics |
| `trades` | 8,000+ | Per-trade detail across all runs |
| `session_context` | 270 | Session-level summary (day type, bias, IB, VA) |
| `deterministic_tape` | 7,362 | 5-min time series (38 module outputs) |
| `observations` | 29+ | Structured findings (human, system, LLM sources) |
| `trade_assessments` | 1,029 | Per-trade AI analysis |
| `agent_decisions` | varies | Per-signal agent pipeline decisions |
| `session_reviews` | varies | Per-session review analysis + alignment |

**Views**: `v_trade_context`, `v_trade_tape`, `v_agent_accuracy`, `v_agent_vs_mechanical`

**Observation sources**: `human_review`, `system_review`, `llm_trade_review`, `meta_review`

---

## 4. Test Coverage

- **1,046 tests passing** (as of 2026-03-13)
- Key test files:
  - `test_agents.py` (28) — core agent pipeline
  - `test_agent_filter.py` (10) — filter integration
  - `test_domain_experts.py` (49) — TPO, VWAP, EMA, pipeline integration, LLMProvider
  - `test_all_domain_experts.py` (63) — ICT, Scalper, OrderFlow, Divergence, MeanReversion, ConflictDetector, full pipeline
  - `test_self_learning.py` (27) — TradeReviewer, session reviews, observation persistence

---

## 5. Architecture Summary

```
Signal fires (from StrategyBase)
    │
    ├── Mechanical Filters (configs/filters.yaml)
    │   ├── BiasAlignmentFilter — blocks counter-bias
    │   ├── DayTypeGateFilter — blocks wrong day types
    │   └── AntiChaseFilter — disabled (too aggressive)
    │
    ├── Agent Pipeline (optional, disabled by default)
    │   │
    │   ├── Legacy mode: AgentPipeline()
    │   │   └── CRIGate → ProfileObserver (4) + MomentumObserver (5) → Orchestrator
    │   │
    │   └── Expert mode: AgentPipeline(preset="experts")
    │       └── CRIGate → 8 DomainExperts + MomentumObserver (25+ cards)
    │           → ConflictDetector → [LLM Debate] → Orchestrator
    │
    └── Decision: TAKE / SKIP / REDUCE_SIZE

Self-Learning Loop:
  /review-session → DuckDB observations
  /meta-review → meta-observations
  TradeReviewer (LLM) → trade_assessments + observations
  All observations feed into future Advocate/Skeptic debates via _query_historical()
```

---

## 6. What's Outstanding

### NOT YET DONE from 10-Next-steps.md

| Item | Original Phase | Status | Priority |
|------|---------------|--------|----------|
| **Bayesian calibration pipeline** | Phase 4.1 | Not started | LOW — domain experts + debate may obviate this |
| **50/50 train/test split** | Phase 4.3 | Not started | MEDIUM — important for validation |
| **ComboRunner persistence** | Phase 3 | Not started | LOW — combo optimization deprioritized |
| **Correlation engine** | Phase 3 | Partially done via views | LOW — views cover most use cases |
| **LLM LoRA training** | Phase 5 | Pipeline ready, training not executed | MEDIUM — training data exists |
| **Run E full backtest** | Phase 4c | Only 5-session validation done | HIGH — 270-session LLM debate A/B test |

### NOT YET DONE from 10A-Next-steps-domain-experts.md

| Item | Status | Priority |
|------|--------|----------|
| **Ad-hoc query system** (`consult()`) | Not started | MEDIUM — "I want to short at X, what do experts say?" |
| **Level Expert** (confluence scoring) | Not started (Phase B) | HIGH — highest-value new domain per 10A |
| **Structure Expert** (CRI sub-components, IB, acceptance) | Not started | HIGH — CRI data underexposed |
| **Regime Expert** (ATR, VIX, consecutive balance) | Not started | MEDIUM |
| **Swing/Trendline Expert** | Not started (Phase C) | MEDIUM — needs new modules |
| **Cross-Instrument Expert** (SMT) | Not started (Phase D) | LOW — needs ES/YM data |
| **Expert vs Legacy A/B benchmark** (Run F vs Run G) | Not started | HIGH — must validate before switching defaults |

### Strategy Lifecycle Tracker (from 12-strategy-expansion-roadmap.md)

Legend: Study = quant study done | Code = strategy file built | BT = backtested with results | Enabled = in production config

#### COMPLETE: Study + Code + Backtest + Enabled (10 strategies)

| Strategy | Study | Backtest Results | File | Notes |
|----------|-------|------------------|------|-------|
| OR Reversal | Yes | 55 trades, 76.4% WR, PF 5.39, +$54,630 | `or_reversal.py` | Alpha engine. Original core. |
| OR Acceptance | Yes | 89 trades, 64.0% WR, PF 3.31, +$24,839 | `or_acceptance.py` | Consistency machine. |
| 80P Rule | Yes | 54 trades, 48.1% WR, PF 2.32, +$25,846 | `eighty_percent_rule.py` | SHORT=60.9%, LONG=38.7%. Rewritten 03-02. |
| 20P IB Extension | Yes | 35 trades, 51.4% WR, PF 2.43, +$14,804 | `twenty_percent_rule.py` | Fixed 03-08 (removed extra filters). |
| B-Day | Yes | 26 trades, 57.7% WR, PF 1.76, +$5,767 | `b_day.py` | Block on trend days. |
| **Trend Day Bull** | Yes (`quant-study-trend-day.md`) | 85 trades, 44.7% WR, PF 1.43, +$14,187 | `trend_bull.py` | Complete rewrite 03-13. 15-min EMA + ADX≥25. |
| **Trend Day Bear** | Yes (`quant-study-trend-day.md`) | 49 trades, 42.9% WR, PF 1.78, +$16,679 | `trend_bear.py` | Complete rewrite 03-13. ADX≥35 for bears. |
| **PDH/PDL Reaction** | Yes (`quant-study-pdh-pdl.md`) | 21 trades, 52.4% WR, PF 1.35, +$2,826 | `pdh_pdl_reaction.py` | Built 03-12. |
| **NDOG Gap Fill** | Yes (`quant-study-ndog.md`) | 42 trades, 88.1% WR, PF 12.08 (study) | `ndog_gap_fill.py` | Built 03-12. Pre-IB entry needed for full edge. |
| **Double Distribution** | Yes (03-13 study) | 17 trades, 47.1% WR, PF 2.10, +$6,190 | `double_distribution.py` | Built 03-13. POC spread≥75pt + early detection. |

#### COMPLETE: Study + Code + Backtest + DISABLED (framework blockers)

These strategies were built and backtested but disabled because the backtest engine only fires `on_bar()` after 10:30 AM, blocking pre-IB entries. They need engine changes to unlock their full edge.

| Strategy | Study | Backtest Issue | File | Fix Needed |
|----------|-------|----------------|------|------------|
| **NWOG Gap Fill** | Yes (`quant-study-nwog.md`) | 8 trades, 25% WR, -$11K | `nwog_gap_fill.py` | Monday-only. RTH open entry blocked. |
| **Single Print Gap Fill** | Yes (`quant-study-single-print-gap-fill.md`) | 0 trades (entry blocked) | `single_print_gap_fill.py` | Needs pre-10:30 entry. |
| **Poor HL Repair** | Yes (`quant-study-poor-highlow.md`) | 0 trades (entry blocked) | `poor_highlow_repair.py` | Needs pre-10:30 entry. |
| **CVD Divergence** | Yes (`quant-study-cvd-divergence.md`) | 0 trades (delta calc timing) | `cvd_divergence.py` | Delta needs full bar history from open. |
| **RTH Gap Fill** | Yes (`quant-study-rth-gap-fill.md`) | 0 trades (entry blocked) | `rth_gap_fill.py` | Needs RTH open entry (9:30). |

#### STUDIED but NOT YET CODED

| Strategy | Study | Key Finding | Worth Pursuing? |
|----------|-------|-------------|-----------------|
| VA Edge Fade | Yes (v1 + v2: `quant-study-va-edge-fade.md`) | 72.4% WR at 2nd VA test | **YES — HIGH.** Best unstudied edge. Fills mid-session gap. |
| IB Edge Fade | Yes (`quant-study-ib-edge-fade.md`) | IB rejection setups | MEDIUM — complements 20P. |
| IB Retracement | Yes (v1 + v2: `quant-study-ib-retracement.md`) | IB pullback entries | MEDIUM — overlaps with IB Edge Fade. |
| Mean Reversion VWAP | Yes (`quant-study-mr-vwap.md`) | Currently losing (-$6,925) | MEDIUM — needs ADX gating rewrite. |
| VWAP Sigma Bands | Yes (`quant-study-vwap-sigma-bands.md`) | Sigma band bounce | LOW — thin edge. |

#### REJECTED (Study showed no edge)

| Strategy | Study | Result | Decision |
|----------|-------|--------|----------|
| **Bear Accept / IBL Accept** | Yes (03-13 study, 4 variants) | PF 0.53, MAE=132pts | REJECTED. Failed breakouts too common in NQ. |

#### NOT YET STUDIED (from roadmap, no quant work done)

| Strategy | Roadmap Ref | Priority | Blocker |
|----------|-------------|----------|---------|
| Asia Session Sweep | G2 | LOW | Needs Globex session data |
| Intraday Momentum Breakout | G3 | LOW | 14-day noise area calc |
| SMT Divergence (filter, not strategy) | G1 | LOW | ES data loading for cross-instrument |
| ICT Silver Bullet | G8 | LOW | FVG time-window gating |
| IB Extension Continuation | G7 | LOW | Complements 20P |
| B-Day IBH Short | B4 | LOW | Subset of B-Day |

#### Strategies RETIRED / DEPRECATED

Already removed or disabled with no plans to revisit:
- ORB Enhanced, ORB VWAP Breakout, Super Trend Bull/Bear, P-Day (standalone), Neutral Day, PM Morph, EMA Trend Follow, Liquidity Sweep, MACD Crossover

#### Summary: 15 quant studies completed, 15 strategies coded, 10 enabled, 5 blocked, 1 rejected

### NOT YET DONE from 13-agentic-ideas.md

The 8 domain experts requested in this doc are **ALL BUILT**. Remaining items:

| Item | Status | Priority |
|------|--------|----------|
| Scalper fast-path (<100ms) | Not started | LOW — current pipeline already <50ms without LLM |
| Domain-specific DuckDB queries per expert | Partial — TpoExpert has `historical_query()`, others don't | MEDIUM |
| Per-domain A/B measurement | Not started | HIGH — measure each expert's marginal value |

---

## 7. Infrastructure & Tools

| Tool | Status | Notes |
|------|--------|-------|
| Ollama (Qwen3.5) | Running on spark-ai DGX | `http://spark-ai:11434/v1`, 128K context |
| DuckDB | Local, gitignored | Rebuild via `scripts/init_research_db.py` |
| Filter pipeline | YAML-driven | `configs/filters.yaml` |
| Skills (Claude Code) | 15 skills | /backtest, /review-session, /meta-review, /backtest-report, etc. |
| Deterministic snapshots | 270+ days generated | `data/json_snapshots/deterministic_*.jsonl` |
| Training data | 164 pairs ready | ChatML format, not yet trained |

---

## 8. Recommended Next Steps (Priority Order)

### Immediate (This Week)

1. **Run E: Full 270-session LLM debate backtest** — validate that LLM Advocate/Skeptic adds alpha over deterministic-only. Key decision gate for the agent system.

2. **Expert preset A/B test** — run `AgentPipeline(preset="experts")` vs `AgentPipeline()` (legacy) on 270 sessions. Measure: do 25+ cards improve WR/PF over 9 cards?

3. **Pre-IB entry engine fix** — unblock 5 disabled strategies (NWOG, Single Print, Poor HL, CVD Divergence, RTH Gap Fill) by allowing `on_bar()` to fire before 10:30. Highest leverage infrastructure change.

### Short-term (Next 2 Weeks)

4. **VA Edge Fade (new strategy)** — best unstudied edge (72.4% WR at 2nd VA test). Fills mid-session gap. `/add-strategy va_edge_fade`.

5. **Level Expert + Structure Expert** — highest-value new domains from 10A. Level confluence is the #1 missing signal. Structure Expert exposes CRI sub-components.

6. **IB Edge Fade / IB Retracement** — two studies done, complements 20P. Pick the better one and build.

### Medium-term (Month 2)

7. **Ad-hoc query system** — "I want to short at 21,500, what do experts say?" ConsultationResult with expert cards + matching strategies + confluence score.

8. **LoRA training** — training data pipeline is ready. Train Qwen3.5 LoRA on DGX Spark.

9. **Mean Reversion VWAP rewrite** — currently losing (-$6,925). Needs ADX gating. Study exists.

10. **Strategy retirement** — remove 9 deprecated strategies cluttering the codebase.

---

## 9. Document Status

| Document | Status | Action |
|----------|--------|--------|
| `10-Next-steps.md` | **Phases 1-5 DONE**, Phase 6 added 2026-03-13 | Mark Phases 1-5 as COMPLETE. Phase 6 (Trend Day/Bear Accept) is active. |
| `10A-Next-steps-domain-experts.md` | **Phase 1 DONE** (all 8 experts built). Phases 2-5 outstanding. | Mark Phase 1 COMPLETE. Phases 2-5 (ad-hoc query, Level/Structure/Swing experts) are active. |
| `12-strategy-expansion-roadmap.md` | **Mostly DONE**. 15 strategies coded, 10 enabled, 5 blocked (pre-IB), 1 rejected, 6 unstudied. | Keep for remaining backlog (VA Edge Fade, IB Edge Fade, etc.) |
| `13-agentic-ideas.md` | **DONE** — all 8 domain experts + ConflictDetector + LLMProvider built. | Mark COMPLETE. Architecture absorbed into codebase. |

---

*Document Version: 1.0*
*Date: 2026-03-13*
*Branch: claude/bridge-implementation*
*Tests: 1,046 passing*
