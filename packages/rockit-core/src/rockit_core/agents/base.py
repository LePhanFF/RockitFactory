"""
Abstract base class for all agents.

Every agent implements evaluate(context) -> list[EvidenceCard].
Same code runs inline (backtest) or via HTTP (FastAPI wrapper).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from rockit_core.agents.evidence import EvidenceCard


class AgentBase(ABC):
    """Base class for all agents in the pipeline."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent identifier for logging and tracing."""

    @abstractmethod
    def evaluate(self, context: dict) -> list[EvidenceCard]:
        """Evaluate market context and return evidence cards.

        Args:
            context: Dict with keys like 'signal', 'bar', 'session_context',
                     'tape_row' (nearest deterministic snapshot).

        Returns:
            List of EvidenceCard observations.
        """
