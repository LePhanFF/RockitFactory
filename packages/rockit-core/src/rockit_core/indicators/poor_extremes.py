"""
Poor High/Low Session-Level Detection
======================================

Detects whether a session ended with a "poor high" or "poor low" — meaning the
market failed to properly reject its extreme (no tail/excess). The next session
often revisits to "repair" this unfinished business.

Two detection methods are combined:

Method A (Enhanced Bar Analysis):
  Looks at ALL bars within a proximity zone of the session extreme (not just
  the single highest/lowest bar). Computes the average close position of these
  bars relative to their individual bar range. If the average close position is
  near the extreme (>75% for highs, <25% for lows), it indicates no rejection.

Method B (TPO Period Count):
  Counts how many distinct TPO periods (30-min blocks) touched the session
  extreme area. If only 1-2 periods touched → poor (price arrived, no sustained
  activity to build excess). If 3+ periods touched → proper rejection/excess.

Combined: A session extreme is flagged as "poor" if EITHER method detects it.

Quality score (0-1) represents how "poor" the extreme is, with higher values
meaning more poor (less rejection). It averages contributions from both methods.
"""

from __future__ import annotations

from datetime import time as _time
from typing import Dict, Optional

import numpy as np
import pandas as pd


# ── Constants ──────────────────────────────────────────────
# Method A
PROXIMITY_TICKS = 2           # How many ticks from session extreme to include bars
DEFAULT_TICK_SIZE = 0.25      # NQ tick size
POOR_CLOSE_THRESHOLD = 0.75   # Close in top/bottom 25% of bar range → poor
MIN_BAR_RANGE_PTS = 0.5       # Ignore bars with < 0.5pt range (doji/flat)

# Method B (TPO)
TPO_PROXIMITY_PTS = 2.0       # How close a bar must be to count as "touching" extreme
TPO_PERIOD_MINUTES = 30       # Standard TPO period length
POOR_TPO_MAX_PERIODS = 2      # <= 2 periods touching = poor (no sustained rejection)

# RTH boundaries
RTH_START = _time(9, 30)
RTH_END = _time(16, 0)


def _get_tpo_period(bar_time: _time) -> str:
    """Map a bar time to its TPO period label (A, B, C, ...)."""
    if bar_time is None:
        return "?"
    minutes_from_open = (bar_time.hour - 9) * 60 + bar_time.minute - 30
    if minutes_from_open < 0:
        return "?"
    period_index = minutes_from_open // TPO_PERIOD_MINUTES
    if period_index < 0:
        return "?"
    if period_index > 25:
        period_index = 25
    return chr(ord('A') + period_index)


def _extract_bar_time(bar) -> Optional[_time]:
    """Extract time from a bar (Series or dict) with various timestamp formats."""
    ts = None
    for col in ('timestamp', 'time', 'datetime'):
        if col in bar.index if hasattr(bar, 'index') else col in bar:
            ts = bar[col] if not (hasattr(bar, 'get') and bar.get(col) is None) else None
            if ts is not None:
                break

    if ts is None:
        return None

    if isinstance(ts, _time):
        return ts
    if isinstance(ts, str):
        # Try parsing HH:MM or HH:MM:SS
        try:
            parts = ts.strip().split(':')
            return _time(int(parts[0]), int(parts[1]),
                         int(parts[2]) if len(parts) > 2 else 0)
        except (ValueError, IndexError):
            pass
    if hasattr(ts, 'time'):
        return ts.time()
    return None


def _method_a_detect_high(
    session_bars: pd.DataFrame,
    session_high: float,
    tick_size: float,
) -> tuple[bool, float]:
    """
    Method A (enhanced): Check ALL bars near the session high.

    Returns (is_poor, quality_score) where quality_score 0-1, higher = more poor.
    """
    proximity = PROXIMITY_TICKS * tick_size
    near_high_mask = session_bars['high'] >= (session_high - proximity)
    near_bars = session_bars[near_high_mask]

    if len(near_bars) == 0:
        return False, 0.0

    # Compute close position within each bar's range (0 = bar low, 1 = bar high)
    close_positions = []
    for _, bar in near_bars.iterrows():
        bar_range = float(bar['high']) - float(bar['low'])
        if bar_range < MIN_BAR_RANGE_PTS:
            continue
        pos = (float(bar['close']) - float(bar['low'])) / bar_range
        close_positions.append(pos)

    if len(close_positions) == 0:
        return False, 0.0

    avg_close_pos = float(np.mean(close_positions))
    # Higher avg_close_pos → closes near bar highs → no rejection → poor
    is_poor = avg_close_pos >= POOR_CLOSE_THRESHOLD
    # Quality score: rescale so 0.75→0.5, 1.0→1.0, 0.5→0.0
    quality = max(0.0, min(1.0, (avg_close_pos - 0.5) * 2.0))
    return is_poor, quality


def _method_a_detect_low(
    session_bars: pd.DataFrame,
    session_low: float,
    tick_size: float,
) -> tuple[bool, float]:
    """
    Method A (enhanced): Check ALL bars near the session low.

    Returns (is_poor, quality_score) where quality_score 0-1, higher = more poor.
    """
    proximity = PROXIMITY_TICKS * tick_size
    near_low_mask = session_bars['low'] <= (session_low + proximity)
    near_bars = session_bars[near_low_mask]

    if len(near_bars) == 0:
        return False, 0.0

    close_positions = []
    for _, bar in near_bars.iterrows():
        bar_range = float(bar['high']) - float(bar['low'])
        if bar_range < MIN_BAR_RANGE_PTS:
            continue
        pos = (float(bar['close']) - float(bar['low'])) / bar_range
        close_positions.append(pos)

    if len(close_positions) == 0:
        return False, 0.0

    avg_close_pos = float(np.mean(close_positions))
    # Lower avg_close_pos → closes near bar lows → no rejection → poor
    is_poor = avg_close_pos <= (1.0 - POOR_CLOSE_THRESHOLD)
    # Quality score: rescale so 0.25→0.5, 0.0→1.0, 0.5→0.0
    quality = max(0.0, min(1.0, (0.5 - avg_close_pos) * 2.0))
    return is_poor, quality


def _method_b_detect_high(
    session_bars: pd.DataFrame,
    session_high: float,
) -> tuple[bool, float]:
    """
    Method B (TPO-based): Count distinct TPO periods touching session high area.

    Returns (is_poor, quality_score) where quality_score 0-1, higher = more poor.
    """
    touching_periods: set[str] = set()
    for _, bar in session_bars.iterrows():
        if float(bar['high']) >= (session_high - TPO_PROXIMITY_PTS):
            period = _get_tpo_period(_extract_bar_time(bar))
            if period != "?":
                touching_periods.add(period)

    n_periods = len(touching_periods)
    if n_periods == 0:
        # Fallback: if we can't determine periods, check bar count
        near_bars = session_bars[
            session_bars['high'] >= (session_high - TPO_PROXIMITY_PTS)
        ]
        n_bars = len(near_bars)
        is_poor = n_bars <= 2
        quality = max(0.0, min(1.0, 1.0 - (n_bars - 1) * 0.25))
        return is_poor, quality

    is_poor = n_periods <= POOR_TPO_MAX_PERIODS
    # Quality: 1 period → 1.0, 2 → 0.67, 3 → 0.33, 4+ → 0.0
    quality = max(0.0, min(1.0, 1.0 - (n_periods - 1) / 3.0))
    return is_poor, quality


def _method_b_detect_low(
    session_bars: pd.DataFrame,
    session_low: float,
) -> tuple[bool, float]:
    """
    Method B (TPO-based): Count distinct TPO periods touching session low area.

    Returns (is_poor, quality_score) where quality_score 0-1, higher = more poor.
    """
    touching_periods: set[str] = set()
    for _, bar in session_bars.iterrows():
        if float(bar['low']) <= (session_low + TPO_PROXIMITY_PTS):
            period = _get_tpo_period(_extract_bar_time(bar))
            if period != "?":
                touching_periods.add(period)

    n_periods = len(touching_periods)
    if n_periods == 0:
        near_bars = session_bars[
            session_bars['low'] <= (session_low + TPO_PROXIMITY_PTS)
        ]
        n_bars = len(near_bars)
        is_poor = n_bars <= 2
        quality = max(0.0, min(1.0, 1.0 - (n_bars - 1) * 0.25))
        return is_poor, quality

    is_poor = n_periods <= POOR_TPO_MAX_PERIODS
    quality = max(0.0, min(1.0, 1.0 - (n_periods - 1) / 3.0))
    return is_poor, quality


def detect_poor_extremes(
    session_bars: pd.DataFrame,
    tick_size: float = DEFAULT_TICK_SIZE,
) -> dict:
    """
    Detect poor highs and poor lows for a single session.

    Parameters
    ----------
    session_bars : pd.DataFrame
        All RTH bars for the session. Must have columns: high, low, close.
        Optionally: timestamp (for TPO period detection in Method B).
    tick_size : float
        Instrument tick size (default 0.25 for NQ).

    Returns
    -------
    dict with keys:
        poor_high, poor_low : bool
        session_high, session_low : float
        high_quality_score, low_quality_score : float (0-1, higher = more poor)
        method_a_high, method_b_high : bool (per-method results)
        method_a_low, method_b_low : bool (per-method results)
    """
    if session_bars is None or len(session_bars) == 0:
        return {
            'poor_high': False, 'poor_low': False,
            'session_high': float('nan'), 'session_low': float('nan'),
            'high_quality_score': 0.0, 'low_quality_score': 0.0,
            'method_a_high': False, 'method_b_high': False,
            'method_a_low': False, 'method_b_low': False,
        }

    session_high = float(session_bars['high'].max())
    session_low = float(session_bars['low'].min())

    # Method A: Enhanced bar analysis
    ma_high, ma_high_q = _method_a_detect_high(session_bars, session_high, tick_size)
    ma_low, ma_low_q = _method_a_detect_low(session_bars, session_low, tick_size)

    # Method B: TPO period count
    mb_high, mb_high_q = _method_b_detect_high(session_bars, session_high)
    mb_low, mb_low_q = _method_b_detect_low(session_bars, session_low)

    # Combined: poor if EITHER method flags it
    poor_high = ma_high or mb_high
    poor_low = ma_low or mb_low

    # Quality score: average of both methods (capped at 1.0)
    high_quality = min(1.0, (ma_high_q + mb_high_q) / 2.0) if poor_high else 0.0
    low_quality = min(1.0, (ma_low_q + mb_low_q) / 2.0) if poor_low else 0.0

    # If only one method flagged, use that method's quality as floor
    if poor_high:
        if ma_high and not mb_high:
            high_quality = max(high_quality, ma_high_q * 0.6)
        elif mb_high and not ma_high:
            high_quality = max(high_quality, mb_high_q * 0.6)

    if poor_low:
        if ma_low and not mb_low:
            low_quality = max(low_quality, ma_low_q * 0.6)
        elif mb_low and not ma_low:
            low_quality = max(low_quality, mb_low_q * 0.6)

    return {
        'poor_high': poor_high,
        'poor_low': poor_low,
        'session_high': session_high,
        'session_low': session_low,
        'high_quality_score': round(high_quality, 4),
        'low_quality_score': round(low_quality, 4),
        'method_a_high': ma_high,
        'method_b_high': mb_high,
        'method_a_low': ma_low,
        'method_b_low': mb_low,
    }


def compute_prior_poor_extremes(
    df: pd.DataFrame,
    tick_size: float = DEFAULT_TICK_SIZE,
) -> Dict[str, dict]:
    """
    Compute poor extremes for each session, keyed by the NEXT session's date.

    This is the format needed by the strategy: for each session date, look up
    what poor extremes existed in the PRIOR session.

    Parameters
    ----------
    df : pd.DataFrame
        Multi-session bar data. Must have a 'session_date' column (or 'date')
        plus high, low, close columns. Optionally 'timestamp' for Method B.
    tick_size : float
        Instrument tick size.

    Returns
    -------
    dict mapping session_date_str → poor_extremes dict from the prior session.
    """
    # Determine session date column
    date_col = None
    for col in ('session_date', 'date', 'Date'):
        if col in df.columns:
            date_col = col
            break

    if date_col is None:
        raise ValueError(
            "DataFrame must have a 'session_date' or 'date' column"
        )

    # Get sorted unique session dates
    session_dates = sorted(df[date_col].unique())

    # Compute poor extremes per session
    session_results = {}
    for sd in session_dates:
        session_bars = df[df[date_col] == sd].copy()
        result = detect_poor_extremes(session_bars, tick_size=tick_size)
        session_results[str(sd)] = result

    # Map: next_session_date → prior_session's poor extremes
    prior_map: Dict[str, dict] = {}
    for i in range(1, len(session_dates)):
        prior_date = str(session_dates[i - 1])
        current_date = str(session_dates[i])
        prior_map[current_date] = session_results[prior_date]

    return prior_map
