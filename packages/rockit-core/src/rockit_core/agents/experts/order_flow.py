"""
Order Flow Expert — CVD, delta, and imbalance analysis.

Produces up to 3 cards:
  1. CVD trend (cumulative delta alignment with price)
  2. CVD divergence (price vs CVD disagreement — distribution/accumulation)
  3. Delta imbalance (extreme ask/bid ratio)

Uses pre-computed columns: cumulative_delta, delta_zscore, imbalance_ratio,
cvd_div_bull, cvd_div_bear.
"""

from __future__ import annotations

import math

from rockit_core.agents.evidence import EvidenceCard
from rockit_core.agents.experts.base import DomainExpert


class OrderFlowExpert(DomainExpert):
    """Order flow domain expert — CVD, delta, and imbalance signals."""

    @property
    def domain(self) -> str:
        return "order_flow"

    def scorecard(self, context: dict) -> list[EvidenceCard]:
        cards: list[EvidenceCard] = []
        bar = context.get("bar") or {}
        session_ctx = context.get("session_context") or {}
        signal = context.get("signal") or {}
        signal_dir = signal.get("direction", "").upper()

        for fn in (
            self._cvd_trend_card,
            self._cvd_divergence_card,
            self._delta_imbalance_card,
        ):
            c = fn(bar, session_ctx, signal_dir)
            if c is not None:
                cards.append(c)

        return cards

    def _cvd_trend_card(
        self, bar: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """CVD trend alignment with signal direction."""
        cvd = _get_float(bar, session_ctx, "cumulative_delta")
        cvd_ma = _get_float(bar, session_ctx, "cumulative_delta_ma")

        if cvd is None:
            return None

        # Use CVD vs its MA for direction, or just sign of CVD
        if cvd_ma is not None:
            cvd_bullish = cvd > cvd_ma
        else:
            cvd_bullish = cvd > 0

        if cvd_bullish:
            if signal_dir == "LONG":
                direction, strength = "bullish", 0.7
                obs = f"CVD trending bullish (CVD={cvd:,.0f}) — buying pressure aligned with LONG"
            else:
                direction, strength = "bullish", 0.35
                obs = f"CVD trending bullish (CVD={cvd:,.0f}) — buying pressure opposes SHORT"
        else:
            if signal_dir == "SHORT":
                direction, strength = "bearish", 0.7
                obs = f"CVD trending bearish (CVD={cvd:,.0f}) — selling pressure aligned with SHORT"
            else:
                direction, strength = "bearish", 0.35
                obs = f"CVD trending bearish (CVD={cvd:,.0f}) — selling pressure opposes LONG"

        return EvidenceCard(
            card_id="flow_cvd_trend",
            source="expert_order_flow",
            layer="certainty",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=2 if cvd_ma else 1,
            raw_data={"cvd": cvd, "cvd_ma": cvd_ma, "cvd_bullish": cvd_bullish},
        )

    def _cvd_divergence_card(
        self, bar: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """CVD divergence — price and volume disagree (distribution/accumulation)."""
        div_bull = _get_bool(bar, "cvd_div_bull")
        div_bear = _get_bool(bar, "cvd_div_bear")

        if not div_bull and not div_bear:
            return None

        if div_bull:
            # Bullish divergence: price making lower lows but CVD making higher lows
            if signal_dir == "LONG":
                direction, strength = "bullish", 0.7
                obs = "Bullish CVD divergence — hidden accumulation despite price weakness, strongly supports LONG"
            else:
                direction, strength = "bullish", 0.45
                obs = "Bullish CVD divergence — hidden accumulation, warns against SHORT"
            return EvidenceCard(
                card_id="flow_cvd_divergence",
                source="expert_order_flow",
                layer="probabilistic",
                observation=obs,
                direction=direction,
                strength=strength,
                data_points=1,
                raw_data={"divergence": "bullish"},
            )

        if div_bear:
            # Bearish divergence: price making higher highs but CVD making lower highs
            if signal_dir == "SHORT":
                direction, strength = "bearish", 0.7
                obs = "Bearish CVD divergence — hidden distribution despite price strength, strongly supports SHORT"
            else:
                direction, strength = "bearish", 0.45
                obs = "Bearish CVD divergence — hidden distribution, warns against LONG"
            return EvidenceCard(
                card_id="flow_cvd_divergence",
                source="expert_order_flow",
                layer="probabilistic",
                observation=obs,
                direction=direction,
                strength=strength,
                data_points=1,
                raw_data={"divergence": "bearish"},
            )

        return None

    def _delta_imbalance_card(
        self, bar: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """Extreme delta z-score — unusual buying/selling pressure."""
        zscore = _get_float(bar, session_ctx, "delta_zscore")

        if zscore is None or abs(zscore) < 2.0:
            return None

        if zscore >= 2.0:
            # Extreme buying
            if signal_dir == "LONG":
                direction, strength = "bullish", 0.6
                obs = f"Extreme buying pressure (delta z={zscore:.1f}) — aggressive buyers, supports LONG"
            else:
                direction, strength = "bullish", 0.4
                obs = f"Extreme buying pressure (delta z={zscore:.1f}) — aggressive buyers, warns against SHORT"
        else:
            # Extreme selling (zscore <= -2.0)
            if signal_dir == "SHORT":
                direction, strength = "bearish", 0.6
                obs = f"Extreme selling pressure (delta z={zscore:.1f}) — aggressive sellers, supports SHORT"
            else:
                direction, strength = "bearish", 0.4
                obs = f"Extreme selling pressure (delta z={zscore:.1f}) — aggressive sellers, warns against LONG"

        return EvidenceCard(
            card_id="flow_delta_imbalance",
            source="expert_order_flow",
            layer="instinct",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=1,
            raw_data={"delta_zscore": zscore},
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


def _get_bool(bar: dict, key: str) -> bool:
    v = bar.get(key)
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    try:
        return bool(v)
    except (TypeError, ValueError):
        return False
