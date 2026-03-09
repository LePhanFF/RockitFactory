"""Tests for B-Day IBL Fade strategy — 30-min acceptance model (Config H)."""

from datetime import datetime, time as _time

import pandas as pd
import pytest

from rockit_core.strategies.b_day import BDayStrategy
from rockit_core.config.constants import BDAY_ACCEPTANCE_BARS, BDAY_TOUCH_TOLERANCE


@pytest.fixture
def strategy():
    return BDayStrategy()


@pytest.fixture
def session_context():
    """Standard session context for a b_day session."""
    return {
        'day_type': 'b_day',
        'trend_strength': 'weak',
        'bar_time': _time(11, 0),
    }


def make_bar(close, low=None, high=None, vwap=None, timestamp=None):
    """Helper to create a bar Series."""
    if low is None:
        low = close - 5
    if high is None:
        high = close + 5
    data = {
        'close': close,
        'low': low,
        'high': high,
        'open': close,
        'volume': 100,
    }
    if vwap is not None:
        data['vwap'] = vwap
    if timestamp is not None:
        data['timestamp'] = timestamp
    return pd.Series(data)


# --- Day Type Tests ---

class TestApplicableDayTypes:
    def test_all_day_types_allowed(self, strategy):
        """Study: day type is unpredictable at IB close — all types allowed."""
        assert strategy.applicable_day_types == []

    def test_accepts_trend_up(self, strategy):
        """No day type filter — trend_up sessions qualify for acceptance model."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})
        ctx = {'day_type': 'trend_up', 'bar_time': _time(11, 0)}

        # Touch IBL
        touch_bar = make_bar(14910, low=14898, timestamp=datetime.now())
        strategy.on_bar(touch_bar, 0, ctx)

        # Acceptance at bar 30
        accept_bar = make_bar(14920, low=14915, timestamp=datetime.now())
        signal = strategy.on_bar(accept_bar, BDAY_ACCEPTANCE_BARS, ctx)
        assert signal is not None

    def test_accepts_neutral(self, strategy, session_context):
        """Neutral day type should allow entry through acceptance model."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})
        session_context['day_type'] = 'neutral'

        # Touch IBL
        touch_bar = make_bar(14910, low=14898, timestamp=datetime.now())
        strategy.on_bar(touch_bar, 0, session_context)

        # Wait 30 bars, then check acceptance
        acceptance_bar = make_bar(14920, low=14915, timestamp=datetime.now())
        signal = strategy.on_bar(acceptance_bar, BDAY_ACCEPTANCE_BARS, session_context)
        assert signal is not None
        assert signal.day_type == 'neutral'


# --- 30-Bar Acceptance Tests ---

class TestAcceptanceModel:
    def test_no_entry_on_touch_bar(self, strategy, session_context):
        """Must NOT enter on the bar that touches IBL."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})
        touch_bar = make_bar(14910, low=14898, timestamp=datetime.now())
        signal = strategy.on_bar(touch_bar, 0, session_context)
        assert signal is None

    def test_no_entry_before_30_bars(self, strategy, session_context):
        """Must NOT enter during the 30-bar waiting period."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})

        # Touch
        touch_bar = make_bar(14910, low=14898, timestamp=datetime.now())
        strategy.on_bar(touch_bar, 0, session_context)

        # Bar 15 — still waiting
        mid_bar = make_bar(14920, low=14915, timestamp=datetime.now())
        signal = strategy.on_bar(mid_bar, 15, session_context)
        assert signal is None

    def test_entry_at_bar_30_on_acceptance(self, strategy, session_context):
        """At bar 30, if close > IBL, emit LONG signal."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})

        # Touch at bar 5
        touch_bar = make_bar(14910, low=14898, timestamp=datetime.now())
        strategy.on_bar(touch_bar, 5, session_context)

        # Bar 35 (5 + 30) = acceptance check
        acceptance_bar = make_bar(14920, low=14915, timestamp=datetime.now())
        signal = strategy.on_bar(acceptance_bar, 35, session_context)
        assert signal is not None
        assert signal.direction == 'LONG'
        assert signal.setup_type == 'B_DAY_IBL_FADE'
        assert signal.entry_price == 14920

    def test_no_entry_on_failed_acceptance(self, strategy, session_context):
        """At bar 30, if close <= IBL, no signal (failed acceptance)."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})

        # Touch
        touch_bar = make_bar(14910, low=14895, timestamp=datetime.now())
        strategy.on_bar(touch_bar, 0, session_context)

        # Bar 30: close at or below IBL
        fail_bar = make_bar(14890, low=14880, timestamp=datetime.now())
        signal = strategy.on_bar(fail_bar, BDAY_ACCEPTANCE_BARS, session_context)
        assert signal is None

    def test_no_second_trade_after_failed_acceptance(self, strategy, session_context):
        """After failed acceptance at bar 30, first-touch is consumed — no more trades."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})

        # Touch #1
        touch_bar = make_bar(14910, low=14895, timestamp=datetime.now())
        strategy.on_bar(touch_bar, 0, session_context)

        # Fail acceptance at bar 30
        fail_bar = make_bar(14890, low=14880, timestamp=datetime.now())
        strategy.on_bar(fail_bar, BDAY_ACCEPTANCE_BARS, session_context)

        # Second touch attempt — should be ignored (first touch consumed)
        touch2_bar = make_bar(14905, low=14898, timestamp=datetime.now())
        strategy.on_bar(touch2_bar, 50, session_context)
        assert strategy._touch_bar_index is None  # Not tracking new touch


# --- First-Touch Filter Tests ---

class TestFirstTouchFilter:
    def test_only_first_touch_triggers(self, strategy, session_context):
        """After first touch is recorded, subsequent touches are ignored."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})

        # First touch
        bar1 = make_bar(14910, low=14898, timestamp=datetime.now())
        strategy.on_bar(bar1, 0, session_context)
        assert strategy._first_touch_taken is True
        assert strategy._touch_bar_index == 0

        # Acceptance → trade
        bar2 = make_bar(14920, low=14910, timestamp=datetime.now())
        signal = strategy.on_bar(bar2, BDAY_ACCEPTANCE_BARS, session_context)
        assert signal is not None

        # Second touch — should not start new tracking
        bar3 = make_bar(14905, low=14895, timestamp=datetime.now())
        signal2 = strategy.on_bar(bar3, 50, session_context)
        assert signal2 is None

    def test_max_one_trade_per_session(self, strategy, session_context):
        """Only one LONG per session, enforced by _val_fade_taken."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})

        # Touch + acceptance → first trade
        touch = make_bar(14910, low=14898, timestamp=datetime.now())
        strategy.on_bar(touch, 0, session_context)
        accept = make_bar(14920, low=14910, timestamp=datetime.now())
        signal = strategy.on_bar(accept, BDAY_ACCEPTANCE_BARS, session_context)
        assert signal is not None

        # Any further bar should return None
        later = make_bar(14905, low=14895, timestamp=datetime.now())
        assert strategy.on_bar(later, 60, session_context) is None


# --- VWAP Alignment Tests ---

class TestVWAPAlignment:
    def test_vwap_above_ib_mid_gives_high_confidence(self, strategy, session_context):
        """VWAP > IB mid at touch time → confidence = 'high'."""
        ib_mid = (15000 + 14900) / 2  # 14950
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})

        # Touch with VWAP above IB mid
        touch = make_bar(14910, low=14898, vwap=14960, timestamp=datetime.now())
        strategy.on_bar(touch, 0, session_context)

        # Accept
        accept = make_bar(14920, low=14910, timestamp=datetime.now())
        signal = strategy.on_bar(accept, BDAY_ACCEPTANCE_BARS, session_context)
        assert signal is not None
        assert signal.confidence == 'high'

    def test_vwap_below_ib_mid_gives_medium_confidence(self, strategy, session_context):
        """VWAP <= IB mid at touch time → confidence = 'medium'."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})

        # Touch with VWAP below IB mid (14950)
        touch = make_bar(14910, low=14898, vwap=14940, timestamp=datetime.now())
        strategy.on_bar(touch, 0, session_context)

        # Accept
        accept = make_bar(14920, low=14910, timestamp=datetime.now())
        signal = strategy.on_bar(accept, BDAY_ACCEPTANCE_BARS, session_context)
        assert signal is not None
        assert signal.confidence == 'medium'

    def test_no_vwap_gives_medium_confidence(self, strategy, session_context):
        """Missing VWAP data → confidence = 'medium' (conservative default)."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})

        # Touch without VWAP
        touch = make_bar(14910, low=14898, timestamp=datetime.now())
        strategy.on_bar(touch, 0, session_context)

        # Accept
        accept = make_bar(14920, low=14910, timestamp=datetime.now())
        signal = strategy.on_bar(accept, BDAY_ACCEPTANCE_BARS, session_context)
        assert signal is not None
        assert signal.confidence == 'medium'


# --- Touch Tolerance Tests ---

class TestTouchTolerance:
    def test_touch_within_tolerance(self, strategy, session_context):
        """Bar low within BDAY_TOUCH_TOLERANCE of IBL triggers touch."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})

        # Low = 14904 → within 5 pts of IBL (14900)
        bar = make_bar(14910, low=14900 + BDAY_TOUCH_TOLERANCE, timestamp=datetime.now())
        strategy.on_bar(bar, 0, session_context)
        assert strategy._first_touch_taken is True

    def test_no_touch_outside_tolerance(self, strategy, session_context):
        """Bar low more than BDAY_TOUCH_TOLERANCE above IBL → no touch."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})

        bar = make_bar(14920, low=14900 + BDAY_TOUCH_TOLERANCE + 1, timestamp=datetime.now())
        strategy.on_bar(bar, 0, session_context)
        assert strategy._first_touch_taken is False


# --- Stop/Target/R:R Tests ---

class TestStopTargetRR:
    def test_stop_and_target_prices(self, strategy, session_context):
        """Stop = IBL - 10% IB range; Target = IB midpoint."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})

        touch = make_bar(14910, low=14898, timestamp=datetime.now())
        strategy.on_bar(touch, 0, session_context)

        accept = make_bar(14920, low=14910, timestamp=datetime.now())
        signal = strategy.on_bar(accept, BDAY_ACCEPTANCE_BARS, session_context)

        assert signal.stop_price == 14900 - (100 * 0.1)  # 14890
        assert signal.target_price == 14950  # IB midpoint

    def test_rr_filter_rejects_bad_trade(self, strategy, session_context):
        """R:R > 2.5 → skip. Entry near target = tiny reward, big risk."""
        # IB: 15000-14900, mid=14950, stop=14890
        # Entry at 14945 → risk=55, reward=5 → R:R=11 → SKIP
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})

        touch = make_bar(14910, low=14898, timestamp=datetime.now())
        strategy.on_bar(touch, 0, session_context)

        # Entry near target
        accept = make_bar(14945, low=14940, timestamp=datetime.now())
        signal = strategy.on_bar(accept, BDAY_ACCEPTANCE_BARS, session_context)
        assert signal is None

    def test_rejects_close_above_ibh(self, strategy, session_context):
        """Study: acceptance = close INSIDE IB (> IBL AND < IBH).
        If price ran above IBH, it's a trend day — not acceptance."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})

        touch = make_bar(14910, low=14898, timestamp=datetime.now())
        strategy.on_bar(touch, 0, session_context)

        # Price above IBH at bar 30 — NOT inside IB, failed acceptance
        accept = make_bar(15010, low=15000, timestamp=datetime.now())
        signal = strategy.on_bar(accept, BDAY_ACCEPTANCE_BARS, session_context)
        assert signal is None


# --- Time Gate Tests ---

class TestTimeGate:
    def test_no_entry_after_1400(self, strategy, session_context):
        """Time gate: no entries after 14:00."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})
        session_context['bar_time'] = _time(14, 1)

        touch = make_bar(14910, low=14898, timestamp=datetime.now())
        signal = strategy.on_bar(touch, 0, session_context)
        assert signal is None

    def test_entry_before_1400(self, strategy, session_context):
        """Entry allowed before 14:00."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})
        session_context['bar_time'] = _time(13, 30)

        touch = make_bar(14910, low=14898, timestamp=datetime.now())
        strategy.on_bar(touch, 0, session_context)

        accept = make_bar(14920, low=14910, timestamp=datetime.now())
        signal = strategy.on_bar(accept, BDAY_ACCEPTANCE_BARS, session_context)
        assert signal is not None


# --- Session Reset Tests ---

class TestSessionReset:
    def test_state_resets_on_new_session(self, strategy, session_context):
        """All tracking state resets when a new session starts."""
        strategy.on_session_start('2025-01-01', 15000, 14900, 100, {})

        # Take a trade
        touch = make_bar(14910, low=14898, timestamp=datetime.now())
        strategy.on_bar(touch, 0, session_context)
        accept = make_bar(14920, low=14910, timestamp=datetime.now())
        strategy.on_bar(accept, BDAY_ACCEPTANCE_BARS, session_context)
        assert strategy._val_fade_taken is True

        # New session
        strategy.on_session_start('2025-01-02', 15100, 15000, 100, {})
        assert strategy._val_fade_taken is False
        assert strategy._first_touch_taken is False
        assert strategy._touch_bar_index is None
        assert strategy._vwap_aligned is False
