"""
Evidence dataclasses for the agent framework.

EvidenceCard  — single observation from an agent
ConfluenceResult — aggregated bull/bear scoring
AgentDecision — final TAKE/SKIP/REDUCE_SIZE decision
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class EvidenceCard:
    """A single observation produced by an agent."""

    card_id: str
    source: str  # "gate_cri", "observer_profile", "observer_momentum"
    layer: str  # "certainty" | "probabilistic" | "instinct"
    observation: str  # Human-readable
    direction: str  # "bullish" | "bearish" | "neutral"
    strength: float  # 0.0-1.0
    data_points: int = 1
    historical_support: str | None = None
    admitted: bool | None = None  # None=pre-debate, True/False=post-debate
    raw_data: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.direction not in ("bullish", "bearish", "neutral"):
            raise ValueError(f"Invalid direction: {self.direction}")
        self.strength = max(0.0, min(1.0, self.strength))


@dataclass
class ConfluenceResult:
    """Aggregated bull/bear evidence scoring."""

    direction: str  # "bullish" | "bearish" | "neutral"
    conviction: float  # 0.0-1.0
    bull_score: float
    bear_score: float
    bull_cards: int
    bear_cards: int
    total_evidence: int
    total_rejected: int
    cards: list[EvidenceCard] = field(default_factory=list)


@dataclass
class AgentDecision:
    """Final decision from the orchestrator."""

    decision: str  # "TAKE" | "SKIP" | "REDUCE_SIZE"
    confidence: float
    direction: str | None
    confluence: ConfluenceResult
    reasoning: str
    gate_passed: bool
    evidence_cards: list[EvidenceCard] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        """Serialize for JSON/DuckDB storage."""
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "direction": self.direction,
            "reasoning": self.reasoning,
            "gate_passed": self.gate_passed,
            "timestamp": self.timestamp,
            "bull_score": self.confluence.bull_score,
            "bear_score": self.confluence.bear_score,
            "conviction": self.confluence.conviction,
            "evidence_direction": self.confluence.direction,
            "total_evidence": self.confluence.total_evidence,
            "bull_cards": self.confluence.bull_cards,
            "bear_cards": self.confluence.bear_cards,
            "evidence_cards": [
                {
                    "card_id": c.card_id,
                    "source": c.source,
                    "layer": c.layer,
                    "observation": c.observation,
                    "direction": c.direction,
                    "strength": c.strength,
                    "data_points": c.data_points,
                }
                for c in self.evidence_cards
            ],
        }
