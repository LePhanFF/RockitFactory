"""
Agent Pipeline — chains Gate → Domain Experts → [Debate] → Orchestrator.

Same code runs inline (backtest, fast) and via HTTP (FastAPI wrapper).
Debate layer is OPTIONAL — if disabled or LLM unreachable, falls back to deterministic.

Supports both legacy observers (ProfileObserver, MomentumObserver) and
new DomainExpert plug-ins (TpoExpert, VwapExpert, EmaExpert, etc.).
"""

from __future__ import annotations

import logging

from rockit_core.agents.evidence import AgentDecision, DebateResult
from rockit_core.agents.gate import CRIGateAgent
from rockit_core.agents.llm_client import OllamaClient
from rockit_core.agents.observers.momentum import MomentumObserver
from rockit_core.agents.orchestrator import DeterministicOrchestrator

logger = logging.getLogger(__name__)


class AgentPipeline:
    """Chains gate → observers → conflict detection → [debate] → orchestrator.

    Accepts both legacy observers (AgentBase) and new DomainExpert instances.
    Default: legacy 2-observer pipeline (ProfileObserver + MomentumObserver).
    Use preset="experts" for the full 8 domain experts + ConflictDetector.
    """

    PRESET_LEGACY = "legacy"
    PRESET_EXPERTS = "experts"

    def __init__(
        self,
        gate: CRIGateAgent | None = None,
        observers: list | None = None,
        orchestrator: DeterministicOrchestrator | None = None,
        llm_client: OllamaClient | None = None,
        enable_debate: bool = False,
        conflict_detector=None,
        preset: str | None = None,
    ):
        self.gate = gate or CRIGateAgent()
        if observers is not None:
            self.observers = observers
        elif preset == self.PRESET_EXPERTS:
            self.observers = self._build_expert_observers()
        else:
            # Legacy default — matches original 2-observer pipeline
            from rockit_core.agents.observers.profile import ProfileObserver
            self.observers = [ProfileObserver(), MomentumObserver()]
        # ConflictDetector: only enabled for expert preset (or explicit)
        if conflict_detector is not None:
            self.conflict_detector = conflict_detector
        elif preset == self.PRESET_EXPERTS:
            from rockit_core.agents.experts.conflict import ConflictDetector
            self.conflict_detector = ConflictDetector()
        else:
            self.conflict_detector = None
        self.orchestrator = orchestrator or DeterministicOrchestrator()
        self.llm_client = llm_client
        self.enable_debate = enable_debate and llm_client is not None

        # Lazy-init debate agents only when needed
        self._advocate = None
        self._skeptic = None
        if self.enable_debate:
            self._init_debate_agents()

    def _init_debate_agents(self) -> None:
        """Initialize Advocate and Skeptic agents."""
        from rockit_core.agents.debate.advocate import AdvocateAgent
        from rockit_core.agents.debate.skeptic import SkepticAgent

        self._advocate = AdvocateAgent(self.llm_client)
        self._skeptic = SkepticAgent(self.llm_client)

    @staticmethod
    def _build_expert_observers() -> list:
        """Build the full 8 domain experts + MomentumObserver list."""
        from rockit_core.agents.experts.tpo import TpoExpert
        from rockit_core.agents.experts.vwap import VwapExpert
        from rockit_core.agents.experts.ema import EmaExpert
        from rockit_core.agents.experts.ict import IctExpert
        from rockit_core.agents.experts.scalper import ScalperExpert
        from rockit_core.agents.experts.order_flow import OrderFlowExpert
        from rockit_core.agents.experts.divergence import DivergenceExpert
        from rockit_core.agents.experts.mean_reversion import MeanReversionExpert

        return [
            TpoExpert(),
            MomentumObserver(),
            VwapExpert(),
            EmaExpert(),
            IctExpert(),
            ScalperExpert(),
            OrderFlowExpert(),
            DivergenceExpert(),
            MeanReversionExpert(),
        ]

    def evaluate_signal(
        self,
        signal_dict: dict,
        bar: dict | None = None,
        session_context: dict | None = None,
    ) -> AgentDecision:
        """Evaluate a trading signal through the full agent pipeline.

        Args:
            signal_dict: Dict with at least 'direction', 'strategy_name', 'entry_price'.
            bar: Current bar data (optional, used for price if not in tape).
            session_context: Full session context from backtest engine.

        Returns:
            AgentDecision with TAKE/SKIP/REDUCE_SIZE.
        """
        context = self._build_context(signal_dict, bar, session_context)

        # 1. Gate check (soft — CRI is evidence, not a block)
        gate_passed = self.gate.passes(context)
        all_cards = self.gate.evaluate(context)

        # 2. Domain experts / observers produce evidence cards
        for obs in self.observers:
            all_cards.extend(obs.evaluate(context))

        # 3. ConflictDetector: resolve opposing evidence between domains
        if self.conflict_detector and len(all_cards) > 2:
            try:
                conflict_cards = self.conflict_detector.resolve_conflicts(
                    all_cards, signal_dict=signal_dict
                )
                all_cards.extend(conflict_cards)
            except Exception:  # noqa: BLE001
                logger.debug("ConflictDetector failed, continuing without resolution", exc_info=True)

        # 4. Debate (optional — between experts and orchestrator)
        if self.enable_debate and len(all_cards) > 1:
            try:
                advocate_result, skeptic_result = self._run_debate(
                    all_cards, signal_dict, session_context or {}
                )
                # Add instinct cards from debate to the card pool
                all_cards.extend(advocate_result.instinct_cards)
                all_cards.extend(skeptic_result.instinct_cards)

                return self.orchestrator.decide_with_debate(
                    signal_dict, all_cards, gate_passed,
                    advocate_result, skeptic_result,
                )
            except Exception:  # noqa: BLE001
                logger.warning("Debate failed, falling back to deterministic", exc_info=True)

        # 5. Orchestrator decision (deterministic fallback)
        return self.orchestrator.decide(signal_dict, all_cards, gate_passed)

    def _run_debate(
        self,
        evidence_cards: list,
        signal_dict: dict,
        session_context: dict,
    ) -> tuple[DebateResult, DebateResult]:
        """Run Advocate then Skeptic debate (sequential — Skeptic needs Advocate's thesis)."""
        # Enrich context with DuckDB historical stats if available
        historical = self._query_historical(signal_dict, session_context)
        strategy = signal_dict.get("strategy_name", "?")
        direction = signal_dict.get("direction", "?")
        session = session_context.get("session_date", "?") if session_context else "?"
        logger.info("DEBATE [%s] %s %s — calling Advocate...", session, strategy, direction)

        debate_context = {
            "evidence_cards": evidence_cards,
            "signal": signal_dict,
            "session_context": session_context,
            "historical": historical,
        }

        # Advocate builds the case
        advocate_result = self._advocate.debate(debate_context)
        logger.info(
            "DEBATE [%s] Advocate done: direction=%s confidence=%.2f — calling Skeptic...",
            session, advocate_result.direction, advocate_result.confidence,
        )

        # Skeptic challenges (sees Advocate's argument)
        debate_context["advocate_result"] = advocate_result
        skeptic_result = self._skeptic.debate(debate_context)
        logger.info(
            "DEBATE [%s] Skeptic done: direction=%s confidence=%.2f warnings=%d",
            session, skeptic_result.direction, skeptic_result.confidence,
            len(skeptic_result.warnings),
        )

        return advocate_result, skeptic_result

    @staticmethod
    def _query_historical(signal_dict: dict, session_context: dict) -> dict:
        """Query DuckDB for historical strategy stats under similar conditions.

        Returns dict with strategy-level and condition-level stats, or empty dict on failure.
        """
        try:
            from rockit_core.research.db import connect as db_connect, query as db_query
        except ImportError:
            return {}

        strategy = signal_dict.get("strategy_name", "")
        direction = signal_dict.get("direction", "")
        day_type = session_context.get("day_type", "")

        if not strategy:
            return {}

        try:
            conn = db_connect()
            result: dict = {}

            # 1. Overall strategy stats
            rows = db_query(
                conn,
                """
                SELECT COUNT(*) AS n,
                       ROUND(100.0 * SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) / COUNT(*), 1) AS wr,
                       ROUND(SUM(CASE WHEN net_pnl > 0 THEN net_pnl ELSE 0 END) /
                             NULLIF(ABS(SUM(CASE WHEN net_pnl <= 0 THEN net_pnl ELSE 0 END)), 0), 2) AS pf,
                       ROUND(AVG(net_pnl), 2) AS avg_pnl
                FROM trades WHERE strategy_name = ?
                """,
                [strategy],
            )
            if rows and rows[0][0]:
                result["strategy_overall"] = {
                    "trades": rows[0][0], "win_rate": rows[0][1],
                    "profit_factor": rows[0][2], "avg_pnl": rows[0][3],
                }

            # 2. Strategy + direction combo
            if direction:
                rows = db_query(
                    conn,
                    """
                    SELECT COUNT(*) AS n,
                           ROUND(100.0 * SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) / COUNT(*), 1) AS wr,
                           ROUND(AVG(net_pnl), 2) AS avg_pnl
                    FROM trades WHERE strategy_name = ? AND direction = ?
                    """,
                    [strategy, direction],
                )
                if rows and rows[0][0]:
                    result["strategy_direction"] = {
                        "trades": rows[0][0], "win_rate": rows[0][1],
                        "avg_pnl": rows[0][2], "direction": direction,
                    }

            # 3. Strategy + day_type combo
            if day_type:
                rows = db_query(
                    conn,
                    """
                    SELECT COUNT(*) AS n,
                           ROUND(100.0 * SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) / COUNT(*), 1) AS wr,
                           ROUND(AVG(net_pnl), 2) AS avg_pnl
                    FROM trades WHERE strategy_name = ? AND day_type = ?
                    """,
                    [strategy, day_type],
                )
                if rows and rows[0][0]:
                    result["strategy_day_type"] = {
                        "trades": rows[0][0], "win_rate": rows[0][1],
                        "avg_pnl": rows[0][2], "day_type": day_type,
                    }

            # 4. Recent observations for this strategy (last 5)
            rows = db_query(
                conn,
                """
                SELECT observation, evidence, confidence
                FROM observations
                WHERE strategy = ? OR scope = 'portfolio'
                ORDER BY created_at DESC LIMIT 5
                """,
                [strategy],
            )
            if rows:
                result["observations"] = [
                    {"observation": r[0], "evidence": r[1], "confidence": r[2]}
                    for r in rows
                ]

            conn.close()
            return result

        except Exception as exc:  # noqa: BLE001
            logger.debug("DuckDB historical query failed: %s", exc)
            return {}

    def _build_context(
        self,
        signal_dict: dict,
        bar: dict | None,
        session_context: dict | None,
    ) -> dict:
        """Build unified context dict from signal, bar, and session_context.

        The tape_row is derived from session_context — it contains the same
        deterministic data that was injected during bias computation.
        """
        session_context = session_context or {}
        bar = bar or {}

        # Build tape_row from session_context fields that match deterministic tape
        tape_row = {
            "cri_status": session_context.get("cri_status"),
            "tpo_shape": session_context.get("tpo_shape"),
            "current_poc": session_context.get("current_poc")
            or session_context.get("prior_va_poc"),
            "current_vah": session_context.get("current_vah")
            or session_context.get("prior_va_vah"),
            "current_val": session_context.get("current_val")
            or session_context.get("prior_va_val"),
            "dpoc_migration": session_context.get("dpoc_migration"),
            "trend_strength": session_context.get("trend_strength"),
            "bias": session_context.get("session_bias")
            or session_context.get("regime_bias"),
            "extension_multiple": session_context.get("extension_multiple"),
            "close": session_context.get("current_price")
            or (bar.get("Close") if bar else None),
            "snapshot_json": session_context.get("snapshot_json"),
        }

        return {
            "signal": signal_dict,
            "bar": bar,
            "session_context": session_context,
            "tape_row": tape_row,
        }
