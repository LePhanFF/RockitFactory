"""FastAPI application for Rockit live trading system.

Serves:
- Dashboard WebSocket (real-time market state + strategy signals)
- Bot API (REST polling + WebSocket for NinjaTrader and other algos)
- User auth (JWT multi-user with strategy preferences)
- Trade journal (per-user, separate from research DuckDB)
- Agent evaluation (existing pipeline)
- Market context (deterministic analysis data)
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rockit_serve.config import CORS_ORIGINS, DEMO_MODE
from rockit_serve.database import init_db
from rockit_serve.routers.agents import router as agents_router
from rockit_serve.routers.auth import router as auth_router
from rockit_serve.routers.journal import router as journal_router
from rockit_serve.routers.market import router as market_router
from rockit_serve.routers.signals import router as signals_router

logger = logging.getLogger(__name__)

_demo_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    logger.info("User database initialized")

    global _demo_task
    if DEMO_MODE:
        from rockit_serve.services.market_state import demo_loop
        _demo_task = asyncio.create_task(demo_loop.start())
        logger.info("Demo market loop started (ROCKIT_DEMO_MODE=true)")

    yield

    # Shutdown
    if _demo_task:
        from rockit_serve.services.market_state import demo_loop
        demo_loop.stop()
        _demo_task.cancel()


app = FastAPI(
    title="Rockit Trading API",
    version="0.2.0",
    description="Live trading signals, multi-user journal, bot subscriptions",
    lifespan=lifespan,
)

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth_router)
app.include_router(signals_router)
app.include_router(market_router)
app.include_router(journal_router)
app.include_router(agents_router)


@app.get("/health")
def health():
    return {"status": "ok", "demo_mode": DEMO_MODE}
