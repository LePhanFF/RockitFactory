"""
Price Divergence Expert — cross-instrument and SMT divergence analysis.

Produces up to 2 cards:
  1. SMT divergence (pre-market NQ vs ES vs YM divergence from snapshot)
  2. Overnight compression (london range compressed relative to overnight — breakout signal)

Uses snapshot_json premarket data. Full intraday cross-instrument divergence
requires multi-instrument data loader (future enhancement).
"""

from __future__ import annotations

import json as _json

from rockit_core.agents.evidence import EvidenceCard
from rockit_core.agents.experts.base import DomainExpert


class DivergenceExpert(DomainExpert):
    """Price divergence domain expert — SMT and compression signals."""

    @property
    def domain(self) -> str:
        return "divergence"

    def scorecard(self, context: dict) -> list[EvidenceCard]:
        cards: list[EvidenceCard] = []
        tape_row = context.get("tape_row") or {}
        session_ctx = context.get("session_context") or {}
        signal = context.get("signal") or {}
        signal_dir = signal.get("direction", "").upper()

        for fn in (
            self._smt_divergence_card,
            self._overnight_compression_card,
        ):
            c = fn(tape_row, session_ctx, signal_dir)
            if c is not None:
                cards.append(c)

        return cards

    def _smt_divergence_card(
        self, tape_row: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """SMT divergence from premarket data."""
        snapshot = tape_row.get("snapshot_json") or {}
        if isinstance(snapshot, str):
            try:
                snapshot = _json.loads(snapshot)
            except (_json.JSONDecodeError, TypeError):
                snapshot = {}

        premarket = snapshot.get("premarket") or {}
        smt = premarket.get("smt_preopen_signal") or premarket.get("smt_divergence")

        if not smt:
            return None

        # SMT can be a dict or string
        if isinstance(smt, dict):
            smt_type = smt.get("type", "").lower()
            smt_desc = smt.get("description", "")
        elif isinstance(smt, str):
            smt_type = smt.lower()
            smt_desc = smt
        else:
            return None

        if not smt_type or smt_type == "none":
            return None

        if "bullish" in smt_type:
            if signal_dir == "LONG":
                direction, strength = "bullish", 0.65
                obs = f"Bullish SMT divergence — {smt_desc or 'NQ/ES diverging bullish'}, supports LONG"
            else:
                direction, strength = "bullish", 0.4
                obs = f"Bullish SMT divergence — {smt_desc or 'NQ/ES diverging bullish'}, warns against SHORT"
        elif "bearish" in smt_type:
            if signal_dir == "SHORT":
                direction, strength = "bearish", 0.65
                obs = f"Bearish SMT divergence — {smt_desc or 'NQ/ES diverging bearish'}, supports SHORT"
            else:
                direction, strength = "bearish", 0.4
                obs = f"Bearish SMT divergence — {smt_desc or 'NQ/ES diverging bearish'}, warns against LONG"
        else:
            return None

        return EvidenceCard(
            card_id="divergence_smt",
            source="expert_divergence",
            layer="probabilistic",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=1,
            raw_data={"smt_type": smt_type, "smt_desc": smt_desc},
        )

    def _overnight_compression_card(
        self, tape_row: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """Overnight range compression — narrow London range signals pending breakout."""
        snapshot = tape_row.get("snapshot_json") or {}
        if isinstance(snapshot, str):
            try:
                snapshot = _json.loads(snapshot)
            except (_json.JSONDecodeError, TypeError):
                snapshot = {}

        premarket = snapshot.get("premarket") or {}
        compression = premarket.get("compression_flag", False)

        if not compression:
            return None

        return EvidenceCard(
            card_id="divergence_compression",
            source="expert_divergence",
            layer="instinct",
            observation="Overnight compression detected — London range < 35% of overnight range, expect directional breakout at RTH open",
            direction="neutral",
            strength=0.55,
            data_points=1,
            raw_data={"compression_flag": True},
        )
