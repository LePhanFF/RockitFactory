"""
Single Print Zone Detector -- TPO-based Single Print Analysis
=============================================================

Detects single print zones from 1-minute bar data within a session.

In Market Profile / TPO analysis, single prints are price levels where only
ONE TPO letter printed during a session. They represent areas the market moved
through quickly (no two-way trade), creating "gaps" in the profile that often
get revisited/filled.

A single print ZONE is a contiguous range of single-print price levels.

TPO Period Mapping (RTH):
  A = 9:30-10:00, B = 10:00-10:30, C = 10:30-11:00, D = 11:00-11:30,
  E = 11:30-12:00, F = 12:00-12:30, G = 12:30-13:00, H = 13:00-13:30,
  I = 13:30-14:00, J = 14:00-14:30, K = 14:30-15:00, L = 15:00-15:30,
  M = 15:30-16:00
"""

from datetime import time as _time
from typing import Optional

import numpy as np
import pandas as pd


# RTH 30-minute periods: letter -> (start_time, end_time exclusive)
TPO_PERIODS = {
    "A": (_time(9, 30), _time(10, 0)),
    "B": (_time(10, 0), _time(10, 30)),
    "C": (_time(10, 30), _time(11, 0)),
    "D": (_time(11, 0), _time(11, 30)),
    "E": (_time(11, 30), _time(12, 0)),
    "F": (_time(12, 0), _time(12, 30)),
    "G": (_time(12, 30), _time(13, 0)),
    "H": (_time(13, 0), _time(13, 30)),
    "I": (_time(13, 30), _time(14, 0)),
    "J": (_time(14, 0), _time(14, 30)),
    "K": (_time(14, 30), _time(15, 0)),
    "L": (_time(15, 0), _time(15, 30)),
    "M": (_time(15, 30), _time(16, 0)),
}


def _assign_tpo_period(bar_time: _time) -> Optional[str]:
    """Assign a TPO period letter to a bar based on its timestamp."""
    for letter, (start, end) in TPO_PERIODS.items():
        if start <= bar_time < end:
            return letter
    return None


def _build_tpo_profile(
    session_bars: pd.DataFrame,
    tick_size: float = 0.25,
) -> dict[float, set[str]]:
    """
    Build a TPO profile: for each price level (tick granularity), track which
    TPO periods traded there.

    Args:
        session_bars: DataFrame with 'timestamp' (or index), 'high', 'low' columns.
                      Should contain only RTH bars for one session.
        tick_size: Price bin size (0.25 for NQ/ES).

    Returns:
        Dict mapping price_level -> set of TPO period letters that traded there.
    """
    profile: dict[float, set[str]] = {}

    for _, bar in session_bars.iterrows():
        # Determine bar time
        if "timestamp" in session_bars.columns:
            bar_time = pd.to_datetime(bar["timestamp"]).time()
        elif hasattr(session_bars.index, "time"):
            bar_time = bar.name.time() if hasattr(bar.name, "time") else None
        else:
            continue

        if bar_time is None:
            continue

        period = _assign_tpo_period(bar_time)
        if period is None:
            continue

        bar_high = float(bar["high"])
        bar_low = float(bar["low"])

        # Generate all price levels from low to high at tick_size granularity
        level = np.floor(bar_low / tick_size) * tick_size
        top = np.ceil(bar_high / tick_size) * tick_size
        while level <= top + tick_size / 2:
            rounded = round(level, 4)
            if rounded not in profile:
                profile[rounded] = set()
            profile[rounded].add(period)
            level += tick_size

    return profile


def detect_single_print_zones(
    session_bars: pd.DataFrame,
    tick_size: float = 0.25,
    vah: Optional[float] = None,
    val: Optional[float] = None,
    min_zone_ticks: int = 10,
) -> list[dict]:
    """
    Detect single print zones from 1-minute bar data within a session.

    Single prints are price levels where exactly 1 TPO period traded.
    Contiguous single-print levels are grouped into zones.

    Args:
        session_bars: DataFrame with 'timestamp', 'high', 'low' columns.
                      Should contain RTH bars (9:30-16:00) for one session.
        tick_size: Price bin size (0.25 for NQ/ES).
        vah: Value Area High (for location classification). Optional.
        val: Value Area Low (for location classification). Optional.
        min_zone_ticks: Minimum zone size in ticks to include (default 10 = 2.5 pts on NQ).

    Returns:
        List of zone dicts: {high, low, size_ticks, period, location}
        - period: TPO letter(s) that created the single prints (the lone period)
        - location: "above_vah", "below_val", "within_va", or "unknown"
    """
    if session_bars.empty:
        return []

    profile = _build_tpo_profile(session_bars, tick_size)
    if not profile:
        return []

    # Find single print levels (exactly 1 period)
    single_levels = {}
    for price, periods in profile.items():
        if len(periods) == 1:
            single_levels[price] = next(iter(periods))

    if not single_levels:
        return []

    # Sort by price and group contiguous levels into zones
    sorted_prices = sorted(single_levels.keys())
    zones = []
    zone_start = sorted_prices[0]
    zone_end = sorted_prices[0]
    zone_periods: set[str] = {single_levels[sorted_prices[0]]}

    for i in range(1, len(sorted_prices)):
        price = sorted_prices[i]
        gap = price - zone_end
        # Contiguous if within 1.5 * tick_size (tolerance for float rounding)
        if gap <= tick_size * 1.5:
            zone_end = price
            zone_periods.add(single_levels[price])
        else:
            # Close current zone
            zones.append((zone_start, zone_end, zone_periods.copy()))
            zone_start = price
            zone_end = price
            zone_periods = {single_levels[price]}

    # Close final zone
    zones.append((zone_start, zone_end, zone_periods.copy()))

    # Build output, filtering by min_zone_ticks
    result = []
    for low, high, periods in zones:
        size_ticks = round((high - low) / tick_size)
        if size_ticks < min_zone_ticks:
            continue

        # Classify location relative to Value Area
        zone_mid = (high + low) / 2
        if vah is not None and val is not None:
            if zone_mid > vah:
                location = "above_vah"
            elif zone_mid < val:
                location = "below_val"
            else:
                location = "within_va"
        else:
            location = "unknown"

        result.append(
            {
                "high": round(high, 4),
                "low": round(low, 4),
                "size_ticks": size_ticks,
                "period": ",".join(sorted(periods)),
                "zone_type": "single_print",
                "location": location,
            }
        )

    return result


def detect_price_gap_zones(
    session_bars: pd.DataFrame,
    tick_size: float = 0.25,
    vah: Optional[float] = None,
    val: Optional[float] = None,
    min_zone_ticks: int = 4,
) -> list[dict]:
    """
    Detect true price gap zones (zero-print levels) from 1-minute bar data.

    A price gap is a price level between the session high and low where ZERO
    TPO periods traded. The market moved so fast it skipped those prices
    entirely, creating a "vacuum" that is a stronger fill signal than single
    prints (1 TPO).

    Args:
        session_bars: DataFrame with 'timestamp', 'high', 'low' columns.
                      Should contain RTH bars (9:30-16:00) for one session.
        tick_size: Price bin size (0.25 for NQ/ES).
        vah: Value Area High (for location classification). Optional.
        val: Value Area Low (for location classification). Optional.
        min_zone_ticks: Minimum zone size in ticks to include (default 4 = 1 pt on NQ).

    Returns:
        List of zone dicts: {high, low, size_ticks, zone_type, location}
        - zone_type: always "price_gap"
        - location: "above_vah", "below_val", "within_va", or "unknown"
    """
    if session_bars.empty:
        return []

    profile = _build_tpo_profile(session_bars, tick_size)
    if not profile:
        return []

    # Determine session high/low from actual bar data (not just profile keys)
    session_high = float(session_bars["high"].max())
    session_low = float(session_bars["low"].min())

    # Generate ALL price levels from session low to session high
    all_levels = set()
    level = np.floor(session_low / tick_size) * tick_size
    top = np.ceil(session_high / tick_size) * tick_size
    while level <= top + tick_size / 2:
        all_levels.add(round(level, 4))
        level += tick_size

    # Zero-print levels: in the session range but NOT in the profile
    zero_print_levels = sorted(all_levels - set(profile.keys()))

    if not zero_print_levels:
        return []

    # Group contiguous zero-print levels into zones
    zones = []
    zone_start = zero_print_levels[0]
    zone_end = zero_print_levels[0]

    for i in range(1, len(zero_print_levels)):
        price = zero_print_levels[i]
        gap = price - zone_end
        # Contiguous if within 1.5 * tick_size (tolerance for float rounding)
        if gap <= tick_size * 1.5:
            zone_end = price
        else:
            zones.append((zone_start, zone_end))
            zone_start = price
            zone_end = price

    zones.append((zone_start, zone_end))

    # Build output, filtering by min_zone_ticks
    result = []
    for low, high in zones:
        size_ticks = round((high - low) / tick_size)
        if size_ticks < min_zone_ticks:
            continue

        # Classify location relative to Value Area
        zone_mid = (high + low) / 2
        if vah is not None and val is not None:
            if zone_mid > vah:
                location = "above_vah"
            elif zone_mid < val:
                location = "below_val"
            else:
                location = "within_va"
        else:
            location = "unknown"

        result.append(
            {
                "high": round(high, 4),
                "low": round(low, 4),
                "size_ticks": size_ticks,
                "zone_type": "price_gap",
                "location": location,
            }
        )

    return result


def compute_prior_session_single_prints(
    df: pd.DataFrame,
    tick_size: float = 0.25,
    min_zone_ticks: int = 10,
) -> dict[str, list[dict]]:
    """
    Compute single print zones and price gap zones for each session and map
    them to the NEXT session.

    For each session date, the returned zones are from the PRIOR session
    (since single prints / price gaps from yesterday are what today's session
    may fill).

    This mirrors the pattern in value_area.add_prior_va_features().

    Args:
        df: DataFrame with 'session_date', 'timestamp', 'high', 'low', 'volume' columns.
        tick_size: Price bin size.
        min_zone_ticks: Minimum zone size in ticks (for single prints).

    Returns:
        Dict mapping session_date_str -> list of zone dicts from the prior session.
        Each zone has a 'zone_type' field: "single_print" or "price_gap".
    """
    # Import here to avoid circular dependency
    from rockit_core.indicators.value_area import compute_session_value_areas

    # Compute VA for each session (needed for location classification)
    va_by_session = compute_session_value_areas(df, tick_size)

    sessions = sorted(df["session_date"].unique())
    result: dict[str, list[dict]] = {}

    for i in range(1, len(sessions)):
        current_session = sessions[i]
        prior_session = sessions[i - 1]

        # Get prior session bars (RTH only)
        prior_bars = df[df["session_date"] == prior_session].copy()
        if "timestamp" in prior_bars.columns:
            bar_times = pd.to_datetime(prior_bars["timestamp"]).dt.time
            rth_mask = (bar_times >= _time(9, 30)) & (bar_times < _time(16, 0))
            prior_bars = prior_bars[rth_mask]

        if prior_bars.empty:
            continue

        # Get prior session VA for location classification
        prior_key = str(prior_session)
        vah = None
        val = None
        if prior_key in va_by_session:
            va = va_by_session[prior_key]
            vah = va.vah
            val = va.val

        sp_zones = detect_single_print_zones(
            prior_bars,
            tick_size=tick_size,
            vah=vah,
            val=val,
            min_zone_ticks=min_zone_ticks,
        )

        pg_zones = detect_price_gap_zones(
            prior_bars,
            tick_size=tick_size,
            vah=vah,
            val=val,
            min_zone_ticks=4,  # Lower threshold for price gaps
        )

        current_key = str(current_session)
        result[current_key] = sp_zones + pg_zones

    return result
