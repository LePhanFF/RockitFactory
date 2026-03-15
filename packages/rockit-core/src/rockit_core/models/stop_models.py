"""Concrete stop model implementations."""

from __future__ import annotations

import pandas as pd

from rockit_core.models.base import StopModel
from rockit_core.models.signals import Direction, EntrySignal, StopLevel


class ATRStopModel(StopModel):
    """Stop at N * ATR from entry."""

    def __init__(self, atr_multiple: float = 1.0):
        self._atr_multiple = atr_multiple

    @property
    def name(self) -> str:
        return f"{self._atr_multiple}_atr"

    def compute(self, entry_signal: EntrySignal, bar: pd.Series, session_context: dict) -> StopLevel:
        atr = session_context.get('atr14', session_context.get('ib_range', 20.0))
        distance = atr * self._atr_multiple

        if entry_signal.direction == Direction.LONG:
            stop_price = entry_signal.price - distance
        else:
            stop_price = entry_signal.price + distance

        return StopLevel(
            model_name=self.name,
            price=stop_price,
            distance_points=distance,
        )


class LVNHVNStopModel(StopModel):
    """Stop at nearest LVN/HVN (Low/High Volume Node)."""

    @property
    def name(self) -> str:
        return "lvn_hvn"

    def compute(self, entry_signal: EntrySignal, bar: pd.Series, session_context: dict) -> StopLevel:
        ib_range = session_context.get('ib_range', 20.0)
        ib_high = session_context.get('ib_high', entry_signal.price + ib_range / 2)
        ib_low = session_context.get('ib_low', entry_signal.price - ib_range / 2)

        # Use IB edges as proxy for structure levels
        if entry_signal.direction == Direction.LONG:
            stop_price = ib_low - ib_range * 0.1  # Below IB low with buffer
            distance = entry_signal.price - stop_price
        else:
            stop_price = ib_high + ib_range * 0.1  # Above IB high with buffer
            distance = stop_price - entry_signal.price

        return StopLevel(
            model_name=self.name,
            price=stop_price,
            distance_points=abs(distance),
        )


class IFVGStopModel(StopModel):
    """Stop below/above the nearest inverse FVG."""

    @property
    def name(self) -> str:
        return "ifvg"

    def compute(self, entry_signal: EntrySignal, bar: pd.Series, session_context: dict) -> StopLevel:
        # Fallback to ATR-based stop if no FVG data available
        atr = session_context.get('atr14', session_context.get('ib_range', 20.0))
        distance = atr * 1.5

        if entry_signal.direction == Direction.LONG:
            stop_price = entry_signal.price - distance
        else:
            stop_price = entry_signal.price + distance

        return StopLevel(
            model_name=self.name,
            price=stop_price,
            distance_points=distance,
        )


class LevelBufferStop(StopModel):
    """Stop at entry price ± (buffer_pct × IB_range)."""

    def __init__(self, buffer_pct: float = 0.1):
        self._buffer_pct = buffer_pct

    @property
    def name(self) -> str:
        pct_label = int(self._buffer_pct * 100)
        return f"level_buffer_{pct_label}pct"

    def compute(self, entry_signal: EntrySignal, bar: pd.Series, session_context: dict) -> StopLevel:
        ib_range = session_context.get('ib_range', 20.0)
        distance = self._buffer_pct * ib_range

        if entry_signal.direction == Direction.LONG:
            stop_price = entry_signal.price - distance
        else:
            stop_price = entry_signal.price + distance

        return StopLevel(
            model_name=self.name,
            price=stop_price,
            distance_points=distance,
        )


class FixedPointsStop(StopModel):
    """Stop at entry ± N points."""

    def __init__(self, points: float = 15.0):
        self._points = points

    @property
    def name(self) -> str:
        return f"fixed_{int(self._points)}pts"

    def compute(self, entry_signal: EntrySignal, bar: pd.Series, session_context: dict) -> StopLevel:
        if entry_signal.direction == Direction.LONG:
            stop_price = entry_signal.price - self._points
        else:
            stop_price = entry_signal.price + self._points

        return StopLevel(
            model_name=self.name,
            price=stop_price,
            distance_points=self._points,
        )


class IBEdgeStop(StopModel):
    """Stop at IB high/low ± (buffer_pct × IB_range)."""

    def __init__(self, buffer_pct: float = 0.1):
        self._buffer_pct = buffer_pct

    @property
    def name(self) -> str:
        pct_label = int(self._buffer_pct * 100)
        return f"ib_edge_{pct_label}pct"

    def compute(self, entry_signal: EntrySignal, bar: pd.Series, session_context: dict) -> StopLevel:
        ib_range = session_context.get('ib_range', 20.0)
        ib_high = session_context.get('ib_high', entry_signal.price + ib_range / 2)
        ib_low = session_context.get('ib_low', entry_signal.price - ib_range / 2)
        buffer = self._buffer_pct * ib_range

        if entry_signal.direction == Direction.LONG:
            stop_price = ib_low - buffer
            distance = entry_signal.price - stop_price
        else:
            stop_price = ib_high + buffer
            distance = stop_price - entry_signal.price

        return StopLevel(
            model_name=self.name,
            price=stop_price,
            distance_points=abs(distance),
        )


class VAEdgeStop(StopModel):
    """Stop at prior VA edge + fixed buffer.

    LONG: prior_va_val - buffer_pts
    SHORT: prior_va_vah + buffer_pts
    """

    def __init__(self, buffer_pts: float = 10.0):
        self._buffer_pts = buffer_pts

    @property
    def name(self) -> str:
        return f"va_edge_{self._buffer_pts}pts"

    def compute(self, entry_signal: EntrySignal, bar: pd.Series, session_context: dict) -> StopLevel:
        if entry_signal.direction == Direction.LONG:
            edge = session_context.get('prior_va_val', entry_signal.price)
            price = edge - self._buffer_pts
        else:
            edge = session_context.get('prior_va_vah', entry_signal.price)
            price = edge + self._buffer_pts
        dist = abs(entry_signal.price - price)
        return StopLevel(model_name=self.name, price=price, distance_points=dist)


class StructuralStop(StopModel):
    """Stop at a named structural level (VWAP, EMA, etc.) ± (buffer_pct × IB_range)."""

    def __init__(self, level_key: str = 'vwap', buffer_pct: float = 0.4):
        self._level_key = level_key
        self._buffer_pct = buffer_pct

    @property
    def name(self) -> str:
        pct_label = int(self._buffer_pct * 100)
        return f"structural_{self._level_key}_{pct_label}pct"

    def compute(self, entry_signal: EntrySignal, bar: pd.Series, session_context: dict) -> StopLevel:
        ib_range = session_context.get('ib_range', 20.0)
        level = session_context.get(self._level_key)
        if level is None:
            level = entry_signal.price
        buffer = self._buffer_pct * ib_range

        if entry_signal.direction == Direction.LONG:
            stop_price = level - buffer
            distance = entry_signal.price - stop_price
        else:
            stop_price = level + buffer
            distance = stop_price - entry_signal.price

        return StopLevel(
            model_name=self.name,
            price=stop_price,
            distance_points=abs(distance),
        )
