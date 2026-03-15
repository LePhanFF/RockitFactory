"""Dataclasses for trade model signals and specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Direction(Enum):
    LONG = "long"
    SHORT = "short"


class TrailType(Enum):
    BREAKEVEN = "breakeven"
    FVG = "fvg"
    BPR = "bpr"
    ATR = "atr"
    FIXED = "fixed"


@dataclass(frozen=True)
class EntrySignal:
    """Signal emitted by an EntryModel when entry conditions are met.

    Attributes:
        model_name: Which entry model produced this signal.
        direction: Long or short.
        price: Suggested entry price.
        confidence: 0.0 to 1.0 confidence in the signal.
        setup_type: Human-readable setup description.
        metadata: Additional context (confluences, delta, etc.).
    """

    model_name: str
    direction: Direction
    price: float
    confidence: float
    setup_type: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class StopLevel:
    """Stop-loss level computed by a StopModel.

    Attributes:
        model_name: Which stop model produced this level.
        price: Stop-loss price.
        distance_points: Distance from entry in points.
        risk_dollars: Dollar risk at this stop level (given instrument).
    """

    model_name: str
    price: float
    distance_points: float
    risk_dollars: float = 0.0


@dataclass(frozen=True)
class TargetSpec:
    """Target specification computed by a TargetModel.

    Attributes:
        model_name: Which target model produced this spec.
        price: Target exit price.
        r_multiple: Risk-reward multiple (target distance / stop distance).
        trail_rule: Optional trailing stop rule to apply after reaching this target.
    """

    model_name: str
    price: float
    r_multiple: float = 0.0
    trail_rule: TrailRule | None = None


@dataclass(frozen=True)
class TrailRule:
    """Trailing stop rule activated after a target is reached.

    Attributes:
        trail_type: Type of trailing mechanism.
        activation_r: R-multiple at which trailing begins.
        trail_distance_points: Distance to trail behind price (for fixed/ATR).
    """

    trail_type: TrailType
    activation_r: float = 1.0
    trail_distance_points: float = 0.0
