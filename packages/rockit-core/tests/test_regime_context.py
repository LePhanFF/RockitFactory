"""Tests for regime classification context module."""

import pandas as pd
import numpy as np
import pytest

from rockit_core.deterministic.modules.regime_context import (
    get_regime_context,
    _build_daily_bars,
    _compute_atr,
    _classify_prior_day,
    _count_consecutive_balance,
    _compute_weekly_context,
    _classify_regime,
)


def _make_session_data(dates, prices, with_session_date=True):
    """Create multi-day 1-min DataFrame for testing.

    Args:
        dates: list of 'YYYY-MM-DD' strings
        prices: list of base prices (one per date)
        with_session_date: include session_date column
    """
    rows = []
    for date_str, base_price in zip(dates, prices):
        dt = pd.to_datetime(date_str)
        for h in range(9, 16):
            start_min = 30 if h == 9 else 0
            for m in range(start_min, 60):
                ts = dt.replace(hour=h, minute=m)
                noise = np.random.uniform(-5, 5)
                price = base_price + noise
                row = {
                    'timestamp': ts,
                    'open': price - 1,
                    'high': price + 3,
                    'low': price - 3,
                    'close': price,
                }
                if with_session_date:
                    row['session_date'] = date_str
                rows.append(row)

    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df['timestamp'])
    df.index.name = None
    return df


class TestBuildDailyBars:
    def test_builds_from_session_date(self):
        dates = ['2025-06-10', '2025-06-11', '2025-06-12']
        prices = [21000, 21100, 21200]
        df = _make_session_data(dates, prices)
        current_date = pd.to_datetime('2025-06-12')

        daily = _build_daily_bars(df, current_date)
        # Should exclude current date (2025-06-12)
        assert len(daily) == 2
        assert daily.index[0] == pd.to_datetime('2025-06-10')

    def test_empty_df_returns_empty(self):
        df = pd.DataFrame(columns=['open', 'high', 'low', 'close'])
        daily = _build_daily_bars(df, pd.to_datetime('2025-06-12'))
        assert len(daily) == 0


class TestComputeATR:
    def test_known_atr(self):
        """ATR of constant-range bars should equal the range."""
        n = 20
        data = {
            'open': [100.0] * n,
            'high': [110.0] * n,
            'low': [90.0] * n,
            'close': [100.0] * n,
        }
        df = pd.DataFrame(data)
        atr = _compute_atr(df, period=14)
        # Range is 20 for each bar, so ATR should be close to 20
        assert atr is not None
        assert 19.0 < atr < 21.0

    def test_insufficient_data_returns_none(self):
        df = pd.DataFrame({
            'open': [100, 101, 102],
            'high': [105, 106, 107],
            'low': [95, 96, 97],
            'close': [100, 101, 102],
        })
        assert _compute_atr(df, period=14) is None


class TestClassifyPriorDay:
    def test_trend_day(self):
        """Day with one-sided IB break + range > 2x IB should classify as trend."""
        dates = ['2025-06-10', '2025-06-11']
        df = _make_session_data(dates, [21000, 21000])

        # Override to create a trend day: narrow IB, breakout ONLY above
        date_str = '2025-06-10'
        mask = df['session_date'] == date_str

        # Set IB bars (9:30-10:30) to narrow range
        ib_mask = mask & (df.index.time <= pd.to_datetime('10:30').time())
        df.loc[ib_mask, 'high'] = 21010
        df.loc[ib_mask, 'low'] = 21000
        df.loc[ib_mask, 'open'] = 21002
        df.loc[ib_mask, 'close'] = 21008

        # Set afternoon bars: break high only, stay above IB low
        pm_mask = mask & (df.index.time > pd.to_datetime('10:30').time())
        df.loc[pm_mask, 'high'] = 21060
        df.loc[pm_mask, 'low'] = 21005  # Still above IB low (21000)
        df.loc[pm_mask, 'open'] = 21010
        df.loc[pm_mask, 'close'] = 21055

        current_date = pd.to_datetime('2025-06-11')
        daily = _build_daily_bars(df, current_date)
        result = _classify_prior_day(daily, df, current_date)
        # IB range=10, day range=60, broke high only → trend or p_day_up
        assert result in ('trend', 'p_day_up', 'normal_up')

    def test_balance_day(self):
        """Day contained within IB should classify as balance."""
        dates = ['2025-06-10', '2025-06-11']
        df = _make_session_data(dates, [21000, 21000])
        date_str = '2025-06-10'
        mask = df['session_date'] == date_str

        # Set all bars to same range (everything within IB)
        df.loc[mask, 'high'] = 21010
        df.loc[mask, 'low'] = 21000

        current_date = pd.to_datetime('2025-06-11')
        daily = _build_daily_bars(df, current_date)
        result = _classify_prior_day(daily, df, current_date)
        assert result == 'balance'

    def test_empty_daily_returns_none(self):
        daily = pd.DataFrame(columns=['open', 'high', 'low', 'close'])
        df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'session_date'])
        df.index = pd.DatetimeIndex([])
        result = _classify_prior_day(daily, df, pd.to_datetime('2025-06-11'))
        assert result is None


class TestConsecutiveBalance:
    def test_all_balance_days(self):
        """All balance days should count correctly."""
        dates = ['2025-06-09', '2025-06-10', '2025-06-11', '2025-06-12']
        df = _make_session_data(dates, [21000] * 4)

        # Make all days narrow (balance)
        for d in dates:
            mask = df['session_date'] == d
            df.loc[mask, 'high'] = 21005
            df.loc[mask, 'low'] = 21000

        current_date = pd.to_datetime('2025-06-12')
        daily = _build_daily_bars(df, current_date)
        count = _count_consecutive_balance(daily, df, current_date)
        # All 3 prior days are balance
        assert count >= 2

    def test_broken_by_trend(self):
        """Trend day should break the balance streak."""
        dates = ['2025-06-09', '2025-06-10', '2025-06-11', '2025-06-12']
        df = _make_session_data(dates, [21000] * 4)

        # Day 1: balance (all bars tight range)
        mask1 = df['session_date'] == '2025-06-09'
        df.loc[mask1, 'high'] = 21005
        df.loc[mask1, 'low'] = 21000
        df.loc[mask1, 'open'] = 21002
        df.loc[mask1, 'close'] = 21003

        # Day 2: trend (narrow IB, one-sided breakout above)
        mask2 = df['session_date'] == '2025-06-10'
        ib2 = mask2 & (df.index.time <= pd.to_datetime('10:30').time())
        df.loc[ib2, 'high'] = 21005
        df.loc[ib2, 'low'] = 21000
        df.loc[ib2, 'open'] = 21002
        df.loc[ib2, 'close'] = 21004
        pm2 = mask2 & (df.index.time > pd.to_datetime('10:30').time())
        df.loc[pm2, 'high'] = 21060
        df.loc[pm2, 'low'] = 21005  # Stay above IB low → one-sided break
        df.loc[pm2, 'open'] = 21010
        df.loc[pm2, 'close'] = 21055

        # Day 3: balance again (all bars tight range)
        mask3 = df['session_date'] == '2025-06-11'
        df.loc[mask3, 'high'] = 21005
        df.loc[mask3, 'low'] = 21000
        df.loc[mask3, 'open'] = 21002
        df.loc[mask3, 'close'] = 21003

        current_date = pd.to_datetime('2025-06-12')
        daily = _build_daily_bars(df, current_date)
        count = _count_consecutive_balance(daily, df, current_date)
        # Only day 3 (most recent) is balance, day 2 breaks the streak
        assert count == 1


class TestWeeklyContext:
    def test_weekly_range(self):
        n = 6
        data = {
            'open': [100 + i * 10 for i in range(n)],
            'high': [105 + i * 10 for i in range(n)],
            'low': [95 + i * 10 for i in range(n)],
            'close': [100 + i * 10 for i in range(n)],
        }
        daily = pd.DataFrame(data, index=pd.date_range('2025-06-09', periods=n))
        result = _compute_weekly_context(daily)
        assert result['weekly_range'] is not None
        assert result['weekly_high'] is not None
        assert result['weekly_low'] is not None

    def test_weekly_direction_up(self):
        data = {
            'open': [100, 105, 110, 115, 120],
            'high': [105, 110, 115, 120, 125],
            'low': [95, 100, 105, 110, 115],
            'close': [105, 110, 115, 120, 125],
        }
        daily = pd.DataFrame(data, index=pd.date_range('2025-06-09', periods=5))
        result = _compute_weekly_context(daily)
        assert result['weekly_direction'] == 'up'

    def test_weekly_direction_down(self):
        data = {
            'open': [125, 120, 115, 110, 105],
            'high': [130, 125, 120, 115, 110],
            'low': [120, 115, 110, 105, 100],
            'close': [120, 115, 110, 105, 100],
        }
        daily = pd.DataFrame(data, index=pd.date_range('2025-06-09', periods=5))
        result = _compute_weekly_context(daily)
        assert result['weekly_direction'] == 'down'

    def test_insufficient_data(self):
        data = {
            'open': [100, 101],
            'high': [105, 106],
            'low': [95, 96],
            'close': [100, 101],
        }
        daily = pd.DataFrame(data, index=pd.date_range('2025-06-09', periods=2))
        result = _compute_weekly_context(daily)
        assert result['weekly_range'] is None


class TestClassifyRegime:
    def test_compressed_pre_breakout(self):
        result = _classify_regime(
            atr14_daily=150, ib_range=80, ib_atr_ratio=0.5,
            consecutive_balance=4, vix_regime='low', weekly_direction='flat'
        )
        assert result == 'compressed_pre_breakout'

    def test_expansion(self):
        result = _classify_regime(
            atr14_daily=200, ib_range=300, ib_atr_ratio=1.5,
            consecutive_balance=0, vix_regime='high', weekly_direction='up'
        )
        assert result == 'expansion'

    def test_high_vol_trend(self):
        result = _classify_regime(
            atr14_daily=200, ib_range=180, ib_atr_ratio=1.0,
            consecutive_balance=0, vix_regime='elevated', weekly_direction='down'
        )
        assert result == 'high_vol_trend'

    def test_low_vol_balance(self):
        result = _classify_regime(
            atr14_daily=100, ib_range=90, ib_atr_ratio=0.9,
            consecutive_balance=3, vix_regime='moderate', weekly_direction='flat'
        )
        assert result == 'low_vol_balance'

    def test_low_vol_trend(self):
        result = _classify_regime(
            atr14_daily=100, ib_range=100, ib_atr_ratio=1.0,
            consecutive_balance=0, vix_regime='low', weekly_direction='up'
        )
        assert result == 'low_vol_trend'

    def test_unknown_without_data(self):
        result = _classify_regime(atr14_daily=None, ib_range=None)
        assert result == 'unknown'

    def test_high_vol_range(self):
        result = _classify_regime(
            atr14_daily=200, ib_range=180, ib_atr_ratio=1.0,
            consecutive_balance=0, vix_regime='high', weekly_direction='flat'
        )
        assert result == 'high_vol_range'


class TestGetRegimeContext:
    def test_returns_all_fields(self):
        """Full integration: verify output has all expected keys."""
        dates = ['2025-06-01', '2025-06-02', '2025-06-03', '2025-06-04', '2025-06-05',
                 '2025-06-06', '2025-06-09', '2025-06-10', '2025-06-11', '2025-06-12',
                 '2025-06-13', '2025-06-14', '2025-06-15', '2025-06-16', '2025-06-17',
                 '2025-06-18']
        prices = [21000 + i * 10 for i in range(len(dates))]
        df = _make_session_data(dates, prices)

        intraday_data = {
            'ib': {
                'ib_range': 100,
                'ib_range_vs_atr': 0.9,
            }
        }

        result = get_regime_context(
            df, df[df['session_date'] == '2025-06-18'],
            intraday_data, '2025-06-18', '12:00'
        )

        expected_keys = [
            'atr14_daily', 'atr14_5min',
            'prior_day_type', 'consecutive_balance_days',
            'weekly_range', 'weekly_high', 'weekly_low',
            'weekly_direction', 'weekly_atr',
            'vix_open', 'vix_close', 'vix_regime',
            'vix_5d_avg', 'vix_change_pct',
            'composite_regime', 'note',
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_handles_minimal_data(self):
        """Should not crash with insufficient data."""
        dates = ['2025-06-15']
        df = _make_session_data(dates, [21000])
        intraday_data = {'ib': {}}

        result = get_regime_context(df, df, intraday_data, '2025-06-15', '10:00')
        assert 'composite_regime' in result
        # Not enough data for daily ATR
        assert result['atr14_daily'] is None
