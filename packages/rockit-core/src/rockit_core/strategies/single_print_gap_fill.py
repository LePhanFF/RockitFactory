"""
Strategy: Single Print Gap Fill
================================

Single prints in the Market Profile represent areas of fast, one-directional
movement where only one TPO letter printed. These areas act as "gaps" in
the profile that tend to get filled (revisited) in subsequent sessions.
This strategy trades the fill of prior-session single print zones.

Study Results (optimal config):
  - Config: min_10 ticks zone size, above_vah location, immediate entry,
    atr_1x stop, 2R target, morning window, BOTH directions
  - 117 trades, 69.2% WR, PF 4.49, $22,525

Logic:
  1. on_session_start: Identify prior-session single print zones from
     session_context (tpo_data or prior_day). Filter to zones >= 10 ticks
     and zones above prior VAH.
  2. on_bar: Morning window only (before 11:00 / bar_index < 30). When price
     reaches a stored zone, emit signal immediately. Zone above price = SHORT
     (expect rejection), zone below price = LONG (expect bounce).
  3. Stop: 1x ATR. Target: 2R.
  4. One signal per zone max.
"""

from datetime import time as _time
from typing import Optional, List

import pandas as pd
import numpy as np

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal

# ── Constants ────────────────────────────────────────────────
MIN_ZONE_TICKS = 10          # Minimum zone size in ticks
TICK_SIZE = 0.25             # NQ tick size (pts)
MIN_ZONE_PTS = MIN_ZONE_TICKS * TICK_SIZE  # 2.5 pts
MORNING_CUTOFF = _time(11, 0)  # No entries after 11:00 AM ET
MORNING_BAR_LIMIT = 30       # Fallback: ~30 bars post-IB ≈ 11:00
ATR_STOP_MULT = 1.0          # Stop = 1x ATR
TARGET_R = 2.0               # Target = 2R
MAX_SIGNALS_PER_SESSION = 1  # One signal per session


class SinglePrintGapFill(StrategyBase):
    """
    Single Print Gap Fill: trade the fill of prior-session TPO single print zones.

    Single prints above VAH that get revisited tend to reject (SHORT).
    Single prints below current price that get revisited tend to bounce (LONG).
    """

    @property
    def name(self) -> str:
        return "SP Gap Fill"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._signal_count = 0
        self._touched_zones = set()  # Track which zones already signaled
        self._zones = []  # List of valid single print zones

        # Get prior VAH for zone location filtering
        prior_vah = session_context.get('prior_va_vah') or session_context.get('prior_va_high')
        prior_val = session_context.get('prior_va_val') or session_context.get('prior_va_low')

        # prior_vah may be None for first session — zones will be filtered in loop below

        # Get ATR for stop calculation
        self._atr = session_context.get('atr14', 20.0)
        if self._atr is None or (isinstance(self._atr, float) and pd.isna(self._atr)):
            self._atr = 20.0

        # Extract single print zones from tpo_data or prior_day
        raw_zones = self._extract_single_print_zones(session_context)

        # Filter zones: >= 10 ticks, use enrichment's pre-computed location
        for zone in raw_zones:
            zone_high = zone['high']
            zone_low = zone['low']
            zone_size_pts = zone_high - zone_low

            # Size filter: must be >= MIN_ZONE_TICKS
            zone_size_ticks = zone_size_pts / TICK_SIZE
            if zone_size_ticks < MIN_ZONE_TICKS:
                continue

            # Use enrichment's pre-computed location field
            # (enrichment classifies as above_vah/below_val/within_va/unknown)
            location = zone.get('location', '')

            # Fallback: re-compute if enrichment didn't provide location
            if not location or location == 'unknown':
                if prior_vah is not None and not (isinstance(prior_vah, float) and pd.isna(prior_vah)):
                    if zone_low >= prior_vah:
                        location = 'above_vah'
                    elif prior_val is not None and not (isinstance(prior_val, float) and pd.isna(prior_val)) and zone_high <= prior_val:
                        location = 'below_val'
                    else:
                        location = 'within_va'
                else:
                    location = 'unknown'

            # Only trade zones outside VA (above_vah or below_val)
            if location not in ('above_vah', 'below_val'):
                continue

            self._zones.append({
                'high': zone_high,
                'low': zone_low,
                'size_ticks': zone_size_ticks,
                'size_pts': zone_size_pts,
                'location': location,
            })

        self._day_type = session_context.get('day_type', '')
        self._trend_strength = session_context.get('trend_strength', '')

    def _extract_single_print_zones(self, session_context: dict) -> list:
        """
        Extract single print zones from session context.

        Looks in tpo_data.single_prints or prior_day.single_prints.
        Each zone is a dict with 'high' and 'low' keys.
        """
        zones = []

        # Try tpo_data first
        tpo_data = session_context.get('tpo_data', {})
        if isinstance(tpo_data, dict):
            sp = tpo_data.get('single_prints', [])
            if isinstance(sp, list):
                zones.extend(sp)

        # Try prior_day
        if not zones:
            prior_day = session_context.get('prior_day', {})
            if isinstance(prior_day, dict):
                sp = prior_day.get('single_prints', [])
                if isinstance(sp, list):
                    zones.extend(sp)

        # Validate zone dicts have required keys
        valid = []
        for z in zones:
            if isinstance(z, dict) and 'high' in z and 'low' in z:
                try:
                    h = float(z['high'])
                    l = float(z['low'])
                    if not (pd.isna(h) or pd.isna(l)) and h > l:
                        valid.append({'high': h, 'low': l})
                except (ValueError, TypeError):
                    continue

        return valid

    def on_pre_ib_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        """Single print fills can happen during IB formation (morning window)."""
        return self._check_zone_touch(bar, bar_index, session_context)

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        return self._check_zone_touch(bar, bar_index, session_context)

    def _check_zone_touch(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        if not self._zones or self._signal_count >= MAX_SIGNALS_PER_SESSION:
            return None

        # Morning window filter
        bar_time = session_context.get('bar_time')
        if bar_time and bar_time >= MORNING_CUTOFF:
            return None
        if bar_time is None and bar_index >= MORNING_BAR_LIMIT:
            return None

        close = float(bar['close'])
        high = float(bar['high'])
        low = float(bar['low'])

        for i, zone in enumerate(self._zones):
            if i in self._touched_zones:
                continue

            zone_high = zone['high']
            zone_low = zone['low']

            # Check if price reaches into the zone
            price_touches_zone = (high >= zone_low and low <= zone_high)

            if not price_touches_zone:
                continue

            # Mark zone as touched
            self._touched_zones.add(i)

            # Determine direction from zone location:
            # above_vah → SHORT (price reaches up to fill zone, expect rejection)
            # below_val → LONG (price reaches down to fill zone, expect bounce)
            # Study best: above_vah|immediate|atr_1x|2R|morning|BOTH = 117t, 69.2% WR, PF 4.49
            # NOTE: In practice, zone fill entries via backtest engine enter at
            # market when price touches zone, so direction is zone-dependent.
            zone_loc = zone.get('location', '')
            if zone_loc == 'above_vah':
                # Zone above VAH: price rose into zone, expect rejection → SHORT
                direction = 'SHORT'
                entry = close
                stop = entry + ATR_STOP_MULT * self._atr
                risk = stop - entry
                target = entry - TARGET_R * risk
            elif zone_loc == 'below_val':
                # Zone below VAL: price fell into zone, expect bounce → LONG
                direction = 'LONG'
                entry = close
                stop = entry - ATR_STOP_MULT * self._atr
                risk = entry - stop
                target = entry + TARGET_R * risk
            else:
                continue  # Skip zones with unknown location

            if risk <= 0:
                continue

            self._signal_count += 1

            bar_ts = bar.get('timestamp', bar.name) if hasattr(bar, 'name') else bar.get('timestamp')

            return Signal(
                timestamp=bar_ts,
                direction=direction,
                entry_price=entry,
                stop_price=stop,
                target_price=target,
                strategy_name=self.name,
                setup_type=f'SP_GAP_FILL_{direction}',
                day_type=self._day_type,
                trend_strength=self._trend_strength,
                confidence='high',
                metadata={
                    'zone_high': round(zone_high, 2),
                    'zone_low': round(zone_low, 2),
                    'zone_size_ticks': round(zone['size_ticks'], 1),
                    'zone_location': zone['location'],
                    'atr': round(self._atr, 2),
                },
            )

        return None
