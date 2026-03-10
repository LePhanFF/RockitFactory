"""
AgentFilter — wraps AgentPipeline as a FilterBase for the backtest engine.

Drops into the existing CompositeFilter chain. No changes to BacktestEngine needed.
"""

from __future__ import annotations

import pandas as pd

from rockit_core.agents.evidence import AgentDecision
from rockit_core.agents.pipeline import AgentPipeline
from rockit_core.filters.base import FilterBase
from rockit_core.strategies.signal import Signal


class AgentFilter(FilterBase):
    """Wraps AgentPipeline as FilterBase — plugs into existing CompositeFilter chain."""

    def __init__(self, pipeline: AgentPipeline | None = None):
        self._pipeline = pipeline or AgentPipeline()
        self._decisions: list[AgentDecision] = []

    @property
    def name(self) -> str:
        return "agent_evaluation"

    @property
    def decisions(self) -> list[AgentDecision]:
        """Access recorded decisions for post-hoc analysis."""
        return self._decisions

    def should_trade(self, signal: Signal, bar: pd.Series, session_context: dict) -> bool:
        """Evaluate signal through agent pipeline. TAKE/REDUCE_SIZE → True, SKIP → False."""
        signal_dict = {
            "direction": signal.direction,
            "strategy_name": signal.strategy_name,
            "setup_type": signal.setup_type,
            "entry_price": signal.entry_price,
            "stop_price": signal.stop_price,
            "target_price": signal.target_price,
            "day_type": signal.day_type,
            "trend_strength": signal.trend_strength,
            "confidence": signal.confidence,
            "timestamp": str(signal.timestamp),
        }

        bar_dict = bar.to_dict() if isinstance(bar, pd.Series) else (bar or {})
        decision = self._pipeline.evaluate_signal(signal_dict, bar_dict, session_context)
        self._decisions.append(decision)

        return decision.decision in ("TAKE", "REDUCE_SIZE")

    def reset(self) -> None:
        """Clear recorded decisions (call between backtest runs)."""
        self._decisions.clear()
