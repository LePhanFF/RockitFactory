# Technical Design Documents — Index

> These documents provide implementation-level specifications for each component.
> They are detailed enough for a coding agent (Qwen 3.5) to implement, with
> Claude Opus 4.6 reviewing for architectural compliance.

## Coding Agent Workflow

```
Opus 4.6 (architect)                  Qwen 3.5 (coder)
─────────────────                     ────────────────
Writes technical design doc    ──►    Reads design doc
                                      Implements code
                                      Writes tests
                                      Runs tests locally
                               ◄──    Submits PR

Reviews PR for:                ──►    Fixes issues
  - Architecture compliance
  - Interface correctness
  - Test coverage
  - Edge cases missed

Approves or requests changes   ──►    Merges to main
```

## Document Map

### Foundation (Phase 0)

| Doc | Component | Type | Status |
|-----|-----------|------|--------|
| [01-conventions.md](01-conventions.md) | Project-wide coding standards | Standards | Draft |
| [02-config-schemas.md](02-config-schemas.md) | YAML/JSON configuration schemas | Schema | Draft |
| [03-metrics-framework.md](03-metrics-framework.md) | MetricsCollector, DuckDB, MetricEvent | New code | Draft |

### Core Library (Phase 1)

| Doc | Component | Type | Status |
|-----|-----------|------|--------|
| [04-strategy-framework.md](04-strategy-framework.md) | StrategyBase, Signal, DayType, registry | Migrate + extend | Draft |
| [05-trade-models.md](05-trade-models.md) | EntryModel, StopModel, TargetModel registry | New code | Draft |
| [06-backtest-engine.md](06-backtest-engine.md) | BacktestEngine, ExecutionModel, PositionManager, Trade | Migrate | Draft |
| [07-filters.md](07-filters.md) | FilterBase, CompositeFilter, 5 filter types | Migrate | Draft |
| [08-indicators.md](08-indicators.md) | ICT models, SMT divergence, technical indicators | Migrate | Draft |
| [09-profiles.md](09-profiles.md) | Volume profile, TPO, DPOC, IB analysis | Migrate | Draft |
| [10-deterministic-modules.md](10-deterministic-modules.md) | Orchestrator, 38 modules, snapshot generation | Migrate + deduplicate | Draft |
| [11-data-and-config.md](11-data-and-config.md) | CSV loader, features, session grouping, instruments | Migrate | Draft |

### API & Infrastructure (Phase 2-3)

| Doc | Component | Type | Status |
|-----|-----------|------|--------|
| [12-data-ingestion.md](12-data-ingestion.md) | CSV watcher, GCS upload | New code | Planned |
| [13-signals-api.md](13-signals-api.md) | FastAPI routes, WebSocket, auth | New code | Planned |

### Agent System (Phase 5)

| Doc | Component | Type | Status |
|-----|-----------|------|--------|
| [14-agent-graph.md](14-agent-graph.md) | LangGraph evidence-gathering pipeline: 4 observers (parallel) → Pattern Miner → Advocate/Skeptic debate → Orchestrator decision | New code | Planned |
| [15-reflection-pipeline.md](15-reflection-pipeline.md) | Outcome logger, scorecards (observer + debate accuracy), reflection, meta-review | New code | Planned |

### Workflows (Cross-Cutting)

| Doc | Component | Type | Status |
|-----|-----------|------|--------|
| [14-strategy-agent-lifecycle.md](14-strategy-agent-lifecycle.md) | Strategy lifecycle (idea → live), agent improvement lifecycle, git workflow | Process | Draft |

### Training & MLOps (Phase 4)

| Doc | Component | Type | Status |
|-----|-----------|------|--------|
| [12-training-mlops.md](12-training-mlops.md) | Training pipeline, evaluation suite, model registry, quantization, benchmarking | New code | Draft |
| [13-automation-infrastructure.md](13-automation-infrastructure.md) | APScheduler, CI/CD (GitHub Actions), Makefile, monitoring, data validation, auto-rollback | New code | Draft |
| [16-training-pipeline.md](16-training-pipeline.md) | Dataset builder, LoRA trainer, evaluator, registry | Migrate + extend | Planned |

---

## How to Read These Documents

Each design doc follows a standard structure:

1. **Purpose** — What this component does
2. **Source** — What existing code is being migrated (file paths, LOC)
3. **Interface** — Full class/function signatures with type hints
4. **Data Flow** — How data moves through the component
5. **Dependencies** — What this component imports/requires
6. **Configuration** — YAML/JSON config the component reads
7. **Metrics** — What MetricEvents this component emits
8. **Migration Notes** — What changes from the original code
9. **Test Contract** — What tests must exist (links to testing-design/)

## Type Conventions in These Docs

- `MIGRATE` — Existing code being moved with minimal changes
- `EXTEND` — Existing code being moved with interface additions (metrics, config)
- `NEW` — Net-new code, no existing source
- `DEDUP` — Module exists in both repos, pick canonical version
