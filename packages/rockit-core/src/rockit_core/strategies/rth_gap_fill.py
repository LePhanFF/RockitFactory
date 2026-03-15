"""
Strategy: RTH Gap Fill (LONG and SHORT)

Trades the gap between RTH open and prior RTH close. When the market opens
with a gap (open != prior close), price tends to fill back to the prior close.

Study targets (both directions):
  - Frequency: 22 trades
  - Win Rate: 95.5%
  - Profit Factor: 15.81

Detection logic:
  1. Compute gap = RTH open (first IB bar open) - prior close
  2. UP gap (open > prior close + min_gap): SHORT entry, target = prior close
  3. DOWN gap (open < prior close - min_gap): LONG entry, target = prior close
  4. Entry at first IB bar open price (9:30 market open)
  5. Stop: configurable (fixed_50pt or gap_2x)
  6. Target: full fill (prior close) or half fill (50% of gap)

Implementation: Detects gap during on_session_start(), caches signal,
emits on first post-IB on_bar() call.
"""

from typing import Optional, List

import pandas as pd

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal

# Default configuration
MIN_GAP_POINTS = 10.0          # Minimum gap size to trade (filter noise)
FIXED_STOP_POINTS = 50.0       # Fixed stop distance in points
GAP_STOP_MULTIPLIER = 2.0      # Stop = gap_size * multiplier
TARGET_FILL_PCT = 1.0           # 1.0 = full fill, 0.5 = half fill
STOP_MODEL = 'fixed_50pt'       # 'fixed_50pt' or 'gap_2x'


class RTHGapFill(StrategyBase):
    """
    RTH Gap Fill: trade the gap between RTH open and prior close.

    Detects the gap at session start, caches a signal, and emits on
    first on_bar() call after IB formation.

    Parameters:
        min_gap_points: Minimum gap size in points to trade (default: 10)
        stop_model: 'fixed_50pt' or 'gap_2x' (default: 'fixed_50pt')
        target_fill_pct: 1.0 for full fill, 0.5 for half fill (default: 1.0)
        direction: 'both', 'long', or 'short' (default: 'both')
    """

    def __init__(
        self,
        min_gap_points: float = MIN_GAP_POINTS,
        stop_model: str = STOP_MODEL,
        target_fill_pct: float = TARGET_FILL_PCT,
        direction: str = 'both',
        gap_stop_multiplier: float = GAP_STOP_MULTIPLIER,
        fixed_stop_points: float = FIXED_STOP_POINTS,
    ):
        self._min_gap_points = min_gap_points
        self._stop_model = stop_model
        self._target_fill_pct = target_fill_pct
        self._direction_filter = direction.lower()
        self._gap_stop_multiplier = gap_stop_multiplier
        self._fixed_stop_points = fixed_stop_points

    @property
    def name(self) -> str:
        return "RTH Gap Fill"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._cached_signal = None
        self._signal_emitted = False

        # Need prior close and IB bars
        prior_close = session_context.get('prior_close')
        if prior_close is None:
            return

        ib_bars = session_context.get('ib_bars')
        if ib_bars is None or len(ib_bars) == 0:
            return

        # RTH open = first IB bar open
        first_bar = ib_bars.iloc[0]
        rth_open = first_bar['open']

        # Compute gap
        gap = rth_open - prior_close  # positive = UP gap, negative = DOWN gap
        gap_size = abs(gap)

        # Filter: minimum gap size
        if gap_size < self._min_gap_points:
            return

        # Determine direction
        if gap > 0:
            # UP gap: open above prior close -> SHORT to fill down
            direction = 'SHORT'
            if self._direction_filter == 'long':
                return
        else:
            # DOWN gap: open below prior close -> LONG to fill up
            direction = 'LONG'
            if self._direction_filter == 'short':
                return

        # Entry price = RTH open
        entry_price = rth_open

        # Compute stop
        if self._stop_model == 'gap_2x':
            stop_distance = gap_size * self._gap_stop_multiplier
        else:  # fixed_50pt
            stop_distance = self._fixed_stop_points

        if direction == 'SHORT':
            stop_price = entry_price + stop_distance
        else:
            stop_price = entry_price - stop_distance

        # Compute target = fill toward prior close
        fill_distance = gap_size * self._target_fill_pct
        if direction == 'SHORT':
            target_price = entry_price - fill_distance
        else:
            target_price = entry_price + fill_distance

        # Get timestamp from first bar
        bar_ts = first_bar.get('timestamp', first_bar.name) if hasattr(first_bar, 'name') else first_bar.get('timestamp')

        setup_type = f'RTH_GAP_FILL_{direction}'

        self._cached_signal = Signal(
            timestamp=bar_ts,
            direction=direction,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            strategy_name=self.name,
            setup_type=setup_type,
            day_type='neutral',
            trend_strength='moderate',
            confidence='high',
            metadata={
                'gap_direction': 'UP' if gap > 0 else 'DOWN',
                'gap_size': round(gap_size, 2),
                'prior_close': prior_close,
                'rth_open': rth_open,
                'stop_model': self._stop_model,
                'target_fill_pct': self._target_fill_pct,
            },
        )

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        # Emit cached signal on first bar after IB
        if self._cached_signal is not None and not self._signal_emitted:
            self._signal_emitted = True
            signal = self._cached_signal
            self._cached_signal = None
            return signal
        return None
