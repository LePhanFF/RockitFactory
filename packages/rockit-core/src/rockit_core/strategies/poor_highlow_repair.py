"""
Strategy: Poor High/Low Repair
==============================

When a session ends with a "poor high" or "poor low" (no excess/tail -- price
just stopped without rejection), it signals unfinished business. The next
session often "repairs" this by revisiting and pushing through that level.

Detection (Method A):
  - Poor HIGH: The bar at the session high has its close in the top 25% of
    that bar's range (no upper wick rejection).
  - Poor LOW: The bar at the session low has its close in the bottom 25% of
    that bar's range (no lower wick rejection).

Study Results (optimal config):
  - Config: Method A, within_10 touch tolerance, accept_3, stop_10pt, target_1R, morning
  - 54 trades, 66.7% WR, PF 2.01, $8,964
  - Poor LOW repair (LONG) is stronger than Poor HIGH repair (SHORT)

Logic:
  1. on_session_start: Get prior day high/low. Detect if they were "poor"
     (Method A). Store poor levels if within 10pts of session open.
  2. on_bar (morning only, before 11:00):
     - Monitor price approaching poor level (touch tolerance)
     - Require 3-bar acceptance (3 consecutive closes on repair side)
     - Poor HIGH -> SHORT (repair = rejection), Poor LOW -> LONG (repair = bounce)
     - Stop: 10 points fixed, Target: 1R
     - One signal per poor level max
"""

from datetime import time as _time
from typing import Optional, List

import pandas as pd

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal


# ── Constants ──────────────────────────────────────────────
POOR_CLOSE_PCT = 0.25          # Close within top/bottom 25% of bar range
TOUCH_TOLERANCE_PTS = 10.0     # Price must come within 10pts of poor level
ACCEPTANCE_BARS = 3            # 3 consecutive bars closing on repair side
STOP_PTS = 10.0                # 10-point fixed stop
TARGET_MULT = 1.0              # 1R target (same distance as stop)
MORNING_CUTOFF = _time(11, 0)  # No entries after 11:00 AM ET
PROXIMITY_PTS = 500.0          # Poor level can be up to 500pts from session open (NQ range)
MIN_BAR_RANGE = 0.5            # Minimum bar range to evaluate poor quality


class PoorHighLowRepair(StrategyBase):
    """
    Poor High/Low Repair: trade the "unfinished business" from prior session.

    When the prior session ended with a poor high or poor low (no rejection
    tail), the next session typically revisits and repairs that level.
    """

    def __init__(self):
        # Cross-session state: computed at end of each session, used in next
        self._prior_poor_high: Optional[float] = None
        self._prior_poor_low: Optional[float] = None
        self._prior_session_high: Optional[float] = None
        self._prior_session_low: Optional[float] = None
        # Bar tracking for computing poor quality at session end
        self._high_bar_close: Optional[float] = None
        self._high_bar_range: float = 0.0
        self._high_bar_high: float = 0.0
        self._low_bar_close: Optional[float] = None
        self._low_bar_range: float = 0.0
        self._low_bar_low: float = float('inf')
        self._session_high: float = 0.0
        self._session_low: float = float('inf')

    @property
    def name(self) -> str:
        return "Poor HL Repair"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        # Get session open from IB bars
        self._session_open = 0.0
        ib_bars = session_context.get('ib_bars')
        if ib_bars is not None and len(ib_bars) > 0:
            first_bar = ib_bars.iloc[0]
            self._session_open = float(first_bar.get('open', first_bar['close']))
            if pd.isna(self._session_open):
                self._session_open = float(first_bar['close'])

        # Determine active poor levels from prior session
        # First try enrichment data (enhanced detection from indicators/poor_extremes.py)
        # Then fall back to self-tracked values (computed in on_session_end)
        self._active_poor_high: Optional[float] = None
        self._active_poor_low: Optional[float] = None

        # Check enrichment data from session_context (injected by engine)
        prior_day = session_context.get('prior_day', {})
        tpo_data = session_context.get('tpo_data', {})
        enrichment = prior_day if isinstance(prior_day, dict) else {}
        if not enrichment:
            enrichment = tpo_data if isinstance(tpo_data, dict) else {}

        enrich_poor_high = enrichment.get('prior_poor_high_level')
        enrich_poor_low = enrichment.get('prior_poor_low_level')

        # Use enrichment data if available, otherwise fall back to self-tracked
        poor_high_level = enrich_poor_high if enrich_poor_high is not None else self._prior_poor_high
        poor_low_level = enrich_poor_low if enrich_poor_low is not None else self._prior_poor_low

        if poor_high_level is not None and self._session_open > 0:
            if abs(poor_high_level - self._session_open) <= PROXIMITY_PTS:
                self._active_poor_high = poor_high_level

        if poor_low_level is not None and self._session_open > 0:
            if abs(poor_low_level - self._session_open) <= PROXIMITY_PTS:
                self._active_poor_low = poor_low_level

        # Per-session state
        self._signal_fired_high = False
        self._signal_fired_low = False
        self._accept_count_high = 0  # Consecutive bars closing below poor high
        self._accept_count_low = 0   # Consecutive bars closing above poor low
        self._touched_high = False
        self._touched_low = False

        # Reset bar tracking for this session's poor detection
        self._session_high = 0.0
        self._session_low = float('inf')
        self._high_bar_close = None
        self._high_bar_range = 0.0
        self._high_bar_high = 0.0
        self._low_bar_close = None
        self._low_bar_range = 0.0
        self._low_bar_low = float('inf')

        # Also process IB bars for session extreme tracking
        if ib_bars is not None:
            for i in range(len(ib_bars)):
                bar = ib_bars.iloc[i]
                self._track_bar_extremes(bar)

    def _track_bar_extremes(self, bar):
        """Track bar-level data for session high/low quality detection."""
        high = float(bar['high'])
        low = float(bar['low'])
        close = float(bar['close'])
        bar_range = high - low

        if high > self._session_high:
            self._session_high = high
            self._high_bar_close = close
            self._high_bar_range = bar_range
            self._high_bar_high = high
        elif high == self._session_high:
            # If tie, update if this bar's close is higher (more "poor")
            if self._high_bar_close is None or close > self._high_bar_close:
                self._high_bar_close = close
                self._high_bar_range = bar_range
                self._high_bar_high = high

        if low < self._session_low:
            self._session_low = low
            self._low_bar_close = close
            self._low_bar_range = bar_range
            self._low_bar_low = low
        elif low == self._session_low:
            # If tie, update if this bar's close is lower (more "poor")
            if self._low_bar_close is None or close < self._low_bar_close:
                self._low_bar_close = close
                self._low_bar_range = bar_range
                self._low_bar_low = low

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        # Track extremes for next session's poor detection
        self._track_bar_extremes(bar)

        # Time gate: morning only
        bar_time = session_context.get('bar_time')
        if bar_time and bar_time >= MORNING_CUTOFF:
            return None

        close = float(bar['close'])
        high = float(bar['high'])
        low = float(bar['low'])

        # === Check Poor HIGH repair (SHORT) — DISABLED ===
        # Study results: SHORT side unprofitable (drags portfolio negative).
        # Poor LOW repair (LONG) is the only profitable direction.
        # if (self._active_poor_high is not None
        #         and not self._signal_fired_high):
        #     signal = self._check_poor_high_repair(bar, close, high, low, session_context)
        #     if signal:
        #         return signal

        # === Check Poor LOW repair (LONG) ===
        if (self._active_poor_low is not None
                and not self._signal_fired_low):
            signal = self._check_poor_low_repair(bar, close, high, low, session_context)
            if signal:
                return signal

        return None

    def _check_poor_high_repair(self, bar, close, high, low, session_context) -> Optional[Signal]:
        """Check for SHORT signal at poor high level."""
        level = self._active_poor_high

        # Step 1: Price must touch/approach the poor high level
        if high >= level - TOUCH_TOLERANCE_PTS:
            self._touched_high = True

        if not self._touched_high:
            return None

        # Step 2: Acceptance -- 3 consecutive bars closing below the poor high
        if close < level:
            self._accept_count_high += 1
        else:
            self._accept_count_high = 0

        if self._accept_count_high < ACCEPTANCE_BARS:
            return None

        # Step 3: Emit SHORT signal (repair = rejection of poor high)
        entry = close
        stop = entry + STOP_PTS
        target = entry - (STOP_PTS * TARGET_MULT)

        self._signal_fired_high = True
        return Signal(
            timestamp=bar.get('timestamp', bar.name) if hasattr(bar, 'name') else bar.get('timestamp'),
            direction='SHORT',
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            strategy_name=self.name,
            setup_type='POOR_HIGH_REPAIR',
            day_type=session_context.get('day_type', ''),
            trend_strength=session_context.get('trend_strength', ''),
            confidence='medium',
            metadata={
                'poor_type': 'HIGH',
                'poor_level': round(level, 2),
                'detection_method': 'method_a',
                'acceptance_bars': self._accept_count_high,
                'session_open': round(self._session_open, 2),
            },
        )

    def _check_poor_low_repair(self, bar, close, high, low, session_context) -> Optional[Signal]:
        """Check for LONG signal at poor low level."""
        level = self._active_poor_low

        # Step 1: Price must touch/approach the poor low level
        if low <= level + TOUCH_TOLERANCE_PTS:
            self._touched_low = True

        if not self._touched_low:
            return None

        # Step 2: Acceptance -- 3 consecutive bars closing above the poor low
        if close > level:
            self._accept_count_low += 1
        else:
            self._accept_count_low = 0

        if self._accept_count_low < ACCEPTANCE_BARS:
            return None

        # Step 3: Emit LONG signal (repair = bounce off poor low)
        entry = close
        stop = entry - STOP_PTS
        target = entry + (STOP_PTS * TARGET_MULT)

        self._signal_fired_low = True
        return Signal(
            timestamp=bar.get('timestamp', bar.name) if hasattr(bar, 'name') else bar.get('timestamp'),
            direction='LONG',
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            strategy_name=self.name,
            setup_type='POOR_LOW_REPAIR',
            day_type=session_context.get('day_type', ''),
            trend_strength=session_context.get('trend_strength', ''),
            confidence='medium',
            metadata={
                'poor_type': 'LOW',
                'poor_level': round(level, 2),
                'detection_method': 'method_a',
                'acceptance_bars': self._accept_count_low,
                'session_open': round(self._session_open, 2),
            },
        )

    def on_session_end(self, session_date) -> None:
        """Compute poor high/low for this session and cache for next."""
        self._prior_poor_high = None
        self._prior_poor_low = None
        self._prior_session_high = self._session_high
        self._prior_session_low = self._session_low

        # Check if session high bar was "poor" (Method A)
        # Poor HIGH = close in top 25% of bar range (no rejection wick above)
        if (self._high_bar_close is not None
                and self._high_bar_range >= MIN_BAR_RANGE):
            bar_low = self._high_bar_high - self._high_bar_range
            close_position = (self._high_bar_close - bar_low) / self._high_bar_range
            if close_position >= (1.0 - POOR_CLOSE_PCT):
                self._prior_poor_high = self._session_high

        # Check if session low bar was "poor" (Method A)
        # Poor LOW = close in bottom 25% of bar range (no rejection wick below)
        if (self._low_bar_close is not None
                and self._low_bar_range >= MIN_BAR_RANGE):
            bar_low = self._low_bar_low
            close_position = (self._low_bar_close - bar_low) / self._low_bar_range
            if close_position <= POOR_CLOSE_PCT:
                self._prior_poor_low = self._session_low
