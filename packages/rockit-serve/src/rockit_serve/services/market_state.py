"""Market state service — provides mock data for demo mode, or reads from live pipeline.

In demo mode, generates realistic-looking NQ market data that cycles through
the 4 trading phases with strategy state changes. This lets you test the full
dashboard without any live market connection.

In live mode, this will be replaced by the actual strategy runner + deterministic
orchestrator feeding the signal bus.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone

from rockit_serve.config import DEMO_MODE
from rockit_serve.schemas import MarketContext, StrategyState, TradeIdea
from rockit_serve.services.signal_bus import signal_bus

logger = logging.getLogger(__name__)

# Strategy metadata from backtests
STRATEGY_META = {
    "or_reversal": {"wr": 0.644, "pf": 2.96, "phase_start": "10:30", "phase_end": "10:30"},
    "or_acceptance": {"wr": 0.599, "pf": 2.10, "phase_start": "10:30", "phase_end": "10:30"},
    "80p_rule": {"wr": 0.423, "pf": 2.83, "phase_start": "10:30", "phase_end": "11:00"},
    "20p_ib_extension": {"wr": 0.50, "pf": 1.90, "phase_start": "10:30", "phase_end": "12:30"},
    "trend_bull": {"wr": 0.56, "pf": 2.30, "phase_start": "10:30", "phase_end": "12:00"},
    "trend_bear": {"wr": 0.44, "pf": 2.50, "phase_start": "10:30", "phase_end": "11:30"},
    "bday": {"wr": 0.464, "pf": 2.10, "phase_start": "11:00", "phase_end": "13:00"},
    "ib_edge_fade": {"wr": 0.48, "pf": 1.80, "phase_start": "10:30", "phase_end": "13:00"},
    "pdh_pdl_reaction": {"wr": 0.529, "pf": 3.59, "phase_start": "10:00", "phase_end": "11:30"},
    "va_edge_fade": {"wr": 0.60, "pf": 1.80, "phase_start": "10:30", "phase_end": "13:00"},
    "ndog_gap_fill": {"wr": 0.571, "pf": 1.96, "phase_start": "09:30", "phase_end": "09:30"},
    "nwog_gap_fill": {"wr": 0.65, "pf": 5.02, "phase_start": "09:30", "phase_end": "09:30"},
}


def _get_phase(time_str: str) -> int:
    """Determine trading phase from time string HH:MM."""
    h, m = map(int, time_str.split(":"))
    minutes = h * 60 + m
    if minutes < 570:  # before 9:30
        return 0
    if minutes < 630:  # 9:30-10:30
        return 1
    if minutes < 720:  # 10:30-12:00
        return 2
    return 3  # 12:00+


class DemoMarketLoop:
    """Generates mock market data for testing the dashboard."""

    def __init__(self) -> None:
        self._running = False
        self._base_price = 21500.0
        self._tick = 0
        # Simulated session timeline (minutes from 9:30)
        self._session_minute = 0
        self._strategy_states: dict[str, str] = {sid: "INACTIVE" for sid in STRATEGY_META}

    async def start(self) -> None:
        self._running = True
        logger.info("Demo market loop started")
        while self._running:
            await self._emit_tick()
            await asyncio.sleep(2)  # 2-second ticks in demo

    def stop(self) -> None:
        self._running = False

    async def _emit_tick(self) -> None:
        self._tick += 1
        self._session_minute = self._tick  # 1 tick = 1 minute in demo

        # Simulate price movement
        drift = random.gauss(0, 2.5)
        self._base_price += drift
        price = round(self._base_price, 2)

        # Calculate time
        total_min = 570 + self._session_minute  # 9:30 + offset
        if total_min > 960:  # 16:00 — reset session
            self._session_minute = 0
            self._tick = 0
            total_min = 570
            self._strategy_states = {sid: "INACTIVE" for sid in STRATEGY_META}
        h, m = divmod(total_min, 60)
        time_str = f"{h:02d}:{m:02d}"
        phase = _get_phase(time_str)

        # Build market context
        ib_high = self._base_price + 65 if self._session_minute >= 60 else None
        ib_low = self._base_price - 65 if self._session_minute >= 60 else None

        market = MarketContext(
            instrument="NQ",
            current_price=price,
            current_time=time_str,
            phase=phase,
            day_type="BALANCE" if self._session_minute < 90 else "P-DAY",
            day_type_confidence=0.72 if self._session_minute < 90 else 0.85,
            bias="LONG",
            ib_high=ib_high,
            ib_low=ib_low,
            ib_range=round(ib_high - ib_low, 2) if ib_high and ib_low else None,
            vwap=round(price - random.uniform(-5, 5), 2),
            poc=round(price - random.uniform(-10, 10), 2),
            vah=round(price + 30, 2),
            val=round(price - 30, 2),
            pdh=round(price + 80, 2),
            pdl=round(price - 120, 2),
            prior_poc=round(price - 15, 2),
            ema20=round(price - random.uniform(-8, 8), 2),
            ema50=round(price - random.uniform(-15, 15), 2),
            ema200=round(price - 40, 2),
            rsi14=round(50 + random.gauss(0, 10), 1),
            atr14=round(180 + random.gauss(0, 20), 1),
            adx14=round(30 + random.gauss(0, 5), 1),
            cvd=round(random.gauss(500, 800), 0),
            tpo_shape="b" if price > self._base_price else "p",
            dpoc=round(price + random.uniform(-5, 5), 2),
            dpoc_direction="up" if drift > 0 else "down",
            regime="low_vol_balance",
        )
        await signal_bus.update_market(market)

        # Update strategy states based on phase
        await self._update_strategy_states(time_str, phase, price)

        # Generate trade ideas for ARMED strategies
        ideas = self._generate_trade_ideas(price)
        if ideas:
            await signal_bus.update_trade_ideas(ideas)

    async def _update_strategy_states(self, time_str: str, phase: int, price: float) -> None:
        for sid, meta in STRATEGY_META.items():
            current = self._strategy_states[sid]
            state = self._compute_strategy_state(sid, meta, time_str, phase, price, current)
            self._strategy_states[sid] = state.state
            await signal_bus.update_strategy(state)

    def _compute_strategy_state(
        self, sid: str, meta: dict, time_str: str, phase: int, price: float, current: str
    ) -> StrategyState:
        wr = meta["wr"]
        pf = meta["pf"]

        # NWOG only on Mondays — in demo, always inactive
        if sid == "nwog_gap_fill":
            return StrategyState(strategy_id=sid, state="INACTIVE", historical_wr=wr, historical_pf=pf)

        # NDOG fires at 9:30
        if sid == "ndog_gap_fill":
            if phase == 0:
                return StrategyState(strategy_id=sid, state="WATCHING", historical_wr=wr, historical_pf=pf)
            if self._session_minute <= 5 and current != "DONE":
                return StrategyState(
                    strategy_id=sid, state="FIRED", direction="LONG",
                    entry_price=round(price - 15, 2), stop_price=round(price - 40, 2),
                    target_price=round(price + 10, 2), current_pnl=round(random.uniform(-200, 600), 2),
                    historical_wr=wr, historical_pf=pf,
                )
            return StrategyState(strategy_id=sid, state="DONE", direction="LONG",
                                 current_pnl=420.0, historical_wr=wr, historical_pf=pf)

        # Phase 1 strategies — before IB close
        if phase < 1:
            return StrategyState(strategy_id=sid, state="INACTIVE", historical_wr=wr, historical_pf=pf)

        # PDH/PDL starts in phase 1B
        if sid == "pdh_pdl_reaction" and phase >= 1:
            if self._session_minute < 45:
                return StrategyState(strategy_id=sid, state="WATCHING", historical_wr=wr, historical_pf=pf,
                                     condition_progress={"pdh_distance": round(abs(price - (price + 80)), 1)})
            return StrategyState(strategy_id=sid, state="DONE", historical_wr=wr, historical_pf=pf)

        # IB close strategies fire at phase 2
        if phase < 2:
            if sid in ("or_reversal", "or_acceptance", "80p_rule", "trend_bull", "trend_bear", "ib_edge_fade"):
                return StrategyState(strategy_id=sid, state="WATCHING", historical_wr=wr, historical_pf=pf)
            return StrategyState(strategy_id=sid, state="INACTIVE", historical_wr=wr, historical_pf=pf)

        # Phase 2+ — demo fires OR Rev, arms 80P, blocks Trend Bear
        if sid == "or_reversal":
            if current != "DONE":
                return StrategyState(
                    strategy_id=sid, state="FIRED", direction="LONG",
                    entry_price=round(price - 30, 2), stop_price=round(price - 60, 2),
                    target_price=round(price + 30, 2), trailing_stop=round(price - 20, 2),
                    current_pnl=round(random.uniform(200, 1200), 2),
                    historical_wr=wr, historical_pf=pf,
                )
            return StrategyState(strategy_id=sid, state="DONE", direction="LONG",
                                 current_pnl=850.0, historical_wr=wr, historical_pf=pf)

        if sid == "or_acceptance":
            return StrategyState(strategy_id=sid, state="BLOCKED", block_reason="Bias mismatch",
                                 historical_wr=wr, historical_pf=pf)

        if sid == "80p_rule":
            timer = min(30, self._session_minute - 60)
            if timer < 30:
                return StrategyState(
                    strategy_id=sid, state="ARMED", direction="SHORT",
                    entry_price=round(price + 5, 2), stop_price=round(price + 35, 2),
                    target_price=round(price - 30, 2),
                    condition_progress={"timer_bars": timer, "timer_required": 30},
                    historical_wr=wr, historical_pf=pf,
                )
            return StrategyState(strategy_id=sid, state="FIRED", direction="SHORT",
                                 entry_price=round(price + 5, 2), stop_price=round(price + 35, 2),
                                 target_price=round(price - 30, 2), current_pnl=round(random.uniform(-300, 500), 2),
                                 historical_wr=wr, historical_pf=pf)

        if sid == "trend_bear":
            return StrategyState(strategy_id=sid, state="BLOCKED", block_reason="Bias is LONG",
                                 historical_wr=wr, historical_pf=pf)

        if sid == "trend_bull":
            return StrategyState(strategy_id=sid, state="WATCHING", historical_wr=wr, historical_pf=pf,
                                 condition_progress={"adx": 33, "adx_required": 28, "ema_aligned": True, "ibh_break": False})

        if sid == "bday" and phase >= 2:
            return StrategyState(strategy_id=sid, state="WATCHING", historical_wr=wr, historical_pf=pf,
                                 condition_progress={"ib_range_holding": True})

        return StrategyState(strategy_id=sid, state="WATCHING" if phase >= 2 else "INACTIVE",
                             historical_wr=wr, historical_pf=pf)

    def _generate_trade_ideas(self, price: float) -> list[TradeIdea]:
        ideas = []
        for sid, state in self._strategy_states.items():
            if state == "ARMED":
                meta = STRATEGY_META[sid]
                ideas.append(TradeIdea(
                    id=f"idea_{sid}",
                    strategy_id=sid,
                    confidence="high" if meta["pf"] > 2.5 else "medium",
                    direction="SHORT" if sid == "80p_rule" else "LONG",
                    entry_price=round(price + 5, 2),
                    stop_price=round(price + 35, 2),
                    target_price=round(price - 30, 2),
                    r_reward=round(35 / 30, 2),
                    rationale=f"{sid.replace('_', ' ').title()} setup developing. Conditions at 80% met.",
                    evidence_for=[
                        {"source": "TPO Expert", "direction": "SHORT", "strength": 0.85, "signal": "b-shape profile"},
                        {"source": "VWAP Expert", "direction": "SHORT", "strength": 0.70, "signal": "below VWAP"},
                        {"source": "ICT Expert", "direction": "SHORT", "strength": 0.60, "signal": "unfilled FVG below"},
                    ],
                    evidence_against=[
                        {"source": "EMA Expert", "direction": "LONG", "strength": 0.65, "signal": "EMAs aligned up"},
                    ],
                    agent_verdict="TAKE",
                    agent_reasoning="Evidence weight favors 3:1. Strategy has strong PF despite sub-50% WR.",
                    status="ready",
                ))
        return ideas


# Module-level instance
demo_loop = DemoMarketLoop()
