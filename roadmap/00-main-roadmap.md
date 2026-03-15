# RockitFactory Main Roadmap

> Master roadmap linking all phases and sub-roadmaps.
> Each phase has its own detailed sub-roadmap with tasks, acceptance criteria, and dependencies.

---

## Roadmap Overview

```
Phase 0 ──► Phase 1a ──► Phase 1b ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6
Foundation   Proven       Full         Data        Signals     Training    Agents &     Retire
             Strategies   Core Lib     Ingestion   API         Pipeline    Dashboard    Old Repos
Week 1-2     Week 2-4     Week 4-6     Week 5-6    Week 6-9    Week 8-11   Week 10-14   Week 16+
                                       (parallel)              (parallel)  (parallel)
```

### Phase Dependencies

```
Phase 0 (Foundation)
  └──► Phase 1a (Proven Strategies — PRIORITY 1)
         └──► Phase 1b (Full Core Library) ──────────────┐
                ├──► Phase 2 (Data Ingestion) [overlap]   │
                ├──► Phase 3 (Signals API) ◄──────────────┘
                │      └──► Phase 5a (Agent System)
                │             ├──► Phase 5b (Dashboard)
                │             └──► Phase 5c (NinjaTrader Client)
                └──► Phase 4 (Training Pipeline)  [can overlap with Phase 3]
                       └──► Phase 5a (Agent System)  [needs trained model]

Phase 6 (Retire Old Repos) ◄── All phases complete + 2 weeks parallel operation
```

---

## Phase Summary

| Phase | Name | Goal | Detailed Roadmap | Status |
|-------|------|------|-----------------|--------|
| 0 | Foundation | Monorepo skeleton, dev environment, CI | [01-foundation.md](01-foundation.md) | Not started |
| 1a | **Proven Strategies** | **Migrate proven profitable strategies first: 20% rule, 80% rule, balance day, opening reversal, opening acceptance. Backtest engine + these strategies + supporting filters/indicators.** | [02a-proven-strategies.md](02a-proven-strategies.md) | Not started |
| 1b | Full Core Library | Migrate remaining strategies, all deterministic modules, entry/stop/target model registry | [02b-core-library.md](02b-core-library.md) | Not started |
| 2 | Data Ingestion | Replace Google Drive sync with GCS direct upload | [03-data-ingestion.md](03-data-ingestion.md) | Not started |
| 3 | Signals API | Build `rockit-serve` with annotation + trade setup endpoints | [04-signals-api.md](04-signals-api.md) | Not started |
| 4 | Training Pipeline | LLM tape reader: V2 schema, 20K+ pairs, Qwen3.5 LoRA | [05-training-pipeline.md](05-training-pipeline.md) | **In progress** — V1 schema + 164 pairs + scripts done |
| 5a | Agent System | Tape reader + Advocate/Skeptic/Orchestrator + DuckDB | [06-agent-system.md](06-agent-system.md) | **Designing** — brainstorm/07 whiteboard (2100+ lines) |
| 5b | Dashboard | Agent monitor, signals view, performance charts | [07-dashboard.md](07-dashboard.md) | Not started |
| 5c | Platform Clients | NinjaTrader thin client, TradingView indicator | [08-platform-clients.md](08-platform-clients.md) | Not started |
| 6 | Retire Old Repos | Archive originals, RockitFactory becomes single source | [09-retire-repos.md](09-retire-repos.md) | Not started |

---

## Cross-Cutting Concerns (Apply to Every Phase)

| Concern | Sub-Roadmap | Description |
|---------|------------|-------------|
| Evaluation & Metrics | [10-evaluation.md](10-evaluation.md) | 6-layer metrics framework, baseline system, evaluation gates — implemented incrementally from Phase 0 onward |
| Entry/Stop/Target Models | [11-trade-models.md](11-trade-models.md) | Composable entry, stop, and target model registry — designed in Phase 0, built in Phase 1 |
| Testing | [12-testing.md](12-testing.md) | Testing pyramid by phase — what tests exist at each stage |

---

## Milestones & Validation Gates

| Milestone | Validation | Phase |
|-----------|-----------|-------|
| `make setup && make test` works | Empty test suite passes, packages importable | Phase 0 |
| Proven strategies backtest validated | 20% rule, 80% rule, balance day, OR, OA produce expected signals | Phase 1a |
| Backtest engine runs end-to-end | Engine + proven strategies + filters produce trade results | Phase 1a |
| Full 259-session backtest matches original | Output comparison, zero diff | Phase 1b |
| Deterministic snapshots match original | Snapshot comparison, zero diff | Phase 1b |
| CSV → GCS within 5 seconds | Latency measurement during live session | Phase 2 |
| API returns correct annotations for historical sessions | Integration test suite | Phase 3 |
| WebSocket streams updates < 1s | Latency measurement | Phase 3 |
| LoRA training completes and passes eval gates | Model evaluation vs holdout set | Phase 4 |
| Multi-agent backtest over 90 days completes | Performance report generated | Phase 5a |
| Walk-forward validation shows OOS improvement | A/B comparison across 2+ windows | Phase 5a |
| Dashboard shows live agent debates | Manual verification during RTH | Phase 5b |
| NinjaTrader paints annotations from API | Visual verification vs dashboard | Phase 5c |
| 2 weeks parallel operation, no regressions | Comparison report | Phase 6 |

---

## What This Roadmap Does NOT Cover

- **Individual strategy development** — Adding new strategies (e.g., new entry models) happens continuously after Phase 1b. Each strategy follows the lifecycle workflow (see [technical-design/14-strategy-agent-lifecycle.md](../technical-design/14-strategy-agent-lifecycle.md)).
- **Model experiments** — Trying Qwen 70B, different LoRA ranks, etc. happens after Phase 4. Each experiment is tracked in MLflow.
- **Prop firm integration** — Future scope, not in this roadmap.
- **Multi-instrument expansion** — Adding CL, GC, etc. is post-Phase 6.

---

## Project Management

This roadmap is designed to work with lightweight project management:

### Option A: GitHub Issues + Projects (Recommended)
- Each sub-roadmap maps to a GitHub Milestone
- Each task in a sub-roadmap maps to a GitHub Issue
- GitHub Projects board for Kanban-style tracking
- Labels: `phase-0`, `phase-1`, etc. + `blocked`, `in-progress`, `done`
- Free, integrated with the repo, PRs link to issues

### Option B: Linear
- If GitHub Projects feels too lightweight
- Better for timeline visualization and sprint planning
- Syncs with GitHub for PR linking

### Option C: Notion / Markdown-only
- Keep everything in this `roadmap/` folder
- Update status manually in the markdown files
- Simplest, no external tools, but no automation

**Recommendation:** Start with GitHub Issues + Projects. It's free, it's where the code lives, and you can always migrate to Linear later if needed. Each sub-roadmap below can be converted to issues with a script.
