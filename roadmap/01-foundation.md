# Phase 0: Foundation — Detailed Roadmap

> **Goal:** Set up the monorepo skeleton so `make setup && make test && make serve` works.
> **Duration:** Week 1-2
> **Depends on:** Nothing
> **Blocks:** All other phases

---

## Tasks

### 0.1 Initialize monorepo structure
- [ ] Create `packages/` directory with subdirectories for each package
- [ ] Create `infra/`, `configs/`, `scripts/` directories
- [ ] Create root `pyproject.toml` with `uv` workspace config
- [ ] Create `Makefile` with `setup`, `test`, `lint`, `serve`, `backtest` targets
- [ ] Create `.github/workflows/ci.yaml` (lint + test on push)
- [ ] Create `.gitignore` for Python, Node, C#

**Acceptance:** `git clone && make setup` installs all dependencies.

### 0.2 Package skeletons
- [ ] `packages/rockit-core/` — pyproject.toml, src/rockit_core/__init__.py, empty tests/
- [ ] `packages/rockit-train/` — pyproject.toml, src/rockit_train/__init__.py, empty tests/
- [ ] `packages/rockit-serve/` — pyproject.toml, src/rockit_serve/__init__.py, empty tests/
- [ ] `packages/rockit-ingest/` — pyproject.toml, src/rockit_ingest/__init__.py, empty tests/
- [ ] `packages/rockit-pipeline/` — pyproject.toml, src/rockit_pipeline/__init__.py, empty tests/
- [ ] Verify cross-package imports work: `from rockit_core import __version__`

**Acceptance:** `make test` runs (empty) test suite for all packages, exits 0.

### 0.3 Docker Compose for local dev
- [ ] Create `infra/docker/docker-compose.yaml` (rockit-serve skeleton)
- [ ] Create `infra/docker/docker-compose.dev.yaml` (dev overrides)
- [ ] Create `packages/rockit-serve/Dockerfile` (minimal FastAPI hello world)
- [ ] Verify `docker compose up` starts and responds on port 8000

**Acceptance:** `curl http://localhost:8000/health` returns `{"status": "ok"}`.

### 0.4 Metrics infrastructure skeleton
- [ ] Create `packages/rockit-core/src/rockit_core/metrics/` module
- [ ] Implement `MetricsCollector` with DuckDB backend (can be in-memory for tests)
- [ ] Implement `MetricEvent` dataclass
- [ ] Create no-op `NullCollector` for tests that don't need metrics

**Acceptance:** Modules can `collector.record(MetricEvent(...))` and query results back from DuckDB.

### 0.5 Configuration schema
- [ ] Create `configs/strategies.yaml` (empty strategy template with schema comments)
- [ ] Create `configs/instruments.yaml` (NQ, MNQ, ES, MES, YM, MYM specs)
- [ ] Create `configs/eval/gates.yaml` (evaluation gate thresholds)
- [ ] Create `configs/baselines/` directory

**Acceptance:** Config files parse without errors. Strategy YAML schema is documented.

### 0.6 Entry/Stop/Target model interfaces
- [ ] Design `EntryModel` abstract base class
- [ ] Design `StopModel` abstract base class
- [ ] Design `TargetModel` abstract base class
- [ ] Design `EntrySignal`, `TargetSpec`, `TrailRule` dataclasses
- [ ] Create `packages/rockit-core/src/rockit_core/models/` module
- [ ] Write interface tests (contract tests for any implementation)

**Acceptance:** Abstract classes exist with clear docstrings. At least one stub implementation passes contract tests.

---

## Definition of Done

- [ ] `git clone && make setup` works on fresh machine
- [ ] `make test` passes (all packages)
- [ ] `make lint` passes (ruff)
- [ ] `make serve` starts FastAPI on port 8000
- [ ] `docker compose up` works
- [ ] CI pipeline runs on GitHub push
- [ ] Entry/Stop/Target model interfaces defined
- [ ] Metrics collector skeleton exists
- [ ] All config schemas defined
