"""Contract tests for entry/stop/target model interfaces."""

import pandas as pd

from rockit_core.models.base import EntryModel, StopModel, TargetModel
from rockit_core.models.signals import (
    Direction,
    EntrySignal,
    StopLevel,
    TargetSpec,
    TrailRule,
    TrailType,
)


# --- Stub implementations for contract testing ---


class StubEntryModel(EntryModel):
    @property
    def name(self) -> str:
        return "stub_entry"

    def evaluate(self, bar: pd.Series, session_context: dict) -> EntrySignal | None:
        if bar.get("close", 0) > session_context.get("ibh", 0):
            return EntrySignal(
                model_name=self.name,
                direction=Direction.LONG,
                price=bar["close"],
                confidence=0.8,
                setup_type="IB breakout",
            )
        return None


class StubStopModel(StopModel):
    @property
    def name(self) -> str:
        return "stub_stop_1atr"

    def compute(self, entry_signal: EntrySignal, bar: pd.Series, session_context: dict) -> StopLevel:
        atr = session_context.get("atr", 10.0)
        if entry_signal.direction == Direction.LONG:
            stop_price = entry_signal.price - atr
        else:
            stop_price = entry_signal.price + atr
        return StopLevel(
            model_name=self.name,
            price=stop_price,
            distance_points=atr,
        )


class StubTargetModel(TargetModel):
    @property
    def name(self) -> str:
        return "stub_target_2r"

    def compute(
        self, entry_signal: EntrySignal, stop_level: StopLevel, bar: pd.Series, session_context: dict
    ) -> TargetSpec:
        distance = stop_level.distance_points * 2
        if entry_signal.direction == Direction.LONG:
            target_price = entry_signal.price + distance
        else:
            target_price = entry_signal.price - distance
        return TargetSpec(
            model_name=self.name,
            price=target_price,
            r_multiple=2.0,
            trail_rule=TrailRule(trail_type=TrailType.BREAKEVEN, activation_r=1.0),
        )


# --- Contract tests ---


def test_entry_model_returns_signal():
    model = StubEntryModel()
    bar = pd.Series({"close": 15100.0, "high": 15110.0, "low": 15090.0})
    context = {"ibh": 15050.0, "ibl": 14950.0}
    signal = model.evaluate(bar, context)
    assert signal is not None
    assert signal.direction == Direction.LONG
    assert signal.price == 15100.0
    assert signal.model_name == "stub_entry"


def test_entry_model_returns_none():
    model = StubEntryModel()
    bar = pd.Series({"close": 14900.0, "high": 14910.0, "low": 14890.0})
    context = {"ibh": 15050.0, "ibl": 14950.0}
    signal = model.evaluate(bar, context)
    assert signal is None


def test_stop_model_computes_level():
    entry = EntrySignal(
        model_name="test",
        direction=Direction.LONG,
        price=15100.0,
        confidence=0.8,
        setup_type="test",
    )
    model = StubStopModel()
    bar = pd.Series({"close": 15100.0})
    stop = model.compute(entry, bar, {"atr": 20.0})
    assert stop.price == 15080.0
    assert stop.distance_points == 20.0


def test_target_model_computes_spec():
    entry = EntrySignal(
        model_name="test",
        direction=Direction.LONG,
        price=15100.0,
        confidence=0.8,
        setup_type="test",
    )
    stop = StopLevel(model_name="test", price=15080.0, distance_points=20.0)
    model = StubTargetModel()
    bar = pd.Series({"close": 15100.0})
    target = model.compute(entry, stop, bar, {})
    assert target.price == 15140.0
    assert target.r_multiple == 2.0
    assert target.trail_rule is not None
    assert target.trail_rule.trail_type == TrailType.BREAKEVEN


def test_signal_dataclasses_are_frozen():
    signal = EntrySignal(
        model_name="test",
        direction=Direction.LONG,
        price=100.0,
        confidence=0.5,
        setup_type="test",
    )
    try:
        signal.price = 200.0  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass
