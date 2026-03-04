# modules/dalton.py
"""
Dalton TPO trend analysis module.
Implements v5.15 trend confirmation and strength quantification rules.

Trend Confirmation:
- 2x 5-min bars closing outside IB range, OR
- 1x 30-min TPO period holding outside IB range

Trend Strength (IB extension multiple):
- Weak: <0.5x IB extension
- Moderate: 0.5-1.0x IB extension + >=1 30-min bracket
- Strong: 1.0-2.0x IB extension + >=60 min stacked brackets
- Super: >2.0x IB extension OR extreme DPOC + >=60 min hold
"""

import pandas as pd
from datetime import time


def get_trend_analysis(df_nq, intraday_data, current_time_str="11:45"):
    """
    Main entry point for trend analysis.

    Args:
        df_nq: DataFrame with 5-min price data
        intraday_data: Dict containing ib, dpoc_migration, core_confluences
        current_time_str: Current snapshot time

    Returns:
        dict: {
            'trend_confirmed': bool,
            'confirmation_type': str,
            'trend_strength': str,
            'ib_extension_multiple': float,
            'brackets_outside_ib': int,
            'minutes_outside_ib': int,
            'direction': str,
            'morph_status': str
        }
    """
    # Parse current time
    try:
        current_time = pd.to_datetime(current_time_str).time()
    except:
        current_time = time(11, 45)

    # Filter to only data up to current_time
    available_df = df_nq[df_nq.index.time <= current_time].copy()

    if len(available_df) == 0:
        return _empty_result("no_data_up_to_current_time")

    # Extract IB data from intraday_data
    ib_data = intraday_data.get('ib', {})
    ib_high = ib_data.get('ib_high')
    ib_low = ib_data.get('ib_low')
    ib_range = ib_data.get('ib_range')
    current_close = ib_data.get('current_close')

    if ib_high is None or ib_low is None or ib_range is None or ib_range == 0:
        return _empty_result("ib_data_incomplete")

    # Get DPOC migration data for trend strength enhancement
    dpoc_data = intraday_data.get('dpoc_migration', {})
    dpoc_regime = dpoc_data.get('dpoc_regime', '')
    net_migration = dpoc_data.get('net_migration_pts', 0)

    # Get core confluences for additional context
    confluences = intraday_data.get('core_confluences', {})

    # Session data (post-IB only for trend analysis)
    post_ib_df = available_df[available_df.index.time >= time(10, 30)].copy()

    if len(post_ib_df) == 0:
        return _empty_result("pre_1030")

    # === Compute IB Extension Multiple ===
    ib_mid = (ib_high + ib_low) / 2
    if current_close > ib_high:
        # Bullish extension
        extension = current_close - ib_high
        direction = "up"
        ib_extension_multiple = extension / ib_range if ib_range > 0 else 0
    elif current_close < ib_low:
        # Bearish extension
        extension = ib_low - current_close
        direction = "down"
        ib_extension_multiple = extension / ib_range if ib_range > 0 else 0
    else:
        # Inside IB
        direction = "flat"
        ib_extension_multiple = 0

    # === Count 5-min bars Closing Outside IB ===
    closes_above_ibh = post_ib_df[post_ib_df['close'] > ib_high]
    closes_below_ibl = post_ib_df[post_ib_df['close'] < ib_low]

    bars_above_ibh = len(closes_above_ibh)
    bars_below_ibl = len(closes_below_ibl)

    # Directional focus
    if direction == "up":
        bars_outside_ib = bars_above_ibh
    elif direction == "down":
        bars_outside_ib = bars_below_ibl
    else:
        bars_outside_ib = max(bars_above_ibh, bars_below_ibl)

    # === Count 30-min TPO Brackets Outside IB ===
    post_ib_df['period'] = post_ib_df.index.floor('30min')
    periods = post_ib_df['period'].unique()

    brackets_outside_ib = 0
    minutes_outside_ib = 0

    for period in sorted(periods):
        period_df = post_ib_df[post_ib_df['period'] == period]

        # Check if entire period is outside IB (trending bracket)
        if direction == "up":
            if period_df['low'].min() > ib_high:
                brackets_outside_ib += 1
                minutes_outside_ib += len(period_df) * 1  # 1-min bars
        elif direction == "down":
            if period_df['high'].max() < ib_low:
                brackets_outside_ib += 1
                minutes_outside_ib += len(period_df) * 1
        else:
            # For flat, check both directions
            if period_df['low'].min() > ib_high or period_df['high'].max() < ib_low:
                brackets_outside_ib += 1
                minutes_outside_ib += len(period_df) * 1

    # BUG FIX: DO NOT overwrite minutes_outside_ib calculation
    # Removed lines that were overwriting the correct bracket-based calculation:
    # if direction == "up":
    #     minutes_outside_ib = bars_above_ibh * 5
    # elif direction == "down":
    #     minutes_outside_ib = bars_below_ibl * 5

    # === Determine Trend Confirmation ===
    # 2x 5-min bars closing outside IB
    two_5min_confirmation = bars_outside_ib >= 2

    # 1x 30-min TPO period holding outside IB
    one_30min_confirmation = brackets_outside_ib >= 1

    # Potential morph (15-min shaping but not confirmed)
    potential_morph = bars_outside_ib >= 1 and brackets_outside_ib == 0

    if one_30min_confirmation:
        trend_confirmed = True
        confirmation_type = "30min_tpo"
    elif two_5min_confirmation:
        trend_confirmed = True
        confirmation_type = "2x_5min"
    elif potential_morph:
        trend_confirmed = False
        confirmation_type = "potential_morph"
    else:
        trend_confirmed = False
        confirmation_type = "none"

    # === Determine Morph Status ===
    if brackets_outside_ib >= 2 and minutes_outside_ib >= 60:
        morph_status = "super_trending_locked"
    elif one_30min_confirmation:
        morph_status = "morphing_confirmed"
    elif potential_morph:
        morph_status = "potential_morph"
    else:
        morph_status = "none"

    # === Determine Trend Strength ===
    # Check for extreme DPOC migration (Super trend condition)
    extreme_dpoc = abs(net_migration) >= 50  # Significant migration

    # Super: >2.0x IB extension OR extreme DPOC + >=60 min hold
    if ib_extension_multiple > 2.0:
        trend_strength = "Super"
    elif extreme_dpoc and minutes_outside_ib >= 60:
        trend_strength = "Super"
    # Strong: 1.0-2.0x IB extension + >=60 min stacked brackets
    elif ib_extension_multiple >= 1.0 and minutes_outside_ib >= 60:
        trend_strength = "Strong"
    # Moderate: 0.5-1.0x IB extension + >=1 30-min bracket
    elif ib_extension_multiple >= 0.5 and brackets_outside_ib >= 1:
        trend_strength = "Moderate"
    # Weak: <0.5x IB extension
    else:
        trend_strength = "Weak"

    # Override strength based on DPOC regime
    if dpoc_regime == "trending_on_the_move" and trend_strength in ["Weak", "Moderate"]:
        trend_strength = "Strong"
    elif dpoc_regime == "trending_fading_momentum" and trend_strength == "Super":
        trend_strength = "Strong"

    return {
        "trend_confirmed": bool(trend_confirmed),
        "confirmation_type": confirmation_type,
        "trend_strength": trend_strength,
        "ib_extension_multiple": round(float(ib_extension_multiple), 2),
        "brackets_outside_ib": int(brackets_outside_ib),
        "minutes_outside_ib": int(minutes_outside_ib),
        "direction": direction,
        "morph_status": morph_status,
        "bars_outside_ib": int(bars_outside_ib),
        "dpoc_regime": dpoc_regime,
        "note": "Trend analysis based on Dalton TPO rules. confirmation_type: 30min_tpo (strongest), 2x_5min (confirmed), potential_morph (watch), none. morph_status: super_trending_locked (>=60min hold), morphing_confirmed (30min TPO), potential_morph (shaping)."
    }


def _empty_result(note):
    """Return empty result dict with note."""
    return {
        "trend_confirmed": False,
        "confirmation_type": "none",
        "trend_strength": "Weak",
        "ib_extension_multiple": 0.0,
        "brackets_outside_ib": 0,
        "minutes_outside_ib": 0,
        "direction": "flat",
        "morph_status": "none",
        "bars_outside_ib": 0,
        "dpoc_regime": "",
        "note": note
    }
