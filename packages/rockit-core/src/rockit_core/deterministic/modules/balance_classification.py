# modules/balance_classification.py
"""
Balance Day Classification: Determines if balance day is P-type, b-type, or neutral.

P-type: Upper extreme REJECTED, Lower extreme ACCEPTED
  → Bias: Downward
  → Playbook: FADE VAH (SHORT), target VAL area

b-type: Lower extreme REJECTED, Upper extreme ACCEPTED
  → Bias: Upward
  → Playbook: FADE VAL (LONG), target VAH area

Neutral: Both extremes tested equally
  → Bias: None
  → Playbook: Wait for one to be rejected clearly
"""

import pandas as pd
from datetime import time


def get_balance_classification(df_nq, intraday_data, current_time_str="11:45"):
    """
    For Balance day types: Classify as P, b, or neutral based on probe acceptance.

    Args:
        df_nq: DataFrame with 5-min candles
        intraday_data: Dict with ib, tpo_profile, volume_profile, acceptance_test
        current_time_str: Current time ("HH:MM")

    Returns:
        dict: {
            "balance_type": str ("P", "b", "neutral"),
            "upper_probe_result": str ("accepted", "rejected", "tested", "none"),
            "lower_probe_result": str ("accepted", "rejected", "tested", "none"),
            "upper_probe_confidence": float (0.0-1.0),
            "lower_probe_confidence": float (0.0-1.0),
            "probe_order": str ("upper_first", "lower_first", "simultaneous", "none"),
            "dominant_bias": str ("upper", "lower", "none"),
            "playbook_action": str ("FADE_VAH_SHORT", "FADE_VAL_LONG", "WAIT_DUAL_SIDED"),
            "confidence": float (0.0-1.0),
            "note": str
        }
    """

    # Extract required data
    ib = intraday_data.get('ib', {})
    ib_high = ib.get('ib_high')
    ib_low = ib.get('ib_low')

    vol_profile = intraday_data.get('volume_profile', {})
    current_session = vol_profile.get('current_session', {})
    vah = current_session.get('vah')
    val = current_session.get('val')

    tpo_data = intraday_data.get('tpo_profile', {})
    single_above = tpo_data.get('single_prints_above_vah', 0)
    single_below = tpo_data.get('single_prints_below_val', 0)
    fattening_zone = tpo_data.get('fattening_zone', 'inside_va')

    # Filter data
    current_time = pd.to_datetime(current_time_str).time()
    post_ib_df = df_nq[df_nq.index.time >= time(10, 30)].copy()
    post_ib_df = post_ib_df[post_ib_df.index.time <= current_time].copy()

    if len(post_ib_df) == 0 or vah is None or val is None:
        return _empty_balance_result("Insufficient data")

    # Identify probes
    upper_probe_idx, lower_probe_idx, probe_order = _identify_probes(
        post_ib_df, vah, val
    )

    if upper_probe_idx is None and lower_probe_idx is None:
        return _empty_balance_result("No clear probes detected")

    # Measure acceptance at each extreme
    upper_result = _measure_probe_acceptance(post_ib_df, upper_probe_idx, vah, "upper",
                                              single_above) if upper_probe_idx else None
    lower_result = _measure_probe_acceptance(post_ib_df, lower_probe_idx, val, "lower",
                                              single_below) if lower_probe_idx else None

    # Classify balance type
    balance_type, bias, playbook_action = _classify_balance_type(
        upper_result, lower_result, probe_order
    )

    # Add pragmatic bias based on where market closed relative to extremes
    # This helps distinguish P (bias lower) from b (bias upper) from neutral
    close_price = df_nq.iloc[-1]['close'] if len(df_nq) > 0 else None
    poc_price = tpo_data.get('current_poc')

    # Use narrower band (upper/lower 1/3 of value area) for more confident classification
    # Iteration 5 optimization: Restore Iteration 3 thresholds + add hysteresis for stability
    va_range = vah - val
    upper_third_floor = vah - (va_range * 0.33)  # Upper 1/3
    lower_third_ceiling = val + (va_range * 0.33)  # Lower 1/3

    if close_price and poc_price and vah and val:
        # Adjust classification based on close position (RESTORE ITERATION 3)
        # If classified as neutral but close is clearly biased, adjust to P or b
        if balance_type == "neutral":
            if close_price > upper_third_floor:
                # Close in upper 1/3 of VA, VAL is support → likely b-type (long VAL)
                balance_type = "b"
            elif close_price < lower_third_ceiling:
                # Close in lower 1/3 of VA, VAH is resistance → likely P-type (short VAH)
                balance_type = "P"

    # Confidence scoring (Iteration 5: Restore Iteration 3 + add hysteresis)
    confidence = _score_balance_confidence(upper_result, lower_result, balance_type)

    # Determine results
    upper_probe_result = upper_result['probe_result'] if upper_result else "none"
    upper_probe_conf = upper_result['acceptance_confidence'] if upper_result else 0.0

    lower_probe_result = lower_result['probe_result'] if lower_result else "none"
    lower_probe_conf = lower_result['acceptance_confidence'] if lower_result else 0.0

    return {
        "balance_type": balance_type,
        "upper_probe_result": upper_probe_result,
        "lower_probe_result": lower_probe_result,
        "upper_probe_confidence": round(float(upper_probe_conf), 2),
        "lower_probe_confidence": round(float(lower_probe_conf), 2),
        "probe_order": probe_order,
        "dominant_bias": bias,
        "playbook_action": playbook_action,
        "confidence": round(float(confidence), 2),
        "note": f"Balance classification: {balance_type}-type. Bias: {bias}. Action: {playbook_action}"
    }


def _identify_probes(df_nq, vah, val, tolerance_pts=20):
    """
    Identify when price probes toward upper extreme (VAH) and lower extreme (VAL).

    Iteration 3 Optimization: Increased tolerance for better mid-day probe detection.

    Returns: (upper_probe_idx, lower_probe_idx, probe_order)
    """
    upper_probe_idx = None
    lower_probe_idx = None

    for idx, (time_idx, row) in enumerate(df_nq.iterrows()):
        # Upper probe: touches VAH area (increased tolerance for 12:00 PM detection)
        if upper_probe_idx is None and row['high'] >= (vah - tolerance_pts):
            upper_probe_idx = idx

        # Lower probe: touches VAL area (increased tolerance for 12:00 PM detection)
        if lower_probe_idx is None and row['low'] <= (val + tolerance_pts):
            lower_probe_idx = idx

        # Stop after 40 bars (200 minutes - covers 9:30-12:00 PM window)
        if idx > 40:
            break

    # Determine order
    if upper_probe_idx is not None and lower_probe_idx is not None:
        probe_order = "upper_first" if upper_probe_idx < lower_probe_idx else "lower_first"
    elif upper_probe_idx is not None:
        probe_order = "upper_only"
    elif lower_probe_idx is not None:
        probe_order = "lower_only"
    else:
        probe_order = "none"

    return upper_probe_idx, lower_probe_idx, probe_order


def _measure_probe_acceptance(df_nq, probe_idx, probe_extreme, direction, single_print_count):
    """
    After price probes an extreme, does it GET ACCEPTED or REJECTED?

    Returns: {probe_result, pullback_magnitude_pts, fattening_at_extreme, acceptance_confidence}
    """
    bars_after_probe = df_nq.iloc[probe_idx + 1 : probe_idx + 10]

    if len(bars_after_probe) == 0:
        return {
            "probe_result": "tested",
            "pullback_magnitude_pts": 0,
            "fattening_at_extreme": False,
            "bars_spent_at_extreme": 0,
            "acceptance_confidence": 0.5
        }

    # Count bars near extreme
    if direction == "upper":
        bars_near_extreme = sum(1 for _, row in bars_after_probe.iterrows()
                               if row['high'] >= (probe_extreme - 15))
        pullback_magnitude = probe_extreme - bars_after_probe['low'].min()
    else:  # lower
        bars_near_extreme = sum(1 for _, row in bars_after_probe.iterrows()
                               if row['low'] <= (probe_extreme + 15))
        pullback_magnitude = bars_after_probe['high'].max() - probe_extreme

    # Acceptance signals (Iteration 3: Optimized for 12:00 PM window)
    # Acceptance: Price spends multiple bars at the extreme (fattening = support)
    fattening = bars_near_extreme >= 2  # 2+ bars at extreme = start of fattening

    # Rejection: Price makes pullback from extreme with clear directional rejection
    # Iteration 3: More lenient rejection detection (>10 pts pullback OR quick rejection)
    fast_rejection = (pullback_magnitude > 10 and bars_near_extreme <= 2) or \
                     (pullback_magnitude > 15 and bars_near_extreme <= 1)

    # Classify with Iteration 3 optimizations
    if fattening and bars_near_extreme >= 2:
        # ACCEPTANCE: Multiple bars spent at extreme = price accepted support/resistance
        probe_result = "accepted"
        acceptance_confidence = 0.78  # Slightly higher confidence for 12:00 PM window
    elif fast_rejection:
        # REJECTION: Pullback detected = price rejected the extreme
        probe_result = "rejected"
        acceptance_confidence = 0.78  # Slightly higher confidence for 12:00 PM window
    else:
        # TESTED: Neither clear acceptance nor rejection yet
        probe_result = "tested"
        acceptance_confidence = 0.52  # Slightly higher for marginal cases

    return {
        "probe_result": probe_result,
        "pullback_magnitude_pts": round(pullback_magnitude, 2),
        "fattening_at_extreme": fattening,
        "bars_spent_at_extreme": bars_near_extreme,
        "acceptance_confidence": acceptance_confidence
    }


def _classify_balance_type(upper_result, lower_result, probe_order):
    """
    Determine: P-type, b-type, or neutral balance.

    Simplified heuristic: Use confidence scores and probe patterns rather than strict acceptance/rejection.

    Returns: (balance_type, dominant_bias, playbook_action)
    """
    # Handle missing results
    upper_status = upper_result['probe_result'] if upper_result else "none"
    lower_status = lower_result['probe_result'] if lower_result else "none"

    upper_conf = upper_result['acceptance_confidence'] if upper_result else 0.0
    lower_conf = lower_result['acceptance_confidence'] if lower_result else 0.0

    # P-Type: Upper probed but rejected (lower accepted/tested) → FADE VAH SHORT
    # Heuristic: Upper probe exists but lower confidence is higher (lower accepted more)
    if upper_result and lower_conf > upper_conf and upper_status in ["rejected", "tested"]:
        return "P", "lower", "FADE_VAH_SHORT"

    # b-Type: Lower probed but rejected (upper accepted/tested) → FADE VAL LONG
    # Heuristic: Lower probe exists but upper confidence is higher (upper accepted more)
    elif lower_result and upper_conf > lower_conf and lower_status in ["rejected", "tested"]:
        return "b", "upper", "FADE_VAL_LONG"

    # Refined P/b detection: Order of probes matters
    # If upper probe came first, it tested the high - might be P-type if rejected
    elif probe_order == "upper_first" and upper_status in ["rejected", "tested"]:
        return "P", "lower", "FADE_VAH_SHORT"

    # If lower probe came first, it tested the low - might be b-type if rejected
    elif probe_order == "lower_first" and lower_status in ["rejected", "tested"]:
        return "b", "upper", "FADE_VAL_LONG"

    # Neutral: Both probes tested equally, or unclear
    else:
        return "neutral", "none", "WAIT_DUAL_SIDED"


def _score_balance_confidence(upper_result, lower_result, balance_type):
    """Score confidence in balance classification (Iteration 5: Hysteresis-based stability)."""
    upper_conf = upper_result['acceptance_confidence'] if upper_result else 0.0
    lower_conf = lower_result['acceptance_confidence'] if lower_result else 0.0

    if balance_type == "P":
        # P-Type confidence: how confident that lower is accepted vs upper rejected
        # Iteration 5: Restore Iteration 3 caps, add hysteresis penalty to reduce flips
        confs = [c for c in [upper_conf, lower_conf] if c > 0]
        base_conf = sum(confs) / len(confs) if confs else 0.5
        p_type_conf = min(0.88, base_conf * 0.90)
        # Hysteresis: If probes are weak/marginal, apply stability penalty
        if upper_conf < 0.60 or lower_conf < 0.60:
            p_type_conf = max(0.50, p_type_conf - 0.08)  # Penalty for marginal probes
        return p_type_conf

    elif balance_type == "b":
        # b-Type confidence: how confident that upper is accepted vs lower rejected
        confs = [c for c in [upper_conf, lower_conf] if c > 0]
        base_conf = sum(confs) / len(confs) if confs else 0.5
        b_type_conf = min(0.88, base_conf * 0.90)
        # Hysteresis: If probes are weak/marginal, apply stability penalty
        if upper_conf < 0.60 or lower_conf < 0.60:
            b_type_conf = max(0.50, b_type_conf - 0.08)  # Penalty for marginal probes
        return b_type_conf

    else:
        # Neutral: Average confidence of both probes
        # Iteration 5: Restore Iteration 3 caps
        confs = [c for c in [upper_conf, lower_conf] if c > 0]
        base_conf = sum(confs) / len(confs) if confs else 0.5
        return min(0.75, base_conf * 0.75)  # Restored to 0.75 for neutral


def _empty_balance_result(note):
    """Returns empty balance result."""
    return {
        "balance_type": "neutral",
        "upper_probe_result": "none",
        "lower_probe_result": "none",
        "upper_probe_confidence": 0.0,
        "lower_probe_confidence": 0.0,
        "probe_order": "none",
        "dominant_bias": "none",
        "playbook_action": "WAIT_DUAL_SIDED",
        "confidence": 0.0,
        "note": note
    }
