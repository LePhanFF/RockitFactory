"""Tests for Trend Day Bull and Trend Day Bear strategies (re-optimized)."""
import pandas as pd
import numpy as np
import pytest

from rockit_core.strategies.trend_bull import TrendDayBull
from rockit_core.strategies.trend_bear import TrendDayBear
from rockit_core.strategies.signal import Signal


def _make_bar(close, high=None, low=None, delta=100, vwap=None,
              ema20=None, ema20_15m=None, ema50_15m=None, adx14_15m=30.0,
              timestamp='2025-06-10 11:00:00'):
    """Helper to create a bar Series."""
    if high is None:
        high = close + 2
    if low is None:
        low = close - 2
    return pd.Series({
        'open': close - 1,
        'high': high,
        'low': low,
        'close': close,
        'volume': 1000,
        'delta': delta,
        'vwap': vwap if vwap is not None else close - 10,
        'ema20': ema20 if ema20 is not None else close - 5,
        'ema20_15m': ema20_15m if ema20_15m is not None else close - 15,
        'ema50_15m': ema50_15m if ema50_15m is not None else close - 25,
        'adx14_15m': adx14_15m,
        'timestamp': pd.Timestamp(timestamp),
    })


def _make_ctx(**overrides):
    """Helper to create session context."""
    ctx = {
        'day_type': 'neutral',
        'trend_strength': 'moderate',
        'bar_time': pd.Timestamp('2025-06-10 11:00:00').time(),
    }
    ctx.update(overrides)
    return ctx


# ═══════════════════════════════════════════════════════════════
# TREND DAY BULL TESTS
# ═══════════════════════════════════════════════════════════════

class TestTrendDayBull:
    def setup_method(self):
        self.strategy = TrendDayBull()

    def test_name(self):
        assert self.strategy.name == "Trend Day Bull"

    def test_applicable_day_types_empty(self):
        """All day types allowed — alignment is the filter."""
        assert self.strategy.applicable_day_types == []

    def test_no_signal_before_acceptance(self):
        """Should not fire until 2 bars close above IBH."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        bar = _make_bar(19950)  # Below IBH
        result = self.strategy.on_bar(bar, 0, _make_ctx())
        assert result is None

    def test_acceptance_requires_two_bars(self):
        """Acceptance needs 2 consecutive bars above IBH."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        # Bar 1: above IBH
        bar1 = _make_bar(20010)
        self.strategy.on_bar(bar1, 0, _make_ctx())
        assert not self.strategy._acceptance_confirmed
        # Bar 2: above IBH again
        bar2 = _make_bar(20015)
        self.strategy.on_bar(bar2, 1, _make_ctx())
        assert self.strategy._acceptance_confirmed

    def test_acceptance_resets_on_pullback(self):
        """Counter bar resets acceptance counter."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        bar1 = _make_bar(20010)
        self.strategy.on_bar(bar1, 0, _make_ctx())
        bar2 = _make_bar(19995)  # Back below IBH
        self.strategy.on_bar(bar2, 1, _make_ctx())
        assert self.strategy._consecutive_above == 0

    def test_signal_with_all_conditions_met(self):
        """Full signal: accepted + 15m bull align + ADX>=25 + delta>0 + EMA pullback."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        # Acceptance phase
        self.strategy.on_bar(_make_bar(20010), 0, _make_ctx())
        self.strategy.on_bar(_make_bar(20015), 1, _make_ctx())
        # Entry bar: price=20020, ema20_15m=20010, ema50_15m=19990 (bull align)
        # VWAP far away (19900) so VWAP_PULLBACK doesn't fire
        # ema20(1m)=20015 (close to price, within 0.2x IB), delta>0
        bar = _make_bar(
            20020, delta=200, vwap=19900, ema20=20015,
            ema20_15m=20010, ema50_15m=19990, adx14_15m=30.0,
            timestamp='2025-06-10 11:00:00',
        )
        ctx = _make_ctx()
        signal = self.strategy.on_bar(bar, 2, ctx)
        assert signal is not None
        assert signal.direction == 'LONG'
        assert signal.entry_price == 20020
        assert signal.stop_price == 20020 - 40
        assert signal.target_price == 20020 + 100
        assert signal.strategy_name == "Trend Day Bull"
        assert signal.setup_type == 'EMA20_PULLBACK'

    def test_no_signal_without_bull_alignment(self):
        """Bear alignment should not trigger bull entry."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        self.strategy.on_bar(_make_bar(20010), 0, _make_ctx())
        self.strategy.on_bar(_make_bar(20015), 1, _make_ctx())
        # EMA50 > EMA20 = bear alignment, not bull
        bar = _make_bar(20020, delta=200, ema20=20015,
                        ema20_15m=20010, ema50_15m=20030, adx14_15m=30.0)
        result = self.strategy.on_bar(bar, 2, _make_ctx())
        assert result is None

    def test_no_signal_when_adx_low(self):
        """ADX below threshold should block entry."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        self.strategy.on_bar(_make_bar(20010), 0, _make_ctx())
        self.strategy.on_bar(_make_bar(20015), 1, _make_ctx())
        bar = _make_bar(20020, delta=200, ema20=20015,
                        ema20_15m=20010, ema50_15m=19990, adx14_15m=20.0)
        result = self.strategy.on_bar(bar, 2, _make_ctx())
        assert result is None

    def test_no_signal_when_delta_negative(self):
        """Negative delta should block bull entry."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        self.strategy.on_bar(_make_bar(20010), 0, _make_ctx())
        self.strategy.on_bar(_make_bar(20015), 1, _make_ctx())
        bar = _make_bar(20020, delta=-100, ema20=20015,
                        ema20_15m=20010, ema50_15m=19990, adx14_15m=30.0)
        result = self.strategy.on_bar(bar, 2, _make_ctx())
        assert result is None

    def test_no_signal_below_ibh(self):
        """Price must be above IBH for bull trend entry."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        self.strategy.on_bar(_make_bar(20010), 0, _make_ctx())
        self.strategy.on_bar(_make_bar(20015), 1, _make_ctx())
        # Price falls back below IBH
        bar = _make_bar(19995, delta=200, ema20=19990,
                        ema20_15m=20010, ema50_15m=19990, adx14_15m=30.0)
        result = self.strategy.on_bar(bar, 2, _make_ctx())
        assert result is None

    def test_only_one_signal_per_session(self):
        """Strategy fires only once per session."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        self.strategy.on_bar(_make_bar(20010), 0, _make_ctx())
        self.strategy.on_bar(_make_bar(20015), 1, _make_ctx())
        bar = _make_bar(20020, delta=200, ema20=20015,
                        ema20_15m=20010, ema50_15m=19990, adx14_15m=30.0)
        sig1 = self.strategy.on_bar(bar, 2, _make_ctx())
        assert sig1 is not None
        sig2 = self.strategy.on_bar(bar, 3, _make_ctx())
        assert sig2 is None

    def test_no_signal_after_cutoff(self):
        """No entries after 14:00."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        self.strategy.on_bar(_make_bar(20010), 0, _make_ctx())
        self.strategy.on_bar(_make_bar(20015), 1, _make_ctx())
        bar = _make_bar(20020, delta=200, ema20=20015,
                        ema20_15m=20010, ema50_15m=19990, adx14_15m=30.0,
                        timestamp='2025-06-10 14:05:00')
        ctx = _make_ctx(bar_time=pd.Timestamp('2025-06-10 14:05:00').time())
        result = self.strategy.on_bar(bar, 2, ctx)
        assert result is None

    def test_vwap_pullback_preferred(self):
        """VWAP pullback should be preferred over EMA20 when both available."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        self.strategy.on_bar(_make_bar(20010), 0, _make_ctx())
        self.strategy.on_bar(_make_bar(20015), 1, _make_ctx())
        # Price=20020, VWAP=20015 (dist=5/100=0.05 < 0.4), ema20=20015
        bar = _make_bar(20020, delta=200, vwap=20015, ema20=20015,
                        ema20_15m=20010, ema50_15m=19990, adx14_15m=30.0)
        sig = self.strategy.on_bar(bar, 2, _make_ctx())
        assert sig is not None
        assert sig.setup_type == 'VWAP_PULLBACK'

    def test_signal_metadata(self):
        """Signal metadata should contain 15-min indicators."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        self.strategy.on_bar(_make_bar(20010), 0, _make_ctx())
        self.strategy.on_bar(_make_bar(20015), 1, _make_ctx())
        bar = _make_bar(20020, delta=200, ema20=20015,
                        ema20_15m=20010, ema50_15m=19990, adx14_15m=32.5)
        sig = self.strategy.on_bar(bar, 2, _make_ctx())
        assert sig is not None
        assert sig.metadata['ema20_15m'] == 20010.0
        assert sig.metadata['ema50_15m'] == 19990.0
        assert sig.metadata['adx14_15m'] == 32.5


# ═══════════════════════════════════════════════════════════════
# TREND DAY BEAR TESTS
# ═══════════════════════════════════════════════════════════════

class TestTrendDayBear:
    def setup_method(self):
        self.strategy = TrendDayBear()

    def test_name(self):
        assert self.strategy.name == "Trend Day Bear"

    def test_applicable_day_types_empty(self):
        assert self.strategy.applicable_day_types == []

    def test_no_signal_before_acceptance(self):
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        bar = _make_bar(19950)  # Inside range
        result = self.strategy.on_bar(bar, 0, _make_ctx())
        assert result is None

    def test_acceptance_requires_three_bars(self):
        """Bear acceptance needs 3 consecutive bars below IBL."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        self.strategy.on_bar(_make_bar(19890), 0, _make_ctx())
        assert not self.strategy._acceptance_confirmed
        self.strategy.on_bar(_make_bar(19885), 1, _make_ctx())
        assert not self.strategy._acceptance_confirmed
        self.strategy.on_bar(_make_bar(19880), 2, _make_ctx())
        assert self.strategy._acceptance_confirmed

    def test_signal_with_all_conditions_met(self):
        """Full signal: accepted + 15m bear align + ADX>=35 + delta<0."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        for i in range(3):
            self.strategy.on_bar(_make_bar(19890 - i * 5), i, _make_ctx())
        # ADX=40 (above 35 threshold for bear)
        bar = _make_bar(
            19870, delta=-200, ema20=19875,
            ema20_15m=19880, ema50_15m=19920, adx14_15m=40.0,
            timestamp='2025-06-10 11:00:00',
        )
        signal = self.strategy.on_bar(bar, 3, _make_ctx())
        assert signal is not None
        assert signal.direction == 'SHORT'
        assert signal.entry_price == 19870
        assert signal.stop_price == 19870 + 40
        assert signal.target_price == 19870 - 100
        assert signal.strategy_name == "Trend Day Bear"

    def test_no_signal_without_bear_alignment(self):
        """Bull alignment should not trigger bear entry."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        for i in range(3):
            self.strategy.on_bar(_make_bar(19890 - i * 5), i, _make_ctx())
        bar = _make_bar(19870, delta=-200, ema20=19875,
                        ema20_15m=19920, ema50_15m=19880, adx14_15m=40.0)
        result = self.strategy.on_bar(bar, 3, _make_ctx())
        assert result is None

    def test_no_signal_when_adx_below_35(self):
        """ADX below 35 should block bear entry (bears need stronger trend)."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        for i in range(3):
            self.strategy.on_bar(_make_bar(19890 - i * 5), i, _make_ctx())
        bar = _make_bar(19870, delta=-200, ema20=19875,
                        ema20_15m=19880, ema50_15m=19920, adx14_15m=30.0)
        result = self.strategy.on_bar(bar, 3, _make_ctx())
        assert result is None

    def test_no_signal_when_delta_positive(self):
        """Positive delta should block bear entry."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        for i in range(3):
            self.strategy.on_bar(_make_bar(19890 - i * 5), i, _make_ctx())
        bar = _make_bar(19870, delta=100, ema20=19875,
                        ema20_15m=19880, ema50_15m=19920, adx14_15m=40.0)
        result = self.strategy.on_bar(bar, 3, _make_ctx())
        assert result is None

    def test_no_signal_above_ibl(self):
        """Price must be below IBL for bear entry."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        for i in range(3):
            self.strategy.on_bar(_make_bar(19890 - i * 5), i, _make_ctx())
        bar = _make_bar(19910, delta=-200, ema20=19905,
                        ema20_15m=19880, ema50_15m=19920, adx14_15m=40.0)
        result = self.strategy.on_bar(bar, 3, _make_ctx())
        assert result is None

    def test_only_one_signal_per_session(self):
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        for i in range(3):
            self.strategy.on_bar(_make_bar(19890 - i * 5), i, _make_ctx())
        bar = _make_bar(19870, delta=-200, ema20=19875,
                        ema20_15m=19880, ema50_15m=19920, adx14_15m=40.0)
        sig1 = self.strategy.on_bar(bar, 3, _make_ctx())
        assert sig1 is not None
        sig2 = self.strategy.on_bar(bar, 4, _make_ctx())
        assert sig2 is None

    def test_bear_continuation_entry(self):
        """When no VWAP level hit, bear continuation should fire."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        for i in range(3):
            self.strategy.on_bar(_make_bar(19890 - i * 5), i, _make_ctx())
        bar = _make_bar(19800, delta=-200, vwap=19950, ema20=19850,
                        ema20_15m=19880, ema50_15m=19920, adx14_15m=40.0)
        sig = self.strategy.on_bar(bar, 3, _make_ctx())
        assert sig is not None
        assert sig.setup_type == 'BEAR_CONTINUATION'

    def test_signal_rr_ratio(self):
        """Stop=40pt, target=100pt should give 2.5:1 R:R."""
        self.strategy.on_session_start('2025-06-10', 20000, 19900, 100, {})
        for i in range(3):
            self.strategy.on_bar(_make_bar(19890 - i * 5), i, _make_ctx())
        bar = _make_bar(19870, delta=-200, ema20=19875,
                        ema20_15m=19880, ema50_15m=19920, adx14_15m=40.0)
        sig = self.strategy.on_bar(bar, 3, _make_ctx())
        assert sig is not None
        assert sig.risk_points == 40.0
        assert sig.reward_points == 100.0
        assert sig.risk_reward_ratio == 2.5


# ═══════════════════════════════════════════════════════════════
# 15-MIN INDICATOR PIPELINE TESTS
# ═══════════════════════════════════════════════════════════════

class TestTrendIndicators:
    def test_compute_15m_trend_indicators(self):
        """Verify 15-min indicators are added to dataframe."""
        from rockit_core.indicators.technical import compute_15m_trend_indicators
        # Create 100 1-min bars with timestamps
        dates = pd.date_range('2025-06-10 09:30:00', periods=100, freq='1min')
        df = pd.DataFrame({
            'timestamp': dates,
            'open': np.random.randn(100).cumsum() + 20000,
            'high': np.random.randn(100).cumsum() + 20005,
            'low': np.random.randn(100).cumsum() + 19995,
            'close': np.random.randn(100).cumsum() + 20000,
            'volume': np.random.randint(100, 1000, 100),
        })
        df['high'] = df[['open', 'high', 'close']].max(axis=1)
        df['low'] = df[['open', 'low', 'close']].min(axis=1)

        result = compute_15m_trend_indicators(df)
        assert 'ema20_15m' in result.columns
        assert 'ema50_15m' in result.columns
        assert 'adx14_15m' in result.columns
        assert len(result) == 100  # Same length as input
        # At least some values should be non-NaN
        assert result['ema20_15m'].notna().sum() > 0
