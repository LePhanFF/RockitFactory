"""
Deterministic Orchestrator — scores evidence cards and makes TAKE/SKIP/REDUCE_SIZE decisions.

Supports two modes:
  1. decide()            — deterministic-only (all cards admitted, fast)
  2. decide_with_debate() — LLM debate resolves disputed cards, adds instinct
"""

from __future__ import annotations

from rockit_core.agents.evidence import (
    AgentDecision,
    ConfluenceResult,
    DebateResult,
    EvidenceCard,
)

# Layer weights for scoring
LAYER_WEIGHTS = {
    "certainty": 1.0,
    "probabilistic": 0.8,
    "instinct": 0.6,
}

# Decision thresholds
TAKE_THRESHOLD = 0.3
SKIP_THRESHOLD = 0.1


class DeterministicOrchestrator:
    """Rule-based orchestrator that scores evidence and decides TAKE/SKIP/REDUCE_SIZE."""

    def __init__(
        self,
        take_threshold: float = TAKE_THRESHOLD,
        skip_threshold: float = SKIP_THRESHOLD,
        layer_weights: dict[str, float] | None = None,
    ):
        self.take_threshold = take_threshold
        self.skip_threshold = skip_threshold
        self.layer_weights = layer_weights or LAYER_WEIGHTS

    def decide(
        self,
        signal_dict: dict,
        evidence_cards: list[EvidenceCard],
        gate_passed: bool,
    ) -> AgentDecision:
        """Score evidence cards and return a decision.

        Args:
            signal_dict: Signal info with at least 'direction', 'strategy_name'.
            evidence_cards: All cards from gate + observers.
            gate_passed: Whether the CRI gate allows this signal.

        Returns:
            AgentDecision with TAKE, SKIP, or REDUCE_SIZE.
        """
        signal_dir = signal_dict.get("direction", "").upper()

        # Admit all cards (MVP: no debate filtering)
        for card in evidence_cards:
            card.admitted = True

        # Score confluence
        confluence = self._build_confluence(evidence_cards, signal_dir)

        # Make decision
        decision, reasoning = self._apply_rules(confluence, signal_dir)

        return AgentDecision(
            decision=decision,
            confidence=confluence.conviction,
            direction=confluence.direction if confluence.direction != "neutral" else None,
            confluence=confluence,
            reasoning=reasoning,
            gate_passed=True,
            evidence_cards=evidence_cards,
        )

    def decide_with_debate(
        self,
        signal_dict: dict,
        evidence_cards: list[EvidenceCard],
        gate_passed: bool,
        advocate_result: DebateResult,
        skeptic_result: DebateResult,
    ) -> AgentDecision:
        """Score evidence with debate-informed card admission.

        1. Resolve disputed cards (both agree = done, disputed = 0.7× weight).
        2. Add instinct cards from both sides (weight 0.6).
        3. Recompute confluence with admitted-only cards.
        4. Include debate reasoning in decision.
        """
        signal_dir = signal_dict.get("direction", "").upper()

        # Resolve card admission disputes
        admitted_cards = self._resolve_disputes(
            evidence_cards, advocate_result, skeptic_result
        )

        # Add instinct cards from debate (already in evidence_cards list from pipeline)
        # Mark debate instinct cards as admitted
        for card in evidence_cards:
            if card.source in ("debate_advocate", "debate_skeptic"):
                card.admitted = True

        # Score confluence (admitted cards only)
        confluence = self._build_confluence_admitted(evidence_cards, signal_dir)

        # Make decision
        decision, base_reasoning = self._apply_rules(confluence, signal_dir)

        # Enrich reasoning with debate context
        debate_reasoning = self._debate_reasoning(
            advocate_result, skeptic_result, decision
        )

        # Capture debate context for persistence
        debate_context = {
            "advocate": {
                "thesis": advocate_result.thesis,
                "direction": advocate_result.direction,
                "confidence": advocate_result.confidence,
            },
            "skeptic": {
                "thesis": skeptic_result.thesis,
                "direction": skeptic_result.direction,
                "confidence": skeptic_result.confidence,
                "warnings": skeptic_result.warnings,
            },
            "cards_admitted": [c.card_id for c in evidence_cards if c.admitted is True],
            "cards_rejected": [c.card_id for c in evidence_cards if c.admitted is False],
            "instinct_cards": [
                {"observation": c.observation, "direction": c.direction, "strength": c.strength}
                for c in evidence_cards if c.source in ("debate_advocate", "debate_skeptic")
            ],
        }

        return AgentDecision(
            decision=decision,
            confidence=confluence.conviction,
            direction=confluence.direction if confluence.direction != "neutral" else None,
            confluence=confluence,
            reasoning=f"{base_reasoning} | Debate: {debate_reasoning}",
            gate_passed=True,
            evidence_cards=evidence_cards,
            debate=debate_context,
        )

    def _resolve_disputes(
        self,
        evidence_cards: list[EvidenceCard],
        advocate_result: DebateResult,
        skeptic_result: DebateResult,
    ) -> list[EvidenceCard]:
        """Resolve card admission between Advocate and Skeptic.

        Rules:
          - Both admit → admitted (full weight)
          - Both reject → rejected
          - Advocate admits, Skeptic rejects → admitted at 0.7× strength
          - Advocate rejects, Skeptic admits → admitted at 0.7× strength
          - Not mentioned by either → admitted (default)
        """
        adv_admit = set(advocate_result.admit)
        adv_reject = set(advocate_result.reject)
        skp_admit = set(skeptic_result.admit)
        skp_reject = set(skeptic_result.reject)

        admitted: list[EvidenceCard] = []
        for card in evidence_cards:
            if card.source == "gate_cri":
                card.admitted = True
                admitted.append(card)
                continue
            if card.source in ("debate_advocate", "debate_skeptic"):
                # Instinct cards from debate — always admitted
                card.admitted = True
                admitted.append(card)
                continue

            cid = card.card_id

            # Both agree to reject
            if cid in adv_reject and cid in skp_reject:
                card.admitted = False
                continue

            # Both agree to admit
            if cid in adv_admit and cid in skp_admit:
                card.admitted = True
                admitted.append(card)
                continue

            # Disputed: one admits, the other rejects → admit at 0.7× weight
            if (cid in adv_admit and cid in skp_reject) or (
                cid in adv_reject and cid in skp_admit
            ):
                card.admitted = True
                card.strength = card.strength * 0.7  # Reduce disputed card weight
                admitted.append(card)
                continue

            # Not mentioned by either → admit by default
            card.admitted = True
            admitted.append(card)

        return admitted

    def _build_confluence_admitted(
        self, cards: list[EvidenceCard], signal_dir: str
    ) -> ConfluenceResult:
        """Aggregate only admitted evidence cards."""
        bull_score = 0.0
        bear_score = 0.0
        bull_count = 0
        bear_count = 0
        rejected = 0

        for card in cards:
            if card.source == "gate_cri" and card.direction == "neutral":
                continue  # Neutral gate cards (READY/MISSING) don't contribute

            if card.admitted is False:
                rejected += 1
                continue

            weight = self.layer_weights.get(card.layer, 0.5)
            weighted = card.strength * weight

            if card.direction == "bullish":
                bull_score += weighted
                bull_count += 1
            elif card.direction == "bearish":
                bear_score += weighted
                bear_count += 1

        total = bull_score + bear_score
        conviction = abs(bull_score - bear_score) / total if total > 0 else 0.0

        if bull_score > bear_score:
            direction = "bullish"
        elif bear_score > bull_score:
            direction = "bearish"
        else:
            direction = "neutral"

        return ConfluenceResult(
            direction=direction,
            conviction=conviction,
            bull_score=round(bull_score, 4),
            bear_score=round(bear_score, 4),
            bull_cards=bull_count,
            bear_cards=bear_count,
            total_evidence=len(cards),
            total_rejected=rejected,
            cards=cards,
        )

    @staticmethod
    def _debate_reasoning(
        advocate_result: DebateResult,
        skeptic_result: DebateResult,
        decision: str,
    ) -> str:
        """Summarize debate outcome for the reasoning field."""
        parts = []
        if advocate_result.thesis:
            parts.append(f"Advocate ({advocate_result.direction}, {advocate_result.confidence:.0%}): {advocate_result.thesis[:80]}")
        if skeptic_result.thesis:
            parts.append(f"Skeptic ({skeptic_result.direction}, {skeptic_result.confidence:.0%}): {skeptic_result.thesis[:80]}")
        if skeptic_result.warnings:
            parts.append(f"Warnings: {', '.join(skeptic_result.warnings[:3])}")
        return " | ".join(parts) if parts else "No debate reasoning"

    def _build_confluence(
        self, cards: list[EvidenceCard], signal_dir: str
    ) -> ConfluenceResult:
        """Aggregate evidence cards into bull/bear scores."""
        bull_score = 0.0
        bear_score = 0.0
        bull_count = 0
        bear_count = 0
        rejected = 0

        for card in cards:
            if card.source == "gate_cri" and card.direction == "neutral":
                continue  # Neutral gate cards (READY/MISSING) don't contribute to scoring

            weight = self.layer_weights.get(card.layer, 0.5)
            weighted = card.strength * weight

            if card.direction == "bullish":
                bull_score += weighted
                bull_count += 1
            elif card.direction == "bearish":
                bear_score += weighted
                bear_count += 1
            # neutral cards don't affect directional scoring

        total = bull_score + bear_score
        if total > 0:
            conviction = abs(bull_score - bear_score) / total
        else:
            conviction = 0.0

        if bull_score > bear_score:
            direction = "bullish"
        elif bear_score > bull_score:
            direction = "bearish"
        else:
            direction = "neutral"

        return ConfluenceResult(
            direction=direction,
            conviction=conviction,
            bull_score=round(bull_score, 4),
            bear_score=round(bear_score, 4),
            bull_cards=bull_count,
            bear_cards=bear_count,
            total_evidence=len(cards),
            total_rejected=rejected,
            cards=cards,
        )

    def _apply_rules(
        self, confluence: ConfluenceResult, signal_dir: str
    ) -> tuple[str, str]:
        """Apply decision rules based on confluence and signal direction.

        Returns:
            (decision, reasoning) tuple.
        """
        # Map signal direction to evidence direction
        signal_evidence_dir = "bullish" if signal_dir == "LONG" else "bearish"

        # No evidence at all → pass through (don't block on missing data)
        if confluence.total_evidence <= 1:  # Only gate card
            return "TAKE", "No observer evidence available — pass-through"

        # Evidence opposes signal direction
        if confluence.direction != "neutral" and confluence.direction != signal_evidence_dir:
            if confluence.conviction >= self.skip_threshold:
                return (
                    "SKIP",
                    f"Evidence direction ({confluence.direction}) opposes signal ({signal_dir}), "
                    f"conviction={confluence.conviction:.2f}",
                )

        # Very weak conviction → SKIP
        if confluence.conviction < self.skip_threshold:
            return (
                "SKIP",
                f"Conviction too weak ({confluence.conviction:.2f} < {self.skip_threshold})",
            )

        # Moderate conviction → REDUCE_SIZE
        if confluence.conviction < self.take_threshold:
            return (
                "REDUCE_SIZE",
                f"Moderate conviction ({confluence.conviction:.2f} < {self.take_threshold}) "
                f"— reduce position size",
            )

        # Strong conviction aligned → TAKE
        if confluence.direction == signal_evidence_dir:
            return (
                "TAKE",
                f"Evidence aligned ({confluence.direction}), "
                f"conviction={confluence.conviction:.2f}, "
                f"bull={confluence.bull_score:.2f} bear={confluence.bear_score:.2f}",
            )

        # Neutral evidence with decent conviction → TAKE
        if confluence.direction == "neutral" and confluence.conviction >= self.take_threshold:
            return "TAKE", f"Neutral evidence, conviction={confluence.conviction:.2f}"

        return "TAKE", f"Default pass — conviction={confluence.conviction:.2f}"
