"""
Strategy: NWOG Gap Fill — Monday weekly gap fill.

Research Source: NWOG Quantitative Study (54 weeks, NQ, 270 sessions)

Best config from study (highest PnL):
  B_OR_CLOSE|g10|fixed_75|full_fill|tEOD|DOWN_ONLY
  17 trades, 82.4% WR, PF 12.20, $50,755

Key findings:
  - DOWN gaps are the edge: 78.3% Monday fill rate vs 35.5% for UP gaps
  - VWAP confirmation strongest predictor but filters too aggressively
  - Entry at OR close (9:45) captures early momentum
  - Full gap fill target lets winners run

Entry: At 9:45 AM (OR close, end of Opening Range)
Direction: DOWN gaps only → LONG (gap fill = mean reversion up to Friday close)
Stop: 75 pts fixed
Target: Friday close (full gap fill)
Time stop: EOD (let position run)
Qualifier: gap >= 10 pts, Monday only, DOWN gap only
"""

from datetime import datetime, time as _time
from typing import List, Optional, TYPE_CHECKING

import pandas as pd

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal

if TYPE_CHECKING:
    pass

# NWOG parameters — study best: B_OR_CLOSE|g10|fixed_75|full_fill|tEOD|DOWN_ONLY
MIN_GAP_POINTS = 10.0           # gap >= 10 pts (study: g10)
STOP_POINTS = 75.0              # fixed_75 stop
OR_CLOSE_TIME = _time(9, 45)    # Entry at OR close (9:45 AM)
ENTRY_WINDOW_END = _time(9, 50) # Must enter within 5 min of OR close


class NWOGGapFill(StrategyBase):
    """NWOG Gap Fill — Monday DOWN gap fill at OR close.

    Enters LONG on first bar after 9:45 when a DOWN gap >= 10pts is detected
    on Monday. Target is Friday close (full gap fill). Fixed 75pt stop.
    """

    @property
    def name(self) -> str:
        return "NWOG Gap Fill"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types — Monday only, day type agnostic

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._active = False
        self._signal_emitted = False
        self._gap_size = 0.0
        self._friday_close = None
        self._monday_open = None

        # Check if Monday
        try:
            date_str = str(session_date).split(" ")[0].split("T")[0]
            day_of_week = datetime.strptime(date_str, "%Y-%m-%d").weekday()
        except (ValueError, TypeError):
            return

        if day_of_week != 0:  # 0 = Monday
            return

        # Get prior Friday close
        prior_close = session_context.get("prior_close")
        if prior_close is None:
            return

        # Get Monday open from first IB bar
        ib_bars = session_context.get("ib_bars")
        if ib_bars is None or len(ib_bars) == 0:
            return

        monday_open = float(ib_bars.iloc[0]["open"])

        # Compute gap
        gap = monday_open - prior_close
        gap_size = abs(gap)

        if gap_size < MIN_GAP_POINTS:
            return

        # DOWN gaps only (study: DOWN_ONLY has 82.4% WR, PF 12.20)
        if gap >= 0:
            return  # Skip UP gaps

        self._friday_close = prior_close
        self._monday_open = monday_open
        self._gap_size = gap_size
        self._active = True

    def on_pre_ib_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        """Enter at OR close (9:45 AM) during IB formation."""
        if not self._active or self._signal_emitted:
            return None

        bar_time = session_context.get("bar_time")
        if bar_time is None:
            return None

        # Wait for OR close (9:45)
        if bar_time < OR_CLOSE_TIME:
            return None

        # Must enter within window
        if bar_time >= ENTRY_WINDOW_END:
            self._active = False
            return None

        entry_price = bar["close"]

        # LONG to fill DOWN gap (gap fill = price moving back up to Friday close)
        direction = "LONG"
        stop_price = entry_price - STOP_POINTS
        target_price = self._friday_close  # Full gap fill

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
            setup_type="NWOG_GAP_FILL",
            day_type=session_context.get("day_type", ""),
            confidence="high",
            metadata={
                "gap_size": self._gap_size,
                "gap_direction": "DOWN",
                "friday_close": self._friday_close,
                "monday_open": self._monday_open,
                "stop_model": "fixed_75pts",
                "target_model": "full_fill",
                "entry_timing": "or_close",
            },
        )

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        """Post-IB: no additional entries needed (entered during IB at OR close)."""
        return None

    def on_session_end(self, session_date) -> None:
        self._active = False
