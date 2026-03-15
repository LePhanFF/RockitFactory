"""
DomainExpert — base class for all domain expert agents.

Domain experts are deterministic, fast (<50ms), and produce evidence cards
for a specific analytical domain. They extend AgentBase with:
  - domain: str identifier (e.g., "tpo", "vwap", "ema")
  - scorecard(): domain-specific card production
  - historical_query(): optional DuckDB enrichment
"""

from __future__ import annotations

from abc import abstractmethod

from rockit_core.agents.base import AgentBase
from rockit_core.agents.evidence import EvidenceCard


class DomainExpert(AgentBase):
    """Base class for domain-specific expert observers.

    Subclasses must define:
      - domain: str property (e.g., "tpo", "vwap", "ema")
      - scorecard(context) -> list[EvidenceCard]

    The evaluate() method delegates to scorecard(), maintaining
    compatibility with the existing AgentBase interface.
    """

    @property
    @abstractmethod
    def domain(self) -> str:
        """Domain identifier (e.g., 'tpo', 'vwap', 'ema', 'ict')."""

    @property
    def name(self) -> str:
        """Agent name defaults to 'expert_{domain}'."""
        return f"expert_{self.domain}"

    def evaluate(self, context: dict) -> list[EvidenceCard]:
        """AgentBase interface — delegates to scorecard()."""
        return self.scorecard(context)

    @abstractmethod
    def scorecard(self, context: dict) -> list[EvidenceCard]:
        """Produce domain-specific evidence cards.

        Args:
            context: Dict with keys: signal, bar, session_context, tape_row.

        Returns:
            List of EvidenceCard observations for this domain.
        """

    def historical_query(self, conn, signal: dict) -> dict:
        """Optional: query DuckDB for domain-specific historical context.

        Override in subclasses to provide domain-specific enrichment
        that feeds into Advocate/Skeptic debate prompts.

        Args:
            conn: DuckDB connection.
            signal: Signal dict with strategy_name, direction, etc.

        Returns:
            Dict of historical context (e.g., conditional WR, patterns).
        """
        return {}
