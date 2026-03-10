"""
Agent Pipeline — chains Gate → Observers → Orchestrator.

Same code runs inline (backtest, fast) and via HTTP (FastAPI wrapper).
"""

from __future__ import annotations

from rockit_core.agents.evidence import AgentDecision
from rockit_core.agents.gate import CRIGateAgent
from rockit_core.agents.observers.momentum import MomentumObserver
from rockit_core.agents.observers.profile import ProfileObserver
from rockit_core.agents.orchestrator import DeterministicOrchestrator


class AgentPipeline:
    """Chains gate → observers → orchestrator into a single evaluate_signal() call."""

    def __init__(
        self,
        gate: CRIGateAgent | None = None,
        observers: list | None = None,
        orchestrator: DeterministicOrchestrator | None = None,
    ):
        self.gate = gate or CRIGateAgent()
        self.observers = observers or [ProfileObserver(), MomentumObserver()]
        self.orchestrator = orchestrator or DeterministicOrchestrator()

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

        # 1. Gate check
        gate_passed = self.gate.passes(context)
        all_cards = self.gate.evaluate(context)

        # 2. Observers (only if gate passes)
        if gate_passed:
            for obs in self.observers:
                all_cards.extend(obs.evaluate(context))

        # 3. Orchestrator decision
        return self.orchestrator.decide(signal_dict, all_cards, gate_passed)

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
