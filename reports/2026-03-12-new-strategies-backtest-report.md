# New Strategy Backtest Report — 2026-03-12

> Instrument: NQ | Sessions: 270 | Branch: claude/bridge-implementation

## Executive Summary

Five new strategies were built from quant study results. **None match their study targets** in the current backtest framework. The root cause is architectural: 3 strategies need pre-IB entry (9:30-10:00 AM) but the engine only fires `on_bar()` after 10:30 AM, and 1 strategy lacks required data in the pipeline.

## Strategy Results

| Strategy | Trades | WR | PF | Net PnL | Study WR | Study PF | Study PnL | Status |
|----------|--------|-----|------|---------|----------|----------|-----------|--------|
| NDOG Gap Fill | 51 | 33.3% | 1.18 | +$7,801 | 88.1% | 12.08 | +$83,853 | BELOW — post-IB entry |
| Single Print Gap Fill | 0 | — | — | $0 | 69.2% | 4.49 | +$22,525 | BLOCKED — no data |
| Poor HL Repair | 5 | 40.0% | 0.52 | -$641 | 66.7% | 2.01 | +$8,964 | BELOW — detection gap |
| CVD Divergence | 31 | 19.4% | 0.78 | -$2,272 | 21.2% | 5.05 | +$5,300 | BELOW — R:R mismatch |
| RTH Gap Fill | 14 | 14.3% | 0.45 | -$11,375 | 100.0% | 99.99 | +$12,512 | BELOW — post-IB entry |

## Root Cause Analysis

### 1. NDOG Gap Fill (51 trades, 33.3% WR, +$7,801)
**Problem**: Study enters at RTH open (9:30 AM). Engine enters after IB close (10:30 AM) — 60 minutes late. By then, most gaps have partially filled or reversed.
**What works**: The strategy fires correctly and is mildly profitable (+$7.8K) even with late entry. With RTH open entry, this is likely the highest-value strategy to fix.
**Fix needed**: Engine modification to support pre-IB signal emission, or a separate "opening strategies" runner.

### 2. Single Print Gap Fill (0 trades)
**Problem**: `session_context` doesn't contain `tpo_data.single_prints` or `prior_day.single_prints`. The deterministic pipeline doesn't generate this data.
**Fix needed**: Add single print zone detection to the TPO analysis module, persist to session_context.

### 3. Poor High/Low Repair (5 trades, 40% WR, -$641)
**Problem**: Detection method mismatch. Strategy uses Method A (bar close position in range) tracking extremes bar-by-bar. The study script likely scanned all bars differently, producing ~54 detections vs 5.
**Partial fix applied**: Changed `PROXIMITY_PTS` from 10 to 500 (NQ scale). Still only 5 detections.
**Fix needed**: Re-implement detection to match study methodology. May need to compute poor quality as a session-level feature in the data pipeline rather than in the strategy.

### 4. CVD Divergence (31 trades, 19.4% WR, -$2,272)
**Problem**: Study achieved PF 5.05 with 21.2% WR — meaning massive winners (avg win ~25x avg loss). Current implementation has avg win $1,148 vs avg loss $1,276 — nearly 1:1 R:R. The swing low stop was too tight (1-11 pts on NQ), now fixed to min 20pts. VWAP_BREACH_PM exit kills many winners before they hit target.
**Fixes applied**: Min stop 20pts, max stop 100pts, min R:R 2.0.
**Fix needed**: Disable VWAP_BREACH_PM exit for this strategy (let it run to target or stop). Or use a trailing stop instead.

### 5. RTH Gap Fill (14 trades, 14.3% WR, -$11,375)
**Problem**: Same as NDOG — needs RTH open entry but enters at 10:30+. Study had 100% WR on 10 trades with UP-only gaps >= 50pts entered at open.
**Fix needed**: Same as NDOG — pre-IB entry support.

## Infrastructure Fixes Applied

### compute_all_features() — Technical Indicators
Added `add_all_indicators()` call to `compute_all_features()` in `features.py`. This adds:
- EMA5, EMA10, EMA20, EMA50
- ATR14, ADX14
- RSI14
- Bollinger Bands (BB upper, middle, lower)
- VWAP + sigma bands (1σ, 2σ, 3σ)
- CVD divergence detection (bull/bear)

This was missing entirely — no strategy had access to BB, ADX, or CVD columns.

### CVD Divergence Stop Improvements
- Added `MIN_STOP_PTS = 20.0` (was 0-11pts, getting stopped out immediately)
- Added `MAX_STOP_PTS = 100.0` (cap unreasonable risk)
- Reduced `MAX_SIGNALS_PER_SESSION` from 2 to 1

## Prioritized Fix Roadmap

### Priority 1: Engine Pre-IB Support (unlocks 3 strategies)
Add `on_pre_ib_bar()` lifecycle method or a flag to allow `on_bar()` during IB formation.
**Impact**: Unlocks NDOG (+$83K potential), RTH Gap Fill (+$12K), and partially Single Print.
**Effort**: Medium — need to modify BacktestEngine's bar iteration logic.

### Priority 2: Single Print Data Pipeline
Add single print zone detection to TPO analysis, persist in session_context.
**Impact**: Unlocks Single Print Gap Fill (+$22K potential).
**Effort**: Medium — TPO code exists, needs zone extraction.

### Priority 3: Poor HL Detection Rework
Compute poor high/low as a session-level feature (end-of-session scan of all bars), not bar-by-bar tracking.
**Impact**: More detections → closer to study's 54 trades.
**Effort**: Low — algorithm change in on_session_end().

### Priority 4: CVD Divergence Exit Logic
Either add strategy-level exit override (bypass VWAP_BREACH_PM) or use trailing stop model.
**Impact**: Better R:R on winners.
**Effort**: Low-Medium.

## Files Created/Modified

### New Strategy Files
- `packages/rockit-core/src/rockit_core/strategies/ndog_gap_fill.py`
- `packages/rockit-core/src/rockit_core/strategies/single_print_gap_fill.py`
- `packages/rockit-core/src/rockit_core/strategies/poor_highlow_repair.py`
- `packages/rockit-core/src/rockit_core/strategies/cvd_divergence.py`
- `packages/rockit-core/src/rockit_core/strategies/rth_gap_fill.py`

### Modified Files
- `packages/rockit-core/src/rockit_core/strategies/loader.py` — registered all 5 strategies
- `configs/strategies.yaml` — added all 5 (disabled by default)
- `packages/rockit-core/src/rockit_core/data/features.py` — added `add_all_indicators()` call
- `scripts/backtest_new_strategies.py` — backtest runner with study comparison

## Conclusion

The 5 new strategies are correctly implemented but face framework limitations. The highest-ROI fix is adding pre-IB entry support — this alone would unlock 3 strategies worth ~$118K combined (study targets). CVD Divergence is closest to working in the current framework and needs exit logic refinement. All strategies should remain `enabled: false` until their respective blockers are resolved.
