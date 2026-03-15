"""
Agent evaluation endpoint — POST /agents/evaluate.

Same AgentPipeline that runs inline during backtest, now exposed via HTTP.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from rockit_core.agents.pipeline import AgentPipeline

router = APIRouter(prefix="/agents", tags=["agents"])

# Singleton pipeline (stateless, safe to reuse)
_pipeline = AgentPipeline()


class SignalEvaluationRequest(BaseModel):
    """Request body for signal evaluation."""

    direction: str  # "LONG" or "SHORT"
    strategy_name: str
    setup_type: str = ""
    entry_price: float = 0.0
    stop_price: float = 0.0
    target_price: float = 0.0
    day_type: str = ""
    trend_strength: str = ""
    confidence: str = "medium"
    session_context: dict[str, Any] = {}


class EvidenceCardResponse(BaseModel):
    card_id: str
    source: str
    layer: str
    observation: str
    direction: str
    strength: float
    data_points: int


class AgentDecisionResponse(BaseModel):
    decision: str  # "TAKE" | "SKIP" | "REDUCE_SIZE"
    confidence: float
    direction: str | None
    reasoning: str
    gate_passed: bool
    bull_score: float
    bear_score: float
    conviction: float
    total_evidence: int
    evidence_cards: list[EvidenceCardResponse]


@router.post("/evaluate", response_model=AgentDecisionResponse)
async def evaluate_signal(request: SignalEvaluationRequest) -> AgentDecisionResponse:
    """Evaluate a trading signal through the agent pipeline."""
    signal_dict = {
        "direction": request.direction,
        "strategy_name": request.strategy_name,
        "setup_type": request.setup_type,
        "entry_price": request.entry_price,
        "stop_price": request.stop_price,
        "target_price": request.target_price,
        "day_type": request.day_type,
        "trend_strength": request.trend_strength,
        "confidence": request.confidence,
    }

    decision = _pipeline.evaluate_signal(
        signal_dict=signal_dict,
        bar=None,
        session_context=request.session_context,
    )

    return AgentDecisionResponse(
        decision=decision.decision,
        confidence=decision.confidence,
        direction=decision.direction,
        reasoning=decision.reasoning,
        gate_passed=decision.gate_passed,
        bull_score=decision.confluence.bull_score,
        bear_score=decision.confluence.bear_score,
        conviction=decision.confluence.conviction,
        total_evidence=decision.confluence.total_evidence,
        evidence_cards=[
            EvidenceCardResponse(
                card_id=c.card_id,
                source=c.source,
                layer=c.layer,
                observation=c.observation,
                direction=c.direction,
                strength=c.strength,
                data_points=c.data_points,
            )
            for c in decision.evidence_cards
        ],
    )


@router.get("/status")
async def agent_status():
    """Return agent pipeline status."""
    return {
        "agents": ["cri_gate", "profile_observer", "momentum_observer", "orchestrator"],
        "status": "ready",
    }
