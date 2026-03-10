"""
Deterministic Orchestrator — scores evidence cards and makes TAKE/SKIP/REDUCE_SIZE decisions.

MVP: Rule-based scoring with layer weights. No LLM debate.
All certainty-layer cards admitted by default.
"""

from __future__ import annotations

from rockit_core.agents.evidence import AgentDecision, ConfluenceResult, EvidenceCard

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

        # 1. Gate blocked → SKIP immediately
        if not gate_passed:
            confluence = self._build_confluence(evidence_cards, signal_dir)
            return AgentDecision(
                decision="SKIP",
                confidence=1.0,
                direction=None,
                confluence=confluence,
                reasoning="CRI gate: STAND_DOWN — signal blocked",
                gate_passed=False,
                evidence_cards=evidence_cards,
            )

        # 2. Admit all cards (MVP: no debate filtering)
        for card in evidence_cards:
            card.admitted = True

        # 3. Score confluence
        confluence = self._build_confluence(evidence_cards, signal_dir)

        # 4. Make decision
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
            if card.source == "gate_cri":
                continue  # Gate cards don't contribute to directional scoring

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
