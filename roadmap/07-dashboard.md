# Phase 5b: Dashboard — Detailed Roadmap

> **Goal:** Agent monitoring dashboard — decision support tool.
> **Duration:** Week 12-14
> **Depends on:** Phase 5a (agent API endpoints)
> **Blocks:** Nothing (NinjaTrader and TradingView are parallel)

---

## Tasks

### 5b.1 React/Next.js app skeleton
- [ ] Initialize Next.js project in `packages/rockit-clients/dashboard/`
- [ ] Set up Tailwind CSS, component library
- [ ] Dockerfile for deployment
- [ ] WebSocket hook for agent stream

### 5b.2 Live View page (default)
- [ ] Agent grid showing active/monitoring/error states
- [ ] Live debate feed (streaming advocate/skeptic/consensus)
- [ ] Signal feed with entry/stop/target levels
- [ ] System health gauges (LLM latency, GPU, queue)

### 5b.3 Signals & Outcomes page
- [ ] Signal log with drill-down (full debate, filters, order flow, outcome)
- [ ] Filter by strategy, date, outcome

### 5b.4 Performance page
- [ ] Per-strategy win rate, PF, expectancy (5/10/20/60 day rolling)
- [ ] Confidence calibration chart
- [ ] Equity curve, drawdown analysis
- [ ] Before/after version change comparison

### 5b.5 Reflection & Learning page
- [ ] Daily reflection journals
- [ ] A/B test progress with significance indicator
- [ ] Version timeline
- [ ] Pending adjustment proposals

### 5b.6 Evaluation dashboard (FAQ Q18)
- [ ] 6-layer metrics display (component → strategy → data → LLM → agent → system)
- [ ] Baseline comparison view
- [ ] LLM quality trends over time

---

## Definition of Done

- [ ] Dashboard shows live agent debates during RTH
- [ ] Performance page shows rolling metrics matching DuckDB data
- [ ] Evaluation metrics visible at all 6 layers
- [ ] Deployed and accessible at localhost:3000 (dev) / Cloud Run (prod)
