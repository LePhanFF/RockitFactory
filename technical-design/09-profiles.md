# Technical Design: Market Profile

> **Package:** `rockit-core/profile/`
> **Type:** MIGRATE from BookMapOrderFlowStudies/profile/ + DEDUP with rockit-framework/modules/
> **Source files:** 6 files from BookMap, 6 overlapping modules from rockit-framework
> **Tests:** See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#profiles)

---

## Purpose

Market profile modules compute volume-at-price distributions, TPO (Time-Price Opportunity) profiles, developing POC migration, IB-specific analytics, level confluences, and wick extremes analysis. These are used by the backtest engine (via session context), by strategies for decision-making, and by the deterministic orchestrator for snapshot generation.

---

## Source Files (Being Migrated)

### BookMapOrderFlowStudies/profile/ (canonical versions)

| File | LOC | Destination | Type |
|------|-----|-------------|------|
| `profile/volume_profile.py` | ~200 | `profile/volume_profile.py` | MIGRATE |
| `profile/tpo_profile.py` | ~250 | `profile/tpo_profile.py` | MIGRATE |
| `profile/dpoc_migration.py` | ~180 | `profile/dpoc_migration.py` | MIGRATE |
| `profile/ib_analysis.py` | ~150 | `profile/ib_analysis.py` | MIGRATE |
| `profile/confluences.py` | ~120 | `profile/confluences.py` | MIGRATE |
| `profile/wick_parade.py` | ~100 | `profile/wick_parade.py` | MIGRATE |

### rockit-framework/modules/ (duplicate versions — DISCARD)

| File | LOC | Action |
|------|-----|--------|
| `modules/volume_profile.py` | 116 | DISCARD — use BookMap version, wrap for orchestrator |
| `modules/tpo_profile.py` | 166 | DISCARD — use BookMap version, wrap for orchestrator |
| `modules/dpoc_migration.py` | 167 | DISCARD — use BookMap version, wrap for orchestrator |
| `modules/wick_parade.py` | 42 | DISCARD — use BookMap version, wrap for orchestrator |
| `modules/ib_location.py` | 96 | DISCARD — merge into BookMap ib_analysis.py |
| `modules/core_confluences.py` | 146 | DISCARD — use BookMap version, wrap for orchestrator |

---

## Interface: volume_profile.py

```python
# packages/rockit-core/src/rockit_core/profile/volume_profile.py

"""Volume-at-price profile computation.

Source: BookMapOrderFlowStudies/profile/volume_profile.py (~200 LOC)
Migration: MIGRATE as canonical version. rockit-framework/modules/volume_profile.py
           is discarded; the orchestrator wrapper calls this module instead.

Dependencies: pandas, numpy
"""

from dataclasses import dataclass, field

import pandas as pd
import numpy as np


@dataclass
class VolumeProfileResult:
    """Complete volume profile for a session."""
    poc: float                          # Point of Control (highest volume price)
    vah: float                          # Value Area High
    val: float                          # Value Area Low
    hvn_levels: list[float] = field(default_factory=list)   # High Volume Nodes
    lvn_levels: list[float] = field(default_factory=list)   # Low Volume Nodes
    total_volume: float = 0.0
    value_area_volume_pct: float = 0.70
    price_distribution: dict[float, float] = field(default_factory=dict)  # price → volume


def compute_volume_profile(
    bars: pd.DataFrame,
    tick_size: float = 0.25,
    value_area_pct: float = 0.70,
    hvn_threshold_pct: float = 0.80,
    lvn_threshold_pct: float = 0.20,
) -> VolumeProfileResult:
    """Compute volume profile from bar data.

    1. Build volume-at-price histogram (using close prices binned by tick_size)
    2. Find POC (price level with highest volume)
    3. Expand from POC to find VA (70% of total volume)
    4. Identify HVN (>80th percentile volume) and LVN (<20th percentile volume)

    Args:
        bars: DataFrame with close, volume columns.
        tick_size: Price binning resolution.
        value_area_pct: Target volume percentage for value area.
        hvn_threshold_pct: Percentile threshold for High Volume Nodes.
        lvn_threshold_pct: Percentile threshold for Low Volume Nodes.

    Returns:
        VolumeProfileResult with POC, VAH, VAL, HVN/LVN levels.
    """
    ...


def compute_developing_profile(
    bars: pd.DataFrame,
    up_to_index: int,
    tick_size: float = 0.25,
) -> VolumeProfileResult:
    """Compute developing volume profile up to a specific bar index.

    Used for intraday developing POC/VA tracking.

    Args:
        bars: Full session bars.
        up_to_index: Compute profile only using bars 0..up_to_index.
        tick_size: Price binning resolution.

    Returns:
        VolumeProfileResult for the partial session.
    """
    ...


def compute_prior_session_profile(
    prior_bars: pd.DataFrame,
    tick_size: float = 0.25,
) -> VolumeProfileResult:
    """Compute volume profile for the prior trading session.

    Args:
        prior_bars: Prior session bar data.
        tick_size: Price binning resolution.

    Returns:
        VolumeProfileResult for prior session.
    """
    return compute_volume_profile(prior_bars, tick_size)
```

---

## Interface: tpo_profile.py

```python
# packages/rockit-core/src/rockit_core/profile/tpo_profile.py

"""TPO (Time-Price Opportunity) profile computation.

Source: BookMapOrderFlowStudies/profile/tpo_profile.py (~250 LOC)
Migration: MIGRATE as canonical version.

Assigns TPO letters to 30-minute periods, computes profile shape,
identifies single prints, poor highs/lows, and fattening zones.

Dependencies: pandas, numpy
"""

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class TPOProfileResult:
    """Complete TPO profile for a session."""
    shape: str                          # "D" | "P" | "b" | "B" | "wide" | "narrow"
    tpo_count: int                      # Total TPO count
    single_prints_above: int            # Single prints above POC
    single_prints_below: int            # Single prints below POC
    poor_high: bool                     # Multiple TPOs at session high (weak rejection)
    poor_low: bool                      # Multiple TPOs at session low (weak rejection)
    fattening_zones: list[dict] = field(default_factory=list)
    # [{"price_low": float, "price_high": float, "period": str}, ...]
    tpo_letters: dict[str, list[float]] = field(default_factory=dict)
    # {"A": [price1, price2, ...], "B": [...], ...}


def compute_tpo_profile(
    bars: pd.DataFrame,
    tick_size: float = 0.25,
    period_minutes: int = 30,
) -> TPOProfileResult:
    """Compute TPO profile from bar data.

    Assigns letters A, B, C, ... to each 30-minute period.
    Each price level touched during a period gets that letter.

    Shape classification:
    - "D": Normal distribution (bell curve) — balanced day
    - "P": Excess volume at top (buying tail) — bullish
    - "b": Excess volume at bottom (selling tail) — bearish
    - "B": Double distribution (bimodal) — two-timeframe activity
    - "wide": Wide range, no clear shape
    - "narrow": Narrow range, compressed

    Args:
        bars: Session bar data with timestamp, high, low, close.
        tick_size: Price granularity for TPO assignment.
        period_minutes: Duration of each TPO period.

    Returns:
        TPOProfileResult with shape, single prints, poor highs/lows.
    """
    ...


def detect_single_prints(
    tpo_letters: dict[str, list[float]],
    poc: float,
) -> tuple[int, int]:
    """Count single prints above and below POC.

    A single print is a price level that only has one TPO letter.
    Single prints indicate fast price movement (institutional activity).

    Args:
        tpo_letters: TPO letter assignments from compute_tpo_profile.
        poc: Point of Control price.

    Returns:
        Tuple of (single_prints_above_poc, single_prints_below_poc).
    """
    ...


def classify_tpo_shape(
    tpo_letters: dict[str, list[float]],
    vah: float,
    val: float,
    poc: float,
) -> str:
    """Classify the TPO profile shape.

    Args:
        tpo_letters: TPO letter assignments.
        vah: Value Area High.
        val: Value Area Low.
        poc: Point of Control.

    Returns:
        Shape string: "D", "P", "b", "B", "wide", or "narrow".
    """
    ...
```

---

## Interface: dpoc_migration.py

```python
# packages/rockit-core/src/rockit_core/profile/dpoc_migration.py

"""Developing POC (DPOC) migration tracking.

Source: BookMapOrderFlowStudies/profile/dpoc_migration.py (~180 LOC)
Migration: MIGRATE as canonical version.

Tracks how the POC moves throughout the session in 30-minute slices.
A migrating DPOC indicates institutional conviction. A stale DPOC
(not moving) suggests balance.

Dependencies: pandas
"""

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class DPOCSlice:
    """DPOC position at a point in time."""
    time: str               # "HH:MM"
    dpoc: float             # Current developing POC price
    direction: str          # "up" | "down" | "flat" vs previous slice


@dataclass
class DPOCMigrationResult:
    """Full DPOC migration analysis for a session."""
    slices: list[DPOCSlice] = field(default_factory=list)
    net_direction: str = "flat"         # "up" | "down" | "flat"
    migration_magnitude: float = 0.0    # Total points moved
    migration_speed: float = 0.0        # Points per hour
    is_migrating: bool = False          # True if DPOC moved > 2 ticks


def compute_dpoc_migration(
    bars: pd.DataFrame,
    tick_size: float = 0.25,
    slice_minutes: int = 30,
) -> DPOCMigrationResult:
    """Track DPOC migration through the session.

    Computes volume profile at each 30-minute slice and records the
    developing POC. Compares consecutive slices to determine direction.

    Args:
        bars: Session bar data.
        tick_size: Price binning resolution.
        slice_minutes: Time interval between DPOC snapshots.

    Returns:
        DPOCMigrationResult with all slices and summary metrics.
    """
    ...
```

---

## Interface: ib_analysis.py

```python
# packages/rockit-core/src/rockit_core/profile/ib_analysis.py

"""Initial Balance specific analysis.

Source: BookMapOrderFlowStudies/profile/ib_analysis.py (~150 LOC)
       + rockit-framework/modules/ib_location.py (~96 LOC) merged in
Migration: MIGRATE + MERGE

Combines IB metrics from both repos into a single module:
- IB range, width classification, extension tracking (from BookMap)
- IB location relative to prior day levels, ATR context (from framework)

Dependencies: pandas
"""

from dataclasses import dataclass

import pandas as pd


@dataclass
class IBAnalysisResult:
    """Complete IB analysis."""
    # Core IB metrics
    ib_high: float
    ib_low: float
    ib_range: float
    ib_midpoint: float

    # Width classification
    width_classification: str       # "narrow" | "normal" | "wide" | "extreme"
    ib_pct_of_atr: float           # IB range / ATR(14) * 100

    # Location relative to prior day
    location_vs_prior_va: str       # "above_vah" | "inside_va" | "below_val"
    location_vs_prior_range: str    # "above_high" | "inside_range" | "below_low"
    gap_from_prior_close: float     # IB mid - prior close

    # Extension tracking (updated post-IB)
    ibh_broken: bool = False
    ibl_broken: bool = False
    extension_above: float = 0.0    # points above IBH
    extension_below: float = 0.0    # points below IBL


def compute_ib_analysis(
    ib_bars: pd.DataFrame,
    prior_day: dict,
    atr: float,
) -> IBAnalysisResult:
    """Compute full IB analysis.

    Args:
        ib_bars: First 60 minutes of bar data.
        prior_day: Dict with prior session high, low, close, vah, val, poc.
        atr: ATR(14) value.

    Returns:
        IBAnalysisResult with all metrics.
    """
    ...


def update_ib_extensions(
    analysis: IBAnalysisResult,
    current_high: float,
    current_low: float,
) -> IBAnalysisResult:
    """Update IB extension metrics with current session high/low.

    Called on each post-IB bar to track how far price extends beyond IB.

    Args:
        analysis: Existing IBAnalysisResult.
        current_high: Running session high.
        current_low: Running session low.

    Returns:
        Updated IBAnalysisResult.
    """
    analysis.ibh_broken = current_high > analysis.ib_high
    analysis.ibl_broken = current_low < analysis.ib_low
    analysis.extension_above = max(0, current_high - analysis.ib_high)
    analysis.extension_below = max(0, analysis.ib_low - current_low)
    return analysis
```

---

## Interface: confluences.py

```python
# packages/rockit-core/src/rockit_core/profile/confluences.py

"""Level confluence detection.

Source: BookMapOrderFlowStudies/profile/confluences.py (~120 LOC)
Migration: MIGRATE as canonical version.

Detects when multiple support/resistance levels cluster within a
price zone. Confluence zones are higher-probability reaction levels.

Dependencies: none (stdlib only)
"""

from dataclasses import dataclass, field


@dataclass
class ConfluenceZone:
    """A price zone where multiple levels converge."""
    center: float                       # Center price of the zone
    width: float                        # Zone width in points
    level_count: int                    # Number of levels in the zone
    levels: list[dict] = field(default_factory=list)
    # [{"type": "poc", "price": 17450.0}, {"type": "vah", "price": 17452.5}, ...]
    strength: str = "weak"              # "weak" (2) | "moderate" (3) | "strong" (4+)


def detect_confluences(
    levels: list[dict],
    tolerance: float = 5.0,
) -> list[ConfluenceZone]:
    """Find price zones where multiple levels cluster.

    Args:
        levels: List of level dicts with "type" and "price" keys.
            Types: "poc", "vah", "val", "hvn", "lvn", "ema20", "ema50",
                   "prior_high", "prior_low", "prior_poc", "fvg", "ib_high", "ib_low"
        tolerance: Maximum distance in points for levels to be
                   considered confluent.

    Returns:
        List of ConfluenceZone objects, sorted by level_count descending.
    """
    ...
```

---

## Interface: wick_parade.py

```python
# packages/rockit-core/src/rockit_core/profile/wick_parade.py

"""Wick parade (extremes) analysis.

Source: BookMapOrderFlowStudies/profile/wick_parade.py (~100 LOC)
Migration: MIGRATE as canonical version.

Counts bullish and bearish wicks in a rolling window to detect
buying/selling pressure at extremes. A "wick parade" at the bottom
(many bullish wicks) signals buying interest.

Dependencies: pandas
"""

from dataclasses import dataclass

import pandas as pd


@dataclass
class WickParadeResult:
    """Wick analysis for a session or window."""
    bullish_wicks: int          # Count of bars with lower wick > 50% of range
    bearish_wicks: int          # Count of bars with upper wick > 50% of range
    net_direction: str          # "bullish" | "bearish" | "neutral"
    dominant_pct: float         # Max(bullish, bearish) / total * 100


def compute_wick_parade(
    bars: pd.DataFrame,
    window: int = 12,
    wick_threshold_pct: float = 0.50,
) -> WickParadeResult:
    """Analyze wick patterns in a rolling window.

    A bullish wick: (close - low) / (high - low) > threshold
    A bearish wick: (high - close) / (high - low) > threshold

    Args:
        bars: Bar data with open, high, low, close.
        window: Number of bars in the analysis window.
        wick_threshold_pct: Minimum wick ratio to count.

    Returns:
        WickParadeResult with counts and direction.
    """
    ...
```

---

## Data Flow

```
Bar Data (pd.DataFrame)
    │
    ├──► volume_profile.py
    │       ├── compute_volume_profile() ──► VolumeProfileResult
    │       │       ├── poc, vah, val
    │       │       ├── hvn_levels, lvn_levels
    │       │       └── price_distribution
    │       └── compute_developing_profile() ──► developing VP
    │
    ├──► tpo_profile.py
    │       └── compute_tpo_profile() ──► TPOProfileResult
    │               ├── shape (D, P, b, B)
    │               ├── single_prints_above/below
    │               ├── poor_high, poor_low
    │               └── fattening_zones
    │
    ├──► dpoc_migration.py
    │       └── compute_dpoc_migration() ──► DPOCMigrationResult
    │               ├── slices [{time, dpoc, direction}, ...]
    │               ├── net_direction
    │               └── migration_magnitude
    │
    ├──► ib_analysis.py
    │       ├── compute_ib_analysis() ──► IBAnalysisResult
    │       └── update_ib_extensions() ──► updated IBAnalysisResult
    │
    ├──► confluences.py
    │       └── detect_confluences(all_levels) ──► [ConfluenceZone, ...]
    │
    └──► wick_parade.py
            └── compute_wick_parade() ──► WickParadeResult
    │
    ▼
session_context dict / deterministic snapshot JSON
```

---

## Dependencies

| This module | Depends on |
|-------------|-----------|
| `profile/volume_profile.py` | `pandas`, `numpy` |
| `profile/tpo_profile.py` | `pandas` |
| `profile/dpoc_migration.py` | `pandas`, `profile/volume_profile.py` |
| `profile/ib_analysis.py` | `pandas` |
| `profile/confluences.py` | None (stdlib only) |
| `profile/wick_parade.py` | `pandas` |

Note: `dpoc_migration.py` depends on `volume_profile.py` because it computes developing profiles at each slice. All other profile modules are independent.

---

## DEDUP Notes

| Duplicated Module | BookMap Version | Framework Version | Resolution |
|-------------------|----------------|-------------------|------------|
| volume_profile | `profile/volume_profile.py` (~200 LOC) | `modules/volume_profile.py` (116 LOC) | **Keep BookMap** — more complete, has HVN/LVN detection |
| tpo_profile | `profile/tpo_profile.py` (~250 LOC) | `modules/tpo_profile.py` (166 LOC) | **Keep BookMap** — has shape classification and fattening zones |
| dpoc_migration | `profile/dpoc_migration.py` (~180 LOC) | `modules/dpoc_migration.py` (167 LOC) | **Keep BookMap** — equivalent, but BookMap version has dataclass output |
| wick_parade | `profile/wick_parade.py` (~100 LOC) | `modules/wick_parade.py` (42 LOC) | **Keep BookMap** — framework version is a thin wrapper |
| ib_analysis | `profile/ib_analysis.py` (~150 LOC) | `modules/ib_location.py` (96 LOC) | **Merge** — BookMap has core metrics, framework adds location context |
| confluences | `profile/confluences.py` (~120 LOC) | `modules/core_confluences.py` (146 LOC) | **Keep BookMap** — framework version adds boolean logic that moves to orchestrator wrapper |

The deterministic orchestrator modules (`deterministic/modules/`) will import from `profile/` and wrap the calls with the `get_X(df, time, **kwargs) -> dict` interface expected by the orchestrator. See [10-deterministic-modules.md](10-deterministic-modules.md).

---

## Metrics Emitted

Profile modules are pure functions and do not directly emit metrics. When called by the deterministic orchestrator, the orchestrator wrapper emits module-level metrics:

| Metric | Layer | When |
|--------|-------|------|
| `module.volume_profile.duration_ms` | module | Volume profile computation time |
| `module.tpo_profile.duration_ms` | module | TPO profile computation time |
| `module.dpoc_migration.duration_ms` | module | DPOC migration computation time |

---

## Migration Notes

1. **BookMap versions are canonical.** They are more complete, better structured (dataclass outputs), and are what the backtest engine already uses.

2. **Framework module wrappers.** The deterministic orchestrator will call thin wrapper functions in `deterministic/modules/` that import from `profile/` and convert the dataclass outputs to dicts matching the snapshot schema.

3. **ib_analysis.py is a merge.** BookMap `ib_analysis.py` provides IB range metrics. Framework `ib_location.py` provides location relative to prior day. The merged version includes both.

4. **No API changes.** The function signatures and return types are preserved from the BookMap versions.

---

## Test Contract

1. **Volume profile** — known price/volume data, verify POC/VAH/VAL match hand calculation
2. **HVN/LVN detection** — known distribution with clear peaks and valleys
3. **TPO shape classification** — construct D, P, b, B shapes, verify classification
4. **Single prints** — construct profile with known single prints, verify count
5. **DPOC migration** — construct session with migrating POC, verify direction and magnitude
6. **IB analysis** — known IB bars and prior day data, verify all fields
7. **Confluence detection** — place 4 levels within 5 points, verify zone detected
8. **Wick parade** — construct bars with strong lower wicks, verify bullish detection
9. **Developing profile** — compute at bar 10 vs bar 20, verify POC can shift

See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#profiles)
