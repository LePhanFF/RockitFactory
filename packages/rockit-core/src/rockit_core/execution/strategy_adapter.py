"""StrategyAdapter: wraps a strategy to capture detections for combo replay.

Returns original signals unchanged — zero impact on behavior.
"""

from __future__ import annotations

from copy import deepcopy
from typing import List, Optional, Tuple

import pandas as pd

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal


class StrategyAdapter(StrategyBase):
    """Wraps a strategy to capture (signal, bar, session_context) for combo replay.

    Passes through all calls to the wrapped strategy unchanged.
    """

    def __init__(self, strategy: StrategyBase):
        self._strategy = strategy
        self.detections: List[Tuple[Signal, pd.Series, dict]] = []

    @property
    def name(self) -> str:
        return self._strategy.name

    @property
    def applicable_day_types(self) -> list:
        return self._strategy.applicable_day_types

    def on_session_start(
        self, session_date, ib_high, ib_low, ib_range, session_context,
    ) -> None:
        self._strategy.on_session_start(
            session_date, ib_high, ib_low, ib_range, session_context,
        )

    def on_bar(
        self, bar: pd.Series, bar_index: int, session_context: dict,
    ) -> Optional[Signal]:
        signal = self._strategy.on_bar(bar, bar_index, session_context)
        if signal is not None:
            self.detections.append((
                signal,
                bar.copy(),
                deepcopy(session_context),
            ))
        return signal

    def on_session_end(self, session_date) -> None:
        self._strategy.on_session_end(session_date)

    def reset_detections(self) -> None:
        """Clear captured detections."""
        self.detections = []
