# modules/tape_context.py
"""
Tape reading context module — V1 deterministic additions for LLM tape reader.

Computes:
1. IB edge touch counter (touch_count_ibh, touch_count_ibl, first_touch_time)
2. C-period close classification (above_ibh / below_ibl / inside_ib)
3. Session open type (Acceptance / Judas / Rotation / Both)
4. VA entry depth % (for 80P quality assessment)
5. DPOC retention % (exhaustion detection)
6. Delta context (CVD, delta trend, divergence detection)

All functions are no-lookahead: they only use data up to current_time_str.
"""
import pandas as pd
import numpy as np
from datetime import time


def get_tape_context(df_current, intraday_data, premarket_data, current_time_str="11:45"):
    """
    Compute tape reading context from current session data.

    Args:
        df_current: Current session DataFrame (1-min or 5-min bars)
        intraday_data: Dict with 'ib', 'volume_profile', 'dpoc_migration', etc.
        premarket_data: Dict with overnight/london/asia levels
        current_time_str: "HH:MM" format (no lookahead past this time)

    Returns:
        dict with ib_touch_counter, c_period, session_open_type, va_entry_depth,
        dpoc_retention, delta_context
    """
    try:
        current_time = pd.to_datetime(current_time_str).time()
    except (ValueError, TypeError):
        current_time = time(11, 45)

    # Filter to only data up to current_time (no lookahead)
    available_df = df_current[df_current.index.time <= current_time].copy()

    ib_data = intraday_data.get("ib", {})
    dpoc_data = intraday_data.get("dpoc_migration", {})
    volume_profile = intraday_data.get("volume_profile", {})

    result = {
        "ib_touch_counter": _get_ib_touch_counter(available_df, ib_data, current_time),
        "c_period": _get_c_period_classification(available_df, ib_data, current_time),
        "session_open_type": _get_session_open_type(available_df, premarket_data, current_time),
        "va_entry_depth": _get_va_entry_depth(ib_data, volume_profile),
        "dpoc_retention": _get_dpoc_retention(dpoc_data),
        "delta_context": _get_delta_context(available_df),
    }

    return result


def _get_ib_touch_counter(available_df, ib_data, current_time):
    """
    Count how many times price touched IBH/IBL after IB was established.
    Critical for B-Day first-touch filter: 1st touch = 82% WR, 2nd = 20%, 3rd = 13%.

    A "touch" = bar high within tolerance of IBH, or bar low within tolerance of IBL.
    Only counts touches AFTER 10:30 (IB must be complete first).
    """
    ib_high = ib_data.get("ib_high")
    ib_low = ib_data.get("ib_low")
    ib_status = ib_data.get("ib_status")
    atr14 = ib_data.get("atr14")

    if not ib_high or not ib_low or ib_status != "complete":
        return {
            "touch_count_ibh": 0,
            "touch_count_ibl": 0,
            "first_touch_ibh_time": None,
            "first_touch_ibl_time": None,
            "last_touch_ibh_time": None,
            "last_touch_ibl_time": None,
            "note": "IB not complete" if ib_status != "complete" else "IB levels unavailable",
        }

    # Touch tolerance: 0.15% of IB range or 3pts, whichever is larger
    ib_range = ib_data.get("ib_range", 0)
    tolerance = max(ib_range * 0.0015, 3.0) if ib_range else 3.0

    # Only count post-IB touches (after 10:30)
    post_ib = available_df[available_df.index.time >= time(10, 30)]

    if post_ib.empty:
        return {
            "touch_count_ibh": 0,
            "touch_count_ibl": 0,
            "first_touch_ibh_time": None,
            "first_touch_ibl_time": None,
            "last_touch_ibh_time": None,
            "last_touch_ibl_time": None,
            "note": "No post-IB data yet",
        }

    # IBH touches: bar high >= IBH - tolerance (approaching IBH from below)
    ibh_touches = post_ib[post_ib["high"] >= (ib_high - tolerance)]
    # IBL touches: bar low <= IBL + tolerance (approaching IBL from above)
    ibl_touches = post_ib[post_ib["low"] <= (ib_low + tolerance)]

    # Cluster consecutive touches into single events (5-bar minimum gap between events)
    ibh_touch_times = _cluster_touches(ibh_touches.index, min_gap_bars=5)
    ibl_touch_times = _cluster_touches(ibl_touches.index, min_gap_bars=5)

    return {
        "touch_count_ibh": len(ibh_touch_times),
        "touch_count_ibl": len(ibl_touch_times),
        "first_touch_ibh_time": ibh_touch_times[0].strftime("%H:%M") if ibh_touch_times else None,
        "first_touch_ibl_time": ibl_touch_times[0].strftime("%H:%M") if ibl_touch_times else None,
        "last_touch_ibh_time": ibh_touch_times[-1].strftime("%H:%M") if ibh_touch_times else None,
        "last_touch_ibl_time": ibl_touch_times[-1].strftime("%H:%M") if ibl_touch_times else None,
        "note": f"tolerance={tolerance:.1f}pts, post-IB bars={len(post_ib)}",
    }


def _cluster_touches(touch_index, min_gap_bars=5):
    """Group consecutive touching bars into distinct touch events."""
    if len(touch_index) == 0:
        return []

    events = [touch_index[0]]
    last_event_idx = 0

    for i in range(1, len(touch_index)):
        # If this bar is far enough from the last event's start, it's a new event
        bars_since_last = i - last_event_idx
        if bars_since_last >= min_gap_bars:
            events.append(touch_index[i])
            last_event_idx = i

    return events


def _get_c_period_classification(available_df, ib_data, current_time):
    """
    Classify where the C-period (10:30-11:00) closed relative to IB.
    Dalton: C-period close above IBH = 70-75% continuation UP.
    C-period close below IBL = 70-75% continuation DOWN.
    C-period inside IB = 70-75% reversal to opposite IB extreme.
    """
    ib_high = ib_data.get("ib_high")
    ib_low = ib_data.get("ib_low")
    ib_status = ib_data.get("ib_status")

    if not ib_high or not ib_low or ib_status != "complete":
        return {
            "classification": "na",
            "c_period_close": None,
            "note": "IB not complete",
        }

    # C-period = first 30-min candle after IB (10:30-11:00)
    c_period_end = time(11, 0)

    if current_time < c_period_end:
        # C-period not yet complete — show developing status
        c_bars = available_df[
            (available_df.index.time >= time(10, 30)) &
            (available_df.index.time < c_period_end)
        ]
        if c_bars.empty:
            return {
                "classification": "developing",
                "c_period_close": None,
                "note": "C-period not started yet",
            }

        # Show current position even though not complete
        current_close = round(float(c_bars.iloc[-1]["close"]), 2)
        if current_close > ib_high:
            developing = "above_ibh"
        elif current_close < ib_low:
            developing = "below_ibl"
        else:
            developing = "inside_ib"

        return {
            "classification": "developing",
            "developing_position": developing,
            "c_period_close": current_close,
            "note": "C-period still forming",
        }

    # C-period complete — classify the close
    c_bars = available_df[
        (available_df.index.time >= time(10, 30)) &
        (available_df.index.time < c_period_end)
    ]

    if c_bars.empty:
        return {
            "classification": "na",
            "c_period_close": None,
            "note": "No C-period data",
        }

    c_close = round(float(c_bars.iloc[-1]["close"]), 2)

    if c_close > ib_high:
        classification = "above_ibh"
        implication = "70-75% continuation UP"
    elif c_close < ib_low:
        classification = "below_ibl"
        implication = "70-75% continuation DOWN"
    else:
        classification = "inside_ib"
        implication = "70-75% reversal to opposite IB extreme"

    return {
        "classification": classification,
        "c_period_close": c_close,
        "c_period_high": round(float(c_bars["high"].max()), 2),
        "c_period_low": round(float(c_bars["low"].min()), 2),
        "distance_from_ibh": round(c_close - ib_high, 2),
        "distance_from_ibl": round(c_close - ib_low, 2),
        "implication": implication,
    }


def _get_session_open_type(available_df, premarket_data, current_time):
    """
    Classify the session open type by 10:00 ET.
    Types: Acceptance (break + hold), Judas (sweep + reverse),
           Rotation (choppy), Both (swept both sides).

    Uses the first 30 bars (9:30-10:00) to classify.
    """
    if current_time < time(9, 45):
        return {
            "classification": "too_early",
            "note": "Need at least 15 min of data",
        }

    # Get the opening window (9:30-10:00)
    open_window = available_df[
        (available_df.index.time >= time(9, 30)) &
        (available_df.index.time < time(10, 0))
    ]

    if len(open_window) < 3:
        return {
            "classification": "insufficient_data",
            "note": f"Only {len(open_window)} bars in opening window",
        }

    # Premarket levels
    london_high = premarket_data.get("london_high")
    london_low = premarket_data.get("london_low")
    asia_high = premarket_data.get("asia_high")
    asia_low = premarket_data.get("asia_low")
    pdh = premarket_data.get("previous_day_high")
    pdl = premarket_data.get("previous_day_low")
    on_high = premarket_data.get("overnight_high")
    on_low = premarket_data.get("overnight_low")

    # Build level map (name → price) for levels that exist
    levels_above = {}
    levels_below = {}
    open_price = float(open_window.iloc[0]["open"])

    for name, price in [
        ("london_high", london_high), ("london_low", london_low),
        ("asia_high", asia_high), ("asia_low", asia_low),
        ("pdh", pdh), ("pdl", pdl),
        ("overnight_high", on_high), ("overnight_low", on_low),
    ]:
        if price is not None:
            if price > open_price:
                levels_above[name] = float(price)
            else:
                levels_below[name] = float(price)

    window_high = float(open_window["high"].max())
    window_low = float(open_window["low"].min())
    window_close = float(open_window.iloc[-1]["close"])

    # Check which levels were swept (price went beyond then returned)
    swept_above = {}
    for name, price in levels_above.items():
        if window_high >= price:
            # Did price return below the level?
            after_sweep = open_window[open_window["high"] >= price]
            if not after_sweep.empty:
                post_bars = open_window.loc[after_sweep.index[-1]:]
                if len(post_bars) > 1 and float(post_bars.iloc[-1]["close"]) < price:
                    swept_above[name] = price

    swept_below = {}
    for name, price in levels_below.items():
        if window_low <= price:
            after_sweep = open_window[open_window["low"] <= price]
            if not after_sweep.empty:
                post_bars = open_window.loc[after_sweep.index[-1]:]
                if len(post_bars) > 1 and float(post_bars.iloc[-1]["close"]) > price:
                    swept_below[name] = price

    # Check for acceptance (broke and held)
    accepted_above = {}
    for name, price in levels_above.items():
        if window_high >= price and name not in swept_above:
            # Count consecutive closes above
            closes_above = (open_window["close"] > price).sum()
            if closes_above >= 2:
                accepted_above[name] = price

    accepted_below = {}
    for name, price in levels_below.items():
        if window_low <= price and name not in swept_below:
            closes_below = (open_window["close"] < price).sum()
            if closes_below >= 2:
                accepted_below[name] = price

    # Classify
    has_sweep = bool(swept_above or swept_below)
    has_acceptance = bool(accepted_above or accepted_below)
    both_sides = bool(swept_above and swept_below)

    if both_sides:
        classification = "both"
        note = f"Swept above ({list(swept_above.keys())}) AND below ({list(swept_below.keys())})"
    elif has_sweep and not has_acceptance:
        classification = "judas"
        swept_names = list(swept_above.keys()) + list(swept_below.keys())
        note = f"Swept {swept_names} then reversed"
    elif has_acceptance and not has_sweep:
        classification = "acceptance"
        acc_names = list(accepted_above.keys()) + list(accepted_below.keys())
        note = f"Accepted beyond {acc_names}"
    elif has_sweep and has_acceptance:
        classification = "judas"  # sweep dominates
        note = "Mixed: sweep detected alongside acceptance"
    else:
        classification = "rotation"
        note = "No levels swept or accepted — choppy open"

    return {
        "classification": classification,
        "swept_levels": {**swept_above, **swept_below},
        "accepted_levels": {**accepted_above, **accepted_below},
        "window_high": round(window_high, 2),
        "window_low": round(window_low, 2),
        "window_range": round(window_high - window_low, 2),
        "open_price": round(open_price, 2),
        "note": note,
    }


def _get_va_entry_depth(ib_data, volume_profile):
    """
    Calculate how deep price has penetrated into prior session VA.
    Study finding: 80P losers enter at 23% VA depth, winners at 45%.
    Higher depth = higher quality entry.
    """
    prior_day = volume_profile.get("previous_day", {})
    vah = prior_day.get("vah")
    val = prior_day.get("val")
    current_close = ib_data.get("current_close")

    if not vah or not val or not current_close:
        return {
            "depth_pct": None,
            "position": "unavailable",
            "note": "Missing VA or price data",
        }

    va_width = vah - val
    if va_width <= 0:
        return {
            "depth_pct": None,
            "position": "invalid_va",
            "note": "VA width is zero or negative",
        }

    # Where is price relative to VA?
    if current_close > vah:
        # Above VA — measure distance above VAH as negative depth
        depth_pct = -round((current_close - vah) / va_width * 100, 1)
        position = "above_va"
    elif current_close < val:
        # Below VA — measure distance below VAL as negative depth
        depth_pct = -round((val - current_close) / va_width * 100, 1)
        position = "below_va"
    else:
        # Inside VA — measure depth from closest edge
        dist_from_vah = vah - current_close
        dist_from_val = current_close - val
        if dist_from_vah < dist_from_val:
            # Closer to VAH — entered from above
            depth_pct = round(dist_from_vah / va_width * 100, 1)
            position = "inside_from_above"
        else:
            # Closer to VAL — entered from below
            depth_pct = round(dist_from_val / va_width * 100, 1)
            position = "inside_from_below"

    # Quality assessment based on study finding
    if depth_pct is not None and depth_pct > 0:
        if depth_pct >= 45:
            quality = "high"  # Winner territory
        elif depth_pct >= 30:
            quality = "moderate"
        else:
            quality = "low"  # Loser territory (23%)
    else:
        quality = "outside_va"

    return {
        "depth_pct": depth_pct,
        "position": position,
        "quality": quality,
        "vah": round(float(vah), 2),
        "val": round(float(val), 2),
        "va_width": round(float(va_width), 2),
        "note": "Study: losers enter at 23% depth, winners at 45%",
    }


def _get_dpoc_retention(dpoc_data):
    """
    Extract and reframe DPOC retention from the dpoc_migration module.
    The module already computes relative_retain_percent — we add tape reader interpretation.
    Low retention (<40%) = exhaustion signal → skip trade.
    High retention (>70%) = conviction still strong.
    """
    retention_raw = dpoc_data.get("relative_retain_percent")
    net_migration = dpoc_data.get("net_migration_pts")
    dpoc_regime = dpoc_data.get("dpoc_regime")
    prior_exhausted = dpoc_data.get("prior_exhausted", False)

    if retention_raw is None:
        return {
            "retention_pct": None,
            "status": "unavailable",
            "note": "DPOC migration data not available",
        }

    retention = round(float(retention_raw), 1)

    if retention >= 70:
        status = "strong"
    elif retention >= 40:
        status = "moderate"
    else:
        status = "exhaustion"

    # Override to exhaustion if prior_exhausted flag is set
    if prior_exhausted:
        status = "exhaustion"

    return {
        "retention_pct": retention,
        "status": status,
        "net_migration": round(float(net_migration), 2) if net_migration is not None else None,
        "regime": dpoc_regime,
        "prior_exhausted": prior_exhausted,
        "note": "<40% = exhaustion (skip trade), >70% = conviction strong",
    }


def _get_delta_context(available_df):
    """
    Compute cumulative volume delta (CVD) context for tape reading.

    CVD = running sum of (vol_ask - vol_bid) from session open.
    Key signals:
    - Price up + CVD down = bearish divergence (weak rally, likely to reverse)
    - Price down + CVD up = bullish divergence (weak selloff, likely to bounce)
    - Price up + CVD up = confirmed rally
    - Price down + CVD down = confirmed selloff

    Uses vol_ask, vol_bid columns from volumetric CSV data.
    """
    # Check if delta columns exist
    has_vol_ask = 'vol_ask' in available_df.columns
    has_vol_bid = 'vol_bid' in available_df.columns
    has_vol_delta = 'vol_delta' in available_df.columns

    if not (has_vol_ask and has_vol_bid) and not has_vol_delta:
        return {
            "cvd": None,
            "cvd_trend": "unavailable",
            "note": "No vol_ask/vol_bid or vol_delta columns in data",
        }

    # RTH session only (9:30+)
    rth_df = available_df[available_df.index.time >= time(9, 30)]
    if len(rth_df) < 2:
        return {
            "cvd": None,
            "cvd_trend": "insufficient",
            "note": "Less than 2 RTH bars",
        }

    # Compute per-bar delta
    if has_vol_ask and has_vol_bid:
        bar_delta = rth_df['vol_ask'] - rth_df['vol_bid']
    else:
        bar_delta = rth_df['vol_delta']

    # CVD = cumulative sum
    cvd = bar_delta.cumsum()
    cvd_current = int(cvd.iloc[-1])
    cvd_values = cvd.values

    # Session total volume for context
    session_volume = int(rth_df['volume'].sum()) if 'volume' in rth_df.columns else None

    # CVD trend: compare last 30 bars vs first 30 bars
    n = len(cvd_values)
    if n >= 30:
        recent_cvd = float(np.mean(cvd_values[-15:]))
        earlier_cvd = float(np.mean(cvd_values[:15]))
        cvd_slope = recent_cvd - earlier_cvd
    elif n >= 10:
        mid = n // 2
        recent_cvd = float(np.mean(cvd_values[mid:]))
        earlier_cvd = float(np.mean(cvd_values[:mid]))
        cvd_slope = recent_cvd - earlier_cvd
    else:
        cvd_slope = float(cvd_values[-1] - cvd_values[0])

    # Classify CVD trend
    if abs(cvd_slope) < 50:
        cvd_trend = "flat"
    elif cvd_slope > 0:
        cvd_trend = "rising"
    else:
        cvd_trend = "falling"

    # Price direction (close-to-close)
    price_start = float(rth_df.iloc[0]['close'])
    price_end = float(rth_df.iloc[-1]['close'])
    price_change = price_end - price_start

    # Divergence detection
    if price_change > 3 and cvd_trend == "falling":
        divergence = "bearish_divergence"
        divergence_note = "Price rising but CVD falling — weak rally, sellers absorbing"
    elif price_change < -3 and cvd_trend == "rising":
        divergence = "bullish_divergence"
        divergence_note = "Price falling but CVD rising — weak selloff, buyers absorbing"
    elif price_change > 3 and cvd_trend == "rising":
        divergence = "confirmed_up"
        divergence_note = "Price and CVD both rising — confirmed buying"
    elif price_change < -3 and cvd_trend == "falling":
        divergence = "confirmed_down"
        divergence_note = "Price and CVD both falling — confirmed selling"
    else:
        divergence = "neutral"
        divergence_note = "No clear divergence or confirmation"

    # Delta at current bar
    current_delta = int(bar_delta.iloc[-1])

    # Rolling delta (last 15 bars) — recent order flow pressure
    last_15 = bar_delta.iloc[-min(15, n):]
    delta_15bar_sum = int(last_15.sum())
    delta_15bar_bias = "buyers" if delta_15bar_sum > 50 else "sellers" if delta_15bar_sum < -50 else "neutral"

    return {
        "cvd": cvd_current,
        "cvd_trend": cvd_trend,
        "current_bar_delta": current_delta,
        "delta_15bar_sum": delta_15bar_sum,
        "delta_15bar_bias": delta_15bar_bias,
        "session_volume": session_volume,
        "price_change": round(price_change, 2),
        "divergence": divergence,
        "divergence_note": divergence_note,
    }
