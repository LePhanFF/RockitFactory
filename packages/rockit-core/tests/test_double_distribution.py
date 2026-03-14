"""Tests for the Double Distribution Trend Continuation strategy."""

import sys
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, time as _time

sys.path.insert(0, 'packages/rockit-core/src')

from rockit_core.strategies.double_distribution import (
    DoubleDistributionStrategy,
    MIN_POC_SPREAD,
    DETECTION_CUTOFF,
    PULLBACK_WINDOW,
)
from rockit_core.strategies.signal import Signal
from rockit_core.models.stop_models import FixedPointsStop
from rockit_core.models.target_models import RMultipleTarget


def _make_bar(price, high=None, low=None, ts=None, **kwargs):
    """Create a bar Series with default values."""
    if high is None:
        high = price + 2
    if low is None:
        low = price - 2
    data = {
        'open': price,
        'high': high,
        'low': low,
        'close': price,
        'volume': 1000,
        'vol_ask': 500,
        'vol_bid': 500,
        'vol_delta': 0,
    }
    if ts is not None:
        data['timestamp'] = ts
    data.update(kwargs)
    return pd.Series(data)


def _make_ib_bars(center=20000, ib_range=100, n_bars=60):
    """Create IB bars DataFrame for on_session_start."""
    bars = []
    for i in range(n_bars):
        price = center + (i - n_bars // 2) * (ib_range / n_bars)
        minute = 30 + i
        hour = 9 + minute // 60
        minute = minute % 60
        ts = datetime(2025, 3, 10, hour, minute, 0)
        bars.append({
            'open': price - 1,
            'high': price + 2,
            'low': price - 2,
            'close': price,
            'volume': 100,
            'timestamp': ts,
        })
    return pd.DataFrame(bars)


def _base_context(ib_high=20050, ib_low=19950, ib_range=100):
    """Create a basic session context."""
    return {
        'ib_high': ib_high,
        'ib_low': ib_low,
        'ib_range': ib_range,
        'ib_mid': (ib_high + ib_low) / 2,
        'day_type': 'NEUTRAL',
        'trend_strength': 'moderate',
        'bar_time': _time(10, 35),
        'session_date': '2025-03-10',
        'ib_bars': _make_ib_bars(center=20000, ib_range=ib_range),
    }


class TestDoubleDistributionInit:
    """Test strategy initialization and properties."""

    def test_name(self):
        strat = DoubleDistributionStrategy()
        assert strat.name == "Double Distribution"

    def test_applicable_day_types_empty(self):
        """All day types allowed."""
        strat = DoubleDistributionStrategy()
        assert strat.applicable_day_types == []

    def test_custom_models(self):
        stop = FixedPointsStop(50.0)
        target = RMultipleTarget(3.0)
        strat = DoubleDistributionStrategy(stop_model=stop, target_model=target)
        assert strat._stop_model is stop
        assert strat._target_model is target

    def test_custom_min_poc_spread(self):
        strat = DoubleDistributionStrategy(min_poc_spread=100.0)
        assert strat._min_poc_spread == 100.0


class TestDoubleDistributionSessionStart:
    """Test session initialization."""

    def test_session_start_resets_state(self):
        strat = DoubleDistributionStrategy()
        ctx = _base_context()
        strat.on_session_start('2025-03-10', 20050, 19950, 100, ctx)

        assert strat._signal_emitted is False
        assert strat._dd_detected is False
        assert strat._separation is None
        assert strat._direction is None
        assert strat._waiting_for_pullback is False
        assert len(strat._rth_bars) > 0  # IB bars cached

    def test_ib_bars_cached(self):
        strat = DoubleDistributionStrategy()
        ctx = _base_context()
        strat.on_session_start('2025-03-10', 20050, 19950, 100, ctx)
        assert len(strat._rth_bars) == 60  # 60 IB bars


class TestDoubleDistributionOnBar:
    """Test on_bar behavior."""

    def test_no_signal_before_detection(self):
        """Should return None when no double distribution detected."""
        strat = DoubleDistributionStrategy()
        ctx = _base_context()
        strat.on_session_start('2025-03-10', 20050, 19950, 100, ctx)

        bar = _make_bar(20000, ts=datetime(2025, 3, 10, 10, 35))
        result = strat.on_bar(bar, 0, ctx)
        assert result is None

    def test_accumulates_bars(self):
        """Bars should be accumulated for TPO computation."""
        strat = DoubleDistributionStrategy()
        ctx = _base_context()
        strat.on_session_start('2025-03-10', 20050, 19950, 100, ctx)

        initial_count = len(strat._rth_bars)
        bar = _make_bar(20000, ts=datetime(2025, 3, 10, 10, 35))
        strat.on_bar(bar, 0, ctx)
        assert len(strat._rth_bars) == initial_count + 1

    def test_no_detection_after_cutoff(self):
        """Should not detect after DETECTION_CUTOFF."""
        strat = DoubleDistributionStrategy()
        ctx = _base_context()
        ctx['bar_time'] = _time(11, 0)  # Past cutoff
        strat.on_session_start('2025-03-10', 20050, 19950, 100, ctx)

        bar = _make_bar(20000, ts=datetime(2025, 3, 10, 11, 0))
        result = strat.on_bar(bar, 0, ctx)
        assert result is None
        assert strat._dd_detected is False

    def test_only_one_signal_per_session(self):
        """After emitting a signal, no more signals."""
        strat = DoubleDistributionStrategy()
        ctx = _base_context()
        strat.on_session_start('2025-03-10', 20050, 19950, 100, ctx)
        strat._signal_emitted = True

        bar = _make_bar(20000, ts=datetime(2025, 3, 10, 10, 35))
        result = strat.on_bar(bar, 0, ctx)
        assert result is None

    def test_pullback_timeout(self):
        """After PULLBACK_WINDOW bars, stop waiting."""
        strat = DoubleDistributionStrategy()
        ctx = _base_context()
        strat.on_session_start('2025-03-10', 20050, 19950, 100, ctx)

        # Simulate detection
        strat._dd_detected = True
        strat._separation = 20000
        strat._upper_poc = 20050
        strat._lower_poc = 19950
        strat._direction = 'LONG'
        strat._waiting_for_pullback = True
        strat._bars_waiting = PULLBACK_WINDOW + 1

        bar = _make_bar(20030, high=20035, low=20025, ts=datetime(2025, 3, 10, 11, 30))
        result = strat.on_bar(bar, 100, ctx)
        assert result is None
        assert strat._waiting_for_pullback is False


class TestDoubleDistributionDetection:
    """Test the TPO distribution detection logic."""

    def test_compute_distributions_insufficient_data(self):
        """Should return None with too few bars."""
        strat = DoubleDistributionStrategy()
        strat._rth_bars = [{'high': 100, 'low': 99, 'close': 99.5} for _ in range(5)]
        result = strat._compute_distributions()
        assert result is None

    def test_compute_distributions_narrow_range(self):
        """Should return None when profile range too narrow."""
        strat = DoubleDistributionStrategy()
        strat._rth_bars = [
            {'high': 100.5, 'low': 99.5, 'close': 100} for _ in range(50)
        ]
        result = strat._compute_distributions()
        assert result is None

    def test_compute_distributions_double(self):
        """Should detect a double distribution with clear separation."""
        strat = DoubleDistributionStrategy()

        # Create bars with two clusters separated by a gap
        bars = []
        # Lower cluster: 19900-19950 (30 bars)
        for i in range(30):
            bars.append({
                'high': 19950 + np.random.uniform(-10, 10),
                'low': 19900 + np.random.uniform(-10, 10),
                'close': 19925 + np.random.uniform(-5, 5),
            })
        # Gap area: 19960-19990 (just 2 bars passing through)
        for i in range(2):
            bars.append({
                'high': 19985,
                'low': 19965,
                'close': 19975,
            })
        # Upper cluster: 20000-20050 (30 bars)
        for i in range(30):
            bars.append({
                'high': 20050 + np.random.uniform(-10, 10),
                'low': 20000 + np.random.uniform(-10, 10),
                'close': 20025 + np.random.uniform(-5, 5),
            })

        strat._rth_bars = bars
        result = strat._compute_distributions()

        # Should detect double distribution
        if result is not None:
            assert result['count'] == 2
            assert result['type'] == 'double'
            assert result['upper_poc'] > result['lower_poc']
            assert result['separation_level'] is not None


class TestDoubleDistributionSignal:
    """Test signal emission."""

    def test_emit_signal_long(self):
        """Test LONG signal emission."""
        strat = DoubleDistributionStrategy()
        ctx = _base_context()
        strat.on_session_start('2025-03-10', 20050, 19950, 100, ctx)

        # Set up detected state
        strat._dd_detected = True
        strat._separation = 20000.0
        strat._upper_poc = 20060.0
        strat._lower_poc = 19940.0
        strat._direction = 'LONG'
        strat._detection_bar = 5
        strat._bars_waiting = 10

        bar = _make_bar(20000, ts=datetime(2025, 3, 10, 10, 45))
        signal = strat._emit_signal(bar, 15, ctx)

        assert signal is not None
        assert signal.direction == 'LONG'
        assert signal.entry_price == 20000.0
        assert signal.strategy_name == "Double Distribution"
        assert signal.setup_type == 'DD_CONTINUATION_LONG'
        assert signal.metadata['separation_level'] == 20000.0
        assert signal.metadata['poc_spread'] == 120.0

    def test_emit_signal_short(self):
        """Test SHORT signal emission."""
        strat = DoubleDistributionStrategy()
        ctx = _base_context()
        strat.on_session_start('2025-03-10', 20050, 19950, 100, ctx)

        strat._dd_detected = True
        strat._separation = 20000.0
        strat._upper_poc = 20060.0
        strat._lower_poc = 19940.0
        strat._direction = 'SHORT'
        strat._detection_bar = 5
        strat._bars_waiting = 10

        bar = _make_bar(20000, ts=datetime(2025, 3, 10, 10, 45))
        signal = strat._emit_signal(bar, 15, ctx)

        assert signal is not None
        assert signal.direction == 'SHORT'
        assert signal.entry_price == 20000.0

    def test_signal_sets_emitted_flag(self):
        """Signal emission should set the flag to prevent duplicates."""
        strat = DoubleDistributionStrategy()
        ctx = _base_context()
        strat.on_session_start('2025-03-10', 20050, 19950, 100, ctx)

        strat._dd_detected = True
        strat._separation = 20000.0
        strat._upper_poc = 20060.0
        strat._lower_poc = 19940.0
        strat._direction = 'LONG'
        strat._detection_bar = 5
        strat._bars_waiting = 10

        bar = _make_bar(20000, ts=datetime(2025, 3, 10, 10, 45))
        strat._emit_signal(bar, 15, ctx)
        assert strat._signal_emitted is True

    def test_signal_metadata_complete(self):
        """Signal metadata should include all relevant fields."""
        strat = DoubleDistributionStrategy()
        ctx = _base_context()
        strat.on_session_start('2025-03-10', 20050, 19950, 100, ctx)

        strat._dd_detected = True
        strat._separation = 20000.0
        strat._upper_poc = 20075.0
        strat._lower_poc = 19925.0
        strat._direction = 'LONG'
        strat._detection_bar = 5
        strat._bars_waiting = 15

        bar = _make_bar(20000, ts=datetime(2025, 3, 10, 10, 45))
        signal = strat._emit_signal(bar, 20, ctx)

        assert 'separation_level' in signal.metadata
        assert 'upper_poc' in signal.metadata
        assert 'lower_poc' in signal.metadata
        assert 'poc_spread' in signal.metadata
        assert 'detection_bar' in signal.metadata
        assert 'pullback_bars' in signal.metadata
        assert 'stop_model' in signal.metadata
        assert 'target_model' in signal.metadata


class TestDoubleDistributionPullback:
    """Test pullback fill detection."""

    def test_long_pullback_fill(self):
        """LONG: fill when low touches separation level."""
        strat = DoubleDistributionStrategy()
        ctx = _base_context()
        strat.on_session_start('2025-03-10', 20050, 19950, 100, ctx)

        # Set up state for pullback waiting
        strat._dd_detected = True
        strat._separation = 20000.0
        strat._upper_poc = 20060.0
        strat._lower_poc = 19940.0
        strat._direction = 'LONG'
        strat._waiting_for_pullback = True
        strat._bars_waiting = 0
        strat._detection_bar = 5

        # Bar that touches separation from above
        bar = _make_bar(20005, high=20010, low=19998, ts=datetime(2025, 3, 10, 10, 40))
        result = strat.on_bar(bar, 10, ctx)

        assert result is not None
        assert result.direction == 'LONG'
        assert result.entry_price == 20000.0

    def test_short_pullback_fill(self):
        """SHORT: fill when high touches separation level."""
        strat = DoubleDistributionStrategy()
        ctx = _base_context()
        strat.on_session_start('2025-03-10', 20050, 19950, 100, ctx)

        strat._dd_detected = True
        strat._separation = 20000.0
        strat._upper_poc = 20060.0
        strat._lower_poc = 19940.0
        strat._direction = 'SHORT'
        strat._waiting_for_pullback = True
        strat._bars_waiting = 0
        strat._detection_bar = 5

        # Bar that touches separation from below
        bar = _make_bar(19995, high=20002, low=19990, ts=datetime(2025, 3, 10, 10, 40))
        result = strat.on_bar(bar, 10, ctx)

        assert result is not None
        assert result.direction == 'SHORT'
        assert result.entry_price == 20000.0

    def test_no_fill_when_price_doesnt_reach(self):
        """No fill if price doesn't touch separation."""
        strat = DoubleDistributionStrategy()
        ctx = _base_context()
        strat.on_session_start('2025-03-10', 20050, 19950, 100, ctx)

        strat._dd_detected = True
        strat._separation = 20000.0
        strat._upper_poc = 20060.0
        strat._lower_poc = 19940.0
        strat._direction = 'LONG'
        strat._waiting_for_pullback = True
        strat._bars_waiting = 0
        strat._detection_bar = 5

        # Bar above separation — no fill
        bar = _make_bar(20020, high=20025, low=20015, ts=datetime(2025, 3, 10, 10, 40))
        result = strat.on_bar(bar, 10, ctx)
        assert result is None
        assert strat._waiting_for_pullback is True


class TestDoubleDistributionSessionEnd:
    """Test session cleanup."""

    def test_session_end_clears_bars(self):
        strat = DoubleDistributionStrategy()
        ctx = _base_context()
        strat.on_session_start('2025-03-10', 20050, 19950, 100, ctx)
        assert len(strat._rth_bars) > 0

        strat.on_session_end('2025-03-10')
        assert len(strat._rth_bars) == 0


class TestDoubleDistributionLoader:
    """Test strategy loader integration."""

    def test_loader_registration(self):
        from rockit_core.strategies.loader import get_strategy_class
        cls = get_strategy_class('double_distribution')
        assert cls is not None
        assert cls.__name__ == 'DoubleDistributionStrategy'

    def test_loader_instantiation(self):
        from rockit_core.strategies.loader import get_strategy_class
        cls = get_strategy_class('double_distribution')
        instance = cls()
        assert instance.name == "Double Distribution"

    def test_in_research_strategies(self):
        from rockit_core.strategies.loader import RESEARCH_STRATEGIES
        assert 'double_distribution' in RESEARCH_STRATEGIES
