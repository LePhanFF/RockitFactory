"""Trading strategies based on Dalton Market Profile / Auction Market Theory."""

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.day_confidence import DayTypeConfidence, DayTypeConfidenceScorer
from rockit_core.strategies.day_type import DayType, TrendStrength, classify_day_type, classify_trend_strength
from rockit_core.strategies.signal import Signal

__all__ = [
    # Foundation
    "DayType",
    "DayTypeConfidence",
    "DayTypeConfidenceScorer",
    "Signal",
    "StrategyBase",
    "TrendStrength",
    "classify_day_type",
    "classify_trend_strength",
]
