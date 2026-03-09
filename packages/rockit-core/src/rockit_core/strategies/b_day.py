"""
Strategy 6: B-Day IBL Fade — 30-Minute Acceptance Model (Config H)

Research Source: Balance Day IBL Fade study (259 sessions, NQ 1-min bars)

Key Finding: "For IB edges, delta provides zero value (-2pp). The market
needs TIME to prove rejection." The 30-min acceptance model (+28pp edge)
is the correct primary filter.

Entry Model (30-min acceptance):
  1. Detect first IBL touch (low within 5 pts of IBL)
  2. Wait 30 bars (30 min at 1-min resolution)
  3. At bar 30: if close > IBL → acceptance confirmed → ENTER LONG
  4. If close <= IBL at bar 30 → failed acceptance → no trade

First-Touch Filter (Tier 3):
  - Only trade the FIRST IBL touch per session
  - Touch #1 = 33% raw success vs #2 = 20%, #3 = 13%

VWAP Alignment (confidence booster, not hard filter):
  - At touch time: VWAP > IB mid → confidence = 'high'
  - VWAP aligned LONG = 46% raw success (2.7x baseline)
  - Still takes the trade either way — acceptance is the primary filter

Expanded Day Types:
  - LONG works on B-Day (76%), P-Day (62%), Neutral (61%)
  - "You CANNOT predict EOD day type at IB close (20-32% accuracy).
    Fade every IB edge and let the acceptance model filter."

Stops: IBL - 10% of IB range
Targets: IB midpoint (POC/VWAP mean reversion)
Time gate: No entries after 14:00
Max 1 LONG per session

Study Results:
  - Config H: 64% WR, 24.2 trades/mo
  - Tier 3 (first-touch): 82% WR, PF 9.35, 3.4 trades/mo
"""

from typing import Optional, List

import pandas as pd

from datetime import time as _time
from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal
from rockit_core.config.constants import (
    BDAY_ACCEPTANCE_BARS,
    BDAY_TOUCH_TOLERANCE,
    BDAY_STOP_IB_BUFFER,
)

# B-Day last entry time: entries after 14:00 have insufficient time to reach target.
BDAY_LAST_ENTRY_TIME = _time(14, 0)


class BDayStrategy(StrategyBase):

    @property
    def name(self) -> str:
        return "B-Day"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types — study says day type is unpredictable at IB close

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._ib_high = ib_high
        self._ib_low = ib_low
        self._ib_range = ib_range
        self._ib_mid = (ib_high + ib_low) / 2

        self._val_fade_taken = False
        self._touch_bar_index = None
        self._first_touch_taken = False
        self._vwap_aligned = False

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        # Already traded this session
        if self._val_fade_taken:
            return None

        # Time gate
        bar_time = session_context.get('bar_time')
        if bar_time and bar_time >= BDAY_LAST_ENTRY_TIME:
            return None

        current_price = bar['close']

        # Phase 1: Detect first IBL touch
        if self._touch_bar_index is None and not self._first_touch_taken:
            if bar['low'] <= self._ib_low + BDAY_TOUCH_TOLERANCE:
                self._touch_bar_index = bar_index
                self._first_touch_taken = True
                # Check VWAP alignment at touch time
                vwap = bar.get('vwap')
                self._vwap_aligned = vwap is not None and vwap > self._ib_mid
                return None  # Don't enter yet, wait for acceptance

        # Phase 2: Wait for acceptance (30 bars after touch)
        if self._touch_bar_index is not None:
            bars_since_touch = bar_index - self._touch_bar_index
            if bars_since_touch < BDAY_ACCEPTANCE_BARS:
                return None  # Still waiting

            # Phase 3: Check acceptance at bar 30
            # Study: "closes inside IB" = close > IBL AND close < IBH
            # This naturally excludes trend days where price runs past IBH
            if bars_since_touch == BDAY_ACCEPTANCE_BARS:
                if current_price > self._ib_low and current_price < self._ib_high:
                    # Acceptance confirmed — price is inside IB → ENTER LONG
                    entry_price = current_price
                    stop_price = self._ib_low - (self._ib_range * BDAY_STOP_IB_BUFFER)
                    target_price = self._ib_mid

                    # R:R sanity check — skip if risk > 2.5x reward
                    risk = abs(entry_price - stop_price)
                    reward = abs(target_price - entry_price)
                    if reward > 0 and risk / reward > 2.5:
                        self._touch_bar_index = None
                        return None

                    confidence = 'high' if self._vwap_aligned else 'medium'

                    self._val_fade_taken = True

                    return Signal(
                        timestamp=bar.get('timestamp', bar.name) if hasattr(bar, 'name') else bar.get('timestamp'),
                        direction='LONG',
                        entry_price=entry_price,
                        stop_price=stop_price,
                        target_price=target_price,
                        strategy_name=self.name,
                        setup_type='B_DAY_IBL_FADE',
                        day_type=session_context.get('day_type', ''),
                        confidence=confidence,
                    )
                else:
                    # Failed acceptance — reset (first touch consumed, no more trades)
                    self._touch_bar_index = None
                    return None

        return None
