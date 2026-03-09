"""
Strategy: 80% Rule (Return to Balance)
=======================================

Dalton's 80% Rule: When price opens outside the prior day's Value Area and
then re-enters the VA, there is an 80% chance price will rotate through to
the opposite side of the Value Area. This strategy trades that return-to-balance.

Research Branch Reference (v3):
  - VA Source: ETH 1-day (overnight+RTH). NOTE: our engine provides RTH-only VA,
    which produces narrower VA levels. This will reduce trade count and change WR.
  - Acceptance: 1 × 30-min close inside VA (we aggregate 30 1-min bars)
  - Stop: VA boundary + 10pt fixed buffer
  - Min VA width: 25pt
  - Entry cutoff: 13:00 ET, Exit cutoff: 15:30 ET

Research Results (ETH VA):
  - Acceptance + 4R:   60 trades, 38.3% WR, PF 1.70, $955/mo
  - 100% Retest + 2R:  35 trades, 65.7% WR, PF 3.45, $915/mo
  - Limit 50% VA + 4R: 47 trades, 44.7% WR, PF 2.57, $1,922/mo

Critical rule: Retest entries MUST use VA-edge stops (58-66% WR).
  Candle-extreme stops = 5-14% WR (catastrophic).

FILTERS:
  - VA width >= 25 pts minimum
  - No entry after 13:00 ET
"""

from datetime import time as _time
from typing import Optional, List, TYPE_CHECKING
import pandas as pd
import numpy as np

from rockit_core.models.signals import Direction, EntrySignal
from rockit_core.models.stop_models import VAEdgeStop
from rockit_core.models.target_models import RMultipleTarget
from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal

if TYPE_CHECKING:
    from rockit_core.models.base import StopModel, TargetModel


# ── 80P Rule Constants (matched to research source) ──────────
ACCEPT_30M_BARS = 30               # 30 × 1-min bars = 1 × 30-min candle
STOP_BUFFER_PTS = 10.0             # Fixed 10pt beyond VA edge
ENTRY_CUTOFF = _time(13, 0)        # No new entries after 1 PM ET
MIN_VA_WIDTH = 25.0                # Research: 25pt minimum
TARGET_MODE = '2R'                 # '2R', '4R', 'opposite_va', 'POC'
ENTRY_MODEL = 'acceptance'         # 'acceptance' or 'retest_100pct'
MAX_ENTRIES_PER_SESSION = 1


class EightyPercentRule(StrategyBase):
    """
    80% Rule: Open outside prior VA, re-enter → trade return-to-balance.

    Research-aligned implementation:
    - 1 × 30-min acceptance (aggregate 30 bars, check close)
    - VA edge + 10pt fixed stop
    - Target: 2R default
    """

    def __init__(self, target_mode: str = TARGET_MODE,
                 entry_model: str = ENTRY_MODEL,
                 stop_model: Optional['StopModel'] = None,
                 target_model: Optional['TargetModel'] = None):
        self._target_mode = target_mode
        self._entry_model = entry_model
        self._stop_model = stop_model or VAEdgeStop(STOP_BUFFER_PTS)
        self._target_model = target_model or RMultipleTarget(2.0)

    @property
    def name(self) -> str:
        return "80P Rule"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._ib_high = ib_high
        self._ib_low = ib_low
        self._ib_range = ib_range

        # Prior VA levels
        self._prior_vah = session_context.get('prior_va_vah', None)
        self._prior_val = session_context.get('prior_va_val', None)
        self._prior_poc = session_context.get('prior_va_poc', None)

        # Fall back to prior_va_high/low if vah/val not available
        if self._prior_vah is None or (isinstance(self._prior_vah, float) and pd.isna(self._prior_vah)):
            self._prior_vah = session_context.get('prior_va_high', None)
        if self._prior_val is None or (isinstance(self._prior_val, float) and pd.isna(self._prior_val)):
            self._prior_val = session_context.get('prior_va_low', None)

        self._va_range = 0
        if (self._prior_vah is not None and self._prior_val is not None
                and not pd.isna(self._prior_vah) and not pd.isna(self._prior_val)):
            self._va_range = self._prior_vah - self._prior_val

        # Get session open from first IB bar
        self._session_open = 0
        ib_bars = session_context.get('ib_bars')
        if ib_bars is not None and len(ib_bars) > 0:
            first_bar = ib_bars.iloc[0]
            self._session_open = first_bar.get('open', first_bar['close'])
            if pd.isna(self._session_open):
                self._session_open = first_bar['close']

        # Determine if session opened outside prior VA
        self._open_above_va = False
        self._open_below_va = False
        self._active = False

        if (self._prior_vah is not None and self._prior_val is not None
                and not pd.isna(self._prior_vah) and not pd.isna(self._prior_val)
                and self._session_open > 0):
            if self._va_range >= MIN_VA_WIDTH:
                if self._session_open > self._prior_vah:
                    self._open_above_va = True
                    self._active = True
                elif self._session_open < self._prior_val:
                    self._open_below_va = True
                    self._active = True

        # State tracking
        self._signal_fired = False

        # 30-min candle aggregation for acceptance
        self._30m_bar_count = 0
        self._30m_open = None
        self._30m_high = None
        self._30m_low = None
        self._30m_close = None

        # Acceptance state
        self._accepted = False
        self._accept_candle_high = 0
        self._accept_candle_low = 0
        self._accept_candle_close = 0

        # 100% retest state
        self._waiting_for_retest = False

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        if not self._active or self._signal_fired:
            return None

        close = bar['close']
        high = bar['high']
        low = bar['low']

        # Time gate
        bar_time = session_context.get('bar_time')
        if bar_time and bar_time >= ENTRY_CUTOFF:
            return None

        # === 30-min candle aggregation ===
        self._30m_bar_count += 1
        bar_open = bar.get('open', close)
        if pd.isna(bar_open):
            bar_open = close

        if self._30m_open is None:
            self._30m_open = bar_open
            self._30m_high = high
            self._30m_low = low
        else:
            self._30m_high = max(self._30m_high, high)
            self._30m_low = min(self._30m_low, low)
        self._30m_close = close

        # On 30-min candle completion, check acceptance
        if self._30m_bar_count >= ACCEPT_30M_BARS:
            if not self._accepted:
                accept_dir = self._check_30m_acceptance()
                if accept_dir and self._entry_model == 'acceptance':
                    # Enter immediately at acceptance candle close
                    entry = self._accept_candle_close
                    model_dir = Direction.LONG if accept_dir == 'LONG' else Direction.SHORT
                    entry_signal = EntrySignal(
                        model_name=self.name,
                        direction=model_dir,
                        price=entry,
                        confidence=0.8,
                        setup_type='80P_RETURN_TO_BALANCE',
                    )
                    ctx = dict(session_context)
                    ctx.setdefault('prior_va_vah', self._prior_vah)
                    ctx.setdefault('prior_va_val', self._prior_val)

                    stop_level = self._stop_model.compute(entry_signal, bar, ctx)
                    stop = stop_level.price

                    target = self._compute_target(accept_dir, entry, stop)

                    if accept_dir == 'SHORT':
                        risk = stop - entry
                        reward = entry - target
                    else:
                        risk = entry - stop
                        reward = target - entry

                    if risk > 0 and reward > 0:
                        self._signal_fired = True
                        # Reset candle state before returning
                        self._30m_bar_count = 0
                        self._30m_open = None
                        self._30m_high = None
                        self._30m_low = None
                        self._30m_close = None
                        return self._emit_signal(
                            bar, session_context, accept_dir,
                            entry, stop, target,
                            'ABOVE_VA' if accept_dir == 'SHORT' else 'BELOW_VA',
                        )

            # Reset 30-min aggregation
            self._30m_bar_count = 0
            self._30m_open = None
            self._30m_high = None
            self._30m_low = None
            self._30m_close = None

        # === If accepted with retest model, look for 100% retest entry ===
        if self._waiting_for_retest:
            signal = self._check_retest_entry(bar, bar_index, session_context, close, high, low)
            if signal:
                return signal

        return None

    def _check_30m_acceptance(self):
        """Check if the 30-min candle closes inside VA (acceptance)."""
        if self._30m_close is None:
            return None

        if self._open_above_va:
            # Need 30-min close below VAH (inside VA)
            if self._30m_close < self._prior_vah:
                self._accepted = True
                self._accept_candle_high = self._30m_high
                self._accept_candle_low = self._30m_low
                self._accept_candle_close = self._30m_close
                if self._entry_model == 'retest_100pct':
                    self._waiting_for_retest = True
                    return None
                return 'SHORT'

        elif self._open_below_va:
            # Need 30-min close above VAL (inside VA)
            if self._30m_close > self._prior_val:
                self._accepted = True
                self._accept_candle_high = self._30m_high
                self._accept_candle_low = self._30m_low
                self._accept_candle_close = self._30m_close
                if self._entry_model == 'retest_100pct':
                    self._waiting_for_retest = True
                    return None
                return 'LONG'

        return None

    def _check_retest_entry(self, bar, bar_index, session_context,
                            close, high, low) -> Optional[Signal]:
        """
        100% Retest (double top/bottom) entry after acceptance.

        Research: 35 trades, 65.7% WR, PF 3.45, $915/mo
        - LONG: acceptance candle pushed up into VA, price pulls back
          to candle LOW (double bottom). Enter on touch.
        - SHORT: acceptance candle pushed down into VA, price bounces
          back to candle HIGH (double top). Enter on touch.
        - Stop: VA edge + 10pt (NOT candle-based)
        """
        if self._open_above_va:
            # SHORT: price bounces back UP to acceptance candle HIGH
            if high >= self._accept_candle_high:
                entry = self._accept_candle_high
                entry_signal = EntrySignal(
                    model_name=self.name, direction=Direction.SHORT,
                    price=entry, confidence=0.8, setup_type='80P_RETURN_TO_BALANCE',
                )
                ctx = dict(session_context)
                ctx.setdefault('prior_va_vah', self._prior_vah)
                ctx.setdefault('prior_va_val', self._prior_val)
                stop_level = self._stop_model.compute(entry_signal, bar, ctx)
                stop = stop_level.price
                target = self._compute_target('SHORT', entry, stop)
                risk = stop - entry
                reward = entry - target
                if risk <= 0 or reward <= 0:
                    return None
                self._signal_fired = True
                return self._emit_signal(bar, session_context, 'SHORT',
                                         entry, stop, target, 'ABOVE_VA')

        elif self._open_below_va:
            # LONG: price pulls back DOWN to acceptance candle LOW
            if low <= self._accept_candle_low:
                entry = self._accept_candle_low
                entry_signal = EntrySignal(
                    model_name=self.name, direction=Direction.LONG,
                    price=entry, confidence=0.8, setup_type='80P_RETURN_TO_BALANCE',
                )
                ctx = dict(session_context)
                ctx.setdefault('prior_va_vah', self._prior_vah)
                ctx.setdefault('prior_va_val', self._prior_val)
                stop_level = self._stop_model.compute(entry_signal, bar, ctx)
                stop = stop_level.price
                target = self._compute_target('LONG', entry, stop)
                risk = entry - stop
                reward = target - entry
                if risk <= 0 or reward <= 0:
                    return None
                self._signal_fired = True
                return self._emit_signal(bar, session_context, 'LONG',
                                         entry, stop, target, 'BELOW_VA')

        return None

    def _emit_signal(self, bar, session_context, direction, entry, stop, target, open_side):
        return Signal(
            timestamp=bar.get('timestamp', bar.name) if hasattr(bar, 'name') else bar.get('timestamp'),
            direction=direction,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            strategy_name=self.name,
            setup_type='80P_RETURN_TO_BALANCE',
            day_type=session_context.get('day_type', ''),
            trend_strength=session_context.get('trend_strength', ''),
            confidence='high',
            metadata={
                'open_side': open_side,
                'entry_model': self._entry_model,
                'target_mode': self._target_mode,
                'session_open': self._session_open,
                'prior_vah': round(self._prior_vah, 2),
                'prior_val': round(self._prior_val, 2),
                'prior_poc': round(self._prior_poc, 2) if self._prior_poc and not pd.isna(self._prior_poc) else 0,
                'va_range': round(self._va_range, 2),
                'accept_candle_high': round(self._accept_candle_high, 2),
                'accept_candle_low': round(self._accept_candle_low, 2),
                'stop_model': self._stop_model.name,
                'target_model': self._target_model.name,
            },
        )

    def _compute_target(self, direction: str, entry: float, stop: float) -> float:
        risk = abs(entry - stop)

        if self._target_mode == 'opposite_va':
            return self._prior_val if direction == 'SHORT' else self._prior_vah
        elif self._target_mode == 'POC':
            poc = self._prior_poc if self._prior_poc and not pd.isna(self._prior_poc) else (self._prior_vah + self._prior_val) / 2
            return poc
        elif self._target_mode == '2R':
            return entry - 2 * risk if direction == 'SHORT' else entry + 2 * risk
        elif self._target_mode == '4R':
            return entry - 4 * risk if direction == 'SHORT' else entry + 4 * risk
        else:
            poc = self._prior_poc if self._prior_poc and not pd.isna(self._prior_poc) else (self._prior_vah + self._prior_val) / 2
            return poc
