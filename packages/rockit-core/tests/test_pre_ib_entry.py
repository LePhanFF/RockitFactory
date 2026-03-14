"""
Tests for on_pre_ib_bar() support — strategies that enter BEFORE IB close.

Covers:
  - StrategyBase.on_pre_ib_bar() default returns None
  - NDOG Gap Fill emits signal on first pre-IB bar with valid gap
  - RTH Gap Fill emits signal on first qualifying pre-IB bar with VWAP confirmation
  - BacktestEngine processes pre-IB signals during IB formation
"""

from datetime import time as _time
from typing import List, Optional

import pandas as pd
import pytest

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.ndog_gap_fill import NDOGGapFill
from rockit_core.strategies.rth_gap_fill import RTHGapFill
from rockit_core.strategies.signal import Signal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ib_bars(open_price, count=60, vwap=None):
    """Create mock IB bars (9:30 - 10:29)."""
    bars = []
    for i in range(count):
        minute = 30 + i
        hour = 9 + minute // 60
        minute = minute % 60
        close = open_price - 5 + (i * 0.1)  # Slight drift
        bar = {
            "timestamp": pd.Timestamp(f"2025-06-10 {hour:02d}:{minute:02d}:00"),
            "open": open_price if i == 0 else close - 1,
            "high": max(open_price, close) + 5,
            "low": min(open_price, close) - 5,
            "close": close,
            "volume": 1000,
        }
        if vwap is not None:
            bar["vwap"] = vwap
        bars.append(bar)
    return pd.DataFrame(bars)


def _make_session_context(prior_close, ib_bars, session_date="2025-06-10"):
    """Build a minimal session_context dict for testing."""
    ib_high = ib_bars["high"].max()
    ib_low = ib_bars["low"].min()
    ib_range = ib_high - ib_low
    return {
        "ib_high": ib_high,
        "ib_low": ib_low,
        "ib_range": ib_range,
        "ib_mid": (ib_high + ib_low) / 2,
        "ib_bars": ib_bars,
        "prior_close": prior_close,
        "session_date": session_date,
        "day_type": "NEUTRAL",
        "trend_strength": "NONE",
        "session_bias": "NEUTRAL",
        "regime_bias": "NEUTRAL",
    }


class ConcreteStrategyStub(StrategyBase):
    """Minimal concrete strategy for testing the base class default."""

    @property
    def name(self) -> str:
        return "Stub"

    @property
    def applicable_day_types(self) -> List[str]:
        return []

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        pass

    def on_bar(self, bar, bar_index, session_context) -> Optional[Signal]:
        return None


# ---------------------------------------------------------------------------
# Tests: StrategyBase default on_pre_ib_bar
# ---------------------------------------------------------------------------

class TestStrategyBasePreIB:

    def test_default_returns_none(self):
        """StrategyBase.on_pre_ib_bar() returns None by default."""
        strategy = ConcreteStrategyStub()
        bar = pd.Series({"open": 100, "high": 101, "low": 99, "close": 100})
        result = strategy.on_pre_ib_bar(bar, 0, {})
        assert result is None

    def test_default_does_not_require_override(self):
        """Strategies that don't override on_pre_ib_bar still work fine."""
        strategy = ConcreteStrategyStub()
        # Call multiple times — always None
        for i in range(5):
            bar = pd.Series({"open": 100 + i, "high": 102 + i, "low": 99 + i, "close": 101 + i})
            assert strategy.on_pre_ib_bar(bar, i, {}) is None


# ---------------------------------------------------------------------------
# Tests: NDOG Gap Fill on_pre_ib_bar
# ---------------------------------------------------------------------------

class TestNDOGPreIB:

    def test_emits_signal_on_first_bar_up_gap(self):
        """NDOG emits SHORT signal on bar_index=0 for UP gap >= 20pts."""
        strategy = NDOGGapFill()
        prior_close = 20000.0
        session_open = 20050.0  # 50pt UP gap
        vwap = 20060.0  # price below VWAP -> bearish confirm for UP gap fill

        ib_bars = _make_ib_bars(session_open, vwap=vwap)
        ctx = _make_session_context(prior_close, ib_bars)

        strategy.on_session_start("2025-06-10", ctx["ib_high"], ctx["ib_low"], ctx["ib_range"], ctx)

        # First IB bar
        bar = ib_bars.iloc[0]
        pre_ctx = dict(ctx)
        pre_ctx["bar_time"] = _time(9, 30)
        pre_ctx["current_price"] = bar["close"]

        signal = strategy.on_pre_ib_bar(bar, 0, pre_ctx)
        assert signal is not None
        assert signal.direction == "SHORT"
        assert signal.strategy_name == "NDOG Gap Fill"
        assert signal.setup_type == "NDOG_GAP_FILL"
        assert signal.metadata["gap_direction"] == "UP"

    def test_emits_signal_on_first_bar_down_gap(self):
        """NDOG emits LONG signal on bar_index=0 for DOWN gap >= 20pts."""
        strategy = NDOGGapFill()
        prior_close = 20050.0
        session_open = 20000.0  # 50pt DOWN gap
        vwap = 19990.0  # price above VWAP -> bullish confirm for DOWN gap fill

        ib_bars = _make_ib_bars(session_open, vwap=vwap)
        ctx = _make_session_context(prior_close, ib_bars)

        strategy.on_session_start("2025-06-10", ctx["ib_high"], ctx["ib_low"], ctx["ib_range"], ctx)

        bar = ib_bars.iloc[0]
        pre_ctx = dict(ctx)
        pre_ctx["bar_time"] = _time(9, 30)
        pre_ctx["current_price"] = bar["close"]

        signal = strategy.on_pre_ib_bar(bar, 0, pre_ctx)
        assert signal is not None
        assert signal.direction == "LONG"
        assert signal.metadata["gap_direction"] == "DOWN"

    def test_no_signal_on_second_bar(self):
        """NDOG only fires on bar_index=0, not later bars."""
        strategy = NDOGGapFill()
        prior_close = 20000.0
        session_open = 20050.0
        vwap = 20060.0

        ib_bars = _make_ib_bars(session_open, vwap=vwap)
        ctx = _make_session_context(prior_close, ib_bars)

        strategy.on_session_start("2025-06-10", ctx["ib_high"], ctx["ib_low"], ctx["ib_range"], ctx)

        # Second bar — should return None
        bar = ib_bars.iloc[1]
        pre_ctx = dict(ctx)
        pre_ctx["bar_time"] = _time(9, 31)
        pre_ctx["current_price"] = bar["close"]

        signal = strategy.on_pre_ib_bar(bar, 1, pre_ctx)
        assert signal is None

    def test_no_signal_when_gap_too_small(self):
        """NDOG requires gap >= 20pts."""
        strategy = NDOGGapFill()
        prior_close = 20000.0
        session_open = 20010.0  # Only 10pt gap

        ib_bars = _make_ib_bars(session_open, vwap=20020.0)
        ctx = _make_session_context(prior_close, ib_bars)

        strategy.on_session_start("2025-06-10", ctx["ib_high"], ctx["ib_low"], ctx["ib_range"], ctx)

        bar = ib_bars.iloc[0]
        pre_ctx = dict(ctx)
        pre_ctx["bar_time"] = _time(9, 30)
        pre_ctx["current_price"] = bar["close"]

        signal = strategy.on_pre_ib_bar(bar, 0, pre_ctx)
        assert signal is None

    def test_no_signal_without_vwap_confirmation(self):
        """NDOG requires VWAP confirmation: UP gap needs price < VWAP."""
        strategy = NDOGGapFill()
        prior_close = 20000.0
        session_open = 20050.0  # 50pt UP gap
        vwap = 20010.0  # price ABOVE vwap -> NO bearish confirm

        ib_bars = _make_ib_bars(session_open, vwap=vwap)
        ctx = _make_session_context(prior_close, ib_bars)

        strategy.on_session_start("2025-06-10", ctx["ib_high"], ctx["ib_low"], ctx["ib_range"], ctx)
        # _active should be False because VWAP didn't confirm
        assert not strategy._active

    def test_on_bar_returns_none(self):
        """After moving to on_pre_ib_bar, on_bar always returns None."""
        strategy = NDOGGapFill()
        prior_close = 20000.0
        session_open = 20050.0
        vwap = 20060.0

        ib_bars = _make_ib_bars(session_open, vwap=vwap)
        ctx = _make_session_context(prior_close, ib_bars)

        strategy.on_session_start("2025-06-10", ctx["ib_high"], ctx["ib_low"], ctx["ib_range"], ctx)

        bar = ib_bars.iloc[0]
        signal = strategy.on_bar(bar, 0, ctx)
        assert signal is None

    def test_no_duplicate_signal(self):
        """NDOG emits only one signal per session."""
        strategy = NDOGGapFill()
        prior_close = 20000.0
        session_open = 20050.0
        vwap = 20060.0

        ib_bars = _make_ib_bars(session_open, vwap=vwap)
        ctx = _make_session_context(prior_close, ib_bars)

        strategy.on_session_start("2025-06-10", ctx["ib_high"], ctx["ib_low"], ctx["ib_range"], ctx)

        bar = ib_bars.iloc[0]
        pre_ctx = dict(ctx)
        pre_ctx["bar_time"] = _time(9, 30)
        pre_ctx["current_price"] = bar["close"]

        signal1 = strategy.on_pre_ib_bar(bar, 0, pre_ctx)
        assert signal1 is not None

        # Second call on same bar — already emitted
        signal2 = strategy.on_pre_ib_bar(bar, 0, pre_ctx)
        assert signal2 is None


# ---------------------------------------------------------------------------
# Tests: RTH Gap Fill on_pre_ib_bar
# ---------------------------------------------------------------------------

class TestRTHGapFillPreIB:

    def test_emits_signal_on_first_qualifying_bar_up_gap(self):
        """RTH Gap Fill emits SHORT on first bar where VWAP confirms (UP gap)."""
        strategy = RTHGapFill(up_only=True)
        prior_close = 20000.0
        session_open = 20080.0  # 80pt UP gap (>= 50)
        vwap = 20090.0  # price below VWAP -> confirms fill direction

        ib_bars = _make_ib_bars(session_open, vwap=vwap)
        ctx = _make_session_context(prior_close, ib_bars)

        strategy.on_session_start("2025-06-10", ctx["ib_high"], ctx["ib_low"], ctx["ib_range"], ctx)

        bar = ib_bars.iloc[0]
        pre_ctx = dict(ctx)
        pre_ctx["bar_time"] = _time(9, 30)
        pre_ctx["current_price"] = bar["close"]

        signal = strategy.on_pre_ib_bar(bar, 0, pre_ctx)
        assert signal is not None
        assert signal.direction == "SHORT"
        assert signal.strategy_name == "RTH Gap Fill"
        assert signal.setup_type == "RTH_GAP_FILL"
        assert signal.metadata["gap_direction"] == "UP"
        assert signal.metadata["target_model"] == "half_fill"

    def test_emits_signal_down_gap_when_not_up_only(self):
        """RTH Gap Fill with up_only=False emits LONG on DOWN gap."""
        strategy = RTHGapFill(up_only=False)
        prior_close = 20080.0
        session_open = 20000.0  # 80pt DOWN gap
        vwap = 19990.0  # price above VWAP -> confirms fill direction

        ib_bars = _make_ib_bars(session_open, vwap=vwap)
        ctx = _make_session_context(prior_close, ib_bars)

        strategy.on_session_start("2025-06-10", ctx["ib_high"], ctx["ib_low"], ctx["ib_range"], ctx)

        bar = ib_bars.iloc[0]
        pre_ctx = dict(ctx)
        pre_ctx["bar_time"] = _time(9, 30)
        pre_ctx["current_price"] = bar["close"]

        signal = strategy.on_pre_ib_bar(bar, 0, pre_ctx)
        assert signal is not None
        assert signal.direction == "LONG"

    def test_no_signal_when_gap_too_small(self):
        """RTH Gap Fill requires gap >= 50pts."""
        strategy = RTHGapFill()
        prior_close = 20000.0
        session_open = 20030.0  # Only 30pt gap

        ib_bars = _make_ib_bars(session_open, vwap=20040.0)
        ctx = _make_session_context(prior_close, ib_bars)

        strategy.on_session_start("2025-06-10", ctx["ib_high"], ctx["ib_low"], ctx["ib_range"], ctx)

        bar = ib_bars.iloc[0]
        pre_ctx = dict(ctx)
        pre_ctx["bar_time"] = _time(9, 30)

        signal = strategy.on_pre_ib_bar(bar, 0, pre_ctx)
        assert signal is None

    def test_no_signal_without_vwap_confirmation(self):
        """RTH Gap Fill skips bar if VWAP doesn't confirm fill direction."""
        strategy = RTHGapFill(up_only=True)
        prior_close = 20000.0
        session_open = 20080.0  # 80pt UP gap
        # For UP gap, price must be BELOW VWAP. Set vwap below price so confirm fails.
        vwap = 20040.0  # price ABOVE vwap -> no confirm

        ib_bars = _make_ib_bars(session_open, vwap=vwap)
        ctx = _make_session_context(prior_close, ib_bars)

        strategy.on_session_start("2025-06-10", ctx["ib_high"], ctx["ib_low"], ctx["ib_range"], ctx)

        bar = ib_bars.iloc[0]
        pre_ctx = dict(ctx)
        pre_ctx["bar_time"] = _time(9, 30)

        signal = strategy.on_pre_ib_bar(bar, 0, pre_ctx)
        assert signal is None

    def test_confirms_on_later_bar_if_first_doesnt_qualify(self):
        """RTH Gap Fill waits for VWAP confirmation — can fire on bar 2+ if bar 0 fails."""
        strategy = RTHGapFill(up_only=True)
        prior_close = 20000.0
        session_open = 20080.0  # 80pt UP gap

        # Build bars: bar 0 has VWAP below price (no confirm), bar 1 has VWAP above price (confirms)
        ib_bars = _make_ib_bars(session_open, count=60, vwap=20090.0)
        # Override bar 0 VWAP to NOT confirm
        ib_bars.loc[0, "vwap"] = 20040.0  # price above VWAP -> fail
        # Bar 1 still has vwap=20090 -> price below VWAP -> confirms

        ctx = _make_session_context(prior_close, ib_bars)
        strategy.on_session_start("2025-06-10", ctx["ib_high"], ctx["ib_low"], ctx["ib_range"], ctx)

        # Bar 0 — no confirm
        bar0 = ib_bars.iloc[0]
        pre_ctx = dict(ctx)
        pre_ctx["bar_time"] = _time(9, 30)
        signal0 = strategy.on_pre_ib_bar(bar0, 0, pre_ctx)
        assert signal0 is None

        # Bar 1 — confirms
        bar1 = ib_bars.iloc[1]
        pre_ctx["bar_time"] = _time(9, 31)
        pre_ctx["current_price"] = bar1["close"]
        signal1 = strategy.on_pre_ib_bar(bar1, 1, pre_ctx)
        assert signal1 is not None
        assert signal1.direction == "SHORT"

    def test_time_stop_blocks_signal(self):
        """RTH Gap Fill blocks signals after 11:00."""
        strategy = RTHGapFill(up_only=True)
        prior_close = 20000.0
        session_open = 20080.0
        vwap = 20090.0

        ib_bars = _make_ib_bars(session_open, vwap=vwap)
        ctx = _make_session_context(prior_close, ib_bars)

        strategy.on_session_start("2025-06-10", ctx["ib_high"], ctx["ib_low"], ctx["ib_range"], ctx)

        bar = ib_bars.iloc[0]
        pre_ctx = dict(ctx)
        pre_ctx["bar_time"] = _time(11, 1)  # After 11:00 time stop

        signal = strategy.on_pre_ib_bar(bar, 0, pre_ctx)
        assert signal is None

    def test_on_bar_returns_none(self):
        """After moving to on_pre_ib_bar, on_bar always returns None."""
        strategy = RTHGapFill()
        prior_close = 20000.0
        session_open = 20080.0
        vwap = 20090.0

        ib_bars = _make_ib_bars(session_open, vwap=vwap)
        ctx = _make_session_context(prior_close, ib_bars)

        strategy.on_session_start("2025-06-10", ctx["ib_high"], ctx["ib_low"], ctx["ib_range"], ctx)

        bar = ib_bars.iloc[0]
        signal = strategy.on_bar(bar, 0, ctx)
        assert signal is None

    def test_half_fill_target(self):
        """RTH Gap Fill target = midpoint(session_open, prior_close)."""
        strategy = RTHGapFill(up_only=True)
        prior_close = 20000.0
        session_open = 20100.0  # 100pt UP gap
        vwap = 20110.0

        ib_bars = _make_ib_bars(session_open, vwap=vwap)
        ctx = _make_session_context(prior_close, ib_bars)

        strategy.on_session_start("2025-06-10", ctx["ib_high"], ctx["ib_low"], ctx["ib_range"], ctx)

        bar = ib_bars.iloc[0]
        pre_ctx = dict(ctx)
        pre_ctx["bar_time"] = _time(9, 30)

        signal = strategy.on_pre_ib_bar(bar, 0, pre_ctx)
        assert signal is not None
        # Half fill = (20100 + 20000) / 2 = 20050
        assert signal.target_price == 20050.0
