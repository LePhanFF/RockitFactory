"""Tests for 20P IB Extension strategy — 3x5-min acceptance model."""

from datetime import time as _time

import pandas as pd
import pytest

from rockit_core.strategies.twenty_percent_rule import (
    TwentyPercentRule,
    ACCEPT_5M_BARS,
    ATR_STOP_MULT,
    TARGET_R_MULTIPLE,
    _compute_atr14,
)
from rockit_core.models.stop_models import ATRStopModel, FixedPointsStop
from rockit_core.models.target_models import RMultipleTarget


@pytest.fixture
def strategy():
    return TwentyPercentRule()


@pytest.fixture
def session_context():
    """Default context: session opens above prior VAH → LONG allowed."""
    return {
        'day_type': 'neutral',
        'trend_strength': 'moderate',
        'bar_time': _time(11, 0),
        'atr14': 16.0,
        'prior_va_vah': 19990.0,   # open (19999) > VAH → LONG allowed
        'prior_va_val': 19980.0,
    }


@pytest.fixture
def short_session_context():
    """Context where session opens below prior VAL → SHORT allowed."""
    return {
        'day_type': 'neutral',
        'trend_strength': 'moderate',
        'bar_time': _time(11, 0),
        'atr14': 16.0,
        'prior_va_vah': 20010.0,   # open (19999) < VAL → SHORT allowed
        'prior_va_val': 20005.0,
    }


def make_bar(close, high=None, low=None, timestamp=None):
    if high is None:
        high = close + 3
    if low is None:
        low = close - 3
    data = {
        'close': close,
        'high': high,
        'low': low,
        'open': close,
        'volume': 100,
    }
    if timestamp is not None:
        data['timestamp'] = timestamp
    return pd.Series(data)


def make_ib_bars(n=60, base=20000.0):
    """Generate n IB bars for ATR computation."""
    rows = []
    for i in range(n):
        rows.append({
            'open': base - 1,
            'high': base + 5,
            'low': base - 5,
            'close': base,
            'volume': 100,
        })
    return pd.DataFrame(rows)


# --- Basic Properties ---

class TestProperties:
    def test_name(self, strategy):
        assert strategy.name == "20P IB Extension"

    def test_applicable_day_types_empty(self, strategy):
        assert strategy.applicable_day_types == []


# --- Session Initialization ---

class TestSessionStart:
    def test_session_start_sets_ib(self, strategy, session_context):
        ib_bars = make_ib_bars()
        session_context['ib_bars'] = ib_bars
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)
        assert strategy._ib_high == 20050
        assert strategy._ib_low == 19950
        assert strategy._ib_range == 100

    def test_session_start_computes_atr(self, strategy, session_context):
        ib_bars = make_ib_bars()
        session_context['ib_bars'] = ib_bars
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)
        assert strategy._atr14 > 0

    def test_session_start_uses_context_atr_without_ib_bars(self, strategy, session_context):
        session_context['atr14'] = 25.0
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)
        assert strategy._atr14 == 25.0

    def test_session_start_resets_state(self, strategy, session_context):
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)
        assert strategy._triggered is False
        assert strategy._entry_count == 0
        assert strategy._consec_above == 0
        assert strategy._consec_below == 0


# --- 5-Min Bar End Detection ---

class TestFiveMinBarEnd:
    def test_no_signal_on_non_5m_bars(self, strategy, session_context):
        """Should only check at 5-min bar boundaries."""
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)

        # Bars 0-3 are not 5-min ends (bar 4 is first 5-min end)
        for i in range(4):
            bar = make_bar(20060)  # Above IBH
            sig = strategy.on_bar(bar, i, session_context)
            assert sig is None

    def test_signal_checks_at_5m_boundary(self, strategy, session_context):
        """Bar index 4 is the first 5-min end: (4+1)%5 == 0."""
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)

        # Bar 4 is a 5-min end, but only 1 consecutive close
        bar = make_bar(20060)  # Above IBH=20050
        sig = strategy.on_bar(bar, 4, session_context)
        assert sig is None  # Need 3 consecutive


# --- Acceptance Detection ---

class TestAcceptance:
    def test_long_acceptance_after_3_consecutive(self, strategy, session_context):
        """3 consecutive 5-min closes above IBH should trigger LONG."""
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)

        # 3 consecutive 5-min bars above IBH (bar indices 4, 9, 14)
        sig = strategy.on_bar(make_bar(20060), 4, session_context)
        assert sig is None  # 1 of 3
        sig = strategy.on_bar(make_bar(20065), 9, session_context)
        assert sig is None  # 2 of 3
        sig = strategy.on_bar(make_bar(20070), 14, session_context)
        assert sig is not None  # 3 of 3 → LONG
        assert sig.direction == 'LONG'

    def test_short_acceptance_after_3_consecutive(self, strategy, short_session_context):
        """3 consecutive 5-min closes below IBL should trigger SHORT."""
        short_session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, short_session_context)

        # 3 consecutive 5-min bars below IBL (bar indices 4, 9, 14)
        sig = strategy.on_bar(make_bar(19940), 4, short_session_context)
        assert sig is None
        sig = strategy.on_bar(make_bar(19935), 9, short_session_context)
        assert sig is None
        sig = strategy.on_bar(make_bar(19930), 14, short_session_context)
        assert sig is not None
        assert sig.direction == 'SHORT'

    def test_reset_on_close_inside_ib(self, strategy, session_context):
        """Consecutive counter resets if a bar closes back inside IB."""
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)

        # 2 closes above IBH
        strategy.on_bar(make_bar(20060), 4, session_context)
        strategy.on_bar(make_bar(20065), 9, session_context)

        # Close inside IB → reset
        strategy.on_bar(make_bar(20000), 14, session_context)

        # Restart: need 3 more
        strategy.on_bar(make_bar(20060), 19, session_context)
        strategy.on_bar(make_bar(20065), 24, session_context)
        sig = strategy.on_bar(make_bar(20070), 29, session_context)
        assert sig is not None  # Now 3 consecutive → LONG

    def test_direction_switch_resets_counter(self, strategy):
        """Closing below IBL after closing above IBH resets the above counter."""
        # Need LONG allowed to test above-IBH counting, direction gate blocks SHORT
        ctx = {
            'day_type': 'neutral', 'trend_strength': 'moderate',
            'bar_time': _time(11, 0), 'atr14': 16.0,
            'prior_va_vah': 19990.0, 'prior_va_val': 19980.0,
            'ib_bars': make_ib_bars(),
        }
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, ctx)

        # 2 closes above IBH
        strategy.on_bar(make_bar(20060), 4, ctx)
        strategy.on_bar(make_bar(20065), 9, ctx)
        assert strategy._consec_above == 2

        # Close below IBL → above resets, below starts
        strategy.on_bar(make_bar(19940), 14, ctx)
        assert strategy._consec_above == 0
        assert strategy._consec_below == 1

    def test_no_signal_with_only_2_consecutive(self, strategy, session_context):
        """2 consecutive is not enough."""
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)

        sig = strategy.on_bar(make_bar(20060), 4, session_context)
        assert sig is None
        sig = strategy.on_bar(make_bar(20065), 9, session_context)
        assert sig is None


# --- Stop and Target Computation ---

class TestStopTarget:
    def test_long_stop_target(self, strategy, session_context):
        """LONG: stop = entry - 2*ATR, target = entry + 2*risk."""
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)
        atr = strategy._atr14

        # Trigger acceptance
        strategy.on_bar(make_bar(20060), 4, session_context)
        strategy.on_bar(make_bar(20065), 9, session_context)
        sig = strategy.on_bar(make_bar(20070), 14, session_context)

        assert sig is not None
        risk = ATR_STOP_MULT * atr
        assert sig.entry_price == 20070
        assert sig.stop_price == pytest.approx(20070 - risk, abs=0.01)
        assert sig.target_price == pytest.approx(20070 + TARGET_R_MULTIPLE * risk, abs=0.01)

    def test_short_stop_target(self, strategy, short_session_context):
        """SHORT: stop = entry + 2*ATR, target = entry - 2*risk."""
        short_session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, short_session_context)
        atr = strategy._atr14

        strategy.on_bar(make_bar(19940), 4, short_session_context)
        strategy.on_bar(make_bar(19935), 9, short_session_context)
        sig = strategy.on_bar(make_bar(19930), 14, short_session_context)

        assert sig is not None
        risk = ATR_STOP_MULT * atr
        assert sig.entry_price == 19930
        assert sig.stop_price == pytest.approx(19930 + risk, abs=0.01)
        assert sig.target_price == pytest.approx(19930 - TARGET_R_MULTIPLE * risk, abs=0.01)


# --- Filters Removed (Regression Tests) ---

class TestNoExtraFilters:
    """Verify the removed filters no longer block signals."""

    def test_fires_without_trend_strength(self, strategy, session_context):
        """Should fire even with weak trend strength (filter was removed)."""
        session_context['ib_bars'] = make_ib_bars()
        session_context['trend_strength'] = 'weak'
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)

        strategy.on_bar(make_bar(20060), 4, session_context)
        strategy.on_bar(make_bar(20065), 9, session_context)
        sig = strategy.on_bar(make_bar(20070), 14, session_context)
        assert sig is not None  # Weak trend should NOT block

    def test_fires_without_delta_confirmation(self, strategy, session_context):
        """Should fire even without delta confirmation (filter was removed)."""
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)

        # LONG signal — delta is negative (would have blocked before)
        bar = make_bar(20060)
        bar['delta'] = -100
        strategy.on_bar(bar, 4, session_context)

        bar = make_bar(20065)
        bar['delta'] = -50
        strategy.on_bar(bar, 9, session_context)

        bar = make_bar(20070)
        bar['delta'] = -200
        sig = strategy.on_bar(bar, 14, session_context)
        assert sig is not None  # Negative delta should NOT block LONG

    def test_fires_with_narrow_ib(self, strategy, session_context):
        """Should fire even with narrow IB range (MIN_IB_RANGE filter was removed)."""
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20010, 19990, 20, session_context)  # 20pt IB

        strategy.on_bar(make_bar(20015), 4, session_context)
        strategy.on_bar(make_bar(20020), 9, session_context)
        sig = strategy.on_bar(make_bar(20025), 14, session_context)
        assert sig is not None  # Narrow IB should NOT block

    def test_fires_without_extension_threshold(self, strategy, session_context):
        """Should fire when price is just 1pt beyond IBH (no 20% extension needed)."""
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)

        # Close just 1pt beyond IBH — previously would fail 20% extension check
        strategy.on_bar(make_bar(20051), 4, session_context)
        strategy.on_bar(make_bar(20052), 9, session_context)
        sig = strategy.on_bar(make_bar(20053), 14, session_context)
        assert sig is not None  # No extension threshold needed


# --- Max Entries Per Session ---

class TestMaxEntries:
    def test_only_one_entry_per_session(self, strategy, session_context):
        """Max 1 entry per session."""
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)

        # First signal fires
        strategy.on_bar(make_bar(20060), 4, session_context)
        strategy.on_bar(make_bar(20065), 9, session_context)
        sig1 = strategy.on_bar(make_bar(20070), 14, session_context)
        assert sig1 is not None

        # Second signal blocked — but actually _triggered prevents any more bars
        sig2 = strategy.on_bar(make_bar(20080), 19, session_context)
        assert sig2 is None


# --- Signal Metadata ---

class TestSignalMetadata:
    def test_signal_has_correct_metadata(self, strategy, session_context):
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)

        strategy.on_bar(make_bar(20060), 4, session_context)
        strategy.on_bar(make_bar(20065), 9, session_context)
        sig = strategy.on_bar(make_bar(20070), 14, session_context)

        assert sig.strategy_name == "20P IB Extension"
        assert sig.setup_type == "20P_IB_EXT_LONG"
        assert 'ib_range' in sig.metadata
        assert 'atr14' in sig.metadata
        assert 'risk_pts' in sig.metadata
        assert sig.metadata['acceptance_bars'] == 3

    def test_short_signal_setup_type(self, strategy, short_session_context):
        short_session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, short_session_context)

        strategy.on_bar(make_bar(19940), 4, short_session_context)
        strategy.on_bar(make_bar(19935), 9, short_session_context)
        sig = strategy.on_bar(make_bar(19930), 14, short_session_context)

        assert sig.setup_type == "20P_IB_EXT_SHORT"


# --- ATR Computation ---

class TestATRComputation:
    def test_atr14_positive(self):
        df = make_ib_bars(30, 20000.0)
        atr = _compute_atr14(df)
        assert atr > 0

    def test_atr14_with_few_bars(self):
        df = make_ib_bars(2, 20000.0)
        atr = _compute_atr14(df)
        assert atr > 0

    def test_atr14_with_empty_df(self):
        df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        atr = _compute_atr14(df)
        assert atr == 20.0  # Default fallback


# --- Prior VA Prerequisite ---

class TestPriorVAPrerequisite:
    def test_no_signal_when_open_inside_va(self, strategy):
        """Session opens inside prior VA → no trades allowed."""
        ctx = {
            'day_type': 'neutral', 'trend_strength': 'moderate',
            'bar_time': _time(11, 0), 'atr14': 16.0,
            'prior_va_vah': 20010.0,  # open (19999) is inside VA
            'prior_va_val': 19990.0,
            'ib_bars': make_ib_bars(),
        }
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, ctx)
        assert strategy._allowed_direction is None

        # 3 consecutive above IBH → still blocked
        strategy.on_bar(make_bar(20060), 4, ctx)
        strategy.on_bar(make_bar(20065), 9, ctx)
        sig = strategy.on_bar(make_bar(20070), 14, ctx)
        assert sig is None

    def test_no_signal_without_prior_va(self, strategy):
        """Missing prior VA data → no trades."""
        ctx = {
            'day_type': 'neutral', 'trend_strength': 'moderate',
            'bar_time': _time(11, 0), 'atr14': 16.0,
            'ib_bars': make_ib_bars(),
        }
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, ctx)
        assert strategy._allowed_direction is None

    def test_long_blocked_when_short_allowed(self, strategy, short_session_context):
        """Open below VAL → SHORT only. LONG acceptance should be blocked."""
        short_session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, short_session_context)
        assert strategy._allowed_direction == 'SHORT'

        # 3 consecutive above IBH → LONG direction blocked
        strategy.on_bar(make_bar(20060), 4, short_session_context)
        strategy.on_bar(make_bar(20065), 9, short_session_context)
        sig = strategy.on_bar(make_bar(20070), 14, short_session_context)
        assert sig is None


# --- 13:00 Entry Cutoff ---

class TestEntryCutoff:
    def test_no_entry_after_1300(self, strategy, session_context):
        """13:00 ET cutoff for new entries."""
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)

        session_context['bar_time'] = _time(13, 1)
        strategy.on_bar(make_bar(20060), 4, session_context)
        strategy.on_bar(make_bar(20065), 9, session_context)
        sig = strategy.on_bar(make_bar(20070), 14, session_context)
        assert sig is None

    def test_entry_before_1300(self, strategy, session_context):
        """Entries allowed before 13:00."""
        session_context['ib_bars'] = make_ib_bars()
        session_context['bar_time'] = _time(12, 0)
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)

        strategy.on_bar(make_bar(20060), 4, session_context)
        strategy.on_bar(make_bar(20065), 9, session_context)
        sig = strategy.on_bar(make_bar(20070), 14, session_context)
        assert sig is not None


# --- Pluggable Model Tests ---

class TestPluggableModels:
    def test_default_models_produce_same_output(self, session_context):
        """Default ATRStopModel(2.0) + RMultipleTarget(2.0) matches hardcoded logic."""
        strategy = TwentyPercentRule()  # No custom models
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)
        atr = strategy._atr14

        strategy.on_bar(make_bar(20060), 4, session_context)
        strategy.on_bar(make_bar(20065), 9, session_context)
        sig = strategy.on_bar(make_bar(20070), 14, session_context)

        assert sig is not None
        risk = ATR_STOP_MULT * atr
        assert sig.stop_price == pytest.approx(20070 - risk, abs=0.01)
        assert sig.target_price == pytest.approx(20070 + TARGET_R_MULTIPLE * risk, abs=0.01)

    def test_custom_stop_model_changes_stop(self, session_context):
        """Injecting FixedPointsStop produces a different stop price."""
        strategy = TwentyPercentRule(stop_model=FixedPointsStop(25.0))
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)

        strategy.on_bar(make_bar(20060), 4, session_context)
        strategy.on_bar(make_bar(20065), 9, session_context)
        sig = strategy.on_bar(make_bar(20070), 14, session_context)

        assert sig is not None
        # FixedPointsStop(25) → stop = 20070 - 25 = 20045
        assert sig.stop_price == pytest.approx(20045, abs=0.01)
        # Target = 2R = 20070 + 2*25 = 20120
        assert sig.target_price == pytest.approx(20120, abs=0.01)

    def test_custom_target_model_changes_target(self, session_context):
        """Injecting RMultipleTarget(3.0) produces a different target."""
        strategy = TwentyPercentRule(target_model=RMultipleTarget(3.0))
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)
        atr = strategy._atr14
        risk = ATR_STOP_MULT * atr

        strategy.on_bar(make_bar(20060), 4, session_context)
        strategy.on_bar(make_bar(20065), 9, session_context)
        sig = strategy.on_bar(make_bar(20070), 14, session_context)

        assert sig is not None
        # 3R target instead of 2R
        assert sig.target_price == pytest.approx(20070 + 3.0 * risk, abs=0.01)

    def test_metadata_includes_model_names(self, session_context):
        """Signal metadata should include stop_model and target_model names."""
        strategy = TwentyPercentRule()
        session_context['ib_bars'] = make_ib_bars()
        strategy.on_session_start('2025-01-15', 20050, 19950, 100, session_context)

        strategy.on_bar(make_bar(20060), 4, session_context)
        strategy.on_bar(make_bar(20065), 9, session_context)
        sig = strategy.on_bar(make_bar(20070), 14, session_context)

        assert sig is not None
        assert 'stop_model' in sig.metadata
        assert 'target_model' in sig.metadata
        assert sig.metadata['stop_model'] == '2.0_atr'
        assert sig.metadata['target_model'] == '2r'
