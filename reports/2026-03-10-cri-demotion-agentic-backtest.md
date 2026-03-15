# CRI Demotion to Soft Evidence + Agentic Backtest Report

**Date**: 2026-03-10
**Branch**: `claude/bridge-implementation`
**Status**: Code changes complete, A/B backtest running

---

## Problem Statement

CRI (Confirmation/Readiness/Inflection) STAND_DOWN was acting as a **hard gate** that blocked ALL signals before observers or LLM debate could run. On 2026-03-10, CRI blocked both signals (including an OR Acceptance +$505 winner) due to a Bear Trap false positive (26/26 wicks = 50/50 split, not a real bear signal).

**Impact**: The LLM debate layer — the most sophisticated part of the pipeline — never fires when CRI blocks. This defeats the purpose of the agentic framework.

## Changes Made

### 1. CRI Gate Agent (`agents/gate.py`)

| Status | Before | After |
|--------|--------|-------|
| READY/MISSING | neutral, strength 1.0 | neutral, strength 1.0 (unchanged) |
| STAND_DOWN | neutral, strength **0.0** (hard block) | **bearish**, strength **0.7** (soft signal) |
| CAUTION | neutral, strength 0.5 | **bearish**, strength **0.4** |
| `passes()` | Returns False on STAND_DOWN | **Always returns True** |

**Rationale**: CRI STAND_DOWN now contributes a strong (0.7) bearish evidence card to the scoring instead of vetoing the entire pipeline. This means observers run, LLM debate fires, and the orchestrator weighs CRI alongside all other evidence.

### 2. Agent Pipeline (`agents/pipeline.py`)

- **Before**: Observers only run `if gate_passed:`
- **After**: Observers **always run** regardless of CRI status
- **Before**: Debate only runs `if self.enable_debate and gate_passed and len(all_cards) > 1`
- **After**: Debate runs `if self.enable_debate and len(all_cards) > 1` (gate_passed removed from condition)

### 3. Deterministic Orchestrator (`agents/orchestrator.py`)

- **Removed**: `if not gate_passed: return SKIP` from both `decide()` and `decide_with_debate()`
- **Updated**: `_build_confluence()` and `_build_confluence_admitted()` now include directional (bearish) CRI cards in scoring. Only neutral CRI cards (READY/MISSING) are still skipped.

### 4. Agent Filter (`agents/agent_filter.py`)

No code changes needed — it delegates to pipeline and checks `decision.decision`, which works correctly with the new behavior.

### 5. Tests Updated

| Test File | Changes |
|-----------|---------|
| `test_agents.py` | Updated 4 tests: STAND_DOWN → bearish str=0.7, passes()=True, observers run, debate flows through |
| `test_agent_filter.py` | Updated 1 test: STAND_DOWN no longer auto-blocks |

**Test Results**: 59/60 pass (1 pre-existing failure: OllamaClient timeout default 180 vs test expectation 30)

## Design Rationale

### Why Soft Evidence Instead of Hard Gate?

1. **False positives are costly**: CRI STAND_DOWN blocked a +$505 OR Acceptance winner on 2026-03-10. The wick trap data (26 bear / 26 bull) was 50/50 — not a real bear signal.

2. **LLM debate adds context**: The Advocate/Skeptic debate can evaluate CRI STAND_DOWN in context (e.g., "wick data is 50/50, not a real bear trap") — something a hard gate can't do.

3. **0.7 strength is still strong**: A bearish 0.7 card in the certainty layer (weight 1.0) contributes 0.7 bearish score. This will shift many signals to SKIP or REDUCE_SIZE unless strong bullish evidence overrides it. CRI is influential but not absolute.

4. **Consistent with architecture**: The agent framework design calls for evidence-based decisions, not binary gates. Every signal deserves full evaluation.

## A/B Backtest (In Progress)

Running full 270-session backtest with 5 runs:

| Run | Configuration |
|-----|---------------|
| A | No filters (baseline) |
| B | Mechanical filters only |
| C | Mechanical + Agent |
| D | Agent only |
| E | **Mechanical + Agent + LLM debate** |

**Key difference from previous backtest**: With CRI demoted, Run E now gets debate data for ALL signals, not just those that pass CRI. This is the first time the full agentic pipeline runs unblocked.

**Estimated time**: ~3-4 hours for 270 sessions (LLM calls ~70s each, 2 per signal)

**Command**: `uv run python scripts/ab_test_agents.py --no-merge --enable-debate`

## Expected Outcomes

### Optimistic Scenario
- Run E shows improved WR/PF over Run C (signals that were previously blocked by CRI but had strong bullish evidence now get through)
- Debate catches false-positive CRI STAND_DOWN sessions and correctly overrides

### Pessimistic Scenario
- Some signals that were correctly blocked by CRI now leak through as losses
- Net PnL drops slightly but we gain data on debate effectiveness

### Either Way
- We get debate data for ALL signals, enabling much better analysis of the LLM layer
- We can tune CRI strength (0.7 → 0.5, 0.8, etc.) based on results

## Next Steps

1. **Wait for backtest completion** (~3-4 hours)
2. **Analyze Run E results**:
   - Compare Run E vs Run C (previous best)
   - Look at signals where CRI was STAND_DOWN — did debate correctly override?
   - Check PnL contribution of previously-blocked signals
3. **Tune CRI weight**: If 0.7 is too strong/weak, adjust based on data
4. **Phase 4b**: Pattern Miner (DuckDB historical context) — next major agent capability
5. **Update memory**: Record findings for future sessions

---

*Report will be updated with backtest results when complete.*
