# modules/ib_location.py
import numpy as np
import pandas as pd
from datetime import time

HIGH_ATR_THRESHOLD = 20.0
LOW_ATR_THRESHOLD = 12.0


def _compute_adx(df, period=14):
    """
    Compute ADX(14) using Wilder smoothing from OHLC data.
    Returns the latest ADX value, or None if insufficient data.
    """
    if len(df) < period * 2:
        return None

    high = df['high'].values
    low = df['low'].values
    close = df['close'].values

    # True Range, +DM, -DM
    tr = np.zeros(len(df))
    plus_dm = np.zeros(len(df))
    minus_dm = np.zeros(len(df))

    for i in range(1, len(df)):
        h_l = high[i] - low[i]
        h_pc = abs(high[i] - close[i - 1])
        l_pc = abs(low[i] - close[i - 1])
        tr[i] = max(h_l, h_pc, l_pc)

        up_move = high[i] - high[i - 1]
        down_move = low[i - 1] - low[i]

        plus_dm[i] = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm[i] = down_move if (down_move > up_move and down_move > 0) else 0.0

    # Wilder smoothing (first value = sum of first `period` values, then EMA-like)
    atr_w = np.zeros(len(df))
    plus_di_smooth = np.zeros(len(df))
    minus_di_smooth = np.zeros(len(df))

    atr_w[period] = np.sum(tr[1:period + 1])
    plus_di_smooth[period] = np.sum(plus_dm[1:period + 1])
    minus_di_smooth[period] = np.sum(minus_dm[1:period + 1])

    for i in range(period + 1, len(df)):
        atr_w[i] = atr_w[i - 1] - (atr_w[i - 1] / period) + tr[i]
        plus_di_smooth[i] = plus_di_smooth[i - 1] - (plus_di_smooth[i - 1] / period) + plus_dm[i]
        minus_di_smooth[i] = minus_di_smooth[i - 1] - (minus_di_smooth[i - 1] / period) + minus_dm[i]

    # +DI, -DI, DX
    dx = np.zeros(len(df))
    for i in range(period, len(df)):
        if atr_w[i] == 0:
            continue
        plus_di = 100 * plus_di_smooth[i] / atr_w[i]
        minus_di = 100 * minus_di_smooth[i] / atr_w[i]
        di_sum = plus_di + minus_di
        if di_sum > 0:
            dx[i] = 100 * abs(plus_di - minus_di) / di_sum

    # ADX = Wilder smoothed DX
    adx_start = period * 2
    if adx_start >= len(df):
        return None

    adx = np.zeros(len(df))
    adx[adx_start] = np.mean(dx[period:adx_start + 1])

    for i in range(adx_start + 1, len(df)):
        adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period

    return round(float(adx[-1]), 2)


def _compute_bollinger_bands(df_1min, current_time, bb_period=20, bb_std=2):
    """
    Compute Bollinger Bands BB(20,2) from 5-min resampled close data.
    Returns dict with bb_upper, bb_lower, bb_mid, bb_position, bb_width, or None values.
    """
    result = {
        "bb_upper": None, "bb_lower": None, "bb_mid": None,
        "bb_position": None, "bb_width": None,
    }

    available = df_1min[df_1min.index.time <= current_time].copy()
    if len(available) < 5:
        return result

    # Resample to 5-min bars
    ohlc_5min = available['close'].resample('5min').last().dropna()

    if len(ohlc_5min) < bb_period:
        return result

    closes = ohlc_5min.values[-bb_period:]
    sma = float(np.mean(closes))
    std = float(np.std(closes, ddof=1))

    bb_upper = round(sma + bb_std * std, 2)
    bb_lower = round(sma - bb_std * std, 2)
    bb_mid = round(sma, 2)

    current_price = float(available['close'].iloc[-1])
    band_range = bb_upper - bb_lower
    bb_position = round((current_price - bb_lower) / band_range, 4) if band_range > 0 else 0.5
    bb_position = max(0.0, min(1.0, bb_position))  # clamp 0-1
    bb_width = round(band_range / bb_mid, 4) if bb_mid > 0 else None

    return {
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "bb_mid": bb_mid,
        "bb_position": round(bb_position, 4),
        "bb_width": bb_width,
    }

def get_ib_location(df_nq, current_time_str="11:45"):
    """
    100% no-lookahead IB calculation + additional indicators + safe ATR regime
    """

    # Parse current snapshot time
    try:
        current_time = pd.to_datetime(current_time_str).time()
    except (ValueError, TypeError):
        current_time = time(11, 45)

    # Filter to only data up to current_time
    available_df = df_nq[df_nq.index.time <= current_time].copy()

    if len(available_df) == 0:
        return {"note": "no_data_up_to_current_time"}

    # IB calculation (09:30 – 10:30 ET)
    ib_start = time(9, 30)
    ib_end = time(10, 30)
    ib_df = available_df[(available_df.index.time >= ib_start) & (available_df.index.time < ib_end)]


    if len(ib_df) == 0:
        ib_status = "partial"  # or "not_started"
        ib_high = available_df['high'].max() if not available_df.empty else None
        ib_low = available_df['low'].min() if not available_df.empty else None
    else:
        # IB complete when last bar opens at 10:25+ (5-min) or 10:29+ (1-min)
        # Both cover through 10:30. Use 10:25 as threshold — works for both resolutions.
        if ib_df.index.time[-1] >= time(10, 25):
            ib_status = "complete"
        else:
            ib_status = "partial"
        ib_high = ib_df['high'].max()
        ib_low = ib_df['low'].min()

    ib_range = round(ib_high - ib_low, 2) if ib_high is not None and ib_low is not None else None
    ib_mid = round((ib_high + ib_low) / 2, 2) if ib_high is not None and ib_low is not None else None

    # ATR-normalized IB width (computed after atr14 is read below, placeholder here)
    ib_atr_ratio = None
    ib_width_class = "unknown"

    # Current bar (latest available)
    current_bar = available_df.iloc[-1]
    current_price = round(current_bar['close'], 2)
    current_open = round(current_bar['open'], 2)
    current_high = round(current_bar['high'], 2)
    current_low = round(current_bar['low'], 2)
    current_volume = int(current_bar['volume'])
    current_vwap = round(current_bar['vwap'], 2) if 'vwap' in current_bar else None

    # Pull indicators
    ema20 = round(current_bar['ema20'], 2) if 'ema20' in current_bar else None
    ema50 = round(current_bar['ema50'], 2) if 'ema50' in current_bar else None
    ema200 = round(current_bar['ema200'], 2) if 'ema200' in current_bar else None
    rsi14 = round(current_bar['rsi14'], 2) if 'rsi14' in current_bar else None
    atr14 = round(current_bar['atr14'], 2) if 'atr14' in current_bar else None

    # ADX(14) — trend strength indicator (Wilder smoothing from 1-min OHLC)
    adx14 = _compute_adx(available_df, period=14)

    # Bollinger Bands BB(20,2) from 5-min resampled closes
    bb = _compute_bollinger_bands(available_df, current_time)

    # ATR-normalized IB width (Dalton framework)
    # Narrow: < 0.7x ATR — high trend potential, breakout likely
    # Normal: 0.7-1.3x ATR — standard auction, any day type possible
    # Wide:   1.3-2.0x ATR — reduced trend potential, balance/neutral more likely
    # Extreme: > 2.0x ATR — most of move done, balance day skew expected
    if ib_range and atr14 and atr14 > 0:
        ib_atr_ratio = round(ib_range / atr14, 2)
        if ib_atr_ratio < 0.7:
            ib_width_class = "narrow"
        elif ib_atr_ratio < 1.3:
            ib_width_class = "normal"
        elif ib_atr_ratio < 2.0:
            ib_width_class = "wide"
        else:
            ib_width_class = "extreme"

    # Price location vs IB
    if ib_range:
        upper_third = ib_high - (ib_range / 3)
        lower_third = ib_low + (ib_range / 3)
        if current_price >= upper_third:
            location = "upper_third_hug"
        elif current_price <= lower_third:
            location = "lower_third_hug"
        else:
            location = "middle"
    else:
        location = "ib_incomplete"

    # Extension magnitude (how far price has moved beyond IB)
    extension_pts = 0.0
    extension_direction = "none"
    extension_multiple = 0.0
    if ib_range and ib_range > 0 and current_price and ib_high and ib_low:
        above = max(0, current_price - ib_high)
        below = max(0, ib_low - current_price)
        if above > below:
            extension_pts = round(above, 2)
            extension_direction = "up"
        elif below > above:
            extension_pts = round(below, 2)
            extension_direction = "down"
        extension_multiple = round(max(above, below) / ib_range, 2)

    return {
        "ib_status": ib_status,
        "ib_high": round(ib_high, 2) if ib_high else None,
        "ib_low": round(ib_low, 2) if ib_low else None,
        "ib_range": ib_range,
        "ib_mid": ib_mid,
        "price_vs_ib": location,
        "price_vs_vwap": ("above" if current_price > current_vwap else "below" if current_price < current_vwap else "at") if current_vwap is not None else "no_vwap",
        "current_close": current_price,
        "current_open": current_open,
        "current_high": current_high,
        "current_low": current_low,
        "current_volume": current_volume,
        "current_vwap": current_vwap,
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "rsi14": rsi14,
        "atr14": atr14,
        "adx14": adx14,
        "bb_upper": bb["bb_upper"],
        "bb_lower": bb["bb_lower"],
        "bb_mid": bb["bb_mid"],
        "bb_position": bb["bb_position"],
        "bb_width": bb["bb_width"],
        "ib_atr_ratio": ib_atr_ratio,
        "ib_width_class": ib_width_class,
        "extension_pts": extension_pts,
        "extension_direction": extension_direction,
        "extension_multiple": extension_multiple,
        "note": "IB location + technical indicators + ATR regime from CSV (no lookahead)"
    }