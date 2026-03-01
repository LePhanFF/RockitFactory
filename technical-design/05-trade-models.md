# Technical Design: Entry / Stop / Target Models

> **Package:** `rockit-core/models/`
> **Type:** NEW — no existing code, net-new implementation
> **Tests:** See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#trade-models)

---

## Purpose

Composable trade model modules that standardize how entries, stops, and targets are computed. The same code runs in backtesting, playbook generation, and live execution. Strategies compose these models via YAML config rather than hardcoding logic.

---

## Directory Structure

```
packages/rockit-core/src/rockit_core/models/
├── __init__.py           # Public exports: EntryModel, StopModel, TargetModel, registries
├── base.py               # Abstract base classes + dataclasses
├── registry.py           # Model registries (name → class)
├── entry/
│   ├── __init__.py
│   ├── unicorn_ict.py
│   ├── orderflow_cvd.py
│   ├── smt_divergence.py
│   ├── liquidity_sweep.py
│   ├── tpo_rejection.py
│   ├── three_drive.py
│   ├── double_top.py
│   ├── trendline.py
│   ├── trendline_backside.py
│   ├── tick_divergence.py
│   ├── bpr.py
│   ├── ifvg_reclaim.py
│   └── volume_imbalance.py
├── stop/
│   ├── __init__.py
│   ├── atr_stop.py        # 1 ATR and 2 ATR
│   ├── lvn_hvn.py
│   ├── ifvg_stop.py
│   ├── ib_stop.py
│   ├── prior_day_va.py
│   └── swing_stop.py
└── target/
    ├── __init__.py
    ├── atr_target.py       # 1 ATR and 2 ATR
    ├── r_multiple.py       # 2R, 3R
    ├── gap_fill.py         # 4H and 1H gap fill
    ├── time_liquidity.py   # Time-based liquidity levels
    ├── dpoc_target.py
    ├── va_target.py        # VAH/VAL targets
    ├── prior_day.py        # Prior day high/low
    └── trail/
        ├── __init__.py
        ├── fvg_trail.py    # Trail to BE after 5m FVG
        ├── bpr_trail.py    # Trail to BE after BPR invert + CISD
        └── atr_trail.py    # Trail by ATR increments
```

---

## Base Interfaces

```python
# packages/rockit-core/src/rockit_core/models/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd


@dataclass
class SessionContext:
    """Market context available to all trade models.

    Built by the backtest engine from bar data and passed to models.
    Models should only read from this — never modify.
    """
    # IB (Initial Balance)
    ib_high: float
    ib_low: float
    ib_range: float

    # Current state
    current_price: float
    current_time: datetime
    session_high: float
    session_low: float

    # Technical
    atr14: float
    vwap: float
    ema20: float
    ema50: float
    ema200: float
    rsi14: float

    # Order flow
    delta: float                     # Current bar buy volume - sell volume
    cumulative_delta: float          # Session cumulative
    cvd_trend: str                   # 'up', 'down', 'flat'

    # Volume profile (current session)
    poc: float                       # Point of Control
    vah: float                       # Value Area High
    val: float                       # Value Area Low
    hvn_levels: list[float] = field(default_factory=list)
    lvn_levels: list[float] = field(default_factory=list)

    # TPO
    tpo_shape: str = ""              # 'D', 'P', 'b', 'B', etc.
    single_prints_above: int = 0
    single_prints_below: int = 0
    dpoc: float = 0.0

    # Prior day
    prior_high: float = 0.0
    prior_low: float = 0.0
    prior_close: float = 0.0
    prior_vah: float = 0.0
    prior_val: float = 0.0
    prior_poc: float = 0.0

    # ICT structures (populated by indicators/ict_models.py)
    fvgs: list[dict] = field(default_factory=list)     # [{high, low, tf, direction}, ...]
    ifvgs: list[dict] = field(default_factory=list)
    bprs: list[dict] = field(default_factory=list)
    mss_levels: list[dict] = field(default_factory=list)

    # Day type
    day_type: str = ""
    day_type_confidence: float = 0.0

    # Full bar data (for models that need to scan history)
    bars: pd.DataFrame | None = None


# ─── ENTRY MODELS ──────────────────────────────────────────────

@dataclass
class EntrySignal:
    """Output of an entry model detection."""
    model: str              # 'unicorn_ict'
    direction: str          # 'LONG' or 'SHORT'
    entry_price: float
    confidence: float       # 0.0 to 1.0
    evidence: dict = field(default_factory=dict)  # Model-specific reasoning


class EntryModel(ABC):
    """Abstract base for all entry detection models.

    Entry models detect specific price patterns that indicate
    a high-probability entry point. They are stateless — given
    a SessionContext, they return whether an entry signal exists.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Model name for config reference. E.g., 'unicorn_ict'."""

    @abstractmethod
    def detect(self, context: SessionContext) -> list[EntrySignal]:
        """Detect entry signals in current context.

        Args:
            context: Full market context at current time.

        Returns:
            List of EntrySignal objects (can be empty).
            Multiple signals possible if pattern appears at multiple levels.
        """


# ─── STOP MODELS ───────────────────────────────────────────────

class StopModel(ABC):
    """Abstract base for stop placement models."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Model name for config reference. E.g., '1_atr'."""

    @abstractmethod
    def compute(
        self,
        entry: EntrySignal,
        context: SessionContext,
    ) -> float:
        """Compute stop price for a given entry.

        Args:
            entry: The entry signal (direction, entry_price)
            context: Full market context

        Returns:
            Stop price (float). Must be:
            - Below entry_price for LONG
            - Above entry_price for SHORT
        """


# ─── TARGET MODELS ─────────────────────────────────────────────

@dataclass
class TrailRule:
    """Defines a condition for moving the stop."""
    trigger: str            # 'fvg_formed_5m', 'bpr_inverted', '2r_reached', 'time_15:00'
    action: str             # 'move_to_breakeven', 'trail_by_1_atr', 'exit_market'
    params: dict = field(default_factory=dict)


@dataclass
class TargetSpec:
    """Output of a target model."""
    targets: list[float]            # Price targets (can have multiple for scaling)
    trail_rules: list[TrailRule] = field(default_factory=list)


class TargetModel(ABC):
    """Abstract base for target/profit-taking models."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Model name for config reference. E.g., '2r'."""

    @abstractmethod
    def compute(
        self,
        entry: EntrySignal,
        stop_price: float,
        context: SessionContext,
    ) -> TargetSpec:
        """Compute target price(s) and trail rules.

        Args:
            entry: The entry signal
            stop_price: The computed stop price
            context: Full market context

        Returns:
            TargetSpec with target price(s) and optional trail rules.
        """
```

---

## Concrete Implementations

### Entry Models

```python
# packages/rockit-core/src/rockit_core/models/entry/unicorn_ict.py

class UnicornICTEntry(EntryModel):
    """ICT Unicorn model: FVG + MSS + OTE confluence.

    Detects:
    1. Market Structure Shift (MSS) — break of recent swing
    2. Fair Value Gap (FVG) — 3-candle imbalance in direction of MSS
    3. Optimal Trade Entry (OTE) — price retraces to 62-79% fib of the impulse

    Signal: Enter when price enters the FVG zone within OTE range.

    Dependencies:
        - context.fvgs (from indicators/ict_models.py)
        - context.mss_levels (from indicators/ict_models.py)
        - context.bars (for fib calculation)
    """

    @property
    def name(self) -> str:
        return "unicorn_ict"

    def detect(self, context: SessionContext) -> list[EntrySignal]:
        signals = []

        # 1. Find recent MSS
        mss = self._find_recent_mss(context)
        if not mss:
            return signals

        # 2. Find FVG in direction of MSS
        fvg = self._find_aligned_fvg(context, mss)
        if not fvg:
            return signals

        # 3. Check if current price is in OTE zone of FVG
        ote_zone = self._compute_ote_zone(context, mss)
        if not self._price_in_zone(context.current_price, fvg, ote_zone):
            return signals

        signals.append(EntrySignal(
            model=self.name,
            direction=mss["direction"],
            entry_price=context.current_price,
            confidence=self._compute_confidence(context, mss, fvg, ote_zone),
            evidence={
                "mss_level": mss["price"],
                "fvg_high": fvg["high"],
                "fvg_low": fvg["low"],
                "ote_range": ote_zone,
            },
        ))
        return signals

    def _find_recent_mss(self, context: SessionContext) -> dict | None:
        ...

    def _find_aligned_fvg(self, context: SessionContext, mss: dict) -> dict | None:
        ...

    def _compute_ote_zone(self, context: SessionContext, mss: dict) -> tuple[float, float]:
        ...

    def _price_in_zone(self, price: float, fvg: dict, ote: tuple) -> bool:
        ...

    def _compute_confidence(self, context, mss, fvg, ote) -> float:
        ...
```

```python
# packages/rockit-core/src/rockit_core/models/entry/orderflow_cvd.py

class OrderFlowCVDEntry(EntryModel):
    """Order flow entry based on CVD divergence.

    Detects:
    1. Price making new highs/lows
    2. CVD NOT confirming (divergence)
    3. Delta shift confirming reversal

    Signal: Enter on divergence confirmation.

    Dependencies:
        - context.delta
        - context.cumulative_delta
        - context.cvd_trend
        - context.bars (for price swing detection)
    """

    @property
    def name(self) -> str:
        return "orderflow_cvd"

    def detect(self, context: SessionContext) -> list[EntrySignal]:
        ...
```

```python
# packages/rockit-core/src/rockit_core/models/entry/smt_divergence.py

class SMTDivergenceEntry(EntryModel):
    """Smart Money Theory divergence between correlated instruments.

    Detects:
    1. NQ makes new high, ES does not (or vice versa)
    2. Divergence implies institutional distribution/accumulation

    Dependencies:
        - Requires cross-market data (ES/YM alongside NQ)
        - context.metadata must contain cross_market data
    """

    @property
    def name(self) -> str:
        return "smt_divergence"

    def detect(self, context: SessionContext) -> list[EntrySignal]:
        ...
```

*(Similar stubs for: liquidity_sweep, tpo_rejection, three_drive, double_top,
trendline, trendline_backside, tick_divergence, bpr, ifvg_reclaim, volume_imbalance)*

### Stop Models

```python
# packages/rockit-core/src/rockit_core/models/stop/atr_stop.py

class ATRStop(StopModel):
    """ATR-based stop placement.

    Places stop at N * ATR(14) from entry price.
    Configurable multiplier (default: 1.0).
    """

    def __init__(self, multiplier: float = 1.0):
        self._multiplier = multiplier

    @property
    def name(self) -> str:
        return f"{self._multiplier:.0f}_atr"

    def compute(self, entry: EntrySignal, context: SessionContext) -> float:
        distance = self._multiplier * context.atr14
        if entry.direction == 'LONG':
            return entry.entry_price - distance
        return entry.entry_price + distance


# Convenience instances
ATR1Stop = lambda: ATRStop(1.0)   # "1_atr"
ATR2Stop = lambda: ATRStop(2.0)   # "2_atr"
```

```python
# packages/rockit-core/src/rockit_core/models/stop/lvn_hvn.py

class LVNHVNStop(StopModel):
    """Stop at nearest LVN or HVN below/above entry.

    For longs: finds nearest LVN below entry price.
    For shorts: finds nearest HVN above entry price.

    Falls back to 1.5 ATR if no suitable level found.
    """

    @property
    def name(self) -> str:
        return "lvn_hvn"

    def compute(self, entry: EntrySignal, context: SessionContext) -> float:
        if entry.direction == 'LONG':
            # Find nearest LVN below entry
            candidates = [l for l in context.lvn_levels if l < entry.entry_price]
            if candidates:
                return max(candidates)  # Nearest below
        else:
            # Find nearest HVN above entry
            candidates = [l for l in context.hvn_levels if l > entry.entry_price]
            if candidates:
                return min(candidates)  # Nearest above

        # Fallback: 1.5 ATR
        distance = 1.5 * context.atr14
        if entry.direction == 'LONG':
            return entry.entry_price - distance
        return entry.entry_price + distance
```

```python
# packages/rockit-core/src/rockit_core/models/stop/ifvg_stop.py

class IFVGStop(StopModel):
    """Stop below/above the Inverse FVG that triggered entry.

    Only meaningful when entry_model is 'unicorn_ict' or 'ifvg_reclaim'.
    Falls back to 1 ATR if no IFVG reference in entry evidence.
    """

    @property
    def name(self) -> str:
        return "ifvg"

    def compute(self, entry: EntrySignal, context: SessionContext) -> float:
        ifvg = entry.evidence.get("fvg_low") or entry.evidence.get("fvg_high")
        if ifvg and entry.direction == 'LONG':
            return ifvg - (context.atr14 * 0.25)  # Small buffer below FVG
        elif ifvg and entry.direction == 'SHORT':
            return ifvg + (context.atr14 * 0.25)

        # Fallback
        return ATRStop(1.0).compute(entry, context)
```

### Target Models

```python
# packages/rockit-core/src/rockit_core/models/target/r_multiple.py

class RMultipleTarget(TargetModel):
    """Target at N times the risk (entry-to-stop distance).

    2R means target is 2x the risk distance from entry.
    """

    def __init__(self, multiple: float = 2.0):
        self._multiple = multiple

    @property
    def name(self) -> str:
        return f"{self._multiple:.0f}r"

    def compute(self, entry: EntrySignal, stop_price: float, context: SessionContext) -> TargetSpec:
        risk = abs(entry.entry_price - stop_price)
        if entry.direction == 'LONG':
            target = entry.entry_price + (risk * self._multiple)
        else:
            target = entry.entry_price - (risk * self._multiple)

        return TargetSpec(targets=[target])
```

```python
# packages/rockit-core/src/rockit_core/models/target/trail/fvg_trail.py

class FVGTrailToBE(TargetModel):
    """Trail stop to breakeven after a 5-minute FVG forms in direction.

    Primary target is 2R. Trail rule: when a new FVG forms on the
    5-minute chart in the trade direction, move stop to breakeven.

    This model wraps a primary target with trail rules.
    """

    def __init__(self, primary_target_r: float = 2.0):
        self._primary_r = primary_target_r

    @property
    def name(self) -> str:
        return "trail_be_fvg"

    def compute(self, entry: EntrySignal, stop_price: float, context: SessionContext) -> TargetSpec:
        risk = abs(entry.entry_price - stop_price)
        if entry.direction == 'LONG':
            target = entry.entry_price + (risk * self._primary_r)
        else:
            target = entry.entry_price - (risk * self._primary_r)

        return TargetSpec(
            targets=[target],
            trail_rules=[
                TrailRule(
                    trigger="fvg_formed_5m",
                    action="move_to_breakeven",
                    params={"timeframe": "5m", "direction": entry.direction},
                ),
            ],
        )
```

---

## Registry

```python
# packages/rockit-core/src/rockit_core/models/registry.py

from rockit_core.models.entry.unicorn_ict import UnicornICTEntry
from rockit_core.models.entry.orderflow_cvd import OrderFlowCVDEntry
from rockit_core.models.entry.smt_divergence import SMTDivergenceEntry
from rockit_core.models.entry.liquidity_sweep import LiquiditySweepEntry
from rockit_core.models.entry.tpo_rejection import TPORejectionEntry
from rockit_core.models.entry.three_drive import ThreeDriveEntry
from rockit_core.models.entry.double_top import DoubleTopEntry
from rockit_core.models.entry.trendline import TrendlineEntry
from rockit_core.models.entry.trendline_backside import TrendlineBacksideEntry
from rockit_core.models.entry.tick_divergence import TickDivergenceEntry
from rockit_core.models.entry.bpr import BPREntry
from rockit_core.models.entry.ifvg_reclaim import IFVGReclaimEntry
from rockit_core.models.entry.volume_imbalance import VolumeImbalanceEntry

from rockit_core.models.stop.atr_stop import ATRStop
from rockit_core.models.stop.lvn_hvn import LVNHVNStop
from rockit_core.models.stop.ifvg_stop import IFVGStop
from rockit_core.models.stop.ib_stop import IBStop
from rockit_core.models.stop.prior_day_va import PriorDayVAStop
from rockit_core.models.stop.swing_stop import SwingStop

from rockit_core.models.target.r_multiple import RMultipleTarget
from rockit_core.models.target.atr_target import ATRTarget
from rockit_core.models.target.gap_fill import GapFillTarget
from rockit_core.models.target.time_liquidity import TimeLiquidityTarget
from rockit_core.models.target.dpoc_target import DPOCTarget
from rockit_core.models.target.va_target import VATarget
from rockit_core.models.target.prior_day import PriorDayTarget
from rockit_core.models.target.trail.fvg_trail import FVGTrailToBE
from rockit_core.models.target.trail.bpr_trail import BPRTrailToBE
from rockit_core.models.target.trail.atr_trail import ATRTrail


ENTRY_MODELS: dict[str, type[EntryModel]] = {
    "unicorn_ict": UnicornICTEntry,
    "orderflow_cvd": OrderFlowCVDEntry,
    "smt_divergence": SMTDivergenceEntry,
    "liquidity_sweep": LiquiditySweepEntry,
    "tpo_rejection": TPORejectionEntry,
    "three_drive": ThreeDriveEntry,
    "double_top": DoubleTopEntry,
    "trendline": TrendlineEntry,
    "trendline_backside": TrendlineBacksideEntry,
    "tick_divergence": TickDivergenceEntry,
    "bpr": BPREntry,
    "ifvg_reclaim": IFVGReclaimEntry,
    "volume_imbalance": VolumeImbalanceEntry,
}

STOP_MODELS: dict[str, type[StopModel] | callable] = {
    "1_atr": lambda: ATRStop(1.0),
    "2_atr": lambda: ATRStop(2.0),
    "lvn_hvn": LVNHVNStop,
    "ifvg": IFVGStop,
    "ib": IBStop,
    "prior_day_va": PriorDayVAStop,
    "swing": SwingStop,
}

TARGET_MODELS: dict[str, type[TargetModel] | callable] = {
    "1_atr": lambda: ATRTarget(1.0),
    "2_atr": lambda: ATRTarget(2.0),
    "2r": lambda: RMultipleTarget(2.0),
    "3r": lambda: RMultipleTarget(3.0),
    "4h_gap_fill": lambda: GapFillTarget("4h"),
    "1h_gap_fill": lambda: GapFillTarget("1h"),
    "time_liquidity": TimeLiquidityTarget,
    "dpoc": DPOCTarget,
    "val_vah": VATarget,
    "prior_day": PriorDayTarget,
    "trail_be_fvg": FVGTrailToBE,
    "trail_be_bpr": BPRTrailToBE,
    "trail_atr": ATRTrail,
}


def get_entry_model(name: str) -> EntryModel:
    """Look up and instantiate an entry model by name."""
    factory = ENTRY_MODELS.get(name)
    if factory is None:
        raise ValueError(f"Unknown entry model: {name}. Available: {list(ENTRY_MODELS.keys())}")
    return factory() if callable(factory) and not isinstance(factory, type) else factory()


def get_stop_model(name: str) -> StopModel:
    """Look up and instantiate a stop model by name."""
    factory = STOP_MODELS.get(name)
    if factory is None:
        raise ValueError(f"Unknown stop model: {name}. Available: {list(STOP_MODELS.keys())}")
    return factory() if callable(factory) else factory()


def get_target_model(name: str) -> TargetModel:
    """Look up and instantiate a target model by name."""
    factory = TARGET_MODELS.get(name)
    if factory is None:
        raise ValueError(f"Unknown target model: {name}. Available: {list(TARGET_MODELS.keys())}")
    return factory() if callable(factory) else factory()
```

---

## How Strategies Compose Models

```python
# In the backtest engine, when a strategy emits a Signal:

def apply_trade_models(signal: Signal, context: SessionContext, strategy_config: dict) -> Signal:
    """Apply entry/stop/target models from config to a raw signal.

    If the strategy already set entry/stop/target prices (hardcoded),
    and no models are configured in YAML, use the strategy's values.

    If models are configured, they override the strategy's values.
    """
    # Entry models (optional — strategy may already provide entry_price)
    if strategy_config.get("entry_models"):
        for model_name in strategy_config["entry_models"]:
            model = get_entry_model(model_name)
            detections = model.detect(context)
            if detections:
                best = max(detections, key=lambda d: d.confidence)
                signal.entry_price = best.entry_price
                signal.entry_model = best.model
                signal.confidence = str(best.confidence)
                signal.metadata["entry_evidence"] = best.evidence
                break  # Use first model that detects

    # Stop model (optional — strategy may already provide stop_price)
    if strategy_config.get("stop_model"):
        model = get_stop_model(strategy_config["stop_model"])
        signal.stop_price = model.compute(
            EntrySignal(model="", direction=signal.direction,
                        entry_price=signal.entry_price, confidence=0.0,
                        evidence=signal.metadata.get("entry_evidence", {})),
            context,
        )
        signal.stop_model = model.name

    # Target model
    if strategy_config.get("target_model"):
        model = get_target_model(strategy_config["target_model"])
        spec = model.compute(
            EntrySignal(model="", direction=signal.direction,
                        entry_price=signal.entry_price, confidence=0.0),
            signal.stop_price,
            context,
        )
        if spec.targets:
            signal.target_price = spec.targets[0]
        signal.target_model = model.name
        signal.metadata["trail_rules"] = [
            {"trigger": r.trigger, "action": r.action, "params": r.params}
            for r in spec.trail_rules
        ]

    return signal
```

---

## Metrics Emitted

| Metric | Layer | When |
|--------|-------|------|
| `entry_model.detected` | component | Entry model finds a signal |
| `entry_model.no_detection` | component | Entry model finds nothing |
| `entry_model.confidence` | component | Confidence score of detection |
| `stop_model.computed` | component | Stop price computed |
| `stop_model.fallback` | component | Model fell back to default (e.g., no LVN found) |
| `target_model.computed` | component | Target price computed |
| `target_model.trail_rules_count` | component | Number of trail rules attached |

---

## Test Contract

Each model must have:

1. **Unit test with known context** — given a specific SessionContext, does the model produce the expected output?
2. **Edge case tests** — what happens when context is missing data (no FVGs, no LVN levels)?
3. **Fallback tests** — do fallback behaviors trigger correctly?
4. **Direction tests** — test both LONG and SHORT for every model
5. **Integration test** — compose entry + stop + target and verify the resulting Signal has consistent prices (stop < entry < target for LONG)

See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#trade-models)
