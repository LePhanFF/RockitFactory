"""
MACD Crossover — Proof-of-concept strategy using pluggable execution models.

Demonstrates the new pattern: strategy detects → pluggable models compute stop/target.
Not expected to be a winning strategy — it's a framework proof.

Detection logic:
  - MACD(12,26,9) line crosses signal line
  - After IB (10:30+), VWAP confirmation
  - No new entries after 14:00

Unlike existing strategies which hardcode stop/target, this strategy
delegates to injected StopModel and TargetModel instances.
"""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING, List, Optional

import numpy as np
import pandas as pd

from rockit_core.models.bridge import signal_to_entry_signal
from rockit_core.models.signals import Direction, EntrySignal
from rockit_core.models.stop_models import ATRStopModel
from rockit_core.models.target_models import RMultipleTarget
from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal

if TYPE_CHECKING:
    from rockit_core.models.base import StopModel, TargetModel

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
ENTRY_CUTOFF = time(14, 0)


class MACDCrossover(StrategyBase):
    """MACD crossover strategy with pluggable stop/target models.

    Constructor takes optional stop_model and target_model.
    Defaults to ATRStopModel(2.0) and RMultipleTarget(2.0).
    """

    def __init__(
        self,
        stop_model: Optional[StopModel] = None,
        target_model: Optional[TargetModel] = None,
    ):
        self._stop_model = stop_model or ATRStopModel(2.0)
        self._target_model = target_model or RMultipleTarget(2.0)
        self._closes: List[float] = []
        self._prev_macd: Optional[float] = None
        self._prev_signal_line: Optional[float] = None

    @property
    def name(self) -> str:
        return "MACD Crossover"

    @property
    def applicable_day_types(self) -> list:
        return []  # All day types

    def on_session_start(
        self, session_date, ib_high, ib_low, ib_range, session_context,
    ) -> None:
        self._closes = []
        self._prev_macd = None
        self._prev_signal_line = None

        # Pre-load IB bar closes for MACD warm-up
        ib_bars = session_context.get('ib_bars')
        if ib_bars is not None and len(ib_bars) > 0:
            self._closes = list(ib_bars['close'].values)

    def on_bar(
        self, bar: pd.Series, bar_index: int, session_context: dict,
    ) -> Optional[Signal]:
        close = bar['close']
        self._closes.append(close)

        # Need enough bars for MACD computation
        if len(self._closes) < MACD_SLOW + MACD_SIGNAL:
            return None

        # Time gate: no entries after 14:00
        bar_time = session_context.get('bar_time')
        if bar_time is not None and bar_time >= ENTRY_CUTOFF:
            return None

        # Compute MACD
        closes = np.array(self._closes, dtype=float)
        macd_line, signal_line = _compute_macd(closes)

        if self._prev_macd is None:
            self._prev_macd = macd_line
            self._prev_signal_line = signal_line
            return None

        # Detect crossover
        direction = self._detect_crossover(
            macd_line, signal_line, self._prev_macd, self._prev_signal_line,
        )

        self._prev_macd = macd_line
        self._prev_signal_line = signal_line

        if direction is None:
            return None

        # VWAP confirmation
        vwap = session_context.get('vwap', close)
        if direction == 'LONG' and close < vwap:
            return None
        if direction == 'SHORT' and close > vwap:
            return None

        # Build EntrySignal for model computation
        model_direction = Direction.LONG if direction == 'LONG' else Direction.SHORT
        entry_signal = EntrySignal(
            model_name=self.name,
            direction=model_direction,
            price=close,
            confidence=0.6,
            setup_type='MACD_CROSSOVER',
        )

        # Delegate to pluggable models
        stop_level = self._stop_model.compute(entry_signal, bar, session_context)
        target_spec = self._target_model.compute(
            entry_signal, stop_level, bar, session_context,
        )

        day_type = session_context.get('day_type', 'neutral')
        trend_strength = session_context.get('trend_strength', '')

        return Signal(
            timestamp=bar.get('timestamp'),
            direction=direction,
            entry_price=close,
            stop_price=stop_level.price,
            target_price=target_spec.price,
            strategy_name=self.name,
            setup_type='MACD_CROSSOVER',
            day_type=day_type,
            trend_strength=trend_strength,
            confidence='medium',
            metadata={
                'macd': macd_line,
                'signal_line': signal_line,
                'stop_model': self._stop_model.name,
                'target_model': self._target_model.name,
            },
        )

    @staticmethod
    def _detect_crossover(
        macd: float, signal: float, prev_macd: float, prev_signal: float,
    ) -> Optional[str]:
        """Detect MACD/signal line crossover."""
        # MACD crosses above signal → LONG
        if prev_macd <= prev_signal and macd > signal:
            return 'LONG'
        # MACD crosses below signal → SHORT
        if prev_macd >= prev_signal and macd < signal:
            return 'SHORT'
        return None


def _compute_macd(
    closes: np.ndarray,
) -> tuple[float, float]:
    """Compute MACD line and signal line from close prices.

    Returns (macd_line, signal_line) as the latest values.
    """
    fast_ema = _ema(closes, MACD_FAST)
    slow_ema = _ema(closes, MACD_SLOW)
    macd_line = fast_ema - slow_ema

    # Signal line is EMA of MACD line
    signal_line_val = _ema(macd_line[MACD_SLOW - 1:], MACD_SIGNAL)

    return float(macd_line[-1]), float(signal_line_val[-1])


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Compute EMA using pandas for accuracy."""
    s = pd.Series(data)
    return s.ewm(span=period, adjust=False).mean().values
