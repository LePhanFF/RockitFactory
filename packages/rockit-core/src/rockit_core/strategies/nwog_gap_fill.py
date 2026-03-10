"""
Strategy: NWOG Gap Fill — Monday weekly gap fill with VWAP + acceptance filters.

Research Source: NWOG Quantitative Study (54 weeks, NQ, 270 sessions)

Key Finding: When VWAP confirms the fill direction at 10:00 and >=30%
of the first 30 min bars close on the fill side, Monday RTH fill rate
reaches 100% (13/13 observations).

Entry: At 10:00 AM (post-acceptance-check at end of IB)
Direction: SHORT if UP gap, LONG if DOWN gap (gap fill = mean reversion)
Stop: 75 pts fixed
Target: Friday close (full gap fill)
Time stop: 13:00 (exit if still open)
Qualifier: gap >= 20 pts, Monday only
"""

from datetime import datetime, time as _time
from typing import List, Optional, TYPE_CHECKING

import pandas as pd

from rockit_core.models.stop_models import FixedPointsStop
from rockit_core.models.target_models import RMultipleTarget
from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal

if TYPE_CHECKING:
    from rockit_core.models.base import StopModel, TargetModel

# NWOG parameters
MIN_GAP_POINTS = 20.0
ACCEPTANCE_THRESHOLD = 0.30  # 30% of first 30 min bars
STOP_POINTS = 75.0
TIME_STOP = _time(13, 0)
LAST_ENTRY_TIME = _time(10, 35)  # Must enter within 5 min of IB close


class NWOGGapFill(StrategyBase):
    """NWOG Gap Fill — Monday weekly gap fill with VWAP + acceptance filters.

    Defaults to FixedPointsStop(75.0) and 2R target (overridden by gap fill level).
    """

    def __init__(
        self,
        stop_model: Optional['StopModel'] = None,
        target_model: Optional['TargetModel'] = None,
    ):
        self._stop_model = stop_model or FixedPointsStop(STOP_POINTS)
        self._target_model = target_model  # Not used — target is gap fill level

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
        self._gap_direction = None  # "UP" or "DOWN"
        self._friday_close = None
        self._monday_open = None
        self._ce_level = None

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

        self._friday_close = prior_close
        self._monday_open = monday_open
        self._gap_size = gap_size
        self._gap_direction = "UP" if gap > 0 else "DOWN"
        self._ce_level = (monday_open + prior_close) / 2.0

        # Count acceptance in IB bars (first 30 min = first 30 bars of IB)
        first_30_bars = ib_bars.head(30)
        fill_side_count = 0
        for _, bar in first_30_bars.iterrows():
            close = bar["close"]
            if self._gap_direction == "UP":
                # UP gap fills DOWN — bars closing below CE are on fill side
                if close < self._ce_level:
                    fill_side_count += 1
            else:
                # DOWN gap fills UP — bars closing above CE are on fill side
                if close > self._ce_level:
                    fill_side_count += 1

        acceptance_pct = fill_side_count / len(first_30_bars) if len(first_30_bars) > 0 else 0

        # Check VWAP at IB close
        last_ib_bar = ib_bars.iloc[-1]
        vwap = last_ib_bar.get("vwap") if "vwap" in last_ib_bar.index else None
        last_price = last_ib_bar["close"]

        vwap_confirms = False
        if vwap is not None and not pd.isna(vwap):
            if self._gap_direction == "UP":
                # UP gap fills DOWN — price should be below VWAP
                vwap_confirms = last_price < vwap
            else:
                # DOWN gap fills UP — price should be above VWAP
                vwap_confirms = last_price > vwap

        # Both filters must pass
        if acceptance_pct >= ACCEPTANCE_THRESHOLD and vwap_confirms:
            self._active = True
            self._acceptance_pct = acceptance_pct
            self._vwap_at_entry = vwap
        else:
            self._active = False

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        if not self._active or self._signal_emitted:
            return None

        bar_time = session_context.get("bar_time")

        # Time stop check (for backtest engine — strategy can't close positions,
        # but we stop emitting new signals after TIME_STOP)
        if bar_time and bar_time >= LAST_ENTRY_TIME:
            self._active = False
            return None

        # Emit signal on first post-IB bar (10:30, right at IB close)
        entry_price = bar["close"]

        # Direction: fill the gap
        if self._gap_direction == "UP":
            direction = "SHORT"  # Gap up → expect fill down
            stop_price = entry_price + STOP_POINTS
            target_price = self._friday_close  # Gap fill level
        else:
            direction = "LONG"  # Gap down → expect fill up
            stop_price = entry_price - STOP_POINTS
            target_price = self._friday_close  # Gap fill level

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
                "gap_direction": self._gap_direction,
                "ce_level": self._ce_level,
                "acceptance_pct": round(self._acceptance_pct, 3),
                "vwap_at_entry": self._vwap_at_entry,
                "friday_close": self._friday_close,
                "monday_open": self._monday_open,
                "stop_model": "fixed_75pts",
            },
        )

    def on_session_end(self, session_date) -> None:
        self._active = False
