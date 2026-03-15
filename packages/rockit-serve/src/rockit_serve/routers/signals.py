"""Signal endpoints — WebSocket for dashboard + REST/WS for bots.

Dashboard clients connect via /ws/dashboard (JWT auth).
Bot clients connect via /ws/bot (API key auth) or poll /api/v1/signals (API key auth).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from rockit_serve.dependencies import get_bot_user
from rockit_serve.models import BotApiKey
from rockit_serve.schemas import SignalEvent
from rockit_serve.services.signal_bus import signal_bus

router = APIRouter(tags=["signals"])


# ─── Dashboard WebSocket ─────────────────────────────────────────────────────

@router.websocket("/ws/dashboard")
async def dashboard_ws(ws: WebSocket):
    """WebSocket for dashboard clients. Sends full LiveSnapshot on connect, then deltas."""
    # Note: In production, validate JWT from query param or first message.
    # For prototype, we accept all connections.
    await signal_bus.connect_dashboard(ws)
    try:
        while True:
            # Keep connection alive — client can send pings or commands
            data = await ws.receive_text()
            # Future: handle client commands (pause, filter, consult)
    except WebSocketDisconnect:
        signal_bus.disconnect_dashboard(ws)


# ─── Bot WebSocket ───────────────────────────────────────────────────────────

@router.websocket("/ws/bot")
async def bot_ws(ws: WebSocket, api_key: str = Query(...)):
    """WebSocket for bot subscribers. Pushes SignalEvent on strategy fires.

    Connect: ws://host/ws/bot?api_key=YOUR_KEY
    Receives: JSON SignalEvent for each ARMED/FIRED/CLOSED state change.
    """
    # Validate API key
    from rockit_serve.database import async_session
    from sqlalchemy import select
    async with async_session() as db:
        result = await db.execute(
            select(BotApiKey).where(BotApiKey.api_key == api_key, BotApiKey.is_active == True)  # noqa: E712
        )
        key = result.scalar_one_or_none()
        if key is None:
            await ws.close(code=4001, reason="Invalid API key")
            return

    await signal_bus.connect_bot(ws, api_key)
    try:
        while True:
            await ws.receive_text()  # Keep alive
    except WebSocketDisconnect:
        signal_bus.disconnect_bot(ws, api_key)


# ─── Bot REST API (polling) ──────────────────────────────────────────────────

@router.get("/api/v1/signals", response_model=list[SignalEvent], tags=["bot-api"])
async def get_active_signals(
    instrument: str = Query(default="NQ"),
    _key: BotApiKey = Depends(get_bot_user),
):
    """Get currently active signals (ARMED or FIRED).

    NinjaTrader bots poll this endpoint every 30s:
    GET /api/v1/signals?instrument=NQ
    Header: X-API-Key: YOUR_KEY
    """
    return signal_bus.get_active_signals(instrument)


@router.get("/api/v1/signals/history", response_model=list[SignalEvent], tags=["bot-api"])
async def get_signal_history(
    instrument: str = Query(default="NQ"),
    limit: int = Query(default=50, le=200),
    _key: BotApiKey = Depends(get_bot_user),
):
    """Get recent signal history for audit/review.

    GET /api/v1/signals/history?instrument=NQ&limit=20
    Header: X-API-Key: YOUR_KEY
    """
    return signal_bus.get_signal_history(instrument, limit)
