"""Unit tests for new stop and target model implementations."""

import pandas as pd
import pytest

from rockit_core.models.signals import Direction, EntrySignal, StopLevel
from rockit_core.models.stop_models import (
    ATRStopModel,
    FixedPointsStop,
    IBEdgeStop,
    LevelBufferStop,
    StructuralStop,
    VAEdgeStop,
)
from rockit_core.models.target_models import (
    AdaptiveTarget,
    IBRangeTarget,
    LevelTarget,
    RMultipleTarget,
)


# --- Fixtures ---

def _entry(direction=Direction.LONG, price=20000.0):
    return EntrySignal(
        model_name="test",
        direction=direction,
        price=price,
        confidence=0.7,
        setup_type="TEST",
    )


def _bar():
    return pd.Series({'open': 19990, 'high': 20010, 'low': 19980, 'close': 20000, 'volume': 1000})


def _ctx(ib_range=100.0, ib_high=20050.0, ib_low=19950.0, **extras):
    ctx = {
        'ib_range': ib_range,
        'ib_high': ib_high,
        'ib_low': ib_low,
        'ib_mid': (ib_high + ib_low) / 2,
        'atr14': 80.0,
        'vwap': 20000.0,
        'ema20': 19990.0,
    }
    ctx.update(extras)
    return ctx


def _stop(price=20000.0, distance=50.0):
    return StopLevel(model_name="test", price=price, distance_points=distance)


# ========== STOP MODELS ==========

class TestLevelBufferStop:
    def test_long_stop_below_entry(self):
        model = LevelBufferStop(buffer_pct=0.1)
        result = model.compute(_entry(Direction.LONG, 20000), _bar(), _ctx(ib_range=100))
        assert result.price == 20000 - 10  # 10% of 100
        assert result.distance_points == 10.0

    def test_short_stop_above_entry(self):
        model = LevelBufferStop(buffer_pct=0.2)
        result = model.compute(_entry(Direction.SHORT, 20000), _bar(), _ctx(ib_range=100))
        assert result.price == 20000 + 20  # 20% of 100
        assert result.distance_points == 20.0

    def test_name_format(self):
        assert LevelBufferStop(0.1).name == "level_buffer_10pct"
        assert LevelBufferStop(0.3).name == "level_buffer_30pct"


class TestFixedPointsStop:
    def test_long_stop(self):
        model = FixedPointsStop(15.0)
        result = model.compute(_entry(Direction.LONG, 20000), _bar(), _ctx())
        assert result.price == 19985.0
        assert result.distance_points == 15.0

    def test_short_stop(self):
        model = FixedPointsStop(20.0)
        result = model.compute(_entry(Direction.SHORT, 20000), _bar(), _ctx())
        assert result.price == 20020.0
        assert result.distance_points == 20.0

    def test_name_format(self):
        assert FixedPointsStop(15).name == "fixed_15pts"
        assert FixedPointsStop(30).name == "fixed_30pts"


class TestIBEdgeStop:
    def test_long_stop_below_ib_low(self):
        model = IBEdgeStop(buffer_pct=0.1)
        result = model.compute(
            _entry(Direction.LONG, 20000), _bar(),
            _ctx(ib_range=100, ib_low=19950),
        )
        # Stop = IB low - 10% of IB range = 19950 - 10 = 19940
        assert result.price == 19940.0
        assert result.distance_points == 60.0  # 20000 - 19940

    def test_short_stop_above_ib_high(self):
        model = IBEdgeStop(buffer_pct=0.1)
        result = model.compute(
            _entry(Direction.SHORT, 20000), _bar(),
            _ctx(ib_range=100, ib_high=20050),
        )
        assert result.price == 20060.0  # 20050 + 10
        assert result.distance_points == 60.0

    def test_name_format(self):
        assert IBEdgeStop(0.1).name == "ib_edge_10pct"
        assert IBEdgeStop(0.2).name == "ib_edge_20pct"


class TestStructuralStop:
    def test_long_stop_below_vwap(self):
        model = StructuralStop('vwap', 0.4)
        result = model.compute(
            _entry(Direction.LONG, 20000), _bar(),
            _ctx(ib_range=100, vwap=19980),
        )
        # Stop = vwap - 40% of IB range = 19980 - 40 = 19940
        assert result.price == 19940.0
        assert result.distance_points == 60.0

    def test_short_stop_above_ema(self):
        model = StructuralStop('ema20', 0.4)
        result = model.compute(
            _entry(Direction.SHORT, 20000), _bar(),
            _ctx(ib_range=100, ema20=20020),
        )
        # Stop = ema20 + 40% of IB range = 20020 + 40 = 20060
        assert result.price == 20060.0
        assert result.distance_points == 60.0

    def test_missing_level_falls_back_to_entry(self):
        model = StructuralStop('nonexistent_level', 0.4)
        result = model.compute(_entry(Direction.LONG, 20000), _bar(), _ctx(ib_range=100))
        # Falls back to entry price: 20000 - 40 = 19960
        assert result.price == 19960.0

    def test_name_format(self):
        assert StructuralStop('vwap', 0.4).name == "structural_vwap_40pct"


# ========== TARGET MODELS ==========

class TestIBRangeTarget:
    def test_long_target(self):
        model = IBRangeTarget(1.5)
        result = model.compute(_entry(Direction.LONG, 20000), _stop(19950, 50), _bar(), _ctx(ib_range=100))
        assert result.price == 20150.0  # 20000 + 1.5 * 100
        assert result.r_multiple == 3.0  # 150 / 50

    def test_short_target(self):
        model = IBRangeTarget(2.0)
        result = model.compute(_entry(Direction.SHORT, 20000), _stop(20050, 50), _bar(), _ctx(ib_range=100))
        assert result.price == 19800.0  # 20000 - 2.0 * 100
        assert result.r_multiple == 4.0  # 200 / 50

    def test_name_format(self):
        assert IBRangeTarget(1.5).name == "ib_1.5x"


class TestLevelTarget:
    def test_target_at_named_level(self):
        model = LevelTarget('ib_mid')
        ctx = _ctx(ib_range=100, ib_high=20050, ib_low=19950)
        result = model.compute(_entry(Direction.LONG, 19960), _stop(19910, 50), _bar(), ctx)
        assert result.price == 20000.0  # ib_mid = (20050 + 19950) / 2

    def test_missing_level_falls_back(self):
        model = LevelTarget('nonexistent')
        result = model.compute(_entry(Direction.LONG, 20000), _stop(19950, 50), _bar(), _ctx())
        # Falls back to entry + stop distance = 20000 + 50 = 20050
        assert result.price == 20050.0

    def test_name_format(self):
        assert LevelTarget('ib_mid').name == "level_ib_mid"
        assert LevelTarget('vwap').name == "level_vwap"


class TestAdaptiveTarget:
    def test_trend_day_uses_2_5x_ib(self):
        model = AdaptiveTarget()
        ctx = _ctx(ib_range=100, day_type='trend_bull')
        result = model.compute(_entry(Direction.LONG, 20000), _stop(19950, 50), _bar(), ctx)
        assert result.price == 20250.0  # 20000 + 2.5 * 100

    def test_p_day_uses_1_5x_ib(self):
        model = AdaptiveTarget()
        ctx = _ctx(ib_range=100, day_type='p_day_bull')
        result = model.compute(_entry(Direction.LONG, 20000), _stop(19950, 50), _bar(), ctx)
        assert result.price == 20150.0

    def test_b_day_uses_ib_mid(self):
        model = AdaptiveTarget()
        ctx = _ctx(ib_range=100, ib_high=20050, ib_low=19950, day_type='b_day')
        result = model.compute(_entry(Direction.LONG, 19960), _stop(19910, 50), _bar(), ctx)
        # ib_mid = 20000, distance from 19960 = 40. But 40 < 50 (stop dist),
        # so falls back to 1.5 * stop = 75 → target = 19960 + 75 = 20035
        assert result.price == 20035.0

    def test_neutral_day_uses_1x_ib(self):
        model = AdaptiveTarget()
        ctx = _ctx(ib_range=100, day_type='neutral')
        result = model.compute(_entry(Direction.LONG, 20000), _stop(19950, 50), _bar(), ctx)
        assert result.price == 20100.0  # 20000 + 1.0 * 100

    def test_name(self):
        assert AdaptiveTarget().name == "adaptive"


# ========== VA EDGE STOP ==========

class TestVAEdgeStop:
    def test_long_stop_below_val(self):
        model = VAEdgeStop(10.0)
        ctx = _ctx()
        ctx['prior_va_val'] = 19900.0
        ctx['prior_va_vah'] = 20100.0
        result = model.compute(_entry(Direction.LONG, 19950.0), _bar(), ctx)
        # LONG: prior_va_val - buffer = 19900 - 10 = 19890
        assert result.price == 19890.0
        assert result.distance_points == 60.0  # |19950 - 19890|

    def test_short_stop_above_vah(self):
        model = VAEdgeStop(10.0)
        ctx = _ctx()
        ctx['prior_va_val'] = 19900.0
        ctx['prior_va_vah'] = 20100.0
        result = model.compute(_entry(Direction.SHORT, 20050.0), _bar(), ctx)
        # SHORT: prior_va_vah + buffer = 20100 + 10 = 20110
        assert result.price == 20110.0
        assert result.distance_points == 60.0  # |20050 - 20110|

    def test_name(self):
        assert VAEdgeStop(10.0).name == "va_edge_10.0pts"
        assert VAEdgeStop(5.0).name == "va_edge_5.0pts"

    def test_fallback_when_no_va_levels(self):
        model = VAEdgeStop(10.0)
        ctx = _ctx()  # No prior_va_val/vah
        result = model.compute(_entry(Direction.LONG, 20000.0), _bar(), ctx)
        # Falls back to entry_price: 20000 - 10 = 19990
        assert result.price == 19990.0
        assert result.distance_points == 10.0


# ========== REGISTRY ==========

class TestRegistry:
    def test_all_new_stops_registered(self):
        from rockit_core.models.registry import get_stop_model
        for key in ['level_buffer_10pct', 'fixed_15pts', 'ib_edge_10pct', 'structural_vwap_40pct']:
            model = get_stop_model(key)
            assert model is not None

    def test_all_new_targets_registered(self):
        from rockit_core.models.registry import get_target_model
        for key in ['ib_1.5x', 'level_ib_mid', 'adaptive']:
            model = get_target_model(key)
            assert model is not None

    def test_unknown_stop_raises(self):
        from rockit_core.models.registry import get_stop_model
        with pytest.raises(KeyError):
            get_stop_model("nonexistent")

    def test_unknown_target_raises(self):
        from rockit_core.models.registry import get_target_model
        with pytest.raises(KeyError):
            get_target_model("nonexistent")
