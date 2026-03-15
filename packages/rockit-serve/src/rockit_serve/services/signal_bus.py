"""In-memory signal bus — broadcasts strategy signals to WebSocket clients and bot subscribers.

This is the central nervous system of the live trading system.
The strategy runner pushes state changes here. The bus fans out to:
1. Dashboard WebSocket clients (full snapshots + deltas)
2. Bot API subscribers (signal events only)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

from rockit_serve.schemas import LiveSnapshot, MarketContext, SignalEvent, StrategyState, TradeIdea

logger = logging.getLogger(__name__)


class SignalBus:
    """Singleton signal bus for broadcasting live state."""

    def __init__(self) -> None:
        # Connected dashboard WebSocket clients
        self._dashboard_clients: set[WebSocket] = set()
        # Connected bot WebSocket clients (keyed by API key)
        self._bot_clients: dict[str, set[WebSocket]] = {}
        # Current state
        self._market: MarketContext = MarketContext()
        self._strategies: dict[str, StrategyState] = {}
        self._trade_ideas: list[TradeIdea] = []
        self._positions: list[dict] = []
        self._session_pnl: float = 0.0
        self._risk_rules: dict[str, Any] = {
            "max_positions": 2,
            "current_positions": 0,
            "daily_loss_limit": -4000,
            "current_daily_pnl": 0,
            "consecutive_losses": 0,
            "max_consecutive_losses": 2,
        }
        # Signal history for bot polling
        self._signal_history: list[SignalEvent] = []
        self._lock = asyncio.Lock()

    # ─── Dashboard connections ────────────────────────────────────────────

    async def connect_dashboard(self, ws: WebSocket) -> None:
        await ws.accept()
        self._dashboard_clients.add(ws)
        # Send current full snapshot on connect
        snapshot = self._build_snapshot()
        await ws.send_text(snapshot.model_dump_json())

    def disconnect_dashboard(self, ws: WebSocket) -> None:
        self._dashboard_clients.discard(ws)

    # ─── Bot connections ─────────────────────────────────────────────────

    async def connect_bot(self, ws: WebSocket, api_key: str) -> None:
        await ws.accept()
        if api_key not in self._bot_clients:
            self._bot_clients[api_key] = set()
        self._bot_clients[api_key].add(ws)

    def disconnect_bot(self, ws: WebSocket, api_key: str) -> None:
        if api_key in self._bot_clients:
            self._bot_clients[api_key].discard(ws)

    # ─── State updates (called by strategy runner / market data loop) ────

    async def update_market(self, market: MarketContext) -> None:
        async with self._lock:
            self._market = market
        await self._broadcast_dashboard()

    async def update_strategy(self, state: StrategyState) -> None:
        async with self._lock:
            prev = self._strategies.get(state.strategy_id)
            self._strategies[state.strategy_id] = state

            # Log signal events for bot history
            if prev and prev.state != state.state and state.state in ("ARMED", "FIRED", "DONE"):
                event = SignalEvent(
                    signal_id=f"{state.strategy_id}_{datetime.now(timezone.utc).strftime('%H%M%S')}",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    instrument=self._market.instrument,
                    strategy_id=state.strategy_id,
                    direction=state.direction or "",
                    state=state.state,
                    entry_price=state.entry_price or 0,
                    stop_price=state.stop_price or 0,
                    target_price=state.target_price or 0,
                )
                self._signal_history.append(event)
                await self._broadcast_bot_signal(event)

        await self._broadcast_dashboard()

    async def update_trade_ideas(self, ideas: list[TradeIdea]) -> None:
        async with self._lock:
            self._trade_ideas = ideas
        await self._broadcast_dashboard()

    async def update_positions(self, positions: list[dict], session_pnl: float) -> None:
        async with self._lock:
            self._positions = positions
            self._session_pnl = session_pnl
            self._risk_rules["current_positions"] = len([p for p in positions if p.get("status") == "OPEN"])
            self._risk_rules["current_daily_pnl"] = session_pnl
        await self._broadcast_dashboard()

    # ─── Bot REST API support ─────────────────────────────────────────────

    def get_active_signals(self, instrument: str = "NQ") -> list[SignalEvent]:
        """Get current active signals for bot polling."""
        signals = []
        for sid, state in self._strategies.items():
            if state.state in ("ARMED", "FIRED") and self._market.instrument == instrument:
                signals.append(SignalEvent(
                    signal_id=f"{sid}_current",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    instrument=instrument,
                    strategy_id=sid,
                    direction=state.direction or "",
                    state=state.state,
                    entry_price=state.entry_price or 0,
                    stop_price=state.stop_price or 0,
                    target_price=state.target_price or 0,
                ))
        return signals

    def get_signal_history(self, instrument: str = "NQ", limit: int = 50) -> list[SignalEvent]:
        """Get recent signal history for bot review."""
        filtered = [s for s in self._signal_history if s.instrument == instrument]
        return filtered[-limit:]

    # ─── Internal broadcast methods ───────────────────────────────────────

    def _build_snapshot(self) -> LiveSnapshot:
        return LiveSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            market=self._market,
            strategies=list(self._strategies.values()),
            trade_ideas=self._trade_ideas,
            positions=self._positions,
            session_pnl=self._session_pnl,
            risk_rules=self._risk_rules,
        )

    async def _broadcast_dashboard(self) -> None:
        if not self._dashboard_clients:
            return
        snapshot = self._build_snapshot()
        msg = snapshot.model_dump_json()
        dead: list[WebSocket] = []
        for ws in self._dashboard_clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._dashboard_clients.discard(ws)

    async def _broadcast_bot_signal(self, event: SignalEvent) -> None:
        msg = event.model_dump_json()
        for api_key, clients in self._bot_clients.items():
            dead: list[WebSocket] = []
            for ws in clients:
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                clients.discard(ws)


# Module-level singleton
signal_bus = SignalBus()
