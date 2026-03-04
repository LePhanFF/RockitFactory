#!/usr/bin/env python3
"""
VA Edge Fade — Price Pokes Beyond VA Boundary, Fails, Fade Back In

Price approaches the prior session VA edge, temporarily pokes outside
(1-min bar breaks VA edge AND closes back inside same bar = rejection signal),
then confirmed with 2x consecutive 5-min closes back inside.

Key research findings (Feb 2026, 259 sessions backtest):
- Best overall: 1st poke, 2x5min entry, 2 ATR stop, 0.2 ATR trail → 66.9% WR, PF 5.42
- SHORTS ONLY (VAH poke): 70.0% WR, PF 7.28, $396/mo — NQ structural sell-side supply
- 2nd poke (retest): 67.6% WR, PF 4.54 on limit entry at VA edge
- Stop: 2x ATR (NOT 0.5 ATR trail — 0.5 ATR creates dead zone, 44% early exits)
- Min VA width filter: 25 pts
- Entry cutoff: 13:00 ET (entries 10:00-11:00 window have 2-5% better WR)
- Events per month: 1st poke ~13 events, 2nd poke ~9 events

Poke Types:
  - 1st poke: First time price touches/breaks VA edge today (highest signal quality)
  - 2nd poke: Second test of same VA edge (retest = higher confirmation)

Entry Models:
  - 2x5min: Wait for 2 consecutive 5-min closes back inside VA (best frequency/WR combo)
  - Limit VA edge: Place limit at VA edge ± 5pt buffer (fills on retest sweep)
"""

import pandas as pd
from typing import Dict, Optional, Tuple


def get_va_edge_fade(
    df_current: pd.DataFrame,
    current_time_str: str = "11:45",
    previous_session_vah: float = None,
    previous_session_val: float = None,
    atr14: float = None,
    **kwargs
) -> Dict:
    """
    Detect VA edge fade setups on both VAH (SHORT) and VAL (LONG).

    Args:
        df_current: Current session 5-min bars (no lookahead)
        current_time_str: Current time HH:MM
        previous_session_vah: Prior session VAH (from globex_va_analysis)
        previous_session_val: Prior session VAL (from globex_va_analysis)
        atr14: ATR(14) from ib_location

    Returns:
        {
            "vah_poke_count": int (pokes above VAH today),
            "val_poke_count": int (pokes below VAL today),
            "active_setup": "short_vah_fade" | "long_val_fade" | "none",
            "poke_number": int (1st or 2nd poke = higher quality),
            "confirmation_method": "2x5min" | "watching" | "none",
            "confirmed": bool,
            "entry_price": float,
            "stop_price": float (2x ATR from entry),
            "risk_pts": float,
            "target_poc": float (prior session POC),
            "target_2r": float,
            "short_bias_bonus": bool (SHORTS get +WR per NQ structure),
            "confidence": int 0-100,
            ...
        }
    """

    if previous_session_vah is None or previous_session_val is None:
        return {
            "va_edge_fade_active": False,
            "status": "no_previous_va",
            "note": "Need previous session VAH/VAL from globex_va_analysis"
        }

    va_width = previous_session_vah - previous_session_val
    if va_width < 25:
        return {
            "va_edge_fade_active": False,
            "status": "va_too_narrow",
            "note": "VA width < 25pts — edge fade skipped"
        }

    current_time = pd.to_datetime(current_time_str).time()
    entry_cutoff = pd.to_datetime("13:00").time()
    rth_start = pd.to_datetime("09:30").time()

    available_df = df_current[df_current.index.time <= current_time].copy()
    rth_df = available_df[available_df.index.time >= rth_start]

    if rth_df.empty:
        return {"va_edge_fade_active": False, "status": "no_rth_data"}

    # =========================================================================
    # STEP 1: Detect poke events at VAH and VAL
    # =========================================================================

    vah_pokes, val_pokes = _detect_pokes(rth_df, previous_session_vah, previous_session_val)

    # =========================================================================
    # STEP 2: Classify active setup (most recent poke that has not resolved)
    # =========================================================================

    active_setup, poke_number, poke_bar_idx = _classify_active_setup(
        rth_df, vah_pokes, val_pokes, previous_session_vah, previous_session_val
    )

    if active_setup == "none":
        return {
            "va_edge_fade_active": False,
            "vah_poke_count": len(vah_pokes),
            "val_poke_count": len(val_pokes),
            "active_setup": "none",
            "status": "no_poke_detected",
        }

    # =========================================================================
    # STEP 3: Confirmation via 2x consecutive 5-min closes back inside VA
    # =========================================================================

    confirmed, confirm_entry_price, five_min_consec = _check_confirmation(
        rth_df, poke_bar_idx, active_setup,
        previous_session_vah, previous_session_val
    )

    # =========================================================================
    # STEP 4: Entry/Stop/Target
    # =========================================================================

    stop_price = None
    risk_pts = None
    entry_price = confirm_entry_price
    target_2r = None
    target_3r = None

    if confirmed and entry_price:
        if atr14 and atr14 > 0:
            stop_distance = round(2 * atr14, 2)
        else:
            stop_distance = round(0.10 * va_width, 2)  # Fallback: 10% of VA width

        if active_setup == "short_vah_fade":
            stop_price = round(entry_price + stop_distance, 2)
        else:
            stop_price = round(entry_price - stop_distance, 2)

        risk_pts = round(abs(entry_price - stop_price), 1)
        target_2r = round(entry_price - (2 * risk_pts), 2) if active_setup == "short_vah_fade" else round(entry_price + (2 * risk_pts), 2)
        target_3r = round(entry_price - (3 * risk_pts), 2) if active_setup == "short_vah_fade" else round(entry_price + (3 * risk_pts), 2)

    # Limit order setup (alternative: place limit at VA edge ± 5pt buffer)
    if active_setup == "short_vah_fade":
        limit_entry = round(previous_session_vah + 5, 2)  # SHORT limit above VAH
        limit_stop = round(previous_session_vah + 10 + (2 * (atr14 or 20)), 2)
    else:
        limit_entry = round(previous_session_val - 5, 2)   # LONG limit below VAL
        limit_stop = round(previous_session_val - 10 - (2 * (atr14 or 20)), 2)

    # Short bias: VAH fades (SHORT) get structural NQ bonus per research
    short_bias_bonus = active_setup == "short_vah_fade"

    past_cutoff = current_time >= entry_cutoff
    # Peak window: 10:00-11:00 ET gets 2-5% WR boost
    morning_window = (pd.to_datetime("10:00").time() <= current_time <= pd.to_datetime("11:00").time())

    confidence = _compute_confidence(
        active_setup, poke_number, confirmed, short_bias_bonus,
        past_cutoff, morning_window
    )

    return {
        # Poke tracking
        "vah_poke_count": len(vah_pokes),
        "val_poke_count": len(val_pokes),
        "poke_number": poke_number,                    # 1 = first touch, 2 = retest (higher conf)

        # Setup state
        "active_setup": active_setup,                  # short_vah_fade | long_val_fade | none
        "va_edge_fade_active": confirmed,
        "confirmation_method": "2x5min" if confirmed else ("watching" if active_setup != "none" else "none"),
        "five_min_consec_inside": five_min_consec,

        # Trade parameters
        "entry_price": entry_price,
        "stop_price": stop_price,                      # 2x ATR (NOT 0.5 ATR — dead zone)
        "risk_pts": risk_pts,
        "target_2r": target_2r,
        "target_3r": target_3r,

        # Alternate: limit order setup
        "limit_entry_price": limit_entry,
        "limit_stop_price": limit_stop,

        # Metadata
        "short_bias_bonus": short_bias_bonus,          # SHORTS: 70% WR vs ~50% LONGS
        "morning_window": morning_window,              # 10:00-11:00 best timing
        "past_entry_cutoff": past_cutoff,
        "confidence": confidence,
        "note": "VA Edge Fade: SHORT at VAH poke=70% WR. 2x5min entry+2ATR stop. 0.5ATR trail=dead zone (avoid)."
    }


# ============================================================================
# POKE DETECTION
# ============================================================================


def _detect_pokes(rth_df, vah, val):
    """
    Poke = 1-min bar breaks VA edge AND closes back inside same bar.
    In 5-min data: bar.high > VAH AND bar.close <= VAH (for VAH poke).
    """
    vah_pokes = []
    val_pokes = []

    for i, (ts, row) in enumerate(rth_df.iterrows()):
        if row["high"] > vah and row["close"] <= vah:
            vah_pokes.append((i, ts, row["high"], row["close"]))
        if row["low"] < val and row["close"] >= val:
            val_pokes.append((i, ts, row["low"], row["close"]))

    return vah_pokes, val_pokes


def _classify_active_setup(rth_df, vah_pokes, val_pokes, vah, val):
    """
    Classify most recent poke as setup.
    Poke #2 (retest) has higher WR than poke #1.
    """
    # Find most recent poke event
    last_vah_poke_idx = vah_pokes[-1][0] if vah_pokes else -1
    last_val_poke_idx = val_pokes[-1][0] if val_pokes else -1

    # Use whichever is more recent
    if last_vah_poke_idx < 0 and last_val_poke_idx < 0:
        return "none", 0, None

    if last_vah_poke_idx >= last_val_poke_idx:
        poke_number = len(vah_pokes)
        return "short_vah_fade", poke_number, last_vah_poke_idx
    else:
        poke_number = len(val_pokes)
        return "long_val_fade", poke_number, last_val_poke_idx


def _check_confirmation(rth_df, poke_bar_idx, active_setup, vah, val):
    """
    Check 2x5min confirmation: 2 consecutive 5-min closes inside VA after poke.
    """
    if poke_bar_idx is None or poke_bar_idx < 0:
        return False, None, 0

    post_poke = rth_df.iloc[poke_bar_idx + 1:]
    if post_poke.empty:
        return False, None, 0

    # Resample to 5-min
    five_min = post_poke.resample("5min").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum"
    }).dropna(subset=["close"])

    consecutive = 0
    entry_price = None

    for i, (_, bar) in enumerate(five_min.iterrows()):
        close = bar["close"]
        inside_va = val <= close <= vah
        below_vah = close < vah   # Inside = below VAH (for short fade)
        above_val = close > val   # Inside = above VAL (for long fade)

        if active_setup == "short_vah_fade" and below_vah:
            consecutive += 1
            if consecutive >= 2:
                entry_price = round(close, 2)
                return True, entry_price, consecutive
        elif active_setup == "long_val_fade" and above_val:
            consecutive += 1
            if consecutive >= 2:
                entry_price = round(close, 2)
                return True, entry_price, consecutive
        else:
            consecutive = 0

    return False, None, consecutive


# ============================================================================
# CONFIDENCE SCORING
# ============================================================================


def _compute_confidence(active_setup, poke_number, confirmed, short_bias_bonus, past_cutoff, morning_window):
    if active_setup == "none":
        return 0

    if not confirmed:
        # Watching for confirmation
        base = 45 if poke_number >= 2 else 35
        if short_bias_bonus:
            base += 10  # VAH poke short = higher baseline
        return base

    # Confirmed setup
    if short_bias_bonus:
        base = 82  # SHORT: 70% WR baseline
    else:
        base = 65  # LONG: ~50% WR baseline

    if poke_number >= 2:
        base += 5   # 2nd poke = retest = higher conviction

    if morning_window:
        base += 3   # 10:00-11:00 best window

    if past_cutoff:
        base -= 15  # After 13:00 = degraded

    return min(95, max(0, base))


if __name__ == "__main__":
    import sys, json
    from rockit_core.deterministic.modules.loader import load_nq_csv

    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/raw_csv/NQ_Minute_5_CME US Index Futures ETH_VWAP_Tick.csv"
    session_date = sys.argv[2] if len(sys.argv) > 2 else "2026-01-02"
    test_time = sys.argv[3] if len(sys.argv) > 3 else "11:00"

    df_ext, df_curr = load_nq_csv(csv_path, session_date)
    result = get_va_edge_fade(df_curr, test_time,
                              previous_session_vah=25555.0,
                              previous_session_val=25605.5,
                              atr14=36.3)
    print(json.dumps(result, indent=2))
