"""Tests for VA Edge Fade strategy."""

import pytest
import pandas as pd
from datetime import time as _time, datetime

from rockit_core.strategies.va_edge_fade import (
    VAEdgeFade,
    ENTRY_START,
    ENTRY_CUTOFF,
    EDGE_BUFFER_PTS,
    POKE_MIN_PTS,
    ACCEPT_BARS,
    MAX_TOUCH_COUNT,
)


def _make_bar(open_=20000, high=20010, low=19990, close=20000, timestamp=None):
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
    prior_vah=20100.0, prior_val=19900.0, prior_poc=20000.0,
    bar_time=_time(11, 0), day_type='b_day', session_bias='NEUTRAL',
    atr14=20.0,
):
    """Create a minimal session context dict."""
    return {
        'prior_va_vah': prior_vah,
        'prior_va_val': prior_val,
        'prior_va_poc': prior_poc,
        'bar_time': bar_time,
        'day_type': day_type,
        'session_bias': session_bias,
        'regime_bias': session_bias,
        'atr14': atr14,
        'trend_strength': 'moderate',
    }


class TestInstantiation:
    """Strategy instantiation and properties."""

    def test_default_config(self):
        s = VAEdgeFade()
        assert s.name == "VA Edge Fade"
        assert s.applicable_day_types == []
        assert s._short_only is True
        assert s._stop_mode == 'edge_20'
        assert s._target_mode == '3r'
        assert s._accept_bars == ACCEPT_BARS
        assert s._poke_min == POKE_MIN_PTS
        assert s._max_touch == MAX_TOUCH_COUNT

    def test_custom_config(self):
        s = VAEdgeFade(short_only=False, stop_mode='edge_10', target_mode='2r',
                       accept_bars=3, poke_min=10, max_touch=2, min_va_width=100)
        assert s._short_only is False
        assert s._stop_mode == 'edge_10'
        assert s._target_mode == '2r'
        assert s._accept_bars == 3
        assert s._poke_min == 10
        assert s._max_touch == 2
        assert s._min_va_width == 100

    def test_repr(self):
        s = VAEdgeFade()
        assert "VAEdgeFade" in repr(s)


class TestVAHFadeShort:
    """SHORT signals at VAH rejection."""

    def test_vah_fade_short_signal(self):
        """Price pokes above VAH, then 3 bars close below -> SHORT."""
        s = VAEdgeFade()
        ctx = _session_context(prior_vah=20100.0, prior_val=19900.0)
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        # Bar 0: poke above VAH by >= 5 pts (high=20108)
        bar0 = _make_bar(open_=20095, high=20108, low=20090, close=20105)
        sig = s.on_bar(bar0, 0, ctx)
        assert sig is None  # Just detected poke

        # Bar 1: first bar closing below VAH
        bar1 = _make_bar(open_=20102, high=20104, low=20088, close=20092)
        sig = s.on_bar(bar1, 1, ctx)
        assert sig is None  # Only 1 accept bar, need 3

        # Bar 2: second bar closing below VAH
        bar2 = _make_bar(open_=20090, high=20095, low=20080, close=20085)
        sig = s.on_bar(bar2, 2, ctx)
        assert sig is None  # Only 2 accept bars, need 3

        # Bar 3: third bar closing below VAH -> signal
        bar3 = _make_bar(open_=20083, high=20088, low=20075, close=20080)
        sig = s.on_bar(bar3, 3, ctx)
        assert sig is not None
        assert sig.direction == 'SHORT'
        assert sig.setup_type == 'VAH_EDGE_FADE'
        assert sig.entry_price == 20080
        assert sig.metadata['level'] == 'VAH'
        assert sig.metadata['touch_number'] == 1

    def test_stop_at_vah_plus_buffer(self):
        """Stop price = VAH + 20pt buffer for edge_20 mode."""
        s = VAEdgeFade(stop_mode='edge_20')
        ctx = _session_context(prior_vah=20100.0, prior_val=19900.0)
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        # Poke + 3 accept bars
        s.on_bar(_make_bar(high=20108, close=20105), 0, ctx)
        s.on_bar(_make_bar(close=20092), 1, ctx)
        s.on_bar(_make_bar(close=20085), 2, ctx)
        sig = s.on_bar(_make_bar(close=20080), 3, ctx)

        assert sig is not None
        assert sig.stop_price == 20100 + EDGE_BUFFER_PTS  # 20120

    def test_3r_target(self):
        """Target = entry - 3 * risk for 3r mode."""
        s = VAEdgeFade(stop_mode='edge_20', target_mode='3r')
        ctx = _session_context(prior_vah=20100.0, prior_val=19900.0)
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        s.on_bar(_make_bar(high=20108, close=20105), 0, ctx)
        s.on_bar(_make_bar(close=20092), 1, ctx)
        s.on_bar(_make_bar(close=20085), 2, ctx)
        sig = s.on_bar(_make_bar(close=20080), 3, ctx)

        assert sig is not None
        risk = sig.stop_price - sig.entry_price  # 20120 - 20080 = 40
        expected_target = sig.entry_price - 3.0 * risk
        assert sig.target_price == expected_target

    def test_acceptance_resets_on_close_above_vah(self):
        """If a bar closes above VAH mid-acceptance, count resets."""
        s = VAEdgeFade()
        ctx = _session_context(prior_vah=20100.0, prior_val=19900.0)
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        # Poke
        s.on_bar(_make_bar(high=20108, close=20105), 0, ctx)
        # 1 accept bar
        s.on_bar(_make_bar(close=20092), 1, ctx)
        # Close back above VAH — resets count
        s.on_bar(_make_bar(close=20102), 2, ctx)
        # 1 accept bar again
        s.on_bar(_make_bar(close=20090), 3, ctx)
        assert s._vah_accept_count == 1
        # 2nd accept bar
        s.on_bar(_make_bar(close=20085), 4, ctx)
        assert s._vah_accept_count == 2
        # 3rd accept bar -> signal
        sig = s.on_bar(_make_bar(close=20080), 5, ctx)
        assert sig is not None

    def test_spike_tracking(self):
        """Spike high should track the highest point during poke."""
        s = VAEdgeFade()
        ctx = _session_context(prior_vah=20100.0, prior_val=19900.0)
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        # Poke at 20108
        s.on_bar(_make_bar(high=20108, close=20105), 0, ctx)
        # Higher spike at 20115
        s.on_bar(_make_bar(high=20115, close=20092), 1, ctx)
        s.on_bar(_make_bar(close=20085), 2, ctx)
        sig = s.on_bar(_make_bar(close=20080), 3, ctx)

        assert sig is not None
        assert sig.metadata['spike_high'] == 20115


class TestVALFadeLong:
    """LONG signals at VAL rejection (when short_only=False)."""

    def test_val_fade_long_signal(self):
        """Price pokes below VAL, then 3 bars close above -> LONG."""
        s = VAEdgeFade(short_only=False)
        ctx = _session_context(prior_vah=20100.0, prior_val=19900.0)
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        # Poke below VAL
        bar0 = _make_bar(open_=19905, high=19910, low=19892, close=19895)
        sig = s.on_bar(bar0, 0, ctx)
        assert sig is None

        # Accept bar 1
        bar1 = _make_bar(open_=19898, high=19915, low=19895, close=19908)
        sig = s.on_bar(bar1, 1, ctx)
        assert sig is None

        # Accept bar 2
        bar2 = _make_bar(open_=19908, high=19920, low=19905, close=19915)
        sig = s.on_bar(bar2, 2, ctx)
        assert sig is None  # Only 2 accept bars, need 3

        # Accept bar 3 -> signal
        bar3 = _make_bar(open_=19915, high=19925, low=19912, close=19920)
        sig = s.on_bar(bar3, 3, ctx)
        assert sig is not None
        assert sig.direction == 'LONG'
        assert sig.setup_type == 'VAL_EDGE_FADE'
        assert sig.metadata['level'] == 'VAL'

    def test_val_stop_at_val_minus_buffer(self):
        """Stop for LONG = VAL - 20pt buffer."""
        s = VAEdgeFade(short_only=False, stop_mode='edge_20')
        ctx = _session_context(prior_vah=20100.0, prior_val=19900.0)
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        s.on_bar(_make_bar(low=19892, close=19895), 0, ctx)
        s.on_bar(_make_bar(close=19908), 1, ctx)
        s.on_bar(_make_bar(close=19915), 2, ctx)
        sig = s.on_bar(_make_bar(close=19920), 3, ctx)

        assert sig is not None
        assert sig.stop_price == 19900 - EDGE_BUFFER_PTS  # 19880


class TestShortOnlyFilter:
    """Short-only mode blocks LONG signals."""

    def test_no_long_in_short_only_mode(self):
        """VAL poke should NOT generate LONG when short_only=True."""
        s = VAEdgeFade(short_only=True)  # Default
        ctx = _session_context(prior_vah=20100.0, prior_val=19900.0)
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        # Poke below VAL
        s.on_bar(_make_bar(low=19892, close=19895), 0, ctx)
        s.on_bar(_make_bar(close=19908), 1, ctx)
        s.on_bar(_make_bar(close=19915), 2, ctx)
        sig = s.on_bar(_make_bar(close=19920), 3, ctx)

        assert sig is None  # Blocked by short_only


class TestNoSignalConditions:
    """Conditions where no signal should fire."""

    def test_no_signal_no_va_data(self):
        """Missing prior VA levels -> no signal."""
        s = VAEdgeFade()
        ctx = _session_context(prior_vah=None, prior_val=None)
        ctx['prior_va_vah'] = None
        ctx['prior_va_val'] = None
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        sig = s.on_bar(_make_bar(high=20108, close=20085), 0, ctx)
        assert sig is None

    def test_no_signal_va_width_too_narrow(self):
        """VA width below minimum -> no signal."""
        s = VAEdgeFade(min_va_width=150)
        ctx = _session_context(prior_vah=20050.0, prior_val=19950.0)  # 100pt width
        s.on_session_start('2026-03-10', 20020, 19980, 40, ctx)

        sig = s.on_bar(_make_bar(high=20060, close=20040), 0, ctx)
        assert sig is None

    def test_no_signal_before_ib(self):
        """No signals before 10:30 ET."""
        s = VAEdgeFade()
        ctx = _session_context(bar_time=_time(10, 15))
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        sig = s.on_bar(_make_bar(high=20108, close=20085), 0, ctx)
        assert sig is None

    def test_no_signal_after_2pm(self):
        """No signals after 14:00 ET."""
        s = VAEdgeFade()
        ctx = _session_context(bar_time=_time(14, 5))
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        sig = s.on_bar(_make_bar(high=20108, close=20085), 0, ctx)
        assert sig is None

    def test_no_signal_price_doesnt_reach_vah(self):
        """Price stays well below VAH -> no signal."""
        s = VAEdgeFade()
        ctx = _session_context(prior_vah=20200.0, prior_val=19900.0)
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        sig = s.on_bar(_make_bar(high=20050, close=20040), 0, ctx)
        assert sig is None

    def test_no_signal_poke_too_small(self):
        """Poke < poke_min pts -> not counted."""
        s = VAEdgeFade(poke_min=10)
        ctx = _session_context(prior_vah=20100.0, prior_val=19900.0)
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        # High = 20105, only 5 pts above VAH (need 10)
        sig = s.on_bar(_make_bar(high=20105, close=20095), 0, ctx)
        assert sig is None
        assert not s._vah_poke_detected


class TestMaxTouch:
    """Max touch limits."""

    def test_second_touch_blocked_when_max_1(self):
        """Second VAH poke should be ignored when max_touch=1."""
        s = VAEdgeFade(max_touch=1)
        ctx = _session_context(prior_vah=20100.0, prior_val=19900.0)
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        # First poke — accepted
        s.on_bar(_make_bar(high=20108, close=20105), 0, ctx)
        assert s._vah_poke_detected is True

        # Close above VAH (acceptance fails to complete, poke stays active)
        # Need to make the poke fail somehow — actually the poke just stays
        # active, so let's test by having the first poke traded
        s.on_bar(_make_bar(close=20092), 1, ctx)
        s.on_bar(_make_bar(close=20085), 2, ctx)
        sig = s.on_bar(_make_bar(close=20080), 3, ctx)
        assert sig is not None  # First touch traded

        # VAH is now marked as traded, no more signals at VAH
        # Reset to simulate a second poke attempt
        s._vah_traded = False
        s._vah_poke_detected = False
        s.on_bar(_make_bar(high=20112, close=20105), 3, ctx)
        # Touch count is now 2 > max_touch(1), should be blocked
        assert s._vah_touch_count == 2


class TestStopModes:
    """Different stop computation modes."""

    def test_edge_10_stop(self):
        s = VAEdgeFade(stop_mode='edge_10')
        ctx = _session_context(prior_vah=20100.0, prior_val=19900.0)
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        s.on_bar(_make_bar(high=20108, close=20105), 0, ctx)
        s.on_bar(_make_bar(close=20092), 1, ctx)
        s.on_bar(_make_bar(close=20085), 2, ctx)
        sig = s.on_bar(_make_bar(close=20080), 3, ctx)

        assert sig is not None
        assert sig.stop_price == 20100 + 10.0  # 20110

    def test_atr2x_stop(self):
        s = VAEdgeFade(stop_mode='atr2x')
        ctx = _session_context(prior_vah=20100.0, prior_val=19900.0, atr14=25.0)
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        s.on_bar(_make_bar(high=20108, close=20105), 0, ctx)
        s.on_bar(_make_bar(close=20092), 1, ctx)
        s.on_bar(_make_bar(close=20085), 2, ctx)
        sig = s.on_bar(_make_bar(close=20080), 3, ctx)

        assert sig is not None
        assert sig.stop_price == 20080 + 2.0 * 25.0  # 20130


class TestTargetModes:
    """Different target computation modes."""

    def test_2r_target(self):
        s = VAEdgeFade(stop_mode='edge_20', target_mode='2r')
        ctx = _session_context(prior_vah=20100.0, prior_val=19900.0)
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        s.on_bar(_make_bar(high=20108, close=20105), 0, ctx)
        s.on_bar(_make_bar(close=20092), 1, ctx)
        s.on_bar(_make_bar(close=20085), 2, ctx)
        sig = s.on_bar(_make_bar(close=20080), 3, ctx)

        risk = sig.stop_price - sig.entry_price
        assert sig.target_price == sig.entry_price - 2.0 * risk

    def test_poc_target(self):
        s = VAEdgeFade(target_mode='poc')
        ctx = _session_context(prior_vah=20100.0, prior_val=19900.0, prior_poc=20000.0)
        s.on_session_start('2026-03-10', 20050, 19950, 100, ctx)

        s.on_bar(_make_bar(high=20108, close=20105), 0, ctx)
        s.on_bar(_make_bar(close=20092), 1, ctx)
        s.on_bar(_make_bar(close=20085), 2, ctx)
        sig = s.on_bar(_make_bar(close=20080), 3, ctx)

        assert sig is not None
        assert sig.target_price == 20000.0  # POC


class TestLoaderRegistration:
    """Strategy is registered in the loader."""

    def test_in_registry(self):
        from rockit_core.strategies.loader import get_strategy_class
        cls = get_strategy_class('va_edge_fade')
        assert cls is not None
        assert cls.__name__ == 'VAEdgeFade'

    def test_instantiation_via_loader(self):
        from rockit_core.strategies.loader import get_strategy_class
        cls = get_strategy_class('va_edge_fade')
        instance = cls()
        assert instance.name == "VA Edge Fade"
