# modules/regime_context.py
"""
Regime classification context — enriches snapshots with regime dimensions.

Computes:
1. ATR14 on daily timeframe (volatility regime from prior 14 sessions)
2. ATR14 on 5-min bars (intraday volatility regime)
3. Prior day type (yesterday's final classification)
4. Consecutive balance days counter
5. Weekly range and direction
6. VIX data integration
7. Composite regime label

All computations use only data available at the given time (no lookahead).
"""

import numpy as np
import pandas as pd
from datetime import time

from rockit_core.deterministic.modules.vix_regime import get_vix_regime


def get_regime_context(df_extended, df_current, intraday_data, session_date, current_time_str="11:45"):
    """
    Compute regime classification context for the session.

    Args:
        df_extended: Multi-day DataFrame (14+ prior days) for historical context
        df_current: Current session DataFrame (1-min bars)
        intraday_data: Dict with 'ib' key containing IB data
        session_date: 'YYYY-MM-DD' string
        current_time_str: 'HH:MM' format

    Returns:
        dict with regime dimensions and composite label
    """
    try:
        current_time = pd.to_datetime(current_time_str).time()
    except (ValueError, TypeError):
        current_time = time(11, 45)

    current_date = pd.to_datetime(session_date)

    # Build daily OHLC from df_extended (prior sessions only)
    daily_bars = _build_daily_bars(df_extended, current_date)

    # 1. ATR14 on daily timeframe
    atr14_daily = _compute_atr(daily_bars, period=14) if len(daily_bars) >= 15 else None

    # 2. ATR14 on 5-min bars (intraday)
    available_df = df_current[df_current.index.time <= current_time].copy()
    fivemin = available_df.resample('5min').agg(
        {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
    ).dropna()
    atr14_5min = _compute_atr(fivemin, period=14) if len(fivemin) >= 15 else None

    # 3. Prior day type classification
    prior_day_type = _classify_prior_day(daily_bars, df_extended, current_date)

    # 4. Consecutive balance days
    consecutive_balance = _count_consecutive_balance(daily_bars, df_extended, current_date)

    # 5. Weekly range and direction
    weekly = _compute_weekly_context(daily_bars)

    # 6. VIX data
    vix_data = _get_vix_data(session_date)

    # 7. Composite regime label
    ib_data = intraday_data.get('ib', {})
    composite = _classify_regime(
        atr14_daily=atr14_daily,
        ib_range=ib_data.get('ib_range'),
        ib_atr_ratio=ib_data.get('ib_range_vs_atr'),
        consecutive_balance=consecutive_balance,
        vix_regime=vix_data.get('vix_regime'),
        weekly_direction=weekly.get('weekly_direction'),
    )

    return {
        "atr14_daily": round(atr14_daily, 2) if atr14_daily else None,
        "atr14_5min": round(atr14_5min, 4) if atr14_5min else None,
        "prior_day_type": prior_day_type,
        "consecutive_balance_days": consecutive_balance,
        "weekly_range": weekly.get('weekly_range'),
        "weekly_high": weekly.get('weekly_high'),
        "weekly_low": weekly.get('weekly_low'),
        "weekly_direction": weekly.get('weekly_direction'),
        "weekly_atr": weekly.get('weekly_atr'),
        "vix_open": vix_data.get('vix_open'),
        "vix_close": vix_data.get('vix_close'),
        "vix_regime": vix_data.get('vix_regime'),
        "vix_5d_avg": vix_data.get('vix_5d_avg'),
        "vix_change_pct": vix_data.get('vix_change_pct'),
        "composite_regime": composite,
        "note": "Regime context: daily ATR, 5min ATR, prior day, balance streak, weekly, VIX, composite label.",
    }


def _build_daily_bars(df_extended, current_date):
    """Build daily OHLC bars from extended data, excluding current date."""
    if df_extended.empty:
        return pd.DataFrame(columns=['open', 'high', 'low', 'close'])

    # Only use data before the current session
    prior_data = df_extended[df_extended.index.normalize() < current_date]
    if prior_data.empty:
        return pd.DataFrame(columns=['open', 'high', 'low', 'close'])

    # Group by session_date if available, otherwise by calendar date
    if 'session_date' in prior_data.columns:
        daily = prior_data.groupby('session_date').agg(
            open=('open', 'first'),
            high=('high', 'max'),
            low=('low', 'min'),
            close=('close', 'last'),
        )
        daily.index = pd.to_datetime(daily.index)
    else:
        daily = prior_data.resample('D').agg(
            {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
        ).dropna()

    return daily.sort_index()


def _compute_atr(df, period=14):
    """Compute ATR(N) from OHLC data. Returns latest value or None."""
    if len(df) < period + 1:
        return None

    high = df['high'].values
    low = df['low'].values
    close = df['close'].values

    tr = np.zeros(len(df))
    for i in range(1, len(df)):
        h_l = high[i] - low[i]
        h_pc = abs(high[i] - close[i - 1])
        l_pc = abs(low[i] - close[i - 1])
        tr[i] = max(h_l, h_pc, l_pc)

    # Wilder smoothing
    atr = np.mean(tr[1:period + 1])
    for i in range(period + 1, len(df)):
        atr = (atr * (period - 1) + tr[i]) / period

    return float(atr)


def _classify_prior_day(daily_bars, df_extended, current_date):
    """Classify the prior trading day's type from its price action."""
    if daily_bars.empty:
        return None

    prev_bar = daily_bars.iloc[-1]
    prev_date = daily_bars.index[-1]

    # Need the prior day's session data to classify
    if 'session_date' in df_extended.columns:
        prev_date_str = prev_date.strftime('%Y-%m-%d')
        prev_session = df_extended[df_extended['session_date'] == prev_date_str]
    else:
        prev_session = df_extended[df_extended.index.normalize() == prev_date.normalize()]

    if prev_session.empty:
        return _simple_day_classify(prev_bar)

    # Compute IB for prior day (first hour: 9:30-10:30)
    rth_data = prev_session[
        (prev_session.index.time >= time(9, 30)) &
        (prev_session.index.time <= time(16, 0))
    ]
    if rth_data.empty:
        return _simple_day_classify(prev_bar)

    ib_data = rth_data[rth_data.index.time <= time(10, 30)]
    if ib_data.empty:
        return _simple_day_classify(prev_bar)

    ib_high = ib_data['high'].max()
    ib_low = ib_data['low'].min()
    ib_range = ib_high - ib_low

    day_high = rth_data['high'].max()
    day_low = rth_data['low'].min()
    day_range = day_high - day_low

    if ib_range == 0:
        return 'neutral'

    extension_ratio = day_range / ib_range

    # Classify based on IB extension
    broke_high = day_high > ib_high + 0.5
    broke_low = day_low < ib_low - 0.5

    if broke_high and broke_low:
        return 'neutral'  # Both sides broken = rotation/neutral
    elif extension_ratio >= 2.0:
        return 'trend'
    elif broke_high and not broke_low:
        return 'p_day_up' if extension_ratio >= 1.5 else 'normal_up'
    elif broke_low and not broke_high:
        return 'p_day_down' if extension_ratio >= 1.5 else 'normal_down'
    else:
        return 'balance'


def _simple_day_classify(bar):
    """Simple day type from single OHLC bar (fallback)."""
    body = abs(bar['close'] - bar['open'])
    full_range = bar['high'] - bar['low']
    if full_range == 0:
        return 'balance'
    body_pct = body / full_range
    if body_pct > 0.6:
        return 'trend'
    elif body_pct < 0.3:
        return 'balance'
    return 'neutral'


def _count_consecutive_balance(daily_bars, df_extended, current_date):
    """Count consecutive balance/neutral days looking back from current date."""
    if len(daily_bars) < 2:
        return 0

    count = 0
    for i in range(len(daily_bars) - 1, -1, -1):
        bar = daily_bars.iloc[i]
        bar_date = daily_bars.index[i]

        # Get session data for this day
        if 'session_date' in df_extended.columns:
            date_str = bar_date.strftime('%Y-%m-%d')
            session = df_extended[df_extended['session_date'] == date_str]
        else:
            session = df_extended[df_extended.index.normalize() == bar_date.normalize()]

        if session.empty:
            day_type = _simple_day_classify(bar)
        else:
            rth = session[
                (session.index.time >= time(9, 30)) &
                (session.index.time <= time(16, 0))
            ]
            if rth.empty:
                day_type = _simple_day_classify(bar)
            else:
                ib = rth[rth.index.time <= time(10, 30)]
                if ib.empty:
                    day_type = _simple_day_classify(bar)
                else:
                    ib_high = ib['high'].max()
                    ib_low = ib['low'].min()
                    ib_range_val = ib_high - ib_low
                    day_high = rth['high'].max()
                    day_low = rth['low'].min()
                    day_range = day_high - day_low

                    if ib_range_val > 0:
                        ratio = day_range / ib_range_val
                        broke_high = day_high > ib_high + 0.5
                        broke_low = day_low < ib_low - 0.5
                        if broke_high and broke_low:
                            day_type = 'neutral'
                        elif ratio >= 2.0:
                            day_type = 'trend'
                        elif broke_high or broke_low:
                            day_type = 'normal'
                        else:
                            day_type = 'balance'
                    else:
                        day_type = 'balance'

        if day_type in ('balance', 'neutral'):
            count += 1
        else:
            break

    return count


def _compute_weekly_context(daily_bars):
    """Compute weekly range, direction, and ATR from daily bars."""
    result = {
        'weekly_range': None,
        'weekly_high': None,
        'weekly_low': None,
        'weekly_direction': None,
        'weekly_atr': None,
    }

    if len(daily_bars) < 5:
        return result

    last5 = daily_bars.iloc[-5:]
    weekly_high = float(last5['high'].max())
    weekly_low = float(last5['low'].min())
    weekly_range = round(weekly_high - weekly_low, 2)

    # Direction based on close vs open of the 5-day window
    first_open = float(last5['open'].iloc[0])
    last_close = float(last5['close'].iloc[-1])
    change_pct = (last_close - first_open) / first_open * 100 if first_open > 0 else 0

    if change_pct > 0.3:
        direction = 'up'
    elif change_pct < -0.3:
        direction = 'down'
    else:
        direction = 'flat'

    # Weekly ATR: ATR(5) on daily bars
    weekly_atr = _compute_atr(last5, period=min(5, len(last5) - 1))

    result['weekly_range'] = weekly_range
    result['weekly_high'] = round(weekly_high, 2)
    result['weekly_low'] = round(weekly_low, 2)
    result['weekly_direction'] = direction
    result['weekly_atr'] = round(weekly_atr, 2) if weekly_atr else None

    return result


def _get_vix_data(session_date):
    """Get VIX data for the session, with graceful fallback."""
    try:
        return get_vix_regime(session_date)
    except Exception:
        return {
            'vix_open': None,
            'vix_close': None,
            'vix_regime': None,
            'vix_5d_avg': None,
            'vix_change_pct': None,
        }


def _classify_regime(atr14_daily=None, ib_range=None, ib_atr_ratio=None,
                     consecutive_balance=0, vix_regime=None, weekly_direction=None):
    """
    Classify composite regime from multiple dimensions.

    Returns one of:
    - low_vol_balance: quiet market, rangebound
    - low_vol_trend: steady directional move, low volatility
    - high_vol_trend: strong directional move, volatile
    - high_vol_range: volatile but no direction (chop)
    - compressed_pre_breakout: narrow IB, balance streak, low vol — breakout incoming
    - expansion: wide IB, strong trend, high vol
    - transitional: mixed signals, regime changing
    """
    # Default when insufficient data
    if atr14_daily is None or ib_range is None:
        return 'unknown'

    # Determine volatility level
    is_high_vol = vix_regime in ('elevated', 'high', 'extreme') if vix_regime else False
    is_low_vol = vix_regime in ('low', 'moderate') if vix_regime else True

    # IB classification
    ib_narrow = (ib_atr_ratio or 0) < 0.8 if ib_atr_ratio is not None else False
    ib_wide = (ib_atr_ratio or 0) > 1.3 if ib_atr_ratio is not None else False

    # Compression detection: narrow IB + balance streak
    if ib_narrow and consecutive_balance >= 3 and is_low_vol:
        return 'compressed_pre_breakout'

    # Expansion: wide IB + high vol
    if ib_wide and is_high_vol:
        return 'expansion'

    # High vol trend
    if is_high_vol and weekly_direction in ('up', 'down'):
        return 'high_vol_trend'

    # High vol range
    if is_high_vol and weekly_direction == 'flat':
        return 'high_vol_range'

    # Low vol trend
    if is_low_vol and weekly_direction in ('up', 'down') and not ib_narrow:
        return 'low_vol_trend'

    # Low vol balance
    if is_low_vol and (weekly_direction == 'flat' or consecutive_balance >= 2):
        return 'low_vol_balance'

    return 'transitional'
