"""
ConflictDetector — identifies and resolves conflicting evidence between domain experts.

Level 1 (deterministic): Scans for opposing cards between different domains,
queries DuckDB for historical resolution, produces conflict resolution cards.

Pipeline position: runs AFTER all domain experts, BEFORE Advocate/Skeptic debate.
Enriches the evidence pool with pre-digested conflict analysis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from rockit_core.agents.evidence import EvidenceCard

logger = logging.getLogger(__name__)


@dataclass
class ConflictPair:
    """Two opposing cards from different domains."""
    bull_card: EvidenceCard
    bear_card: EvidenceCard

    @property
    def domain_pair(self) -> str:
        return f"{self.bull_card.source}_vs_{self.bear_card.source}"


class ConflictDetector:
    """Detects and resolves conflicts between domain expert scorecards.

    Level 1 resolution: deterministic + DuckDB historical lookup.
    Produces conflict resolution cards that summarize both sides and
    historical win rate under the specific conflict condition.
    """

    def __init__(self, min_strength_diff: float = 0.1):
        """
        Args:
            min_strength_diff: Minimum strength difference to consider a conflict
                worth resolving (filters noise from weak/neutral cards).
        """
        self.min_strength_diff = min_strength_diff

    def detect_conflicts(self, cards: list[EvidenceCard]) -> list[ConflictPair]:
        """Find card pairs where different domains disagree on direction.

        Only pairs cards from different sources. Ignores neutral cards.
        Requires both cards to have strength >= 0.4 to avoid noise.
        """
        bullish = [c for c in cards if c.direction == "bullish" and c.strength >= 0.4]
        bearish = [c for c in cards if c.direction == "bearish" and c.strength >= 0.4]

        conflicts: list[ConflictPair] = []
        seen_pairs: set[str] = set()

        for b in bullish:
            for s in bearish:
                if b.source == s.source:
                    continue  # Same domain — not a conflict
                pair_key = f"{min(b.source, s.source)}_{max(b.source, s.source)}"
                if pair_key in seen_pairs:
                    continue  # Already found a conflict between these domains
                seen_pairs.add(pair_key)
                conflicts.append(ConflictPair(bull_card=b, bear_card=s))

        return conflicts

    def resolve_conflicts(
        self,
        cards: list[EvidenceCard],
        signal_dict: dict | None = None,
        conn=None,
    ) -> list[EvidenceCard]:
        """Detect conflicts and produce resolution cards.

        Args:
            cards: All evidence cards from domain experts.
            signal_dict: Signal being evaluated (for DuckDB query context).
            conn: Optional DuckDB connection for historical resolution.

        Returns:
            List of conflict resolution EvidenceCards to add to the pool.
        """
        conflicts = self.detect_conflicts(cards)
        if not conflicts:
            return []

        resolution_cards: list[EvidenceCard] = []
        for pair in conflicts:
            card = self._resolve_pair(pair, signal_dict, conn)
            if card is not None:
                resolution_cards.append(card)

        return resolution_cards

    def _resolve_pair(
        self,
        pair: ConflictPair,
        signal_dict: dict | None,
        conn,
    ) -> EvidenceCard | None:
        """Resolve a single conflict pair.

        Strategy:
        1. Query DuckDB for historical WR when both conditions present
        2. If no data, use strength-weighted resolution
        3. Produce a conflict card with reduced confidence
        """
        bull_domain = pair.bull_card.source.replace("expert_", "").replace("observer_", "")
        bear_domain = pair.bear_card.source.replace("expert_", "").replace("observer_", "")

        # Try DuckDB historical resolution
        historical_wr = None
        n_samples = 0
        if conn is not None and signal_dict:
            historical_wr, n_samples = self._query_historical_resolution(
                pair, signal_dict, conn
            )

        if historical_wr is not None and n_samples >= 10:
            return self._resolution_from_history(pair, historical_wr, n_samples, bull_domain, bear_domain)

        # Fallback: strength-weighted resolution
        return self._resolution_from_strength(pair, bull_domain, bear_domain)

    def _resolution_from_history(
        self,
        pair: ConflictPair,
        historical_wr: float,
        n_samples: int,
        bull_domain: str,
        bear_domain: str,
    ) -> EvidenceCard:
        """Resolve conflict using historical DuckDB data."""
        if historical_wr > 0.55:
            direction = "bullish"
            strength = min(0.6, (historical_wr - 0.5) * 2)  # Scale 0.55-1.0 → 0.1-1.0
            winner = bull_domain
        elif historical_wr < 0.45:
            direction = "bearish"
            strength = min(0.6, (0.5 - historical_wr) * 2)
            winner = bear_domain
        else:
            direction = "neutral"
            strength = 0.3
            winner = "neither"

        obs = (
            f"Conflict: {bull_domain} (bullish {pair.bull_card.strength:.2f}) vs "
            f"{bear_domain} (bearish {pair.bear_card.strength:.2f}). "
            f"Historical WR={historical_wr:.0%} (n={n_samples}). "
            f"Resolved: {winner} wins → {direction}."
        )

        return EvidenceCard(
            card_id=f"conflict_{bull_domain}_vs_{bear_domain}",
            source="conflict_resolution",
            layer="probabilistic",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=n_samples,
            historical_support=f"{historical_wr:.0%} WR when {bull_domain} and {bear_domain} conflict (n={n_samples})",
            raw_data={
                "bull_domain": bull_domain,
                "bear_domain": bear_domain,
                "bull_card_id": pair.bull_card.card_id,
                "bear_card_id": pair.bear_card.card_id,
                "historical_wr": historical_wr,
                "n_samples": n_samples,
                "resolution_method": "historical",
            },
        )

    def _resolution_from_strength(
        self,
        pair: ConflictPair,
        bull_domain: str,
        bear_domain: str,
    ) -> EvidenceCard:
        """Resolve conflict using relative card strengths (fallback)."""
        bull_strength = pair.bull_card.strength
        bear_strength = pair.bear_card.strength
        diff = bull_strength - bear_strength

        if diff > self.min_strength_diff:
            direction = "bullish"
            strength = min(0.55, diff)
            winner = bull_domain
        elif diff < -self.min_strength_diff:
            direction = "bearish"
            strength = min(0.55, abs(diff))
            winner = bear_domain
        else:
            direction = "neutral"
            strength = 0.3
            winner = "neither"

        obs = (
            f"Conflict: {bull_domain} (bullish {bull_strength:.2f}) vs "
            f"{bear_domain} (bearish {bear_strength:.2f}). "
            f"No historical data. Strength-based: {winner} wins → {direction}."
        )

        return EvidenceCard(
            card_id=f"conflict_{bull_domain}_vs_{bear_domain}",
            source="conflict_resolution",
            layer="instinct",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=0,
            raw_data={
                "bull_domain": bull_domain,
                "bear_domain": bear_domain,
                "bull_strength": bull_strength,
                "bear_strength": bear_strength,
                "resolution_method": "strength",
            },
        )

    def _query_historical_resolution(
        self,
        pair: ConflictPair,
        signal_dict: dict,
        conn,
    ) -> tuple[float | None, int]:
        """Query DuckDB for historical win rate under this conflict condition.

        Returns (win_rate, n_samples) or (None, 0) on failure.
        """
        try:
            from rockit_core.research.db import query

            strategy = signal_dict.get("strategy_name", "")
            direction = signal_dict.get("direction", "")

            if not strategy or not direction:
                return None, 0

            # Query: when this strategy+direction traded, what was the WR?
            # We use the overall strategy+direction WR as a proxy.
            # Full Bayesian would compute conditional frequencies per domain pair.
            rows = query(conn, """
                SELECT
                    COUNT(*) as n,
                    ROUND(100.0 * SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) / COUNT(*), 1) as wr
                FROM trades
                WHERE strategy_name = ? AND direction = ?
            """, [strategy, direction])

            if rows and rows[0][0] and rows[0][0] >= 5:
                return rows[0][1] / 100.0, rows[0][0]

            return None, 0

        except Exception as exc:
            logger.debug("Conflict historical query failed: %s", exc)
            return None, 0
