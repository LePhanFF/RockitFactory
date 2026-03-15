"""Composable filter modules for signal filtering."""

from rockit_core.filters.base import FilterBase
from rockit_core.filters.composite import CompositeFilter
from rockit_core.filters.time_filter import TimeFilter, LunchFadeFilter
from rockit_core.filters.volatility_filter import VolatilityFilter, IBRangeFilter
from rockit_core.filters.trend_filter import TrendFilter, EMAAlignmentFilter
from rockit_core.filters.order_flow_filter import DeltaFilter, CVDFilter, VolumeFilter
from rockit_core.filters.regime_filter import RegimeFilter, SimpleRegimeFilter
from rockit_core.filters.bias_filter import BiasAlignmentFilter
from rockit_core.filters.day_type_gate_filter import DayTypeGateFilter
from rockit_core.filters.anti_chase_filter import AntiChaseFilter
from rockit_core.filters.pipeline import build_filter_pipeline

# FilterChain is an alias for CompositeFilter (legacy compatibility)
FilterChain = CompositeFilter

__all__ = [
    "FilterBase",
    "FilterChain",
    "CompositeFilter",
    "TimeFilter",
    "LunchFadeFilter",
    "VolatilityFilter",
    "IBRangeFilter",
    "TrendFilter",
    "EMAAlignmentFilter",
    "DeltaFilter",
    "CVDFilter",
    "VolumeFilter",
    "RegimeFilter",
    "SimpleRegimeFilter",
    "BiasAlignmentFilter",
    "DayTypeGateFilter",
    "AntiChaseFilter",
    "build_filter_pipeline",
]
