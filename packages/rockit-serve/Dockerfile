FROM python:3.11-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock* ./
COPY packages/rockit-core/ packages/rockit-core/
COPY packages/rockit-serve/ packages/rockit-serve/

RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "rockit_serve.app:app", "--host", "0.0.0.0", "--port", "8000"]
