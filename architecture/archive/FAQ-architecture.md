# Architecture Decision Records

> Concise record of every key architecture decision, with rationale and alternatives considered.
> For detailed design, see the referenced architecture doc.

---

## ADR-01: DuckDB for structured storage (not TimescaleDB/ClickHouse)

**Decision:** Use embedded DuckDB for all structured data (snapshots, signal outcomes, scorecards, debate transcripts, version changes).

**Rationale:** One trader, ~7,500 rows/year. DuckDB is embedded (no separate container), file-backed (easy GCS backup), SQL-native (agents query directly). No operational overhead.

**Upgrade path:** PostgreSQL (with TimescaleDB) if scaling to multiple traders or needing concurrent write throughput.

**Ref:** [08-agent-system.md](08-agent-system.md) Section 8

---

## ADR-02: Structured retrieval over vector RAG

**Decision:** Use DuckDB SQL queries for 90% of retrieval needs. Defer embedding-based RAG to Phase 2.

**Rationale:** Trading data is structured and numerical (IB range, delta, CRI score, day type). SQL exact-match and aggregation are faster, more predictable, and sufficient. Embeddings only needed for unstructured text (reflection journals, Dalton theory docs).

**Phase 2 addition:** ChromaDB/pgvector over reflection journals for open-ended pattern discovery.

**Ref:** [08-agent-system.md](08-agent-system.md) Section 2

---

## ADR-03: Three distinct data activities (not conflated)

**Decision:** Clearly separate deterministic training data (all 259+ sessions, fast, free), multi-agent backtest (90 days, LLM-expensive), and RAG retrieval (all sessions, milliseconds).

**Rationale:** The brainstorm docs conflated these. Each has different data scope, cost, and purpose.

| Activity | Scope | LLM? | Cost |
|----------|-------|------|------|
| Deterministic training data | All 259+ sessions | No | Minutes |
| Multi-agent backtest | 90+ days | Yes (~10,900 calls) | 4-8 hours GPU |
| Structured retrieval | All sessions | No | Milliseconds |

**Ref:** [08-agent-system.md](08-agent-system.md) Section 6

---

## ADR-04: Composable entry/stop/target models via YAML registry

**Decision:** Entry, stop, target, and trail models are separate abstract classes with concrete implementations, composed via YAML config per strategy.

**Rationale:** Current strategies hardcode entry/stop/target logic inline. Composable models allow mixing (e.g., UnicornICT entry + ATR stop + 2R target) without modifying strategy code.

**Registry pattern:**
```python
ENTRY_MODELS = {"unicorn_ict": UnicornICTEntry, "orderflow_cvd": OrderFlowCVDEntry, ...}
STOP_MODELS = {"1_atr": ATRStop, "lvn_hvn": LVNHVNStop, ...}
TARGET_MODELS = {"2r": RMultipleTarget, "fvg_trail_be": FVGTrailToBE, ...}
```

**YAML composition:**
```yaml
strategies:
  TrendDayBull:
    entry_model: unicorn_ict
    stop_model: 1_atr
    target_model: 2r
```

**Ref:** [technical-design/05-trade-models.md](../technical-design/05-trade-models.md)

---

## ADR-05: One LoRA adapter, prompt-driven agent specialization

**Decision:** Single Qwen3.5 model + one LoRA adapter for all agent roles. Differentiation via system prompts.

**Alternatives rejected:**
- Per-agent LoRA (3-8 adapters, tiny datasets each, swap overhead)
- Per-strategy LoRA (16 adapters, management nightmare)

**Rationale:** Domain knowledge (market structure, Dalton theory, order flow) is shared across all agents. What differs is reasoning stance (argue for vs against vs synthesize) — exactly what system prompts excel at.

**Training data:** Existing ROCKIT v5.6 dataset (`{input: snapshot, output: analysis}`) teaches market understanding that serves all roles. Role-specific examples added in Phase 2.

**Ref:** [08-agent-system.md](08-agent-system.md) Section 1

---

## ADR-06: LangGraph for agent orchestration

**Decision:** Use LangGraph for the multi-agent debate pipeline.

**Alternatives rejected:**
- CrewAI (too high-level, no precise conditional routing)
- AutoGen (over-featured for strict debate protocol)
- Raw Python (would reinvent state mgmt, streaming, checkpointing)

**Key features used:** Conditional edges (debate only when confidence < threshold), state management, streaming to dashboard, checkpointing for replay/debug.

**Ref:** [08-agent-system.md](08-agent-system.md) Section 1

---

## ADR-07: Docker Compose, not Kubernetes

**Decision:** Three containers (rockit-serve, LLM, dashboard) via Docker Compose. No Kubernetes.

**Rationale:** One trader, one GPU, one system. Kubernetes adds operational complexity with zero benefit at this scale. `restart: always` handles crashes. `docker compose up -d` handles deploys.

**Upgrade path:** Cloud Run for the API layer if serving multiple traders. DGX uses systemd for auto-start.

**Ref:** [12-deployment.md](12-deployment.md)

---

## ADR-08: Three-tier model hierarchy

**Decision:**
- **Tier 0:** Deterministic Python rules (<10ms, no LLM)
- **Tier 1:** Qwen3.5 local (agent debates, daily reflection)
- **Tier 2:** Opus 4.6 API (meta-review every 1-3 days)

**Rationale:** Most signals don't need LLM debate (high-confidence deterministic). Agent debates use fast local model. Only meta-review uses expensive API calls — amortized over days.

**Cost:** Tier 0 free, Tier 1 free (local GPU), Tier 2 ~$2-5/meta-review (every 3 days).

**Ref:** [08-agent-system.md](08-agent-system.md) Section 1

---

## ADR-09: Self-modification boundaries (autonomous/reviewed/never)

**Decision:** Three tiers of self-modification:
1. **Autonomous** (Qwen3.5): Confidence thresholds +-10%, filter params within bounds, prompt emphasis shifts
2. **Requires Opus review**: Full prompt rewrites, filter changes, strategy enable/disable, risk params
3. **Never autonomous**: Account risk limits, instruments, prop firm rules, infrastructure

**Guard:** Auto-rollback if win rate <30% in 3 sessions after change, or session loss >2x rolling average.

**Ref:** [08-agent-system.md](08-agent-system.md) Section 5

---

## ADR-10: 6-layer evaluation framework (Measure Everything)

**Decision:** Every layer of the system emits metrics, all flowing to DuckDB. No change ships without measurable comparison to baseline.

| Layer | What | Example Metric |
|-------|------|---------------|
| 1. Component | Individual module output | FVG detection precision |
| 2. Strategy | Per-strategy trading performance | Win rate, PF per strategy |
| 3. Data Quality | Schema compliance, completeness | Snapshot field coverage |
| 4. LLM Quality | Model accuracy pre/post training | Day type accuracy |
| 5. Agent Quality | Agent value-added over deterministic | Consensus override accuracy |
| 6. System | End-to-end trading performance | Net P&L, Sharpe, drawdown |

**Evaluation gates block deployment:**
```yaml
gates:
  component: "All 38 modules produce valid output"
  strategy: "Win rate >= baseline - 5%, PF >= baseline - 0.15"
  data_quality: "Schema compliance >= 98%"
  llm_quality: "Day type accuracy >= 65%"
  system: "Max drawdown <= baseline + $500"
```

**Ref:** [roadmap/10-evaluation.md](../roadmap/10-evaluation.md), Design Principle #5 in [01-overview.md](01-overview.md)

---

## ADR-11: Walk-forward validation for self-learning

**Decision:** Validate self-learning improvements via walk-forward backtesting — train on period A (e.g., Sept-Nov 2025), test on unseen period B (Jan-Feb 2026), compare with vs without improvements.

**Protocol:**
1. Run system WITHOUT improvements on test period → baseline metrics
2. Run system WITH improvements on same test period → improved metrics
3. Compare. Improvement must be statistically significant (p < 0.05 over 40+ sessions).

**GPU cost:** ~16,942 LLM calls, 6-8 hours on DGX.

---

## ADR-12: Multi-agent coding workflow (Qwen 3.5 codes, Opus 4.6 reviews)

**Decision:** Use multiple Qwen 3.5 coding agents for implementation, with Opus 4.6 as architect/reviewer.

**Workflow:**
```
Opus 4.6 → writes technical design doc → Qwen 3.5 → implements code + tests → Opus 4.6 reviews PR
```

**Parallelism:** Multiple Qwen agents work on independent packages simultaneously (e.g., one on filters, one on indicators).

**Guard rails:** Technical design docs are detailed enough for implementation without ambiguity. Architecture compliance checked on every PR.

**Ref:** [technical-design/00-index.md](../technical-design/00-index.md)

---

## ADR-13: Industry validation

The Rockit architecture draws from proven patterns:

| Our Pattern | Industry Precedent |
|-------------|-------------------|
| Advocate/Skeptic consensus | TradingAgents (Columbia U, LangGraph multi-agent trading) |
| LoRA fine-tuning for finance | FinGPT / FinLoRA (Columbia U, validated on stock prediction) |
| Agent-based trading systems | FinRL (Columbia U, RL for trading) |
| Structured retrieval over RAG | Common in financial systems (structured data > embeddings) |
| Daily reflection loop | Novel for trading, standard in ML experiment tracking |

**Ref:** TradingAgents paper, FinGPT framework, FinRL library

---

## ADR-14: YAML-driven strategy configuration

**Decision:** Strategy behavior (enabled/disabled, entry/stop/target models, instrument, risk) is configured via YAML. No code changes for configuration.

```yaml
strategies:
  TrendDayBull:
    enabled: true
    applicable_day_types: [TREND, SUPER_TREND]
    instruments: [NQ, MNQ]
    max_risk_per_trade: 400.0
    entry_model: unicorn_ict
    stop_model: 1_atr
    target_model: 2r
```

**Rationale:** Reduces code churn. Strategy enable/disable, risk parameters, and model composition change via config without PRs.

**Ref:** [technical-design/04-strategy-framework.md](../technical-design/04-strategy-framework.md)

---

## ADR-15: Annotation protocol (API provides instructions, clients execute)

**Decision:** The API serves two things: annotations (what to draw) and trade setups (what trades to take). Clients are thin renderers/executors.

**Key:** Entry price, stop price, targets, trail rules come from the API. NinjaTrader fills the order, sets the stop, manages the trail locally. The API does not manage positions.

**Ref:** [04-platform-abstraction.md](04-platform-abstraction.md)

---

## ADR-16: GCS direct upload, then API push (no Google Drive)

**Decision:** Replace Google Drive sync with:
1. **Phase 1:** Local file watcher → GCS upload (2-5s latency, minimal change)
2. **Phase 2:** Direct API push (sub-second, requires signals API)
3. **Phase 3:** Pub/Sub streaming (if needed for multi-consumer)

**Start with Phase 1** because the signals API doesn't exist yet.

**Ref:** [05-data-ingestion.md](05-data-ingestion.md)
