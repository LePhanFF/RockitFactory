# modules/volume_profile.py
import pandas as pd
import numpy as np

def get_volume_profile(df_extended, df_current, current_time_str="11:45"):
    """
    Calculate current session volume profile (up to current_time) and previous day + previous 3 days.
    - Current: POC, VAH, VAL (70% value area) + top HVN/LVN nodes
    - Previous day & previous 3 days: same
    No lookahead – uses only available data up to current_time for current session.
    """
    # Current session up to current_time
    current_time = pd.to_datetime(current_time_str).time()
    available_current = df_current[df_current.index.time <= current_time].copy()
    current_session = available_current.between_time('09:30', current_time_str)

    # Previous day from extended df
    current_date = pd.to_datetime(df_extended['session_date'].max())
    all_dates = pd.to_datetime(df_extended['session_date'].unique()).sort_values()
    previous_dates = all_dates[all_dates < current_date]
    if previous_dates.empty:
        prev_day_df = pd.DataFrame()
    else:
        prev_day = previous_dates[-1]
        prev_day_str = prev_day.strftime('%Y-%m-%d')
        prev_day_df = df_extended[df_extended['session_date'] == prev_day_str]

    # Previous 3 days from extended df
    all_dates = pd.to_datetime(df_extended['session_date'].unique()).sort_values()
    prev_3_dates = all_dates[all_dates < current_date][-3:]
    prev_3_df = df_extended[df_extended['session_date'].isin(prev_3_dates.strftime('%Y-%m-%d'))]

    # Previous 5 days composite
    prev_5_dates = all_dates[all_dates < current_date][-5:]
    prev_5_df = df_extended[df_extended['session_date'].isin(prev_5_dates.strftime('%Y-%m-%d'))]

    # Previous 10 days composite
    prev_10_dates = all_dates[all_dates < current_date][-10:]
    prev_10_df = df_extended[df_extended['session_date'].isin(prev_10_dates.strftime('%Y-%m-%d'))]

    def calculate_profile(df):
        empty_result = {
            "poc": "not_available",
            "vah": "not_available",
            "val": "not_available",
            "high": "not_available",
            "low": "not_available",
            "hvn_nodes": [],
            "lvn_nodes": []
        }
        if df.empty:
            return empty_result

        high = df['high'].max()
        low = df['low'].min()

        # Build volume profile at tick resolution (0.25 for NQ/ES)
        # Distribute each bar's volume across its high-low range
        tick_size = 0.25
        price_bins = {}
        for _, row in df.iterrows():
            bar_low = row['low']
            bar_high = row['high']
            vol = row['volume']
            num_ticks = max(1, round((bar_high - bar_low) / tick_size))
            vol_per_tick = vol / num_ticks
            tick = bar_low
            while tick <= bar_high + tick_size * 0.5:
                key = round(round(tick / tick_size) * tick_size, 2)
                price_bins[key] = price_bins.get(key, 0) + vol_per_tick
                tick += tick_size

        if not price_bins:
            return empty_result

        total_volume = sum(price_bins.values())
        if total_volume == 0:
            return {**empty_result, "high": round(high, 2), "low": round(low, 2)}

        # POC = price level with highest volume
        poc = max(price_bins, key=lambda p: price_bins[p])

        # CBOT standard Value Area: expand outward from POC until 70% captured
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

        vah = sorted_prices[vah_idx]
        val = sorted_prices[val_idx]

        # HVN: top 3 price levels by volume
        sorted_by_vol = sorted(price_bins.items(), key=lambda x: x[1], reverse=True)
        hvn_nodes = [round(p, 2) for p, _ in sorted_by_vol[:3]]

        # LVN: 3 lowest-volume levels within the traded range (exclude extremes)
        # Only consider levels between VAL and VAH to find meaningful LVNs
        interior_bins = {p: v for p, v in price_bins.items() if val <= p <= vah and v > 0}
        if len(interior_bins) >= 3:
            sorted_interior = sorted(interior_bins.items(), key=lambda x: x[1])
            lvn_nodes = sorted([round(p, 2) for p, _ in sorted_interior[:3]])
        else:
            lvn_nodes = []

        return {
            "poc": round(float(poc), 2),
            "vah": round(float(vah), 2),
            "val": round(float(val), 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "hvn_nodes": hvn_nodes,
            "lvn_nodes": lvn_nodes
        }

    current_profile = calculate_profile(current_session)
    prev_day_profile = calculate_profile(prev_day_df)
    prev_3_profile = calculate_profile(prev_3_df)
    prev_5_profile = calculate_profile(prev_5_df)
    prev_10_profile = calculate_profile(prev_10_df)

    return {
        "current_session": current_profile,
        "previous_day": prev_day_profile,
        "previous_3_days": prev_3_profile,
        "previous_5_days": prev_5_profile,
        "previous_10_days": prev_10_profile,
        "note": "Volume profile (70% value area) + top HVN/LVN nodes. Current = up to snapshot time (no lookahead)"
    }