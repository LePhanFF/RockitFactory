#!/usr/bin/env python3
"""
IB Extension Analysis — Consecutive close tracking beyond IB boundaries.

Market structure module: Tracks consecutive closes beyond IB high/low
to detect IB extension behavior. Pure observation — no trade signals.

Detection logic:
- IB completes at 10:30, then tracks 5-min closes beyond IB boundary
- Counts consecutive closes above IBH and below IBL
- Reports extension direction and 20P trigger status
- IB range filter: skip if IB < 20 pts (too narrow)
"""

import pandas as pd
from typing import Dict, Optional


def get_ib_extension_analysis(
    df_current: pd.DataFrame,
    current_time_str: str = "11:45",
    atr14: float = None,
    ib_high: float = None,
    ib_low: float = None,
    ib_range: float = None,
    volume_profile: dict = None,
    tpo_profile: dict = None,
    **kwargs
) -> Dict:
    """
    Analyze IB extension behavior — consecutive closes beyond IB boundaries.

    Market structure module: Pure observation — no trade signals.

    Args:
        df_current: Current session 5-min bars
        current_time_str: Current time (HH:MM)
        atr14: ATR(14) value from ib_location module (unused, kept for API compat)
        ib_high: IB high from ib_location module
        ib_low: IB low from ib_location module
        ib_range: IB range from ib_location module

    Returns:
        IB completion status, extension tracking, 20P trigger status
    """

    current_time = pd.to_datetime(current_time_str).time()
    ib_complete_time = pd.to_datetime("10:30").time()
    entry_cutoff = pd.to_datetime("13:00").time()

    available_df = df_current[df_current.index.time <= current_time].copy()

    if available_df.empty:
        return _no_setup("no_data")

    # =========================================================================
    # STEP 1: Validate IB is complete
    # =========================================================================

    ib_complete = current_time > ib_complete_time

    if not ib_complete:
        return _no_setup("ib_not_complete", {
            "ib_complete": False,
            "note": "IB completes at 10:30 — 20P check begins post-IB"
        })

    # =========================================================================
    # STEP 2: IB range filter (skip if < 20 pts)
    # =========================================================================

    if ib_range is None and ib_high is not None and ib_low is not None:
        ib_range = ib_high - ib_low

    ib_filter_pass = ib_range is not None and ib_range >= 20

    if not ib_filter_pass:
        return _no_setup("ib_too_narrow", {
            "ib_complete": True,
            "ib_range_pts": round(ib_range, 1) if ib_range else None,
            "ib_filter_pass": False,
            "note": "IB range < 20pts — 20P setup skipped (noise filter)"
        })

    # =========================================================================
    # STEP 3: Check entry cutoff (no new entries after 13:00 ET)
    # =========================================================================

    past_cutoff = current_time >= entry_cutoff

    # =========================================================================
    # STEP 4: Build 5-min bars from post-IB data
    # =========================================================================

    # Get data after IB completion (post 10:30)
    post_ib_df = available_df[available_df.index.time > ib_complete_time]

    if post_ib_df.empty:
        return _no_setup("no_post_ib_data", {
            "ib_complete": True,
            "ib_range_pts": round(ib_range, 1),
            "ib_filter_pass": True,
        })

    # post_ib_df is already 5-min bars from the loader — no resample needed
    five_min_bars = post_ib_df

    if len(five_min_bars) < 3:
        return {
            "ib_complete": True,
            "ib_range_pts": round(ib_range, 1),
            "ib_filter_pass": True,
            "20p_triggered": False,
            "bars_post_ib": len(five_min_bars),
            "note": "Need 3 consecutive 5-min closes — watching"
        }

    # =========================================================================
    # STEP 5: Count consecutive closes beyond IB boundary
    # =========================================================================

    consec_above, consec_below, trigger_bar_idx = _count_consecutive_extensions(
        five_min_bars, ib_high, ib_low
    )

    # =========================================================================
    # STEP 6: 3-close trigger check
    # =========================================================================

    triggered_long = consec_above >= 3
    triggered_short = consec_below >= 3
    triggered = (triggered_long or triggered_short) and not past_cutoff

    direction = "none"
    if triggered_long:
        direction = "long"
    elif triggered_short:
        direction = "short"

    # =========================================================================
    # STEP 7: Volume + TPO acceptance context (Dalton cross-reference)
    # =========================================================================

    # Volume acceptance: check if current session POC has migrated beyond IB
    volume_accepted = False
    vol_poc_location = "inside_ib"
    if volume_profile and isinstance(volume_profile, dict):
        current_vp = volume_profile.get("current_session", {})
        if isinstance(current_vp, dict):
            current_poc = current_vp.get("poc")
            if isinstance(current_poc, (int, float)):
                if current_poc > ib_high:
                    volume_accepted = True
                    vol_poc_location = "above_ibh"
                elif current_poc < ib_low:
                    volume_accepted = True
                    vol_poc_location = "below_ibl"

    # TPO acceptance: check if TPO POC has migrated beyond IB
    tpo_accepted = False
    tpo_poc_location = "inside_ib"
    if tpo_profile and isinstance(tpo_profile, dict):
        tpo_poc = tpo_profile.get("current_poc")
        if isinstance(tpo_poc, (int, float)):
            if tpo_poc > ib_high:
                tpo_accepted = True
                tpo_poc_location = "above_ibh"
            elif tpo_poc < ib_low:
                tpo_accepted = True
                tpo_poc_location = "below_ibl"

    return {
        # IB state
        "ib_complete": True,
        "ib_range_pts": round(ib_range, 1),
        "ib_filter_pass": True,

        # Extension tracking
        "bars_post_ib": len(five_min_bars),
        "consecutive_closes_above_ibh": consec_above,
        "consecutive_closes_below_ibl": consec_below,
        "extension_direction": "long" if consec_above > consec_below else ("short" if consec_below > consec_above else "none"),

        # 20P trigger status
        "20p_triggered": triggered,
        "20p_direction": direction,

        # Volume + TPO acceptance context
        "volume_accepted": volume_accepted,
        "vol_poc_location": vol_poc_location,
        "tpo_accepted": tpo_accepted,
        "tpo_poc_location": tpo_poc_location,

        "note": f"IB extension: {consec_above} closes above IBH, {consec_below} closes below IBL, triggered={triggered}"
    }


# Keep old name as alias for backward compatibility during transition
get_twenty_percent_rule = get_ib_extension_analysis


def _count_consecutive_extensions(five_min_bars, ib_high, ib_low):
    """Count max consecutive closes beyond IB boundary, return count and trigger bar idx."""
    max_above = 0
    max_below = 0
    current_above = 0
    current_below = 0
    trigger_idx = None

    for i, (_, bar) in enumerate(five_min_bars.iterrows()):
        close = bar["close"]
        if close > ib_high:
            current_above += 1
            current_below = 0
            if current_above >= 3 and trigger_idx is None:
                trigger_idx = i
                max_above = current_above
        elif close < ib_low:
            current_below += 1
            current_above = 0
            if current_below >= 3 and trigger_idx is None:
                trigger_idx = i
                max_below = current_below
        else:
            if current_above > max_above:
                max_above = current_above
            if current_below > max_below:
                max_below = current_below
            current_above = 0
            current_below = 0

    if current_above > max_above:
        max_above = current_above
    if current_below > max_below:
        max_below = current_below

    return max_above, max_below, trigger_idx


def _compute_confidence(triggered, direction, consec_above, consec_below, past_cutoff):
    if not triggered:
        # Not triggered yet — how close are we?
        max_consec = max(consec_above, consec_below)
        if max_consec == 2:
            return 55  # One bar away
        elif max_consec == 1:
            return 35
        return 20

    if past_cutoff:
        return 30  # Past 13:00 — degraded WR per research

    # Triggered
    base = 75  # 45.5% WR baseline
    if direction == "long":
        base += 5  # Long bias on NQ
    return base


def _no_setup(reason, extra=None):
    result = {
        "20p_triggered": False,
        "20p_direction": "none",
        "ib_complete": False,
        "status": reason,
    }
    if extra:
        result.update(extra)
    return result


if __name__ == "__main__":
    import sys, json
    from rockit_core.deterministic.modules.loader import load_nq_csv

    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/raw_csv/NQ_Minute_5_CME US Index Futures ETH_VWAP_Tick.csv"
    session_date = sys.argv[2] if len(sys.argv) > 2 else "2026-01-02"
    test_time = sys.argv[3] if len(sys.argv) > 3 else "11:30"

    df_ext, df_curr = load_nq_csv(csv_path, session_date)
    result = get_twenty_percent_rule(df_curr, test_time, ib_high=25803.75, ib_low=25457.25, ib_range=346.5, atr14=36.3)
    print(json.dumps(result, indent=2))
