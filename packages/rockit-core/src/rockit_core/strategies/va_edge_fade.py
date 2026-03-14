"""
Strategy: VA Edge Fade — Prior Day Value Area Edge Rejection

Trades reversals when price pokes beyond prior day's VAH or VAL and fails
to sustain (acceptance fails), fading back inside the Value Area.

Quant study results (273 NQ sessions, V2):
  Best config (ETH edge_20 + 3R SHORT-only):
    - 117 trades, 35.0% WR, PF 1.70, +$38,643
    - Avg win $2,283, avg loss $723, expectancy $330/trade

  Balanced config (ETH edge_10 + 2R SHORT-only):
    - 117 trades, 42.7% WR, PF 1.60, +$22,033

Production config (from V2 recommendation A):
  - direction: SHORT only (LONG at VAL is net loser)
  - stop_mode: edge_20 (VA edge + 20 pts)
  - target_mode: 3r (3x risk)
  - accept_bars: 2 (2x 5-min closes confirming rejection)
  - poke_min: 5 pts (minimum poke beyond VA edge)
  - max_touch: 1 (first touch only — edge diminishes on retests)
  - day_type_filter: OFF (strategy already fires mostly on b_days)

Key findings:
  - SHORT-only is the single most impactful filter
  - Higher R targets (3R) beat 2R on PF in SHORT-only configs
  - Midday entries are losers — morning entries best
  - PF 1.70 with 35% WR = outsized winners (3.16:1 win/loss ratio)
"""

from datetime import time as _time
from typing import Optional, List

import pandas as pd

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal

# ── Parameters ────────────────────────────────────────────────
ENTRY_START = _time(10, 30)        # After IB formation
ENTRY_CUTOFF = _time(14, 0)        # No entries after 2 PM ET
POKE_MIN_PTS = 5.0                 # Min pts beyond VA edge to count as poke
ACCEPT_BARS = 3                    # N consecutive 5-min closes confirming fade (study: 3 bars = PF 2.07 vs 2 bars = PF 1.46)
EDGE_BUFFER_PTS = 20.0             # Stop buffer beyond VA edge
MAX_TOUCH_COUNT = 1                # Only first touch (per edge)
MIN_VA_WIDTH_PTS = 0.0             # Minimum VA width (0 = no filter)


class VAEdgeFade(StrategyBase):
    """
    VA Edge Fade: trades rejection at prior day Value Area edges.

    Configurable via constructor:
      - short_only: only SHORT at VAH (default True per V2 study)
      - stop_mode: 'edge_20' (VA edge + 20pt), 'edge_10', 'atr2x'
      - target_mode: '3r', '2r', 'poc'
      - accept_bars: number of consecutive bars confirming fade
      - poke_min: minimum pts beyond edge to qualify
      - max_touch: max touches per edge per session
      - min_va_width: minimum prior VA width to trade
    """

    def __init__(
        self,
        short_only: bool = True,
        stop_mode: str = 'edge_20',
        target_mode: str = '3r',
        accept_bars: int = ACCEPT_BARS,
        poke_min: float = POKE_MIN_PTS,
        max_touch: int = MAX_TOUCH_COUNT,
        min_va_width: float = MIN_VA_WIDTH_PTS,
    ):
        self._short_only = short_only
        self._stop_mode = stop_mode
        self._target_mode = target_mode
        self._accept_bars = accept_bars
        self._poke_min = poke_min
        self._max_touch = max_touch
        self._min_va_width = min_va_width

    @property
    def name(self) -> str:
        return "VA Edge Fade"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types (study showed day_type filter OFF is better)

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._ib_high = ib_high
        self._ib_low = ib_low
        self._ib_range = ib_range

        # Prior day VA levels
        self._prior_vah = session_context.get('prior_va_vah')
        self._prior_val = session_context.get('prior_va_val')
        self._prior_poc = session_context.get('prior_va_poc')

        # Compute VA width
        if self._prior_vah is not None and self._prior_val is not None:
            self._va_width = self._prior_vah - self._prior_val
        else:
            self._va_width = 0.0

        # ATR from session context
        self._atr14 = session_context.get('atr14', 20.0)

        # State: VAH tracking
        self._vah_touch_count = 0
        self._vah_poke_detected = False
        self._vah_accept_count = 0     # Consecutive bars closing below VAH after poke
        self._vah_spike_high = None
        self._vah_traded = False

        # State: VAL tracking
        self._val_touch_count = 0
        self._val_poke_detected = False
        self._val_accept_count = 0     # Consecutive bars closing above VAL after poke
        self._val_spike_low = None
        self._val_traded = False

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        # Skip if no prior VA data
        if self._prior_vah is None or self._prior_val is None:
            return None

        # Skip if VA width too narrow
        if self._va_width < self._min_va_width:
            return None

        # Time filter
        bar_time = session_context.get('bar_time')
        if bar_time is not None:
            if bar_time < ENTRY_START or bar_time >= ENTRY_CUTOFF:
                return None

        price = bar['close']
        high = bar['high']
        low = bar['low']
        day_type = session_context.get('day_type', '')

        # ── VAH Fade (SHORT) ─────────────────────────────────────
        if not self._vah_traded:
            signal = self._check_vah_fade(bar, bar_index, price, high, low,
                                           session_context, day_type)
            if signal is not None:
                return signal

        # ── VAL Fade (LONG) — only if short_only is False ────────
        if not self._short_only and not self._val_traded:
            signal = self._check_val_fade(bar, bar_index, price, high, low,
                                           session_context, day_type)
            if signal is not None:
                return signal

        return None

    def _check_vah_fade(self, bar, bar_index, price, high, low, ctx, day_type):
        """SHORT when price pokes above VAH and confirms fade back inside."""
        vah = self._prior_vah

        # Phase 1: Detect poke above VAH
        if not self._vah_poke_detected:
            if high >= vah + self._poke_min:
                self._vah_touch_count += 1
                if self._vah_touch_count > self._max_touch:
                    return None
                self._vah_poke_detected = True
                self._vah_spike_high = high
                self._vah_accept_count = 0
            return None

        # Track spike extreme
        if high > self._vah_spike_high:
            self._vah_spike_high = high

        # Phase 2: Acceptance counting — bar closes below VAH
        if price < vah:
            self._vah_accept_count += 1
        else:
            # Reset acceptance count if bar closes above VAH again
            self._vah_accept_count = 0

        # Phase 3: Confirmed fade — N consecutive closes below VAH
        if self._vah_accept_count >= self._accept_bars:
            entry_price = price
            stop_price = self._compute_stop(entry_price, 'SHORT')
            target_price = self._compute_target(entry_price, stop_price, 'SHORT', ctx)

            self._vah_traded = True

            return Signal(
                timestamp=self._get_timestamp(bar),
                direction='SHORT',
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                strategy_name=self.name,
                setup_type='VAH_EDGE_FADE',
                day_type=day_type,
                trend_strength=ctx.get('trend_strength', ''),
                confidence='medium',
                metadata={
                    'level': 'VAH',
                    'prior_vah': self._prior_vah,
                    'prior_val': self._prior_val,
                    'prior_poc': self._prior_poc,
                    'spike_high': self._vah_spike_high,
                    'va_width': self._va_width,
                    'poke_pts': self._vah_spike_high - vah,
                    'accept_bars': self._vah_accept_count,
                    'touch_number': self._vah_touch_count,
                },
            )

        return None

    def _check_val_fade(self, bar, bar_index, price, high, low, ctx, day_type):
        """LONG when price pokes below VAL and confirms fade back inside."""
        val = self._prior_val

        # Phase 1: Detect poke below VAL
        if not self._val_poke_detected:
            if low <= val - self._poke_min:
                self._val_touch_count += 1
                if self._val_touch_count > self._max_touch:
                    return None
                self._val_poke_detected = True
                self._val_spike_low = low
                self._val_accept_count = 0
            return None

        # Track spike extreme
        if low < self._val_spike_low:
            self._val_spike_low = low

        # Phase 2: Acceptance counting — bar closes above VAL
        if price > val:
            self._val_accept_count += 1
        else:
            self._val_accept_count = 0

        # Phase 3: Confirmed fade — N consecutive closes above VAL
        if self._val_accept_count >= self._accept_bars:
            entry_price = price
            stop_price = self._compute_stop(entry_price, 'LONG')
            target_price = self._compute_target(entry_price, stop_price, 'LONG', ctx)

            self._val_traded = True

            return Signal(
                timestamp=self._get_timestamp(bar),
                direction='LONG',
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                strategy_name=self.name,
                setup_type='VAL_EDGE_FADE',
                day_type=day_type,
                trend_strength=ctx.get('trend_strength', ''),
                confidence='medium',
                metadata={
                    'level': 'VAL',
                    'prior_vah': self._prior_vah,
                    'prior_val': self._prior_val,
                    'prior_poc': self._prior_poc,
                    'spike_low': self._val_spike_low,
                    'va_width': self._va_width,
                    'poke_pts': val - self._val_spike_low,
                    'accept_bars': self._val_accept_count,
                    'touch_number': self._val_touch_count,
                },
            )

        return None

    # ── Stop / Target Computation ───────────────────────────────

    def _compute_stop(self, entry_price, direction):
        """Compute stop price based on stop_mode."""
        if self._stop_mode == 'edge_20':
            if direction == 'SHORT':
                return self._prior_vah + EDGE_BUFFER_PTS
            else:
                return self._prior_val - EDGE_BUFFER_PTS
        elif self._stop_mode == 'edge_10':
            if direction == 'SHORT':
                return self._prior_vah + 10.0
            else:
                return self._prior_val - 10.0
        elif self._stop_mode == 'atr2x':
            risk = 2.0 * self._atr14
            if direction == 'SHORT':
                return entry_price + risk
            else:
                return entry_price - risk
        else:
            # Default: edge_20
            if direction == 'SHORT':
                return self._prior_vah + EDGE_BUFFER_PTS
            else:
                return self._prior_val - EDGE_BUFFER_PTS

    def _compute_target(self, entry_price, stop_price, direction, ctx):
        """Compute target price based on target_mode."""
        risk = abs(entry_price - stop_price)

        if self._target_mode == '3r':
            if direction == 'SHORT':
                return entry_price - 3.0 * risk
            else:
                return entry_price + 3.0 * risk
        elif self._target_mode == '2r':
            if direction == 'SHORT':
                return entry_price - 2.0 * risk
            else:
                return entry_price + 2.0 * risk
        elif self._target_mode == 'poc':
            poc = self._prior_poc
            if poc is not None:
                return poc
            # Fallback: midpoint of VA
            return (self._prior_vah + self._prior_val) / 2.0
        else:
            # Fallback: 3R
            if direction == 'SHORT':
                return entry_price - 3.0 * risk
            else:
                return entry_price + 3.0 * risk

    # ── Helpers ──────────────────────────────────────────────────

    def _get_timestamp(self, bar):
        """Extract timestamp from bar Series."""
        if 'timestamp' in bar.index:
            return bar['timestamp']
        if hasattr(bar, 'name'):
            return bar.name
        return None
