# Phase 5c: Platform Clients — Detailed Roadmap

> **Goal:** NinjaTrader thin client + TradingView indicator consuming the signals API.
> **Duration:** Week 14+
> **Depends on:** Phase 3 (API), Phase 5b (dashboard validates correctness)

---

## Tasks

### 5c.1 NinjaTrader thin client (full rewrite)
- [ ] `RockitIndicator.cs` (~150 LOC) — polls API, draws annotations on chart
- [ ] `RockitStrategy.cs` (~150 LOC) — fills trades from API setups, manages stops/trails locally
- [ ] Test in NinjaTrader Sim/Playback against API
- [ ] Verify annotations match dashboard (same API, same output)

### 5c.2 TradingView indicator (net-new)
- [ ] `rockit_indicator.pine` — webhook-driven annotation display
- [ ] Set up webhook integration with rockit-serve
- [ ] Test with TradingView paper trading

### 5c.3 Validation
- [ ] NinjaTrader, TradingView, and Dashboard all show identical annotations for same session
- [ ] NinjaTrader fills trades at prices API specifies
- [ ] Client-side stop/trail management works correctly

---

## Definition of Done

- [ ] NinjaTrader paints annotations from API (visual match with dashboard)
- [ ] NinjaTrader strategy fills trades at API prices
- [ ] All three clients display consistent information from same API
