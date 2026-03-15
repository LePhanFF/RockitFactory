"""
Mean Reversion Expert — statistical mean reversion / regime detection.

Produces up to 3 cards:
  1. BB position (Bollinger Band percentile — extreme = reversion likely)
  2. Regime classification (ADX-based trending vs range-bound)
  3. VWAP band stretch (distance from VWAP σ bands)

Uses pre-computed columns: bb_upper, bb_middle, bb_lower, adx14, vwap_sigma_*.
"""

from __future__ import annotations

import math

from rockit_core.agents.evidence import EvidenceCard
from rockit_core.agents.experts.base import DomainExpert


class MeanReversionExpert(DomainExpert):
    """Mean reversion domain expert — BB position, regime, and VWAP stretch."""

    @property
    def domain(self) -> str:
        return "mean_reversion"

    def scorecard(self, context: dict) -> list[EvidenceCard]:
        cards: list[EvidenceCard] = []
        bar = context.get("bar") or {}
        session_ctx = context.get("session_context") or {}
        signal = context.get("signal") or {}
        signal_dir = signal.get("direction", "").upper()

        for fn in (
            self._bb_position_card,
            self._regime_card,
            self._vwap_stretch_card,
        ):
            c = fn(bar, session_ctx, signal_dir)
            if c is not None:
                cards.append(c)

        return cards

    def _bb_position_card(
        self, bar: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """Bollinger Band percentile — extreme position signals reversion."""
        price = _get_float(bar, session_ctx, "close")
        bb_upper = _get_float(bar, session_ctx, "bb_upper")
        bb_lower = _get_float(bar, session_ctx, "bb_lower")

        if price is None or bb_upper is None or bb_lower is None:
            return None
        if bb_upper <= bb_lower:
            return None

        bb_pct = (price - bb_lower) / (bb_upper - bb_lower)
        bb_pct = max(0.0, min(1.0, bb_pct))

        if bb_pct >= 0.9:
            # Near upper band — mean reversion SHORT favored
            if signal_dir == "SHORT":
                direction, strength = "bearish", 0.6
                obs = f"BB percentile {bb_pct:.0%} — near upper band, mean reversion supports SHORT"
            elif signal_dir == "LONG":
                direction, strength = "bearish", 0.45
                obs = f"BB percentile {bb_pct:.0%} — near upper band, LONG chasing into resistance"
            else:
                return None
        elif bb_pct <= 0.1:
            # Near lower band — mean reversion LONG favored
            if signal_dir == "LONG":
                direction, strength = "bullish", 0.6
                obs = f"BB percentile {bb_pct:.0%} — near lower band, mean reversion supports LONG"
            elif signal_dir == "SHORT":
                direction, strength = "bullish", 0.45
                obs = f"BB percentile {bb_pct:.0%} — near lower band, SHORT chasing into support"
            else:
                return None
        else:
            return None  # Mid-band — no edge

        return EvidenceCard(
            card_id="mr_bb_position",
            source="expert_mean_reversion",
            layer="probabilistic",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=3,
            raw_data={"bb_pct": round(bb_pct, 3), "price": price, "bb_upper": bb_upper, "bb_lower": bb_lower},
        )

    def _regime_card(
        self, bar: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """ADX-based regime classification — trending vs range-bound."""
        adx = _get_float(bar, session_ctx, "adx14")

        if adx is None:
            return None

        # Determine if this is a mean-reversion or trend-following signal
        # based on strategy_name from context
        signal = (bar if "strategy_name" not in bar else {}) or {}

        if adx < 20:
            # Weak trend / range-bound — mean reversion strategies favored
            direction = "neutral"
            strength = 0.6
            obs = f"ADX {adx:.0f} — range-bound regime, mean reversion strategies favored over trend following"
            return EvidenceCard(
                card_id="mr_regime",
                source="expert_mean_reversion",
                layer="certainty",
                observation=obs,
                direction=direction,
                strength=strength,
                data_points=1,
                raw_data={"adx": adx, "regime": "range_bound"},
            )
        elif adx > 30:
            # Strong trend — trend following favored, mean reversion risky
            direction = "neutral"
            strength = 0.55
            obs = f"ADX {adx:.0f} — strong trending regime, trend following favored, mean reversion risky"
            return EvidenceCard(
                card_id="mr_regime",
                source="expert_mean_reversion",
                layer="certainty",
                observation=obs,
                direction=direction,
                strength=strength,
                data_points=1,
                raw_data={"adx": adx, "regime": "trending"},
            )

        return None  # Moderate ADX — no strong regime signal

    def _vwap_stretch_card(
        self, bar: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """Distance from VWAP σ bands — extreme stretch = reversion likely."""
        price = _get_float(bar, session_ctx, "close")
        upper_2 = _get_float(bar, session_ctx, "vwap_sigma_upper_2")
        lower_2 = _get_float(bar, session_ctx, "vwap_sigma_lower_2")

        if price is None:
            return None

        if upper_2 is not None and price >= upper_2:
            # At +2σ VWAP band — extreme stretch
            if signal_dir == "SHORT":
                direction, strength = "bearish", 0.65
                obs = f"Price at +2σ VWAP band ({upper_2:.0f}) — extreme stretch, supports SHORT reversion"
            else:
                direction, strength = "bearish", 0.4
                obs = f"Price at +2σ VWAP band ({upper_2:.0f}) — extreme stretch, LONG chasing into ceiling"
            return EvidenceCard(
                card_id="mr_vwap_stretch",
                source="expert_mean_reversion",
                layer="probabilistic",
                observation=obs,
                direction=direction,
                strength=strength,
                data_points=2,
                raw_data={"price": price, "vwap_band": "+2sigma", "level": upper_2},
            )

        if lower_2 is not None and price <= lower_2:
            # At -2σ VWAP band — extreme stretch
            if signal_dir == "LONG":
                direction, strength = "bullish", 0.65
                obs = f"Price at -2σ VWAP band ({lower_2:.0f}) — extreme stretch, supports LONG reversion"
            else:
                direction, strength = "bullish", 0.4
                obs = f"Price at -2σ VWAP band ({lower_2:.0f}) — extreme stretch, SHORT chasing into floor"
            return EvidenceCard(
                card_id="mr_vwap_stretch",
                source="expert_mean_reversion",
                layer="probabilistic",
                observation=obs,
                direction=direction,
                strength=strength,
                data_points=2,
                raw_data={"price": price, "vwap_band": "-2sigma", "level": lower_2},
            )

        return None


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
