# modules/tpo_profile.py
"""
TPO (Time Price Opportunity) profile analysis — Dalton Auction Market Theory.

Generates deterministic structural facts for LLM tape reader inference.
All computations use 30-min TPO letters (A, B, C...) from RTH session.

Output sections:
1. Core levels: POC, VAH, VAL
2. Structure: poor high/low, excess, single print ranges
3. HVN/LVN nodes: high/low volume price clusters
4. Per-period letter ranges: compact profile shape representation
5. One-timeframing: per-period OTF direction sequence
6. Distribution: single vs double, separation level
7. Profile shape: P, b, D, B, elongated classification
8. Naked prior levels: tested vs untested
9. Dynamic note: summarizes key profile features

Dalton references:
- Poor High/Low: ≥3 TPOs at session extreme (weak structure, revisit likely)
- Excess: single prints at extreme (strong rejection, unlikely to revisit)
- Single prints: TPO count=1 interior zones (air pockets, tend to fill)
- HVN: high-volume node = acceptance/balance
- LVN: low-volume node = rejection seam, good entry/exit
- One-timeframing: period extends in one direction only (trend)
- P-shape: distribution concentrated at top (buying tail below)
- b-shape: distribution concentrated at bottom (selling tail above)
"""

import pandas as pd
import numpy as np
from datetime import time


def get_tpo_profile(df_nq, current_time_str="11:45", prior_day=None):
    """
    Build TPO profile with full Dalton structural analysis.

    Args:
        df_nq: Current session DataFrame (1-min bars)
        current_time_str: "HH:MM" format (no lookahead past this time)
        prior_day: dict from volume_profile.previous_day (poc, vah, val, high, low)

    Returns:
        dict with TPO structural facts for LLM inference
    """
    current_time = pd.to_datetime(current_time_str).time()
    available_df = df_nq[df_nq.index.time <= current_time].copy()

    if len(available_df) == 0:
        return {"note": "no_data_yet"}

    session_df = available_df.between_time('09:30', current_time_str)

    if len(session_df) == 0:
        return {"note": "pre_open"}

    # --- Build TPO structure ---
    session_df = session_df.copy()
    session_df['period'] = session_df.index.floor('30min')
    periods = session_df['period'].unique()
    sorted_periods = sorted(periods)
    letter_map = {p: chr(65 + i) for i, p in enumerate(sorted_periods)}

    min_price = session_df['low'].min()
    max_price = session_df['high'].max()
    tick = 0.25
    bins = np.arange(min_price - tick, max_price + tick * 2, tick)

    # TPO count per price level
    tpo_counts = pd.Series(0, index=bins, dtype=int)
    # Track which letters touch each price (for single-print detection)
    letters_at_price = {b: set() for b in bins}

    for _, row in session_df.iterrows():
        letter = letter_map[row['period']]
        price_range = np.arange(row['low'], row['high'] + tick, tick)
        for p in price_range:
            if p in tpo_counts.index:
                tpo_counts.loc[p] += 1
                letters_at_price[p].add(letter)

    tpo_counts = tpo_counts[tpo_counts > 0]
    if tpo_counts.empty:
        return {"note": "no_tpo_yet"}

    # --- Core levels ---
    current_poc = float(tpo_counts.idxmax())
    total_tpo = tpo_counts.sum()
    sorted_tpo = tpo_counts.sort_values(ascending=False)
    cum_tpo = 0
    va_prices = []
    for price, count in sorted_tpo.items():
        va_prices.append(price)
        cum_tpo += count
        if cum_tpo >= 0.7 * total_tpo:
            break
    current_vah = float(max(va_prices))
    current_val = float(min(va_prices))
    va_range = current_vah - current_val
    profile_range = max_price - min_price

    current_price = float(session_df['close'].iloc[-1])
    session_high = float(session_df['high'].max())
    session_low = float(session_df['low'].min())

    # --- Per-period letter ranges (compact profile representation) ---
    period_ranges = []
    for p in sorted_periods:
        letter = letter_map[p]
        p_data = session_df[session_df['period'] == p]
        period_ranges.append({
            "letter": letter,
            "time": p.strftime('%H:%M'),
            "high": round(float(p_data['high'].max()), 2),
            "low": round(float(p_data['low'].min()), 2),
            "width": round(float(p_data['high'].max() - p_data['low'].min()), 2),
        })

    # --- One-timeframing sequence ---
    otf_sequence = []
    for i, pr in enumerate(period_ranges):
        if i == 0:
            otf_sequence.append({"letter": pr["letter"], "otf": "initial"})
            continue
        prev = period_ranges[i - 1]
        higher_high = pr["high"] > prev["high"]
        lower_low = pr["low"] < prev["low"]
        if higher_high and not lower_low:
            otf = "up"
        elif lower_low and not higher_high:
            otf = "down"
        elif higher_high and lower_low:
            otf = "outside"  # range expansion both directions
        else:
            otf = "inside"  # contained within prior period
        otf_sequence.append({"letter": pr["letter"], "otf": otf})

    # Summarize OTF: count consecutive up/down runs
    otf_directions = [o["otf"] for o in otf_sequence[1:]]  # skip initial
    otf_up_count = sum(1 for d in otf_directions if d == "up")
    otf_down_count = sum(1 for d in otf_directions if d == "down")
    total_otf = len(otf_directions)
    if total_otf > 0:
        if otf_up_count / total_otf >= 0.7:
            otf_bias = "strong_up"
        elif otf_down_count / total_otf >= 0.7:
            otf_bias = "strong_down"
        elif otf_up_count > otf_down_count:
            otf_bias = "lean_up"
        elif otf_down_count > otf_up_count:
            otf_bias = "lean_down"
        else:
            otf_bias = "rotation"
    else:
        otf_bias = "insufficient"

    # --- Fattening/thinning detection (per-period width trend) ---
    widths = [pr["width"] for pr in period_ranges]
    if len(widths) >= 3:
        recent_avg = np.mean(widths[-3:])
        early_avg = np.mean(widths[:min(3, len(widths))])
        if recent_avg > early_avg * 1.3:
            width_trend = "fattening"
        elif recent_avg < early_avg * 0.7:
            width_trend = "thinning"
        else:
            width_trend = "stable"
    else:
        width_trend = "insufficient"

    # --- Single prints (interior, above VAH, below VAL) ---
    single_above = int((tpo_counts[tpo_counts.index > current_vah] == 1).sum())
    single_below = int((tpo_counts[tpo_counts.index < current_val] == 1).sum())

    # Single print RANGES (air pockets — contiguous price levels with TPO=1)
    single_print_ranges = _find_single_print_ranges(tpo_counts, current_vah, current_val)

    # --- Excess detection (single prints at session extremes) ---
    # Excess at high: count consecutive single-print ticks down from session high
    excess_high_ticks = 0
    for p in np.arange(max_price, min_price - tick, -tick):
        if p in tpo_counts.index and tpo_counts[p] == 1:
            excess_high_ticks += 1
        else:
            break

    # Excess at low: count consecutive single-print ticks up from session low
    excess_low_ticks = 0
    for p in np.arange(min_price, max_price + tick, tick):
        if p in tpo_counts.index and tpo_counts[p] == 1:
            excess_low_ticks += 1
        else:
            break

    excess_high = excess_high_ticks >= 2  # Dalton: 2+ ticks = excess
    excess_low = excess_low_ticks >= 2

    # --- Poor high/low (Dalton: ≥3 TPO at absolute extreme = poor/weak structure) ---
    max_price_level = tpo_counts.index.max()
    min_price_level = tpo_counts.index.min()
    tpo_at_high = int(tpo_counts[max_price_level])
    tpo_at_low = int(tpo_counts[min_price_level])
    poor_high = int(tpo_at_high >= 3)
    poor_low = int(tpo_at_low >= 3)

    # Effective poor: either classic poor OR many single prints (exhaustion)
    effective_poor_high = 1 if (poor_high or single_above >= 4) else 0
    effective_poor_low = 1 if (poor_low or single_below >= 4) else 0

    # --- Rejection strength ---
    rejection_high = _rejection_strength(single_above)
    rejection_low = _rejection_strength(single_below)

    # --- HVN/LVN nodes ---
    hvn_lvn = _find_hvn_lvn(tpo_counts, current_vah, current_val)

    # --- Distribution analysis ---
    distribution = _detect_distributions(tpo_counts, current_poc, profile_range)

    # --- Profile shape classification ---
    shape = _classify_shape(
        tpo_counts, current_vah, current_val, current_poc,
        profile_range, va_range, excess_high, excess_low,
        single_above, single_below, distribution
    )

    # --- Fattening zone (current price location) ---
    if current_price >= current_vah:
        fattening_zone = "above_vah"
    elif current_price <= current_val:
        fattening_zone = "below_val"
    elif abs(current_price - current_vah) < abs(current_price - current_val):
        fattening_zone = "at_vah"
    elif abs(current_price - current_val) < abs(current_price - current_vah):
        fattening_zone = "at_val"
    else:
        fattening_zone = "inside_va"

    # --- Naked prior levels ---
    naked_levels = _check_naked_levels(prior_day, session_high, session_low, tpo_counts)

    # --- Dynamic note ---
    note = _build_dynamic_note(
        shape, excess_high, excess_low, excess_high_ticks, excess_low_ticks,
        poor_high, poor_low, single_above, single_below,
        otf_bias, width_trend, distribution, fattening_zone,
    )

    return {
        # Core levels (backward compatible)
        "current_poc": round(current_poc, 2),
        "current_vah": round(current_vah, 2),
        "current_val": round(current_val, 2),

        # Single prints (backward compatible)
        "single_prints_above_vah": single_above,
        "single_prints_below_val": single_below,

        # Poor high/low (backward compatible — note: threshold changed to ≥3 per Dalton)
        "poor_high": poor_high,
        "poor_low": poor_low,
        "effective_poor_high": effective_poor_high,
        "effective_poor_low": effective_poor_low,

        # Rejection (backward compatible)
        "rejection_at_high": rejection_high,
        "rejection_at_low": rejection_low,

        # Fattening zone (backward compatible)
        "fattening_zone": fattening_zone,

        # Shape (backward compatible key, improved classification)
        "tpo_shape": shape,

        # Naked levels (backward compatible key, improved logic)
        "naked_levels": naked_levels,

        # === NEW: Enhanced structural data for LLM ===

        # Excess at session extremes (Dalton: strong rejection, won't revisit)
        "excess_high": int(excess_high),
        "excess_low": int(excess_low),
        "excess_high_ticks": excess_high_ticks,
        "excess_low_ticks": excess_low_ticks,
        "tpo_at_high": tpo_at_high,
        "tpo_at_low": tpo_at_low,

        # Single print ranges (air pockets that tend to fill)
        "single_print_ranges": single_print_ranges,

        # HVN/LVN nodes (support/resistance, entries/exits)
        "hvn_nodes": hvn_lvn["hvn"],
        "lvn_nodes": hvn_lvn["lvn"],

        # Per-period letter ranges (compact profile shape for LLM)
        "period_ranges": period_ranges,

        # One-timeframing (trend detection)
        "otf_sequence": otf_sequence,
        "otf_bias": otf_bias,

        # Width trend (fattening = acceptance building, thinning = rejection/acceleration)
        "width_trend": width_trend,

        # Distribution analysis (single vs double distribution)
        "distributions": distribution,

        # Dynamic note (key takeaway for LLM)
        "note": note,
    }


def _rejection_strength(single_count):
    """Classify rejection strength from single print count."""
    if single_count >= 5:
        return "strong"
    elif single_count >= 3:
        return "moderate"
    elif single_count >= 1:
        return "weak"
    return "none"


def _find_single_print_ranges(tpo_counts, vah, val):
    """Find contiguous price ranges where TPO count = 1 (air pockets).

    Returns list of {from, to, location, ticks} dicts.
    """
    ranges = []
    single_mask = tpo_counts == 1
    if not single_mask.any():
        return ranges

    prices = tpo_counts.index[single_mask].sort_values()
    if len(prices) == 0:
        return ranges

    # Group contiguous prices (within 0.25 tick)
    start = float(prices[0])
    prev = start
    for p in prices[1:]:
        if p - prev <= 0.5:  # allow small gap for tick alignment
            prev = p
        else:
            _add_range(ranges, start, prev, vah, val)
            start = float(p)
            prev = p
    _add_range(ranges, start, prev, vah, val)

    return ranges


def _add_range(ranges, start, end, vah, val):
    """Add a single print range with location classification."""
    mid = (start + end) / 2
    if mid > vah:
        location = "above_vah"
    elif mid < val:
        location = "below_val"
    else:
        location = "inside_va"

    ticks = int(round((end - start) / 0.25)) + 1
    if ticks >= 2:  # Only report meaningful ranges
        ranges.append({
            "from": round(start, 2),
            "to": round(end, 2),
            "location": location,
            "ticks": ticks,
        })


def _find_hvn_lvn(tpo_counts, vah, val):
    """Find High Volume Nodes and Low Volume Nodes.

    Uses 5-point price buckets to aggregate TPO counts into meaningful zones,
    then identifies peaks (HVN) and valleys (LVN) in the bucketed distribution.

    HVN: buckets with TPO count > 1.5× mean (acceptance/balance zones)
    LVN: buckets with TPO count < 0.5× mean (rejection seams, good entries)

    Returns dict with hvn and lvn lists, max 5 of each (most significant first).
    """
    result = {"hvn": [], "lvn": []}
    if len(tpo_counts) < 10:
        return result

    # Aggregate into 5-point buckets for meaningful clustering
    bucket_size = 5.0
    min_p = float(tpo_counts.index.min())
    max_p = float(tpo_counts.index.max())
    buckets = {}

    for price, count in tpo_counts.items():
        bucket = round(float(price) // bucket_size * bucket_size + bucket_size / 2, 2)
        buckets[bucket] = buckets.get(bucket, 0) + int(count)

    if not buckets:
        return result

    bucket_series = pd.Series(buckets).sort_index()
    mean_tpo = bucket_series.mean()
    if mean_tpo == 0:
        return result

    # HVN: buckets significantly above average
    hvn_threshold = mean_tpo * 1.5
    hvn_buckets = bucket_series[bucket_series >= hvn_threshold].sort_values(ascending=False)
    for price, count in hvn_buckets.head(5).items():
        result["hvn"].append({
            "price": round(float(price), 2),
            "tpo_count": int(count),
            "bucket_size": bucket_size,
        })

    # LVN: interior buckets significantly below average (rejection seams)
    lvn_threshold = mean_tpo * 0.5
    # Exclude edge buckets (extremes are excess, not LVN)
    interior = bucket_series.iloc[1:-1] if len(bucket_series) > 2 else bucket_series
    lvn_buckets = interior[(interior > 0) & (interior <= lvn_threshold)].sort_values()
    for price, count in lvn_buckets.head(5).items():
        result["lvn"].append({
            "price": round(float(price), 2),
            "tpo_count": int(count),
            "bucket_size": bucket_size,
        })

    return result


def _detect_distributions(tpo_counts, poc, profile_range):
    """Detect single vs double distribution.

    Double distribution: two distinct TPO clusters separated by thin zone (LVN).

    Returns dict with count, and separation info if double.
    """
    result = {"count": 1, "type": "single"}

    if len(tpo_counts) < 20 or profile_range < 10:
        return result

    # Smooth TPO counts with rolling mean to find valleys
    smoothed = tpo_counts.sort_index().rolling(window=5, center=True, min_periods=1).mean()
    mean_val = smoothed.mean()

    if mean_val == 0:
        return result

    # Find significant valleys (< 30% of mean) that separate distributions
    valley_mask = smoothed < (mean_val * 0.3)
    valley_prices = smoothed.index[valley_mask]

    if len(valley_prices) == 0:
        return result

    # Check if the valley is in the interior (not at extremes)
    profile_mid_low = tpo_counts.index.min() + profile_range * 0.2
    profile_mid_high = tpo_counts.index.max() - profile_range * 0.2
    interior_valleys = valley_prices[(valley_prices > profile_mid_low) & (valley_prices < profile_mid_high)]

    if len(interior_valleys) >= 3:  # Need a meaningful thin zone
        separation = float(np.mean(interior_valleys.values))
        result = {
            "count": 2,
            "type": "double",
            "separation_level": round(separation, 2),
            "upper_poc": round(float(tpo_counts[tpo_counts.index > separation].idxmax()), 2)
                if not tpo_counts[tpo_counts.index > separation].empty else None,
            "lower_poc": round(float(tpo_counts[tpo_counts.index < separation].idxmax()), 2)
                if not tpo_counts[tpo_counts.index < separation].empty else None,
        }

    return result


def _classify_shape(tpo_counts, vah, val, poc, profile_range, va_range,
                    excess_high, excess_low, single_above, single_below,
                    distribution):
    """Classify profile shape per Dalton.

    Shapes:
    - "p_shape": buying tail below, distribution at top (bullish)
    - "b_shape": selling tail above, distribution at bottom (bearish)
    - "D_shape": symmetric/bell (balanced, normal day)
    - "B_shape": double distribution (two value areas)
    - "elongated": thin, one-directional (trend day)
    - "neutral": extensions both sides, POC centered
    """
    if profile_range == 0:
        return "insufficient"

    va_pct = va_range / profile_range
    poc_position = (poc - tpo_counts.index.min()) / profile_range  # 0=bottom, 1=top

    # Double distribution
    if distribution["count"] == 2:
        return "B_shape"

    # Elongated (trend): VA is narrow relative to range, single prints dominate
    if va_pct < 0.35:
        return "elongated"

    # P-shape: POC in upper third + excess/rejection at lows (buying tail)
    if poc_position > 0.6 and (excess_low or single_below >= 3):
        return "p_shape"

    # b-shape: POC in lower third + excess/rejection at highs (selling tail)
    if poc_position < 0.4 and (excess_high or single_above >= 3):
        return "b_shape"

    # D-shape: symmetric, VA covers most of range, POC centered
    if va_pct > 0.5 and 0.35 < poc_position < 0.65:
        return "D_shape"

    # Neutral: extensions both sides
    if single_above >= 2 and single_below >= 2:
        return "neutral"

    # Default
    if va_pct > 0.65:
        return "wide_value"

    return "developing"


def _check_naked_levels(prior_day, session_high, session_low, tpo_counts):
    """Check if prior session levels have been tested (price traded at level).

    'naked' = price never reached the level during current session
    'tested' = price traded at or through the level
    """
    levels = {
        "prior_poc": "NA",
        "prior_vah": "NA",
        "prior_val": "NA",
        "prior_high": "NA",
        "prior_low": "NA",
    }

    if not prior_day:
        return levels

    field_map = {
        "prior_poc": ("poc", "prev_poc"),
        "prior_vah": ("vah", "prev_vah"),
        "prior_val": ("val", "prev_val"),
        "prior_high": ("high", "prev_high"),
        "prior_low": ("low", "prev_low"),
    }

    for key, (field_a, field_b) in field_map.items():
        level = prior_day.get(field_a) or prior_day.get(field_b)
        if level is None:
            continue

        level = float(level)
        # Check if any TPO printed at this level (within 1 tick tolerance)
        nearby = tpo_counts[(tpo_counts.index >= level - 0.5) &
                            (tpo_counts.index <= level + 0.5)]
        traded_at = not nearby.empty

        if traded_at:
            levels[key] = "tested"
        elif level > session_high:
            levels[key] = "naked_above"
        elif level < session_low:
            levels[key] = "naked_below"
        else:
            # Level is within session range but no TPO printed there — gap/air
            levels[key] = "naked_gap"

    return levels


def _build_dynamic_note(shape, excess_high, excess_low, excess_high_ticks,
                        excess_low_ticks, poor_high, poor_low,
                        single_above, single_below, otf_bias, width_trend,
                        distribution, fattening_zone):
    """Build a dynamic note summarizing the key profile features."""
    parts = []

    # Shape
    shape_names = {
        "p_shape": "P-shape (buying tail, distribution at top)",
        "b_shape": "b-shape (selling tail, distribution at bottom)",
        "D_shape": "D-shape (symmetric/balanced)",
        "B_shape": "B-shape (double distribution)",
        "elongated": "Elongated (trending, narrow VA)",
        "neutral": "Neutral (extensions both sides)",
        "wide_value": "Wide value area",
        "developing": "Developing profile",
    }
    parts.append(shape_names.get(shape, shape))

    # Excess
    if excess_high and excess_low:
        parts.append(f"Excess both extremes (high: {excess_high_ticks} ticks, low: {excess_low_ticks} ticks)")
    elif excess_high:
        parts.append(f"Excess at highs ({excess_high_ticks} ticks — strong rejection)")
    elif excess_low:
        parts.append(f"Excess at lows ({excess_low_ticks} ticks — strong rejection)")

    # Poor structure
    if poor_high and poor_low:
        parts.append("Poor high AND poor low — weak extremes, likely revisit both")
    elif poor_high:
        parts.append("Poor high (≥3 TPO at extreme — weak, expect revisit)")
    elif poor_low:
        parts.append("Poor low (≥3 TPO at extreme — weak, expect revisit)")

    # OTF
    otf_labels = {
        "strong_up": "Strong one-timeframing UP",
        "strong_down": "Strong one-timeframing DOWN",
        "lean_up": "OTF leaning up",
        "lean_down": "OTF leaning down",
        "rotation": "Rotational (no clear OTF)",
    }
    if otf_bias in otf_labels:
        parts.append(otf_labels[otf_bias])

    # Width trend
    if width_trend == "fattening":
        parts.append(f"Fattening {fattening_zone} (acceptance building)")
    elif width_trend == "thinning":
        parts.append("Thinning (rejection/acceleration)")

    # Double distribution
    if distribution["count"] == 2:
        sep = distribution.get("separation_level")
        parts.append(f"Double distribution separated at {sep}")

    return ". ".join(parts) + "."
