"""
Opening Range Reversal Trade (OR Rev)

Trades the ICT "Judas Swing" at market open. In the first 30 minutes (9:30-10:00),
price makes a false move to sweep pre-market liquidity (overnight H/L, PDH/PDL, Asia H/L),
then reverses. Enter on the reversal.

Performance (259-day backtest, BookMapOrderFlowStudies-2):
  - Win Rate: 61.5% (65 trades)
  - Net P&L: $13,962 (+$215/trade avg)
  - Profit Factor: 3.34
  - Max Drawdown: $1,363
  - SHORT dominates: 75% WR ($10,751 vs LONG 54% WR $3,279)

Detection logic (synced with research engine or_reversal.py):
  1. OR = first 3 5-min bars (9:30-9:44), EOR = first 6 5-min bars (9:30-9:59)
  2. Sweep: EOR extreme near a premarket level (CLOSEST match within threshold)
  3. Dual-sweep: if both sides swept, keep deeper penetration only
  4. Reversal phase: price closes beyond OR midpoint after sweep extreme
  5. Entry: 50% retest zone (halfway between sweep extreme and reversal extreme)
  6. Stop: 2 × ATR14 from entry (NOT swept level + buffer)
  7. Target: 2R
  8. All drives allowed: DRIVE_UP + HIGH sweep SHORT = classic Judas swing
"""

import pandas as pd
import numpy as np
from datetime import time as _time

# Constants — matched to research engine
OR_BARS = 3                       # First 3 5-min bars = Opening Range (9:30-9:44)
EOR_BARS = 6                      # First 6 5-min bars = Extended OR (9:30-9:59)
SWEEP_THRESHOLD_RATIO = 0.17      # Level proximity = 17% of EOR range
VWAP_ALIGNED_RATIO = 0.17         # VWAP proximity = 17% of EOR range
DRIVE_THRESHOLD = 0.4             # Opening drive classification threshold
MIN_RISK_RATIO = 0.03             # Minimum risk = 3% of EOR range
MAX_RISK_RATIO = 1.3              # Maximum risk = 1.3x EOR range
ATR_STOP_MULT = 2.0               # Stop = entry ± 2 × ATR14


def _to_float(val):
    """Safely convert a value to float. Returns None if conversion fails."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _find_closest_swept_level(eor_extreme, candidates, sweep_threshold, eor_range):
    """
    Find the CLOSEST swept level from candidates within threshold.
    Matches research engine: proximity-based, closest wins (not first match).
    """
    best_level = None
    best_name = None
    best_dist = float('inf')

    for name, lvl in candidates:
        if lvl is None:
            continue
        dist = abs(eor_extreme - lvl)
        if dist < sweep_threshold and dist <= eor_range and dist < best_dist:
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


def get_or_reversal_setup(df_current, current_time_str="10:00", intraday_data=None):
    """
    Detect Opening Range Reversal setups (Judas swings).

    Synced with research engine (BookMapOrderFlowStudies-2/strategy/or_reversal.py):
    - Closest-match sweep detection
    - Dual-sweep depth comparison
    - 50% retest zone entry (not just OR mid cross)
    - 2×ATR stop (not EOR buffer)
    - All drives allowed (DRIVE_UP + HIGH sweep = Judas swing)
    """
    current_time = pd.to_datetime(current_time_str).time()
    if current_time < _time(9, 30) or current_time >= _time(10, 16):
        return {"signal": "NONE", "note": "Outside OR window (9:30-10:15)"}

    # Filter to RTH session only
    rth_df = df_current[df_current.index.time >= _time(9, 30)].copy()
    rth_df = rth_df[rth_df.index.time <= current_time].copy()

    if len(rth_df) < EOR_BARS:
        return {"signal": "NONE", "note": f"Insufficient RTH data ({len(rth_df)} bars < {EOR_BARS})"}

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
        return {"signal": "NONE", "note": "EOR range too small"}

    # Thresholds
    sweep_threshold = eor_range * SWEEP_THRESHOLD_RATIO
    vwap_threshold = eor_range * VWAP_ALIGNED_RATIO
    max_risk = eor_range * MAX_RISK_RATIO
    min_risk = eor_range * MIN_RISK_RATIO

    # ATR14 for stop calculation
    atr14 = _compute_atr14(rth_df)

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
        return {"signal": "NONE", "note": "Missing premarket levels"}

    # Build named candidate lists (research: closest match, not first match)
    high_candidates = [('ON_HIGH', overnight_high)]
    if pdh: high_candidates.append(('PDH', pdh))
    if asia_high: high_candidates.append(('ASIA_HIGH', asia_high))
    if london_high: high_candidates.append(('LDN_HIGH', london_high))

    low_candidates = [('ON_LOW', overnight_low)]
    if pdl: low_candidates.append(('PDL', pdl))
    if asia_low: low_candidates.append(('ASIA_LOW', asia_low))
    if london_low: low_candidates.append(('LDN_LOW', london_low))

    # Closest-match sweep detection
    swept_high_level, swept_high_name = _find_closest_swept_level(
        eor_high, high_candidates, sweep_threshold, eor_range)
    swept_low_level, swept_low_name = _find_closest_swept_level(
        eor_low, low_candidates, sweep_threshold, eor_range)

    swept_high = swept_high_level is not None
    swept_low = swept_low_level is not None

    # Dual-sweep depth comparison: if BOTH sides swept, keep deeper penetration
    if swept_high and swept_low:
        high_depth = eor_high - swept_high_level
        low_depth = swept_low_level - eor_low
        if high_depth >= low_depth:
            swept_low_level = None
            swept_low_name = None
            swept_low = False
        else:
            swept_high_level = None
            swept_high_name = None
            swept_high = False

    if not swept_high and not swept_low:
        return _build_result(or_high, or_low, or_mid, eor_high, eor_low, eor_range,
                             opening_drive, False, False)

    # Find extreme bars
    high_bar_idx = eor_bars['high'].argmax()
    low_bar_idx = eor_bars['low'].argmin()

    signal = "NONE"
    entry_price = None
    stop_price = None
    target_price = None

    # === SHORT SETUP: Judas swing UP, then reversal DOWN ===
    # All drives allowed — DRIVE_UP + HIGH sweep IS the classic Judas swing
    if swept_high:
        # Compute 50% retest level: halfway between sweep high and reversal low
        post_high_bars = rth_df.iloc[high_bar_idx:]
        if len(post_high_bars) > 1:
            reversal_low = post_high_bars['close'].min()
        else:
            reversal_low = eor_high
        fifty_pct = reversal_low + (eor_high - reversal_low) * 0.50
        retest_lo = fifty_pct - atr14 * 0.5
        retest_hi = fifty_pct + atr14 * 0.5

        in_reversal = False
        for idx in range(high_bar_idx + 1, min(high_bar_idx + 8, len(rth_df))):
            bar = rth_df.iloc[idx]
            price = bar['close']
            prev_price = rth_df.iloc[idx - 1]['close'] if idx > 0 else price

            # Phase 1: price must close below OR mid (reversal confirmed)
            if price < or_mid:
                in_reversal = True
            if not in_reversal:
                continue

            # Phase 2: entry on retest of 50% zone
            if not (retest_lo <= price <= retest_hi):
                # Also accept if price is simply below OR mid with VWAP alignment
                # (fallback for 5-min bars where 50% zone may be narrow)
                current_vwap = bar.get('vwap', bar['close'])
                if pd.isna(current_vwap):
                    current_vwap = bar['close']
                if abs(price - current_vwap) >= vwap_threshold:
                    continue
                # VWAP-aligned reversal below OR mid — valid entry

            # Must be turning down (retest failing) or at least not rising
            if price > prev_price:
                continue

            # Stop: 2 × ATR14 above entry
            entry_price = price
            stop_price = price + ATR_STOP_MULT * atr14
            risk = stop_price - entry_price

            if min_risk <= risk <= max_risk:
                target_price = entry_price - (2 * risk)
                signal = "SHORT"
                break

    # === LONG SETUP: Judas swing DOWN, then reversal UP ===
    if signal == "NONE" and swept_low:
        post_low_bars = rth_df.iloc[low_bar_idx:]
        if len(post_low_bars) > 1:
            reversal_high = post_low_bars['close'].max()
        else:
            reversal_high = eor_low
        fifty_pct = reversal_high - (reversal_high - eor_low) * 0.50
        retest_lo = fifty_pct - atr14 * 0.5
        retest_hi = fifty_pct + atr14 * 0.5

        in_reversal = False
        for idx in range(low_bar_idx + 1, min(low_bar_idx + 8, len(rth_df))):
            bar = rth_df.iloc[idx]
            price = bar['close']
            prev_price = rth_df.iloc[idx - 1]['close'] if idx > 0 else price

            # Phase 1: price must close above OR mid (reversal confirmed)
            if price > or_mid:
                in_reversal = True
            if not in_reversal:
                continue

            # Phase 2: entry on retest of 50% zone
            if not (retest_lo <= price <= retest_hi):
                current_vwap = bar.get('vwap', bar['close'])
                if pd.isna(current_vwap):
                    current_vwap = bar['close']
                if abs(price - current_vwap) >= vwap_threshold:
                    continue

            # Must be turning up (retest holding)
            if price < prev_price:
                continue

            # Stop: 2 × ATR14 below entry
            entry_price = price
            stop_price = price - ATR_STOP_MULT * atr14
            risk = entry_price - stop_price

            if min_risk <= risk <= max_risk:
                target_price = entry_price + (2 * risk)
                signal = "LONG"
                break

    # Build output
    result = {
        "or_high": float(or_high),
        "or_low": float(or_low),
        "or_mid": float(or_mid),
        "eor_high": float(eor_high),
        "eor_low": float(eor_low),
        "eor_range": float(eor_range),
        "opening_drive": opening_drive,
        "swept_high": bool(swept_high),
        "swept_low": bool(swept_low),
        "signal": signal,
    }

    if signal != "NONE" and entry_price is not None:
        risk = abs(stop_price - entry_price)
        reward = abs(target_price - entry_price)
        rr = reward / risk if risk > 0 else 0

        result.update({
            "entry": float(entry_price),
            "stop": float(stop_price),
            "target": float(target_price),
            "risk": float(risk),
            "reward": float(reward),
            "rr": float(rr),
            "atr14": float(atr14),
            "note": f"Judas swing: EOR {'high' if signal == 'SHORT' else 'low'} swept {swept_high_name or swept_low_name}, "
                    f"50% retest entry, 2xATR stop"
        })
    else:
        result.update({
            "entry": 0.0,
            "stop": 0.0,
            "target": 0.0,
            "risk": 0.0,
            "reward": 0.0,
            "rr": 0.0,
            "note": f"No reversal signal (swept_high={swept_high}, swept_low={swept_low}, drive={opening_drive})"
        })

    return result


def _build_result(or_high, or_low, or_mid, eor_high, eor_low, eor_range,
                  opening_drive, swept_high, swept_low):
    """Build a no-signal result dict."""
    return {
        "or_high": float(or_high),
        "or_low": float(or_low),
        "or_mid": float(or_mid),
        "eor_high": float(eor_high),
        "eor_low": float(eor_low),
        "eor_range": float(eor_range),
        "opening_drive": opening_drive,
        "swept_high": bool(swept_high),
        "swept_low": bool(swept_low),
        "signal": "NONE",
        "entry": 0.0, "stop": 0.0, "target": 0.0,
        "risk": 0.0, "reward": 0.0, "rr": 0.0,
        "note": f"No sweep detected (swept_high={swept_high}, swept_low={swept_low})"
    }
