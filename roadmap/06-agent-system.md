# Phase 5a: Agent System — Detailed Roadmap

> **Goal:** LangGraph agents with debate protocol, self-learning reflection loop.
> **Duration:** Week 10-12
> **Depends on:** Phase 3 (API), Phase 4 (trained model)
> **Blocks:** Phase 5b (dashboard needs agent API), Phase 5c (clients need signals)

---

## Tasks

### 5a.1 LangGraph agent graph
- [ ] `rockit-serve/agents/graph.py` — StateGraph with conditional routing
- [ ] Nodes: evaluate_deterministic, check_historian, advocate, skeptic, orchestrator, risk_check, emit_signal
- [ ] Conditional edges: should_debate (confidence threshold), consensus_decision, risk_approved
- [ ] State checkpointing via MemorySaver

### 5a.2 Agent nodes
- [ ] `nodes/advocate.py` — argues FOR signal with evidence
- [ ] `nodes/skeptic.py` — challenges signal, identifies risks
- [ ] `nodes/orchestrator.py` — synthesizes debate, consensus decision (TAKE/SKIP/REDUCE_SIZE)
- [ ] `nodes/historian.py` — DuckDB structured retrieval for similar sessions
- [ ] `nodes/risk_check.py` — position limits, max drawdown gates

### 5a.3 Model integration
- [ ] `agents/model.py` — Qwen 3.5 via Ollama/vLLM (tier: local)
- [ ] Opus 4.6 via Anthropic API (tier: opus, for meta-review only)
- [ ] Agent prompt templates (versioned in configs/agents/prompts/)

### 5a.4 Streaming to dashboard
- [ ] `agents/runner.py` — async generator streaming debate tokens via WebSocket
- [ ] Agent state changes broadcast to connected clients

### 5a.5 Self-learning reflection loop
- [ ] Outcome Logger (post-market cron, pure Python, no LLM)
- [ ] Per-agent scorecards
- [ ] Daily reflection (Qwen3.5)
- [ ] Meta-review (Opus 4.6, every 1-3 days)
- [ ] Version Manager (prompt/param versioning with rollback)
- [ ] Auto-rollback guards

### 5a.6 Walk-forward validation
- [ ] Implement WalkForwardValidator (FAQ Q17)
- [ ] Run Sept-Nov 2025 train → Jan-Feb 2026 test
- [ ] Validate self-learning improves OOS performance

### 5a.7 Multi-agent backtest
- [ ] 90-day replay with full debate + reflection
- [ ] Compare agent_adaptive vs deterministic_only
- [ ] Establish baseline for agent value-added metrics

---

## Definition of Done

- [ ] Agent debate produces structured TAKE/SKIP decisions
- [ ] Historian retrieves relevant historical context
- [ ] Daily reflection runs and produces adjustment proposals
- [ ] Walk-forward validation shows OOS improvement
- [ ] Agent-level metrics logged (FAQ Q18 Layer 5)
- [ ] Auto-rollback triggers correctly when metrics degrade
