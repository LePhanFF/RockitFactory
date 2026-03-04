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

Skew Analysis (Dalton framework):
  On a balance day, "value" (POC) tells you who's winning.
  - Value migrating above IB mid → buyers accepting (bullish skew)
  - Value migrating below IB mid → sellers accepting (bearish skew)
  - The seam is the pivot level separating bullish from bearish skew.

Morph Detection:
  Balance days tend to morph in PM session (12:00-16:00).
  - Neutral → P-structure (bearish morph): value migrating down
  - Neutral → b-structure (bullish morph): value migrating up
  - Trend morph: IB extension + sustained directional acceptance
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

    # Compute skew + seam (where is value forming relative to IB?)
    skew_result = _compute_skew(intraday_data)
    seam_level, seam_description = _compute_seam(intraday_data)

    # Detect morph (PM session balance→skew shifts)
    morph_result = _detect_morph(intraday_data, current_time_str, balance_type, seam_level)

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
        "skew": skew_result["skew"],
        "skew_strength": skew_result["skew_strength"],
        "skew_factors": skew_result["skew_factors"],
        "seam_level": seam_level,
        "seam_description": seam_description,
        "morph": morph_result,
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


def _compute_skew(intraday_data):
    """
    Determine balance day skew from volume profile, TPO, and DPOC.

    Scoring: Each factor contributes a vote (+1 bullish, -1 bearish, 0 neutral)
    - Volume POC above IB mid → +1
    - TPO POC above IB mid → +1
    - DPOC migrating up → +1
    - Fattening above VA → +1
    - Close in upper third → +1

    Skew = sum of votes / max possible (5)
    > 0 = bullish, < 0 = bearish, 0 = neutral
    """
    ib = intraday_data.get('ib', {})
    ib_high = ib.get('ib_high')
    ib_low = ib.get('ib_low')

    if ib_high is None or ib_low is None:
        return {"skew": "neutral", "skew_strength": 0.0, "skew_factors": _empty_skew_factors()}

    ib_mid = (ib_high + ib_low) / 2.0
    tolerance = 5.0  # POC within ±5 pts of IB mid = "at" (neutral)

    vol_profile = intraday_data.get('volume_profile', {})
    current_session = vol_profile.get('current_session', {})
    vol_poc = current_session.get('poc')
    vah = current_session.get('vah')
    val = current_session.get('val')

    tpo_data = intraday_data.get('tpo_profile', {})
    tpo_poc = tpo_data.get('current_poc')
    fattening_zone = tpo_data.get('fattening_zone', 'inside_va')

    dpoc_migration = intraday_data.get('dpoc_migration', {})
    dpoc_direction = dpoc_migration.get('direction', 'flat')

    current_close = ib.get('current_close')

    # Score each factor
    votes = 0

    # Factor 1: Volume POC vs IB mid
    if vol_poc is not None:
        if vol_poc > ib_mid + tolerance:
            vol_poc_position = "above"
            votes += 1
        elif vol_poc < ib_mid - tolerance:
            vol_poc_position = "below"
            votes -= 1
        else:
            vol_poc_position = "at"
    else:
        vol_poc_position = "at"

    # Factor 2: TPO POC vs IB mid
    if tpo_poc is not None:
        if tpo_poc > ib_mid + tolerance:
            tpo_poc_position = "above"
            votes += 1
        elif tpo_poc < ib_mid - tolerance:
            tpo_poc_position = "below"
            votes -= 1
        else:
            tpo_poc_position = "at"
    else:
        tpo_poc_position = "at"

    # Factor 3: DPOC direction
    if dpoc_direction == "up":
        dpoc_dir = "up"
        votes += 1
    elif dpoc_direction == "down":
        dpoc_dir = "down"
        votes -= 1
    else:
        dpoc_dir = "flat"

    # Factor 4: Fattening zone
    fat_zone = fattening_zone.lower() if isinstance(fattening_zone, str) else "inside_va"
    if fat_zone in ("above_vah", "at_vah"):
        votes += 1
    elif fat_zone in ("below_val", "at_val"):
        votes -= 1

    # Factor 5: Close position relative to VA
    if current_close is not None and vah is not None and val is not None:
        va_range = vah - val
        if va_range > 0:
            upper_third_floor = vah - (va_range * 0.33)
            lower_third_ceiling = val + (va_range * 0.33)
            if current_close > upper_third_floor:
                close_pos = "upper_third"
                votes += 1
            elif current_close < lower_third_ceiling:
                close_pos = "lower_third"
                votes -= 1
            else:
                close_pos = "middle"
        else:
            close_pos = "middle"
    else:
        close_pos = "middle"

    # Compute skew
    max_votes = 5
    skew_strength = round(abs(votes) / max_votes, 2)
    if votes > 0:
        skew = "bullish"
    elif votes < 0:
        skew = "bearish"
    else:
        skew = "neutral"

    skew_factors = {
        "vol_poc_vs_ib_mid": vol_poc_position,
        "tpo_poc_vs_ib_mid": tpo_poc_position,
        "dpoc_direction": dpoc_dir,
        "fattening_zone": fat_zone,
        "close_position": close_pos,
    }

    return {"skew": skew, "skew_strength": skew_strength, "skew_factors": skew_factors}


def _compute_seam(intraday_data):
    """
    Compute the seam level — the pivot that separates bullish from bearish skew.

    Weighted average of:
    - IB midpoint (weight 0.4)
    - Volume POC (weight 0.3)
    - TPO POC (weight 0.3)

    If all three agree (within 10 pts), seam = average.
    If they diverge, seam = IB mid (most reliable).
    """
    ib = intraday_data.get('ib', {})
    ib_high = ib.get('ib_high')
    ib_low = ib.get('ib_low')

    if ib_high is None or ib_low is None:
        return 0.0, "No IB data for seam calculation"

    ib_mid = (ib_high + ib_low) / 2.0

    vol_profile = intraday_data.get('volume_profile', {})
    vol_poc = vol_profile.get('current_session', {}).get('poc')

    tpo_data = intraday_data.get('tpo_profile', {})
    tpo_poc = tpo_data.get('current_poc')

    # Collect available levels
    levels = [ib_mid]
    weights = [0.4]
    descriptions = [f"IB mid {ib_mid:.2f}"]

    if vol_poc is not None:
        levels.append(vol_poc)
        weights.append(0.3)
    if tpo_poc is not None:
        levels.append(tpo_poc)
        weights.append(0.3)

    # Check agreement (within 10 pts)
    if len(levels) == 3:
        spread = max(levels) - min(levels)
        if spread <= 10:
            # All agree — weighted average
            total_weight = sum(weights)
            seam = sum(l * w for l, w in zip(levels, weights)) / total_weight
            desc = f"IB mid {ib_mid:.2f}, vol POC {vol_poc:.2f}, TPO POC {tpo_poc:.2f} — aligned (spread {spread:.1f} pts)"
        else:
            # Divergence — fall back to IB mid
            seam = ib_mid
            desc = f"IB mid {ib_mid:.2f} (vol POC {vol_poc:.2f}, TPO POC {tpo_poc:.2f} diverge by {spread:.1f} pts)"
    elif len(levels) == 2:
        # Only one secondary level available
        total_weight = sum(weights)
        seam = sum(l * w for l, w in zip(levels, weights)) / total_weight
        secondary = vol_poc if vol_poc is not None else tpo_poc
        sec_label = "vol POC" if vol_poc is not None else "TPO POC"
        desc = f"IB mid {ib_mid:.2f}, {sec_label} {secondary:.2f}"
    else:
        seam = ib_mid
        desc = f"IB mid {ib_mid:.2f} only"

    return round(float(seam), 2), desc


def _detect_morph(intraday_data, current_time_str, balance_type, seam_level):
    """
    Detect balance day morph in PM session.

    Only active when current_time >= 12:00 AND balance_type in (P, b, neutral).

    Signal scoring (each adds confidence):
    - DPOC direction changed in PM (was flat, now up/down): +0.20
    - Volume POC crossed seam level: +0.20
    - TPO fattening zone shifted (was inside_va, now at_vah/val): +0.15
    - Close position shifted (was middle, now upper/lower third): +0.15
    - IB extension multiple > 0.5x: +0.15
    - New single prints forming (directional conviction): +0.15

    Status: "developing" (0.30-0.60), "confirmed" (>0.60), "none" (<0.30)
    """
    empty_morph = {
        "status": "none",
        "morph_type": "none",
        "morph_time_window": "am",
        "morph_signals": [],
        "morph_confidence": 0.0,
    }

    # Parse current time
    try:
        current_time = pd.to_datetime(current_time_str).time()
    except (ValueError, TypeError):
        return empty_morph

    # Only active in PM session (>= 12:00)
    if current_time < time(12, 0):
        return empty_morph

    # Only for balance-type days
    if balance_type not in ("P", "b", "neutral"):
        return empty_morph

    # Determine morph time window
    if current_time < time(13, 0):
        morph_window = "pm_early"
    elif current_time < time(14, 30):
        morph_window = "pm_prime"
    else:
        morph_window = "pm_late"

    # Gather signals
    signals = []
    confidence = 0.0

    ib = intraday_data.get('ib', {})
    ib_high = ib.get('ib_high')
    ib_low = ib.get('ib_low')
    current_close = ib.get('current_close')

    vol_profile = intraday_data.get('volume_profile', {})
    current_session = vol_profile.get('current_session', {})
    vol_poc = current_session.get('poc')
    vah = current_session.get('vah')
    val = current_session.get('val')

    tpo_data = intraday_data.get('tpo_profile', {})
    tpo_poc = tpo_data.get('current_poc')
    fattening_zone = tpo_data.get('fattening_zone', 'inside_va')
    single_above = tpo_data.get('single_prints_above_vah', 0)
    single_below = tpo_data.get('single_prints_below_val', 0)

    dpoc_migration = intraday_data.get('dpoc_migration', {})
    dpoc_direction = dpoc_migration.get('direction', 'flat')
    dpoc_regime = dpoc_migration.get('dpoc_regime', 'transitional_unclear')

    # Track bullish vs bearish signal direction
    bullish_signals = 0
    bearish_signals = 0

    # Signal 1: DPOC direction in PM (non-flat = directional conviction)
    if dpoc_direction == "up":
        signals.append("dpoc_migrating_up_in_pm")
        confidence += 0.20
        bullish_signals += 1
    elif dpoc_direction == "down":
        signals.append("dpoc_migrating_down_in_pm")
        confidence += 0.20
        bearish_signals += 1

    # Signal 2: Volume POC crossed seam level
    if vol_poc is not None and seam_level and seam_level > 0:
        if vol_poc > seam_level + 5:
            signals.append("vol_poc_above_seam")
            confidence += 0.20
            bullish_signals += 1
        elif vol_poc < seam_level - 5:
            signals.append("vol_poc_below_seam")
            confidence += 0.20
            bearish_signals += 1

    # Signal 3: TPO fattening zone shifted
    fat_zone = fattening_zone.lower() if isinstance(fattening_zone, str) else "inside_va"
    if fat_zone in ("above_vah", "at_vah"):
        signals.append("tpo_fattening_above_va")
        confidence += 0.15
        bullish_signals += 1
    elif fat_zone in ("below_val", "at_val"):
        signals.append("tpo_fattening_below_va")
        confidence += 0.15
        bearish_signals += 1

    # Signal 4: Close position (upper/lower third of VA)
    if current_close is not None and vah is not None and val is not None:
        va_range = vah - val
        if va_range > 0:
            upper_third_floor = vah - (va_range * 0.33)
            lower_third_ceiling = val + (va_range * 0.33)
            if current_close > upper_third_floor:
                signals.append("close_in_upper_third")
                confidence += 0.15
                bullish_signals += 1
            elif current_close < lower_third_ceiling:
                signals.append("close_in_lower_third")
                confidence += 0.15
                bearish_signals += 1

    # Signal 5: IB extension multiple > 0.5x
    if ib_high is not None and ib_low is not None and current_close is not None:
        ib_range = ib_high - ib_low
        if ib_range > 0:
            ext_above = max(0, current_close - ib_high)
            ext_below = max(0, ib_low - current_close)
            extension = max(ext_above, ext_below)
            ext_multiple = extension / ib_range
            if ext_multiple > 0.5:
                if ext_above > ext_below:
                    signals.append("ib_extension_up_gt_0.5x")
                    confidence += 0.15
                    bullish_signals += 1
                else:
                    signals.append("ib_extension_down_gt_0.5x")
                    confidence += 0.15
                    bearish_signals += 1

    # Signal 6: New single prints forming
    if single_above >= 2:
        signals.append("single_prints_above_vah")
        confidence += 0.15
        bullish_signals += 1
    elif single_below >= 2:
        signals.append("single_prints_below_val")
        confidence += 0.15
        bearish_signals += 1

    # Determine morph type based on dominant direction
    confidence = round(min(confidence, 1.0), 2)

    # When signals cancel out (equal bullish/bearish), no directional morph
    if bullish_signals == bearish_signals or confidence < 0.30:
        return {
            "status": "none",
            "morph_type": "none",
            "morph_time_window": morph_window,
            "morph_signals": signals,
            "morph_confidence": 0.0,
        }

    # Determine direction
    if bullish_signals > bearish_signals:
        # Check if this is a trend morph (IB extension + strong DPOC)
        has_ib_ext = any("ib_extension_up" in s for s in signals)
        if has_ib_ext and dpoc_regime == "trending_on_the_move":
            morph_type = "to_trend_up"
        else:
            morph_type = "neutral_to_bullish"
    else:
        has_ib_ext = any("ib_extension_down" in s for s in signals)
        if has_ib_ext and dpoc_regime == "trending_on_the_move":
            morph_type = "to_trend_down"
        else:
            morph_type = "neutral_to_bearish"

    # Status classification
    if confidence > 0.60:
        status = "confirmed"
    else:
        status = "developing"

    return {
        "status": status,
        "morph_type": morph_type,
        "morph_time_window": morph_window,
        "morph_signals": signals,
        "morph_confidence": confidence,
    }


def _empty_skew_factors():
    """Returns default skew factors when data is insufficient."""
    return {
        "vol_poc_vs_ib_mid": "at",
        "tpo_poc_vs_ib_mid": "at",
        "dpoc_direction": "flat",
        "fattening_zone": "inside_va",
        "close_position": "middle",
    }


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
        "skew": "neutral",
        "skew_strength": 0.0,
        "skew_factors": _empty_skew_factors(),
        "seam_level": 0.0,
        "seam_description": "No data",
        "morph": {
            "status": "none",
            "morph_type": "none",
            "morph_time_window": "am",
            "morph_signals": [],
            "morph_confidence": 0.0,
        },
        "note": note
    }
