"""
Strategy: IB Retracement — Fibonacci Pullback Continuation After IB Extension

After the Initial Balance (IB) forms at 10:30 ET, price often retraces 50-61.8%
of the IB range before continuing in the impulse direction. This is a CONTINUATION
trade: enter on the pullback, ride the extension.

Quant study results (273 NQ sessions):
  V1: ALL 16 configs negative expectancy. Best PF 0.77. REJECTED.
  V2 (liquidity sweep): Best config IB>=300 sweep+VWAP confirm+1.5xIB
    - 6 trades, 50% WR, PF 3.13, +$10,213 — but only 6 trades

  Key findings:
    - Fundamental thesis problem: retracement makes day look like B-day,
      which contradicts the continuation premise
    - LONG trades catastrophically bad (0.31 PF in V1)
    - SHORT marginally profitable in V1 (1.21 PF, 13 trades — too few)
    - Liquidity sweep >> IB close position for direction detection
    - VWAP confirmation is the only entry model producing positive configs
    - IB >= 300 is the sweet spot (but rare — 13.2% of sessions)

  VERDICT: REJECTED for production. Kept for reference/future retesting.
  Set enabled: false in strategies.yaml.
"""

from datetime import time as _time
from typing import Optional, List

import pandas as pd

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal

# ── Parameters ────────────────────────────────────────────────
ENTRY_START = _time(10, 30)        # After IB close
ENTRY_CUTOFF = _time(12, 30)       # No entries after 12:30 ET
MIN_IB_RANGE = 80.0                # Minimum IB range (pts)
FIB_ZONE_LOW = 0.50                # Lower fib level (50% retrace)
FIB_ZONE_HIGH = 0.618              # Upper fib level (61.8% retrace)
IB_CLOSE_THRESHOLD = 0.30          # Top/bottom 30% of IB for impulse detection
STOP_BUFFER_PTS = 10.0             # Buffer beyond IB extreme for stop


class IBRetracement(StrategyBase):
    """
    IB Retracement: continuation trade on fib pullback after IB impulse.

    Configurable via constructor:
      - min_ib_range: minimum IB range in pts to qualify
      - fib_low: lower fib level (default 0.50)
      - fib_high: upper fib level (default 0.618)
      - ib_close_threshold: how extreme IB close must be (default 0.30)
      - target_mode: 'opp_ib', '2r', '1.5x_ib', '1r'
      - stop_buffer: pts beyond IB extreme for stop
    """

    def __init__(
        self,
        min_ib_range: float = MIN_IB_RANGE,
        fib_low: float = FIB_ZONE_LOW,
        fib_high: float = FIB_ZONE_HIGH,
        ib_close_threshold: float = IB_CLOSE_THRESHOLD,
        target_mode: str = 'opp_ib',
        stop_buffer: float = STOP_BUFFER_PTS,
    ):
        self._min_ib_range = min_ib_range
        self._fib_low = fib_low
        self._fib_high = fib_high
        self._ib_close_threshold = ib_close_threshold
        self._target_mode = target_mode
        self._stop_buffer = stop_buffer

    @property
    def name(self) -> str:
        return "IB Retracement"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types (most trades end up as b_day anyway)

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._ib_high = ib_high
        self._ib_low = ib_low
        self._ib_range = ib_range
        self._ib_mid = (ib_high + ib_low) / 2.0

        # Determine impulse direction from IB close position
        # This is the last bar's close within the IB period
        ib_close = session_context.get('ib_close', self._ib_mid)
        if self._ib_range > 0:
            close_position = (ib_close - ib_low) / self._ib_range
        else:
            close_position = 0.5

        # Impulse direction
        if close_position >= (1.0 - self._ib_close_threshold):
            self._impulse_direction = 'UP'    # Close in top 30% -> bullish impulse
        elif close_position <= self._ib_close_threshold:
            self._impulse_direction = 'DOWN'  # Close in bottom 30% -> bearish impulse
        else:
            self._impulse_direction = None     # Middle -> no clear impulse

        # Compute fib retracement zone
        if self._impulse_direction == 'UP':
            # Bullish impulse: retrace from high toward low
            # Fib 50% from high = IB_HIGH - 0.50 * IB_RANGE
            self._fib_zone_upper = ib_high - self._fib_low * ib_range
            self._fib_zone_lower = ib_high - self._fib_high * ib_range
        elif self._impulse_direction == 'DOWN':
            # Bearish impulse: retrace from low toward high
            self._fib_zone_lower = ib_low + self._fib_low * ib_range
            self._fib_zone_upper = ib_low + self._fib_high * ib_range
        else:
            self._fib_zone_upper = None
            self._fib_zone_lower = None

        # State
        self._signal_emitted = False
        self._in_fib_zone = False

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        # Skip if already traded
        if self._signal_emitted:
            return None

        # Skip if no impulse direction detected
        if self._impulse_direction is None:
            return None

        # Skip if IB range too narrow
        if self._ib_range < self._min_ib_range:
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

        # Check if price enters fib zone
        if self._fib_zone_lower is None or self._fib_zone_upper is None:
            return None

        if self._impulse_direction == 'UP':
            # Bullish: wait for price to retrace DOWN into fib zone, then bounce
            if low <= self._fib_zone_upper and low >= self._fib_zone_lower:
                self._in_fib_zone = True

            if self._in_fib_zone and price > self._fib_zone_upper:
                # Rejection confirmed: price bounced out of fib zone upward
                entry_price = price
                stop_price = self._ib_low - self._stop_buffer
                target_price = self._compute_target(entry_price, stop_price, 'LONG')

                self._signal_emitted = True

                return Signal(
                    timestamp=self._get_timestamp(bar),
                    direction='LONG',
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    strategy_name=self.name,
                    setup_type='IB_RETRACE_LONG',
                    day_type=day_type,
                    trend_strength=session_context.get('trend_strength', ''),
                    confidence='low',
                    metadata={
                        'impulse': 'UP',
                        'ib_high': self._ib_high,
                        'ib_low': self._ib_low,
                        'ib_range': self._ib_range,
                        'fib_zone': [self._fib_zone_lower, self._fib_zone_upper],
                    },
                )

        elif self._impulse_direction == 'DOWN':
            # Bearish: wait for price to retrace UP into fib zone, then drop
            if high >= self._fib_zone_lower and high <= self._fib_zone_upper:
                self._in_fib_zone = True

            if self._in_fib_zone and price < self._fib_zone_lower:
                # Rejection confirmed: price dropped out of fib zone downward
                entry_price = price
                stop_price = self._ib_high + self._stop_buffer
                target_price = self._compute_target(entry_price, stop_price, 'SHORT')

                self._signal_emitted = True

                return Signal(
                    timestamp=self._get_timestamp(bar),
                    direction='SHORT',
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    strategy_name=self.name,
                    setup_type='IB_RETRACE_SHORT',
                    day_type=day_type,
                    trend_strength=session_context.get('trend_strength', ''),
                    confidence='low',
                    metadata={
                        'impulse': 'DOWN',
                        'ib_high': self._ib_high,
                        'ib_low': self._ib_low,
                        'ib_range': self._ib_range,
                        'fib_zone': [self._fib_zone_lower, self._fib_zone_upper],
                    },
                )

        return None

    # ── Target Computation ───────────────────────────────────────

    def _compute_target(self, entry_price, stop_price, direction):
        """Compute target price based on target_mode."""
        risk = abs(entry_price - stop_price)

        if self._target_mode == 'opp_ib':
            if direction == 'LONG':
                return self._ib_high
            else:
                return self._ib_low
        elif self._target_mode == '2r':
            if direction == 'LONG':
                return entry_price + 2.0 * risk
            else:
                return entry_price - 2.0 * risk
        elif self._target_mode == '1.5x_ib':
            if direction == 'LONG':
                return entry_price + 1.5 * self._ib_range
            else:
                return entry_price - 1.5 * self._ib_range
        elif self._target_mode == '1r':
            if direction == 'LONG':
                return entry_price + risk
            else:
                return entry_price - risk
        else:
            # Default: opposite IB edge
            if direction == 'LONG':
                return self._ib_high
            else:
                return self._ib_low

    # ── Helpers ──────────────────────────────────────────────────

    def _get_timestamp(self, bar):
        """Extract timestamp from bar Series."""
        if 'timestamp' in bar.index:
            return bar['timestamp']
        if hasattr(bar, 'name'):
            return bar.name
        return None
