"""
Agent framework — deterministic + LLM agents for signal evaluation.

Pipeline: Gate → 8 Domain Experts → ConflictDetector → [Advocate/Skeptic Debate] → Orchestrator

Domain experts (plug-in architecture, all deterministic <50ms):
  - TpoExpert: TPO shape, VA, POC, poor extremes (4 cards)
  - VwapExpert: VWAP trend, mean reversion, reclaim (3 cards)
  - EmaExpert: EMA alignment, dynamic S/R, compression (3 cards)
  - IctExpert: FVG support/resistance, BPR, NDOG/NWOG gaps, HTF FVG (4 cards)
  - ScalperExpert: RSI momentum, exhaustion, volume spikes (3 cards)
  - OrderFlowExpert: CVD trend, CVD divergence, delta imbalance (3 cards)
  - DivergenceExpert: SMT divergence, overnight compression (2 cards)
  - MeanReversionExpert: BB position, ADX regime, VWAP stretch (3 cards)
  - MomentumObserver (legacy): DPOC, trend, wicks, extension, bias (5 cards)

ConflictDetector: Level 1 deterministic conflict resolution between domains.

Legacy observers (backward compatible):
  - ProfileObserver → replaced by TpoExpert
  - MomentumObserver → kept for bias/trend/DPOC
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
from rockit_core.agents.experts.base import DomainExpert
from rockit_core.agents.experts.conflict import ConflictDetector
from rockit_core.agents.experts.divergence import DivergenceExpert
from rockit_core.agents.experts.ema import EmaExpert
from rockit_core.agents.experts.ict import IctExpert
from rockit_core.agents.experts.mean_reversion import MeanReversionExpert
from rockit_core.agents.experts.order_flow import OrderFlowExpert
from rockit_core.agents.experts.scalper import ScalperExpert
from rockit_core.agents.experts.tpo import TpoExpert
from rockit_core.agents.experts.vwap import VwapExpert
from rockit_core.agents.gate import CRIGateAgent
from rockit_core.agents.llm_client import OllamaClient
from rockit_core.agents.llm_provider import LLMProvider, OllamaProvider
from rockit_core.agents.observers.momentum import MomentumObserver
from rockit_core.agents.observers.profile import ProfileObserver
from rockit_core.agents.orchestrator import DeterministicOrchestrator
from rockit_core.agents.pipeline import AgentPipeline
from rockit_core.agents.trade_reviewer import TradeReviewer

__all__ = [
    "AdvocateAgent",
    "AgentBase",
    "AgentDecision",
    "AgentFilter",
    "AgentPipeline",
    "CRIGateAgent",
    "ConflictDetector",
    "ConfluenceResult",
    "DebateResult",
    "DeterministicOrchestrator",
    "DivergenceExpert",
    "DomainExpert",
    "EmaExpert",
    "EvidenceCard",
    "IctExpert",
    "LLMProvider",
    "MeanReversionExpert",
    "MomentumObserver",
    "OllamaClient",
    "OllamaProvider",
    "OrderFlowExpert",
    "ProfileObserver",
    "ScalperExpert",
    "SkepticAgent",
    "TpoExpert",
    "TradeReviewer",
    "VwapExpert",
]
