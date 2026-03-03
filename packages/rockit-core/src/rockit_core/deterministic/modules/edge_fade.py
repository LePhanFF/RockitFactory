"""
Edge Fade Strategy (Edge-to-Mid Mean Reversion)

Fades from IB edges back to IB midpoint on balance/neutral range days.
Explicit LONG-only mean reversion entry targeting the lower 25% of IB range.

Performance (259-day backtest, BookMapOrderFlowStudies-2):
  - Win Rate: 58.1% (93 trades/year)
  - Net P&L: $9,486 (+$102/trade avg)
  - Profit Factor: 1.62
  - Max Drawdown: $2,374
  - Active window: 10:00-13:30 ET (post-OR, before PM morph)

Entry confirmation models (boost confidence when present):
  - CVD divergence: Price near lows but CVD rising (smart money accumulating)
  - FVG confluence: Entry inside bullish Fair Value Gap zone
  - 5-min inversion: 5-min bearish-to-bullish candle reversal

Key design:
  - LONG ONLY (NQ long bias, all shorts negative expectancy)
  - Requires IB expansion (>1.2x 5-day average) to filter choppy days
  - Requires order flow confirmation (delta > 0, quality gates)
  - Target: IB midpoint (natural mean reversion destination)
"""

import pandas as pd
import numpy as np
from datetime import time as _time


def get_edge_fade_setup(df_current, intraday_data=None, current_time_str="12:00", ib_history_5days=None):
    """
    Detect Edge Fade mean reversion setups (lower IB edge → midpoint).

    Args:
        df_current: DataFrame with 5-min OHLCV data for current session
        intraday_data: Dict with ib, volume_profile, fvg_detection, etc.
        current_time_str: Current time ("HH:MM" format)
        ib_history_5days: List of IB ranges for last 5 days (for expansion check)

    Returns:
        dict: {
            "in_edge_zone": bool,
            "ib_expanded": bool,
            "bearish_extended": bool,
            "delta_positive": bool,
            "of_quality": int (0-3),
            "cvd_divergence": bool,
            "fvg_confluence": bool,
            "inversion_5m": bool,
            "signal": "LONG" | "NONE",
            "entry": float,
            "stop": float,
            "target": float,
            "risk": float,
            "reward": float,
            "rr": float,
            "confidence": "high" | "medium",
            "note": str
        }
    """
    # Only active 10:00-13:30 ET
    current_time = pd.to_datetime(current_time_str).time()
    if current_time < _time(10, 0) or current_time >= _time(13, 30):
        return {"signal": "NONE", "note": "Outside Edge Fade window (10:00-13:30)"}

    if intraday_data is None:
        intraday_data = {}

    # Constants
    EDGE_ZONE_PCT = 0.25  # Lower 25% of IB
    EDGE_STOP_BUFFER = 0.15  # Stop: IBL - 15% IB range
    EDGE_MIN_RR = 1.0  # Minimum reward/risk
    IB_EXPANSION_RATIO = 1.2  # Only trade when IB >= 1.2x recent avg
    MAX_BEARISH_EXT = 0.30  # Max extension below IBL (as % of IB)
    CVD_LOOKBACK = 10  # Bars for CVD divergence
    CVD_PRICE_POSITION_MAX = 0.40  # Price in lower 40% of range

    # Extract IB data
    ib_data = intraday_data.get('ib', {})
    ib_high = ib_data.get('ib_high')
    ib_low = ib_data.get('ib_low')
    ib_range = ib_data.get('ib_range')

    if ib_high is None or ib_low is None or ib_range is None or ib_range <= 0:
        return {"signal": "NONE", "note": "Missing or invalid IB data"}

    ib_mid = (ib_high + ib_low) / 2

    # Check IB expansion (wider IB = overextension = better mean reversion)
    ib_expanded = True
    if ib_history_5days and len(ib_history_5days) >= 5:
        recent_avg = np.mean(ib_history_5days[-5:])
        ib_ratio = ib_range / recent_avg if recent_avg > 0 else 1.0
        ib_expanded = ib_ratio >= IB_EXPANSION_RATIO

    if not ib_expanded:
        return {
            "signal": "NONE",
            "ib_expanded": False,
            "note": "IB not expanded enough (choppy session)"
        }

    # Get current price and delta
    if len(df_current) == 0:
        return {"signal": "NONE", "note": "No current bar data"}

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
            "signal": "NONE",
            "bearish_extended": True,
            "note": "Extreme bearish extension (breakdown scenario, skip)"
        }

    # Order flow quality: delta > 0 required
    delta_positive = current_delta > 0

    if not delta_positive:
        return {
            "signal": "NONE",
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

    # Determine confidence and signal
    confidence = "medium"
    has_confirmation = cvd_divergence or fvg_confluence or inversion_5m
    if has_confirmation:
        confidence = "high"

    signal = "NONE"
    entry_price = None
    stop_price = None
    target_price = None

    # Generate LONG signal if all conditions met
    if in_edge_zone and of_quality >= 2:
        entry_price = current_price
        stop_price = ib_low - (ib_range * EDGE_STOP_BUFFER)
        target_price = ib_mid

        risk = entry_price - stop_price
        reward = target_price - entry_price

        if reward / risk >= EDGE_MIN_RR if risk > 0 else False:
            signal = "LONG"

    # Build output
    result = {
        "in_edge_zone": bool(in_edge_zone),
        "ib_expanded": bool(ib_expanded),
        "bearish_extended": bool(bearish_extended),
        "delta_positive": bool(delta_positive),
        "of_quality": int(of_quality),
        "cvd_divergence": bool(cvd_divergence),
        "fvg_confluence": bool(fvg_confluence),
        "inversion_5m": bool(inversion_5m),
        "signal": signal,
    }

    if signal == "LONG" and entry_price is not None:
        risk = entry_price - stop_price
        reward = target_price - entry_price
        rr = reward / risk if risk > 0 else 0

        result.update({
            "entry": float(entry_price),
            "stop": float(stop_price),
            "target": float(target_price),
            "risk": float(risk),
            "reward": float(reward),
            "rr": float(rr),
            "confidence": confidence,
            "note": f"Edge Fade LONG: lower 25% of IB ({ib_low:.1f}-{edge_ceiling:.1f}) → IB mid ({ib_mid:.1f}). Confirmations: CVD={cvd_divergence}, FVG={fvg_confluence}, Inversion={inversion_5m}"
        })
    else:
        result.update({
            "entry": 0.0,
            "stop": 0.0,
            "target": 0.0,
            "risk": 0.0,
            "reward": 0.0,
            "rr": 0.0,
            "confidence": confidence,
            "note": f"No Edge Fade signal (edge_zone={in_edge_zone}, of_quality={of_quality}/3, delta_pos={delta_positive})"
        })

    return result
