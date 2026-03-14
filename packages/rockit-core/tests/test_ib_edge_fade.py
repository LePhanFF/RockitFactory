"""Tests for IB Edge Fade strategy."""

import pytest
import pandas as pd
from datetime import time as _time, datetime

from rockit_core.strategies.ib_edge_fade import (
    IBEdgeFade,
    ENTRY_START,
    ENTRY_CUTOFF,
    MIN_IB_RANGE,
    POKE_MIN_PTS_LONG,
    POKE_MIN_PTS_SHORT,
    ACCEPT_BARS_LONG,
    ACCEPT_BARS_SHORT,
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
    bar_time=_time(11, 0), day_type='b_day', session_bias='NEUTRAL',
    atr14=20.0,
):
    """Create a minimal session context dict."""
    return {
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
        s = IBEdgeFade()
        assert s.name == "IB Edge Fade"
        assert s.applicable_day_types == []
        assert s._poke_min_long == POKE_MIN_PTS_LONG
        assert s._poke_min_short == POKE_MIN_PTS_SHORT
        assert s._accept_bars_long == ACCEPT_BARS_LONG
        assert s._accept_bars_short == ACCEPT_BARS_SHORT
        assert s._stop_mode_long == '10pct_ib'
        assert s._stop_mode_short == '0.5atr'
        assert s._target_mode_long == '2r'
        assert s._target_mode_short == '1r'
        assert s._min_ib_range == MIN_IB_RANGE

    def test_custom_config(self):
        s = IBEdgeFade(poke_min_long=5, poke_min_short=3,
                       accept_bars_long=3, accept_bars_short=2,
                       min_ib_range=150, max_touch=2)
        assert s._poke_min_long == 5
        assert s._poke_min_short == 3
        assert s._accept_bars_long == 3
        assert s._accept_bars_short == 2
        assert s._min_ib_range == 150
        assert s._max_touch == 2

    def test_repr(self):
        s = IBEdgeFade()
        assert "IBEdgeFade" in repr(s)


class TestIBLFadeLong:
    """LONG signals at IBL rejection."""

    def test_ibl_fade_long_signal(self):
        """Price pokes below IBL by >= 3 pts, 2 bars close above -> LONG."""
        s = IBEdgeFade()
        ctx = _session_context()
        # IB: 20200 to 20000, range=200
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        # Bar 0: poke below IBL (20000) by 5 pts
        bar0 = _make_bar(open_=20005, high=20010, low=19995, close=19998)
        sig = s.on_bar(bar0, 0, ctx)
        assert sig is None  # Poke detected

        # Bar 1: first bar closing above IBL
        bar1 = _make_bar(open_=19998, high=20015, low=19995, close=20008)
        sig = s.on_bar(bar1, 1, ctx)
        assert sig is None  # Only 1 accept bar

        # Bar 2: second bar closing above IBL -> signal
        bar2 = _make_bar(open_=20008, high=20020, low=20005, close=20015)
        sig = s.on_bar(bar2, 2, ctx)
        assert sig is not None
        assert sig.direction == 'LONG'
        assert sig.setup_type == 'IBL_EDGE_FADE'
        assert sig.entry_price == 20015
        assert sig.metadata['level'] == 'IBL'
        assert sig.metadata['ib_range'] == 200

    def test_ibl_stop_10pct_ib(self):
        """Stop for LONG with 10%IB stop mode."""
        s = IBEdgeFade(stop_mode_long='10pct_ib')
        ctx = _session_context()
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        s.on_bar(_make_bar(low=19995, close=19998), 0, ctx)
        s.on_bar(_make_bar(close=20008), 1, ctx)
        sig = s.on_bar(_make_bar(close=20015), 2, ctx)

        assert sig is not None
        # 10% of 200 = 20 pts
        assert sig.stop_price == 20015 - 20.0  # 19995

    def test_ibl_target_2r(self):
        """Target for LONG with 2R target mode."""
        s = IBEdgeFade(stop_mode_long='10pct_ib', target_mode_long='2r')
        ctx = _session_context()
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        s.on_bar(_make_bar(low=19995, close=19998), 0, ctx)
        s.on_bar(_make_bar(close=20008), 1, ctx)
        sig = s.on_bar(_make_bar(close=20015), 2, ctx)

        assert sig is not None
        risk = sig.entry_price - sig.stop_price
        assert sig.target_price == sig.entry_price + 2.0 * risk


class TestIBHFadeShort:
    """SHORT signals at IBH rejection."""

    def test_ibh_fade_short_signal(self):
        """Price pokes above IBH (any amount), 1 bar closes below -> SHORT."""
        s = IBEdgeFade()
        ctx = _session_context()
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        # Bar 0: poke above IBH (any poke for SHORT with poke_min=0)
        bar0 = _make_bar(open_=20195, high=20205, low=20190, close=20202)
        sig = s.on_bar(bar0, 0, ctx)
        assert sig is None  # Poke detected

        # Bar 1: close below IBH -> signal (1 accept bar for SHORT)
        bar1 = _make_bar(open_=20198, high=20202, low=20185, close=20190)
        sig = s.on_bar(bar1, 1, ctx)
        assert sig is not None
        assert sig.direction == 'SHORT'
        assert sig.setup_type == 'IBH_EDGE_FADE'
        assert sig.metadata['level'] == 'IBH'

    def test_ibh_stop_half_atr(self):
        """Stop for SHORT with 0.5ATR stop mode."""
        s = IBEdgeFade(stop_mode_short='0.5atr')
        ctx = _session_context(atr14=30.0)
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        s.on_bar(_make_bar(high=20205, close=20202), 0, ctx)
        sig = s.on_bar(_make_bar(close=20190), 1, ctx)

        assert sig is not None
        assert sig.stop_price == 20190 + 0.5 * 30.0  # 20205

    def test_ibh_target_1r(self):
        """Target for SHORT with 1R target mode."""
        s = IBEdgeFade(stop_mode_short='0.5atr', target_mode_short='1r')
        ctx = _session_context(atr14=30.0)
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        s.on_bar(_make_bar(high=20205, close=20202), 0, ctx)
        sig = s.on_bar(_make_bar(close=20190), 1, ctx)

        assert sig is not None
        risk = sig.stop_price - sig.entry_price
        assert sig.target_price == sig.entry_price - risk

    def test_ibh_target_ib_mid(self):
        """Target for SHORT with ib_mid target mode."""
        s = IBEdgeFade(target_mode_short='ib_mid')
        ctx = _session_context()
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        s.on_bar(_make_bar(high=20205, close=20202), 0, ctx)
        sig = s.on_bar(_make_bar(close=20190), 1, ctx)

        assert sig is not None
        assert sig.target_price == 20100.0  # (20200 + 20000) / 2


class TestNoSignalConditions:
    """Conditions where no signal should fire."""

    def test_no_signal_ib_range_too_narrow(self):
        """IB range < 100 pts -> no signal."""
        s = IBEdgeFade(min_ib_range=100)
        ctx = _session_context()
        s.on_session_start('2026-03-10', 20050, 19980, 70, ctx)

        sig = s.on_bar(_make_bar(low=19975, close=19978), 0, ctx)
        assert sig is None

    def test_no_signal_before_ib_close(self):
        """No signals before 10:30 ET."""
        s = IBEdgeFade()
        ctx = _session_context(bar_time=_time(10, 25))
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        sig = s.on_bar(_make_bar(low=19995, close=19998), 0, ctx)
        assert sig is None

    def test_no_signal_after_2pm(self):
        """No signals after 14:00 ET."""
        s = IBEdgeFade()
        ctx = _session_context(bar_time=_time(14, 5))
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        sig = s.on_bar(_make_bar(low=19995, close=19998), 0, ctx)
        assert sig is None

    def test_no_signal_price_inside_ib(self):
        """Price stays inside IB -> no signal."""
        s = IBEdgeFade()
        ctx = _session_context()
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        sig = s.on_bar(_make_bar(high=20180, low=20020, close=20100), 0, ctx)
        assert sig is None

    def test_no_long_when_poke_too_small(self):
        """IBL poke < poke_min_long -> not counted."""
        s = IBEdgeFade(poke_min_long=10)
        ctx = _session_context()
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        # Low = 19995, only 5 pts below IBL (need 10)
        sig = s.on_bar(_make_bar(low=19995, close=19998), 0, ctx)
        assert sig is None
        assert not s._ibl_poke_detected


class TestMaxTouch:
    """Max touch per edge per session."""

    def test_only_one_trade_per_edge(self):
        """After trading IBL, no more IBL signals."""
        s = IBEdgeFade()
        ctx = _session_context()
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        # First trade at IBL
        s.on_bar(_make_bar(low=19995, close=19998), 0, ctx)
        s.on_bar(_make_bar(close=20008), 1, ctx)
        sig = s.on_bar(_make_bar(close=20015), 2, ctx)
        assert sig is not None
        assert s._ibl_traded is True

        # Try to trigger again — should be blocked
        s._ibl_poke_detected = False
        s.on_bar(_make_bar(low=19990, close=19995), 3, ctx)
        s.on_bar(_make_bar(close=20010), 4, ctx)
        sig = s.on_bar(_make_bar(close=20012), 5, ctx)
        assert sig is None

    def test_both_edges_can_trade(self):
        """Can trade both IBL and IBH in same session."""
        s = IBEdgeFade()
        ctx = _session_context()
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        # Trade IBL (LONG)
        s.on_bar(_make_bar(low=19995, close=19998), 0, ctx)
        s.on_bar(_make_bar(close=20008), 1, ctx)
        sig1 = s.on_bar(_make_bar(close=20015), 2, ctx)
        assert sig1 is not None
        assert sig1.direction == 'LONG'

        # Trade IBH (SHORT)
        s.on_bar(_make_bar(high=20205, close=20202), 3, ctx)
        sig2 = s.on_bar(_make_bar(close=20190), 4, ctx)
        assert sig2 is not None
        assert sig2.direction == 'SHORT'


class TestAcceptanceReset:
    """Acceptance count resets when bar closes wrong side."""

    def test_ibl_accept_resets(self):
        """If bar closes below IBL during acceptance, count resets."""
        s = IBEdgeFade()
        ctx = _session_context()
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        # Poke below IBL
        s.on_bar(_make_bar(low=19995, close=19998), 0, ctx)
        # 1 accept bar
        s.on_bar(_make_bar(close=20005), 1, ctx)
        assert s._ibl_accept_count == 1
        # Close below IBL — resets
        s.on_bar(_make_bar(close=19998), 2, ctx)
        assert s._ibl_accept_count == 0
        # Start over
        s.on_bar(_make_bar(close=20005), 3, ctx)
        assert s._ibl_accept_count == 1
        sig = s.on_bar(_make_bar(close=20010), 4, ctx)
        assert sig is not None  # 2nd accept bar fires signal


class TestStopModes:
    """Different stop computation modes."""

    def test_fixed_5pt_stop(self):
        s = IBEdgeFade(stop_mode_short='fixed_5pt')
        ctx = _session_context()
        s.on_session_start('2026-03-10', 20200, 20000, 200, ctx)

        s.on_bar(_make_bar(high=20205, close=20202), 0, ctx)
        sig = s.on_bar(_make_bar(close=20190), 1, ctx)

        assert sig is not None
        assert sig.stop_price == 20190 + 5.0  # 20195

    def test_10pct_ib_stop_floor(self):
        """10% IB stop has 5pt floor."""
        s = IBEdgeFade(stop_mode_long='10pct_ib')
        ctx = _session_context()
        # Very narrow IB (just above min): 10% of 100 = 10 pts
        s.on_session_start('2026-03-10', 20100, 20000, 100, ctx)

        s.on_bar(_make_bar(low=19995, close=19998), 0, ctx)
        s.on_bar(_make_bar(close=20008), 1, ctx)
        sig = s.on_bar(_make_bar(close=20015), 2, ctx)

        assert sig is not None
        assert sig.stop_price == 20015 - 10.0  # 10% of 100 = 10


class TestLoaderRegistration:
    """Strategy is registered in the loader."""

    def test_in_registry(self):
        from rockit_core.strategies.loader import get_strategy_class
        cls = get_strategy_class('ib_edge_fade')
        assert cls is not None
        assert cls.__name__ == 'IBEdgeFade'

    def test_instantiation_via_loader(self):
        from rockit_core.strategies.loader import get_strategy_class
        cls = get_strategy_class('ib_edge_fade')
        instance = cls()
        assert instance.name == "IB Edge Fade"
