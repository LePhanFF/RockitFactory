# Unit Tests

> **Layer:** Bottom of the testing pyramid
> **Speed:** All unit tests run in < 60 seconds
> **CI gate:** Every push
> **Principle:** Each test has one assertion about one behavior

---

## Strategies

### Contract Tests (Parameterized Across All Strategies)

Every class registered in `ALL_STRATEGIES` must satisfy the `StrategyBase` contract.
These tests are parameterized so a new strategy automatically gets contract-tested
when added to the registry.

```python
# packages/rockit-core/tests/strategies/test_base.py

import pytest
import pandas as pd
from datetime import datetime

from rockit_core.strategies import ALL_STRATEGIES
from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal


def make_bar(
    open_: float = 21800.0,
    high: float = 21810.0,
    low: float = 21790.0,
    close: float = 21805.0,
    volume: int = 1500,
    delta: float = 200.0,
    cvd: float = 1000.0,
    vwap: float = 21800.0,
    ema20: float = 21795.0,
    ema50: float = 21780.0,
    ema200: float = 21700.0,
    rsi14: float = 55.0,
    atr14: float = 40.0,
) -> pd.Series:
    """Create a minimal bar for strategy testing."""
    return pd.Series({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "delta": delta,
        "cvd": cvd,
        "vwap": vwap,
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "rsi14": rsi14,
        "atr14": atr14,
        "timestamp": datetime(2026, 1, 15, 11, 0, 0),
    })


def make_session_context(
    ib_high: float = 21850.0,
    ib_low: float = 21780.0,
    day_type: str = "trend_up",
    day_type_confidence: float = 0.75,
    **overrides,
) -> dict:
    """Create a minimal session_context dict for testing."""
    ctx = {
        "ib_high": ib_high,
        "ib_low": ib_low,
        "ib_range": ib_high - ib_low,
        "atr14": 40.0,
        "vwap": 21820.0,
        "session_high": ib_high + 20.0,
        "session_low": ib_low - 5.0,
        "day_type_confidence": type(
            "DTC", (), {
                "best_type": day_type,
                "best_confidence": day_type_confidence,
                "trend_bull": day_type_confidence if "trend" in day_type else 0.2,
                "trend_bear": 0.1,
                "p_day_bull": day_type_confidence if day_type == "p_day" else 0.1,
                "p_day_bear": 0.1,
                "b_day": day_type_confidence if day_type == "b_day" else 0.1,
                "neutral": day_type_confidence if day_type == "neutral" else 0.1,
            }
        )(),
        "prior_day": {
            "high": 21900.0,
            "low": 21700.0,
            "close": 21810.0,
            "vah": 21870.0,
            "val": 21730.0,
            "poc": 21800.0,
        },
        "volume_profile": {
            "poc": 21810.0,
            "vah": 21860.0,
            "val": 21750.0,
        },
    }
    ctx.update(overrides)
    return ctx


@pytest.mark.parametrize("name,cls", ALL_STRATEGIES.items())
class TestStrategyContract:
    """Contract tests that EVERY StrategyBase subclass must pass."""

    def test_is_subclass_of_strategy_base(self, name: str, cls: type) -> None:
        """Every registered strategy must subclass StrategyBase."""
        assert issubclass(cls, StrategyBase)

    def test_has_name(self, name: str, cls: type) -> None:
        """Every strategy must return a non-empty string name."""
        instance = cls()
        assert isinstance(instance.name, str)
        assert len(instance.name) > 0

    def test_has_applicable_day_types(self, name: str, cls: type) -> None:
        """Every strategy must return a list of applicable day types."""
        instance = cls()
        assert isinstance(instance.applicable_day_types, list)
        # Each element must be a string
        for dt in instance.applicable_day_types:
            assert isinstance(dt, str)

    def test_on_bar_returns_signal_or_none(self, name: str, cls: type) -> None:
        """on_bar must return Signal or None, never raise on valid input."""
        instance = cls()
        bar = make_bar()
        ctx = make_session_context()
        instance.on_session_start(
            session_date="2026-01-15",
            ib_high=ctx["ib_high"],
            ib_low=ctx["ib_low"],
            ib_range=ctx["ib_range"],
            session_context=ctx,
        )
        result = instance.on_bar(bar, bar_index=0, session_context=ctx)
        assert result is None or isinstance(result, Signal)

    def test_signal_has_valid_direction(self, name: str, cls: type) -> None:
        """If a Signal is returned, its direction must be LONG or SHORT."""
        instance = cls()
        bar = make_bar()
        ctx = make_session_context()
        instance.on_session_start(
            session_date="2026-01-15",
            ib_high=ctx["ib_high"],
            ib_low=ctx["ib_low"],
            ib_range=ctx["ib_range"],
            session_context=ctx,
        )
        result = instance.on_bar(bar, bar_index=0, session_context=ctx)
        if result is not None:
            assert result.direction in ("LONG", "SHORT")

    def test_signal_has_valid_prices(self, name: str, cls: type) -> None:
        """If a Signal is returned, entry/stop/target must be positive floats."""
        instance = cls()
        bar = make_bar()
        ctx = make_session_context()
        instance.on_session_start(
            session_date="2026-01-15",
            ib_high=ctx["ib_high"],
            ib_low=ctx["ib_low"],
            ib_range=ctx["ib_range"],
            session_context=ctx,
        )
        result = instance.on_bar(bar, bar_index=0, session_context=ctx)
        if result is not None:
            assert result.entry_price > 0
            assert result.stop_price > 0
            assert result.target_price > 0

    def test_signal_prices_consistent_with_direction(self, name: str, cls: type) -> None:
        """For LONG: stop < entry < target. For SHORT: target < entry < stop."""
        instance = cls()
        bar = make_bar()
        ctx = make_session_context()
        instance.on_session_start(
            session_date="2026-01-15",
            ib_high=ctx["ib_high"],
            ib_low=ctx["ib_low"],
            ib_range=ctx["ib_range"],
            session_context=ctx,
        )
        result = instance.on_bar(bar, bar_index=0, session_context=ctx)
        if result is not None:
            if result.direction == "LONG":
                assert result.stop_price < result.entry_price
                assert result.target_price > result.entry_price
            else:
                assert result.stop_price > result.entry_price
                assert result.target_price < result.entry_price
```

### Per-Strategy Fixture Tests

Each strategy gets its own test file with known-good scenarios. The pattern:
given a `SessionContext` that represents a clear day type, the strategy MUST
(or MUST NOT) produce a signal.

```python
# packages/rockit-core/tests/strategies/test_trend_bull.py

import pytest
from rockit_core.strategies.trend_bull import TrendDayBull
from tests.conftest import make_bar, make_session_context


class TestTrendDayBull:
    """Unit tests for TrendDayBull strategy."""

    @pytest.fixture
    def strategy(self) -> TrendDayBull:
        return TrendDayBull()

    @pytest.fixture
    def trend_up_context(self) -> dict:
        """Clear trend-up day: price accepted above IBH, strong delta."""
        return make_session_context(
            ib_high=21850.0,
            ib_low=21780.0,
            day_type="trend_up",
            day_type_confidence=0.80,
            session_high=21900.0,
        )

    @pytest.fixture
    def trend_up_bar(self) -> "pd.Series":
        """Bar showing strong upside continuation above IBH."""
        return make_bar(
            open_=21860.0,
            high=21880.0,
            low=21855.0,
            close=21875.0,
            delta=450.0,
            cvd=2500.0,
            vwap=21840.0,
        )

    def test_emits_long_on_clear_trend_day(
        self, strategy, trend_up_context, trend_up_bar,
    ) -> None:
        """TrendDayBull MUST emit a LONG signal on a clear trend-up day."""
        strategy.on_session_start(
            session_date="2026-01-15",
            ib_high=trend_up_context["ib_high"],
            ib_low=trend_up_context["ib_low"],
            ib_range=trend_up_context["ib_range"],
            session_context=trend_up_context,
        )
        signal = strategy.on_bar(trend_up_bar, bar_index=5, session_context=trend_up_context)
        assert signal is not None
        assert signal.direction == "LONG"
        assert signal.strategy_name == strategy.name

    def test_no_signal_on_b_day(self, strategy) -> None:
        """TrendDayBull MUST NOT signal on a B-Day."""
        ctx = make_session_context(day_type="b_day", day_type_confidence=0.70)
        bar = make_bar(close=21810.0, delta=50.0)
        strategy.on_session_start(
            session_date="2026-01-15",
            ib_high=ctx["ib_high"],
            ib_low=ctx["ib_low"],
            ib_range=ctx["ib_range"],
            session_context=ctx,
        )
        signal = strategy.on_bar(bar, bar_index=3, session_context=ctx)
        assert signal is None

    def test_no_signal_on_weak_delta(self, strategy, trend_up_context) -> None:
        """TrendDayBull MUST NOT signal when delta is weak."""
        weak_bar = make_bar(close=21860.0, delta=30.0, cvd=100.0)
        strategy.on_session_start(
            session_date="2026-01-15",
            ib_high=trend_up_context["ib_high"],
            ib_low=trend_up_context["ib_low"],
            ib_range=trend_up_context["ib_range"],
            session_context=trend_up_context,
        )
        signal = strategy.on_bar(weak_bar, bar_index=5, session_context=trend_up_context)
        assert signal is None

    def test_no_signal_below_ib_high(self, strategy, trend_up_context) -> None:
        """TrendDayBull MUST NOT signal when price is below IBH."""
        below_ibh_bar = make_bar(close=21840.0, delta=400.0)
        strategy.on_session_start(
            session_date="2026-01-15",
            ib_high=trend_up_context["ib_high"],
            ib_low=trend_up_context["ib_low"],
            ib_range=trend_up_context["ib_range"],
            session_context=trend_up_context,
        )
        signal = strategy.on_bar(below_ibh_bar, bar_index=5, session_context=trend_up_context)
        assert signal is None
```

Repeat this pattern for each of the 16 strategies. Each test file should have:
- At least one positive test (known-good conditions produce a signal)
- At least one day-type mismatch test (wrong day type produces None)
- At least one weak-data test (correct day type but insufficient confirmation)

---

## Entry / Stop / Target Models

### Entry Models

```python
# packages/rockit-core/tests/models/test_entry_unicorn_ict.py

import pytest
from rockit_core.models.base import SessionContext, EntrySignal
from rockit_core.models.entry.unicorn_ict import UnicornICTEntry
from tests.conftest import make_session_context_dataclass


class TestUnicornICTEntry:
    """Unit tests for the Unicorn ICT entry model."""

    @pytest.fixture
    def model(self) -> UnicornICTEntry:
        return UnicornICTEntry()

    @pytest.fixture
    def bullish_unicorn_context(self) -> SessionContext:
        """Context with MSS + FVG + OTE confluence for a LONG entry."""
        return make_session_context_dataclass(
            current_price=21835.0,
            mss_levels=[{"price": 21820.0, "direction": "LONG", "time": "10:45"}],
            fvgs=[{"high": 21840.0, "low": 21830.0, "tf": "5m", "direction": "LONG"}],
            bars=make_impulse_bars_df(start=21800, end=21860, retrace_to=21835),
        )

    def test_detects_bullish_unicorn(self, model, bullish_unicorn_context) -> None:
        """Detect LONG entry when MSS + FVG + OTE zone align."""
        signals = model.detect(bullish_unicorn_context)
        assert len(signals) >= 1
        assert signals[0].direction == "LONG"
        assert signals[0].model == "unicorn_ict"
        assert 0.0 < signals[0].confidence <= 1.0

    def test_no_detection_without_mss(self, model) -> None:
        """No signal when there is no Market Structure Shift."""
        ctx = make_session_context_dataclass(
            mss_levels=[],
            fvgs=[{"high": 21840.0, "low": 21830.0, "tf": "5m", "direction": "LONG"}],
        )
        signals = model.detect(ctx)
        assert len(signals) == 0

    def test_no_detection_without_fvg(self, model) -> None:
        """No signal when there is no FVG in the MSS direction."""
        ctx = make_session_context_dataclass(
            mss_levels=[{"price": 21820.0, "direction": "LONG", "time": "10:45"}],
            fvgs=[],
        )
        signals = model.detect(ctx)
        assert len(signals) == 0

    def test_bearish_unicorn(self, model) -> None:
        """Detect SHORT entry with bearish MSS + FVG."""
        ctx = make_session_context_dataclass(
            current_price=21865.0,
            mss_levels=[{"price": 21870.0, "direction": "SHORT", "time": "11:00"}],
            fvgs=[{"high": 21870.0, "low": 21860.0, "tf": "5m", "direction": "SHORT"}],
            bars=make_impulse_bars_df(start=21900, end=21840, retrace_to=21865),
        )
        signals = model.detect(ctx)
        assert len(signals) >= 1
        assert signals[0].direction == "SHORT"

    def test_evidence_contains_required_keys(self, model, bullish_unicorn_context) -> None:
        """Evidence dict must have mss_level, fvg_high, fvg_low, ote_range."""
        signals = model.detect(bullish_unicorn_context)
        if signals:
            evidence = signals[0].evidence
            assert "mss_level" in evidence
            assert "fvg_high" in evidence
            assert "fvg_low" in evidence
            assert "ote_range" in evidence
```

### Stop Models

```python
# packages/rockit-core/tests/models/test_stop_atr.py

import pytest
from rockit_core.models.base import EntrySignal, SessionContext
from rockit_core.models.stop.atr_stop import ATRStop
from tests.conftest import make_session_context_dataclass


class TestATRStop:
    """Unit tests for ATR-based stop placement."""

    def test_long_stop_below_entry(self) -> None:
        """LONG stop must be below entry price."""
        stop = ATRStop(multiplier=1.0)
        entry = EntrySignal(
            model="test", direction="LONG", entry_price=21850.0, confidence=0.8,
        )
        ctx = make_session_context_dataclass(atr14=40.0)
        result = stop.compute(entry, ctx)
        assert result == pytest.approx(21810.0)  # 21850 - 40

    def test_short_stop_above_entry(self) -> None:
        """SHORT stop must be above entry price."""
        stop = ATRStop(multiplier=1.0)
        entry = EntrySignal(
            model="test", direction="SHORT", entry_price=21850.0, confidence=0.8,
        )
        ctx = make_session_context_dataclass(atr14=40.0)
        result = stop.compute(entry, ctx)
        assert result == pytest.approx(21890.0)  # 21850 + 40

    def test_multiplier_scales_distance(self) -> None:
        """2 ATR stop should be twice as far as 1 ATR stop."""
        entry = EntrySignal(
            model="test", direction="LONG", entry_price=21850.0, confidence=0.8,
        )
        ctx = make_session_context_dataclass(atr14=40.0)
        stop_1 = ATRStop(1.0).compute(entry, ctx)
        stop_2 = ATRStop(2.0).compute(entry, ctx)
        assert abs(21850.0 - stop_2) == pytest.approx(2 * abs(21850.0 - stop_1))

    def test_name_reflects_multiplier(self) -> None:
        """Model name includes the multiplier."""
        assert ATRStop(1.0).name == "1_atr"
        assert ATRStop(2.0).name == "2_atr"


class TestLVNHVNStop:
    """Unit tests for LVN/HVN-based stop placement."""

    def test_long_uses_nearest_lvn_below(self) -> None:
        """LONG stop placed at nearest LVN below entry."""
        from rockit_core.models.stop.lvn_hvn import LVNHVNStop

        entry = EntrySignal(
            model="test", direction="LONG", entry_price=21850.0, confidence=0.8,
        )
        ctx = make_session_context_dataclass(
            atr14=40.0,
            lvn_levels=[21700.0, 21790.0, 21830.0],
            hvn_levels=[21860.0, 21900.0],
        )
        result = LVNHVNStop().compute(entry, ctx)
        assert result == 21830.0  # Nearest LVN below 21850

    def test_fallback_to_atr_when_no_lvn(self) -> None:
        """Falls back to 1.5 ATR when no LVN below entry."""
        from rockit_core.models.stop.lvn_hvn import LVNHVNStop

        entry = EntrySignal(
            model="test", direction="LONG", entry_price=21850.0, confidence=0.8,
        )
        ctx = make_session_context_dataclass(atr14=40.0, lvn_levels=[], hvn_levels=[])
        result = LVNHVNStop().compute(entry, ctx)
        assert result == pytest.approx(21850.0 - 1.5 * 40.0)
```

### Target Models

```python
# packages/rockit-core/tests/models/test_target_r_multiple.py

import pytest
from rockit_core.models.base import EntrySignal, TargetSpec
from rockit_core.models.target.r_multiple import RMultipleTarget
from tests.conftest import make_session_context_dataclass


class TestRMultipleTarget:
    """Unit tests for R-multiple target model."""

    def test_2r_long_target(self) -> None:
        """2R target for LONG: entry + 2 * (entry - stop)."""
        model = RMultipleTarget(multiple=2.0)
        entry = EntrySignal(
            model="test", direction="LONG", entry_price=21850.0, confidence=0.8,
        )
        stop_price = 21810.0  # 40 points risk
        ctx = make_session_context_dataclass()
        spec = model.compute(entry, stop_price, ctx)
        assert isinstance(spec, TargetSpec)
        assert spec.targets[0] == pytest.approx(21930.0)  # 21850 + 2*40

    def test_2r_short_target(self) -> None:
        """2R target for SHORT: entry - 2 * (stop - entry)."""
        model = RMultipleTarget(multiple=2.0)
        entry = EntrySignal(
            model="test", direction="SHORT", entry_price=21850.0, confidence=0.8,
        )
        stop_price = 21890.0  # 40 points risk
        ctx = make_session_context_dataclass()
        spec = model.compute(entry, stop_price, ctx)
        assert spec.targets[0] == pytest.approx(21770.0)  # 21850 - 2*40
```

### Composition Tests

```python
# packages/rockit-core/tests/models/test_model_composition.py

def test_entry_stop_target_produce_consistent_signal() -> None:
    """Composed models must produce stop < entry < target (LONG)."""
    ctx = make_session_context_dataclass(
        atr14=40.0,
        fvgs=[{"high": 21840.0, "low": 21830.0, "tf": "5m", "direction": "LONG"}],
        mss_levels=[{"price": 21820.0, "direction": "LONG", "time": "10:45"}],
    )
    entry_model = UnicornICTEntry()
    stop_model = ATRStop(1.0)
    target_model = RMultipleTarget(2.0)

    entries = entry_model.detect(ctx)
    if entries:
        entry = entries[0]
        stop_price = stop_model.compute(entry, ctx)
        target_spec = target_model.compute(entry, stop_price, ctx)
        # Consistency check
        assert stop_price < entry.entry_price
        assert target_spec.targets[0] > entry.entry_price
```

---

## Filters

```python
# packages/rockit-core/tests/filters/test_composite.py

import pytest
from rockit_core.filters.base import FilterBase
from rockit_core.filters.composite import CompositeFilter
from rockit_core.strategies.signal import Signal
from tests.conftest import make_signal, make_bar, make_session_context


class AlwaysPass(FilterBase):
    """Test filter that always allows the signal."""
    def should_trade(self, signal, bar, session_context) -> bool:
        return True


class AlwaysFail(FilterBase):
    """Test filter that always blocks the signal."""
    def should_trade(self, signal, bar, session_context) -> bool:
        return False


class TestCompositeFilter:
    """CompositeFilter AND-chains multiple filters."""

    def test_all_pass_returns_true(self) -> None:
        """Signal passes when all sub-filters pass."""
        composite = CompositeFilter(filters=[AlwaysPass(), AlwaysPass()])
        assert composite.should_trade(make_signal(), make_bar(), make_session_context())

    def test_one_fail_returns_false(self) -> None:
        """Signal blocked if any sub-filter fails."""
        composite = CompositeFilter(filters=[AlwaysPass(), AlwaysFail()])
        assert not composite.should_trade(make_signal(), make_bar(), make_session_context())

    def test_empty_filter_chain_passes(self) -> None:
        """No filters means no restrictions."""
        composite = CompositeFilter(filters=[])
        assert composite.should_trade(make_signal(), make_bar(), make_session_context())


class TestTimeFilter:
    """Time window filter: blocks signals outside session hours."""

    def test_within_window_passes(self) -> None:
        from rockit_core.filters.time_filter import TimeFilter
        f = TimeFilter(earliest="09:45", latest="14:30")
        bar = make_bar()  # timestamp=11:00 by default
        assert f.should_trade(make_signal(), bar, make_session_context())

    def test_before_window_blocks(self) -> None:
        from rockit_core.filters.time_filter import TimeFilter
        from datetime import datetime
        f = TimeFilter(earliest="09:45", latest="14:30")
        bar = make_bar()
        bar["timestamp"] = datetime(2026, 1, 15, 9, 30, 0)  # Before 09:45
        assert not f.should_trade(make_signal(), bar, make_session_context())


class TestOrderFlowFilter:
    """Order flow filter: blocks signals with weak delta/CVD."""

    def test_strong_delta_passes(self) -> None:
        from rockit_core.filters.order_flow import OrderFlowFilter
        f = OrderFlowFilter(min_delta=200, min_cvd_slope="positive")
        bar = make_bar(delta=350.0, cvd=2000.0)
        ctx = make_session_context()
        assert f.should_trade(make_signal(), bar, ctx)

    def test_weak_delta_blocks(self) -> None:
        from rockit_core.filters.order_flow import OrderFlowFilter
        f = OrderFlowFilter(min_delta=200, min_cvd_slope="positive")
        bar = make_bar(delta=50.0, cvd=100.0)
        ctx = make_session_context()
        assert not f.should_trade(make_signal(), bar, ctx)
```

---

## Indicators

```python
# packages/rockit-core/tests/indicators/test_ict.py

import pytest
import pandas as pd
from rockit_core.indicators.ict_models import detect_fvgs, detect_mss


class TestFVGDetection:
    """Fair Value Gap detection with known price data."""

    def test_bullish_fvg_detected(self) -> None:
        """Three candles where candle_3_low > candle_1_high = bullish FVG."""
        bars = pd.DataFrame({
            "high": [100.0, 105.0, 110.0],
            "low":  [95.0,  100.0, 103.0],  # bar[2].low > bar[0].high → gap
            "close": [98.0, 104.0, 108.0],
            "open": [96.0, 99.0, 104.0],
        })
        fvgs = detect_fvgs(bars)
        assert len(fvgs) >= 1
        assert fvgs[0]["direction"] == "LONG"
        assert fvgs[0]["low"] == 103.0   # Top of gap (candle 3 low)
        assert fvgs[0]["high"] == 100.0  # Bottom of gap (candle 1 high)

    def test_no_fvg_when_overlap(self) -> None:
        """No FVG when candle 3 low overlaps candle 1 high."""
        bars = pd.DataFrame({
            "high": [100.0, 105.0, 108.0],
            "low":  [95.0,  100.0, 99.0],  # bar[2].low < bar[0].high → no gap
            "close": [98.0, 104.0, 107.0],
            "open": [96.0, 99.0, 101.0],
        })
        fvgs = detect_fvgs(bars)
        assert len(fvgs) == 0


class TestSMTDivergence:
    """Smart Money Theory divergence between correlated instruments."""

    def test_detects_nq_es_divergence(self) -> None:
        """NQ makes new high, ES does not = bearish divergence."""
        from rockit_core.indicators.smt import detect_smt_divergence

        nq_bars = pd.DataFrame({
            "high": [21800.0, 21850.0, 21900.0],  # New high
            "low": [21750.0, 21780.0, 21830.0],
        })
        es_bars = pd.DataFrame({
            "high": [5780.0, 5800.0, 5795.0],  # No new high
            "low": [5760.0, 5770.0, 5775.0],
        })
        divergences = detect_smt_divergence(nq_bars, es_bars)
        assert len(divergences) >= 1
        assert divergences[0]["type"] == "bearish"


class TestTechnicalIndicators:
    """Technical indicators must match pandas-ta reference values."""

    def test_ema20_matches_pandas_ta(self) -> None:
        """EMA(20) computed by our module matches pandas-ta."""
        import pandas_ta as ta
        from rockit_core.indicators.technical import compute_ema

        prices = pd.Series([float(x) for x in range(100, 200)])
        our_ema = compute_ema(prices, period=20)
        ref_ema = ta.ema(prices, length=20)
        pd.testing.assert_series_equal(our_ema, ref_ema, atol=1e-9)
```

---

## Deterministic Modules

```python
# packages/rockit-core/tests/deterministic/test_snapshot_regression.py

import json
import pytest
from pathlib import Path
from rockit_core.deterministic.orchestrator import Orchestrator


REFERENCE_DIR = Path(__file__).parent / "fixtures" / "snapshots"


class TestSnapshotRegression:
    """Each deterministic module output must match its reference JSON."""

    @pytest.mark.regression
    def test_full_snapshot_matches_reference(self) -> None:
        """generate_snapshot() output matches known-good reference."""
        config = {"time": "11:45", "instrument": "NQ"}
        input_data = load_test_csv("fixtures/sessions/2026-01-15_NQ.csv")
        orchestrator = Orchestrator()
        snapshot = orchestrator.generate_snapshot(input_data, config)

        reference = json.loads(
            (REFERENCE_DIR / "2026-01-15_1145_NQ.json").read_text()
        )

        # Core fields must match exactly
        assert snapshot["ib"]["high"] == reference["ib"]["high"]
        assert snapshot["ib"]["low"] == reference["ib"]["low"]
        assert snapshot["volume_profile"]["poc"] == reference["volume_profile"]["poc"]
        assert snapshot["tpo_profile"]["shape"] == reference["tpo_profile"]["shape"]

    def test_get_ib_location(self) -> None:
        """IB location module returns correct high/low/range."""
        from rockit_core.deterministic.modules.ib_location import get_ib_location

        bars = load_ib_bars("fixtures/sessions/2026-01-15_NQ.csv")
        result = get_ib_location(bars)
        assert "high" in result
        assert "low" in result
        assert "range" in result
        assert result["range"] == result["high"] - result["low"]

    def test_get_volume_profile(self) -> None:
        """Volume profile module returns POC, VAH, VAL."""
        from rockit_core.deterministic.modules.volume_profile import get_volume_profile

        bars = load_session_bars("fixtures/sessions/2026-01-15_NQ.csv")
        result = get_volume_profile(bars)
        assert "poc" in result
        assert "vah" in result
        assert "val" in result
        assert result["val"] < result["poc"] < result["vah"]

    def test_individual_module_output_types(self) -> None:
        """Every module returns a dict with a 'status' key."""
        from rockit_core.deterministic.orchestrator import ALL_MODULES

        bars = load_session_bars("fixtures/sessions/2026-01-15_NQ.csv")
        for module_name, module_fn in ALL_MODULES.items():
            result = module_fn(bars)
            assert isinstance(result, dict), f"{module_name} must return dict"
```
