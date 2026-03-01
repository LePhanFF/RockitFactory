# Phase 3: Signals API — Detailed Roadmap

> **Goal:** Build `rockit-serve` — the signals API that doesn't exist today.
> **Duration:** Week 6-9
> **Depends on:** Phase 1 (rockit-core library)
> **Blocks:** Phase 5a (agent system), Phase 5b (dashboard), Phase 5c (clients)

---

## Tasks

### 3.1 FastAPI application skeleton
- [ ] `rockit-serve/app.py` — FastAPI app with CORS, middleware, error handling
- [ ] `rockit-serve/routes/health.py` — Health/readiness probes
- [ ] JWT auth middleware (absorb from existing RockitAPI)
- [ ] Dockerfile for Cloud Run deployment

### 3.2 Deterministic inference endpoints
- [ ] `routes/annotations.py` — GET /api/v1/annotations?instrument=NQ&date=today
- [ ] `routes/setups.py` — GET /api/v1/setups?instrument=NQ
- [ ] `inference/deterministic.py` — runs orchestrator.generate_snapshot() server-side
- [ ] Define annotation JSON schema (zones, levels, signals, trade setups)

### 3.3 WebSocket streaming
- [ ] WSS /api/v1/stream — push annotation updates as new data arrives
- [ ] Emit metrics for WebSocket latency and connection count

### 3.4 Journal endpoints (backward compatibility)
- [ ] Absorb journal routes from existing RockitAPI
- [ ] Maintain API compatibility for existing clients

### 3.5 LLM inference endpoint (optional for this phase)
- [ ] `inference/llm.py` — call Qwen via OpenAI-compatible API
- [ ] Combine deterministic + LLM output in response
- [ ] Can be deferred to Phase 5a (agent system)

### 3.6 Deploy and validate
- [ ] Deploy to GCP Cloud Run (staging)
- [ ] Integration tests against staging API
- [ ] API returns correct annotations for 10+ historical sessions

---

## Definition of Done

- [ ] API returns correct annotations for historical sessions
- [ ] WebSocket stream pushes updates within 1 second
- [ ] Journal endpoints still work (backward compat)
- [ ] Deployed to staging, health check passing
- [ ] API response latency < 200ms for deterministic-only endpoints
