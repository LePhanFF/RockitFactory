# modules/ib_location.py
import pandas as pd
from datetime import time

HIGH_ATR_THRESHOLD = 20.0
LOW_ATR_THRESHOLD = 12.0

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
        "ib_atr_ratio": ib_atr_ratio,
        "ib_width_class": ib_width_class,
        "extension_pts": extension_pts,
        "extension_direction": extension_direction,
        "extension_multiple": extension_multiple,
        "note": "IB location + technical indicators + ATR regime from CSV (no lookahead)"
    }