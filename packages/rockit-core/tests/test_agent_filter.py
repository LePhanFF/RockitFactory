"""
Integration tests for AgentFilter in the backtest pipeline.

Tests: FilterBase compliance, CompositeFilter chain, decision recording.
"""

from datetime import datetime

import pandas as pd
import pytest

from rockit_core.agents.agent_filter import AgentFilter
from rockit_core.agents.pipeline import AgentPipeline
from rockit_core.filters.base import FilterBase
from rockit_core.filters.composite import CompositeFilter
from rockit_core.strategies.signal import Signal


def _make_signal(direction="LONG", strategy="OR Rev", setup="IBH_RETEST"):
    return Signal(
        timestamp=datetime(2025, 6, 5, 10, 30),
        direction=direction,
        entry_price=20000.0,
        stop_price=19950.0,
        target_price=20100.0,
        strategy_name=strategy,
        setup_type=setup,
        day_type="Trend",
    )


def _make_bar(price=20000.0):
    return pd.Series({"Close": price, "High": price + 5, "Low": price - 5, "Volume": 1000})


def _make_session_context(**kwargs):
    base = {
        "cri_status": "READY",
        "tpo_shape": "b_shape",
        "current_poc": 20000,
        "current_vah": 20050,
        "current_val": 19950,
        "current_price": 20000,
        "session_bias": "Bullish",
        "trend_strength": "strong_bull",
        "dpoc_migration": "trending_on_the_move",
        "day_type": "Trend",
    }
    base.update(kwargs)
    return base


class TestAgentFilterBase:
    def test_is_filter_base(self):
        af = AgentFilter()
        assert isinstance(af, FilterBase)

    def test_name(self):
        af = AgentFilter()
        assert af.name == "agent_evaluation"


class TestAgentFilterDecisions:
    def test_take_returns_true(self):
        """Aligned evidence → TAKE → should_trade returns True."""
        af = AgentFilter()
        ctx = _make_session_context()
        result = af.should_trade(_make_signal("LONG"), _make_bar(), ctx)
        assert result is True

    def test_standdown_soft_evidence(self):
        """STAND_DOWN CRI is soft evidence — signal still evaluated by full pipeline."""
        af = AgentFilter()
        ctx = _make_session_context(cri_status="STAND_DOWN")
        result = af.should_trade(_make_signal("LONG"), _make_bar(), ctx)
        # CRI STAND_DOWN adds bearish weight but doesn't auto-block
        assert len(af.decisions) == 1
        assert af.decisions[0].gate_passed is True

    def test_records_decisions(self):
        """AgentFilter records all decisions for post-hoc analysis."""
        af = AgentFilter()
        ctx = _make_session_context()
        af.should_trade(_make_signal("LONG"), _make_bar(), ctx)
        af.should_trade(_make_signal("SHORT"), _make_bar(), ctx)
        assert len(af.decisions) == 2

    def test_reset_clears_decisions(self):
        af = AgentFilter()
        af.should_trade(_make_signal("LONG"), _make_bar(), _make_session_context())
        assert len(af.decisions) == 1
        af.reset()
        assert len(af.decisions) == 0


class TestAgentFilterInChain:
    def test_works_in_composite_filter(self):
        """AgentFilter works inside CompositeFilter chain."""
        af = AgentFilter()
        composite = CompositeFilter([af])
        ctx = _make_session_context()
        result = composite.should_trade(_make_signal("LONG"), _make_bar(), ctx)
        assert isinstance(result, bool)

    def test_agent_after_mechanical_filter(self):
        """AgentFilter works after mechanical filters in chain."""
        from rockit_core.filters.bias_filter import BiasAlignmentFilter

        af = AgentFilter()
        composite = CompositeFilter([
            BiasAlignmentFilter(neutral_passes=True),
            af,
        ])
        ctx = _make_session_context()
        result = composite.should_trade(_make_signal("LONG"), _make_bar(), ctx)
        assert isinstance(result, bool)

    def test_empty_context_does_not_crash(self):
        """AgentFilter handles empty session_context gracefully."""
        af = AgentFilter()
        result = af.should_trade(_make_signal("LONG"), _make_bar(), {})
        # Empty context → pass-through → TAKE → True
        assert result is True

    def test_opposed_evidence_filters(self):
        """Strong bearish context + LONG signal → filtered out."""
        af = AgentFilter()
        ctx = _make_session_context(
            session_bias="Bearish",
            trend_strength="strong_bear",
            tpo_shape="p_shape",
            dpoc_migration="migrating_down",
        )
        result = af.should_trade(_make_signal("LONG"), _make_bar(), ctx)
        assert result is False
