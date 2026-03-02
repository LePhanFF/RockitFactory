# Technical Design: Data Loading & Configuration

> **Package:** `rockit-core/data/` + `rockit-core/config/`
> **Type:** MIGRATE from BookMapOrderFlowStudies/data/ + BookMapOrderFlowStudies/config/
> **Source files:** 3 data files + 2 config files, ~450 LOC total
> **Tests:** See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#data)

---

## Purpose

Data loading handles ingestion of NinjaTrader volumetric CSV exports into pandas DataFrames. Feature engineering derives order flow features, IB metrics, day type labels, and ICT features from raw bar data. Session utilities detect RTH boundaries and group bars by trading session. Configuration provides instrument specifications and runtime constants.

---

## Source Files (Being Migrated)

### Data (BookMapOrderFlowStudies/data/)

| File | LOC | Destination | Type |
|------|-----|-------------|------|
| `data/loader.py` | ~120 | `data/loader.py` | MIGRATE |
| `data/features.py` | ~180 | `data/features.py` | MIGRATE |
| `data/session.py` | ~80 | `data/session.py` | MIGRATE |

### Config (BookMapOrderFlowStudies/config/)

| File | LOC | Destination | Type |
|------|-----|-------------|------|
| `config/constants.py` | 72 | `config/constants.py` | MIGRATE + EXTEND |
| `config/instruments.py` | 42 | `config/instruments.py` | MIGRATE + EXTEND |

---

## Interface: loader.py

```python
# packages/rockit-core/src/rockit_core/data/loader.py

"""CSV loader for NinjaTrader volumetric bar exports.

Source: BookMapOrderFlowStudies/data/loader.py (~120 LOC)
Migration: MIGRATE — add metrics, validation, GCS support path

Loads CSV files exported from NinjaTrader with OHLCV + volumetric
columns (bid/ask volume, delta, CVD) and optional indicator columns.

Dependencies: pandas
"""

from pathlib import Path
from typing import Any

import pandas as pd

from rockit_core.metrics import MetricsCollector, MetricEvent, NullCollector


def load_csv(
    filepath: str | Path,
    instrument: str = "NQ",
    metrics: MetricsCollector | None = None,
) -> pd.DataFrame:
    """Load a NinjaTrader volumetric CSV export.

    Expected CSV columns:
    - Date, Time (or combined DateTime/Timestamp)
    - Open, High, Low, Close
    - Volume
    - Vol_Ask (ask volume), Vol_Bid (bid volume)
    - Delta (buy - sell volume per bar)
    - CVD (cumulative volume delta, may need recomputation)

    Optional columns (if present, used as-is; if absent, computed):
    - VWAP, EMA20, EMA50, EMA200, RSI14, ATR14

    Args:
        filepath: Path to CSV file.
        instrument: Instrument name for metadata (default "NQ").
        metrics: Optional metrics collector.

    Returns:
        pd.DataFrame with standardized column names:
        timestamp, open, high, low, close, volume,
        vol_ask, vol_bid, delta, cvd
        Plus any available indicator columns.

    Raises:
        FileNotFoundError: If filepath does not exist.
        DataLoadError: If CSV is malformed or missing required columns.
    """
    collector = metrics or NullCollector()
    path = Path(filepath)

    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    df = pd.read_csv(path)
    df = _standardize_columns(df)
    df = _parse_timestamps(df)
    df = _validate_required_columns(df)
    df = _compute_derived_columns(df)

    collector.record(MetricEvent(
        timestamp=df["timestamp"].iloc[0].isoformat() if not df.empty else "",
        layer="infra",
        component="csv_loader",
        metric="csv_rows_loaded",
        value=float(len(df)),
        context={"filepath": str(path), "instrument": instrument},
    ))

    return df


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names to lowercase snake_case.

    Handles various NinjaTrader export formats:
    - "Date" → "date", "Time" → "time"
    - "Open" → "open", "High" → "high", etc.
    - "Vol Ask" or "VolAsk" or "vol_ask" → "vol_ask"
    """
    column_map = {
        "Date": "date",
        "Time": "time",
        "DateTime": "datetime",
        "Timestamp": "timestamp",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
        "Vol Ask": "vol_ask",
        "VolAsk": "vol_ask",
        "Vol Bid": "vol_bid",
        "VolBid": "vol_bid",
        "Delta": "delta",
        "CVD": "cvd",
        "VWAP": "vwap",
    }
    df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})
    df.columns = df.columns.str.lower().str.replace(" ", "_")
    return df


def _parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """Parse and create a unified timestamp column.

    Handles:
    - Combined "timestamp" or "datetime" column
    - Separate "date" + "time" columns
    """
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    elif "datetime" in df.columns:
        df["timestamp"] = pd.to_datetime(df["datetime"])
    elif "date" in df.columns and "time" in df.columns:
        df["timestamp"] = pd.to_datetime(df["date"] + " " + df["time"])
    else:
        raise DataLoadError("No timestamp column found. Expected 'timestamp', 'datetime', or 'date'+'time'.")
    return df


def _validate_required_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Verify required columns exist."""
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise DataLoadError(f"Missing required columns: {missing}")
    return df


def _compute_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Compute derived columns if not present in CSV.

    - delta: vol_ask - vol_bid (if vol_ask and vol_bid present)
    - cvd: cumulative sum of delta
    """
    if "delta" not in df.columns and "vol_ask" in df.columns and "vol_bid" in df.columns:
        df["delta"] = df["vol_ask"] - df["vol_bid"]
    if "cvd" not in df.columns and "delta" in df.columns:
        df["cvd"] = df["delta"].cumsum()
    return df


class DataLoadError(Exception):
    """Raised when CSV data is malformed or missing required columns."""
    pass
```

---

## Interface: features.py

```python
# packages/rockit-core/src/rockit_core/data/features.py

"""Feature engineering from raw bar data.

Source: BookMapOrderFlowStudies/data/features.py (~180 LOC)
Migration: MIGRATE as-is

Computes derived features used by strategies and the backtest engine:
- Order flow features (delta ratio, CVD slope, volume profile)
- IB features (IB range, extensions, acceptance)
- Day type features (classification inputs)
- ICT features (FVG presence, MSS proximity, OTE zones)

Dependencies: pandas, numpy, indicators/technical.py, indicators/ict_models.py
"""

import pandas as pd
import numpy as np


def compute_order_flow_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add order flow feature columns to DataFrame.

    New columns:
    - delta_ratio: delta / volume (normalized delta)
    - delta_ma5: 5-bar moving average of delta
    - cvd_slope: slope of CVD over last 10 bars
    - cvd_trend: "up" | "down" | "flat" based on cvd_slope
    - volume_ma20: 20-bar volume moving average
    - relative_volume: volume / volume_ma20

    Args:
        df: DataFrame with delta, cvd, volume columns.

    Returns:
        DataFrame with new order flow columns added.
    """
    df["delta_ratio"] = df["delta"] / df["volume"].replace(0, np.nan)
    df["delta_ma5"] = df["delta"].rolling(5).mean()

    # CVD slope: linear regression slope over last 10 bars
    df["cvd_slope"] = df["cvd"].rolling(10).apply(
        lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) == 10 else 0,
        raw=False,
    )
    df["cvd_trend"] = df["cvd_slope"].apply(
        lambda s: "up" if s > 0.5 else ("down" if s < -0.5 else "flat")
    )

    df["volume_ma20"] = df["volume"].rolling(20).mean()
    df["relative_volume"] = df["volume"] / df["volume_ma20"].replace(0, np.nan)

    return df


def compute_ib_features(
    df: pd.DataFrame,
    ib_high: float,
    ib_low: float,
) -> pd.DataFrame:
    """Add IB-relative feature columns.

    New columns:
    - ib_range: constant (ib_high - ib_low)
    - price_vs_ib: "above" | "inside" | "below"
    - ib_extension_up: max(0, high - ib_high) / ib_range
    - ib_extension_down: max(0, ib_low - low) / ib_range

    Args:
        df: DataFrame with high, low, close columns.
        ib_high: Initial Balance high price.
        ib_low: Initial Balance low price.

    Returns:
        DataFrame with new IB feature columns.
    """
    ib_range = ib_high - ib_low
    df["ib_range"] = ib_range

    df["price_vs_ib"] = df["close"].apply(
        lambda p: "above" if p > ib_high else ("below" if p < ib_low else "inside")
    )

    df["ib_extension_up"] = (df["high"] - ib_high).clip(lower=0) / max(ib_range, 0.01)
    df["ib_extension_down"] = (ib_low - df["low"]).clip(lower=0) / max(ib_range, 0.01)

    return df


def compute_day_type_features(
    df: pd.DataFrame,
    ib_high: float,
    ib_low: float,
    atr: float,
) -> pd.DataFrame:
    """Add day type classification feature columns.

    New columns:
    - ib_pct_of_atr: ib_range / atr * 100
    - session_range_vs_ib: (session_high - session_low) / ib_range
    - directional_bias: (close - open) / atr (session open to current close)

    Args:
        df: DataFrame with OHLC columns.
        ib_high: IB high.
        ib_low: IB low.
        atr: ATR(14) value.

    Returns:
        DataFrame with day type feature columns.
    """
    ib_range = ib_high - ib_low
    df["ib_pct_of_atr"] = (ib_range / max(atr, 0.01)) * 100

    session_high = df["high"].expanding().max()
    session_low = df["low"].expanding().min()
    df["session_range_vs_ib"] = (session_high - session_low) / max(ib_range, 0.01)

    session_open = df["open"].iloc[0]
    df["directional_bias"] = (df["close"] - session_open) / max(atr, 0.01)

    return df


def compute_ict_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add ICT structure presence features.

    New columns:
    - has_fvg_bullish: bool (bullish FVG detected in last 10 bars)
    - has_fvg_bearish: bool (bearish FVG detected in last 10 bars)
    - nearest_mss_distance: distance to nearest MSS level in points

    Dependencies: indicators/ict_models.py

    Args:
        df: DataFrame with OHLC columns.

    Returns:
        DataFrame with ICT feature columns.
    """
    from rockit_core.indicators.ict_models import detect_fvg, detect_mss

    fvgs = detect_fvg(df, lookback=10)
    df["has_fvg_bullish"] = any(f.direction == "bullish" for f in fvgs)
    df["has_fvg_bearish"] = any(f.direction == "bearish" for f in fvgs)

    mss_levels = detect_mss(df, lookback=20)
    if mss_levels:
        current_price = df["close"].iloc[-1]
        df["nearest_mss_distance"] = min(
            abs(current_price - m.price) for m in mss_levels
        )
    else:
        df["nearest_mss_distance"] = np.nan

    return df
```

---

## Interface: session.py

```python
# packages/rockit-core/src/rockit_core/data/session.py

"""Session boundary detection and grouping.

Source: BookMapOrderFlowStudies/data/session.py (~80 LOC)
Migration: MIGRATE as-is

Identifies RTH (Regular Trading Hours) session boundaries in bar data
and groups bars by trading date. Handles overnight bars and premarket.

Dependencies: pandas
"""

import pandas as pd


def detect_sessions(
    df: pd.DataFrame,
    rth_start: str = "09:30",
    rth_end: str = "16:00",
) -> list[tuple[str, pd.DataFrame]]:
    """Group bars into RTH trading sessions.

    Args:
        df: DataFrame with timestamp column.
        rth_start: RTH start time "HH:MM" ET.
        rth_end: RTH end time "HH:MM" ET.

    Returns:
        List of (session_date_str, session_dataframe) tuples.
        Each DataFrame contains only bars within RTH for that date.
    """
    df = df.copy()
    df["session_date"] = df["timestamp"].dt.date.astype(str)
    df["time_str"] = df["timestamp"].dt.strftime("%H:%M")

    # Filter to RTH only
    rth_mask = (df["time_str"] >= rth_start) & (df["time_str"] <= rth_end)
    rth_df = df[rth_mask]

    sessions = []
    for date, group in rth_df.groupby("session_date"):
        sessions.append((date, group.reset_index(drop=True)))

    return sessions


def split_ib_bars(
    session_bars: pd.DataFrame,
    ib_duration_minutes: int = 60,
    rth_start: str = "09:30",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split session bars into IB and post-IB groups.

    IB = first ib_duration_minutes of RTH (default: 09:30-10:30).

    Args:
        session_bars: Single-session DataFrame with timestamp column.
        ib_duration_minutes: IB duration in minutes.
        rth_start: RTH start time.

    Returns:
        Tuple of (ib_bars, post_ib_bars) DataFrames.
    """
    ib_end_hour = int(rth_start.split(":")[0])
    ib_end_minute = int(rth_start.split(":")[1]) + ib_duration_minutes
    if ib_end_minute >= 60:
        ib_end_hour += ib_end_minute // 60
        ib_end_minute = ib_end_minute % 60
    ib_end = f"{ib_end_hour:02d}:{ib_end_minute:02d}"

    time_str = session_bars["timestamp"].dt.strftime("%H:%M")
    ib_mask = time_str <= ib_end
    ib_bars = session_bars[ib_mask].reset_index(drop=True)
    post_ib_bars = session_bars[~ib_mask].reset_index(drop=True)

    return ib_bars, post_ib_bars


def get_prior_session(
    sessions: list[tuple[str, pd.DataFrame]],
    current_index: int,
) -> pd.DataFrame | None:
    """Get the prior trading session's bars.

    Args:
        sessions: List of (date, bars) tuples from detect_sessions.
        current_index: Index of current session.

    Returns:
        Prior session DataFrame, or None if current is first session.
    """
    if current_index <= 0:
        return None
    return sessions[current_index - 1][1]


def filter_sessions_by_date(
    sessions: list[tuple[str, pd.DataFrame]],
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[tuple[str, pd.DataFrame]]:
    """Filter sessions to a date range.

    Args:
        sessions: List of (date, bars) tuples.
        start_date: Inclusive start date "YYYY-MM-DD" or None.
        end_date: Inclusive end date "YYYY-MM-DD" or None.

    Returns:
        Filtered list of sessions.
    """
    result = sessions
    if start_date:
        result = [(d, b) for d, b in result if d >= start_date]
    if end_date:
        result = [(d, b) for d, b in result if d <= end_date]
    return result
```

---

## Interface: InstrumentSpec & Constants

```python
# packages/rockit-core/src/rockit_core/config/instruments.py

"""Instrument specifications.

Source: BookMapOrderFlowStudies/config/instruments.py (42 LOC)
Migration: MIGRATE + EXTEND — add YAML loading fallback

Provides InstrumentSpec dataclass with point values, tick sizes,
commission, and risk defaults. Can be instantiated from YAML config
or from hardcoded defaults (backward compatibility).

Dependencies: none (stdlib only)
"""

from dataclasses import dataclass


@dataclass
class InstrumentSpec:
    """Specification for a futures instrument."""
    symbol: str
    full_name: str
    point_value: float          # Dollar value per point
    tick_size: float            # Minimum price increment
    tick_value: float           # Dollar value per tick
    commission_per_contract: float
    slippage_ticks: int = 1
    max_contracts: int = 30
    max_daily_loss: float = 2000.0
    max_risk_per_trade: float = 400.0


# Hardcoded defaults (backward compatibility)
NQ_SPEC = InstrumentSpec(
    symbol="NQ", full_name="E-mini NASDAQ 100",
    point_value=20.0, tick_size=0.25, tick_value=5.0,
    commission_per_contract=2.05, slippage_ticks=1,
    max_contracts=30, max_daily_loss=2000.0, max_risk_per_trade=400.0,
)

MNQ_SPEC = InstrumentSpec(
    symbol="MNQ", full_name="Micro E-mini NASDAQ 100",
    point_value=2.0, tick_size=0.25, tick_value=0.50,
    commission_per_contract=0.62, slippage_ticks=1,
    max_contracts=100, max_daily_loss=500.0, max_risk_per_trade=100.0,
)

ES_SPEC = InstrumentSpec(
    symbol="ES", full_name="E-mini S&P 500",
    point_value=50.0, tick_size=0.25, tick_value=12.50,
    commission_per_contract=2.05, slippage_ticks=1,
    max_contracts=20, max_daily_loss=2000.0, max_risk_per_trade=500.0,
)

MES_SPEC = InstrumentSpec(
    symbol="MES", full_name="Micro E-mini S&P 500",
    point_value=5.0, tick_size=0.25, tick_value=1.25,
    commission_per_contract=0.62, slippage_ticks=1,
    max_contracts=100, max_daily_loss=500.0, max_risk_per_trade=100.0,
)

YM_SPEC = InstrumentSpec(
    symbol="YM", full_name="Mini Dow Jones",
    point_value=5.0, tick_size=1.0, tick_value=5.0,
    commission_per_contract=2.05, slippage_ticks=1,
    max_contracts=20, max_daily_loss=2000.0, max_risk_per_trade=400.0,
)

MYM_SPEC = InstrumentSpec(
    symbol="MYM", full_name="Micro Mini Dow Jones",
    point_value=0.50, tick_size=1.0, tick_value=0.50,
    commission_per_contract=0.62, slippage_ticks=1,
    max_contracts=100, max_daily_loss=500.0, max_risk_per_trade=100.0,
)

INSTRUMENTS: dict[str, InstrumentSpec] = {
    "NQ": NQ_SPEC,
    "MNQ": MNQ_SPEC,
    "ES": ES_SPEC,
    "MES": MES_SPEC,
    "YM": YM_SPEC,
    "MYM": MYM_SPEC,
}


def get_instrument(name: str) -> InstrumentSpec:
    """Get instrument spec by symbol name.

    Tries YAML config first (if available), falls back to hardcoded.

    Args:
        name: Instrument symbol (e.g., "NQ", "ES").

    Returns:
        InstrumentSpec for the instrument.

    Raises:
        KeyError: If instrument not found.
    """
    if name not in INSTRUMENTS:
        raise KeyError(f"Unknown instrument: {name}. Available: {list(INSTRUMENTS.keys())}")
    return INSTRUMENTS[name]
```

```python
# packages/rockit-core/src/rockit_core/config/constants.py

"""Runtime constants and thresholds.

Source: BookMapOrderFlowStudies/config/constants.py (72 LOC)
Migration: MIGRATE + EXTEND — values will eventually come from YAML

All constants are module-level variables that can be overridden
by YAML config. Default values match the current BookMapOrderFlowStudies
behavior.
"""

# Session times (Eastern Time)
RTH_START = "09:30"
RTH_END = "16:00"
IB_DURATION_MINUTES = 60        # 09:30-10:30
IB_BARS = 12                    # 5-min bars in IB (60 min / 5 min)
PREMARKET_START = "04:00"

# Day type thresholds
IB_NARROW_THRESHOLD = 0.40      # IB range < 40% of ATR = narrow
IB_WIDE_THRESHOLD = 0.80        # IB range > 80% of ATR = wide
IB_EXTREME_THRESHOLD = 1.20     # IB range > 120% of ATR = extreme

TREND_EXTENSION_THRESHOLD = 1.0     # >= 1x IB range = strong trend
SUPER_TREND_THRESHOLD = 2.0         # >= 2x IB range = super trend

# Risk defaults
DEFAULT_MAX_CONTRACTS = 30
DEFAULT_MAX_DAILY_LOSS = 2000.0     # Dollars
DEFAULT_MAX_RISK_PER_TRADE = 400.0  # Dollars

# Order flow thresholds
DEFAULT_MIN_DELTA = 100.0
DEFAULT_MIN_VOLUME = 500

# Time restrictions
DEFAULT_EARLIEST_SIGNAL = "09:45"
DEFAULT_LATEST_SIGNAL = "15:30"

# Confidence thresholds
DEFAULT_CONFIDENCE_THRESHOLD = 0.60
HIGH_CONFIDENCE_THRESHOLD = 0.80
```

---

## Data Flow

```
NinjaTrader CSV Export
    │
    ▼
loader.load_csv(filepath)
    │
    ├──► _standardize_columns() ──► normalized column names
    ├──► _parse_timestamps() ──► unified timestamp column
    ├──► _validate_required_columns() ──► check OHLCV present
    └──► _compute_derived_columns() ──► delta, cvd if missing
    │
    ▼
pd.DataFrame (raw bars)
    │
    ├──► session.detect_sessions() ──► [(date, session_df), ...]
    │       └──► session.split_ib_bars() ──► ib_bars, post_ib_bars
    │
    ├──► features.compute_order_flow_features()
    │       └──► delta_ratio, cvd_slope, cvd_trend, relative_volume
    │
    ├──► features.compute_ib_features(ib_high, ib_low)
    │       └──► ib_range, price_vs_ib, ib_extension_up/down
    │
    ├──► features.compute_day_type_features(ib_high, ib_low, atr)
    │       └──► ib_pct_of_atr, session_range_vs_ib, directional_bias
    │
    └──► features.compute_ict_features()
            └──► has_fvg_bullish/bearish, nearest_mss_distance
    │
    ▼
Enriched DataFrame ──► BacktestEngine / Deterministic Orchestrator
```

---

## Dependencies

| This module | Depends on |
|-------------|-----------|
| `data/loader.py` | `pandas`, `metrics/` |
| `data/features.py` | `pandas`, `numpy`, `indicators/ict_models.py` |
| `data/session.py` | `pandas` |
| `config/instruments.py` | None (stdlib only) |
| `config/constants.py` | None (stdlib only) |

---

## Metrics Emitted

| Metric | Layer | When |
|--------|-------|------|
| `infra.csv_rows_loaded` | infra | CSV file loaded successfully |
| `infra.csv_load_error` | infra | CSV file failed to load |
| `infra.sessions_detected` | infra | Session boundaries detected |

---

## Migration Notes

1. **loader.py handles multiple NinjaTrader export formats.** Different NinjaTrader versions produce slightly different column names. The `_standardize_columns()` function normalizes them all.

2. **features.py computes on existing DataFrame columns.** It does not read external data. All features are derived from the bar data already loaded.

3. **session.py RTH boundaries are parameterized.** Default is 09:30-16:00 ET, but can be overridden for extended hours analysis.

4. **constants.py values will migrate to YAML.** During the transition, constants.py provides defaults. After YAML migration (see [02-config-schemas.md](02-config-schemas.md)), constants.py becomes a thin wrapper that reads from YAML with hardcoded fallbacks.

5. **InstrumentSpec vs InstrumentConfig.** The existing `InstrumentSpec` dataclass is preserved for backward compatibility. The pydantic `InstrumentConfig` from [02-config-schemas.md](02-config-schemas.md) is the new validation layer. A utility function converts between them.

6. **DataLoadError is new.** The original code used generic exceptions. The migration adds a specific exception class for CSV loading errors.

---

## Test Contract

1. **CSV loading** — load a known CSV file, verify row count, column names, data types
2. **Column normalization** — various NinjaTrader formats all produce same output schema
3. **Timestamp parsing** — separate date+time columns, combined datetime, various formats
4. **Missing columns** — CSV without required column raises DataLoadError
5. **Derived columns** — delta computed from vol_ask/vol_bid, cvd from cumulative delta
6. **Session detection** — multi-day CSV, verify correct session boundaries
7. **IB split** — verify first 60 minutes of bars are IB, rest are post-IB
8. **Order flow features** — verify delta_ratio, cvd_slope calculations on known data
9. **IB features** — verify ib_extension_up/down with known IB levels
10. **InstrumentSpec** — verify NQ spec values, get_instrument("NQ") returns correct spec

See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#data)
