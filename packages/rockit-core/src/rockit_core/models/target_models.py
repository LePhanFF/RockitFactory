"""Concrete target model implementations."""

from __future__ import annotations

import pandas as pd

from rockit_core.models.base import TargetModel
from rockit_core.models.signals import (
    Direction,
    EntrySignal,
    StopLevel,
    TargetSpec,
    TrailRule,
    TrailType,
)


class RMultipleTarget(TargetModel):
    """Target at N * risk (R-multiple)."""

    def __init__(self, r_multiple: float = 2.0):
        self._r_multiple = r_multiple

    @property
    def name(self) -> str:
        return f"{int(self._r_multiple)}r"

    def compute(
        self, entry_signal: EntrySignal, stop_level: StopLevel, bar: pd.Series, session_context: dict
    ) -> TargetSpec:
        distance = stop_level.distance_points * self._r_multiple

        if entry_signal.direction == Direction.LONG:
            target_price = entry_signal.price + distance
        else:
            target_price = entry_signal.price - distance

        return TargetSpec(
            model_name=self.name,
            price=target_price,
            r_multiple=self._r_multiple,
        )


class ATRTarget(TargetModel):
    """Target at N * ATR from entry."""

    def __init__(self, atr_multiple: float = 2.0):
        self._atr_multiple = atr_multiple

    @property
    def name(self) -> str:
        return f"{int(self._atr_multiple)}_atr"

    def compute(
        self, entry_signal: EntrySignal, stop_level: StopLevel, bar: pd.Series, session_context: dict
    ) -> TargetSpec:
        atr = session_context.get('atr14', session_context.get('ib_range', 20.0))
        distance = atr * self._atr_multiple

        if entry_signal.direction == Direction.LONG:
            target_price = entry_signal.price + distance
        else:
            target_price = entry_signal.price - distance

        r_multiple = distance / stop_level.distance_points if stop_level.distance_points > 0 else 0

        return TargetSpec(
            model_name=self.name,
            price=target_price,
            r_multiple=r_multiple,
        )


class TrailBreakevenFVGTarget(TargetModel):
    """Trail to breakeven after 1R, then trail by FVG zones."""

    @property
    def name(self) -> str:
        return "trail_be_fvg"

    def compute(
        self, entry_signal: EntrySignal, stop_level: StopLevel, bar: pd.Series, session_context: dict
    ) -> TargetSpec:
        # Initial target at 2R
        distance = stop_level.distance_points * 2.0

        if entry_signal.direction == Direction.LONG:
            target_price = entry_signal.price + distance
        else:
            target_price = entry_signal.price - distance

        return TargetSpec(
            model_name=self.name,
            price=target_price,
            r_multiple=2.0,
            trail_rule=TrailRule(
                trail_type=TrailType.FVG,
                activation_r=1.0,
            ),
        )


class TrailBreakevenBPRTarget(TargetModel):
    """Trail to breakeven after 1R, then trail by BPR (Balanced Price Range)."""

    @property
    def name(self) -> str:
        return "trail_be_bpr"

    def compute(
        self, entry_signal: EntrySignal, stop_level: StopLevel, bar: pd.Series, session_context: dict
    ) -> TargetSpec:
        distance = stop_level.distance_points * 3.0

        if entry_signal.direction == Direction.LONG:
            target_price = entry_signal.price + distance
        else:
            target_price = entry_signal.price - distance

        return TargetSpec(
            model_name=self.name,
            price=target_price,
            r_multiple=3.0,
            trail_rule=TrailRule(
                trail_type=TrailType.BPR,
                activation_r=1.0,
            ),
        )


class TimeBasedLiquidityTarget(TargetModel):
    """Target based on time-based liquidity (session close, hour gaps)."""

    @property
    def name(self) -> str:
        return "time_based_liquidity"

    def compute(
        self, entry_signal: EntrySignal, stop_level: StopLevel, bar: pd.Series, session_context: dict
    ) -> TargetSpec:
        ib_range = session_context.get('ib_range', 20.0)
        distance = ib_range * 2.0

        if entry_signal.direction == Direction.LONG:
            target_price = entry_signal.price + distance
        else:
            target_price = entry_signal.price - distance

        r_multiple = distance / stop_level.distance_points if stop_level.distance_points > 0 else 0

        return TargetSpec(
            model_name=self.name,
            price=target_price,
            r_multiple=r_multiple,
        )


class IBRangeTarget(TargetModel):
    """Target at N × IB_range from entry."""

    def __init__(self, ib_mult: float = 1.5):
        self._ib_mult = ib_mult

    @property
    def name(self) -> str:
        return f"ib_{self._ib_mult}x"

    def compute(
        self, entry_signal: EntrySignal, stop_level: StopLevel, bar: pd.Series, session_context: dict
    ) -> TargetSpec:
        ib_range = session_context.get('ib_range', 20.0)
        distance = ib_range * self._ib_mult

        if entry_signal.direction == Direction.LONG:
            target_price = entry_signal.price + distance
        else:
            target_price = entry_signal.price - distance

        r_multiple = distance / stop_level.distance_points if stop_level.distance_points > 0 else 0

        return TargetSpec(
            model_name=self.name,
            price=target_price,
            r_multiple=r_multiple,
        )


class LevelTarget(TargetModel):
    """Target at a named level from session_context (e.g. ib_mid, vwap)."""

    def __init__(self, level_key: str = 'ib_mid'):
        self._level_key = level_key

    @property
    def name(self) -> str:
        return f"level_{self._level_key}"

    def compute(
        self, entry_signal: EntrySignal, stop_level: StopLevel, bar: pd.Series, session_context: dict
    ) -> TargetSpec:
        target_price = session_context.get(self._level_key)
        if target_price is None:
            target_price = entry_signal.price + stop_level.distance_points

        distance = abs(target_price - entry_signal.price)
        r_multiple = distance / stop_level.distance_points if stop_level.distance_points > 0 else 0

        return TargetSpec(
            model_name=self.name,
            price=target_price,
            r_multiple=r_multiple,
        )


class AdaptiveTarget(TargetModel):
    """Day-type gated target: trend→2.5x IB, p_day→1.5x IB, b_day→IB mid."""

    @property
    def name(self) -> str:
        return "adaptive"

    def compute(
        self, entry_signal: EntrySignal, stop_level: StopLevel, bar: pd.Series, session_context: dict
    ) -> TargetSpec:
        ib_range = session_context.get('ib_range', 20.0)
        day_type = session_context.get('day_type', 'neutral')

        if day_type in ('trend_bull', 'trend_bear'):
            distance = ib_range * 2.5
        elif day_type in ('p_day_bull', 'p_day_bear', 'p_day'):
            distance = ib_range * 1.5
        elif day_type == 'b_day':
            ib_mid = session_context.get('ib_mid')
            if ib_mid is not None:
                distance = abs(ib_mid - entry_signal.price)
                if distance < stop_level.distance_points:
                    distance = stop_level.distance_points * 1.5
            else:
                distance = ib_range * 0.5
        else:
            distance = ib_range * 1.0

        if entry_signal.direction == Direction.LONG:
            target_price = entry_signal.price + distance
        else:
            target_price = entry_signal.price - distance

        r_multiple = distance / stop_level.distance_points if stop_level.distance_points > 0 else 0

        return TargetSpec(
            model_name=self.name,
            price=target_price,
            r_multiple=r_multiple,
        )
