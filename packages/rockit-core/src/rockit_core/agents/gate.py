"""
CRI Gate Agent — readiness check before observer evaluation.

Reads CRI (Confirmation/Readiness/Inflection) status from the deterministic
tape. Currently DISABLED as scoring evidence — always produces a neutral
pass-through card. CRI status is logged for future analysis but does not
influence the orchestrator's scoring.

TODO: Revisit CRI scoring after studying its correlation with trade outcomes.
The original implementation penalized STAND_DOWN with a 0.7 bearish card in
the certainty layer, which was too aggressive and blocked viable signals.
"""

from __future__ import annotations

from rockit_core.agents.base import AgentBase
from rockit_core.agents.evidence import EvidenceCard


class CRIGateAgent(AgentBase):
    """Gate agent that checks CRI readiness status.

    Currently pass-through only — logs CRI status but does not produce
    directional evidence. Will be re-enabled after CRI scoring is re-studied.
    """

    @property
    def name(self) -> str:
        return "cri_gate"

    def evaluate(self, context: dict) -> list[EvidenceCard]:
        """Produce a neutral pass-through card with CRI status logged."""
        tape_row = context.get("tape_row") or {}
        session_ctx = context.get("session_context") or {}

        cri_status = (
            tape_row.get("cri_status")
            or session_ctx.get("cri_status")
            or ""
        )

        # Always neutral — CRI is logged but does not influence scoring
        return [
            EvidenceCard(
                card_id="gate_cri_passthrough",
                source="gate_cri",
                layer="certainty",
                observation=f"CRI status: {cri_status or 'MISSING'} (pass-through, scoring disabled)",
                direction="neutral",
                strength=0.0,
                data_points=1 if cri_status else 0,
                raw_data={"cri_status": cri_status},
            )
        ]

    def passes(self, context: dict) -> bool:
        """CRI gate always passes — scoring disabled."""
        return True
