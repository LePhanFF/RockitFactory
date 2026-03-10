"""
Momentum Observer — reads trend/DPOC/extension data from deterministic snapshots.

Produces up to 5 evidence cards:
  1. DPOC regime (trending/rotating/migrating)
  2. Trend strength alignment
  3. Wick parade traps (bear/bull wick counts)
  4. Extension multiple (IB overextension warning)
  5. Bias alignment (session bias vs signal direction)
"""

from __future__ import annotations

import json as _json

from rockit_core.agents.base import AgentBase
from rockit_core.agents.evidence import EvidenceCard

_BULLISH_BIASES = {"Bullish", "BULL", "Very Bullish", "bullish"}
_BEARISH_BIASES = {"Bearish", "BEAR", "Very Bearish", "bearish"}


class MomentumObserver(AgentBase):
    """Reads momentum/trend data and emits evidence cards."""

    @property
    def name(self) -> str:
        return "observer_momentum"

    def evaluate(self, context: dict) -> list[EvidenceCard]:
        cards: list[EvidenceCard] = []
        tape_row = context.get("tape_row") or {}
        session_ctx = context.get("session_context") or {}
        signal = context.get("signal") or {}
        signal_dir = signal.get("direction", "").upper()

        c = self._dpoc_regime_card(tape_row, session_ctx, signal_dir)
        if c:
            cards.append(c)

        c = self._trend_strength_card(tape_row, session_ctx, signal_dir)
        if c:
            cards.append(c)

        c = self._wick_traps_card(tape_row, session_ctx, signal_dir)
        if c:
            cards.append(c)

        c = self._extension_card(tape_row, session_ctx, signal_dir)
        if c:
            cards.append(c)

        c = self._bias_alignment_card(tape_row, session_ctx, signal_dir)
        if c:
            cards.append(c)

        return cards

    def _dpoc_regime_card(
        self, tape_row: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """DPOC migration indicates trending vs rotating market."""
        dpoc = (
            tape_row.get("dpoc_migration")
            or session_ctx.get("dpoc_migration")
            or ""
        ).lower()

        if not dpoc:
            return None

        if "trending" in dpoc or "on_the_move" in dpoc or "migrating_up" in dpoc:
            if signal_dir == "LONG":
                direction, strength = "bullish", 0.7
                obs = f"DPOC {dpoc} — trending market aligned with LONG"
            else:
                direction, strength = "bearish", 0.3
                obs = f"DPOC {dpoc} — trending up, SHORT opposes momentum"
        elif "migrating_down" in dpoc:
            if signal_dir == "SHORT":
                direction, strength = "bearish", 0.7
                obs = f"DPOC {dpoc} — trending down aligned with SHORT"
            else:
                direction, strength = "bullish", 0.3
                obs = f"DPOC {dpoc} — trending down, LONG opposes momentum"
        elif "rotating" in dpoc or "stationary" in dpoc:
            direction, strength = "neutral", 0.5
            obs = f"DPOC {dpoc} — range-bound, no momentum edge"
        else:
            direction, strength = "neutral", 0.4
            obs = f"DPOC status: {dpoc}"

        return EvidenceCard(
            card_id="momentum_dpoc_regime",
            source="observer_momentum",
            layer="certainty",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=1,
            raw_data={"dpoc_migration": dpoc, "signal_direction": signal_dir},
        )

    def _trend_strength_card(
        self, tape_row: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """Trend strength alignment with signal."""
        trend = (
            tape_row.get("trend_strength")
            or session_ctx.get("trend_strength")
            or ""
        ).lower()

        if not trend:
            return None

        if "strong" in trend and "bull" in trend:
            if signal_dir == "LONG":
                direction, strength = "bullish", 0.8
                obs = f"Strong bullish trend — aligned with LONG"
            else:
                direction, strength = "bullish", 0.2
                obs = f"Strong bullish trend — WARNING: SHORT opposes strong trend"
        elif "strong" in trend and "bear" in trend:
            if signal_dir == "SHORT":
                direction, strength = "bearish", 0.8
                obs = f"Strong bearish trend — aligned with SHORT"
            else:
                direction, strength = "bearish", 0.2
                obs = f"Strong bearish trend — WARNING: LONG opposes strong trend"
        elif "weak" in trend or "neutral" in trend or "flat" in trend:
            direction, strength = "neutral", 0.5
            obs = f"Weak/neutral trend ({trend}) — no directional conviction"
        else:
            # Moderate trend
            direction, strength = "neutral", 0.5
            obs = f"Trend: {trend} — moderate conviction"

        return EvidenceCard(
            card_id="momentum_trend_strength",
            source="observer_momentum",
            layer="certainty",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=1,
            raw_data={"trend_strength": trend, "signal_direction": signal_dir},
        )

    def _wick_traps_card(
        self, tape_row: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """High wick counts indicate trapping — bearish for LONG, bullish for SHORT."""
        snapshot = tape_row.get("snapshot_json") or {}
        if isinstance(snapshot, str):
            try:
                snapshot = _json.loads(snapshot)
            except (_json.JSONDecodeError, TypeError):
                snapshot = {}

        wick_data = snapshot.get("wick_parade") or {}
        bear_wicks = wick_data.get("bear_wick_count", 0)
        bull_wicks = wick_data.get("bull_wick_count", 0)

        if not bear_wicks and not bull_wicks:
            return None

        # High bear wick count = sellers getting trapped → bullish
        # High bull wick count = buyers getting trapped → bearish
        if bear_wicks >= 3 and signal_dir == "LONG":
            direction, strength = "bullish", 0.6
            obs = f"Bear wick parade ({bear_wicks} wicks) — sellers trapped, supports LONG"
        elif bull_wicks >= 3 and signal_dir == "SHORT":
            direction, strength = "bearish", 0.6
            obs = f"Bull wick parade ({bull_wicks} wicks) — buyers trapped, supports SHORT"
        elif bear_wicks >= 3 and signal_dir == "SHORT":
            direction, strength = "bullish", 0.35
            obs = f"Bear wick parade ({bear_wicks} wicks) — sellers trapped, warns against SHORT"
        elif bull_wicks >= 3 and signal_dir == "LONG":
            direction, strength = "bearish", 0.35
            obs = f"Bull wick parade ({bull_wicks} wicks) — buyers trapped, warns against LONG"
        else:
            direction, strength = "neutral", 0.5
            obs = f"Wick counts: bear={bear_wicks}, bull={bull_wicks} — no strong signal"

        return EvidenceCard(
            card_id="momentum_wick_traps",
            source="observer_momentum",
            layer="instinct",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=bear_wicks + bull_wicks,
            raw_data={"bear_wicks": bear_wicks, "bull_wicks": bull_wicks},
        )

    def _extension_card(
        self, tape_row: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """IB extension multiple — overextension warning."""
        ext = tape_row.get("extension_multiple") or session_ctx.get("extension_multiple")

        if ext is None:
            return None

        try:
            ext = float(ext)
        except (TypeError, ValueError):
            return None

        if ext <= 0:
            return None

        if ext >= 2.0:
            # Overextended — contrarian warning
            direction = "bearish" if signal_dir == "LONG" else "bullish"
            strength = 0.3  # Warning against signal
            obs = f"IB extension {ext:.1f}x — overextended, risk of mean reversion"
        elif ext >= 1.5:
            direction = "neutral"
            strength = 0.5
            obs = f"IB extension {ext:.1f}x — moderately extended"
        else:
            direction = "neutral"
            strength = 0.5
            obs = f"IB extension {ext:.1f}x — within normal range"

        return EvidenceCard(
            card_id="momentum_extension",
            source="observer_momentum",
            layer="probabilistic",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=1,
            raw_data={"extension_multiple": ext},
        )

    def _bias_alignment_card(
        self, tape_row: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """Session bias alignment with signal direction."""
        bias = (
            tape_row.get("bias")
            or session_ctx.get("session_bias")
            or session_ctx.get("regime_bias")
            or ""
        )

        if not bias:
            return None

        if bias in _BULLISH_BIASES:
            if signal_dir == "LONG":
                direction, strength = "bullish", 0.75
                obs = f"Session bias {bias} — strongly aligned with LONG"
            else:
                direction, strength = "bullish", 0.25
                obs = f"Session bias {bias} — SHORT opposes session bias"
        elif bias in _BEARISH_BIASES:
            if signal_dir == "SHORT":
                direction, strength = "bearish", 0.75
                obs = f"Session bias {bias} — strongly aligned with SHORT"
            else:
                direction, strength = "bearish", 0.25
                obs = f"Session bias {bias} — LONG opposes session bias"
        else:
            direction, strength = "neutral", 0.5
            obs = f"Session bias {bias} — neutral, no directional edge"

        return EvidenceCard(
            card_id="momentum_bias_alignment",
            source="observer_momentum",
            layer="certainty",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=1,
            raw_data={"session_bias": bias, "signal_direction": signal_dir},
        )
