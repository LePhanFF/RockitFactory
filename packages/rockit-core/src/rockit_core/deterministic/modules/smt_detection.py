#!/usr/bin/env python3
"""
Intraday SMT (Smart Money Technique) Detection.

Detects cross-market divergence at key price levels throughout the RTH session.
NQ sweeps a level (makes new high/low) while ES and/or YM hold (don't confirm)
= divergence signal.

Key levels checked:
- Session high/low (ongoing)
- IB high/low (after IB complete)
- Prior session VAH/VAL
- Overnight high/low

Premarket SMT is handled separately by premarket.py (08:45-09:15 window).
This module covers RTH session divergences (09:30+).
"""

import pandas as pd
from datetime import time


def get_smt_detection(
    df_nq_current,
    df_es_current=None,
    df_ym_current=None,
    current_time_str="11:45",
    ib_data=None,
    premarket_data=None,
    prior_va_data=None,
):
    """
    Detect intraday SMT divergences at key levels.

    Args:
        df_nq_current: NQ current session DataFrame
        df_es_current: ES current session DataFrame (optional)
        df_ym_current: YM current session DataFrame (optional)
        current_time_str: Current snapshot time (HH:MM)
        ib_data: IB location output (ib_high, ib_low)
        premarket_data: Premarket output (overnight_high, overnight_low)
        prior_va_data: Volume profile previous_day (vah, val)

    Returns:
        dict: SMT divergence status at each key level
    """
    if df_es_current is None and df_ym_current is None:
        return {"note": "SMT requires ES and YM data", "active_divergences": []}

    try:
        current_time = pd.to_datetime(current_time_str).time()
    except Exception:
        current_time = time(11, 45)

    rth_start = time(9, 30)

    # Filter all frames to RTH up to current_time
    nq = _filter_rth(df_nq_current, rth_start, current_time)
    es = _filter_rth(df_es_current, rth_start, current_time) if df_es_current is not None else None
    ym = _filter_rth(df_ym_current, rth_start, current_time) if df_ym_current is not None else None

    if nq.empty:
        return {"note": "No RTH data for SMT detection", "active_divergences": []}

    # Session extremes
    nq_session_high = nq['high'].max()
    nq_session_low = nq['low'].min()

    result = {}
    active_divergences = []

    # 1. Session high/low SMT
    smt_high = _check_smt_at_level(nq, es, ym, nq_session_high, "high", lookback_bars=5)
    smt_low = _check_smt_at_level(nq, es, ym, nq_session_low, "low", lookback_bars=5)
    result["smt_at_session_high"] = smt_high
    result["smt_at_session_low"] = smt_low
    if "divergence" in smt_high:
        active_divergences.append(f"bearish_at_session_high")
    if "divergence" in smt_low:
        active_divergences.append(f"bullish_at_session_low")

    # 2. IB high/low SMT (only if IB data available)
    if ib_data and isinstance(ib_data, dict):
        ib_high = ib_data.get('ib_high')
        ib_low = ib_data.get('ib_low')
        if isinstance(ib_high, (int, float)) and isinstance(ib_low, (int, float)):
            smt_ibh = _check_smt_at_reference(nq, es, ym, ib_high, "high")
            smt_ibl = _check_smt_at_reference(nq, es, ym, ib_low, "low")
            result["smt_at_ib_high"] = smt_ibh
            result["smt_at_ib_low"] = smt_ibl
            if "divergence" in smt_ibh:
                active_divergences.append("bearish_at_ib_high")
            if "divergence" in smt_ibl:
                active_divergences.append("bullish_at_ib_low")
        else:
            result["smt_at_ib_high"] = "no_ib_data"
            result["smt_at_ib_low"] = "no_ib_data"
    else:
        result["smt_at_ib_high"] = "no_ib_data"
        result["smt_at_ib_low"] = "no_ib_data"

    # 3. Prior VA high/low SMT
    if prior_va_data and isinstance(prior_va_data, dict):
        prev_vah = prior_va_data.get('vah')
        prev_val = prior_va_data.get('val')
        if isinstance(prev_vah, (int, float)) and prev_vah != "not_available":
            smt_vah = _check_smt_at_reference(nq, es, ym, prev_vah, "high")
            result["smt_at_prior_vah"] = smt_vah
            if "divergence" in smt_vah:
                active_divergences.append("bearish_at_prior_vah")
        else:
            result["smt_at_prior_vah"] = "no_data"

        if isinstance(prev_val, (int, float)) and prev_val != "not_available":
            smt_val = _check_smt_at_reference(nq, es, ym, prev_val, "low")
            result["smt_at_prior_val"] = smt_val
            if "divergence" in smt_val:
                active_divergences.append("bullish_at_prior_val")
        else:
            result["smt_at_prior_val"] = "no_data"
    else:
        result["smt_at_prior_vah"] = "no_data"
        result["smt_at_prior_val"] = "no_data"

    # 4. Overnight high/low SMT
    if premarket_data and isinstance(premarket_data, dict):
        on_high = premarket_data.get('overnight_high')
        on_low = premarket_data.get('overnight_low')
        if isinstance(on_high, (int, float)):
            smt_onh = _check_smt_at_reference(nq, es, ym, on_high, "high")
            result["smt_at_overnight_high"] = smt_onh
            if "divergence" in smt_onh:
                active_divergences.append("bearish_at_overnight_high")
        else:
            result["smt_at_overnight_high"] = "no_data"

        if isinstance(on_low, (int, float)):
            smt_onl = _check_smt_at_reference(nq, es, ym, on_low, "low")
            result["smt_at_overnight_low"] = smt_onl
            if "divergence" in smt_onl:
                active_divergences.append("bullish_at_overnight_low")
        else:
            result["smt_at_overnight_low"] = "no_data"
    else:
        result["smt_at_overnight_high"] = "no_data"
        result["smt_at_overnight_low"] = "no_data"

    result["active_divergences"] = active_divergences
    n_div = len(active_divergences)
    if n_div == 0:
        result["note"] = "SMT detection: no divergences"
    else:
        result["note"] = f"SMT detection: {n_div} divergence(s) — {', '.join(active_divergences)}"

    return result


def _filter_rth(df, rth_start, current_time):
    """Filter DataFrame to RTH bars up to current_time."""
    if df is None or df.empty:
        return pd.DataFrame()
    return df[(df.index.time >= rth_start) & (df.index.time <= current_time)].copy()


def _check_smt_at_level(nq, es, ym, nq_extreme, direction, lookback_bars=5):
    """
    Check SMT at NQ's session extreme (high or low).

    Finds the bar where NQ made its extreme, then checks if ES/YM
    also made new extremes in a lookback window around that bar.

    Args:
        direction: "high" for session high test, "low" for session low test
        lookback_bars: window around NQ extreme bar to check ES/YM

    Returns:
        "bearish_divergence" | "bullish_divergence" | "confirmed" | "no_test"
    """
    if nq.empty:
        return "no_test"

    if direction == "high":
        extreme_idx = nq['high'].idxmax()
    else:
        extreme_idx = nq['low'].idxmin()

    # Get position of extreme bar
    try:
        pos = nq.index.get_loc(extreme_idx)
    except KeyError:
        return "no_test"

    # Lookback window
    start = max(0, pos - lookback_bars)
    end = min(len(nq), pos + lookback_bars + 1)

    es_confirmed = True
    ym_confirmed = True

    if es is not None and not es.empty:
        es_window = es.iloc[start:end] if end <= len(es) else es.iloc[max(0, len(es) - lookback_bars * 2):]
        if not es_window.empty:
            if direction == "high":
                # ES should also be at/near its session high
                es_session_high = es['high'].max()
                es_window_high = es_window['high'].max()
                es_confirmed = es_window_high >= es_session_high * 0.999
            else:
                es_session_low = es['low'].min()
                es_window_low = es_window['low'].min()
                es_confirmed = es_window_low <= es_session_low * 1.001

    if ym is not None and not ym.empty:
        ym_window = ym.iloc[start:end] if end <= len(ym) else ym.iloc[max(0, len(ym) - lookback_bars * 2):]
        if not ym_window.empty:
            if direction == "high":
                ym_session_high = ym['high'].max()
                ym_window_high = ym_window['high'].max()
                ym_confirmed = ym_window_high >= ym_session_high * 0.999
            else:
                ym_session_low = ym['low'].min()
                ym_window_low = ym_window['low'].min()
                ym_confirmed = ym_window_low <= ym_session_low * 1.001

    if es_confirmed and ym_confirmed:
        return "confirmed"

    if direction == "high":
        return "bearish_divergence"
    else:
        return "bullish_divergence"


def _check_smt_at_reference(nq, es, ym, level, direction):
    """
    Check SMT at a reference level (IB extreme, prior VA, overnight level).

    Checks if NQ tested beyond the level while ES/YM did not.

    Args:
        level: Price level to check (e.g., IB high, prior VAH)
        direction: "high" for level test from above, "low" for test from below

    Returns:
        "bearish_divergence" | "bullish_divergence" | "confirmed" | "no_test"
    """
    if nq.empty:
        return "no_test"

    # Did NQ test this level?
    if direction == "high":
        nq_tested = nq['high'].max() > level
    else:
        nq_tested = nq['low'].min() < level

    if not nq_tested:
        return "no_test"

    # ES/YM confirmation
    # For SMT: we need to normalize to NQ's level. Since ES/YM trade at different
    # prices, we check if they ALSO made new session extremes in the same direction,
    # not if they crossed the same numeric level.
    es_confirmed = True
    ym_confirmed = True

    if es is not None and not es.empty:
        if direction == "high":
            # NQ swept above level. Did ES also make a higher high recently?
            # Use last 5 bars vs rest of session
            if len(es) > 5:
                recent_high = es.iloc[-5:]['high'].max()
                prior_high = es.iloc[:-5]['high'].max()
                es_confirmed = recent_high >= prior_high
            # If <= 5 bars, too early to tell
        else:
            if len(es) > 5:
                recent_low = es.iloc[-5:]['low'].min()
                prior_low = es.iloc[:-5]['low'].min()
                es_confirmed = recent_low <= prior_low

    if ym is not None and not ym.empty:
        if direction == "high":
            if len(ym) > 5:
                recent_high = ym.iloc[-5:]['high'].max()
                prior_high = ym.iloc[:-5]['high'].max()
                ym_confirmed = recent_high >= prior_high
        else:
            if len(ym) > 5:
                recent_low = ym.iloc[-5:]['low'].min()
                prior_low = ym.iloc[:-5]['low'].min()
                ym_confirmed = recent_low <= prior_low

    if es_confirmed and ym_confirmed:
        return "confirmed"

    if direction == "high":
        return "bearish_divergence"
    else:
        return "bullish_divergence"
