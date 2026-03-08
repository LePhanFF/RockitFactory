"""Tests for entry/stop/target model registry and all concrete implementations."""

import pytest
import pandas as pd

from rockit_core.models.base import EntryModel, StopModel, TargetModel
from rockit_core.models.signals import Direction, EntrySignal, StopLevel
from rockit_core.models.registry import (
    ENTRY_MODELS,
    STOP_MODEL_FACTORIES,
    TARGET_MODEL_FACTORIES,
    get_entry_model,
    get_stop_model,
    get_target_model,
)


# --- Registry completeness ---


def test_entry_models_count():
    """All 11 entry models are registered."""
    assert len(ENTRY_MODELS) == 11


def test_stop_models_count():
    """All stop models are registered (4 original + 11 new)."""
    assert len(STOP_MODEL_FACTORIES) == 15


def test_target_models_count():
    """All target models are registered (8 original + 6 new)."""
    assert len(TARGET_MODEL_FACTORIES) == 14


def test_entry_model_keys():
    expected = {
        "orderflow_cvd", "tpo_rejection", "liquidity_sweep",
        "smt_divergence", "unicorn_ict", "three_drive",
        "double_top", "trendline", "trendline_backside",
        "tick_divergence", "bpr",
    }
    assert set(ENTRY_MODELS.keys()) == expected


def test_stop_model_keys():
    expected = {
        "1_atr", "2_atr", "lvn_hvn", "ifvg",
        "level_buffer_10pct", "level_buffer_20pct", "level_buffer_30pct",
        "fixed_10pts", "fixed_15pts", "fixed_20pts", "fixed_30pts",
        "ib_edge_10pct", "ib_edge_20pct",
        "structural_vwap_40pct", "structural_ema20_40pct",
    }
    assert set(STOP_MODEL_FACTORIES.keys()) == expected


def test_target_model_keys():
    expected = {
        "1_atr", "2_atr", "2r", "3r", "4r",
        "trail_be_fvg", "trail_be_bpr", "time_based_liquidity",
        "ib_1.0x", "ib_1.5x", "ib_2.0x",
        "level_ib_mid", "level_vwap", "adaptive",
    }
    assert set(TARGET_MODEL_FACTORIES.keys()) == expected


# --- Factory functions ---


def test_get_entry_model_valid():
    model = get_entry_model("orderflow_cvd")
    assert isinstance(model, EntryModel)
    assert model.name == "orderflow_cvd"


def test_get_entry_model_invalid():
    with pytest.raises(KeyError, match="Unknown entry model"):
        get_entry_model("nonexistent")


def test_get_stop_model_valid():
    model = get_stop_model("1_atr")
    assert isinstance(model, StopModel)


def test_get_stop_model_invalid():
    with pytest.raises(KeyError, match="Unknown stop model"):
        get_stop_model("nonexistent")


def test_get_target_model_valid():
    model = get_target_model("2r")
    assert isinstance(model, TargetModel)


def test_get_target_model_invalid():
    with pytest.raises(KeyError, match="Unknown target model"):
        get_target_model("nonexistent")


# --- All entry models instantiate ---


@pytest.mark.parametrize("key", list(ENTRY_MODELS.keys()))
def test_entry_model_instantiates(key):
    model = get_entry_model(key)
    assert isinstance(model, EntryModel)
    assert hasattr(model, 'evaluate')
    assert hasattr(model, 'name')


# --- All stop models instantiate ---


@pytest.mark.parametrize("key", list(STOP_MODEL_FACTORIES.keys()))
def test_stop_model_instantiates(key):
    model = get_stop_model(key)
    assert isinstance(model, StopModel)
    assert hasattr(model, 'compute')


# --- All target models instantiate ---


@pytest.mark.parametrize("key", list(TARGET_MODEL_FACTORIES.keys()))
def test_target_model_instantiates(key):
    model = get_target_model(key)
    assert isinstance(model, TargetModel)
    assert hasattr(model, 'compute')


# --- Stop model computation ---


def _make_entry_signal(direction=Direction.LONG, price=15100.0) -> EntrySignal:
    return EntrySignal(
        model_name="test",
        direction=direction,
        price=price,
        confidence=0.7,
        setup_type="test",
    )


def _make_bar() -> pd.Series:
    return pd.Series({
        'open': 15095, 'high': 15110, 'low': 15085, 'close': 15100,
        'volume': 1000, 'vol_delta': 100,
    })


def _make_context(atr14=20.0, ib_range=100.0, ib_high=15050, ib_low=14950) -> dict:
    return {'atr14': atr14, 'ib_range': ib_range, 'ib_high': ib_high, 'ib_low': ib_low}


def test_atr_stop_long():
    model = get_stop_model("1_atr")
    entry = _make_entry_signal(Direction.LONG, 15100.0)
    stop = model.compute(entry, _make_bar(), _make_context(atr14=20.0))
    assert stop.price == 15080.0  # 15100 - 20
    assert stop.distance_points == 20.0


def test_atr_stop_short():
    model = get_stop_model("1_atr")
    entry = _make_entry_signal(Direction.SHORT, 15100.0)
    stop = model.compute(entry, _make_bar(), _make_context(atr14=20.0))
    assert stop.price == 15120.0  # 15100 + 20
    assert stop.distance_points == 20.0


def test_2_atr_stop():
    model = get_stop_model("2_atr")
    entry = _make_entry_signal(Direction.LONG, 15100.0)
    stop = model.compute(entry, _make_bar(), _make_context(atr14=20.0))
    assert stop.price == 15060.0  # 15100 - 40
    assert stop.distance_points == 40.0


# --- Target model computation ---


def test_r_multiple_target_long():
    model = get_target_model("2r")
    entry = _make_entry_signal(Direction.LONG, 15100.0)
    stop = StopLevel(model_name="test", price=15080.0, distance_points=20.0)
    target = model.compute(entry, stop, _make_bar(), _make_context())
    assert target.price == 15140.0  # 15100 + 2 * 20
    assert target.r_multiple == 2.0


def test_r_multiple_target_short():
    model = get_target_model("3r")
    entry = _make_entry_signal(Direction.SHORT, 15100.0)
    stop = StopLevel(model_name="test", price=15120.0, distance_points=20.0)
    target = model.compute(entry, stop, _make_bar(), _make_context())
    assert target.price == 15040.0  # 15100 - 3 * 20
    assert target.r_multiple == 3.0


def test_trail_be_fvg_has_trail_rule():
    model = get_target_model("trail_be_fvg")
    entry = _make_entry_signal(Direction.LONG, 15100.0)
    stop = StopLevel(model_name="test", price=15080.0, distance_points=20.0)
    target = model.compute(entry, stop, _make_bar(), _make_context())
    assert target.trail_rule is not None
    assert target.trail_rule.activation_r == 1.0


def test_trail_be_bpr_has_trail_rule():
    model = get_target_model("trail_be_bpr")
    entry = _make_entry_signal(Direction.LONG, 15100.0)
    stop = StopLevel(model_name="test", price=15080.0, distance_points=20.0)
    target = model.compute(entry, stop, _make_bar(), _make_context())
    assert target.trail_rule is not None
    assert target.r_multiple == 3.0
