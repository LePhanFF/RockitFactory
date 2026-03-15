"""
EMA Expert — Exponential Moving Average structure analysis.

Produces up to 3 cards:
  1. EMA alignment (all EMAs stacked bullish/bearish)
  2. EMA dynamic support/resistance (price bouncing off key EMA)
  3. EMA compression (fan width narrow = pending breakout)

Uses pre-computed EMA columns from the bar data (ema_20, ema_50).
"""

from __future__ import annotations

import math

from rockit_core.agents.evidence import EvidenceCard
from rockit_core.agents.experts.base import DomainExpert


class EmaExpert(DomainExpert):
    """EMA structure domain expert — alignment, dynamic S/R, compression."""

    @property
    def domain(self) -> str:
        return "ema"

    def scorecard(self, context: dict) -> list[EvidenceCard]:
        cards: list[EvidenceCard] = []
        bar = context.get("bar") or {}
        session_ctx = context.get("session_context") or {}
        signal = context.get("signal") or {}
        signal_dir = signal.get("direction", "").upper()

        for fn in (
            self._ema_alignment_card,
            self._ema_dynamic_sr_card,
            self._ema_compression_card,
        ):
            c = fn(bar, session_ctx, signal_dir)
            if c is not None:
                cards.append(c)

        return cards

    def historical_query(self, conn, signal: dict) -> dict:
        """Query DuckDB for EMA-conditional win rates."""
        try:
            from rockit_core.research.db import query
            rows = query(conn, """
                SELECT d.trend_strength, t.outcome, COUNT(*) as cnt, AVG(t.net_pnl) as avg_pnl
                FROM trades t
                JOIN deterministic_tape d ON t.session_date = d.session_date
                WHERE t.strategy_name = ? AND t.direction = ?
                  AND d.trend_strength IS NOT NULL
                GROUP BY d.trend_strength, t.outcome
                ORDER BY cnt DESC
                LIMIT 10
            """, [signal.get("strategy_name", ""), signal.get("direction", "")])
            return {"ema_trend_stats": [dict(zip(["trend", "outcome", "count", "avg_pnl"], r)) for r in rows]}
        except Exception:
            return {}

    def _ema_alignment_card(
        self, bar: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """EMA stack alignment — bullish when short > long, bearish when reversed."""
        price = self._get_float(bar, session_ctx, "close")
        ema_20 = self._get_float(bar, session_ctx, "ema_20")
        ema_50 = self._get_float(bar, session_ctx, "ema_50")

        if price is None or ema_20 is None or ema_50 is None:
            return None

        # Determine alignment
        bullish_stack = price > ema_20 > ema_50
        bearish_stack = price < ema_20 < ema_50

        if bullish_stack:
            if signal_dir == "LONG":
                direction, strength = "bullish", 0.75
                obs = f"EMA bullish stack (price {price:.0f} > EMA20 {ema_20:.0f} > EMA50 {ema_50:.0f}) — aligned with LONG"
            else:
                direction, strength = "bullish", 0.3
                obs = f"EMA bullish stack — SHORT opposes EMA structure"
        elif bearish_stack:
            if signal_dir == "SHORT":
                direction, strength = "bearish", 0.75
                obs = f"EMA bearish stack (price {price:.0f} < EMA20 {ema_20:.0f} < EMA50 {ema_50:.0f}) — aligned with SHORT"
            else:
                direction, strength = "bearish", 0.3
                obs = f"EMA bearish stack — LONG opposes EMA structure"
        else:
            # Mixed — EMAs crossing or price between them
            direction, strength = "neutral", 0.45
            obs = f"EMA mixed (price={price:.0f}, EMA20={ema_20:.0f}, EMA50={ema_50:.0f}) — no clear stack"

        return EvidenceCard(
            card_id="ema_alignment",
            source="expert_ema",
            layer="certainty",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=3,
            raw_data={
                "price": price, "ema_20": ema_20, "ema_50": ema_50,
                "bullish_stack": bullish_stack, "bearish_stack": bearish_stack,
            },
        )

    def _ema_dynamic_sr_card(
        self, bar: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """Price near EMA20 — acting as dynamic support (LONG) or resistance (SHORT)."""
        price = self._get_float(bar, session_ctx, "close")
        ema_20 = self._get_float(bar, session_ctx, "ema_20")
        low = self._get_float(bar, session_ctx, "low")
        high = self._get_float(bar, session_ctx, "high")

        if price is None or ema_20 is None:
            return None

        # Distance from EMA20 in points
        distance = abs(price - ema_20)

        # "Near" threshold: within 15 points for NQ
        PROXIMITY_PTS = 15.0
        if distance > PROXIMITY_PTS:
            return None

        # Check if bar touched EMA and bounced
        if low is not None and low <= ema_20 and price > ema_20:
            # Touched EMA20 from below and bounced up — dynamic support
            if signal_dir == "LONG":
                direction, strength = "bullish", 0.65
                obs = f"Price bounced off EMA20 ({ema_20:.0f}) as dynamic support — supports LONG"
            else:
                direction, strength = "bullish", 0.4
                obs = f"Price bounced off EMA20 ({ema_20:.0f}) support — warns against SHORT"
            return EvidenceCard(
                card_id="ema_dynamic_sr",
                source="expert_ema",
                layer="probabilistic",
                observation=obs,
                direction=direction,
                strength=strength,
                data_points=2,
                raw_data={"ema_20": ema_20, "price": price, "distance": round(distance, 1), "type": "support"},
            )

        if high is not None and high >= ema_20 and price < ema_20:
            # Touched EMA20 from above and rejected — dynamic resistance
            if signal_dir == "SHORT":
                direction, strength = "bearish", 0.65
                obs = f"Price rejected at EMA20 ({ema_20:.0f}) as dynamic resistance — supports SHORT"
            else:
                direction, strength = "bearish", 0.4
                obs = f"Price rejected at EMA20 ({ema_20:.0f}) resistance — warns against LONG"
            return EvidenceCard(
                card_id="ema_dynamic_sr",
                source="expert_ema",
                layer="probabilistic",
                observation=obs,
                direction=direction,
                strength=strength,
                data_points=2,
                raw_data={"ema_20": ema_20, "price": price, "distance": round(distance, 1), "type": "resistance"},
            )

        return None

    def _ema_compression_card(
        self, bar: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """EMA fan compression — EMAs converging signals pending breakout."""
        ema_20 = self._get_float(bar, session_ctx, "ema_20")
        ema_50 = self._get_float(bar, session_ctx, "ema_50")

        if ema_20 is None or ema_50 is None:
            return None

        fan_width = abs(ema_20 - ema_50)

        # Compression threshold: EMAs within 10 points for NQ
        COMPRESSION_PTS = 10.0
        if fan_width > COMPRESSION_PTS:
            return None

        direction = "neutral"
        strength = 0.5
        obs = f"EMA compression (EMA20-EMA50 gap: {fan_width:.1f}pts) — breakout imminent, direction TBD"

        return EvidenceCard(
            card_id="ema_compression",
            source="expert_ema",
            layer="instinct",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=2,
            raw_data={"ema_20": ema_20, "ema_50": ema_50, "fan_width": round(fan_width, 1)},
        )

    # ── Helpers ──

    @staticmethod
    def _get_float(bar: dict, session_ctx: dict, key: str) -> float | None:
        for src in (bar, session_ctx):
            v = src.get(key)
            if v is not None:
                try:
                    val = float(v)
                    if not math.isnan(val):
                        return val
                except (TypeError, ValueError):
                    pass
        return None
