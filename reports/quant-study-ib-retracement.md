# IB Retracement Strategy -- Quant Study Report

**Generated**: 2026-03-12
**Instrument**: NQ (Nasdaq 100 Futures, $20/pt)
**Dataset**: 273 sessions
**Verdict**: NEGATIVE EXPECTANCY -- Do NOT deploy

---

## Strategy Thesis

After the Initial Balance (IB) forms at 10:30 ET, price often retraces 50-61.8%
of the IB range before continuing in the impulse direction. This is a CONTINUATION
trade: enter on the pullback, ride the extension.

### Direction Detection
- Close at 10:30 in top 30% of IB range -> impulse UP -> LONG on retrace down
- Close at 10:30 in bottom 30% of IB range -> impulse DOWN -> SHORT on retrace up
- Close in middle 40% -> no clear impulse -> SKIP

### Entry Logic
1. After IB close (10:30 ET): IB high, low, range established
2. Determine impulse direction from IB close position
3. Wait for retracement into fib zone
4. Confirmation: bar closes back outside zone (rejection)
5. Entry at rejection bar close

### Stop/Target
- LONG stop: IB_LOW - 10pt buffer; SHORT stop: IB_HIGH + 10pt buffer
- Target v1: Opposite IB extreme (continuation to IB edge)
- Target v2: 2R (2x risk distance)
- Target v3: 1.5x IB range from entry

### Filters
- IB range >= minimum threshold (tested: 60, 80, 100, 120, 150)
- Time window: 10:30-12:30 ET only
- Max 1 trade per session
- Skip neutral / neutral_range day types

---

## Results -- All Variants (sorted by Profit Factor)

| # | Variant | Trades | WR% | PF | Net PnL | Avg Win | Avg Loss | Expectancy |
|---|---------|-------:|----:|---:|--------:|--------:|---------:|-----------:|
| 1 | fib=38.2-61.8%, target=opp_ib, ib>=80 | 63 | 58.7% | 0.77 | -$11,343 | $1,056 | -$1,939 | -$180 |
| 2 | fib=50-61.8%, target=1.5x_ib, ib>=80 | 19 | 26.3% | 0.73 | -$6,805 | $3,700 | -$1,808 | -$358 |
| 3 | fib=50-61.8%, target=1.5x_ib, ib>=100 | 19 | 26.3% | 0.73 | -$6,805 | $3,700 | -$1,808 | -$358 |
| 4 | fib=50-61.8%, target=opp_ib, ib>=60 | 25 | 40.0% | 0.68 | -$8,578 | $1,829 | -$1,791 | -$343 |
| 5 | fib=50-61.8%, target=opp_ib, ib>=100 | 23 | 39.1% | 0.68 | -$8,274 | $1,948 | -$1,843 | -$360 |
| 6 | **fib=50-61.8%, target=opp_ib, ib>=80 (baseline)** | **26** | **42.3%** | **0.67** | **-$9,457** | **$1,744** | **-$1,909** | **-$364** |
| 7 | fib=50-70%, target=opp_ib, ib>=80 | 26 | 42.3% | 0.67 | -$9,457 | $1,744 | -$1,909 | -$364 |
| 8 | fib=50-61.8%, target=opp_ib, ib>=80, +VWAP | 33 | 48.5% | 0.67 | -$10,200 | $1,276 | -$1,801 | -$309 |
| 9 | fib=50-61.8%, target=2R, ib>=80 | 19 | 26.3% | 0.66 | -$8,533 | $3,355 | -$1,808 | -$449 |
| 10 | fib=38.2-61.8%, target=opp_ib, ib>=100, +VWAP | 50 | 58.0% | 0.66 | -$15,150 | $1,024 | -$2,136 | -$303 |
| 11 | fib=40-60%, target=opp_ib, ib>=80 | 52 | 55.8% | 0.65 | -$16,073 | $1,043 | -$2,013 | -$309 |
| 12 | fib=50-61.8%, target=opp_ib, ib>=120 | 23 | 39.1% | 0.64 | -$9,659 | $1,948 | -$1,942 | -$420 |
| 13 | fib=50-61.8%, target=opp_ib, ib>=150 | 20 | 40.0% | 0.62 | -$10,127 | $2,048 | -$2,210 | -$506 |
| 14 | fib=50-61.8%, target=2R, ib>=80, +VWAP | 16 | 18.8% | 0.51 | -$12,326 | $4,279 | -$1,936 | -$770 |
| 15 | fib=38.2-61.8%, target=2R, ib>=100 | 10 | 10.0% | 0.03 | -$16,421 | $566 | -$1,887 | -$1,642 |
| 16 | fib=40-60%, target=2R, ib>=80, +VWAP | 9 | 0.0% | 0.00 | -$15,502 | $0 | -$1,722 | -$1,722 |

**Every single variant is negative expectancy.** The best PF achieved is 0.77, far below the 1.0 breakeven threshold.

---

## Detailed Analysis (Baseline: fib=50-61.8%, target=opp_ib, ib>=80)

### By Direction

| Direction | Trades | WR% | PF | Net PnL |
|-----------|-------:|----:|---:|--------:|
| **LONG** | **13** | **30.8%** | **0.31** | **-$11,838** |
| SHORT | 13 | 53.8% | 1.21 | +$2,382 |

**Critical finding**: LONG trades are catastrophically bad (0.31 PF), while SHORT trades are marginally profitable (1.21 PF). The NQ long bias makes shorting on retracement more viable, but even SHORT alone would be thin edge at best.

### By Day Type

| Day Type | Trades | WR% | PF | Net PnL |
|----------|-------:|----:|---:|--------:|
| b_day | 26 | 42.3% | 0.67 | -$9,457 |

**All 26 trades classified as b_day.** This is a structural artifact: the strategy requires price to retrace toward the IB midpoint before continuing. While price is retracing, it stays inside the IB, so the dynamic day-type classifier labels the session as balance. This means the strategy inherently fights against the B-Day thesis (balance = mean reversion, not extension).

### Exit Reason Distribution

| Exit Reason | Count | WR% | Net PnL |
|-------------|------:|----:|--------:|
| STOP | 9 | 0.0% | -$23,832 |
| TARGET | 11 | 100.0% | +$19,185 |
| VWAP_BREACH_PM | 6 | 0.0% | -$4,810 |

- **STOP exits dominate losses**: 9 stops at -$23,832 total (avg -$2,648/stop)
- **VWAP_BREACH_PM**: 6 exits, all losers, -$4,810. These are the engine's PM management kicking in -- price moves against VWAP alignment after 1:00 PM
- **TARGET hits are profitable** but insufficient to overcome stop losses

### Best and Worst Trades

| Rank | Date | Dir | PnL | Exit | Notes |
|------|------|-----|----:|------|-------|
| Best | 2025-04-04 | SHORT | +$3,011 | TARGET | Strong impulse down, clean retrace |
| 2nd | 2025-03-11 | SHORT | +$2,506 | TARGET | |
| 3rd | 2025-04-15 | SHORT | +$2,146 | TARGET | |
| Worst | 2025-04-11 | SHORT | -$4,104 | STOP | Wide IB, stop too far |
| 2nd worst | 2025-04-08 | LONG | -$3,539 | STOP | |
| 3rd worst | 2025-04-23 | LONG | -$2,934 | STOP | |

---

## Key Findings

### 1. Fundamental Thesis Problem
The "IB retracement as continuation" thesis has a structural contradiction on NQ:
- For the retracement to occur, price must move back toward the IB midpoint
- While doing this, the day classifies as a balance day (price inside IB)
- Balance days by definition do NOT extend beyond IB -- they mean-revert
- So the "continuation" part of the thesis rarely materializes

### 2. LONG Trades Are Catastrophic
LONG entries (buying the pullback to fib support) have a 30.8% WR and 0.31 PF. On NQ, when the IB close is in the top 30% (bullish impulse), the retrace often turns into a full reversal rather than a shallow pullback. The stop at IB_LOW - 10 is too far away, creating large losses when stops are hit.

### 3. SHORT Trades Show Marginal Edge (1.21 PF)
SHORT trades (selling the bounce to fib resistance) are marginally profitable at 53.8% WR and 1.21 PF. This aligns with NQ's tendency for bearish impulse days to follow through more cleanly. However:
- Only 13 trades over 273 sessions = ~0.6 trades/month
- 1.21 PF is too thin to survive real-world execution
- Not statistically significant at n=13

### 4. VWAP Breach PM Exit Is Destructive
6 of 26 trades (23%) are closed by the engine's VWAP breach PM management, ALL as losers. The strategy is not exempt from this rule (unlike 80P Rule which is classified as mean reversion). Even if exempted, these trades would likely still lose -- the VWAP breach signals a genuine trend failure.

### 5. Wider Fib Zones Increase Trade Count But Not Profitability
- 38.2-61.8%: 63 trades, 58.7% WR, but PF only 0.77 (still losing)
- 40-60%: 52 trades, 55.8% WR, PF 0.65 (worse)
- Wider zones generate more signals but with lower quality

### 6. IB Range Minimum Has Minimal Impact
Varying the minimum IB range from 60 to 150 pts has almost no effect on profitability. The issue is not trade selection -- it is the fundamental setup logic.

### 7. VWAP Confirmation Does Not Help
Adding VWAP confirmation actually increased trade count (33 vs 26) with similar PF (0.67). This suggests the VWAP filter is not discriminating -- it lets through more marginal trades.

---

## Comparison with Existing Strategies

| Strategy | Trades | WR% | PF | Net PnL | Status |
|----------|-------:|----:|---:|--------:|--------|
| OR Rev | 55 | 76.4% | 5.39 | +$54,630 | LIVE |
| OR Accept | 89 | 64.0% | 3.31 | +$24,839 | LIVE |
| 80P Rule | 54 | 48.1% | 2.32 | +$25,846 | LIVE |
| B-Day | 26 | 57.7% | 1.76 | +$5,767 | LIVE |
| **IB Retracement (best)** | **63** | **58.7%** | **0.77** | **-$11,343** | **REJECTED** |

The IB Retracement strategy is far below the performance floor of any deployed strategy.

---

## Recommendation: REJECT

**Do not deploy this strategy.** The results are conclusively negative across all 16 configurations tested.

### Why It Failed
1. **Wrong market structure**: IB retracements on NQ behave as mean reversion (B-Day), not continuation. The impulse detection from IB close position is a weak signal.
2. **Asymmetric risk**: Stops at IB extremes create large risk distances (avg stop ~100-200 pts on NQ), while targets (opposite IB edge) offer limited reward (~50-100 pts for the retrace portion).
3. **NQ long bias**: LONG entries on pullbacks consistently fail because NQ pullbacks in bullish IB sessions tend to be deeper than expected.

### Possible Salvage Attempts (low probability of success)
1. **SHORT-only with tighter stops**: The SHORT side showed 1.21 PF, but needs more filtering. Could try:
   - Only SHORT when session_bias is Bearish
   - Only SHORT when delta cumulative is negative
   - Tighter stops at fib zone boundary (not IB high)
2. **Different impulse detection**: Instead of IB close position, use:
   - OR close vs IB mid
   - First 15-minute (A-period) direction
   - VWAP slope at IB close
3. **Different entry**: Instead of fib retracement, wait for:
   - 5-minute rejection candle pattern (not just close outside zone)
   - Volume exhaustion at fib level
   - Delta divergence at fib level

### Disposition
- Strategy file: `packages/rockit-core/src/rockit_core/strategies/ib_retracement.py` -- KEEP for reference
- Config: Set `enabled: false` in `configs/strategies.yaml`
- Loader: Registration kept for future re-testing if thesis is revised
