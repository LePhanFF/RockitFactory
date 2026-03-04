"""
Phase 12: Mean Reversion Engine
Combines dual acceptance test (VAH + VAL), range classification, and target selection.

Core Logic:
1. Early day_type detection (by 11:00-12:00 AM with confidence)
2. IB range classification (tight < 200pts vs wide > 250pts)
3. Dual acceptance test (rejection at both VAH and VAL)
4. Mean reversion target selection (VWAP for tight, VAH/VAL for wide)
5. Trade setup framing (short high with proper target, long low with proper target)

Strategy:
├─ Tight Range Day (IB < 200pts)
│  ├─ High fails (VAH rejection) → SHORT high, target VWAP
│  ├─ Low fails (VAL rejection) → LONG low, target VWAP
│  └─ Result: Quick mean reversion to VWAP
│
└─ Wide Range Day (IB > 250pts)
   ├─ High fails (VAH rejection) → SHORT high, target VAH (not VWAP)
   ├─ Low fails (VAL rejection) → LONG low, target VAL (not VWAP)
   └─ Result: Mean reversion to extremes (acceptance at bounds)
"""

import pandas as pd
import numpy as np
from datetime import time


def get_mean_reversion_setup(df_nq, intraday_data, current_time_str="11:45"):
    """
    Main entry point: Generate mean reversion trade setup with proper targets.

    Args:
        df_nq: DataFrame with 5-min candles (pre-filtered to current_time)
        intraday_data: Dict with ib, volume_profile, tpo_profile, acceptance_test, inference
        current_time_str: Current snapshot time ("HH:MM")

    Returns:
        dict: {
            "ib_range_classification": str ("tight", "wide", "normal"),
            "ib_range_pts": float,
            "high_rejection": dict (acceptance test at VAH),
            "low_rejection": dict (acceptance test at VAL),
            "mean_reversion_target_high": float (VWAP or VAH),
            "mean_reversion_target_low": float (VWAP or VAL),
            "trade_setup_high": dict (SHORT high with target),
            "trade_setup_low": dict (LONG low with target),
            "combined_confidence": float (0.0-1.0),
            "recommended_action": str ("DUAL_SIDED", "SHORT_BIAS", "LONG_BIAS", "STANDBY"),
            "note": str
        }
    """

    # Extract required data
    ib = intraday_data.get('ib', {})
    ib_high = ib.get('ib_high')
    ib_low = ib.get('ib_low')
    ib_range = ib.get('ib_range')

    vol_profile = intraday_data.get('volume_profile', {})
    current_session = vol_profile.get('current_session', {})
    vah = current_session.get('vah')
    val = current_session.get('val')
    poc = current_session.get('poc')

    # Get VWAP and other price levels
    current_vwap = ib.get('vwap')  # Current VWAP
    current_close = ib.get('current_close')

    tpo_data = intraday_data.get('tpo_profile', {})
    current_poc_tpo = tpo_data.get('current_poc')

    if not all([ib_high, ib_low, ib_range, vah, val, current_vwap]):
        return _empty_setup("Insufficient data for mean reversion analysis")

    # Step 1: Classify IB range (tight vs wide)
    range_class, range_label = _classify_ib_range(ib_range)

    # Step 2: Test acceptance at VAH (high rejection)
    high_rejection = _test_extreme_rejection(
        df_nq, vah, "high", ib_high, ib_range, current_time_str
    )

    # Step 3: Test acceptance at VAL (low rejection)
    low_rejection = _test_extreme_rejection(
        df_nq, val, "low", ib_low, ib_range, current_time_str
    )

    # Step 4: Select mean reversion targets based on range
    target_high = _select_mr_target(vah, current_vwap, range_class, "high")
    target_low = _select_mr_target(val, current_vwap, range_class, "low")

    # Step 5: Generate trade setups
    trade_setup_short = _generate_short_setup(
        ib_high, target_high, high_rejection, range_class, ib_range
    )

    trade_setup_long = _generate_long_setup(
        ib_low, target_low, low_rejection, range_class, ib_range
    )

    # Step 6: Score combined confidence
    combined_conf = _score_combined_confidence(
        high_rejection, low_rejection, range_class
    )

    # Step 7: Recommend action
    action = _recommend_action(
        high_rejection, low_rejection, combined_conf, range_class
    )

    return {
        "ib_range_classification": range_label,
        "ib_range_pts": round(float(ib_range), 1),
        "high_rejection": high_rejection,
        "low_rejection": low_rejection,
        "mean_reversion_target_high": round(float(target_high), 2),
        "mean_reversion_target_low": round(float(target_low), 2),
        "trade_setup_high": trade_setup_short,
        "trade_setup_low": trade_setup_long,
        "combined_confidence": round(float(combined_conf), 2),
        "recommended_action": action,
        "note": f"Mean reversion engine: {range_label} range ({ib_range:.0f}pts). "
                f"High rejection conf {high_rejection['rejection_confidence']:.2f}, "
                f"Low rejection conf {low_rejection['rejection_confidence']:.2f}. "
                f"Action: {action}"
    }


def _classify_ib_range(ib_range_pts):
    """Classify IB range as tight, normal, or wide."""
    if ib_range_pts < 200:
        return "tight", "TIGHT (<200pts)"
    elif ib_range_pts > 250:
        return "wide", "WIDE (>250pts)"
    else:
        return "normal", "NORMAL (200-250pts)"


def _test_extreme_rejection(df_nq, extreme_level, direction, ib_extreme, ib_range,
                            current_time_str, lookback_bars=10):
    """
    Test if price is rejecting an extreme (VAH or VAL).

    Early times (11:00-12:00): Test IB breakout acceptance/rejection
    Later times (16:00): Test VAH/VAL acceptance/rejection

    Returns:
        dict with rejection_confidence, pullback_type, bars_tested, etc.
    """
    current_time = pd.to_datetime(current_time_str).time()
    post_ib_df = df_nq[df_nq.index.time >= time(10, 30)].copy()
    post_ib_df = post_ib_df[post_ib_df.index.time <= current_time].copy()

    if len(post_ib_df) == 0 or extreme_level is None:
        return {
            "tested": False,
            "rejection_confidence": 0.0,
            "pullback_type": "none",
            "bars_tested": 0,
            "bars_to_pullback": 999,
            "pullback_magnitude_pts": 0.0,
            "note": "No test data"
        }

    # Early detection (11:00-12:00): Test IB breakout instead of VAH/VAL (may not exist yet)
    if current_time <= time(12, 30):
        test_level = ib_extreme  # Test against IB extreme, not VAH/VAL
    else:
        test_level = extreme_level  # Test against VAH/VAL at EOD

    # Find if price tested the extreme
    if direction == "high":
        tested = any(post_ib_df['high'] >= (test_level - 10))
        if not tested:
            return {
                "tested": False,
                "rejection_confidence": 0.0,
                "pullback_type": "not_tested",
                "bars_tested": 0,
                "bars_to_pullback": 999,
                "pullback_magnitude_pts": 0.0,
                "note": "High not tested"
            }

        # Find first test of extreme
        test_idx = None
        for idx, (time_idx, row) in enumerate(post_ib_df.iterrows()):
            if row['high'] >= (test_level - 10):
                test_idx = idx
                break

        if test_idx is None:
            return {
                "tested": False,
                "rejection_confidence": 0.0,
                "pullback_type": "none",
                "bars_tested": 0,
                "bars_to_pullback": 999,
                "pullback_magnitude_pts": 0.0,
                "note": "Test not found"
            }

        # Measure pullback after test
        bars_after = post_ib_df.iloc[test_idx + 1 : test_idx + lookback_bars]
        if len(bars_after) == 0:
            pullback_mag = 0.0
            bars_to_pullback = 999
            pullback_crossed = False
        else:
            pullback_mag = test_level - bars_after['low'].min()
            pullback_crossed = any(bars_after['low'] < (test_level - 5))
            # Find bars until pullback
            bars_to_pullback = 0
            for idx, (time_idx, row) in enumerate(bars_after.iterrows()):
                if row['low'] < ib_extreme:
                    bars_to_pullback = idx + 1
                    break
            if bars_to_pullback == 0:
                bars_to_pullback = len(bars_after)

        # Classify rejection
        if pullback_mag > 10 and bars_to_pullback <= 3:
            pullback_type = "fast_rejection"
            rejection_conf = 0.85
        elif pullback_mag > 5 and bars_to_pullback <= 5:
            pullback_type = "clear_rejection"
            rejection_conf = 0.70
        elif pullback_crossed:
            pullback_type = "hesitant_reclaim"
            rejection_conf = 0.55
        else:
            pullback_type = "holding"
            rejection_conf = 0.25

    else:  # direction == "low"
        tested = any(post_ib_df['low'] <= (test_level + 10))
        if not tested:
            return {
                "tested": False,
                "rejection_confidence": 0.0,
                "pullback_type": "not_tested",
                "bars_tested": 0,
                "bars_to_pullback": 999,
                "pullback_magnitude_pts": 0.0,
                "note": "Low not tested"
            }

        # Find first test of extreme
        test_idx = None
        for idx, (time_idx, row) in enumerate(post_ib_df.iterrows()):
            if row['low'] <= (test_level + 10):
                test_idx = idx
                break

        if test_idx is None:
            return {
                "tested": False,
                "rejection_confidence": 0.0,
                "pullback_type": "none",
                "bars_tested": 0,
                "bars_to_pullback": 999,
                "pullback_magnitude_pts": 0.0,
                "note": "Test not found"
            }

        # Measure pullback after test
        bars_after = post_ib_df.iloc[test_idx + 1 : test_idx + lookback_bars]
        if len(bars_after) == 0:
            pullback_mag = 0.0
            bars_to_pullback = 999
            pullback_crossed = False
        else:
            pullback_mag = bars_after['high'].max() - test_level
            pullback_crossed = any(bars_after['high'] > (test_level + 5))
            # Find bars until pullback
            bars_to_pullback = 0
            for idx, (time_idx, row) in enumerate(bars_after.iterrows()):
                if row['high'] > ib_extreme:
                    bars_to_pullback = idx + 1
                    break
            if bars_to_pullback == 0:
                bars_to_pullback = len(bars_after)

        # Classify rejection
        if pullback_mag > 10 and bars_to_pullback <= 3:
            pullback_type = "fast_rejection"
            rejection_conf = 0.85
        elif pullback_mag > 5 and bars_to_pullback <= 5:
            pullback_type = "clear_rejection"
            rejection_conf = 0.70
        elif pullback_crossed:
            pullback_type = "hesitant_reclaim"
            rejection_conf = 0.55
        else:
            pullback_type = "holding"
            rejection_conf = 0.25

    return {
        "tested": True,
        "rejection_confidence": rejection_conf,
        "pullback_type": pullback_type,
        "bars_tested": 1,  # At least 1 bar reached the extreme
        "bars_to_pullback": bars_to_pullback,
        "pullback_magnitude_pts": round(pullback_mag, 2),
        "note": f"{direction.upper()} {pullback_type}: {pullback_mag:.1f}pts pullback in {bars_to_pullback} bars"
    }


def _select_mr_target(extreme_level, vwap, range_class, direction):
    """Select mean reversion target based on range classification."""
    if range_class == "tight":
        # Tight range: revert to VWAP
        return vwap
    elif range_class == "wide":
        # Wide range: revert to opposite extreme (VAH for shorts, VAL for longs)
        return extreme_level
    else:  # normal range
        # Normal: split the difference (VWAP + small offset)
        return vwap


def _generate_short_setup(entry_level, target, high_rejection, range_class, ib_range):
    """
    Generate SHORT trade setup (fade the high).

    Framework-based: Offer setup whenever we have day structure, regardless of rejection.
    Trader uses discretion to enter on pullback toward target.
    """
    # Framework always provides setup (trader decides if/when to enter)
    entry = entry_level + 5  # Entry slightly above failed high (trader waits for pullback)
    stop = entry_level + 15  # Tight stop above failure point
    risk_pts = stop - entry
    reward_pts = entry - target
    rr_ratio = reward_pts / risk_pts if risk_pts > 0 else 0

    # Base confidence on rejection signal if available, otherwise use range classification
    if high_rejection['tested']:
        confidence = high_rejection['rejection_confidence']
    else:
        # Framework confidence based on range
        confidence = 0.65 if range_class == "tight" else 0.60  # Tight ranges more predictable

    return {
        "setup_valid": True,
        "entry": round(float(entry), 2),
        "stop": round(float(stop), 2),
        "target": round(float(target), 2),
        "risk_pts": round(float(risk_pts), 1),
        "reward_pts": round(float(reward_pts), 1),
        "rr_ratio": round(float(rr_ratio), 1),
        "confidence": round(float(confidence), 2),
        "note": f"SHORT framework: High {entry_level:.0f}, Target {target:.0f} ({reward_pts:.0f}pts), RR {rr_ratio:.1f}:1"
    }


def _generate_long_setup(entry_level, target, low_rejection, range_class, ib_range):
    """
    Generate LONG trade setup (fade the low).

    Framework-based: Offer setup whenever we have day structure, regardless of rejection.
    Trader uses discretion to enter on pullback toward target.
    """
    # Framework always provides setup (trader decides if/when to enter)
    entry = entry_level - 5  # Entry slightly below failed low (trader waits for pullback)
    stop = entry_level - 15  # Tight stop below failure point
    risk_pts = entry - stop
    reward_pts = target - entry
    rr_ratio = reward_pts / risk_pts if risk_pts > 0 else 0

    # Base confidence on rejection signal if available, otherwise use range classification
    if low_rejection['tested']:
        confidence = low_rejection['rejection_confidence']
    else:
        # Framework confidence based on range
        confidence = 0.65 if range_class == "tight" else 0.60  # Tight ranges more predictable

    return {
        "setup_valid": True,
        "entry": round(float(entry), 2),
        "stop": round(float(stop), 2),
        "target": round(float(target), 2),
        "risk_pts": round(float(risk_pts), 1),
        "reward_pts": round(float(reward_pts), 1),
        "rr_ratio": round(float(rr_ratio), 1),
        "confidence": round(float(confidence), 2),
        "note": f"LONG framework: Low {entry_level:.0f}, Target {target:.0f} ({reward_pts:.0f}pts), RR {rr_ratio:.1f}:1"
    }


def _score_combined_confidence(high_rejection, low_rejection, range_class):
    """Score combined confidence from both extremes."""
    high_conf = high_rejection['rejection_confidence'] if high_rejection['tested'] else 0.0
    low_conf = low_rejection['rejection_confidence'] if low_rejection['tested'] else 0.0

    # Average confidence
    confs = [c for c in [high_conf, low_conf] if c > 0]
    if not confs:
        return 0.0

    base_conf = sum(confs) / len(confs)

    # Boost if both extremes are rejected (dual-sided setup)
    if len(confs) == 2 and base_conf > 0.60:
        base_conf = min(0.95, base_conf + 0.10)  # Boost for dual confirmation

    return base_conf


def _recommend_action(high_rejection, low_rejection, combined_conf, range_class):
    """
    Recommend trading action based on framework + optional rejection signals.

    Phase 12 philosophy: Framework provides targets. Trader uses discretion for entries.
    - If rejections clear: DUAL_SIDED / SHORT_BIAS / LONG_BIAS (high confidence)
    - Otherwise: FRAMEWORK (mid-day use targets for pullback entries)
    """
    high_conf = high_rejection['rejection_confidence'] if high_rejection['tested'] else 0.0
    low_conf = low_rejection['rejection_confidence'] if low_rejection['tested'] else 0.0

    # High confidence rejection setups
    if high_conf > 0.70 and low_conf > 0.70:
        return "DUAL_SIDED"  # Both extremes rejected clearly
    elif high_conf > 0.70:
        return "SHORT_BIAS"  # High rejected, short opportunity
    elif low_conf > 0.70:
        return "LONG_BIAS"   # Low rejected, long opportunity

    # Framework-based: Recommend pullback entries using targets
    return "FRAMEWORK"  # Use targets for pullback entries (trader discretion on timing)


def _empty_setup(note):
    """Return empty setup when insufficient data."""
    return {
        "ib_range_classification": "unknown",
        "ib_range_pts": 0.0,
        "high_rejection": {"tested": False, "rejection_confidence": 0.0, "note": note},
        "low_rejection": {"tested": False, "rejection_confidence": 0.0, "note": note},
        "mean_reversion_target_high": 0.0,
        "mean_reversion_target_low": 0.0,
        "trade_setup_high": {"setup_valid": False, "confidence": 0.0},
        "trade_setup_low": {"setup_valid": False, "confidence": 0.0},
        "combined_confidence": 0.0,
        "recommended_action": "STANDBY",
        "note": note
    }
