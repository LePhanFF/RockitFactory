"""
Scalper Expert — ultra-short-term momentum analysis.

Produces up to 3 cards:
  1. Momentum direction (RSI + ADX)
  2. Exhaustion warning (RSI overbought/oversold + ADX declining)
  3. Volume spike alert (volume anomaly detection)

Designed for speed: <10ms, no DuckDB queries, no LLM.
Uses pre-computed columns: rsi14, adx14, volume_spike.
"""

from __future__ import annotations

import math

from rockit_core.agents.evidence import EvidenceCard
from rockit_core.agents.experts.base import DomainExpert


class ScalperExpert(DomainExpert):
    """Scalper domain expert — fast momentum, exhaustion, and volume analysis."""

    @property
    def domain(self) -> str:
        return "scalper"

    def scorecard(self, context: dict) -> list[EvidenceCard]:
        cards: list[EvidenceCard] = []
        bar = context.get("bar") or {}
        session_ctx = context.get("session_context") or {}
        signal = context.get("signal") or {}
        signal_dir = signal.get("direction", "").upper()

        for fn in (
            self._momentum_card,
            self._exhaustion_card,
            self._volume_spike_card,
        ):
            c = fn(bar, session_ctx, signal_dir)
            if c is not None:
                cards.append(c)

        return cards

    def _momentum_card(
        self, bar: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """RSI + ADX momentum assessment."""
        rsi = _get_float(bar, session_ctx, "rsi14")
        adx = _get_float(bar, session_ctx, "adx14")

        if rsi is None:
            return None

        # RSI momentum: 50-70 = bullish, 30-50 = bearish, extremes = exhaustion (separate card)
        if 55 <= rsi <= 70:
            if signal_dir == "LONG":
                direction, strength = "bullish", 0.6
                obs = f"RSI {rsi:.0f} — bullish momentum, aligned with LONG"
            else:
                direction, strength = "bullish", 0.35
                obs = f"RSI {rsi:.0f} — bullish momentum, warns against SHORT"
        elif 30 <= rsi <= 45:
            if signal_dir == "SHORT":
                direction, strength = "bearish", 0.6
                obs = f"RSI {rsi:.0f} — bearish momentum, aligned with SHORT"
            else:
                direction, strength = "bearish", 0.35
                obs = f"RSI {rsi:.0f} — bearish momentum, warns against LONG"
        else:
            return None  # Neutral or extreme (handled by exhaustion card)

        # Boost if ADX confirms trend
        if adx is not None and adx > 25:
            strength = min(1.0, strength + 0.1)
            obs += f" (ADX {adx:.0f} confirms trend)"

        return EvidenceCard(
            card_id="scalper_momentum",
            source="expert_scalper",
            layer="probabilistic",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=2 if adx else 1,
            raw_data={"rsi": rsi, "adx": adx},
        )

    def _exhaustion_card(
        self, bar: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """RSI overbought/oversold — exhaustion warning."""
        rsi = _get_float(bar, session_ctx, "rsi14")

        if rsi is None:
            return None

        if rsi >= 75:
            # Overbought — bearish warning
            if signal_dir == "LONG":
                direction, strength = "bearish", 0.55
                obs = f"RSI {rsi:.0f} overbought — LONG entering exhaustion zone, reversal risk"
            else:
                direction, strength = "bearish", 0.6
                obs = f"RSI {rsi:.0f} overbought — exhaustion supports SHORT reversal"
            return EvidenceCard(
                card_id="scalper_exhaustion",
                source="expert_scalper",
                layer="instinct",
                observation=obs,
                direction=direction,
                strength=strength,
                data_points=1,
                raw_data={"rsi": rsi, "condition": "overbought"},
            )

        if rsi <= 25:
            # Oversold — bullish warning
            if signal_dir == "SHORT":
                direction, strength = "bullish", 0.55
                obs = f"RSI {rsi:.0f} oversold — SHORT entering exhaustion zone, bounce risk"
            else:
                direction, strength = "bullish", 0.6
                obs = f"RSI {rsi:.0f} oversold — exhaustion supports LONG bounce"
            return EvidenceCard(
                card_id="scalper_exhaustion",
                source="expert_scalper",
                layer="instinct",
                observation=obs,
                direction=direction,
                strength=strength,
                data_points=1,
                raw_data={"rsi": rsi, "condition": "oversold"},
            )

        return None

    def _volume_spike_card(
        self, bar: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """Volume spike detection — high volume at entry suggests conviction."""
        vol_spike = _get_float(bar, session_ctx, "volume_spike")

        if vol_spike is None or vol_spike < 2.0:
            return None

        # Volume spike > 2x average — significant
        return EvidenceCard(
            card_id="scalper_volume_spike",
            source="expert_scalper",
            layer="instinct",
            observation=f"Volume spike {vol_spike:.1f}x average — high conviction bar, watch for continuation vs exhaustion",
            direction="neutral",
            strength=0.5,
            data_points=1,
            raw_data={"volume_spike": vol_spike},
        )


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
