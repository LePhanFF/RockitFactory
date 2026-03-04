"""
Edge Zone Analysis — IB edge zone detection with order flow context.

Market structure module: Detects when price is in the lower edge zone of IB,
checks for IB expansion, order flow quality, and confirmation signals (CVD
divergence, FVG confluence, 5-min inversion). Pure observation — no trade signals.

Detection window: 10:00-13:30 ET (post-OR, before PM morph)
"""

import pandas as pd
import numpy as np
from datetime import time as _time


def get_edge_zone_analysis(df_current, intraday_data=None, current_time_str="12:00", ib_history_5days=None):
    """
    Analyze edge zone conditions — IB expansion, order flow, confirmations.

    Market structure module: Pure observation — no trade signals.

    Args:
        df_current: DataFrame with 5-min OHLCV data for current session
        intraday_data: Dict with ib, volume_profile, fvg_detection, etc.
        current_time_str: Current time ("HH:MM" format)
        ib_history_5days: List of IB ranges for last 5 days (for expansion check)

    Returns:
        dict: Edge zone status, IB expansion, order flow quality, confirmations
    """
    # Only active 10:00-13:30 ET
    current_time = pd.to_datetime(current_time_str).time()
    if current_time < _time(10, 0) or current_time >= _time(13, 30):
        return {"note": "Outside Edge Fade window (10:00-13:30)"}

    if intraday_data is None:
        intraday_data = {}

    # Constants
    EDGE_ZONE_PCT = 0.25  # Lower 25% of IB
    IB_EXPANSION_RATIO = 1.2  # Only flag when IB >= 1.2x recent avg
    MAX_BEARISH_EXT = 0.30  # Max extension below IBL (as % of IB)
    CVD_LOOKBACK = 10  # Bars for CVD divergence
    CVD_PRICE_POSITION_MAX = 0.40  # Price in lower 40% of range

    # Extract IB data
    ib_data = intraday_data.get('ib', {})
    ib_high = ib_data.get('ib_high')
    ib_low = ib_data.get('ib_low')
    ib_range = ib_data.get('ib_range')

    if ib_high is None or ib_low is None or ib_range is None or ib_range <= 0:
        return {"note": "Missing or invalid IB data"}

    ib_mid = (ib_high + ib_low) / 2

    # Check IB expansion (wider IB = overextension = better mean reversion)
    ib_expanded = True
    if ib_history_5days and len(ib_history_5days) >= 5:
        recent_avg = np.mean(ib_history_5days[-5:])
        ib_ratio = ib_range / recent_avg if recent_avg > 0 else 1.0
        ib_expanded = ib_ratio >= IB_EXPANSION_RATIO

    if not ib_expanded:
        return {
            "ib_expanded": False,
            "note": "IB not expanded enough (choppy session)"
        }

    # Get current price and delta
    if len(df_current) == 0:
        return {"note": "No current bar data"}

    current_bar = df_current.iloc[-1]
    current_price = current_bar.get('close', 0)
    current_delta = current_bar.get('delta', 0)
    if pd.isna(current_delta):
        current_delta = 0

    # Check if price is in edge zone (lower 25% of IB)
    edge_ceiling = ib_low + (ib_range * EDGE_ZONE_PCT)
    in_edge_zone = ib_low <= current_price <= edge_ceiling

    # Check bearish extension (price dropped > 30% below IBL)
    session_low = df_current['low'].min()
    bearish_extension = (ib_low - session_low) / ib_range if ib_range > 0 else 0
    bearish_extended = bearish_extension >= MAX_BEARISH_EXT

    if bearish_extended:
        return {
            "bearish_extended": True,
            "note": "Extreme bearish extension (breakdown scenario, skip)"
        }

    # Order flow quality: delta > 0 required
    delta_positive = current_delta > 0

    if not delta_positive:
        return {
            "delta_positive": False,
            "note": "Delta not positive (selling pressure)"
        }

    # Order flow quality checks (2-of-3 required for entry)
    of_quality = 0

    # 1. Delta percentile (approximate if delta field exists)
    if len(df_current) >= 10:
        recent_deltas = df_current['delta'].tail(10).fillna(0)
        if len(recent_deltas) > 0:
            delta_percentile = (recent_deltas <= current_delta).sum() / len(recent_deltas) * 100
            if delta_percentile >= 60:
                of_quality += 1
    else:
        # Not enough history, assume good
        if current_delta > 0:
            of_quality += 1

    # 2. Volume spike (volume >= 1.0x recent average)
    current_volume = current_bar.get('volume', 0)
    if len(df_current) >= 5:
        recent_volume_avg = df_current['volume'].tail(5).mean()
        if current_volume >= recent_volume_avg:
            of_quality += 1
    else:
        if current_volume > 0:
            of_quality += 1

    # 3. Imbalance ratio (approximate with delta)
    # If delta is positive (buy volume > sell volume), that's imbalance
    if current_delta > 0:
        of_quality += 1

    # Entry confirmation models (optional, boost confidence)
    cvd_divergence = False
    fvg_confluence = False
    inversion_5m = False

    # CVD divergence: price near lows but CVD rising
    if len(df_current) >= CVD_LOOKBACK:
        lookback = df_current.tail(CVD_LOOKBACK)
        if 'cumulative_delta' in lookback.columns:
            cvd_values = lookback['cumulative_delta'].fillna(0)
            if len(cvd_values) >= 3:
                cvd_rising = cvd_values.iloc[-1] > cvd_values.iloc[-3]

                price_range = lookback['high'].max() - lookback['low'].min()
                price_position = (current_price - lookback['low'].min()) / price_range if price_range > 0 else 0.5

                cvd_divergence = cvd_rising and price_position < CVD_PRICE_POSITION_MAX

    # FVG confluence: price in bullish FVG
    fvg_detection = intraday_data.get('fvg_detection', {})
    fvg_bull_zones = fvg_detection.get('5min_fvg', [])  # Or any FVG timeframe
    for fvg in fvg_bull_zones:
        if isinstance(fvg, dict):
            fvg_type = fvg.get('type', '').lower()
            if 'bull' in fvg_type:
                bottom = fvg.get('bottom', 0)
                top = fvg.get('top', float('inf'))
                if bottom <= current_price <= top:
                    fvg_confluence = True
                    break

    # 5-min inversion: bearish-to-bullish candle reversal
    if len(df_current) >= 2:
        prior_bar = df_current.iloc[-2]
        prior_bullish = prior_bar.get('close', 0) > prior_bar.get('open', 0)
        current_bullish = current_bar.get('close', 0) > current_bar.get('open', 0)
        inversion_5m = (not prior_bullish) and current_bullish

    # Determine confidence
    confidence = "medium"
    has_confirmation = cvd_divergence or fvg_confluence or inversion_5m
    if has_confirmation:
        confidence = "high"

    return {
        "in_edge_zone": bool(in_edge_zone),
        "ib_expanded": bool(ib_expanded),
        "bearish_extended": bool(bearish_extended),
        "delta_positive": bool(delta_positive),
        "of_quality": int(of_quality),
        "cvd_divergence": bool(cvd_divergence),
        "fvg_confluence": bool(fvg_confluence),
        "inversion_5m": bool(inversion_5m),
        "confidence": confidence,
        "note": f"Edge zone: in_zone={in_edge_zone}, of_quality={of_quality}/3, CVD={cvd_divergence}, FVG={fvg_confluence}, inv={inversion_5m}"
    }


# Keep old name as alias for backward compatibility during transition
get_edge_fade_setup = get_edge_zone_analysis
