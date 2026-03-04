# modules/acceptance_test.py
"""
Acceptance Test Module: Detects whether price breakouts/probes are ACCEPTED or REJECTED.

Per Dalton's auction market theory:
- ACCEPTED = Price holds at level, TPO fattens, multiple bars spent there
- REJECTED = Price tests level but quickly pulls back, single prints, widening TPO

Used for:
1. Trend day confirmation (is the breakout real?)
2. Balance day classification (which extreme was accepted vs rejected?)
3. Reversion confirmation (which side to fade?)

Critical distinction from mechanical breakout detection:
- Mechanical: "Did price close outside IB?"
- Acceptance: "Is the market comfortable at that price?"
"""

import pandas as pd
import numpy as np
from datetime import time


def get_acceptance_test(df_nq, intraday_data, current_time_str="11:45"):
    """
    Main entry point: Tests whether initial breakout (outside IB) is being accepted or rejected.

    For TREND DAYS: Single breakout (up or down)
    For BALANCE DAYS: Will be called separately for upper and lower probes

    Args:
        df_nq: DataFrame with 5-min candles (pre-filtered to current_time)
        intraday_data: Dict with ib, dpoc_migration, tpo_profile, volume_profile
        current_time_str: Current snapshot time ("HH:MM")

    Returns:
        dict: {
            "breakout_level": float,
            "breakout_direction": str ("up", "down", "none"),
            "breakout_confirmed_at": str ("HH:MM"),
            "pullback_occurred": bool,
            "pullback_type": str ("fast_rejection", "hesitant_reclaim", "holding", "none"),
            "pullback_crossed_breakout": bool,
            "bars_to_pullback": int,
            "minutes_to_pullback": float,
            "pullback_magnitude_pts": float,
            "pullback_magnitude_pct_ib": float,
            "acceptance_confidence": float (0.0-1.0),
            "rejection_confidence": float (0.0-1.0),
            "recommended_action": str ("FADE", "FOLLOW", "STANDBY"),
            "note": str
        }
    """

    # Extract required data
    ib = intraday_data.get('ib', {})
    ib_high = ib.get('ib_high')
    ib_low = ib.get('ib_low')
    ib_range = ib.get('ib_range')

    dpoc_data = intraday_data.get('dpoc_migration', {})
    dpoc_regime = dpoc_data.get('dpoc_regime', '')

    tpo_data = intraday_data.get('tpo_profile', {})
    single_prints_above = tpo_data.get('single_prints_above_vah', 0)
    single_prints_below = tpo_data.get('single_prints_below_val', 0)

    # Filter data to post-10:30 only
    current_time = pd.to_datetime(current_time_str).time()
    post_ib_df = df_nq[df_nq.index.time >= time(10, 30)].copy()
    post_ib_df = post_ib_df[post_ib_df.index.time <= current_time].copy()

    if len(post_ib_df) == 0 or ib_high is None or ib_low is None:
        return _empty_result("Insufficient data (pre-10:30 or no post-IB activity)")

    # Detect breakout direction
    breakout_level, breakout_direction, breakout_bar_idx = _detect_breakout(
        post_ib_df, ib_high, ib_low
    )

    if breakout_direction == "none":
        return _empty_result("No breakout detected (price still within IB)")

    # Detect pullback after breakout
    pullback_occurred, pullback_crossed, bars_to_cross, pullback_mag = _detect_pullback(
        post_ib_df, breakout_level, breakout_direction, breakout_bar_idx
    )

    # Classify pullback type
    pullback_type = _classify_pullback_type(
        pullback_crossed, bars_to_cross, pullback_mag, ib_range, dpoc_regime
    )

    # Score acceptance vs rejection
    acceptance_conf, rejection_conf = _score_confidence(
        pullback_type, dpoc_regime, single_prints_above, single_prints_below,
        breakout_direction, bars_to_cross
    )

    # Determine recommended action
    if rejection_conf > 0.75 and pullback_type in ["fast_rejection", "hesitant_reclaim"]:
        recommended_action = "FADE"
    elif acceptance_conf > 0.75 and pullback_type == "holding":
        recommended_action = "FOLLOW"
    else:
        recommended_action = "STANDBY"

    # Calculate minutes to pullback
    minutes_to_pullback = bars_to_cross * 5 if bars_to_cross else None

    # Calculate pullback as % of IB
    pullback_pct_ib = None
    if pullback_mag and ib_range > 0:
        pullback_pct_ib = round((pullback_mag / ib_range) * 100, 1)

    # Breakout time
    breakout_time = None
    try:
        breakout_time = post_ib_df.index[breakout_bar_idx].strftime('%H:%M')
    except:
        breakout_time = None

    return {
        "breakout_level": round(float(breakout_level), 2) if breakout_level else None,
        "breakout_direction": breakout_direction,
        "breakout_confirmed_at": breakout_time,
        "pullback_occurred": bool(pullback_occurred),
        "pullback_type": pullback_type,
        "pullback_crossed_breakout": bool(pullback_crossed),
        "bars_to_pullback": int(bars_to_cross) if bars_to_cross else None,
        "minutes_to_pullback": round(float(minutes_to_pullback), 1) if minutes_to_pullback else None,
        "pullback_magnitude_pts": round(float(pullback_mag), 2) if pullback_mag else None,
        "pullback_magnitude_pct_ib": pullback_pct_ib,
        "acceptance_confidence": float(acceptance_conf),
        "rejection_confidence": float(rejection_conf),
        "recommended_action": recommended_action,
        "note": f"Breakout {breakout_direction} at {breakout_level}. Type: {pullback_type}. Confidence: Acceptance {acceptance_conf}, Rejection {rejection_conf}"
    }


def _detect_breakout(df_nq, ib_high, ib_low):
    """Identifies first close outside IB (breakout signal)."""
    for idx, (time_idx, row) in enumerate(df_nq.iterrows()):
        if row['close'] > ib_high:
            return ib_high, "up", idx
        elif row['close'] < ib_low:
            return ib_low, "down", idx
    return None, "none", None


def _detect_pullback(df_nq, breakout_level, breakout_direction, breakout_idx):
    """
    After breakout, detects if price pulls back through the breakout level.

    Returns: (pullback_occurred, pullback_crossed, bars_to_cross, pullback_magnitude)
    """
    bars_after = df_nq.iloc[breakout_idx + 1 : breakout_idx + 11]  # Look 10 bars ahead

    if len(bars_after) == 0:
        return False, False, None, None

    pullback_occurred = False
    pullback_crossed = False
    bars_to_cross = None
    max_pullback = 0

    for bar_count, (time_idx, row) in enumerate(bars_after.iterrows(), 1):
        if breakout_direction == "up":
            # Measure pullback from high
            pullback_magnitude = breakout_level - row['low']
            if pullback_magnitude > 0:
                pullback_occurred = True
                max_pullback = max(max_pullback, pullback_magnitude)
            # Check if closed back below breakout
            if row['close'] < breakout_level:
                pullback_crossed = True
                bars_to_cross = bar_count
                break

        elif breakout_direction == "down":
            # Measure pullback from low
            pullback_magnitude = row['high'] - breakout_level
            if pullback_magnitude > 0:
                pullback_occurred = True
                max_pullback = max(max_pullback, pullback_magnitude)
            # Check if closed back above breakout
            if row['close'] > breakout_level:
                pullback_crossed = True
                bars_to_cross = bar_count
                break

    return pullback_occurred, pullback_crossed, bars_to_cross, max_pullback


def _classify_pullback_type(pullback_crossed, bars_to_cross, pullback_magnitude_pts,
                            ib_range, dpoc_regime):
    """
    Classifies pullback as acceptance or rejection signal.

    Returns: "fast_rejection", "hesitant_reclaim", "holding", "none"
    """
    if not pullback_crossed:
        # Price never came back through breakout level
        if dpoc_regime in ["trending_on_the_move"]:
            return "holding"  # Still holding = acceptance
        else:
            return "none"

    # FAST rejection = crossed back in <= 3 bars (very decisive)
    if bars_to_cross <= 3:
        return "fast_rejection"

    # HESITANT = crossed back in 4-6 bars (uncertain)
    elif bars_to_cross <= 6:
        return "hesitant_reclaim"

    # HOLDING = crossed back in 7+ bars (held strong before reclaiming)
    else:
        return "holding"


def _score_confidence(pullback_type, dpoc_regime, single_prints_above, single_prints_below,
                      breakout_direction, bars_to_cross):
    """
    Scores acceptance vs rejection confidence (0.0-1.0).
    """
    acceptance_score = 0.0
    rejection_score = 0.0

    # Pullback type weights
    if pullback_type == "fast_rejection":
        rejection_score += 0.45  # Strong rejection signal
    elif pullback_type == "hesitant_reclaim":
        rejection_score += 0.25  # Weak rejection signal
    elif pullback_type == "holding":
        acceptance_score += 0.40  # Holding signals acceptance

    # DPOC regime weights
    if dpoc_regime in ["trending_on_the_move"]:
        acceptance_score += 0.35
    elif dpoc_regime in ["trending_fading_momentum"]:
        rejection_score += 0.25
    elif dpoc_regime in ["potential_bpr_reversal"]:
        rejection_score += 0.30

    # TPO shape weights (single print skew indicates rejection)
    if breakout_direction == "up" and single_prints_above >= 5:
        rejection_score += 0.15  # Many single prints at high = testing, not accepting
    elif breakout_direction == "down" and single_prints_below >= 5:
        rejection_score += 0.15

    # Speed penalty
    if bars_to_cross and bars_to_cross <= 3:
        rejection_score += 0.05  # Fast = decisive rejection

    # Normalize to 0.0-1.0
    total = acceptance_score + rejection_score
    if total > 0:
        acceptance_confidence = acceptance_score / total
        rejection_confidence = rejection_score / total
    else:
        acceptance_confidence = 0.5
        rejection_confidence = 0.5

    return round(min(1.0, acceptance_confidence), 2), round(min(1.0, rejection_confidence), 2)


def _empty_result(note):
    """Returns empty result with note."""
    return {
        "breakout_level": None,
        "breakout_direction": "none",
        "breakout_confirmed_at": None,
        "pullback_occurred": False,
        "pullback_type": "none",
        "pullback_crossed_breakout": False,
        "bars_to_pullback": None,
        "minutes_to_pullback": None,
        "pullback_magnitude_pts": None,
        "pullback_magnitude_pct_ib": None,
        "acceptance_confidence": 0.5,
        "rejection_confidence": 0.5,
        "recommended_action": "STANDBY",
        "note": note
    }
