.PHONY: setup test lint serve backtest clean

# Default target
all: setup test lint

# Install all dependencies via uv
setup:
	uv sync

# Run all tests
test:
	uv run pytest packages/rockit-core/tests/ packages/rockit-train/tests/ packages/rockit-serve/tests/ packages/rockit-ingest/tests/ packages/rockit-pipeline/tests/ -v

# Run tests with coverage
test-cov:
	uv run pytest packages/rockit-core/tests/ --cov=packages/rockit-core/src --cov-report=html -v

# Lint with ruff
lint:
	uv run ruff check packages/ --fix
	uv run ruff format packages/ --check

# Format code
fmt:
	uv run ruff format packages/

# Start the API server (dev mode)
serve:
	uv run uvicorn rockit_serve.app:app --reload --port 8000

# Run backtest (usage: make backtest, make backtest INSTRUMENT=ES)
INSTRUMENT ?= NQ
backtest:
	uv run python scripts/run_backtest.py --instrument $(INSTRUMENT)

backtest-baseline:
	uv run python scripts/run_backtest.py --instrument $(INSTRUMENT) --save-baseline

# Docker Compose
docker-up:
	docker compose -f infra/docker/docker-compose.yaml -f infra/docker/docker-compose.dev.yaml up --build

docker-down:
	docker compose -f infra/docker/docker-compose.yaml -f infra/docker/docker-compose.dev.yaml down

# Clean build artifacts
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ build/ htmlcov/ .coverage
