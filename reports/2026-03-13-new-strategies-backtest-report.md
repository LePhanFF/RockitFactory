# New Strategies Backtest Report — 2026-03-13

> **Triggered by**: Session review 2026-03-13 (double distribution trend day down)
> **Instrument**: NQ, 274 sessions
> **Branch**: claude/bridge-implementation

---

## Executive Summary

Three quant studies conducted in parallel. Two produced viable strategies, one was conclusively rejected:

| Study | Edge? | Action |
|-------|-------|--------|
| Bear Accept (IBL acceptance) | NO (PF 0.53) | Not built. IB breaks are frequently failed breakouts in NQ |
| Double Distribution | YES (PF 2.10 filtered) | Built + enabled: `double_distribution.py` |
| Trend Day Bull/Bear | YES (PF 1.43/1.78 filtered) | Rebuilt + re-enabled: `trend_bull.py`, `trend_bear.py` |

**Combined impact**: +$37,056 over 274 sessions (mechanical filters), 151 trades, 44.4% WR, PF 1.62

---

## Study 1: Bear Accept — REJECTED

**Concept**: Dalton IB acceptance — 30-min close below IBL → short near IBL

**Result**: 4 study variants, 332 sessions, exhaustive filter combos
- Median MAE = 132 pts ($2,640/contract) — price bounces hard after acceptance
- Best PF = 0.53 (with VWAP + EMA alignment)
- Best WR = 33%

**Conclusion**: Raw IB acceptance has no edge in NQ. Failed breakouts are too common. The existing 20P IB Extension strategy handles this correctly by requiring 3 consecutive 5-min closes AND opening outside prior VA.

**Scripts**: `scripts/_bear_accept_study.py` (v1-v4)

---

## Study 2: Double Distribution — BUILT

**Concept**: When TPO profile shows two distinct value areas (B_shape), enter on pullback to the separation level (LVN between distributions)

### Detection Quality
- `_detect_distributions()` fires on 98% of sessions (too loose)
- POC spread >= 75pts narrows to 44% of sessions
- POC spread >= 100pts narrows to 26% (true double distributions)
- Early detection (before 10:30) has 2x better MFE

### Backtest Results

| Run | Trades | WR | PF | Net PnL |
|-----|--------|----|----|---------|
| A (no filters) | 31 | 35.5% | 1.30 | +$3,753 |
| **B (filtered)** | **17** | **47.1%** | **2.10** | **+$6,190** |

### Strategy Parameters
- Entry: Pullback to separation level (limit fill)
- Stop: 30pt fixed
- Target: 2.5R (75pt)
- Min POC spread: 75pts
- Detection cutoff: 10:30 (early only)
- Max 1 trade/session

**File**: `packages/rockit-core/src/rockit_core/strategies/double_distribution.py`
**Tests**: 25 tests in `test_double_distribution.py`

---

## Study 3: Trend Day Bull/Bear — REBUILT

**Concept**: Re-optimize disabled trend strategies with 15-min EMA alignment + ADX gate

### Key Changes
1. Added 15-min EMA20/EMA50 alignment filter (new `compute_15m_trend_indicators()` in technical.py)
2. ADX >= 25 for bull, ADX >= 35 for bear (bears need stronger trend signal)
3. Delta confirmation (positive for longs, negative for shorts)
4. Removed day_type gate (was blocking viable entries)
5. Fixed 40pt stop / 100pt target (2.5:1 R:R)
6. Entry: VWAP pullback (priority) or EMA20 pullback

### Backtest Results

| Strategy | Run | Trades | WR | PF | Net PnL |
|----------|-----|--------|----|----|---------|
| Trend Bull | A (no filters) | 92 | 43.5% | 1.41 | +$14,823 |
| **Trend Bull** | **B (filtered)** | **85** | **44.7%** | **1.43** | **+$14,187** |
| Trend Bear | A (no filters) | 67 | 35.8% | 1.39 | +$12,310 |
| **Trend Bear** | **B (filtered)** | **49** | **42.9%** | **1.78** | **+$16,679** |

**Files**: `trend_bull.py`, `trend_bear.py` (complete rewrites)
**Tests**: 27 tests in `test_trend_strategies.py`
**Infrastructure**: `compute_15m_trend_indicators()` added to `technical.py`

---

## Combined Portfolio Impact

### New Strategies Only (Run B — Mechanical Filters)

| Strategy | Trades | WR | PF | Net PnL |
|----------|--------|----|----|---------|
| Double Distribution | 17 | 47.1% | 2.10 | +$6,190 |
| Trend Day Bull | 85 | 44.7% | 1.43 | +$14,187 |
| Trend Day Bear | 49 | 42.9% | 1.78 | +$16,679 |
| **Total** | **151** | **44.4%** | **1.62** | **+$37,056** |

### Existing Portfolio (Run B baseline, from memory)
- 259 trades, 61.0% WR, PF 3.07, +$125,885

### Combined Estimate
- ~410 trades, ~55% WR, PF ~2.2, **~$162,941**

---

## Run C: LLM Debate (Pending)

LLM Advocate/Skeptic debate backtest running on spark-ai (Qwen3.5:35b-a3b).
Expected duration: ~30-60 min for 190 signals.

Results will be appended below when complete.

---

## Observations Persisted to DuckDB

7 observations from these studies:
1. Bear Accept has NO edge (MAE too high)
2. Double Distribution edge confirmed (PF 2.10 filtered)
3. Double Distribution + filters improve quality
4. Trend Bull re-optimized (15-min EMA + ADX >= 25)
5. Trend Bear re-optimized (15-min EMA + ADX >= 35, bears need higher threshold)
6. Combined new strategies add $37K to portfolio
7. B_shape detection is too loose (98% fire rate) — POC spread filter is critical

2 backtest runs persisted: `new_strats_A_2026-03-13`, `new_strats_B_2026-03-13`
Run C pending: `new_strats_C_LLM_2026-03-13`

---

## Files Created/Modified

### New Files
- `packages/rockit-core/src/rockit_core/strategies/double_distribution.py` — Double Distribution strategy
- `packages/rockit-core/tests/test_double_distribution.py` — 25 tests
- `packages/rockit-core/tests/test_trend_strategies.py` — 27 tests
- `scripts/_bear_accept_study.py` (v1-v4) — Bear Accept research scripts
- `scripts/_dd_study.py` (v1-v3) — Double Distribution research scripts
- `scripts/_trend_reopt_study.py` — Trend reoptimization research scripts
- `reports/2026-03-13-new-strategies-backtest-report.md` — This report

### Modified Files
- `packages/rockit-core/src/rockit_core/strategies/trend_bull.py` — Complete rewrite
- `packages/rockit-core/src/rockit_core/strategies/trend_bear.py` — Complete rewrite
- `packages/rockit-core/src/rockit_core/indicators/technical.py` — Added 15-min EMA/ADX
- `packages/rockit-core/src/rockit_core/strategies/loader.py` — Registered double_distribution
- `configs/strategies.yaml` — Enabled DD, Trend Bull, Trend Bear
- `packages/rockit-core/tests/test_strategy_loader.py` — Updated counts
- `brainstorm/10-Next-steps.md` — Added Phase 6 (Trend Day & DD strategies)
- `brainstorm/review-sessions/2026.03.13.md` — Appended system analysis
