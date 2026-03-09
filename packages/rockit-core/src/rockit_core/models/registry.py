"""Model registry — lookup entry, stop, and target models by name."""

from __future__ import annotations

from rockit_core.models.base import EntryModel, StopModel, TargetModel
from rockit_core.models.entry_models import (
    BPREntry,
    DoubleTopEntry,
    LiquiditySweepEntry,
    OrderFlowCVDEntry,
    SMTDivergenceEntry,
    ThreeDriveEntry,
    TickDivergenceEntry,
    TPORejectionEntry,
    TrendlineBacksideEntry,
    TrendlineEntry,
    UnicornICTEntry,
)
from rockit_core.models.stop_models import (
    ATRStopModel,
    FixedPointsStop,
    IBEdgeStop,
    IFVGStopModel,
    LVNHVNStopModel,
    LevelBufferStop,
    StructuralStop,
    VAEdgeStop,
)
from rockit_core.models.target_models import (
    ATRTarget,
    AdaptiveTarget,
    IBRangeTarget,
    LevelTarget,
    RMultipleTarget,
    TimeBasedLiquidityTarget,
    TrailBreakevenBPRTarget,
    TrailBreakevenFVGTarget,
)

# Entry model registry
ENTRY_MODELS: dict[str, type[EntryModel]] = {
    "orderflow_cvd": OrderFlowCVDEntry,
    "tpo_rejection": TPORejectionEntry,
    "liquidity_sweep": LiquiditySweepEntry,
    "smt_divergence": SMTDivergenceEntry,
    "unicorn_ict": UnicornICTEntry,
    "three_drive": ThreeDriveEntry,
    "double_top": DoubleTopEntry,
    "trendline": TrendlineEntry,
    "trendline_backside": TrendlineBacksideEntry,
    "tick_divergence": TickDivergenceEntry,
    "bpr": BPREntry,
}

# Stop model registry (instances, since some are parameterized)
STOP_MODEL_FACTORIES: dict[str, type[StopModel] | callable] = {
    "1_atr": lambda: ATRStopModel(1.0),
    "2_atr": lambda: ATRStopModel(2.0),
    "lvn_hvn": LVNHVNStopModel,
    "ifvg": IFVGStopModel,
    "level_buffer_10pct": lambda: LevelBufferStop(0.1),
    "level_buffer_20pct": lambda: LevelBufferStop(0.2),
    "level_buffer_30pct": lambda: LevelBufferStop(0.3),
    "fixed_10pts": lambda: FixedPointsStop(10.0),
    "fixed_15pts": lambda: FixedPointsStop(15.0),
    "fixed_20pts": lambda: FixedPointsStop(20.0),
    "fixed_30pts": lambda: FixedPointsStop(30.0),
    "ib_edge_10pct": lambda: IBEdgeStop(0.1),
    "ib_edge_20pct": lambda: IBEdgeStop(0.2),
    "structural_vwap_40pct": lambda: StructuralStop('vwap', 0.4),
    "structural_ema20_40pct": lambda: StructuralStop('ema20', 0.4),
    "va_edge_10pts": lambda: VAEdgeStop(10.0),
    "va_edge_5pts": lambda: VAEdgeStop(5.0),
}

# Target model registry
TARGET_MODEL_FACTORIES: dict[str, type[TargetModel] | callable] = {
    "1_atr": lambda: ATRTarget(1.0),
    "2_atr": lambda: ATRTarget(2.0),
    "2r": lambda: RMultipleTarget(2.0),
    "3r": lambda: RMultipleTarget(3.0),
    "4r": lambda: RMultipleTarget(4.0),
    "trail_be_fvg": TrailBreakevenFVGTarget,
    "trail_be_bpr": TrailBreakevenBPRTarget,
    "time_based_liquidity": TimeBasedLiquidityTarget,
    "ib_1.0x": lambda: IBRangeTarget(1.0),
    "ib_1.5x": lambda: IBRangeTarget(1.5),
    "ib_2.0x": lambda: IBRangeTarget(2.0),
    "level_ib_mid": lambda: LevelTarget('ib_mid'),
    "level_vwap": lambda: LevelTarget('vwap'),
    "adaptive": AdaptiveTarget,
}


def get_entry_model(name: str) -> EntryModel:
    """Get an entry model by name."""
    cls = ENTRY_MODELS.get(name)
    if cls is None:
        raise KeyError(f"Unknown entry model '{name}'. Available: {list(ENTRY_MODELS.keys())}")
    return cls()


def get_stop_model(name: str) -> StopModel:
    """Get a stop model by name."""
    factory = STOP_MODEL_FACTORIES.get(name)
    if factory is None:
        raise KeyError(f"Unknown stop model '{name}'. Available: {list(STOP_MODEL_FACTORIES.keys())}")
    if callable(factory) and not isinstance(factory, type):
        return factory()
    return factory()


def get_target_model(name: str) -> TargetModel:
    """Get a target model by name."""
    factory = TARGET_MODEL_FACTORIES.get(name)
    if factory is None:
        raise KeyError(f"Unknown target model '{name}'. Available: {list(TARGET_MODEL_FACTORIES.keys())}")
    if callable(factory) and not isinstance(factory, type):
        return factory()
    return factory()
