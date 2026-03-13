"""Tests for PDH/PDL Reaction strategy."""

import pytest
import pandas as pd
import numpy as np
from datetime import time as _time, datetime

from rockit_core.strategies.pdh_pdl_reaction import (
    PDHPDLReaction,
    ENTRY_START,
    ENTRY_CUTOFF,
    MIN_PRIOR_RANGE,
    SPIKE_BUFFER_PTS,
    TOUCH_STOP_PTS,
    POKE_MIN_PTS,
    TOUCH_PROXIMITY_PTS,
    REJECTION_CLOSE_PCT,
)


def _make_bar(open_=20000, high=20010, low=19990, close=20000, timestamp=None):
    """Create a simple bar Series."""
    ts = timestamp or datetime(2026, 3, 10, 10, 30)
    return pd.Series({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': 1000,
        'timestamp': ts,
    })


def _session_context(
    pdh=20050.0, pdl=19900.0, bar_time=_time(10, 30),
    day_type='neutral', session_bias='NEUTRAL', vwap=19975.0,
    atr14=20.0,
):
    """Create a minimal session context dict."""
    return {
        'pdh': pdh,
        'pdl': pdl,
        'prior_session_high': pdh,
        'prior_session_low': pdl,
        'bar_time': bar_time,
        'day_type': day_type,
        'session_bias': session_bias,
        'regime_bias': session_bias,
        'vwap': vwap,
        'atr14': atr14,
        'trend_strength': 'moderate',
    }


class TestInstantiation:
    """Strategy instantiation and properties."""

    def test_default_config(self):
        s = PDHPDLReaction()
        assert s.name == "PDH/PDL Reaction"
        assert s.applicable_day_types == []
        assert s._setup_modes == {'A', 'C'}
        assert s._stop_mode == 'spike'
        assert s._target_mode == '2r'
        assert s._require_bias is True

    def test_custom_config(self):
        s = PDHPDLReaction(setup_modes=['A'], poke_min=10, stop_mode='fixed30',
                           target_mode='poc', require_bias_alignment=False)
        assert s._setup_modes == {'A'}
        assert s._poke_min == 10
        assert s._stop_mode == 'fixed30'
        assert s._target_mode == 'poc'
        assert s._require_bias is False

    def test_repr(self):
        s = PDHPDLReaction()
        assert "PDHPDLReaction" in repr(s)


class TestSetupA_FailedAuction:
    """Setup A: Failed Auction at PDH/PDL."""

    def test_failed_auction_pdh_short(self):
        """Price pokes above PDH, then closes back below -> SHORT."""
        s = PDHPDLReaction(require_bias_alignment=False)
        ctx = _session_context(pdh=20050.0, pdl=19900.0)
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        # Bar 0: poke above PDH by >= 5 pts
        bar0 = _make_bar(open_=20048, high=20058, low=20045, close=20055)
        sig = s.on_bar(bar0, 0, ctx)
        assert sig is None  # Just detected the poke

        # Bar 1: close back below PDH -> signal
        bar1 = _make_bar(open_=20052, high=20054, low=20040, close=20042)
        sig = s.on_bar(bar1, 1, ctx)
        assert sig is not None
        assert sig.direction == 'SHORT'
        assert sig.setup_type == 'PDH_FAILED_AUCTION'
        assert sig.entry_price == 20042
        assert sig.metadata['level'] == 'PDH'
        assert sig.metadata['setup'] == 'A'

    def test_failed_auction_pdl_long(self):
        """Price pokes below PDL, then closes back above -> LONG."""
        s = PDHPDLReaction(require_bias_alignment=False)
        ctx = _session_context(pdh=20050.0, pdl=19900.0)
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        # Bar 0: poke below PDL by >= 5 pts
        bar0 = _make_bar(open_=19902, high=19905, low=19892, close=19895)
        sig = s.on_bar(bar0, 0, ctx)
        assert sig is None

        # Bar 1: close back above PDL -> signal
        bar1 = _make_bar(open_=19898, high=19910, low=19895, close=19908)
        sig = s.on_bar(bar1, 1, ctx)
        assert sig is not None
        assert sig.direction == 'LONG'
        assert sig.setup_type == 'PDL_FAILED_AUCTION'
        assert sig.entry_price == 19908
        assert sig.metadata['level'] == 'PDL'

    def test_failed_auction_expires_after_5_bars(self):
        """Poke that doesn't close back within 5 bars is cancelled."""
        s = PDHPDLReaction(require_bias_alignment=False)
        ctx = _session_context(pdh=20050.0, pdl=19900.0)
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        # Bar 0: poke above PDH
        bar0 = _make_bar(high=20058, close=20055)
        s.on_bar(bar0, 0, ctx)

        # Bars 1-5: stay above PDH
        for i in range(1, 6):
            bar = _make_bar(high=20060, close=20055)
            s.on_bar(bar, i, ctx)

        # Bar 6: NOW close below — should NOT fire (poke expired at bar 5)
        bar6 = _make_bar(close=20040)
        sig = s.on_bar(bar6, 6, ctx)
        assert sig is None

    def test_stop_at_spike_high_plus_buffer(self):
        """Stop price = spike high + 5pt buffer for SHORT."""
        s = PDHPDLReaction(require_bias_alignment=False)
        ctx = _session_context(pdh=20050.0, pdl=19900.0)
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        # Poke with spike to 20065
        bar0 = _make_bar(high=20065, close=20060)
        s.on_bar(bar0, 0, ctx)

        # Close back below PDH
        bar1 = _make_bar(high=20048, close=20042)
        sig = s.on_bar(bar1, 1, ctx)

        assert sig is not None
        assert sig.stop_price == 20065 + SPIKE_BUFFER_PTS  # 20070

    def test_stop_at_spike_low_minus_buffer_long(self):
        """Stop price = spike low - 5pt buffer for LONG."""
        s = PDHPDLReaction(require_bias_alignment=False)
        ctx = _session_context(pdh=20050.0, pdl=19900.0)
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        # Poke below PDL to 19888
        bar0 = _make_bar(low=19888, close=19892)
        s.on_bar(bar0, 0, ctx)

        # Close back above PDL
        bar1 = _make_bar(low=19895, close=19908)
        sig = s.on_bar(bar1, 1, ctx)

        assert sig is not None
        assert sig.stop_price == 19888 - SPIKE_BUFFER_PTS  # 19883


class TestSetupC_ReactionTouch:
    """Setup C: Reaction Touch at PDH/PDL."""

    def test_reaction_touch_pdh_short(self):
        """Touch near PDH with rejection candle -> SHORT."""
        s = PDHPDLReaction(setup_modes=['C'], require_bias_alignment=False)
        ctx = _session_context(pdh=20050.0, pdl=19900.0)
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        # Bar touches PDH (within 3 pts), closes in bottom 30%
        # PDH = 20050, high = 20048 (within 3), bar range = 20
        # close at bottom 30%: close_position = (close - low) / range <= 0.30
        # low=20030, high=20050, close=20034 -> pos = (20034-20030)/20 = 0.20
        bar = _make_bar(open_=20045, high=20048, low=20030, close=20034)
        sig = s.on_bar(bar, 0, ctx)
        assert sig is not None
        assert sig.direction == 'SHORT'
        assert sig.setup_type == 'PDH_REACTION_TOUCH'
        assert sig.metadata['setup'] == 'C'

    def test_reaction_touch_pdl_long(self):
        """Touch near PDL with rejection candle -> LONG."""
        s = PDHPDLReaction(setup_modes=['C'], require_bias_alignment=False)
        ctx = _session_context(pdh=20050.0, pdl=19900.0)
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        # Bar touches PDL (within 3 pts), closes in top 30%
        # PDL = 19900, low = 19902 (within 3), bar range = 20
        # close in top 30%: close_position >= 0.70
        # low=19902, high=19922, close=19918 -> pos = (19918-19902)/20 = 0.80
        bar = _make_bar(open_=19910, high=19922, low=19902, close=19918)
        sig = s.on_bar(bar, 0, ctx)
        assert sig is not None
        assert sig.direction == 'LONG'
        assert sig.setup_type == 'PDL_REACTION_TOUCH'

    def test_no_signal_without_rejection(self):
        """Touch without rejection candle -> no signal."""
        s = PDHPDLReaction(setup_modes=['C'], require_bias_alignment=False)
        ctx = _session_context(pdh=20050.0, pdl=19900.0)
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        # Bar touches PDH but closes in middle of range (no rejection)
        bar = _make_bar(open_=20040, high=20048, low=20030, close=20040)
        sig = s.on_bar(bar, 0, ctx)
        assert sig is None

    def test_stop_at_level_plus_fixed_for_touch(self):
        """Setup C with spike stop_mode but no spike -> falls back to fixed stop."""
        s = PDHPDLReaction(setup_modes=['C'], require_bias_alignment=False)
        ctx = _session_context(pdh=20050.0, pdl=19900.0)
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        # Touch and rejection
        bar = _make_bar(open_=20045, high=20048, low=20030, close=20034)
        sig = s.on_bar(bar, 0, ctx)
        assert sig is not None
        # spike stop_mode with no spike_extreme -> falls back to default
        assert sig.stop_price == 20034 + TOUCH_STOP_PTS  # 20044


class TestNoSignalConditions:
    """Conditions where no signal should fire."""

    def test_no_signal_no_pdh_pdl(self):
        """No prior day levels -> no signal."""
        s = PDHPDLReaction(require_bias_alignment=False)
        ctx = _session_context(pdh=None, pdl=None)
        ctx['pdh'] = None
        ctx['pdl'] = None
        ctx['prior_session_high'] = None
        ctx['prior_session_low'] = None
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        bar = _make_bar(high=20058, close=20042)
        sig = s.on_bar(bar, 0, ctx)
        assert sig is None

    def test_no_signal_prior_range_too_tight(self):
        """Prior range < 50 pts -> no signal."""
        s = PDHPDLReaction(require_bias_alignment=False)
        # PDH - PDL = 30 pts, below 50 min
        ctx = _session_context(pdh=20030.0, pdl=20000.0)
        s.on_session_start('2026-03-10', 20010, 20000, 10, ctx)

        bar = _make_bar(high=20038, close=20025)
        sig = s.on_bar(bar, 0, ctx)
        assert sig is None

    def test_no_signal_price_doesnt_reach_levels(self):
        """Price stays in middle — no signal."""
        s = PDHPDLReaction(require_bias_alignment=False)
        ctx = _session_context(pdh=20100.0, pdl=19800.0)
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        bar = _make_bar(high=19980, low=19940, close=19960)
        sig = s.on_bar(bar, 0, ctx)
        assert sig is None

    def test_no_signal_before_10am(self):
        """No signals before 10:00 ET."""
        s = PDHPDLReaction(require_bias_alignment=False)
        ctx = _session_context(bar_time=_time(9, 45))
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        bar = _make_bar(high=20058, close=20042)
        sig = s.on_bar(bar, 0, ctx)
        assert sig is None

    def test_no_signal_after_2pm(self):
        """No signals after 14:00 ET."""
        s = PDHPDLReaction(require_bias_alignment=False)
        ctx = _session_context(bar_time=_time(14, 5))
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        bar = _make_bar(high=20058, close=20042)
        sig = s.on_bar(bar, 0, ctx)
        assert sig is None


class TestMaxTradesPerSession:
    """Max 1 trade per level, 2 total per session."""

    def test_max_one_pdh_trade(self):
        """Second PDH signal should be blocked."""
        s = PDHPDLReaction(require_bias_alignment=False)
        ctx = _session_context(pdh=20050.0, pdl=19900.0)
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        # First PDH trade
        bar0 = _make_bar(high=20058, close=20055)
        s.on_bar(bar0, 0, ctx)
        bar1 = _make_bar(close=20042)
        sig = s.on_bar(bar1, 1, ctx)
        assert sig is not None  # First trade fires

        # PDH is now marked as traded, so Setup C won't fire either
        bar2 = _make_bar(high=20048, low=20030, close=20034)
        sig = s.on_bar(bar2, 2, ctx)
        assert sig is None

    def test_max_two_total(self):
        """Max 2 trades (1 PDH + 1 PDL) per session."""
        s = PDHPDLReaction(require_bias_alignment=False)
        ctx = _session_context(pdh=20050.0, pdl=19900.0)
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        # Trade 1: PDH failed auction
        bar0 = _make_bar(high=20058, close=20055)
        s.on_bar(bar0, 0, ctx)
        bar1 = _make_bar(close=20042)
        sig1 = s.on_bar(bar1, 1, ctx)
        assert sig1 is not None

        # Trade 2: PDL failed auction
        bar2 = _make_bar(low=19892, close=19895)
        s.on_bar(bar2, 2, ctx)
        bar3 = _make_bar(close=19908)
        sig2 = s.on_bar(bar3, 3, ctx)
        assert sig2 is not None

        # Trade 3: should be blocked (max 2)
        s._pdh_traded = False  # Reset for testing
        s._pdh_spike_high = None
        bar4 = _make_bar(high=20060, close=20055)
        s.on_bar(bar4, 4, ctx)
        bar5 = _make_bar(close=20042)
        sig3 = s.on_bar(bar5, 5, ctx)
        assert sig3 is None


class TestBiasAlignment:
    """Bias alignment filter."""

    def test_skip_short_on_bullish_bias(self):
        """PDH SHORT should be blocked when session bias is BULL."""
        s = PDHPDLReaction(require_bias_alignment=True)
        ctx = _session_context(pdh=20050.0, pdl=19900.0, session_bias='BULL')
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        bar0 = _make_bar(high=20058, close=20055)
        s.on_bar(bar0, 0, ctx)
        bar1 = _make_bar(close=20042)
        sig = s.on_bar(bar1, 1, ctx)
        assert sig is None

    def test_skip_long_on_bearish_bias(self):
        """PDL LONG should be blocked when session bias is BEAR."""
        s = PDHPDLReaction(require_bias_alignment=True)
        ctx = _session_context(pdh=20050.0, pdl=19900.0, session_bias='BEAR')
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        bar0 = _make_bar(low=19892, close=19895)
        s.on_bar(bar0, 0, ctx)
        bar1 = _make_bar(close=19908)
        sig = s.on_bar(bar1, 1, ctx)
        assert sig is None

    def test_allow_short_on_bearish_bias(self):
        """PDH SHORT should fire when bias is BEAR (aligned)."""
        s = PDHPDLReaction(require_bias_alignment=True)
        ctx = _session_context(pdh=20050.0, pdl=19900.0, session_bias='BEAR')
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        bar0 = _make_bar(high=20058, close=20055)
        s.on_bar(bar0, 0, ctx)
        bar1 = _make_bar(close=20042)
        sig = s.on_bar(bar1, 1, ctx)
        assert sig is not None
        assert sig.direction == 'SHORT'

    def test_allow_on_neutral_bias(self):
        """Neutral bias should not block any direction."""
        s = PDHPDLReaction(require_bias_alignment=True)
        ctx = _session_context(pdh=20050.0, pdl=19900.0, session_bias='NEUTRAL')
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        bar0 = _make_bar(high=20058, close=20055)
        s.on_bar(bar0, 0, ctx)
        bar1 = _make_bar(close=20042)
        sig = s.on_bar(bar1, 1, ctx)
        assert sig is not None

    def test_no_bias_filter_when_disabled(self):
        """With require_bias_alignment=False, all directions allowed."""
        s = PDHPDLReaction(require_bias_alignment=False)
        ctx = _session_context(pdh=20050.0, pdl=19900.0, session_bias='BULL')
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        bar0 = _make_bar(high=20058, close=20055)
        s.on_bar(bar0, 0, ctx)
        bar1 = _make_bar(close=20042)
        sig = s.on_bar(bar1, 1, ctx)
        assert sig is not None  # Not blocked despite BULL bias


class TestSetupBDisabled:
    """Setup B (Continuation) is disabled by default."""

    def test_setup_b_not_in_default_modes(self):
        s = PDHPDLReaction()
        assert 'B' not in s._setup_modes

    def test_setup_b_can_be_enabled_explicitly(self):
        s = PDHPDLReaction(setup_modes=['A', 'B', 'C'])
        assert 'B' in s._setup_modes


class TestTargetComputation:
    """Target price computation for different modes."""

    def test_2r_target_short(self):
        s = PDHPDLReaction(target_mode='2r', require_bias_alignment=False)
        ctx = _session_context(pdh=20050.0, pdl=19900.0)
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        bar0 = _make_bar(high=20060, close=20055)
        s.on_bar(bar0, 0, ctx)
        bar1 = _make_bar(close=20042)
        sig = s.on_bar(bar1, 1, ctx)

        assert sig is not None
        # Stop = 20060 + 5 = 20065, risk = 20065 - 20042 = 23
        # Target = 20042 - 2*23 = 19996
        expected_risk = 20065 - 20042
        expected_target = 20042 - 2 * expected_risk
        assert sig.target_price == expected_target

    def test_2r_target_long(self):
        s = PDHPDLReaction(target_mode='2r', require_bias_alignment=False)
        ctx = _session_context(pdh=20050.0, pdl=19900.0)
        s.on_session_start('2026-03-10', 20000, 19950, 50, ctx)

        bar0 = _make_bar(low=19890, close=19895)
        s.on_bar(bar0, 0, ctx)
        bar1 = _make_bar(close=19910)
        sig = s.on_bar(bar1, 1, ctx)

        assert sig is not None
        # Stop = 19890 - 5 = 19885, risk = 19910 - 19885 = 25
        # Target = 19910 + 2*25 = 19960
        expected_risk = 19910 - 19885
        expected_target = 19910 + 2 * expected_risk
        assert sig.target_price == expected_target


class TestLoaderRegistration:
    """Strategy is registered in the loader."""

    def test_in_registry(self):
        from rockit_core.strategies.loader import get_strategy_class
        cls = get_strategy_class('pdh_pdl_reaction')
        assert cls is not None
        assert cls.__name__ == 'PDHPDLReaction'

    def test_instantiation_via_loader(self):
        from rockit_core.strategies.loader import get_strategy_class
        cls = get_strategy_class('pdh_pdl_reaction')
        instance = cls()
        assert instance.name == "PDH/PDL Reaction"
