# modules/volume_profile.py
"""
Volume profile with VRVP-style HVN/LVN detection.

Builds volume-at-price histograms (like TradingView's VRVP indicator) by
distributing each bar's volume across its price range. Identifies:
- POC, VAH, VAL (70% value area, CBOT standard)
- HVN zones: price buckets with volume > 1.5× mean (acceptance/balance)
- LVN zones: interior price buckets with volume < 0.5× mean (rejection seams)

Multi-timeframe: current session, prior day, 3-day, 5-day, 10-day composites.
The 5-day composite is the "visible range" for structural HVN/LVN identification.
"""
import pandas as pd
import numpy as np

# Bucket size for VRVP-style aggregation (5 NQ points = 20 ticks)
VRVP_BUCKET_SIZE = 5.0


def get_volume_profile(df_extended, df_current, current_time_str="11:45"):
    """
    Calculate volume profiles across multiple timeframes with VRVP HVN/LVN.

    Returns profiles for: current session, prior day, 3-day, 5-day, 10-day.
    Each profile has: poc, vah, val, high, low, hvn_zones, lvn_zones.

    NOTE: Current session uses RTH data only (9:30 onward).
    Prior day and multi-day composites use FULL SESSION data (ETH + premarket + RTH).
    This is intentional — 20P and 80P strategies rely on all-day VA calculations
    including premarket volume, not just RTH. ETH VA captures overnight acceptance
    levels that carry into RTH (median VA width: ETH 158pts vs RTH-only 126pts).
    """
    # Current session up to current_time — RTH only
    current_time = pd.to_datetime(current_time_str).time()
    available_current = df_current[df_current.index.time <= current_time].copy()
    current_session = available_current.between_time('09:30', current_time_str)

    # Get sorted unique dates for multi-day composites
    current_date = pd.to_datetime(df_extended['session_date'].max())
    all_dates = pd.to_datetime(df_extended['session_date'].unique()).sort_values()
    previous_dates = all_dates[all_dates < current_date]

    # Previous day — FULL SESSION (ETH + premarket + RTH), not RTH-only
    if previous_dates.empty:
        prev_day_df = pd.DataFrame()
    else:
        prev_day_str = previous_dates[-1].strftime('%Y-%m-%d')
        prev_day_df = df_extended[df_extended['session_date'] == prev_day_str]

    # Multi-day composites
    prev_3_dates = previous_dates[-3:]
    prev_3_df = df_extended[df_extended['session_date'].isin(prev_3_dates.strftime('%Y-%m-%d'))]
    prev_5_dates = previous_dates[-5:]
    prev_5_df = df_extended[df_extended['session_date'].isin(prev_5_dates.strftime('%Y-%m-%d'))]
    prev_10_dates = previous_dates[-10:]
    prev_10_df = df_extended[df_extended['session_date'].isin(prev_10_dates.strftime('%Y-%m-%d'))]

    current_profile = _calculate_profile(current_session)
    prev_day_profile = _calculate_profile(prev_day_df)
    prev_3_profile = _calculate_profile(prev_3_df)
    prev_5_profile = _calculate_profile(prev_5_df)
    prev_10_profile = _calculate_profile(prev_10_df)

    return {
        "current_session": current_profile,
        "previous_day": prev_day_profile,
        "previous_3_days": prev_3_profile,
        "previous_5_days": prev_5_profile,
        "previous_10_days": prev_10_profile,
        "note": (
            "VRVP-style volume profile (70% VA). "
            "HVN = acceptance zones (volume > 1.5× mean bucket). "
            "LVN = rejection seams (volume < 0.5× mean bucket, interior only). "
            "5-day composite = visible range for structural HVN/LVN."
        ),
    }


def _build_tick_histogram(df, tick_size=0.25):
    """Distribute volume across price levels at tick resolution.

    Returns (price_bins dict, total_volume, high, low).
    """
    price_bins = {}
    for _, row in df.iterrows():
        bar_low = row['low']
        bar_high = row['high']
        vol = row.get('volume', 1)
        num_ticks = max(1, round((bar_high - bar_low) / tick_size))
        vol_per_tick = vol / num_ticks
        tick = bar_low
        while tick <= bar_high + tick_size * 0.5:
            key = round(round(tick / tick_size) * tick_size, 2)
            price_bins[key] = price_bins.get(key, 0) + vol_per_tick
            tick += tick_size
    return price_bins


def _compute_value_area(price_bins, poc):
    """CBOT standard: expand outward from POC until 70% of volume captured."""
    total_volume = sum(price_bins.values())
    sorted_prices = sorted(price_bins.keys())
    poc_idx = sorted_prices.index(poc) if poc in sorted_prices else len(sorted_prices) // 2
    vah_idx = poc_idx
    val_idx = poc_idx
    cumulative = price_bins.get(poc, 0)
    target_volume = 0.70 * total_volume

    while cumulative < target_volume:
        can_go_up = vah_idx + 1 < len(sorted_prices)
        can_go_down = val_idx - 1 >= 0

        if not can_go_up and not can_go_down:
            break

        vol_above = price_bins.get(sorted_prices[vah_idx + 1], 0) if can_go_up else 0
        vol_below = price_bins.get(sorted_prices[val_idx - 1], 0) if can_go_down else 0

        if vol_above >= vol_below and can_go_up:
            vah_idx += 1
            cumulative += price_bins.get(sorted_prices[vah_idx], 0)
        elif can_go_down:
            val_idx -= 1
            cumulative += price_bins.get(sorted_prices[val_idx], 0)
        else:
            break

    return sorted_prices[vah_idx], sorted_prices[val_idx]


def _find_vrvp_zones(price_bins, vah, val, bucket_size=VRVP_BUCKET_SIZE):
    """VRVP-style zone detection: bucket volume into price zones, find HVN/LVN.

    HVN: buckets with volume > 1.5× mean (acceptance/balance zones)
    LVN: interior buckets with volume < 0.5× mean (rejection seams)

    Returns dict with hvn_zones, lvn_zones lists (max 5 each).
    """
    if not price_bins:
        return {"hvn_zones": [], "lvn_zones": []}

    # Aggregate tick-level volume into fixed-size buckets
    buckets = {}
    for price, vol in price_bins.items():
        bucket_mid = round(float(price) // bucket_size * bucket_size + bucket_size / 2, 2)
        buckets[bucket_mid] = buckets.get(bucket_mid, 0) + vol

    if len(buckets) < 3:
        return {"hvn_zones": [], "lvn_zones": []}

    bucket_series = pd.Series(buckets).sort_index()
    total_vol = bucket_series.sum()
    mean_vol = bucket_series.mean()
    if mean_vol == 0:
        return {"hvn_zones": [], "lvn_zones": []}

    # HVN: buckets significantly above average
    hvn_threshold = mean_vol * 1.5
    hvn_raw = bucket_series[bucket_series >= hvn_threshold].sort_values(ascending=False)
    hvn_zones = []
    for price, vol in hvn_raw.head(5).items():
        hvn_zones.append({
            "price": round(float(price), 2),
            "range_from": round(float(price) - bucket_size / 2, 2),
            "range_to": round(float(price) + bucket_size / 2, 2),
            "volume": round(float(vol)),
            "pct_of_total": round(float(vol / total_vol * 100), 1),
        })

    # LVN: interior buckets significantly below average (rejection seams)
    # Exclude first/last buckets (extremes are excess, not LVN)
    interior = bucket_series.iloc[1:-1] if len(bucket_series) > 2 else bucket_series
    lvn_threshold = mean_vol * 0.5
    lvn_raw = interior[(interior > 0) & (interior <= lvn_threshold)].sort_values()
    lvn_zones = []
    for price, vol in lvn_raw.head(5).items():
        lvn_zones.append({
            "price": round(float(price), 2),
            "range_from": round(float(price) - bucket_size / 2, 2),
            "range_to": round(float(price) + bucket_size / 2, 2),
            "volume": round(float(vol)),
            "pct_of_total": round(float(vol / total_vol * 100), 1),
        })

    return {"hvn_zones": hvn_zones, "lvn_zones": lvn_zones}


def _calculate_profile(df):
    """Calculate full VRVP profile for a DataFrame."""
    empty_result = {
        "poc": "not_available",
        "vah": "not_available",
        "val": "not_available",
        "high": "not_available",
        "low": "not_available",
        "hvn_zones": [],
        "lvn_zones": [],
    }
    if df.empty:
        return empty_result

    high = df['high'].max()
    low = df['low'].min()

    price_bins = _build_tick_histogram(df)
    if not price_bins:
        return empty_result

    total_volume = sum(price_bins.values())
    if total_volume == 0:
        return {**empty_result, "high": round(high, 2), "low": round(low, 2)}

    # POC = price level with highest volume
    poc = max(price_bins, key=lambda p: price_bins[p])

    # CBOT standard Value Area
    vah, val = _compute_value_area(price_bins, poc)

    # VRVP-style HVN/LVN zones (bucketed, meaningful clusters)
    zones = _find_vrvp_zones(price_bins, vah, val)

    return {
        "poc": round(float(poc), 2),
        "vah": round(float(vah), 2),
        "val": round(float(val), 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "hvn_zones": zones["hvn_zones"],
        "lvn_zones": zones["lvn_zones"],
    }