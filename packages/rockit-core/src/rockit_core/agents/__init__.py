"""
Agent framework — deterministic + LLM agents for signal evaluation.

Pipeline: Gate → Observers → [Advocate/Skeptic Debate] → Orchestrator → TAKE/SKIP/REDUCE_SIZE
"""

from rockit_core.agents.agent_filter import AgentFilter
from rockit_core.agents.base import AgentBase
from rockit_core.agents.debate.advocate import AdvocateAgent
from rockit_core.agents.debate.skeptic import SkepticAgent
from rockit_core.agents.evidence import (
    AgentDecision,
    ConfluenceResult,
    DebateResult,
    EvidenceCard,
)
from rockit_core.agents.gate import CRIGateAgent
from rockit_core.agents.llm_client import OllamaClient
from rockit_core.agents.observers.momentum import MomentumObserver
from rockit_core.agents.observers.profile import ProfileObserver
from rockit_core.agents.orchestrator import DeterministicOrchestrator
from rockit_core.agents.pipeline import AgentPipeline

__all__ = [
    "AdvocateAgent",
    "AgentBase",
    "AgentDecision",
    "AgentFilter",
    "AgentPipeline",
    "CRIGateAgent",
    "ConfluenceResult",
    "DebateResult",
    "DeterministicOrchestrator",
    "EvidenceCard",
    "MomentumObserver",
    "OllamaClient",
    "ProfileObserver",
    "SkepticAgent",
]
