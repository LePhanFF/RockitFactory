# NWOG Gap Fill Strategy — Implementation Document

> **Date**: 2026-03-09
> **Sources**: `02-nwog-study.md` (our quant study), `03-nwog-online-research.md` (ICT/online)

---

## 1. Feature Comparison: Our Rules vs. ICT/Online

| Feature | Our Study | ICT/Online | Gap |
|---------|-----------|------------|-----|
| Gap definition | Friday RTH close to Monday Globex open | Friday 5pm close to Sunday 6pm open | Minor timing diff |
| Gap fill target | Full gap (Friday close) | Full gap + CE (50% midpoint) as partial | **We lack CE partial target** |
| Min gap size | 20 pts | No explicit minimum | Online more permissive |
| VWAP filter | Price on fill side at 10:00 (88.2% fill) | Not mentioned | **Our unique edge** |
| 30-min acceptance | >=30% bars on fill side (100% fill) | Not mentioned | **Our unique edge** |
| Entry time | 10:00 AM (after acceptance check) | Various: London open, NY open, 9:30 | Similar |
| Stop | 60-75 pts fixed | Structural (swing high/low) | Different approach |
| Target | Full gap fill only | CE first, then full gap | **We miss partial scaling** |
| Time stop | 13:00 (not in study, proposed) | No explicit time stop | Gap-up |
| Monday only | Yes (highest fill probability) | Any day (NDOG variant) | Online broader |
| Directional asymmetry | DOWN gaps 73.1% vs UP 42.9% fill | Not quantified | **Our unique finding** |
| ERL/IRL | Not used | External/Internal Range Liquidity alignment | **Gap** |
| Multi-timeframe | Not used | Weekly/daily alignment | **Gap** |
| VIX filter | Not used | Implied: avoid extreme vol | **Gap** |
| S/R role | Not used | Unfilled NWOGs act as S/R levels | **Gap** |

## 2. Gaps Identified (What Online Research Adds)

1. **CE (Consequent Encroachment)**: 50% of gap = most reactive level. We should add this as a partial target (scale 50% at CE, hold 50% for full gap fill).

2. **ERL/IRL alignment**: If external range liquidity (prior week high/low) aligns with gap fill direction, higher probability. We can proxy this with prior week range.

3. **NWOG as persistent S/R**: Unfilled NWOGs from prior weeks remain active. We only trade current-week gaps — could extend to check unfilled gaps.

4. **VIX filter**: Our study didn't test VIX impact. Given 80P and 20P show VIX sensitivity, likely relevant for NWOG too. Add VIX < 25 as a qualifying condition.

5. **NDOG (daily gap)**: Same concept applied to daily close → next open. Could be a follow-on strategy using same logic.

## 3. Combined Rule Set (Best of Both)

### Rule Set A (Our Study Only)
- Monday only, gap >= 20 pts
- VWAP on fill side at 10:00
- >=30% acceptance in first 30 min
- Entry at 10:00 bar close
- Stop: 75 pts fixed
- Target: full gap fill (Friday close)
- Time stop: 13:00

### Rule Set B (Combined = Our Study + Online Additions)
All of Rule Set A, plus:
- VIX filter: skip if VIX > 25
- CE partial target: scale 50% at gap midpoint
- Wider acceptance: >=25% instead of 30% (more inclusive)
- EMA20 alignment: require 5-min EMA20 on fill side
- Persistent NWOG tracking: check if prior unfilled NWOGs align

## 4. A/B Test Plan

| Run | Description | Key Difference |
|-----|-------------|----------------|
| A | Rule Set A (our rules only) | Baseline |
| B | Rule Set B (combined) | VIX + CE + EMA20 + looser acceptance |

**Metrics to compare**: trades, WR%, PF, avg win, avg loss, max DD, net PnL per trade.

**Expected**: Rule Set A produces ~10 trades/year at 70% WR. Rule Set B may increase trade count (looser acceptance) but CE partial scaling could reduce average win.

---

## 5. Implementation Notes

- Strategy class: `NWOGGapFill(StrategyBase)`
- Stop model: `fixed_75pts` (add to registry)
- Target model: Use `Signal.target_price` = Friday close (full gap)
- Day-of-week check: `datetime.strptime(session_date, '%Y-%m-%d').weekday() == 0`
- Prior Friday close: from `session_context['prior_close']`
- Monday open: first bar's open price in `on_session_start`
- Time stop: check `bar_time >= 13:00` in `on_bar`, return close signal

## 6. Data Requirements

All available in existing pipeline:
- 1-min bars with OHLCV + VWAP (have)
- Prior session close (have via `prior_close` in session_context)
- Day of week (derivable from session_date)
- VIX (have via regime_context.py, in deterministic tape)
