"""
Agent framework — deterministic agents for signal evaluation.

Pipeline: Gate → Observers → Orchestrator → TAKE/SKIP/REDUCE_SIZE
"""

from rockit_core.agents.agent_filter import AgentFilter
from rockit_core.agents.base import AgentBase
from rockit_core.agents.evidence import AgentDecision, ConfluenceResult, EvidenceCard
from rockit_core.agents.gate import CRIGateAgent
from rockit_core.agents.observers.momentum import MomentumObserver
from rockit_core.agents.observers.profile import ProfileObserver
from rockit_core.agents.orchestrator import DeterministicOrchestrator
from rockit_core.agents.pipeline import AgentPipeline

__all__ = [
    "AgentBase",
    "AgentDecision",
    "AgentFilter",
    "AgentPipeline",
    "CRIGateAgent",
    "ConfluenceResult",
    "DeterministicOrchestrator",
    "EvidenceCard",
    "MomentumObserver",
    "ProfileObserver",
]
