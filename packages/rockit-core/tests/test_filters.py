"""Tests for filter chain: base, composite, and individual filters."""

from datetime import datetime

import pandas as pd

from rockit_core.filters.base import FilterBase
from rockit_core.filters.composite import CompositeFilter
from rockit_core.strategies.signal import Signal


def _make_signal(**kwargs) -> Signal:
    defaults = dict(
        timestamp=datetime.now(),
        direction='LONG',
        entry_price=15100.0,
        stop_price=15080.0,
        target_price=15150.0,
        strategy_name='test',
        setup_type='test',
        day_type='trend_up',
    )
    defaults.update(kwargs)
    return Signal(**defaults)


def _make_bar(**kwargs) -> pd.Series:
    defaults = dict(
        open=15095, high=15110, low=15085, close=15100,
        volume=1000, vol_ask=550, vol_bid=450, vol_delta=100,
    )
    defaults.update(kwargs)
    return pd.Series(defaults)


class AlwaysPassFilter(FilterBase):
    @property
    def name(self) -> str:
        return "always_pass"

    def should_trade(self, signal, bar, session_context):
        return True


class AlwaysBlockFilter(FilterBase):
    @property
    def name(self) -> str:
        return "always_block"

    def should_trade(self, signal, bar, session_context):
        return False


# --- FilterBase ---

def test_filter_base_is_abstract():
    import pytest
    with pytest.raises(TypeError):
        FilterBase()


# --- CompositeFilter ---

def test_composite_empty_passes():
    """Empty composite passes everything."""
    f = CompositeFilter([])
    assert f.should_trade(_make_signal(), _make_bar(), {})


def test_composite_single_pass():
    f = CompositeFilter([AlwaysPassFilter()])
    assert f.should_trade(_make_signal(), _make_bar(), {})


def test_composite_single_block():
    f = CompositeFilter([AlwaysBlockFilter()])
    assert not f.should_trade(_make_signal(), _make_bar(), {})


def test_composite_mixed_blocks():
    """If any filter blocks, composite blocks."""
    f = CompositeFilter([AlwaysPassFilter(), AlwaysBlockFilter(), AlwaysPassFilter()])
    assert not f.should_trade(_make_signal(), _make_bar(), {})


def test_composite_all_pass():
    f = CompositeFilter([AlwaysPassFilter(), AlwaysPassFilter()])
    assert f.should_trade(_make_signal(), _make_bar(), {})


def test_composite_name():
    f = CompositeFilter([AlwaysPassFilter(), AlwaysBlockFilter()])
    assert "always_pass" in f.name
    assert "always_block" in f.name
    assert "Composite" in f.name


# --- Individual filter imports ---

def test_time_filter_imports():
    from rockit_core.filters.time_filter import TimeFilter
    assert issubclass(TimeFilter, FilterBase)


def test_trend_filter_imports():
    from rockit_core.filters.trend_filter import TrendFilter
    assert issubclass(TrendFilter, FilterBase)


def test_volatility_filter_imports():
    from rockit_core.filters.volatility_filter import VolatilityFilter
    assert issubclass(VolatilityFilter, FilterBase)


def test_order_flow_filter_imports():
    from rockit_core.filters.order_flow_filter import DeltaFilter, CVDFilter, VolumeFilter
    assert issubclass(DeltaFilter, FilterBase)
    assert issubclass(CVDFilter, FilterBase)
    assert issubclass(VolumeFilter, FilterBase)


def test_regime_filter_imports():
    from rockit_core.filters.regime_filter import RegimeFilter
    assert issubclass(RegimeFilter, FilterBase)
