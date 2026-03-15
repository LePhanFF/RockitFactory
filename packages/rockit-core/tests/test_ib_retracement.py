"""Tests for IB Retracement strategy."""

import pytest
import pandas as pd
from datetime import time as _time, datetime

from rockit_core.strategies.ib_retracement import (
    IBRetracement,
    ENTRY_START,
    ENTRY_CUTOFF,
    MIN_IB_RANGE,
    FIB_ZONE_LOW,
    FIB_ZONE_HIGH,
    IB_CLOSE_THRESHOLD,
    STOP_BUFFER_PTS,
)


def _make_bar(open_=20100, high=20110, low=20090, close=20100, timestamp=None):
    """Create a simple bar Series."""
    ts = timestamp or datetime(2026, 3, 10, 11, 0)
    return pd.Series({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': 1000,
        'timestamp': ts,
    })


def _session_context(
    bar_time=_time(11, 0), day_type='b_day', session_bias='NEUTRAL',
    ib_close=None,
):
    """Create a minimal session context dict."""
    ctx = {
        'bar_time': bar_time,
        'day_type': day_type,
        'session_bias': session_bias,
        'trend_strength': 'moderate',
    }
    if ib_close is not None:
        ctx['ib_close'] = ib_close
    return ctx


class TestInstantiation:
    """Strategy instantiation and properties."""

    def test_default_config(self):
        s = IBRetracement()
        assert s.name == "IB Retracement"
        assert s.applicable_day_types == []
        assert s._min_ib_range == MIN_IB_RANGE
        assert s._fib_low == FIB_ZONE_LOW
        assert s._fib_high == FIB_ZONE_HIGH
        assert s._ib_close_threshold == IB_CLOSE_THRESHOLD
        assert s._target_mode == 'opp_ib'
        assert s._stop_buffer == STOP_BUFFER_PTS

    def test_custom_config(self):
        s = IBRetracement(min_ib_range=120, fib_low=0.382, fib_high=0.618,
                          target_mode='2r', stop_buffer=15)
        assert s._min_ib_range == 120
        assert s._fib_low == 0.382
        assert s._fib_high == 0.618
        assert s._target_mode == '2r'
        assert s._stop_buffer == 15

    def test_repr(self):
        s = IBRetracement()
        assert "IBRetracement" in repr(s)


class TestImpulseDetection:
    """Impulse direction detection from IB close position."""

    def test_bullish_impulse_close_top_30pct(self):
        """IB close in top 30% -> UP impulse."""
        s = IBRetracement()
        # IB: 20000-20200 (range 200), close at 20170 (85% position -> top 30%)
        ctx = _session_context(ib_close=20170)
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)
        assert s._impulse_direction == 'UP'

    def test_bearish_impulse_close_bottom_30pct(self):
        """IB close in bottom 30% -> DOWN impulse."""
        s = IBRetracement()
        ctx = _session_context(ib_close=20040)  # 20% position -> bottom 30%
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)
        assert s._impulse_direction == 'DOWN'

    def test_no_impulse_close_middle(self):
        """IB close in middle 40% -> no impulse."""
        s = IBRetracement()
        ctx = _session_context(ib_close=20100)  # 50% position
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)
        assert s._impulse_direction is None

    def test_no_signal_without_impulse(self):
        """No impulse direction -> no signal ever."""
        s = IBRetracement()
        ctx = _session_context(ib_close=20100)
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        sig = s.on_bar(_make_bar(close=20090), 0, ctx)
        assert sig is None


class TestLongRetracementSignal:
    """LONG signals on bullish impulse retracement."""

    def test_long_retrace_signal(self):
        """Bullish impulse, price retraces into fib zone, bounces out -> LONG."""
        s = IBRetracement()
        # IB: 20000-20200 (range 200), close at 20180 (top 10%)
        ctx = _session_context(ib_close=20180)
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        assert s._impulse_direction == 'UP'
        # Fib zone for UP: upper = 20200 - 0.50*200 = 20100
        #                  lower = 20200 - 0.618*200 = 20076.4
        assert abs(s._fib_zone_upper - 20100.0) < 0.1
        assert abs(s._fib_zone_lower - 20076.4) < 0.1

        # Bar 0: low dips into fib zone (20090, within 20076-20100)
        bar0 = _make_bar(open_=20110, high=20115, low=20090, close=20095)
        sig = s.on_bar(bar0, 0, ctx)
        assert sig is None  # In fib zone but close still in zone

        # Bar 1: price bounces out above fib zone upper
        bar1 = _make_bar(open_=20095, high=20120, low=20092, close=20110)
        sig = s.on_bar(bar1, 1, ctx)
        assert sig is not None
        assert sig.direction == 'LONG'
        assert sig.setup_type == 'IB_RETRACE_LONG'
        assert sig.entry_price == 20110
        assert sig.metadata['impulse'] == 'UP'

    def test_long_stop_at_ib_low_minus_buffer(self):
        """Stop for LONG = IB_LOW - 10pt buffer."""
        s = IBRetracement()
        ctx = _session_context(ib_close=20180)
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        s.on_bar(_make_bar(low=20090, close=20095), 0, ctx)
        sig = s.on_bar(_make_bar(close=20110), 1, ctx)

        assert sig is not None
        assert sig.stop_price == 20000 - STOP_BUFFER_PTS  # 19990

    def test_long_target_opp_ib(self):
        """Target for LONG with opp_ib mode = IB_HIGH."""
        s = IBRetracement(target_mode='opp_ib')
        ctx = _session_context(ib_close=20180)
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        s.on_bar(_make_bar(low=20090, close=20095), 0, ctx)
        sig = s.on_bar(_make_bar(close=20110), 1, ctx)

        assert sig is not None
        assert sig.target_price == 20200  # IB_HIGH


class TestShortRetracementSignal:
    """SHORT signals on bearish impulse retracement."""

    def test_short_retrace_signal(self):
        """Bearish impulse, price retraces up into fib zone, drops out -> SHORT."""
        s = IBRetracement()
        # IB: 20000-20200, close at 20030 (15% position -> bottom 30%)
        ctx = _session_context(ib_close=20030)
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        assert s._impulse_direction == 'DOWN'
        # Fib zone for DOWN: lower = 20000 + 0.50*200 = 20100
        #                    upper = 20000 + 0.618*200 = 20123.6
        assert abs(s._fib_zone_lower - 20100.0) < 0.1
        assert abs(s._fib_zone_upper - 20123.6) < 0.1

        # Bar 0: high reaches into fib zone (20110, within 20100-20123.6)
        bar0 = _make_bar(open_=20090, high=20110, low=20085, close=20105)
        sig = s.on_bar(bar0, 0, ctx)
        assert sig is None  # In fib zone but close still in zone

        # Bar 1: price drops below fib zone lower
        bar1 = _make_bar(open_=20105, high=20108, low=20088, close=20092)
        sig = s.on_bar(bar1, 1, ctx)
        assert sig is not None
        assert sig.direction == 'SHORT'
        assert sig.setup_type == 'IB_RETRACE_SHORT'

    def test_short_stop_at_ib_high_plus_buffer(self):
        """Stop for SHORT = IB_HIGH + 10pt buffer."""
        s = IBRetracement()
        ctx = _session_context(ib_close=20030)
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        s.on_bar(_make_bar(high=20110, close=20105), 0, ctx)
        sig = s.on_bar(_make_bar(close=20092), 1, ctx)

        assert sig is not None
        assert sig.stop_price == 20200 + STOP_BUFFER_PTS  # 20210

    def test_short_target_opp_ib(self):
        """Target for SHORT with opp_ib mode = IB_LOW."""
        s = IBRetracement(target_mode='opp_ib')
        ctx = _session_context(ib_close=20030)
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        s.on_bar(_make_bar(high=20110, close=20105), 0, ctx)
        sig = s.on_bar(_make_bar(close=20092), 1, ctx)

        assert sig is not None
        assert sig.target_price == 20000  # IB_LOW


class TestNoSignalConditions:
    """Conditions where no signal should fire."""

    def test_no_signal_ib_range_too_narrow(self):
        """IB range < 80 pts -> no signal."""
        s = IBRetracement(min_ib_range=80)
        ctx = _session_context(ib_close=20058)  # top 30% of 60pt range
        s.on_session_start('2026-03-10', 20060, 20000, 60, ctx)

        sig = s.on_bar(_make_bar(close=20020), 0, ctx)
        assert sig is None

    def test_no_signal_before_ib_close(self):
        """No signals before 10:30 ET."""
        s = IBRetracement()
        ctx = _session_context(ib_close=20180, bar_time=_time(10, 25))
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        sig = s.on_bar(_make_bar(low=20090, close=20095), 0, ctx)
        assert sig is None

    def test_no_signal_after_1230(self):
        """No signals after 12:30 ET."""
        s = IBRetracement()
        ctx = _session_context(ib_close=20180, bar_time=_time(12, 35))
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        sig = s.on_bar(_make_bar(low=20090, close=20095), 0, ctx)
        assert sig is None

    def test_no_signal_price_never_enters_fib_zone(self):
        """Price stays outside fib zone -> no signal."""
        s = IBRetracement()
        ctx = _session_context(ib_close=20180)
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        # Price stays above fib zone upper (20100)
        sig = s.on_bar(_make_bar(high=20150, low=20120, close=20130), 0, ctx)
        assert sig is None

    def test_only_one_signal_per_session(self):
        """After emitting a signal, no more signals."""
        s = IBRetracement()
        ctx = _session_context(ib_close=20180)
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        # First signal
        s.on_bar(_make_bar(low=20090, close=20095), 0, ctx)
        sig = s.on_bar(_make_bar(close=20110), 1, ctx)
        assert sig is not None

        # Second attempt -> blocked
        sig = s.on_bar(_make_bar(low=20085, close=20110), 2, ctx)
        assert sig is None


class TestTargetModes:
    """Different target computation modes."""

    def test_2r_target(self):
        s = IBRetracement(target_mode='2r')
        ctx = _session_context(ib_close=20180)
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        s.on_bar(_make_bar(low=20090, close=20095), 0, ctx)
        sig = s.on_bar(_make_bar(close=20110), 1, ctx)

        assert sig is not None
        risk = sig.entry_price - sig.stop_price  # 20110 - 19990 = 120
        assert sig.target_price == sig.entry_price + 2.0 * risk

    def test_1r_target(self):
        s = IBRetracement(target_mode='1r')
        ctx = _session_context(ib_close=20180)
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        s.on_bar(_make_bar(low=20090, close=20095), 0, ctx)
        sig = s.on_bar(_make_bar(close=20110), 1, ctx)

        assert sig is not None
        risk = sig.entry_price - sig.stop_price
        assert sig.target_price == sig.entry_price + risk

    def test_1_5x_ib_target(self):
        s = IBRetracement(target_mode='1.5x_ib')
        ctx = _session_context(ib_close=20180)
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        s.on_bar(_make_bar(low=20090, close=20095), 0, ctx)
        sig = s.on_bar(_make_bar(close=20110), 1, ctx)

        assert sig is not None
        assert sig.target_price == 20110 + 1.5 * 200  # 20410


class TestConfidenceLevel:
    """IB Retracement should have low confidence (rejected strategy)."""

    def test_low_confidence(self):
        s = IBRetracement()
        ctx = _session_context(ib_close=20180)
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        s.on_bar(_make_bar(low=20090, close=20095), 0, ctx)
        sig = s.on_bar(_make_bar(close=20110), 1, ctx)

        assert sig is not None
        assert sig.confidence == 'low'


class TestLoaderRegistration:
    """Strategy is registered in the loader."""

    def test_in_registry(self):
        from rockit_core.strategies.loader import get_strategy_class
        cls = get_strategy_class('ib_retracement')
        assert cls is not None
        assert cls.__name__ == 'IBRetracement'

    def test_instantiation_via_loader(self):
        from rockit_core.strategies.loader import get_strategy_class
        cls = get_strategy_class('ib_retracement')
        instance = cls()
        assert instance.name == "IB Retracement"
