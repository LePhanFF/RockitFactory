# Deployment Architecture

## Key Decision: Agents Are Not Containers

Rockit agents (Advocate, Skeptic, Orchestrator, Historian, Risk Manager) are **nodes in a LangGraph graph**, not separate services. They run as function calls within a single Python process (`rockit-serve`). No inter-service communication, no Kubernetes, no service mesh.

```
What agents are:                         What agents are NOT:
────────────────                         ───────────────────
Functions in a graph                     Separate containers
Called sequentially/conditionally         Microservices
Share memory (graph state)               Communicate via HTTP/gRPC
All in one process                       Require orchestration platform
LangGraph handles flow                   Need Kubernetes
```

---

## Production Deployment: Docker Compose

Three containers. That's the entire system.

```
┌─────────────────────────────────────────────────────────────┐
│                   DEPLOYMENT (Docker Compose)                │
│                                                              │
│  ┌──────────────────────┐      ┌──────────────────────┐    │
│  │  rockit-serve          │      │  LLM (Ollama/vLLM)   │    │
│  │  ──────────────────    │      │  ─────────────────    │    │
│  │  FastAPI server        │─────▶│  Qwen3.5-32B         │    │
│  │  LangGraph agents      │ HTTP │  OpenAI-compatible    │    │
│  │  WebSocket streaming   │      │  API                  │    │
│  │  Reflection cron       │      │                       │    │
│  │  DuckDB (embedded)     │      │  GPU: 1x A100 or      │    │
│  │                         │      │  Mac Mini M4          │    │
│  │  Port 8000              │      │  Port 11434           │    │
│  └──────────────────────┘      └──────────────────────┘    │
│                                                              │
│  ┌──────────────────────┐      ┌──────────────────────┐    │
│  │  Dashboard             │      │  Volumes               │    │
│  │  ──────────────────    │      │  ─────────────────     │    │
│  │  React/Next.js          │      │  rockit-data:          │    │
│  │  Agent monitor         │      │    /outcomes/           │    │
│  │  Trading view          │      │    /scorecards/         │    │
│  │  Performance charts    │      │    /reflections/        │    │
│  │                         │      │    /rockit.duckdb       │    │
│  │  Port 3000              │      │  ollama-models:        │    │
│  └──────────────────────┘      │    /qwen3.5/             │    │
│                                  └──────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Docker Compose Configuration

```yaml
# infra/docker/docker-compose.yaml
version: '3.8'

services:
  # ── Core API + Agent Engine ──────────────────────────────
  rockit-serve:
    build:
      context: ../../
      dockerfile: packages/rockit-serve/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - LLM_BASE_URL=http://llm:11434/v1
      - LLM_MODEL=qwen3.5
      - DUCKDB_PATH=/data/rockit.duckdb
      - REFLECTION_DATA_PATH=/data/reflection
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - AGENT_PROMPTS_PATH=/app/configs/agents/prompts
      - AGENT_PARAMS_PATH=/app/configs/agents/parameters
    volumes:
      - rockit-data:/data
      - ../../configs:/app/configs:ro
    depends_on:
      llm:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: always

  # ── Local LLM Server ────────────────────────────────────
  llm:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama-models:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 5
    restart: always

  # ── Dashboard UI ─────────────────────────────────────────
  dashboard:
    build:
      context: ../../packages/rockit-clients/dashboard
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
      - NEXT_PUBLIC_WS_URL=ws://localhost:8000
    depends_on:
      - rockit-serve
    restart: always

volumes:
  rockit-data:
    driver: local
  ollama-models:
    driver: local
```

---

## Environment Configurations

### Dev (Mac Mini / Laptop)

```yaml
# infra/docker/docker-compose.dev.yaml
# docker compose -f docker-compose.yaml -f docker-compose.dev.yaml up

services:
  llm:
    image: ollama/ollama:latest
    # No GPU reservation — runs on Apple Silicon / CPU
    deploy: {}

  rockit-serve:
    environment:
      - LOG_LEVEL=debug
      - REFLECTION_ENABLED=false  # Skip during dev
    volumes:
      - ../../packages:/app/packages:ro  # Hot reload
```

### Production (DGX)

```yaml
# infra/docker/docker-compose.prod.yaml
# docker compose -f docker-compose.yaml -f docker-compose.prod.yaml up -d

services:
  llm:
    image: vllm/vllm-openai:latest
    command: >
      --model Qwen/Qwen3.5-32B-AWQ
      --quantization awq
      --max-model-len 8192
      --gpu-memory-utilization 0.85
      --enable-prefix-caching
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  rockit-serve:
    environment:
      - LOG_LEVEL=info
      - REFLECTION_ENABLED=true
      - META_REVIEW_ENABLED=true
```

### Cloud Run (GCP — for API serving only)

```yaml
# infra/cloudbuild/deploy.yaml
# For serving the API when you don't need local LLM
# (uses Anthropic API or remote vLLM endpoint)

steps:
  - name: 'build'
    script: |
      docker build -t gcr.io/$PROJECT_ID/rockit-serve:$COMMIT_SHA \
        -f packages/rockit-serve/Dockerfile .

  - name: 'deploy'
    script: |
      gcloud run deploy rockit-api \
        --image gcr.io/$PROJECT_ID/rockit-serve:$COMMIT_SHA \
        --set-env-vars LLM_BASE_URL=$VLLM_ENDPOINT \
        --memory 2Gi \
        --cpu 2
```

---

## Process Architecture (What Runs Where)

```
┌─────────────────────────────────────────────────────────────────┐
│  rockit-serve (single Python process)                            │
│                                                                  │
│  Thread 1: FastAPI (uvicorn)                                     │
│    ├── REST endpoints (signals, annotations, health)             │
│    ├── WebSocket (agent stream to dashboard)                     │
│    └── Agent routes (trigger evaluation, get status)             │
│                                                                  │
│  Thread 2: Market Data Loop (asyncio)                            │
│    ├── Receives data from rockit-ingest (Pub/Sub or polling)     │
│    ├── Triggers LangGraph evaluation on new data                 │
│    └── Runs every ~30 seconds during RTH                         │
│                                                                  │
│  Background: APScheduler                                         │
│    ├── 4:15 PM ET: Outcome Logger (compute outcomes)             │
│    ├── 4:30 PM ET: Daily Reflection (Qwen3.5 call)              │
│    ├── 5:00 PM ET: Auto-Adjust (safe param tweaks)              │
│    └── Every 3 days: Meta-Review trigger (Opus 4.6 API call)    │
│                                                                  │
│  Embedded: DuckDB                                                │
│    └── File-based, no separate server needed                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  LLM server (separate container, same machine)                   │
│                                                                  │
│  Ollama (dev) or vLLM (prod)                                     │
│    └── Serves Qwen3.5 via OpenAI-compatible HTTP API             │
│    └── rockit-serve calls it like any HTTP API                    │
│    └── Handles request queuing internally                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Why Not Kubernetes

| Concern | Docker Compose Answer |
|---------|----------------------|
| "What if rockit-serve crashes?" | `restart: always` — Docker restarts it in <5 seconds |
| "What about GPU scheduling?" | One GPU, one LLM container. No scheduling needed. |
| "What about scaling?" | One trader, one system. No horizontal scaling needed. |
| "What about health checks?" | Docker healthchecks + dashboard monitoring |
| "What about secrets?" | `.env` file or GCP Secret Manager |
| "What about rolling deploys?" | `docker compose up -d --build` — 10 second deploy |
| "What about logging?" | Docker logs + structured logging to file/GCS |

### When You WOULD Need More

| Scenario | Solution (not Kubernetes) |
|----------|--------------------------|
| Need 2 LLM instances for throughput | Add second vLLM container in compose |
| Serve multiple traders | Cloud Run auto-scaling (stateless API) |
| Need 24/7 uptime guarantee | Systemd service on DGX + monitoring |
| Multiple GPU nodes for training | Spark DGX handles this natively |

---

## Startup Sequence

```bash
# Production startup on DGX
cd /opt/rockit

# 1. Pull latest
git pull origin main

# 2. Start everything
docker compose -f docker-compose.yaml -f docker-compose.prod.yaml up -d

# 3. Load the model (first time only)
docker exec rockit-llm-1 ollama pull qwen3.5

# 4. Verify
curl http://localhost:8000/health
curl http://localhost:11434/api/tags
open http://localhost:3000

# That's it.
```

### Systemd Service (Auto-Start on Boot)

```ini
# /etc/systemd/system/rockit.service
[Unit]
Description=Rockit Trading System
After=docker.service nvidia-persistenced.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/rockit
ExecStart=/usr/bin/docker compose -f docker-compose.yaml -f docker-compose.prod.yaml up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
```

---

## Monitoring & Alerting (Simple)

No Prometheus/Grafana stack needed. The agent dashboard IS the monitoring.

```python
# packages/rockit-serve/src/rockit_serve/monitoring.py

class SystemMonitor:
    """Lightweight monitoring built into rockit-serve."""

    async def health_check(self) -> dict:
        return {
            "status": "healthy",
            "llm": await self.check_llm(),
            "duckdb": self.check_duckdb(),
            "disk_space": self.check_disk(),
            "gpu_memory": self.check_gpu(),
            "uptime": self.get_uptime(),
            "last_signal": self.get_last_signal_time(),
            "agent_errors_24h": self.count_errors(hours=24),
        }

    async def check_llm(self) -> dict:
        """Verify LLM is responsive and measure latency."""
        start = time.time()
        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            latency = time.time() - start
            return {"status": "ok", "latency_ms": int(latency * 1000)}
        except Exception as e:
            return {"status": "error", "error": str(e)}
```

### Alerts (Simple)

```python
# Send alerts via webhook (Slack, Discord, email, or just dashboard)
alerts:
  - condition: "llm health check fails 3x"
    action: "restart llm container + alert dashboard"
  - condition: "no signals emitted by 11:00 ET on a trading day"
    action: "alert dashboard (system may be stuck)"
  - condition: "auto-rollback triggered"
    action: "alert dashboard + log details"
```
