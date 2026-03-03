"""
Strategy: 20% IB Extension Rule — Continuation Entry with Structure Stops

When IB extends >20% of its range, the breakout has momentum.
Ride the continuation with structure-based stops.

Study targets (strategy-studies/20p-rule/ v2):
  - Frequency: 3.7 trades/month
  - Win Rate: 45.5%
  - Profit Factor: 1.78
  - Monthly P&L: $496 (5 MNQ)
  - Risk/trade: ~32 pts median

v2 (structure stops) >> v1 (IB boundary stops):
  - Risk: 32 pts vs 219 pts (85% reduction)
  - PF: 1.78 vs 1.25
  - Clean exits: 24 stops / 20 targets / 0 EOD vs 6/11/27

Entry Model (two-phase):
  Phase 1 — Setup: price extends >20% of IB range beyond IBH or IBL
  Phase 2 — Acceptance: 3x consecutive 5-min closes beyond IB boundary
  Entry at current price on acceptance confirmation
  Stop: 2x ATR from entry
  Target: 2R (2x the stop distance)
  Direction: follows the IB extension direction
  Filter: at least moderate trend strength, delta confirming
"""

from datetime import time as _time
from typing import Optional, List
import pandas as pd
import numpy as np

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal

# ── Parameters ────────────────────────────────────────────────
IB_EXTENSION_THRESHOLD = 0.20    # Minimum 20% IB range extension (setup trigger)
ACCEPT_5M_BARS = 3               # 3 consecutive 5-min closes for acceptance
ATR_PERIOD = 14
ATR_STOP_MULT = 2.0              # Stop = 2x ATR from entry
TARGET_R_MULTIPLE = 2.0           # 2R target
ENTRY_CUTOFF = _time(14, 0)      # No entries after 2 PM ET
MIN_IB_RANGE = 30.0              # Minimum IB range for meaningful trades
MAX_ENTRIES_PER_SESSION = 1


def _compute_atr14(df: pd.DataFrame, n: int = ATR_PERIOD) -> float:
    """Compute ATR(14) from OHLC bars."""
    if len(df) < 3:
        return float((df['high'] - df['low']).mean()) if len(df) > 0 else 20.0
    h = df['high']
    l = df['low']
    pc = df['close'].shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(n, min_periods=3).mean().iloc[-1]
    return float(atr) if not pd.isna(atr) else float((h - l).mean())


class TwentyPercentRule(StrategyBase):
    """
    20P Rule: IB Extension Continuation with structure-based stops.

    Two-phase approach:
      Phase 1: Detect >20% IB extension (setup trigger, one-time event)
      Phase 2: Wait for 3x 5-min acceptance beyond IB boundary
    """

    @property
    def name(self) -> str:
        return "20P IB Extension"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # Can fire on any day type with sufficient extension

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._ib_high = ib_high
        self._ib_low = ib_low
        self._ib_range = ib_range
        self._triggered = False
        self._entry_count = 0

        # Phase 1 state: has the 20% extension event occurred?
        self._extension_triggered = False
        self._extension_direction = None  # 'LONG' or 'SHORT'

        # Phase 2 state: 5-min acceptance tracking
        self._consecutive_5m = 0
        self._last_5m_bar = -1

        # ATR from IB bars for stop computation
        ib_bars = session_context.get('ib_bars')
        if ib_bars is not None and len(ib_bars) > 0:
            self._atr14 = _compute_atr14(ib_bars)
        else:
            self._atr14 = session_context.get('atr14', 20.0)

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        if self._triggered or self._entry_count >= MAX_ENTRIES_PER_SESSION:
            return None

        # Minimum IB range check
        if self._ib_range < MIN_IB_RANGE:
            return None

        bar_time = session_context.get('bar_time')
        if bar_time and bar_time >= ENTRY_CUTOFF:
            return None

        current_price = bar['close']

        # === Phase 1: Detect 20% extension event (one-time trigger) ===
        if not self._extension_triggered:
            ext_threshold = self._ib_range * IB_EXTENSION_THRESHOLD

            if current_price > self._ib_high + ext_threshold:
                self._extension_triggered = True
                self._extension_direction = 'LONG'
            elif current_price < self._ib_low - ext_threshold:
                self._extension_triggered = True
                self._extension_direction = 'SHORT'
            else:
                return None

        # === Phase 2: Wait for 3x 5-min acceptance beyond IB boundary ===
        # Require at least moderate trend strength
        strength = session_context.get('trend_strength', 'weak')
        if strength == 'weak':
            return None

        is_5m_end = ((bar_index + 1) % 5 == 0)
        if not is_5m_end or bar_index <= self._last_5m_bar:
            return None

        self._last_5m_bar = bar_index

        # Check if bar closes beyond IB boundary (not beyond extension threshold)
        if self._extension_direction == 'LONG':
            if current_price > self._ib_high:
                self._consecutive_5m += 1
            else:
                self._consecutive_5m = 0
        elif self._extension_direction == 'SHORT':
            if current_price < self._ib_low:
                self._consecutive_5m += 1
            else:
                self._consecutive_5m = 0

        if self._consecutive_5m < ACCEPT_5M_BARS:
            return None

        # === Generate signal ===
        direction = self._extension_direction
        entry_price = current_price
        risk = ATR_STOP_MULT * self._atr14

        if risk <= 0:
            return None

        if direction == 'LONG':
            stop_price = entry_price - risk
            target_price = entry_price + TARGET_R_MULTIPLE * risk
        else:
            stop_price = entry_price + risk
            target_price = entry_price - TARGET_R_MULTIPLE * risk

        # Delta confirmation: buyers for LONG, sellers for SHORT
        delta = bar.get('delta', 0)
        if pd.isna(delta):
            delta = 0

        if direction == 'LONG' and delta <= 0:
            return None
        if direction == 'SHORT' and delta >= 0:
            return None

        self._triggered = True
        self._entry_count += 1

        return Signal(
            timestamp=bar.get('timestamp', bar.name) if hasattr(bar, 'name') else bar.get('timestamp'),
            direction=direction,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            strategy_name=self.name,
            setup_type=f'20P_IB_EXT_{direction}',
            day_type=session_context.get('day_type', ''),
            trend_strength=session_context.get('trend_strength', ''),
            confidence='high',
            metadata={
                'ib_range': self._ib_range,
                'atr14': self._atr14,
                'acceptance_bars': ACCEPT_5M_BARS,
                'risk_pts': risk,
            },
        )
