# Technical Design: Indicators

> **Package:** `rockit-core/indicators/`
> **Type:** MIGRATE from BookMapOrderFlowStudies/indicators/
> **Source files:** 5 files, ~1,480 LOC
> **Tests:** See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#indicators)

---

## Purpose

Technical indicators compute derived values from raw bar data and populate `session_context` for strategies and filters. Indicators are pure functions or stateless classes — given bar data, they return computed values. They are called by the backtest engine during context building and by the deterministic orchestrator for snapshot generation.

---

## Source Files (Being Migrated)

| File | LOC | Destination | Type |
|------|-----|-------------|------|
| `indicators/technical.py` | ~130 | `indicators/technical.py` | MIGRATE |
| `indicators/ict_models.py` | ~380 | `indicators/ict_models.py` | MIGRATE |
| `indicators/smt_divergence.py` | ~310 | `indicators/smt_divergence.py` | MIGRATE |
| `indicators/ib_width.py` | ~310 | `indicators/ib_width.py` | MIGRATE |
| `indicators/value_area.py` | ~350 | `indicators/value_area.py` | MIGRATE |

---

## Interface: technical.py

```python
# packages/rockit-core/src/rockit_core/indicators/technical.py

"""Standard technical indicators: EMA, VWAP, ATR, RSI.

Source: BookMapOrderFlowStudies/indicators/technical.py (~130 LOC)
Migration: MIGRATE as-is

All functions operate on pandas Series or DataFrames and return
pandas Series. They are called during session context building
by the backtest engine.

Dependencies: pandas, numpy
"""

import pandas as pd
import numpy as np


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Compute Exponential Moving Average.

    Args:
        series: Price series (typically close prices).
        period: EMA period (e.g., 20, 50, 200).

    Returns:
        pd.Series with EMA values. First (period-1) values are NaN.
    """
    return series.ewm(span=period, adjust=False).mean()


def compute_vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
) -> pd.Series:
    """Compute Volume Weighted Average Price (session VWAP).

    VWAP resets at session start. Caller must pass single-session data.

    Args:
        high: Bar highs.
        low: Bar lows.
        close: Bar closes.
        volume: Bar volumes.

    Returns:
        pd.Series with cumulative VWAP values.
    """
    typical_price = (high + low + close) / 3.0
    cum_tp_vol = (typical_price * volume).cumsum()
    cum_vol = volume.cumsum()
    return cum_tp_vol / cum_vol.replace(0, np.nan)


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Compute Average True Range.

    Args:
        high: Bar highs.
        low: Bar lows.
        close: Bar closes.
        period: ATR period (default 14).

    Returns:
        pd.Series with ATR values. First (period) values are NaN.
    """
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Compute Relative Strength Index.

    Args:
        series: Price series (typically close prices).
        period: RSI period (default 14).

    Returns:
        pd.Series with RSI values (0-100).
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))
```

---

## Interface: ict_models.py

```python
# packages/rockit-core/src/rockit_core/indicators/ict_models.py

"""ICT (Inner Circle Trader) model detection.

Source: BookMapOrderFlowStudies/indicators/ict_models.py (~380 LOC)
Migration: MIGRATE as-is

Detects: FVG, IFVG, BPR, MSS, CSS, OTE zones on bar data.
These structures populate session_context.fvgs, .ifvgs, .bprs, .mss_levels
for use by entry models and strategies.

Dependencies: pandas
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class FairValueGap:
    """A Fair Value Gap (3-candle imbalance)."""
    high: float             # Upper boundary
    low: float              # Lower boundary
    direction: str          # "bullish" | "bearish"
    timeframe: str          # "5m" | "15m" | "1h" | "4h"
    bar_index: int          # Index of middle candle
    filled: bool = False    # Whether price has returned to fill the gap


@dataclass
class MarketStructureShift:
    """A Market Structure Shift (break of recent swing)."""
    price: float            # Break level
    direction: str          # "bullish" | "bearish"
    bar_index: int
    swing_high: float = 0.0
    swing_low: float = 0.0


def detect_fvg(
    bars: pd.DataFrame,
    timeframe: str = "5m",
    lookback: int = 50,
) -> list[FairValueGap]:
    """Detect Fair Value Gaps in bar data.

    A bullish FVG exists when bar[i-1].high < bar[i+1].low (gap up).
    A bearish FVG exists when bar[i-1].low > bar[i+1].high (gap down).

    Args:
        bars: DataFrame with open, high, low, close columns.
        timeframe: Label for the timeframe being analyzed.
        lookback: Number of bars to scan backward.

    Returns:
        List of FairValueGap objects found.
    """
    ...


def detect_ifvg(
    bars: pd.DataFrame,
    existing_fvgs: list[FairValueGap],
) -> list[FairValueGap]:
    """Detect Inverse FVGs (FVGs that have been fully filled then act as support/resistance).

    An IFVG is a previously bearish FVG that was filled and now acts as support,
    or a previously bullish FVG that was filled and now acts as resistance.

    Args:
        bars: Current bar data.
        existing_fvgs: Previously detected FVGs.

    Returns:
        List of IFVG objects (repurposed FairValueGap with filled=True).
    """
    ...


def detect_bpr(
    bars: pd.DataFrame,
    fvgs: list[FairValueGap],
) -> list[dict]:
    """Detect Balanced Price Ranges (overlapping bullish and bearish FVGs).

    A BPR exists when a bullish FVG and bearish FVG overlap in price.
    The overlap zone is a high-probability reversal area.

    Args:
        bars: Current bar data.
        fvgs: All detected FVGs.

    Returns:
        List of BPR dicts: {"high": float, "low": float, "bull_fvg": FVG, "bear_fvg": FVG}
    """
    ...


def detect_mss(
    bars: pd.DataFrame,
    lookback: int = 20,
) -> list[MarketStructureShift]:
    """Detect Market Structure Shifts.

    A bullish MSS occurs when price breaks above a recent swing high
    after making a lower low. A bearish MSS is the opposite.

    Args:
        bars: DataFrame with OHLC data.
        lookback: Number of bars to scan for swing points.

    Returns:
        List of MarketStructureShift objects.
    """
    ...


def detect_css(
    bars: pd.DataFrame,
    lookback: int = 20,
) -> list[dict]:
    """Detect Change in State of Delivery (CSS).

    CSS marks a transition from one market state to another
    (e.g., from distribution to accumulation).

    Args:
        bars: DataFrame with OHLC and volume data.
        lookback: Number of bars to analyze.

    Returns:
        List of CSS dicts: {"price": float, "direction": str, "bar_index": int}
    """
    ...


def compute_ote_zone(
    swing_high: float,
    swing_low: float,
    direction: str,
) -> tuple[float, float]:
    """Compute Optimal Trade Entry zone (62%-79% Fibonacci retracement).

    Args:
        swing_high: Recent swing high price.
        swing_low: Recent swing low price.
        direction: "bullish" (retrace down from high) or "bearish" (retrace up from low).

    Returns:
        Tuple of (ote_low, ote_high) price levels.
    """
    fib_range = swing_high - swing_low
    if direction == "bullish":
        ote_high = swing_high - (0.62 * fib_range)
        ote_low = swing_high - (0.79 * fib_range)
    else:
        ote_low = swing_low + (0.62 * fib_range)
        ote_high = swing_low + (0.79 * fib_range)
    return (ote_low, ote_high)
```

---

## Interface: smt_divergence.py

```python
# packages/rockit-core/src/rockit_core/indicators/smt_divergence.py

"""Smart Money Theory cross-market divergence detection.

Source: BookMapOrderFlowStudies/indicators/smt_divergence.py (~310 LOC)
Migration: MIGRATE as-is

Detects divergences between correlated instruments:
- NQ vs ES: NASDAQ vs S&P (high correlation)
- NQ vs YM: NASDAQ vs Dow (moderate correlation)

A bearish SMT: NQ makes new high, ES/YM does not.
A bullish SMT: NQ makes new low, ES/YM does not.

Dependencies: pandas
"""

from dataclasses import dataclass

import pandas as pd


@dataclass
class SMTDivergence:
    """A detected cross-market divergence."""
    primary_instrument: str      # "NQ"
    secondary_instrument: str    # "ES" or "YM"
    direction: str               # "bullish" | "bearish"
    primary_level: float         # Price level on primary
    secondary_level: float       # Price level on secondary
    bar_index: int
    strength: str = "standard"   # "standard" | "confirmed" (both ES and YM diverge)


def detect_smt_divergence(
    primary_bars: pd.DataFrame,
    secondary_bars: pd.DataFrame,
    primary_instrument: str = "NQ",
    secondary_instrument: str = "ES",
    lookback: int = 20,
    swing_threshold: float = 3.0,
) -> list[SMTDivergence]:
    """Detect SMT divergence between two correlated instruments.

    Scans for instances where primary makes a new swing high/low
    but secondary fails to confirm.

    Args:
        primary_bars: OHLC data for primary instrument (e.g., NQ).
        secondary_bars: OHLC data for secondary instrument (e.g., ES).
        primary_instrument: Name of primary instrument.
        secondary_instrument: Name of secondary instrument.
        lookback: Number of bars to scan for swing points.
        swing_threshold: Minimum point threshold for a valid swing.

    Returns:
        List of SMTDivergence objects detected.
    """
    ...


def detect_confirmed_smt(
    nq_bars: pd.DataFrame,
    es_bars: pd.DataFrame,
    ym_bars: pd.DataFrame,
    lookback: int = 20,
) -> list[SMTDivergence]:
    """Detect confirmed SMT where both ES and YM diverge from NQ.

    Stronger signal than single-instrument divergence.

    Args:
        nq_bars: NQ OHLC data.
        es_bars: ES OHLC data.
        ym_bars: YM OHLC data.
        lookback: Number of bars to scan.

    Returns:
        List of SMTDivergence with strength="confirmed".
    """
    ...
```

---

## Interface: ib_width.py

```python
# packages/rockit-core/src/rockit_core/indicators/ib_width.py

"""Initial Balance width analysis and classification.

Source: BookMapOrderFlowStudies/indicators/ib_width.py (~310 LOC)
Migration: MIGRATE as-is

Classifies the IB range relative to ATR and historical norms.
Used by strategies to adjust behavior on narrow vs wide IB days.

Dependencies: pandas, numpy
"""

from dataclasses import dataclass

import pandas as pd
import numpy as np


@dataclass
class IBWidthAnalysis:
    """Analysis of the Initial Balance width."""
    ib_range: float                 # IB high - IB low in points
    ib_range_pct_of_atr: float      # IB range as % of ATR(14)
    classification: str             # "narrow" | "normal" | "wide" | "extreme"
    percentile: float               # Percentile rank vs recent 20 sessions
    historical_avg: float           # Average IB range over lookback period
    z_score: float                  # Standard deviations from mean


def classify_ib_width(
    ib_range: float,
    atr: float,
    recent_ib_ranges: list[float] | None = None,
) -> IBWidthAnalysis:
    """Classify the IB range relative to ATR and history.

    Classification thresholds (% of ATR):
    - Narrow: < 40% of ATR
    - Normal: 40-80% of ATR
    - Wide: 80-120% of ATR
    - Extreme: > 120% of ATR

    Args:
        ib_range: Current session IB range in points.
        atr: ATR(14) value.
        recent_ib_ranges: Optional list of recent session IB ranges
                          for percentile and z-score calculations.

    Returns:
        IBWidthAnalysis with classification and statistics.
    """
    ...


def compute_ib_extension(
    current_price: float,
    ib_high: float,
    ib_low: float,
    ib_range: float,
) -> dict:
    """Compute IB extension metrics.

    Args:
        current_price: Current price.
        ib_high: IB high.
        ib_low: IB low.
        ib_range: IB range.

    Returns:
        Dict with:
        - extension_above: points above IBH (0 if below)
        - extension_below: points below IBL (0 if above)
        - extension_multiple: max extension / ib_range
        - direction: "above" | "below" | "inside"
    """
    ...


def ib_acceptance_check(
    bars: pd.DataFrame,
    ib_high: float,
    ib_low: float,
    acceptance_bars: int = 3,
) -> dict:
    """Check for IB high/low acceptance (price staying beyond boundary).

    Acceptance = price closes beyond IBH/IBL for N consecutive bars.

    Args:
        bars: Post-IB bar data.
        ib_high: IB high price.
        ib_low: IB low price.
        acceptance_bars: Number of consecutive bars needed for acceptance.

    Returns:
        Dict with:
        - ibh_accepted: bool
        - ibl_accepted: bool
        - ibh_acceptance_bar: int (bar index) or None
        - ibl_acceptance_bar: int (bar index) or None
    """
    ...
```

---

## Interface: value_area.py

```python
# packages/rockit-core/src/rockit_core/indicators/value_area.py

"""Value Area computation using the 70% rule.

Source: BookMapOrderFlowStudies/indicators/value_area.py (~350 LOC)
Migration: MIGRATE as-is

Computes VAH, VAL, and value area percentage for a given
volume distribution. Used for both current session and prior
session levels.

Dependencies: pandas, numpy
"""

from dataclasses import dataclass

import pandas as pd
import numpy as np


@dataclass
class ValueArea:
    """Value Area result."""
    vah: float              # Value Area High
    val: float              # Value Area Low
    poc: float              # Point of Control (highest volume price)
    value_area_pct: float   # Actual percentage of volume in VA (target: 70%)
    total_volume: float
    price_levels: int       # Number of price levels in distribution


def compute_value_area(
    prices: pd.Series,
    volumes: pd.Series,
    tick_size: float = 0.25,
    target_pct: float = 0.70,
) -> ValueArea:
    """Compute Value Area using the 70% rule.

    1. Build volume-at-price histogram
    2. Find POC (price with highest volume)
    3. Expand symmetrically from POC until 70% of total volume is captured
    4. VAH = upper boundary, VAL = lower boundary

    Args:
        prices: Price series (close or typical price).
        volumes: Corresponding volume series.
        tick_size: Price granularity for histogram bins.
        target_pct: Target volume percentage (default 70%).

    Returns:
        ValueArea with VAH, VAL, POC, and volume percentage.
    """
    ...


def compute_prior_session_value_area(
    prior_bars: pd.DataFrame,
    tick_size: float = 0.25,
) -> ValueArea:
    """Compute value area for the prior trading session.

    Convenience wrapper that extracts prices/volumes from a DataFrame.

    Args:
        prior_bars: Prior session bar data with close, volume columns.
        tick_size: Price granularity.

    Returns:
        ValueArea for the prior session.
    """
    ...


def check_80_percent_rule(
    open_price: float,
    value_area: ValueArea,
) -> dict:
    """Check the 80% rule for session open relative to value area.

    If price opens outside VA and rotates back inside, there is an
    80% probability of price reaching the other side of VA.

    Args:
        open_price: Session open price.
        value_area: Prior session ValueArea.

    Returns:
        Dict with:
        - rule_active: bool (open is outside VA)
        - direction: "long" | "short" | None
        - target: float (opposite VA boundary) or None
        - open_location: "above_vah" | "below_val" | "inside_va"
    """
    ...
```

---

## How Indicators Populate SessionContext

```python
# Called by BacktestEngine._build_session_context()

def populate_indicators(bars: pd.DataFrame, context: dict) -> dict:
    """Compute all indicators and add to session context.

    Called once during session initialization with IB bars,
    then incrementally updated on each post-IB bar.
    """
    from rockit_core.indicators.technical import compute_ema, compute_vwap, compute_atr, compute_rsi
    from rockit_core.indicators.ib_width import classify_ib_width, compute_ib_extension
    from rockit_core.indicators.value_area import compute_value_area
    from rockit_core.indicators.ict_models import detect_fvg, detect_mss

    close = bars["close"]
    context["ema20"] = compute_ema(close, 20).iloc[-1]
    context["ema50"] = compute_ema(close, 50).iloc[-1]
    context["ema200"] = compute_ema(close, 200).iloc[-1]
    context["vwap"] = compute_vwap(bars["high"], bars["low"], close, bars["volume"]).iloc[-1]
    context["atr14"] = compute_atr(bars["high"], bars["low"], close, 14).iloc[-1]
    context["rsi14"] = compute_rsi(close, 14).iloc[-1]

    context["ib_width_analysis"] = classify_ib_width(
        context["ib_range"], context["atr14"],
    )
    context["fvgs"] = detect_fvg(bars)
    context["mss_levels"] = detect_mss(bars)

    return context
```

---

## Data Flow

```
Raw Bar Data (pd.DataFrame)
    │
    ├──► technical.py
    │       ├── compute_ema(close, 20) ──► ema20
    │       ├── compute_ema(close, 50) ──► ema50
    │       ├── compute_vwap() ──► vwap
    │       ├── compute_atr() ──► atr14
    │       └── compute_rsi() ──► rsi14
    │
    ├──► ict_models.py
    │       ├── detect_fvg() ──► fvgs list
    │       ├── detect_ifvg() ──► ifvgs list
    │       ├── detect_bpr() ──► bprs list
    │       ├── detect_mss() ──► mss_levels list
    │       └── compute_ote_zone() ──► (ote_low, ote_high)
    │
    ├──► smt_divergence.py (requires cross-market data)
    │       └── detect_smt_divergence() ──► divergences list
    │
    ├──► ib_width.py
    │       ├── classify_ib_width() ──► IBWidthAnalysis
    │       ├── compute_ib_extension() ──► extension dict
    │       └── ib_acceptance_check() ──► acceptance dict
    │
    └──► value_area.py
            ├── compute_value_area() ──► current session VA
            ├── compute_prior_session_value_area() ──► prior VA
            └── check_80_percent_rule() ──► 80% rule dict
    │
    ▼
session_context dict (consumed by strategies, filters, trade models)
```

---

## Dependencies

| This module | Depends on |
|-------------|-----------|
| `indicators/technical.py` | `pandas`, `numpy` |
| `indicators/ict_models.py` | `pandas` |
| `indicators/smt_divergence.py` | `pandas` |
| `indicators/ib_width.py` | `pandas`, `numpy` |
| `indicators/value_area.py` | `pandas`, `numpy` |

No dependencies on other rockit-core modules. Indicators are leaf-level computations.

---

## Metrics Emitted

Indicators are pure functions and do not directly emit metrics. The backtest engine records indicator computation time as engine-level metrics:

| Metric | Layer | When |
|--------|-------|------|
| `engine.indicators_computed` | engine | All indicators computed for a session |
| `engine.indicator_duration_ms` | engine | Time to compute all indicators (if metrics enabled) |

---

## Migration Notes

1. **No logic changes.** All indicator computations are migrated as-is from BookMapOrderFlowStudies. The mathematical formulas (EMA, VWAP, ATR, RSI, FVG detection, etc.) must produce identical results.

2. **SMT divergence requires cross-market data.** In the current codebase, NQ-only backtests cannot use SMT divergence. When ES/YM data is available (loaded alongside NQ), SMT divergence is computed. The indicator returns an empty list if secondary data is not available.

3. **value_area.py is shared with profile/volume_profile.py.** Both compute value areas, but `value_area.py` operates on raw bar data while `volume_profile.py` operates on volume-at-price distributions. They are complementary, not duplicates.

4. **ict_models.py overlaps with deterministic/modules/fvg_detection.py.** The `ict_models.py` version is the canonical one for the backtest engine. The deterministic module wraps it for snapshot generation. See [10-deterministic-modules.md](10-deterministic-modules.md) for deduplication details.

---

## Test Contract

1. **EMA/VWAP/ATR/RSI** — compute against known data, compare to reference values (e.g., TradingView or pandas-ta)
2. **FVG detection** — construct bar data with known FVGs, verify detection
3. **MSS detection** — construct swing pattern, verify break detected
4. **OTE zone** — given swing high/low, verify 62-79% zone prices
5. **SMT divergence** — construct two-instrument data with known divergence
6. **IB width classification** — known IB range and ATR, verify classification
7. **Value area** — known volume distribution, verify VAH/VAL/POC match hand calculation
8. **80% rule** — open above VAH, verify long target = VAL

See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#indicators)
