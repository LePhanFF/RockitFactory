"""
Strategy: NDOG Gap Fill — daily overnight gap fill with VWAP confirmation.

Research Source: NDOG Quantitative Study (NQ, 270 sessions)

Key Finding: When the overnight gap (RTH open vs prior day RTH close) is >= 20pts
and VWAP confirms fill direction at RTH open, the gap fill rate is very high.

Study Results:
  - 42 trades, 88.1% WR, PF 12.08, $83,853 total PnL
  - Config: rth_open entry, gap >= 20pt, fixed_75 stop, full_fill target, 13:00 time stop

Entry: At RTH open (first bar of session)
Direction: SHORT if UP gap, LONG if DOWN gap (gap fill = mean reversion toward prior close)
Stop: 75 pts fixed
Target: Prior day RTH close (full gap fill)
Time stop: 13:00 (exit if still open)
Qualifier: gap >= 20 pts, any day of week
VWAP confirmation: at RTH open, price must be on fill side of VWAP
Bias alignment: skip SHORT on bullish days, skip LONG on bearish days

Key Differences from NWOG:
  - NDOG = DAILY gap (every day, not just Monday)
  - NWOG = WEEKLY gap (Monday only, Friday close reference)
  - NDOG gap = RTH open vs prior day RTH close (not weekend gap)
  - No acceptance filter needed (NWOG uses 30% acceptance)
  - VWAP confirmation at RTH open (not IB close)
"""

from datetime import time as _time
from typing import List, Optional, TYPE_CHECKING

import pandas as pd

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal

if TYPE_CHECKING:
    pass

# NDOG parameters
MIN_GAP_POINTS = 20.0
STOP_POINTS = 75.0
TIME_STOP = _time(13, 0)


class NDOGGapFill(StrategyBase):
    """NDOG Gap Fill — daily overnight gap fill with VWAP confirmation.

    Trades the overnight gap fill on any day of the week.
    Entry at RTH open with VWAP confirmation.
    Stop: 75 pts fixed, Target: prior day RTH close (full gap fill).
    """

    @property
    def name(self) -> str:
        return "NDOG Gap Fill"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._active = False
        self._signal_emitted = False
        self._gap_size = 0.0
        self._gap_direction = None  # "UP" or "DOWN"
        self._prior_close = None
        self._session_open = None

        # Get prior day RTH close
        prior_close = session_context.get("prior_close")
        if prior_close is None:
            return

        # Get RTH open from first IB bar
        ib_bars = session_context.get("ib_bars")
        if ib_bars is None or len(ib_bars) == 0:
            return

        session_open = float(ib_bars.iloc[0]["open"])

        # Compute gap: RTH open vs prior day RTH close
        gap = session_open - prior_close
        gap_size = abs(gap)

        if gap_size < MIN_GAP_POINTS:
            return

        self._prior_close = prior_close
        self._session_open = session_open
        self._gap_size = gap_size
        self._gap_direction = "UP" if gap > 0 else "DOWN"

        # Bias alignment: skip counter-bias trades
        bias = (
            session_context.get('session_bias')
            or session_context.get('regime_bias', 'NEUTRAL')
        )
        if self._gap_direction == "UP":
            # UP gap -> SHORT trade -> skip if bullish bias
            if bias and bias.upper() in ('BULL', 'BULLISH'):
                return
        else:
            # DOWN gap -> LONG trade -> skip if bearish bias
            if bias and bias.upper() in ('BEAR', 'BEARISH'):
                return

        # VWAP confirmation at RTH open: price must be on fill side of VWAP
        first_bar = ib_bars.iloc[0]
        vwap = first_bar.get("vwap") if "vwap" in first_bar.index else None
        open_price = first_bar["close"]  # Use close of first bar for VWAP comparison

        vwap_confirms = False
        if vwap is not None and not pd.isna(vwap):
            if self._gap_direction == "UP":
                # UP gap fills DOWN — price should be below VWAP (bearish)
                vwap_confirms = open_price < vwap
            else:
                # DOWN gap fills UP — price should be above VWAP (bullish)
                vwap_confirms = open_price > vwap

        if vwap_confirms:
            self._active = True
            self._vwap_at_entry = vwap
        else:
            self._active = False

    def on_pre_ib_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        """Enter gap fill on the FIRST bar of RTH (during IB formation)."""
        if not self._active or self._signal_emitted:
            return None

        # Only enter on the very first bar (bar_index == 0 = 9:30)
        if bar_index != 0:
            return None

        entry_price = bar["close"]

        # Direction: fill the gap (mean reversion toward prior close)
        if self._gap_direction == "UP":
            direction = "SHORT"  # Gap up -> expect fill down
            stop_price = entry_price + STOP_POINTS
            target_price = self._prior_close  # Full gap fill
        else:
            direction = "LONG"  # Gap down -> expect fill up
            stop_price = entry_price - STOP_POINTS
            target_price = self._prior_close  # Full gap fill

        # R:R sanity check
        risk = abs(entry_price - stop_price)
        reward = abs(target_price - entry_price)
        if reward <= 0 or risk / reward > 5.0:
            self._active = False
            return None

        self._signal_emitted = True

        return Signal(
            timestamp=bar.get("timestamp", bar.name) if hasattr(bar, "name") else bar.get("timestamp"),
            direction=direction,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            strategy_name=self.name,
            setup_type="NDOG_GAP_FILL",
            day_type=session_context.get("day_type", ""),
            confidence="high",
            metadata={
                "gap_size": self._gap_size,
                "gap_direction": self._gap_direction,
                "prior_close": self._prior_close,
                "session_open": self._session_open,
                "vwap_at_entry": self._vwap_at_entry,
                "stop_model": "fixed_75pts",
            },
        )

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        """Post-IB monitoring only — entry happens in on_pre_ib_bar()."""
        return None

    def on_session_end(self, session_date) -> None:
        self._active = False
