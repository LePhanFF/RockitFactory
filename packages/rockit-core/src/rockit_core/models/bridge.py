"""Bridge between strategies.Signal and models.EntrySignal systems.

Converts back and forth without modifying either dataclass.
"""

from __future__ import annotations

import pandas as pd

from rockit_core.models.base import StopModel, TargetModel
from rockit_core.models.signals import Direction, EntrySignal
from rockit_core.strategies.signal import Signal


def signal_to_entry_signal(signal: Signal) -> EntrySignal:
    """Convert strategies.Signal → models.EntrySignal."""
    direction = Direction.LONG if signal.direction == 'LONG' else Direction.SHORT
    return EntrySignal(
        model_name=signal.strategy_name,
        direction=direction,
        price=signal.entry_price,
        confidence=1.0 if signal.confidence == 'high' else 0.7 if signal.confidence == 'medium' else 0.4,
        setup_type=signal.setup_type,
        metadata=dict(signal.metadata) if signal.metadata else {},
    )


def recompute_signal(
    signal: Signal,
    stop_model: StopModel,
    target_model: TargetModel,
    bar: pd.Series,
    session_context: dict,
) -> Signal:
    """Apply stop + target models to produce a new Signal with recomputed prices."""
    entry_signal = signal_to_entry_signal(signal)
    stop_level = stop_model.compute(entry_signal, bar, session_context)
    target_spec = target_model.compute(entry_signal, stop_level, bar, session_context)

    return Signal(
        timestamp=signal.timestamp,
        direction=signal.direction,
        entry_price=signal.entry_price,
        stop_price=stop_level.price,
        target_price=target_spec.price,
        strategy_name=signal.strategy_name,
        setup_type=signal.setup_type,
        day_type=signal.day_type,
        trend_strength=signal.trend_strength,
        confidence=signal.confidence,
        pyramid_level=signal.pyramid_level,
        metadata={
            **signal.metadata,
            'stop_model': stop_model.name,
            'target_model': target_model.name,
        },
    )
