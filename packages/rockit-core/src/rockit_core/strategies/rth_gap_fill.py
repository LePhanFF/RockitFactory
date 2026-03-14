"""
Strategy: RTH Gap Fill — gap fill on large RTH open gaps with VWAP confirmation.

Research Source: RTH Gap Fill Quantitative Study (272 sessions, NQ)

Study results:
  High-conviction: gap_50, up_only, rth_open, vwap_confirm, fixed_50, half_fill
    10 trades, 100% WR, PF inf, $12,512 — very selective but perfect edge

  High-volume: gap_50, both, rth_open, no_vwap, gap_2x, 1R, no_ts
    183 trades, 57.4% WR, PF 1.66, $155,045

Production config (high-conviction):
  Entry: RTH open (first qualifying bar)
  Direction: UP gaps only (SHORT to fill down)
  Gap minimum: 50 pts
  VWAP: Required (price < VWAP confirms fill direction)
  Stop: 50 pts fixed
  Target: half_fill (midpoint between open and prior close)
  Time stop: 11:00
"""

from datetime import time as _time
from typing import List, Optional, TYPE_CHECKING

import pandas as pd

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal

if TYPE_CHECKING:
    from rockit_core.models.base import StopModel, TargetModel

# RTH Gap Fill parameters — study high-conviction config
MIN_GAP_POINTS = 50.0
STOP_POINTS = 50.0
TIME_STOP = _time(11, 0)


class RTHGapFill(StrategyBase):
    """RTH Gap Fill — UP-gap fill with VWAP confirmation.

    Enters SHORT when an UP gap >= 50pts is confirmed by VWAP (price below VWAP).
    Target is half_fill (midpoint between open and prior close).
    """

    @property
    def name(self) -> str:
        return "RTH Gap Fill"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types — gap fill is day type agnostic

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._active = False
        self._signal_emitted = False
        self._gap_size = 0.0
        self._prior_close = None
        self._session_open = None
        self._fill_target = None

        # Get prior close
        prior_close = session_context.get("prior_close")
        if prior_close is None:
            return

        # Get session open from first IB bar
        ib_bars = session_context.get("ib_bars")
        if ib_bars is None or len(ib_bars) == 0:
            return

        session_open = float(ib_bars.iloc[0]["open"])

        # Compute gap
        gap = session_open - prior_close
        gap_size = abs(gap)

        if gap_size < MIN_GAP_POINTS:
            return

        # UP gaps only (study: up_only has highest avg PF)
        if gap <= 0:
            return

        self._prior_close = prior_close
        self._session_open = session_open
        self._gap_size = gap_size
        # Half fill = midpoint between session open and prior close
        self._fill_target = (session_open + prior_close) / 2.0
        self._active = True

    def on_pre_ib_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        """Enter gap fill during IB formation — VWAP confirmation on first qualifying bar."""
        if not self._active or self._signal_emitted:
            return None

        bar_time = session_context.get("bar_time")

        # Time stop: no signals after 11:00
        if bar_time and bar_time >= TIME_STOP:
            self._active = False
            return None

        # VWAP confirmation on first qualifying bar
        vwap = bar.get("vwap") if "vwap" in bar.index else None
        if vwap is None or pd.isna(vwap):
            return None

        entry_price = bar["close"]

        # UP gap fills DOWN → SHORT
        # VWAP confirm: price must be BELOW VWAP (already starting to fill)
        if entry_price >= vwap:
            return None  # VWAP doesn't confirm — skip this bar

        stop_price = entry_price + STOP_POINTS
        target_price = self._fill_target

        # R:R sanity check
        risk = abs(entry_price - stop_price)
        reward = abs(target_price - entry_price)
        if reward <= 0 or risk / reward > 5.0:
            self._active = False
            return None

        self._signal_emitted = True

        return Signal(
            timestamp=bar.get("timestamp", bar.name) if hasattr(bar, "name") else bar.get("timestamp"),
            direction="SHORT",
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            strategy_name=self.name,
            setup_type="RTH_GAP_FILL",
            day_type=session_context.get("day_type", ""),
            confidence="high",
            metadata={
                "gap_size": self._gap_size,
                "gap_direction": "UP",
                "vwap_at_entry": float(vwap),
                "fill_target": self._fill_target,
                "prior_close": self._prior_close,
                "session_open": self._session_open,
                "stop_model": "fixed_50pts",
                "target_model": "half_fill",
            },
        )

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        """Post-IB monitoring only — entry happens in on_pre_ib_bar()."""
        return None

    def on_session_end(self, session_date) -> None:
        self._active = False
