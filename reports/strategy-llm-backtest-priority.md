# Strategy LLM Backtest Priority List

*Generated: 2026-03-12*
*Based on: 15 quant studies + Run E backtest (272 sessions)*

## Current Production Portfolio (already LLM-tested in Run E)

| Strategy | Trades | WR | PF | Net PnL | LLM Impact | Status |
|----------|--------|-----|-----|---------|------------|--------|
| OR Reversal | 52 | 73.1% | 4.48 | $48,650 | +$3K vs no-LLM | LIVE |
| OR Acceptance | 72 | 66.7% | 3.71 | $21,598 | +$2K | LIVE |
| 80P Rule | 48 | 45.8% | 2.48 | $24,113 | +$5K (re-admits) | LIVE |
| 20P IB Extension | 32 | 53.1% | 2.61 | $14,672 | +$2K | LIVE |
| B-Day | 22 | 54.5% | 1.51 | $3,636 | +$3K | LIVE |

**Run E total**: 226 trades, 60.6% WR, PF 3.07, $112,669

---

## Priority 1: DEPLOY — Build & LLM Backtest

These strategies have proven edges and should be implemented, then backtest with LLM debate.

### 1a. NDOG Gap Fill
- **Study**: 42 trades, 88.1% WR, PF 12.08, $83,853
- **Config**: rth_open entry, gap >= 20pt, fixed_75 stop, full_fill target, 13:00 time stop, +VWAP confirm
- **Why LLM**: LLM can evaluate gap context (was gap into supply? demand?) and overnight auction quality
- **Expected LLM value**: HIGH — gap fill is context-dependent, LLM debate should filter false gaps

### 1b. NWOG Gap Fill (tuned)
- **Study**: 17 trades (DOWN gaps), 78% WR, PF 12.20
- **Config**: Monday-only, gap >= 20pt, VWAP + 30% acceptance, 75pt stop, Friday close target
- **Why LLM**: Weekly gap context, multi-day structure evaluation
- **Expected LLM value**: MEDIUM — already highly filtered mechanically

### 1c. Single Print Gap Fill
- **Study**: 117 trades, 69.2% WR, PF 4.49, $22,525
- **Config**: min_10 ticks, above_vah, immediate entry, atr_1x stop, 2R target, morning
- **Why LLM**: LLM can evaluate whether single prints are structural (worth filling) vs exhaustion
- **Expected LLM value**: HIGH — single print quality varies by context

### 1d. Poor High/Low Repair
- **Study**: 54 trades, 66.7% WR, PF 2.01, $8,964
- **Config**: spike stop, 2R target, poke_min >= 8, morning window
- **Why LLM**: LLM evaluates whether poor structure will be repaired (auction incomplete) vs intentional
- **Expected LLM value**: HIGH — requires contextual judgment

### 1e. CVD Divergence (standalone + filter)
- **Study**: 33 trades, 21.2% WR, PF 5.05, $5,300 (standalone); also viable as filter
- **Config**: cvd_div_bb, ADX < 25, swing_low stop, VWAP target, after_ib, LONG only
- **Why LLM**: Divergence significance depends on market regime and volume context
- **Expected LLM value**: MEDIUM — low WR means each trade matters, LLM can filter noise
- **Also**: Deploy as confirmation filter on 80P Rule and OR Reversal

---

## Priority 2: BUILD & TEST — Needs Strategy Code

These need strategy implementation before they can be LLM-tested.

### 2a. RTH Gap Fill (high-conviction)
- **Study**: 10 trades, 100% WR, PF 99+, $12,512 (UP gaps + VWAP confirm); 183 trades, PF 1.66, $155K (volume config)
- **Why LLM**: Gap fill direction + overnight auction quality + regime evaluation
- **Expected LLM value**: HIGH — VWAP confirmation model is mechanical, LLM adds context
- **Action needed**: Build `RTHGapFillStrategy` class, register in strategies.yaml

### 2b. PDH/PDL Reaction
- **Study**: 27 trades, 59.3% WR, PF 1.52 (Setup A, spike stop, 2R)
- **Why LLM**: Prior day level significance varies by context (trend continuation vs reversal)
- **Expected LLM value**: MEDIUM — tight mechanical filter already, LLM marginal
- **Action needed**: Build `PDHPDLReactionStrategy` class

---

## Priority 3: FILTER ONLY — Add as Agent Enhancement

These are better as filters/overlays than standalone strategies.

| Filter | Apply To | Expected Impact |
|--------|----------|-----------------|
| CVD Divergence | 80P LONG, OR Rev | Require cvd_div_bull for LONG, cvd_div_bear for SHORT |
| IB Retracement v2 | All strategies on wide IB days | When IB >= 300 + sweep + VWAP confirm → boost confidence |
| VWAP Sigma Bands | Mean Reversion | ADX < 25 gate + sigma_2 bands for entry zones |

---

## Priority 4: MONITOR — Not Ready for LLM Backtest

| Strategy | Verdict | Issue | Next Step |
|----------|---------|-------|-----------|
| VA Edge Fade v2 | SHORT-ONLY | LONG side loses money | Build SHORT-only variant, retest |
| IB Edge Fade | MARGINAL | PF 1.39, needs work | Not worth LLM compute yet |
| VWAP Sigma Bands | MARGINAL | PF 1.75, 44.6% WR | ADX < 25 gate helps, but not enough edge |
| MR VWAP | SHORT-ONLY | 91% SHORT trades | Monitor SHORT-only performance |
| BB Extreme | PENDING | Study still running | Wait for results |

---

## Priority 5: DISABLED — Do Not Backtest

| Strategy | Verdict | Why |
|----------|---------|-----|
| Trend Day Bull/Bear | DISABLED | 40+ configs tested, all negative or breakeven. VWAP pullback model fundamentally flawed |
| VA Edge Fade (v1) | NOT VIABLE | 33-36% WR vs 70% target. Replaced by v2 SHORT-only |
| IB Retracement (v1) | NEGATIVE | 0.31 PF on LONG, only marginally positive SHORT |

---

## LLM Backtest Execution Plan

### Phase 1: Production Portfolio Re-run (IN PROGRESS)
- **Run E with SKIP logging**: Currently running (`ab_test_agents.py --debate-only`)
- Records all agent SKIP decisions with baseline cross-reference
- Will show: "Trade X was SKIPPED by LLM → baseline shows it WOULD have been a $Y winner/loser"
- ETA: ~3-4 hours remaining

### Phase 2: New Strategies (after Phase 1)
Build and register strategies, then run `ab_test_agents.py --enable-debate`:
1. NDOG Gap Fill → `NDOGGapFillStrategy`
2. Single Print Gap Fill → `SinglePrintGapFillStrategy`
3. Poor High/Low Repair → `PoorHighLowRepairStrategy`
4. RTH Gap Fill → `RTHGapFillStrategy`
5. CVD Divergence → `CVDDivergenceStrategy`

For each: Run A (baseline) + Run E (LLM debate) with full SKIP logging.

### Phase 3: Filter Integration
Add CVD divergence and IB retracement as filters in `configs/filters.yaml`.
Re-run portfolio with enhanced filters + LLM debate.

---

## Key Recording Requirements

For ALL LLM backtests, record in DuckDB `agent_decisions`:
- `decision`: TAKE / SKIP / REDUCE_SIZE
- `reasoning`: Full LLM debate summary
- `advocate_confidence`: 0.0-1.0
- `skeptic_confidence`: 0.0-1.0
- `actual_pnl`: Cross-referenced against baseline for SKIPs
- `actual_outcome`: WIN/LOSS (from baseline for SKIPs)

This enables post-hoc analysis of LLM decision quality:
- "LLM SKIPPED 50 trades → 30 would have been losses, 20 winners → net saved $X"
- "LLM TOOK 180 trades → vs baseline 200, WR improved by X%"
