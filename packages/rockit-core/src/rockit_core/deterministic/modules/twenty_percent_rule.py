#!/usr/bin/env python3
"""
20P Rule — IB Extension Breakout Detection

After IB completes (09:30-10:30), price extends beyond IB boundary with
3 consecutive 5-min closes. High-conviction trend continuation setup.

Key research findings (Feb 2026, 259 sessions backtest):
- Best config: 3x 5-min closes + 2x ATR stop + 2R target → $496/mo, PF 1.78, 45.5% WR
- 3x5min beats 2x5min (45.5% WR vs 37.3%) — extra bar = higher conviction
- Stop: 2x ATR(14) at entry (32pt avg) — NOT IB boundary (219pt = chaos)
- Target: 2R from entry (64pt avg target)
- Entry cutoff: hard 13:00 ET (after = WR drops to ~32%)
- IB range filter: skip if IB < 20 pts (too narrow)
- LONG slightly outperforms SHORT (structural NQ bull bias)
"""

import pandas as pd
from typing import Dict, Optional


def get_twenty_percent_rule(
    df_current: pd.DataFrame,
    current_time_str: str = "11:45",
    atr14: float = None,
    ib_high: float = None,
    ib_low: float = None,
    ib_range: float = None,
    **kwargs
) -> Dict:
    """
    Detect 20P IB extension breakout setup.

    Args:
        df_current: Current session 5-min bars
        current_time_str: Current time (HH:MM)
        atr14: ATR(14) value from ib_location module
        ib_high: IB high from ib_location module
        ib_low: IB low from ib_location module
        ib_range: IB range from ib_location module

    Returns:
        {
            "ib_range_pts": IB range in points,
            "ib_filter_pass": bool (IB >= 20 pts),
            "ib_complete": bool (past 10:30),
            "extension_direction": "long" | "short" | "none",
            "consecutive_closes_above": int,
            "consecutive_closes_below": int,
            "20p_triggered": bool,
            "20p_direction": "long" | "short" | "none",
            "entry_price": float (at close of 3rd bar),
            "stop_price": float (entry ± 2x ATR),
            "risk_pts": float,
            "target_2r": float,
            "confidence": int 0-100,
            ...
        }
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
    # STEP 7: Entry/Stop/Target (on trigger)
    # =========================================================================

    entry_price = None
    stop_price = None
    risk_pts = None
    target_2r = None
    target_3r = None

    if triggered and trigger_bar_idx is not None:
        entry_bar = five_min_bars.iloc[trigger_bar_idx]
        entry_price = round(entry_bar["close"], 2)

        # Stop: 2x ATR(14) from entry (research: 32pt avg, PF 1.78)
        if atr14 and atr14 > 0:
            stop_distance = round(2 * atr14, 2)
        else:
            # Fallback: 0.08 * IB range (research: ib_range * 0.08 ≈ ATR estimate)
            stop_distance = round(2 * 0.08 * ib_range, 2)

        if direction == "long":
            stop_price = round(entry_price - stop_distance, 2)
        else:
            stop_price = round(entry_price + stop_distance, 2)

        risk_pts = round(abs(entry_price - stop_price), 1)
        target_2r = round(entry_price + (2 * risk_pts), 2) if direction == "long" else round(entry_price - (2 * risk_pts), 2)
        target_3r = round(entry_price + (3 * risk_pts), 2) if direction == "long" else round(entry_price - (3 * risk_pts), 2)

    # Confidence scoring
    confidence = _compute_confidence(triggered, direction, consec_above, consec_below, past_cutoff)

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

        # Setup status
        "20p_triggered": triggered,
        "20p_direction": direction,
        "past_entry_cutoff": past_cutoff,

        # Trade parameters
        "entry_price": entry_price,
        "stop_price": stop_price,
        "risk_pts": risk_pts,
        "target_2r": target_2r,
        "target_3r": target_3r,

        "confidence": confidence,
        "note": "20P: 3x5min consecutive closes beyond IB. Stop=2xATR (NOT IB boundary). 2R target. Long bias on NQ."
    }


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
