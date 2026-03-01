# Technical Design: Filter Framework

> **Package:** `rockit-core/filters/`
> **Type:** MIGRATE from BookMapOrderFlowStudies/filters/
> **Source files:** 7 files
> **Tests:** See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#filters)

---

## Purpose

Filters gate strategy signals before execution. A signal must pass ALL active filters to become a trade. Filters are stateless evaluators that inspect the signal, current bar, and session context. They integrate with YAML config for per-strategy threshold overrides and emit metrics for pass/block rate analysis.

---

## Source Files (Being Migrated)

| File | Class(es) | LOC | Destination | Type |
|------|----------|-----|-------------|------|
| `filters/base.py` | `FilterBase` | ~30 | `filters/base.py` | MIGRATE |
| `filters/composite.py` | `CompositeFilter` | ~40 | `filters/composite.py` | MIGRATE |
| `filters/order_flow_filter.py` | `DeltaFilter`, `CVDFilter`, `VolumeFilter` | ~120 | `filters/order_flow.py` | MIGRATE |
| `filters/regime_filter.py` | `RegimeFilter` | ~80 | `filters/regime.py` | MIGRATE |
| `filters/time_filter.py` | `TimeFilter` | ~60 | `filters/time.py` | MIGRATE |
| `filters/trend_filter.py` | `TrendFilter` | ~70 | `filters/trend.py` | MIGRATE |
| `filters/volatility_filter.py` | `VolatilityFilter` | ~80 | `filters/volatility.py` | MIGRATE |

---

## Interface: FilterBase

```python
# packages/rockit-core/src/rockit_core/filters/base.py

from abc import ABC, abstractmethod

import pandas as pd

from rockit_core.strategies.signal import Signal
from rockit_core.metrics import MetricsCollector, NullCollector


class FilterBase(ABC):
    """Abstract base for all signal filters.

    Source: BookMapOrderFlowStudies/filters/base.py
    Migration: MIGRATE — add name property and metrics parameter

    Contract:
    - Filters are stateless. Given the same inputs, they produce the same output.
    - should_trade() returns True to allow the signal, False to block it.
    - Filters never modify the signal — they only accept or reject.
    - All filters are AND-chained: signal must pass ALL filters.
    """

    def __init__(self, metrics: MetricsCollector | None = None):
        self._metrics = metrics or NullCollector()

    @property
    @abstractmethod
    def name(self) -> str:
        """Filter name for metrics and logging."""

    @abstractmethod
    def should_trade(
        self,
        signal: Signal,
        bar: pd.Series,
        session_context: dict,
    ) -> bool:
        """Evaluate whether a signal should proceed to execution.

        Args:
            signal: The Signal emitted by a strategy.
            bar: Current bar data (OHLCV + delta/CVD/indicators).
            session_context: Dict with ib_high, ib_low, day_type_confidence,
                             volume_profile, session_high, session_low, etc.

        Returns:
            True if the signal passes this filter, False to block.
        """
```

---

## Interface: CompositeFilter

```python
# packages/rockit-core/src/rockit_core/filters/composite.py

import pandas as pd

from rockit_core.strategies.signal import Signal
from rockit_core.filters.base import FilterBase
from rockit_core.metrics import MetricsCollector, MetricEvent, NullCollector


class CompositeFilter(FilterBase):
    """Chains multiple filters with AND logic.

    Source: BookMapOrderFlowStudies/filters/composite.py
    Migration: MIGRATE — add per-filter metrics emission

    All child filters must return True for the composite to pass.
    Short-circuits on first rejection for performance.
    """

    def __init__(
        self,
        filters: list[FilterBase],
        metrics: MetricsCollector | None = None,
    ):
        super().__init__(metrics)
        self._filters = filters

    @property
    def name(self) -> str:
        return "composite"

    def should_trade(
        self,
        signal: Signal,
        bar: pd.Series,
        session_context: dict,
    ) -> bool:
        """Evaluate all child filters. Short-circuits on first rejection."""
        from datetime import datetime

        for f in self._filters:
            passed = f.should_trade(signal, bar, session_context)
            ts = bar["timestamp"].isoformat() if hasattr(bar["timestamp"], "isoformat") else str(bar["timestamp"])

            if not passed:
                self._metrics.record(MetricEvent(
                    timestamp=ts,
                    layer="filter",
                    component=f.name,
                    metric="filter_blocked",
                    value=1.0,
                    context={
                        "strategy": signal.strategy_name,
                        "direction": signal.direction,
                    },
                ))
                return False

            self._metrics.record(MetricEvent(
                timestamp=ts,
                layer="filter",
                component=f.name,
                metric="filter_passed",
                value=1.0,
                context={
                    "strategy": signal.strategy_name,
                    "direction": signal.direction,
                },
            ))

        return True

    @property
    def filter_count(self) -> int:
        return len(self._filters)
```

---

## Interface: OrderFlowFilter

```python
# packages/rockit-core/src/rockit_core/filters/order_flow.py

import pandas as pd

from rockit_core.strategies.signal import Signal
from rockit_core.filters.base import FilterBase


class OrderFlowFilter(FilterBase):
    """Order flow quality gate combining delta, CVD, and volume checks.

    Source: BookMapOrderFlowStudies/filters/order_flow_filter.py
    Migration: MIGRATE — consolidate DeltaFilter/CVDFilter/VolumeFilter into one class
               with configurable thresholds from YAML

    Checks:
    1. Delta alignment: bar delta must align with signal direction
    2. CVD slope: cumulative volume delta trend must support direction
    3. Volume threshold: bar volume must exceed minimum
    """

    def __init__(
        self,
        min_delta: float = 100.0,
        min_cvd_slope: str = "any",        # "positive" | "negative" | "any"
        min_volume: float = 0.0,
        metrics: "MetricsCollector | None" = None,
    ):
        super().__init__(metrics)
        self.min_delta = min_delta
        self.min_cvd_slope = min_cvd_slope
        self.min_volume = min_volume

    @property
    def name(self) -> str:
        return "order_flow"

    def should_trade(
        self,
        signal: Signal,
        bar: pd.Series,
        session_context: dict,
    ) -> bool:
        """Check order flow supports signal direction.

        For LONG signals:
        - bar delta must be >= min_delta (positive)
        - CVD slope must be positive (if min_cvd_slope == "positive")

        For SHORT signals:
        - bar delta must be <= -min_delta (negative)
        - CVD slope must be negative (if min_cvd_slope == "negative")
        """
        delta = bar.get("delta", 0.0)
        volume = bar.get("volume", 0.0)

        # Volume check
        if self.min_volume > 0 and volume < self.min_volume:
            return False

        # Delta alignment check
        if signal.direction == "LONG" and delta < self.min_delta:
            return False
        if signal.direction == "SHORT" and delta > -self.min_delta:
            return False

        # CVD slope check
        if self.min_cvd_slope != "any":
            cvd_trend = session_context.get("cvd_trend", "flat")
            if self.min_cvd_slope == "positive" and cvd_trend != "up":
                return False
            if self.min_cvd_slope == "negative" and cvd_trend != "down":
                return False

        return True
```

---

## Interface: RegimeFilter

```python
# packages/rockit-core/src/rockit_core/filters/regime.py

import pandas as pd

from rockit_core.strategies.signal import Signal
from rockit_core.filters.base import FilterBase


class RegimeFilter(FilterBase):
    """Market regime classification gate.

    Source: BookMapOrderFlowStudies/filters/regime_filter.py
    Migration: MIGRATE — add YAML config for required_regime

    Blocks signals when the market regime does not match the required
    regime for the strategy. Regime is determined from session_context.

    Regimes: "trending" | "balance" | "rotational" | "any"
    """

    def __init__(
        self,
        required_regime: str = "any",
        metrics: "MetricsCollector | None" = None,
    ):
        super().__init__(metrics)
        self.required_regime = required_regime

    @property
    def name(self) -> str:
        return "regime"

    def should_trade(
        self,
        signal: Signal,
        bar: pd.Series,
        session_context: dict,
    ) -> bool:
        """Check if current market regime matches required regime.

        Reads regime from session_context["market_regime"].
        Returns True if required_regime is "any" or matches current.
        """
        if self.required_regime == "any":
            return True

        current_regime = session_context.get("market_regime", "unknown")
        return current_regime == self.required_regime
```

---

## Interface: TimeFilter

```python
# packages/rockit-core/src/rockit_core/filters/time.py

import pandas as pd

from rockit_core.strategies.signal import Signal
from rockit_core.filters.base import FilterBase


class TimeFilter(FilterBase):
    """Session time window restriction.

    Source: BookMapOrderFlowStudies/filters/time_filter.py
    Migration: MIGRATE — add YAML config for earliest/latest

    Blocks signals outside the allowed time window.
    Times are in ET (Eastern Time), matching RTH session.
    """

    def __init__(
        self,
        earliest: str = "09:30",
        latest: str = "15:30",
        metrics: "MetricsCollector | None" = None,
    ):
        """
        Args:
            earliest: Earliest allowed signal time, "HH:MM" ET.
            latest: Latest allowed signal time, "HH:MM" ET.
        """
        super().__init__(metrics)
        self.earliest = earliest
        self.latest = latest

    @property
    def name(self) -> str:
        return "time"

    def should_trade(
        self,
        signal: Signal,
        bar: pd.Series,
        session_context: dict,
    ) -> bool:
        """Check if signal timestamp is within allowed time window.

        Compares bar timestamp's time component against earliest/latest.
        """
        bar_time = bar["timestamp"]
        if hasattr(bar_time, "strftime"):
            time_str = bar_time.strftime("%H:%M")
        else:
            time_str = str(bar_time)[-8:-3]  # extract HH:MM from string

        return self.earliest <= time_str <= self.latest
```

---

## Interface: TrendFilter

```python
# packages/rockit-core/src/rockit_core/filters/trend.py

import pandas as pd

from rockit_core.strategies.signal import Signal
from rockit_core.filters.base import FilterBase


class TrendFilter(FilterBase):
    """Trend alignment confirmation.

    Source: BookMapOrderFlowStudies/filters/trend_filter.py
    Migration: MIGRATE as-is

    Blocks signals that fight the prevailing trend:
    - LONG signals require price above EMA20 and EMA50
    - SHORT signals require price below EMA20 and EMA50
    - Can be configured for strict (above both) or loose (above either)
    """

    def __init__(
        self,
        mode: str = "strict",          # "strict" | "loose"
        metrics: "MetricsCollector | None" = None,
    ):
        super().__init__(metrics)
        self.mode = mode

    @property
    def name(self) -> str:
        return "trend"

    def should_trade(
        self,
        signal: Signal,
        bar: pd.Series,
        session_context: dict,
    ) -> bool:
        """Check if signal aligns with EMA trend.

        Strict mode: price must be above both EMA20 and EMA50 for LONG.
        Loose mode: price must be above at least one EMA for LONG.
        """
        price = bar["close"]
        ema20 = bar.get("ema20", 0.0)
        ema50 = bar.get("ema50", 0.0)

        if signal.direction == "LONG":
            if self.mode == "strict":
                return price > ema20 and price > ema50
            return price > ema20 or price > ema50
        else:
            if self.mode == "strict":
                return price < ema20 and price < ema50
            return price < ema20 or price < ema50
```

---

## Interface: VolatilityFilter

```python
# packages/rockit-core/src/rockit_core/filters/volatility.py

import pandas as pd

from rockit_core.strategies.signal import Signal
from rockit_core.filters.base import FilterBase


class VolatilityFilter(FilterBase):
    """IB range and ATR-based volatility gate.

    Source: BookMapOrderFlowStudies/filters/volatility_filter.py
    Migration: MIGRATE — add YAML config for thresholds

    Blocks signals when volatility is too low or too high:
    - min_ib_range: Minimum IB range in points (too narrow = no room)
    - max_ib_range: Maximum IB range in points (too wide = excess risk)
    - min_atr: Minimum ATR(14) threshold
    - max_atr: Maximum ATR(14) threshold
    """

    def __init__(
        self,
        min_ib_range: float = 0.0,
        max_ib_range: float = float("inf"),
        min_atr: float = 0.0,
        max_atr: float = float("inf"),
        metrics: "MetricsCollector | None" = None,
    ):
        super().__init__(metrics)
        self.min_ib_range = min_ib_range
        self.max_ib_range = max_ib_range
        self.min_atr = min_atr
        self.max_atr = max_atr

    @property
    def name(self) -> str:
        return "volatility"

    def should_trade(
        self,
        signal: Signal,
        bar: pd.Series,
        session_context: dict,
    ) -> bool:
        """Check if volatility is within acceptable range.

        Reads ib_range from session_context and atr14 from bar or context.
        """
        ib_range = session_context.get("ib_range", 0.0)
        atr = session_context.get("atr14", bar.get("atr14", 0.0))

        if ib_range < self.min_ib_range:
            return False
        if ib_range > self.max_ib_range:
            return False
        if atr < self.min_atr:
            return False
        if atr > self.max_atr:
            return False

        return True
```

---

## YAML Config Integration

```python
# packages/rockit-core/src/rockit_core/filters/__init__.py

from rockit_core.filters.base import FilterBase
from rockit_core.filters.composite import CompositeFilter
from rockit_core.filters.order_flow import OrderFlowFilter
from rockit_core.filters.regime import RegimeFilter
from rockit_core.filters.time import TimeFilter
from rockit_core.filters.trend import TrendFilter
from rockit_core.filters.volatility import VolatilityFilter
from rockit_core.metrics import MetricsCollector


FILTER_REGISTRY: dict[str, type[FilterBase]] = {
    "order_flow": OrderFlowFilter,
    "regime": RegimeFilter,
    "time": TimeFilter,
    "trend": TrendFilter,
    "volatility": VolatilityFilter,
}


def build_filters_from_config(
    filter_config: dict,
    metrics: MetricsCollector | None = None,
) -> CompositeFilter:
    """Build a CompositeFilter from YAML config dict.

    Args:
        filter_config: Dict from strategies.yaml "filters" section.
            Example: {"order_flow": {"min_delta": 200}, "time": {"earliest": "09:45"}}
        metrics: Optional metrics collector.

    Returns:
        CompositeFilter chaining all configured filters.
    """
    filters: list[FilterBase] = []

    for filter_name, params in filter_config.items():
        cls = FILTER_REGISTRY.get(filter_name)
        if cls is None:
            raise ValueError(f"Unknown filter: {filter_name}. Available: {list(FILTER_REGISTRY.keys())}")
        if isinstance(params, dict):
            filters.append(cls(**params, metrics=metrics))
        else:
            filters.append(cls(metrics=metrics))

    return CompositeFilter(filters=filters, metrics=metrics)
```

---

## Data Flow

```
Strategy.on_bar() returns Signal
    │
    ▼
BacktestEngine._apply_filters(signal, bar, context)
    │
    ▼
CompositeFilter.should_trade(signal, bar, context)
    │
    ├──► OrderFlowFilter.should_trade()
    │       ├── Check delta alignment with direction
    │       ├── Check CVD slope
    │       └── Check volume threshold
    │
    ├──► RegimeFilter.should_trade()
    │       └── Check market_regime matches required
    │
    ├──► TimeFilter.should_trade()
    │       └── Check bar time within [earliest, latest]
    │
    ├──► TrendFilter.should_trade()
    │       └── Check price vs EMA20/EMA50 alignment
    │
    └──► VolatilityFilter.should_trade()
            └── Check IB range and ATR within bounds
    │
    ▼
True (all passed) ──► proceed to trade models and execution
False (any blocked) ──► signal discarded, metric emitted
```

---

## Dependencies

| This module | Depends on |
|-------------|-----------|
| `filters/base.py` | `strategies/signal.py`, `metrics/` |
| `filters/composite.py` | `filters/base.py`, `metrics/event.py` |
| `filters/order_flow.py` | `filters/base.py` |
| `filters/regime.py` | `filters/base.py` |
| `filters/time.py` | `filters/base.py` |
| `filters/trend.py` | `filters/base.py` |
| `filters/volatility.py` | `filters/base.py` |
| `filters/__init__.py` | All filter classes, `metrics/` |

---

## Metrics Emitted

| Metric | Layer | When |
|--------|-------|------|
| `filter.filter_passed` | filter | Signal passes a specific filter |
| `filter.filter_blocked` | filter | Signal blocked by a specific filter |

Context fields on all filter metrics: `strategy` (name), `direction` (LONG/SHORT).

Use `metrics/queries.py:filter_pass_rates()` to analyze which filters block the most signals and for which strategies.

---

## Migration Notes

1. **File rename.** Source files use `_filter` suffix (e.g., `order_flow_filter.py`). Destination drops the suffix to `order_flow.py` since the parent directory is already `filters/`.

2. **DeltaFilter, CVDFilter, VolumeFilter consolidated.** In the original code, these are three separate classes. In the migration, they merge into a single `OrderFlowFilter` with three configurable thresholds. This simplifies YAML config and reduces the number of filter objects in the chain.

3. **Constructor parameters from YAML.** All filter thresholds that were previously hardcoded become constructor parameters that are set from `strategies.yaml` via `build_filters_from_config()`.

4. **Metrics are new.** The original filters had no metrics. The `MetricsCollector` parameter is additive.

5. **No filter logic changes.** The actual condition checks (delta > threshold, time in window, etc.) are migrated as-is.

---

## Test Contract

1. **FilterBase contract test** — verify abstract methods raise NotImplementedError
2. **Per-filter unit tests** — each filter tested with signals that should pass and should block
3. **CompositeFilter AND logic** — verify short-circuit behavior, all pass, first blocks, last blocks
4. **OrderFlowFilter direction alignment** — LONG needs positive delta, SHORT needs negative
5. **TimeFilter boundary cases** — exactly at earliest, exactly at latest, one minute before/after
6. **VolatilityFilter edge cases** — IB range exactly at min/max threshold
7. **build_filters_from_config** — build from YAML dict, verify correct filter types and params
8. **Metrics emission** — verify pass/block metrics are recorded with correct context

See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#filters)
