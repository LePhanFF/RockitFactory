"""
Opening Range Analysis — OR levels, sweeps, acceptance, and drive classification.

Market structure module: Detects OR/EOR levels, premarket level sweeps,
level acceptance, and opening drive direction. Pure observation — no trade signals.

Two key OR patterns (mutually exclusive per level):
  - **Judas sweep**: Price breaches a level then reverses (liquidity grab / fake-out)
  - **Acceptance**: Price breaks a level and HOLDS beyond it (2+ consecutive 5-min closes)

Detection logic (synced with research engine or_reversal.py + or_acceptance.py):
  1. OR = first 3 5-min bars (9:30-9:44), EOR = first 6 5-min bars (9:30-9:59)
  2. Sweep: EOR extreme near a premarket level (CLOSEST match within threshold)
  3. Dual-sweep: if both sides swept, keep deeper penetration only
  4. Drive classification: DRIVE_UP / DRIVE_DOWN / ROTATION based on OR close vs open
  5. Acceptance: 2+ consecutive 5-min closes beyond a level within IB window (9:30-10:30)
"""

import pandas as pd
import numpy as np
from datetime import time as _time

# Constants — matched to research engine
OR_BARS = 3                       # First 3 5-min bars = Opening Range (9:30-9:44)
EOR_BARS = 6                      # First 6 5-min bars = Extended OR (9:30-9:59)
SWEEP_THRESHOLD_RATIO = 0.17      # Level proximity = 17% of EOR range
DRIVE_THRESHOLD = 0.4             # Opening drive classification threshold
ACCEPT_CONSECUTIVE = 2            # Consecutive 5-min closes beyond level = acceptance


def _to_float(val):
    """Safely convert a value to float. Returns None if conversion fails."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _find_closest_swept_level(eor_extreme, candidates, sweep_threshold, eor_range, direction="high"):
    """
    Find the CLOSEST swept level from candidates that was actually breached.

    A sweep requires price to EXCEED the level (Judas swing / liquidity grab):
      - High sweep: eor_high >= level (price breached above)
      - Low sweep: eor_low <= level (price breached below)

    Within the breached levels, pick the closest one.
    """
    best_level = None
    best_name = None
    best_dist = float('inf')

    for name, lvl in candidates:
        if lvl is None:
            continue
        # Require directional breach, not just proximity
        if direction == "high" and eor_extreme < lvl:
            continue  # EOR high never reached this level
        if direction == "low" and eor_extreme > lvl:
            continue  # EOR low never reached this level
        dist = abs(eor_extreme - lvl)
        if dist < sweep_threshold and dist < best_dist:
            best_dist = dist
            best_level = lvl
            best_name = name
    return best_level, best_name


def _compute_atr14(bars_df):
    """Compute ATR(14) from OHLC bars. Falls back to mean H-L if insufficient data."""
    if len(bars_df) < 3:
        return float((bars_df['high'] - bars_df['low']).mean()) if len(bars_df) > 0 else 20.0
    h = bars_df['high']
    l = bars_df['low']
    pc = bars_df['close'].shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14, min_periods=3).mean().iloc[-1]
    return float(atr) if not pd.isna(atr) else float((h - l).mean())


def _detect_acceptance(rth_df, all_candidates, eor_high, eor_low):
    """
    Detect level acceptance: 2+ consecutive 5-min closes beyond a premarket level.

    Acceptance = continuation (price broke the level and is holding).
    Opposite of Judas sweep (fake-out then reversal).

    Returns list of accepted levels with direction, level name, and confirmation bar.
    """
    accepted = []
    if len(rth_df) < ACCEPT_CONSECUTIVE + 1:
        return accepted

    # Check each candidate level for acceptance
    for name, lvl in all_candidates:
        if lvl is None:
            continue

        # Check for closes ABOVE the level (bullish acceptance)
        consecutive_above = 0
        confirmed_bar = None
        for i in range(len(rth_df)):
            if rth_df.iloc[i]['close'] > lvl:
                consecutive_above += 1
                if consecutive_above >= ACCEPT_CONSECUTIVE:
                    confirmed_bar = i
                    break
            else:
                consecutive_above = 0

        if confirmed_bar is not None:
            # Verify the level was actually meaningful (price started near/below it)
            # Check that at least one bar before acceptance had close <= level
            bars_before = rth_df.iloc[:confirmed_bar - ACCEPT_CONSECUTIVE + 2]
            if len(bars_before) > 0 and bars_before['close'].min() <= lvl:
                accepted.append({
                    'level_name': name,
                    'level_price': float(lvl),
                    'direction': 'bullish',
                    'confirmed_at_bar': int(confirmed_bar),
                    'confirmed_time': str(rth_df.index[confirmed_bar].time())[:5],
                })
                continue  # Don't check bearish for same level

        # Check for closes BELOW the level (bearish acceptance)
        consecutive_below = 0
        confirmed_bar = None
        for i in range(len(rth_df)):
            if rth_df.iloc[i]['close'] < lvl:
                consecutive_below += 1
                if consecutive_below >= ACCEPT_CONSECUTIVE:
                    confirmed_bar = i
                    break
            else:
                consecutive_below = 0

        if confirmed_bar is not None:
            bars_before = rth_df.iloc[:confirmed_bar - ACCEPT_CONSECUTIVE + 2]
            if len(bars_before) > 0 and bars_before['close'].max() >= lvl:
                accepted.append({
                    'level_name': name,
                    'level_price': float(lvl),
                    'direction': 'bearish',
                    'confirmed_at_bar': int(confirmed_bar),
                    'confirmed_time': str(rth_df.index[confirmed_bar].time())[:5],
                })

    return accepted


def get_or_analysis(df_current, current_time_str="10:00", intraday_data=None):
    """
    Analyze Opening Range: levels, sweeps (Judas), acceptance, and drive.

    Returns market structure observations — no trade signals.
    Two key patterns per level:
      - Judas sweep: breach + reversal (fade setup)
      - Acceptance: breach + hold (continuation setup)

    Args:
        df_current: DataFrame with 5-min OHLCV data for current session
        current_time_str: Current time ("HH:MM" format)
        intraday_data: Dict with premarket levels for sweep detection

    Returns:
        dict: OR/EOR levels, sweep detection, acceptance, drive classification
    """
    current_time = pd.to_datetime(current_time_str).time()
    if current_time < _time(9, 30):
        return {"note": "Pre-market (before 9:30)"}

    # Filter to RTH session only
    rth_df = df_current[df_current.index.time >= _time(9, 30)].copy()
    rth_df = rth_df[rth_df.index.time <= current_time].copy()

    if len(rth_df) < EOR_BARS:
        return {"note": f"Insufficient RTH data ({len(rth_df)} bars < {EOR_BARS})"}

    # Compute OR and EOR
    or_bars = rth_df.iloc[:OR_BARS]
    or_high = or_bars['high'].max()
    or_low = or_bars['low'].min()
    or_mid = (or_high + or_low) / 2

    eor_bars = rth_df.iloc[:EOR_BARS]
    eor_high = eor_bars['high'].max()
    eor_low = eor_bars['low'].min()
    eor_range = eor_high - eor_low

    if eor_range < 5:
        return {"note": "EOR range too small"}

    # Thresholds
    sweep_threshold = eor_range * SWEEP_THRESHOLD_RATIO

    # Classify opening drive
    first_bars = rth_df.iloc[:OR_BARS]
    open_price = first_bars.iloc[0]['open']
    close_last = first_bars.iloc[-1]['close']
    drive_range = first_bars['high'].max() - first_bars['low'].min()
    drive_pct = (close_last - open_price) / drive_range if drive_range > 0 else 0

    if drive_pct > DRIVE_THRESHOLD:
        opening_drive = 'DRIVE_UP'
    elif drive_pct < -DRIVE_THRESHOLD:
        opening_drive = 'DRIVE_DOWN'
    else:
        opening_drive = 'ROTATION'

    # Get premarket levels
    if intraday_data is None:
        intraday_data = {}

    premarket = intraday_data.get('premarket', {})
    overnight_high = _to_float(premarket.get('overnight_high'))
    overnight_low = _to_float(premarket.get('overnight_low'))
    pdh = _to_float(premarket.get('pdh') or premarket.get('previous_day_high'))
    pdl = _to_float(premarket.get('pdl') or premarket.get('previous_day_low'))
    asia_high = _to_float(premarket.get('asia_high'))
    asia_low = _to_float(premarket.get('asia_low'))
    london_high = _to_float(premarket.get('london_high'))
    london_low = _to_float(premarket.get('london_low'))

    if overnight_high is None or overnight_low is None:
        return {"note": "Missing premarket levels"}

    # Build named candidate lists (research: closest match, not first match)
    high_candidates = [('ON_HIGH', overnight_high)]
    if pdh: high_candidates.append(('PDH', pdh))
    if asia_high: high_candidates.append(('ASIA_HIGH', asia_high))
    if london_high: high_candidates.append(('LDN_HIGH', london_high))

    low_candidates = [('ON_LOW', overnight_low)]
    if pdl: low_candidates.append(('PDL', pdl))
    if asia_low: low_candidates.append(('ASIA_LOW', asia_low))
    if london_low: low_candidates.append(('LDN_LOW', london_low))

    # Closest-match sweep detection (requires directional breach)
    swept_high_level, swept_high_name = _find_closest_swept_level(
        eor_high, high_candidates, sweep_threshold, eor_range, direction="high")
    swept_low_level, swept_low_name = _find_closest_swept_level(
        eor_low, low_candidates, sweep_threshold, eor_range, direction="low")

    swept_high = swept_high_level is not None
    swept_low = swept_low_level is not None

    # Dual-sweep depth comparison: if BOTH sides swept, keep deeper penetration
    sweep_direction = "none"
    sweep_depth_pct = 0.0
    closest_level = None
    if swept_high and swept_low:
        high_depth = eor_high - swept_high_level
        low_depth = swept_low_level - eor_low
        if high_depth >= low_depth:
            swept_low = False
            sweep_direction = "high"
            sweep_depth_pct = float(high_depth / eor_range * 100) if eor_range > 0 else 0.0
            closest_level = swept_high_name
        else:
            swept_high = False
            sweep_direction = "low"
            sweep_depth_pct = float(low_depth / eor_range * 100) if eor_range > 0 else 0.0
            closest_level = swept_low_name
    elif swept_high:
        high_depth = eor_high - swept_high_level
        sweep_direction = "high"
        sweep_depth_pct = float(high_depth / eor_range * 100) if eor_range > 0 else 0.0
        closest_level = swept_high_name
    elif swept_low:
        low_depth = swept_low_level - eor_low
        sweep_direction = "low"
        sweep_depth_pct = float(low_depth / eor_range * 100) if eor_range > 0 else 0.0
        closest_level = swept_low_name

    # Acceptance detection: 2+ consecutive closes beyond a premarket level
    all_candidates = high_candidates + low_candidates
    accepted_levels = _detect_acceptance(rth_df, all_candidates, eor_high, eor_low)

    # Classify OR behavior per level: acceptance (continuation) vs Judas (reversal)
    # A swept level that price then reversed from = Judas
    # A level with 2+ closes beyond = acceptance (continuation)
    or_behavior = "neutral"
    if swept_high or swept_low:
        or_behavior = "judas_sweep"
    if accepted_levels:
        or_behavior = "acceptance" if not (swept_high or swept_low) else "mixed"

    return {
        "or_high": float(or_high),
        "or_low": float(or_low),
        "or_mid": float(or_mid),
        "eor_high": float(eor_high),
        "eor_low": float(eor_low),
        "eor_range": float(eor_range),
        "opening_drive": opening_drive,
        # Judas sweep fields
        "swept_high": bool(swept_high),
        "swept_low": bool(swept_low),
        "sweep_direction": sweep_direction,
        "sweep_depth_pct": round(sweep_depth_pct, 1),
        "closest_level": closest_level,
        # Acceptance fields
        "accepted_levels": accepted_levels,
        "acceptance_count": len(accepted_levels),
        # Overall OR behavior classification
        "or_behavior": or_behavior,
        "note": (f"OR analysis: drive={opening_drive}, behavior={or_behavior}, "
                 f"swept_high={swept_high}, swept_low={swept_low}"
                 + (f", closest={closest_level}" if closest_level else "")
                 + (f", accepted={[a['level_name'] for a in accepted_levels]}"
                    if accepted_levels else ""))
    }


# Keep old name as alias for backward compatibility during transition
get_or_reversal_setup = get_or_analysis
