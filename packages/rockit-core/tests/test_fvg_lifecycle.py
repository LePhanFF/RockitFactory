"""Tests for FVG detection with lifecycle tracking.

Note: 5-min FVG detection is disabled (too noisy). Tests use 15-min timeframe.
Test data uses freq='15min' so bars resample 1:1 into 15-min candles.
"""

import pandas as pd
import pytest

from rockit_core.deterministic.modules.fvg_detection import get_fvg_detection


def _make_bars(prices, start='2025-01-15 09:30', freq='15min'):
    """Create OHLC DataFrame from close prices (high = close+2, low = close-2)."""
    timestamps = pd.date_range(start, periods=len(prices), freq=freq)
    df = pd.DataFrame({
        'open': [p - 1 for p in prices],
        'high': [p + 2 for p in prices],
        'low': [p - 2 for p in prices],
        'close': prices,
    }, index=timestamps)
    return df


def _make_ohlc_bars(bars, start='2025-01-15 09:30', freq='15min'):
    """Create OHLC DataFrame from explicit (o, h, l, c) tuples."""
    timestamps = pd.date_range(start, periods=len(bars), freq=freq)
    df = pd.DataFrame(bars, columns=['open', 'high', 'low', 'close'], index=timestamps)
    return df


class TestFVGDetection:
    def test_bullish_fvg_detected(self):
        """Bullish FVG: bar[0].high < bar[2].low (gap up)."""
        bars = [
            (100, 105, 98, 103),   # bar 0: high = 105
            (104, 115, 103, 112),  # bar 1: middle candle
            (113, 118, 108, 116),  # bar 2: low = 108 > 105 → bullish FVG
        ]
        df = _make_ohlc_bars(bars)
        result = get_fvg_detection(df, df, current_time_str="23:59")
        fvgs = result['15min_fvg']
        bullish = [f for f in fvgs if f['type'] == 'bullish']
        assert len(bullish) >= 1
        assert bullish[0]['bottom'] == 105  # prev high
        assert bullish[0]['top'] == 108     # next low

    def test_bearish_fvg_detected(self):
        """Bearish FVG: bar[0].low > bar[2].high (gap down)."""
        bars = [
            (110, 115, 108, 112),  # bar 0: low = 108
            (107, 108, 95, 96),    # bar 1: middle candle
            (95, 105, 90, 100),    # bar 2: high = 105 < 108 → bearish FVG
        ]
        df = _make_ohlc_bars(bars)
        result = get_fvg_detection(df, df, current_time_str="23:59")
        fvgs = result['15min_fvg']
        bearish = [f for f in fvgs if f['type'] == 'bearish']
        assert len(bearish) >= 1
        assert bearish[0]['top'] == 108     # prev low
        assert bearish[0]['bottom'] == 105  # next high


class TestFVGLifecycle:
    def test_active_fvg_has_correct_status(self):
        """Unfilled FVG should have status='active'."""
        bars = [
            (100, 105, 98, 103),
            (104, 115, 103, 112),
            (113, 118, 108, 116),  # Bullish FVG
            (115, 120, 112, 118),  # Price stays above gap → still active
            (117, 122, 114, 120),
        ]
        df = _make_ohlc_bars(bars)
        result = get_fvg_detection(df, df, current_time_str="23:59")
        fvgs = result['15min_fvg']
        bullish = [f for f in fvgs if f['type'] == 'bullish']
        assert len(bullish) >= 1
        assert bullish[0]['status'] == 'active'
        assert bullish[0]['fill_pct'] == 0.0
        assert bullish[0]['filled_time'] is None

    def test_filled_fvg_retained_with_status(self):
        """Filled FVG should have status='filled', NOT be removed."""
        bars = [
            (100, 105, 98, 103),
            (104, 115, 103, 112),
            (113, 118, 108, 116),  # Bullish FVG: bottom=105, top=108
            (115, 120, 112, 118),  # Still above
            (110, 112, 100, 102),  # Drops to 100 → fills past bottom (105) → fully filled
        ]
        df = _make_ohlc_bars(bars)
        result = get_fvg_detection(df, df, current_time_str="23:59")
        fvgs = result['15min_fvg']
        bullish = [f for f in fvgs if f['type'] == 'bullish']
        assert len(bullish) >= 1
        filled = [f for f in bullish if f['status'] == 'filled']
        assert len(filled) >= 1
        assert filled[0]['fill_pct'] == 1.0
        assert filled[0]['filled_time'] is not None

    def test_partially_filled_fvg(self):
        """FVG with price entering gap but not fully filling it."""
        bars = [
            (100, 105, 98, 103),
            (104, 115, 103, 112),
            (113, 118, 108, 116),  # Bullish FVG: bottom=105, top=108 (gap=3)
            (115, 120, 112, 118),  # Still above
            (112, 114, 106, 110),  # Drops to 106 → entered gap (top=108) but above bottom (105)
        ]
        df = _make_ohlc_bars(bars)
        result = get_fvg_detection(df, df, current_time_str="23:59")
        fvgs = result['15min_fvg']
        bullish = [f for f in fvgs if f['type'] == 'bullish']
        assert len(bullish) >= 1
        # Should be partially filled
        partial = [f for f in bullish if f['status'] == 'partially_filled']
        assert len(partial) >= 1
        assert 0 < partial[0]['fill_pct'] < 1.0


class TestFVGFields:
    def test_fvg_has_id(self):
        bars = [
            (100, 105, 98, 103),
            (104, 115, 103, 112),
            (113, 118, 108, 116),
        ]
        df = _make_ohlc_bars(bars)
        result = get_fvg_detection(df, df, current_time_str="23:59")
        fvgs = result['15min_fvg']
        assert len(fvgs) >= 1
        assert 'fvg_id' in fvgs[0]
        assert fvgs[0]['fvg_id'].startswith('15min_')

    def test_fvg_has_created_time(self):
        bars = [
            (100, 105, 98, 103),
            (104, 115, 103, 112),
            (113, 118, 108, 116),
        ]
        df = _make_ohlc_bars(bars)
        result = get_fvg_detection(df, df, current_time_str="23:59")
        fvgs = result['15min_fvg']
        assert fvgs[0]['created_time'] is not None

    def test_fvg_has_gap_size(self):
        bars = [
            (100, 105, 98, 103),
            (104, 115, 103, 112),
            (113, 118, 108, 116),  # gap = 108 - 105 = 3
        ]
        df = _make_ohlc_bars(bars)
        result = get_fvg_detection(df, df, current_time_str="23:59")
        fvgs = result['15min_fvg']
        bullish = [f for f in fvgs if f['type'] == 'bullish']
        assert bullish[0]['gap_size'] == pytest.approx(3.0)

    def test_fvg_has_timeframe(self):
        bars = [
            (100, 105, 98, 103),
            (104, 115, 103, 112),
            (113, 118, 108, 116),
        ]
        df = _make_ohlc_bars(bars)
        result = get_fvg_detection(df, df, current_time_str="23:59")
        fvgs = result['15min_fvg']
        assert fvgs[0]['timeframe'] == '15min'


class TestRecentlyFilled:
    def test_recently_filled_populated(self):
        """recently_filled should contain FVGs that were recently filled."""
        bars = [
            (100, 105, 98, 103),
            (104, 115, 103, 112),
            (113, 118, 108, 116),  # Bullish FVG
            (115, 120, 112, 118),
            (110, 112, 100, 102),  # Fills the FVG
        ]
        df = _make_ohlc_bars(bars)
        result = get_fvg_detection(df, df, current_time_str="23:59")
        # recently_filled aggregates across timeframes
        assert 'recently_filled' in result

    def test_no_fvgs_returns_empty(self):
        """No FVGs at all → empty results."""
        prices = [100, 101, 102, 103, 104]  # Smooth move, no gaps
        df = _make_bars(prices)
        result = get_fvg_detection(df, df, current_time_str="23:59")
        assert result['15min_fvg'] == []


class TestOutputStructure:
    def test_all_timeframe_keys_present(self):
        prices = list(range(100, 150))
        df = _make_bars(prices)
        result = get_fvg_detection(df, df, current_time_str="23:59")
        expected_keys = [
            'daily_fvg', '4h_fvg', '1h_fvg', '90min_fvg', '15min_fvg', '5min_fvg',
            'daily_bpr', '4h_bpr', '1h_bpr', '90min_bpr', '15min_bpr', '5min_bpr',
            '5min_engulfed', '15min_engulfed', 'recently_filled',
            'ndog', 'nwog', 'note',
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_note_mentions_lifecycle(self):
        prices = list(range(100, 150))
        df = _make_bars(prices)
        result = get_fvg_detection(df, df, current_time_str="23:59")
        assert 'lifecycle' in result['note'].lower()
