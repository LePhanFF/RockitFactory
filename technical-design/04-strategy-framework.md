# Technical Design: Strategy Framework

> **Package:** `rockit-core/strategies/`
> **Type:** MIGRATE from BookMapOrderFlowStudies/strategy/ + EXTEND with YAML config
> **Source files:** 20 files, ~3,500 LOC
> **Tests:** See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md)

---

## Purpose

The strategy framework is the core of Rockit. Strategies evaluate market data bar-by-bar and emit `Signal` objects. They never manage positions, execute trades, or interact with external systems. The pattern: **strategies emit signals, the engine handles everything else.**

---

## Source Files (Being Migrated)

| File | LOC | Destination | Type |
|------|-----|-------------|------|
| `strategy/base.py` | ~50 | `strategies/base.py` | MIGRATE |
| `strategy/signal.py` | ~50 | `strategies/signal.py` | EXTEND |
| `strategy/day_type.py` | ~80 | `strategies/day_type.py` | MIGRATE |
| `strategy/day_confidence.py` | ~200 | `strategies/day_confidence.py` | MIGRATE |
| `strategy/trend_bull.py` | ~150 | `strategies/trend_bull.py` | MIGRATE |
| `strategy/trend_bear.py` | ~130 | `strategies/trend_bear.py` | MIGRATE |
| `strategy/super_trend_bull.py` | ~120 | `strategies/super_trend_bull.py` | MIGRATE |
| `strategy/super_trend_bear.py` | ~100 | `strategies/super_trend_bear.py` | MIGRATE |
| `strategy/p_day.py` | ~170 | `strategies/p_day.py` | MIGRATE |
| `strategy/b_day.py` | ~150 | `strategies/b_day.py` | MIGRATE |
| `strategy/neutral_day.py` | ~20 | `strategies/neutral_day.py` | MIGRATE |
| `strategy/pm_morph.py` | ~130 | `strategies/pm_morph.py` | MIGRATE |
| `strategy/morph_to_trend.py` | ~100 | `strategies/morph_to_trend.py` | MIGRATE |
| `strategy/orb_enhanced.py` | ~581 | `strategies/orb_enhanced.py` | MIGRATE |
| `strategy/orb_vwap_breakout.py` | ~200 | `strategies/orb_vwap_breakout.py` | MIGRATE |
| `strategy/ema_trend_follow.py` | ~150 | `strategies/ema_trend_follow.py` | MIGRATE |
| `strategy/liquidity_sweep.py` | ~180 | `strategies/liquidity_sweep.py` | MIGRATE |
| `strategy/eighty_percent_rule.py` | ~150 | `strategies/eighty_percent_rule.py` | MIGRATE |
| `strategy/mean_reversion_vwap.py` | ~120 | `strategies/mean_reversion_vwap.py` | MIGRATE |

---

## Interface: StrategyBase (MIGRATE)

```python
# packages/rockit-core/src/rockit_core/strategies/base.py

from abc import ABC, abstractmethod
from typing import Optional, List
import pandas as pd

from rockit_core.strategies.signal import Signal
from rockit_core.metrics import MetricsCollector, NullCollector


class StrategyBase(ABC):
    """Abstract base for all trading strategies.

    Contract:
    - Strategies emit Signal objects, they NEVER manage positions.
    - on_session_start() is called once after IB (Initial Balance) forms.
    - on_bar() is called for each subsequent bar.
    - Return Signal from on_bar() to signal an entry.
    - Return None from on_bar() to indicate no signal.

    Source: BookMapOrderFlowStudies/strategy/base.py
    Migration: MIGRATE — add metrics parameter, no logic changes
    """

    def __init__(self, metrics: MetricsCollector | None = None):
        self._metrics = metrics or NullCollector()

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for reporting. E.g., 'TrendDayBull'."""

    @property
    @abstractmethod
    def applicable_day_types(self) -> list[str]:
        """DayType values this strategy trades.

        Return empty list to trade all day types.
        E.g., ['trend_up', 'super_trend_up'] for TrendDayBull.
        """

    @abstractmethod
    def on_session_start(
        self,
        session_date: str,
        ib_high: float,
        ib_low: float,
        ib_range: float,
        session_context: dict,
    ) -> None:
        """Called once per session after IB formation (10:30 ET).

        Use this to store IB levels and compute session-level state.

        Args:
            session_date: "YYYY-MM-DD"
            ib_high: Initial Balance high price
            ib_low: Initial Balance low price
            ib_range: ib_high - ib_low in points
            session_context: Dict containing:
                - atr14: 14-period ATR
                - vwap: Current VWAP
                - day_type_confidence: DayTypeConfidence object
                - prior_day: Dict with prev session high/low/close/VAH/VAL/POC
                - volume_profile: Dict with current POC/VAH/VAL
        """

    @abstractmethod
    def on_bar(
        self,
        bar: pd.Series,
        bar_index: int,
        session_context: dict,
    ) -> Signal | None:
        """Called for each bar after IB.

        Args:
            bar: pd.Series with columns:
                - open, high, low, close
                - volume
                - delta (buy volume - sell volume)
                - cvd (cumulative volume delta)
                - vwap
                - ema20, ema50, ema200
                - rsi14
                - atr14
                - timestamp (datetime)
            bar_index: 0-based index within post-IB bars
            session_context: Same dict as on_session_start, plus:
                - session_high: Running session high
                - session_low: Running session low
                - day_type_confidence: Updated DayTypeConfidence

        Returns:
            Signal if entry conditions met, None otherwise.
        """

    def on_session_end(self, session_date: str) -> None:
        """Optional cleanup. Called at session end (16:00 ET)."""
        pass
```

---

## Interface: Signal (MIGRATE + EXTEND)

```python
# packages/rockit-core/src/rockit_core/strategies/signal.py

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Signal:
    """Signal emitted by a strategy. NOT a trade — just an intent.

    The engine decides whether to fill this signal based on:
    - Filter chain (order flow, regime, time, volatility)
    - Position limits (max contracts, max daily loss)
    - Execution model (slippage, commission)

    Source: BookMapOrderFlowStudies/strategy/signal.py
    Migration: MIGRATE + add entry_model/stop_model/target_model fields
    """

    # Timing
    timestamp: datetime

    # Direction
    direction: str              # 'LONG' or 'SHORT'

    # Prices (set by strategy or by trade models)
    entry_price: float
    stop_price: float
    target_price: float

    # Identity
    strategy_name: str
    setup_type: str             # e.g., 'IBH_RETEST', 'EMA_PULLBACK', 'VAH_FADE'
    day_type: str               # e.g., 'trend_up', 'p_day', 'b_day'

    # Confidence
    confidence: str = 'medium'  # 'low', 'medium', 'high'
    trend_strength: str = ""    # 'weak', 'moderate', 'strong', 'super'

    # Pyramiding
    pyramid_level: int = 0

    # Trade model references (NEW — for composable entry/stop/target)
    entry_model: str = ""       # e.g., 'unicorn_ict', 'orderflow_cvd'
    stop_model: str = ""        # e.g., '1_atr', 'lvn_hvn'
    target_model: str = ""      # e.g., '2r', '4h_gap_fill'

    # Arbitrary metadata
    metadata: dict = field(default_factory=dict)

    @property
    def risk_points(self) -> float:
        """Distance from entry to stop in points."""
        if self.direction == 'LONG':
            return self.entry_price - self.stop_price
        return self.stop_price - self.entry_price

    @property
    def reward_points(self) -> float:
        """Distance from entry to target in points."""
        if self.direction == 'LONG':
            return self.target_price - self.entry_price
        return self.entry_price - self.target_price

    @property
    def risk_reward_ratio(self) -> float:
        """Reward / Risk ratio."""
        risk = self.risk_points
        if risk <= 0:
            return 0.0
        return self.reward_points / risk
```

---

## Interface: DayType (MIGRATE)

```python
# packages/rockit-core/src/rockit_core/strategies/day_type.py

from enum import Enum


class DayType(Enum):
    """Dalton Market Profile day type classification.

    Source: BookMapOrderFlowStudies/strategy/day_type.py
    Migration: MIGRATE as-is
    """
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    SUPER_TREND_UP = "super_trend_up"
    SUPER_TREND_DOWN = "super_trend_down"
    P_DAY = "p_day"
    B_DAY = "b_day"
    NEUTRAL = "neutral"
    PM_MORPH = "pm_morph"
    MORPH_TO_TREND = "morph_to_trend"


class TrendStrength(Enum):
    """IB extension multiple classification.

    WEAK: < 0.5x IB range extension
    MODERATE: 0.5-1.0x
    STRONG: 1.0-2.0x
    SUPER: > 2.0x
    """
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    SUPER = "super"


def classify_trend_strength(ib_extension_multiple: float) -> TrendStrength:
    """Classify trend strength based on how far price extends beyond IB.

    Args:
        ib_extension_multiple: (current_extension / ib_range)

    Returns:
        TrendStrength enum value
    """
    if ib_extension_multiple >= 2.0:
        return TrendStrength.SUPER
    elif ib_extension_multiple >= 1.0:
        return TrendStrength.STRONG
    elif ib_extension_multiple >= 0.5:
        return TrendStrength.MODERATE
    return TrendStrength.WEAK


def classify_day_type(
    ib_high: float,
    ib_low: float,
    current_price: float,
    ib_direction: str = 'INSIDE',
    trend_strength: TrendStrength = TrendStrength.WEAK,
) -> DayType:
    """Classify the current day type based on price action vs IB.

    Args:
        ib_high: Initial Balance high
        ib_low: Initial Balance low
        current_price: Current price
        ib_direction: 'UP', 'DOWN', or 'INSIDE'
        trend_strength: Current trend strength classification

    Returns:
        DayType enum value
    """
    ...  # Implementation migrated from BookMapOrderFlowStudies
```

---

## Interface: DayTypeConfidenceScorer (MIGRATE)

```python
# packages/rockit-core/src/rockit_core/strategies/day_confidence.py

from dataclasses import dataclass, field


@dataclass
class DayTypeConfidence:
    """Bar-by-bar Dalton checklist confidence for each day type.

    Confidence values range 0.0 to 1.0 based on how many checklist
    items are satisfied for each day type.

    Source: BookMapOrderFlowStudies/strategy/day_confidence.py
    """
    trend_bull: float = 0.0
    trend_bear: float = 0.0
    p_day_bull: float = 0.0
    p_day_bear: float = 0.0
    b_day: float = 0.0
    neutral: float = 0.0
    checklist: dict[str, dict[str, bool]] = field(default_factory=dict)

    @property
    def best_type(self) -> str:
        """Day type with highest confidence."""
        scores = {
            'trend_bull': self.trend_bull,
            'trend_bear': self.trend_bear,
            'p_day_bull': self.p_day_bull,
            'p_day_bear': self.p_day_bear,
            'b_day': self.b_day,
            'neutral': self.neutral,
        }
        return max(scores, key=scores.get)

    @property
    def best_confidence(self) -> float:
        """Highest confidence score across all day types."""
        return max(
            self.trend_bull, self.trend_bear,
            self.p_day_bull, self.p_day_bear,
            self.b_day, self.neutral,
        )


class DayTypeConfidenceScorer:
    """Bar-by-bar day type confidence scorer using Dalton checklists.

    Called by the backtest engine on each bar to update confidence scores.
    Strategies use these scores to decide whether to signal.

    Source: BookMapOrderFlowStudies/strategy/day_confidence.py (~200 LOC)
    Migration: MIGRATE as-is
    """

    def on_session_start(
        self,
        ib_high: float,
        ib_low: float,
        ib_range: float,
        atr: float = 0.0,
    ) -> None:
        """Initialize scorer for new session."""
        ...

    def update(self, bar: pd.Series, bar_index: int) -> DayTypeConfidence:
        """Update confidence scores with new bar data.

        Called by the engine for each post-IB bar. Returns updated
        DayTypeConfidence that strategies can read from session_context.

        Args:
            bar: OHLCV bar with delta, CVD, etc.
            bar_index: 0-based post-IB bar index

        Returns:
            Updated DayTypeConfidence with all scores recalculated.
        """
        ...
```

---

## Strategy Registry (NEW)

```python
# packages/rockit-core/src/rockit_core/strategies/__init__.py

from rockit_core.strategies.trend_bull import TrendDayBull
from rockit_core.strategies.trend_bear import TrendDayBear
from rockit_core.strategies.super_trend_bull import SuperTrendBull
from rockit_core.strategies.super_trend_bear import SuperTrendBear
from rockit_core.strategies.p_day import PDayStrategy
from rockit_core.strategies.b_day import BDayStrategy
from rockit_core.strategies.neutral_day import NeutralDayStrategy
from rockit_core.strategies.pm_morph import PMMorphStrategy
from rockit_core.strategies.morph_to_trend import MorphToTrendStrategy
from rockit_core.strategies.orb_enhanced import ORBEnhanced
from rockit_core.strategies.orb_vwap_breakout import ORBVwapBreakout
from rockit_core.strategies.ema_trend_follow import EMATrendFollow
from rockit_core.strategies.liquidity_sweep import LiquiditySweep
from rockit_core.strategies.eighty_percent_rule import EightyPercentRule
from rockit_core.strategies.mean_reversion_vwap import MeanReversionVWAP

# All available strategies
ALL_STRATEGIES: dict[str, type[StrategyBase]] = {
    "trend_bull": TrendDayBull,
    "trend_bear": TrendDayBear,
    "super_trend_bull": SuperTrendBull,
    "super_trend_bear": SuperTrendBear,
    "p_day": PDayStrategy,
    "b_day": BDayStrategy,
    "neutral_day": NeutralDayStrategy,
    "pm_morph": PMMorphStrategy,
    "morph_to_trend": MorphToTrendStrategy,
    "orb_enhanced": ORBEnhanced,
    "orb_vwap_breakout": ORBVwapBreakout,
    "ema_trend_follow": EMATrendFollow,
    "liquidity_sweep": LiquiditySweep,
    "eighty_percent_rule": EightyPercentRule,
    "mean_reversion_vwap": MeanReversionVWAP,
}

# Production-validated core portfolio
CORE_STRATEGIES: list[str] = [
    "trend_bull", "p_day", "b_day", "edge_fade",
    "ibh_sweep", "bear_accept", "or_reversal", "ib_retest",
]


def load_strategies_from_config(config_path: str) -> list[StrategyBase]:
    """Load and instantiate strategies from configs/strategies.yaml.

    Only instantiates strategies where enabled: true.
    Reads entry_model, stop_model, target_model from config and
    injects them into the strategy instance.

    Args:
        config_path: Path to strategies.yaml

    Returns:
        List of instantiated StrategyBase objects
    """
    ...
```

---

## YAML Strategy Configuration (NEW)

```yaml
# configs/strategies.yaml

strategies:
  trend_bull:
    enabled: true
    class: TrendDayBull
    instruments: [NQ, ES]
    applicable_day_types: [trend_up, super_trend_up]

    # Trade models (composable — see 05-trade-models.md)
    entry_models: [unicorn_ict, orderflow_cvd]
    stop_model: 1_atr
    target_model: 2r
    trail_rules:
      - trigger: 5m_fvg_formed
        action: move_to_breakeven
      - trigger: 2r_reached
        action: trail_by_1_atr

    # Filter overrides (merge with global filters)
    filters:
      order_flow:
        min_delta: 200
        min_cvd_slope: positive
      time:
        earliest: "09:45"
        latest: "14:30"
      volatility:
        min_ib_range: 25

    # Confidence
    confidence_threshold: 0.65
    max_daily_signals: 3

  edge_fade:
    enabled: true
    class: EdgeFadeStrategy
    instruments: [NQ]
    applicable_day_types: [b_day]
    entry_models: [tpo_rejection, liquidity_sweep]
    stop_model: lvn_hvn
    target_model: val_vah
    filters:
      regime:
        required: balance
      time:
        earliest: "10:00"
        latest: "15:00"
    confidence_threshold: 0.70

  # Disabled strategies (kept for research)
  trend_bear:
    enabled: false  # Disabled on NQ
    class: TrendDayBear
    note: "Consistently loses on NQ due to overnight bid. Consider for ES only."
```

---

## Data Flow

```
Bar data (pd.Series)
    │
    ├──► DayTypeConfidenceScorer.update(bar)
    │       └──► DayTypeConfidence (updated scores)
    │
    ├──► session_context dict (engine builds this)
    │       ├── ib_high, ib_low, ib_range
    │       ├── day_type_confidence: DayTypeConfidence
    │       ├── session_high, session_low
    │       ├── prior_day: {...}
    │       └── volume_profile: {...}
    │
    └──► Strategy.on_bar(bar, bar_index, session_context)
            │
            ├── Check applicable_day_types matches current
            ├── Check strategy-specific entry conditions
            ├── If conditions met:
            │   ├── Compute entry price
            │   ├── Apply entry_model.detect() if configured
            │   ├── Apply stop_model.compute() if configured
            │   ├── Apply target_model.compute() if configured
            │   └── Return Signal(...)
            └── If not: Return None

Signal
    │
    └──► Engine applies filters, execution, position management
            (See 06-backtest-engine.md)
```

---

## Metrics Emitted

| Metric | Layer | When |
|--------|-------|------|
| `strategy.signal_emitted` | strategy | Strategy returns a Signal |
| `strategy.no_signal` | strategy | Strategy returns None |
| `strategy.day_type_mismatch` | strategy | Bar's day type not in applicable_day_types |
| `day_confidence.updated` | component | DayTypeConfidenceScorer.update() called |
| `day_confidence.best_type` | component | Current best day type classification |

---

## Migration Notes

1. **No logic changes to existing strategies.** Move the code as-is. The only additions are:
   - `metrics` parameter in `__init__`
   - `entry_model`/`stop_model`/`target_model` fields on Signal

2. **Strategy YAML config is new.** Existing strategies have hardcoded entry/stop/target logic. The YAML config adds a layer on top — strategies that don't use YAML continue to work with their built-in logic.

3. **The `edge_fade` strategy referenced in CORE_STRATEGIES comes from the rockit-framework (deterministic modules), not BookMapOrderFlowStudies.** It needs to be wrapped as a StrategyBase subclass.

4. **`ibh_sweep`, `bear_accept`, `ib_retest`** are also from the deterministic modules. They need StrategyBase wrappers.

---

## Test Contract

See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#strategies) for:
- Contract tests for StrategyBase (every strategy must pass)
- Per-strategy unit tests with known-good fixtures
- YAML config loading tests
- Registry tests
