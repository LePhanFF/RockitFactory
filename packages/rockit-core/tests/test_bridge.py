"""Tests for the Signal ↔ EntrySignal bridge."""

from datetime import datetime

import pandas as pd

from rockit_core.models.bridge import recompute_signal, signal_to_entry_signal
from rockit_core.models.signals import Direction
from rockit_core.models.stop_models import ATRStopModel, FixedPointsStop
from rockit_core.models.target_models import RMultipleTarget
from rockit_core.strategies.signal import Signal


def _make_signal(**overrides):
    defaults = dict(
        timestamp=datetime(2025, 1, 15, 10, 35),
        direction='LONG',
        entry_price=20000.0,
        stop_price=19950.0,
        target_price=20100.0,
        strategy_name='TestStrategy',
        setup_type='TEST_SETUP',
        day_type='neutral',
        trend_strength='moderate',
        confidence='high',
        metadata={'key': 'value'},
    )
    defaults.update(overrides)
    return Signal(**defaults)


def _bar():
    return pd.Series({
        'open': 19990, 'high': 20010, 'low': 19980,
        'close': 20000, 'volume': 1000,
    })


def _ctx():
    return {
        'ib_range': 100.0, 'ib_high': 20050.0, 'ib_low': 19950.0,
        'atr14': 80.0, 'vwap': 20000.0,
    }


class TestSignalToEntrySignal:
    def test_long_direction_converted(self):
        sig = _make_signal(direction='LONG')
        entry = signal_to_entry_signal(sig)
        assert entry.direction == Direction.LONG

    def test_short_direction_converted(self):
        sig = _make_signal(direction='SHORT')
        entry = signal_to_entry_signal(sig)
        assert entry.direction == Direction.SHORT

    def test_price_preserved(self):
        sig = _make_signal(entry_price=20123.5)
        entry = signal_to_entry_signal(sig)
        assert entry.price == 20123.5

    def test_strategy_name_becomes_model_name(self):
        sig = _make_signal(strategy_name='MyStrat')
        entry = signal_to_entry_signal(sig)
        assert entry.model_name == 'MyStrat'

    def test_setup_type_preserved(self):
        sig = _make_signal(setup_type='IBH_RETEST')
        entry = signal_to_entry_signal(sig)
        assert entry.setup_type == 'IBH_RETEST'

    def test_confidence_mapping(self):
        assert signal_to_entry_signal(_make_signal(confidence='high')).confidence == 1.0
        assert signal_to_entry_signal(_make_signal(confidence='medium')).confidence == 0.7
        assert signal_to_entry_signal(_make_signal(confidence='low')).confidence == 0.4

    def test_metadata_copied(self):
        sig = _make_signal(metadata={'foo': 'bar'})
        entry = signal_to_entry_signal(sig)
        assert entry.metadata == {'foo': 'bar'}


class TestRecomputeSignal:
    def test_recompute_changes_stop_and_target(self):
        original = _make_signal(stop_price=19950, target_price=20100)
        stop_model = FixedPointsStop(25.0)
        target_model = RMultipleTarget(3.0)

        result = recompute_signal(original, stop_model, target_model, _bar(), _ctx())

        # FixedPointsStop(25) → stop = 20000 - 25 = 19975
        assert result.stop_price == 19975.0
        # RMultipleTarget(3) → target = 20000 + 3*25 = 20075
        assert result.target_price == 20075.0

    def test_recompute_preserves_non_price_fields(self):
        original = _make_signal(
            strategy_name='TestStrat',
            setup_type='TEST',
            day_type='trend_bull',
            trend_strength='strong',
            confidence='high',
            pyramid_level=1,
        )
        result = recompute_signal(original, ATRStopModel(1.0), RMultipleTarget(2.0), _bar(), _ctx())

        assert result.strategy_name == 'TestStrat'
        assert result.setup_type == 'TEST'
        assert result.day_type == 'trend_bull'
        assert result.trend_strength == 'strong'
        assert result.confidence == 'high'
        assert result.pyramid_level == 1

    def test_recompute_adds_model_names_to_metadata(self):
        original = _make_signal(metadata={'original_key': 42})
        stop = ATRStopModel(2.0)
        target = RMultipleTarget(3.0)

        result = recompute_signal(original, stop, target, _bar(), _ctx())

        assert result.metadata['stop_model'] == stop.name
        assert result.metadata['target_model'] == target.name
        assert result.metadata['original_key'] == 42

    def test_recompute_short_direction(self):
        original = _make_signal(direction='SHORT', entry_price=20000)
        stop = FixedPointsStop(20.0)
        target = RMultipleTarget(2.0)

        result = recompute_signal(original, stop, target, _bar(), _ctx())

        # SHORT: stop = 20000 + 20 = 20020
        assert result.stop_price == 20020.0
        # SHORT: target = 20000 - 2*20 = 19960
        assert result.target_price == 19960.0

    def test_different_models_produce_different_results(self):
        original = _make_signal()
        result_tight = recompute_signal(original, ATRStopModel(1.0), RMultipleTarget(2.0), _bar(), _ctx())
        result_wide = recompute_signal(original, ATRStopModel(2.0), RMultipleTarget(2.0), _bar(), _ctx())

        # Wider stop → different stop price
        assert result_tight.stop_price != result_wide.stop_price
        # Wider stop → further target (same R multiple but larger base)
        assert result_tight.target_price != result_wide.target_price
