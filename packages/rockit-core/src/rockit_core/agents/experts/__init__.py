"""
Domain Expert agents — pluggable, domain-specific evidence producers.

Each expert extends DomainExpert and produces a scorecard of EvidenceCards
for its domain (TPO, VWAP, EMA, ICT, etc.).

ConflictDetector runs after all experts to resolve opposing evidence.
"""

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

__all__ = [
    "ConflictDetector",
    "DivergenceExpert",
    "DomainExpert",
    "EmaExpert",
    "IctExpert",
    "MeanReversionExpert",
    "OrderFlowExpert",
    "ScalperExpert",
    "TpoExpert",
    "VwapExpert",
]
