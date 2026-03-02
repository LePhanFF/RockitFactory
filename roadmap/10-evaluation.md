# Cross-Cutting: Evaluation & Metrics — Detailed Roadmap

> **Goal:** 6-layer metrics framework implemented incrementally from Phase 0 onward.
> **This is not a separate phase — it's built into every phase.**

---

## Implementation by Phase

### Phase 0: Infrastructure
- [ ] MetricsCollector + DuckDB backend
- [ ] MetricEvent dataclass
- [ ] NullCollector for tests
- [ ] DuckDB schema for all 6 metric tables

### Phase 1: Component + Strategy metrics
- [ ] Every indicator/filter emits metrics (Layer 1)
- [ ] Strategy metrics per session (Layer 2)
- [ ] Data quality metrics for snapshot generation (Layer 3)
- [ ] Initial baseline from 259-session backtest (configs/baselines/v1.0.0.json)

### Phase 3: API metrics
- [ ] Request latency, error rates
- [ ] WebSocket connection metrics

### Phase 4: LLM quality metrics (Layer 4)
- [ ] Holdout evaluation set
- [ ] Pre/post training comparison
- [ ] Model evaluation gates

### Phase 5a: Agent metrics (Layer 5)
- [ ] Agent value-added measurement
- [ ] Confidence calibration
- [ ] Per-agent scorecards

### Phase 5b: System metrics dashboard (Layer 6)
- [ ] Rolling P&L, Sharpe, drawdown
- [ ] Full 6-layer evaluation dashboard view
- [ ] Baseline comparison view

---

## See FAQ Q18 for full framework specification.
