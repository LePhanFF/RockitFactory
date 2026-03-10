"""
CRI Gate Agent — readiness check before observer evaluation.

Reads CRI (Confirmation/Readiness/Inflection) status from the deterministic
tape and blocks STAND_DOWN signals. Missing CRI data passes through
(don't block on missing data).
"""

from __future__ import annotations

from rockit_core.agents.base import AgentBase
from rockit_core.agents.evidence import EvidenceCard


class CRIGateAgent(AgentBase):
    """Gate agent that checks CRI readiness status."""

    @property
    def name(self) -> str:
        return "cri_gate"

    def evaluate(self, context: dict) -> list[EvidenceCard]:
        """Produce a single evidence card for CRI status."""
        tape_row = context.get("tape_row") or {}
        session_ctx = context.get("session_context") or {}

        # Try tape_row first, fall back to session_context
        cri_status = (
            tape_row.get("cri_status")
            or session_ctx.get("cri_status")
            or ""
        )

        if not cri_status or cri_status.upper() == "READY":
            return [
                EvidenceCard(
                    card_id="gate_cri_ready",
                    source="gate_cri",
                    layer="certainty",
                    observation=f"CRI status: {cri_status or 'MISSING (pass-through)'}",
                    direction="neutral",
                    strength=1.0,
                    data_points=1 if cri_status else 0,
                    raw_data={"cri_status": cri_status},
                )
            ]

        if cri_status.upper() == "STAND_DOWN":
            return [
                EvidenceCard(
                    card_id="gate_cri_standdown",
                    source="gate_cri",
                    layer="certainty",
                    observation=f"CRI status: STAND_DOWN — blocking signal",
                    direction="neutral",
                    strength=0.0,
                    data_points=1,
                    raw_data={"cri_status": cri_status},
                )
            ]

        # Any other status (e.g., CAUTION) — pass through with reduced strength
        return [
            EvidenceCard(
                card_id=f"gate_cri_{cri_status.lower()}",
                source="gate_cri",
                layer="certainty",
                observation=f"CRI status: {cri_status}",
                direction="neutral",
                strength=0.5,
                data_points=1,
                raw_data={"cri_status": cri_status},
            )
        ]

    def passes(self, context: dict) -> bool:
        """Convenience: does the gate allow this signal through?"""
        cards = self.evaluate(context)
        if not cards:
            return True
        # STAND_DOWN has strength 0.0
        return cards[0].strength > 0.0
