"""
Advocate Agent — builds the case FOR a trade signal using LLM reasoning.

Receives evidence cards from deterministic observers + signal context.
Returns DebateResult with admit/reject decisions and instinct-layer cards.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from rockit_core.agents.base import AgentBase
from rockit_core.agents.evidence import DebateResult, EvidenceCard
from rockit_core.agents.llm_client import OllamaClient

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[6] / "configs" / "prompts" / "advocate_system.md"


def _load_system_prompt() -> str:
    """Load the advocate system prompt from configs/prompts/."""
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("Advocate prompt not found at %s, using fallback", _PROMPT_PATH)
        return (
            "You are ADVOCATE. Build the case FOR the trade. "
            "Output valid JSON with: admit, reject, instinct_cards, thesis, direction, confidence, warnings."
        )


class AdvocateAgent(AgentBase):
    """LLM-powered agent that builds the case for a trade signal."""

    def __init__(self, llm_client: OllamaClient, max_tokens: int = 4000):
        self._llm = llm_client
        self._max_tokens = max_tokens
        self._system_prompt = _load_system_prompt()

    @property
    def name(self) -> str:
        return "advocate"

    def evaluate(self, context: dict) -> list[EvidenceCard]:
        """Run Advocate LLM — returns instinct-layer cards.

        Args:
            context: Dict with 'evidence_cards', 'signal', 'session_context'.

        Returns:
            List of instinct-layer EvidenceCards from LLM reasoning.
        """
        result = self.debate(context)
        return result.instinct_cards

    def debate(self, context: dict) -> DebateResult:
        """Full debate — returns DebateResult with admit/reject/instinct/thesis."""
        evidence_cards: list[EvidenceCard] = context.get("evidence_cards", [])
        signal = context.get("signal", {})
        session_ctx = context.get("session_context", {})
        historical = context.get("historical", {})

        user_prompt = self._build_prompt(evidence_cards, signal, session_ctx, historical)
        response = self._llm.chat(self._system_prompt, user_prompt, self._max_tokens)

        if response.get("error"):
            logger.warning("Advocate LLM error: %s", response["error"])
            return DebateResult(agent="advocate", raw_response=str(response))

        return self._parse_response(response.get("content", ""), evidence_cards)

    def _build_prompt(
        self,
        evidence_cards: list[EvidenceCard],
        signal: dict,
        session_ctx: dict,
        historical: dict | None = None,
    ) -> str:
        """Build the user prompt from evidence cards, context, and historical stats."""
        cards_json = [
            {
                "card_id": c.card_id,
                "source": c.source,
                "layer": c.layer,
                "observation": c.observation,
                "direction": c.direction,
                "strength": c.strength,
                "data_points": c.data_points,
            }
            for c in evidence_cards
            if c.source != "gate_cri"  # Gate cards are structural, not evidence
        ]

        context_summary = {
            "day_type": session_ctx.get("day_type", "unknown"),
            "session_bias": session_ctx.get("session_bias") or session_ctx.get("regime_bias", "unknown"),
            "confidence": session_ctx.get("confidence", "unknown"),
            "time": session_ctx.get("current_et_time", "unknown"),
            "trend_strength": session_ctx.get("trend_strength", "unknown"),
            "dpoc_migration": session_ctx.get("dpoc_migration", "unknown"),
        }

        prompt_data = {
            "signal": {
                "direction": signal.get("direction", ""),
                "strategy_name": signal.get("strategy_name", ""),
                "entry_price": signal.get("entry_price", ""),
                "confidence": signal.get("confidence", ""),
            },
            "evidence_cards": cards_json,
            "session_context": context_summary,
        }

        # Add DuckDB historical stats if available
        if historical:
            prompt_data["historical_stats"] = historical

        return json.dumps(prompt_data, indent=2)

    def _parse_response(
        self, content: str, evidence_cards: list[EvidenceCard]
    ) -> DebateResult:
        """Parse LLM JSON response into DebateResult."""
        try:
            # Strip markdown code fences if present
            cleaned = content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                # Remove first and last lines (```json and ```)
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            data = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Advocate response not valid JSON: %s", exc)
            return DebateResult(agent="advocate", raw_response=content)

        # Parse instinct cards
        instinct_cards: list[EvidenceCard] = []
        for i, ic in enumerate(data.get("instinct_cards", [])):
            if not isinstance(ic, dict):
                continue
            direction = ic.get("direction", "neutral")
            if direction not in ("bullish", "bearish", "neutral"):
                direction = "neutral"
            try:
                instinct_cards.append(
                    EvidenceCard(
                        card_id=f"advocate_instinct_{i}",
                        source="debate_advocate",
                        layer="instinct",
                        observation=ic.get("observation", ""),
                        direction=direction,
                        strength=max(0.0, min(1.0, float(ic.get("strength", 0.5)))),
                        data_points=0,
                        raw_data={"reasoning": ic.get("reasoning", "")},
                    )
                )
            except (ValueError, TypeError):
                continue

        return DebateResult(
            agent="advocate",
            admit=data.get("admit", []),
            reject=data.get("reject", []),
            instinct_cards=instinct_cards,
            thesis=data.get("thesis", ""),
            direction=data.get("direction", "neutral"),
            confidence=float(data.get("confidence", 0.5)),
            warnings=data.get("warnings", []),
            raw_response=content,
        )
