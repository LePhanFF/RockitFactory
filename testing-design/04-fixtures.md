# Test Data & Fixtures

> **Purpose:** Define all test data needed to run the test suite
> **Principle:** Minimal fixtures for fast unit tests, real data for regression tests
> **Location:** `packages/{name}/tests/fixtures/` per package, shared data in `tests/shared_fixtures/`

---

## Fixture Organization

```
packages/rockit-core/tests/
├── conftest.py                           # Factory functions, shared pytest fixtures
├── fixtures/
│   ├── sessions/                         # Real session CSV files (10-20 sessions)
│   │   ├── 2026-01-15_NQ.csv            # Known trend-up day
│   │   ├── 2026-01-16_NQ.csv            # Known trend-down day
│   │   ├── 2026-01-22_NQ.csv            # Known B-Day
│   │   ├── 2026-01-28_NQ.csv            # Known P-Day
│   │   └── ...                           # ~40 sessions total
│   ├── snapshots/                        # Reference orchestrator output (JSON)
│   │   ├── 2026-01-15_1145_NQ.json
│   │   └── ...
│   ├── minimal/                          # Tiny DataFrames for unit tests
│   │   ├── 3_bar_fvg.csv                # 3 bars forming a bullish FVG
│   │   ├── 5_bar_mss.csv                # 5 bars with MSS
│   │   └── ib_only.csv                  # Just IB bars (9:30-10:30)
│   └── migration/                        # Outputs from original repos
│       ├── original_trend_bull_signals.json
│       └── original_backtest_trades.json

packages/rockit-pipeline/tests/
├── conftest.py
└── fixtures/
    ├── baselines/                        # Test baseline files
    │   └── test_baseline_v1.json
    ├── outcomes/                          # Outcome logger test data
    │   └── sample_outcomes.json
    └── training/                          # Training data samples
        └── sample_jsonl_5_examples.jsonl
```

---

## Session Fixtures: Known-Good Days by Type

Curate exactly 40 sessions: 10 per day type. These sessions are selected because
they are unambiguous examples of their day type, making them reliable for testing.

### Selection Criteria

- **Trend days:** IB extension > 1.5x, one-directional, strong delta confirmation
- **P-days:** Elongated profile, clear responsive activity at extreme
- **B-days:** Balanced profile, price rotates within value area
- **Neutral days:** Narrow IB, low range, no directional conviction

### Session List

```python
# packages/rockit-core/tests/conftest.py

KNOWN_SESSIONS: dict[str, list[str]] = {
    "trend_up": [
        "2026-01-15_NQ.csv",   # Strong trend, IBH extension 2.1x
        "2026-02-03_NQ.csv",   # Super trend, 3.0x extension
        "2026-02-10_NQ.csv",   # Trend with gap fill
        "2026-02-18_NQ.csv",   # Trend with strong CVD
        "2026-03-05_NQ.csv",   # Trend after FOMC
        "2025-11-12_NQ.csv",   # Clean trend, no news
        "2025-11-20_NQ.csv",   # Trend with pyramid opportunity
        "2025-12-02_NQ.csv",   # Trend from gap up
        "2025-12-10_NQ.csv",   # Trend with delta divergence resolved
        "2025-12-18_NQ.csv",   # Year-end trend day
    ],
    "trend_down": [
        "2026-01-16_NQ.csv",
        "2026-01-29_NQ.csv",
        "2026-02-06_NQ.csv",
        "2026-02-14_NQ.csv",
        "2026-02-25_NQ.csv",
        "2025-11-05_NQ.csv",
        "2025-11-18_NQ.csv",
        "2025-12-04_NQ.csv",
        "2025-12-15_NQ.csv",
        "2025-12-22_NQ.csv",
    ],
    "p_day": [
        "2026-01-28_NQ.csv",
        "2026-02-05_NQ.csv",
        "2026-02-12_NQ.csv",
        "2026-02-20_NQ.csv",
        "2026-02-27_NQ.csv",
        "2025-11-07_NQ.csv",
        "2025-11-14_NQ.csv",
        "2025-11-25_NQ.csv",
        "2025-12-08_NQ.csv",
        "2025-12-19_NQ.csv",
    ],
    "b_day": [
        "2026-01-22_NQ.csv",
        "2026-01-30_NQ.csv",
        "2026-02-07_NQ.csv",
        "2026-02-13_NQ.csv",
        "2026-02-21_NQ.csv",
        "2025-11-06_NQ.csv",
        "2025-11-13_NQ.csv",
        "2025-11-24_NQ.csv",
        "2025-12-05_NQ.csv",
        "2025-12-17_NQ.csv",
    ],
}
```

These files are real historical data. They are committed to the repo under
`packages/rockit-core/tests/fixtures/sessions/`. Total size is approximately
40 files x 100KB = 4MB, which is acceptable.

---

## Minimal Fixtures for Unit Tests

Unit tests must not depend on large CSV files. Instead, use factory functions
that create the smallest possible data for each test scenario.

### Bar Factory

```python
# packages/rockit-core/tests/conftest.py

import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass, field


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
    timestamp: datetime | None = None,
) -> pd.Series:
    """Create a single bar with sensible defaults.

    Args:
        All parameters are optional with NQ-realistic defaults.
        Pass only the fields relevant to your test.

    Returns:
        pd.Series matching the schema expected by StrategyBase.on_bar().
    """
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
        "timestamp": timestamp or datetime(2026, 1, 15, 11, 0, 0),
    })


def make_bars(
    n: int = 10,
    start_price: float = 21800.0,
    direction: str = "up",
    bar_size: float = 5.0,
    start_time: datetime | None = None,
    interval_minutes: int = 5,
) -> pd.DataFrame:
    """Create a DataFrame of N bars trending in a direction.

    Args:
        n: Number of bars to generate.
        start_price: Opening price of the first bar.
        direction: 'up' or 'down' trend.
        bar_size: Average bar range in points.
        start_time: Timestamp of first bar.
        interval_minutes: Minutes between bars.

    Returns:
        pd.DataFrame with all columns expected by the backtest engine.
    """
    start = start_time or datetime(2026, 1, 15, 10, 30, 0)
    rows = []
    price = start_price
    cumulative_delta = 0.0

    for i in range(n):
        if direction == "up":
            o = price
            c = price + bar_size
            h = c + bar_size * 0.3
            l = o - bar_size * 0.2
            delta = 200.0 + i * 20
        else:
            o = price
            c = price - bar_size
            h = o + bar_size * 0.2
            l = c - bar_size * 0.3
            delta = -(200.0 + i * 20)

        cumulative_delta += delta
        rows.append({
            "timestamp": start + timedelta(minutes=i * interval_minutes),
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": 1500 + i * 100,
            "delta": delta,
            "cvd": cumulative_delta,
            "vwap": start_price + (c - start_price) * 0.5,
            "ema20": start_price + (c - start_price) * 0.3,
            "ema50": start_price + (c - start_price) * 0.1,
            "ema200": start_price - 100.0,
            "rsi14": 55.0 + i * 2 if direction == "up" else 45.0 - i * 2,
            "atr14": 40.0,
        })
        price = c

    return pd.DataFrame(rows)
```

### Session Context Factory

```python
# packages/rockit-core/tests/conftest.py

def make_session_context(
    ib_high: float = 21850.0,
    ib_low: float = 21780.0,
    day_type: str = "trend_up",
    day_type_confidence: float = 0.75,
    **overrides,
) -> dict:
    """Create a session_context dict for StrategyBase.on_bar().

    Args:
        ib_high: Initial Balance high price.
        ib_low: Initial Balance low price.
        day_type: Current best day type classification.
        day_type_confidence: Confidence score for best day type.
        **overrides: Any key in session_context to override.

    Returns:
        Dict matching the schema expected by StrategyBase.on_bar().
    """
    ctx = {
        "ib_high": ib_high,
        "ib_low": ib_low,
        "ib_range": ib_high - ib_low,
        "atr14": 40.0,
        "vwap": (ib_high + ib_low) / 2,
        "session_high": ib_high + 20.0,
        "session_low": ib_low - 5.0,
        "day_type_confidence": _make_day_type_confidence(day_type, day_type_confidence),
        "prior_day": {
            "high": 21900.0, "low": 21700.0, "close": 21810.0,
            "vah": 21870.0, "val": 21730.0, "poc": 21800.0,
        },
        "volume_profile": {
            "poc": 21810.0, "vah": 21860.0, "val": 21750.0,
        },
    }
    ctx.update(overrides)
    return ctx
```

### SessionContext Dataclass Factory (For Trade Models)

```python
# packages/rockit-core/tests/conftest.py

from rockit_core.models.base import SessionContext


def make_session_context_dataclass(
    ib_high: float = 21850.0,
    ib_low: float = 21780.0,
    current_price: float = 21860.0,
    atr14: float = 40.0,
    day_type: str = "trend_up",
    day_type_confidence: float = 0.75,
    fvgs: list | None = None,
    ifvgs: list | None = None,
    mss_levels: list | None = None,
    lvn_levels: list | None = None,
    hvn_levels: list | None = None,
    bars: pd.DataFrame | None = None,
    **overrides,
) -> SessionContext:
    """Create a SessionContext dataclass for EntryModel/StopModel/TargetModel tests.

    Args:
        All parameters are optional with NQ-realistic defaults.
        fvgs: List of FVG dicts for ICT models.
        mss_levels: List of MSS dicts for ICT models.
        lvn_levels: LVN price levels for volume-profile stop models.
        hvn_levels: HVN price levels for volume-profile stop models.
        bars: DataFrame of bars for models that need bar history.
        **overrides: Any SessionContext field to override.

    Returns:
        SessionContext instance ready for model testing.
    """
    kwargs = {
        "ib_high": ib_high,
        "ib_low": ib_low,
        "ib_range": ib_high - ib_low,
        "current_price": current_price,
        "current_time": datetime(2026, 1, 15, 11, 0, 0),
        "session_high": ib_high + 20.0,
        "session_low": ib_low - 5.0,
        "atr14": atr14,
        "vwap": (ib_high + ib_low) / 2,
        "ema20": current_price - 10.0,
        "ema50": current_price - 25.0,
        "ema200": current_price - 100.0,
        "rsi14": 58.0,
        "delta": 250.0,
        "cumulative_delta": 2000.0,
        "cvd_trend": "up",
        "poc": (ib_high + ib_low) / 2,
        "vah": ib_high - 5.0,
        "val": ib_low + 5.0,
        "hvn_levels": hvn_levels or [ib_high - 10.0, ib_high + 30.0],
        "lvn_levels": lvn_levels or [ib_low + 10.0, ib_low - 20.0],
        "prior_high": 21900.0,
        "prior_low": 21700.0,
        "prior_close": 21810.0,
        "prior_vah": 21870.0,
        "prior_val": 21730.0,
        "prior_poc": 21800.0,
        "fvgs": fvgs or [],
        "ifvgs": ifvgs or [],
        "bprs": [],
        "mss_levels": mss_levels or [],
        "day_type": day_type,
        "day_type_confidence": day_type_confidence,
        "bars": bars,
    }
    kwargs.update(overrides)
    return SessionContext(**kwargs)
```

### Signal Factory

```python
# packages/rockit-core/tests/conftest.py

from rockit_core.strategies.signal import Signal


def make_signal(
    direction: str = "LONG",
    entry_price: float = 21860.0,
    stop_price: float = 21820.0,
    target_price: float = 21940.0,
    strategy_name: str = "test_strategy",
    setup_type: str = "TEST_SETUP",
    day_type: str = "trend_up",
    confidence: str = "medium",
) -> Signal:
    """Create a Signal for filter and integration tests.

    Args:
        All parameters are optional with sensible defaults.
        Defaults produce a valid LONG signal with 2R reward/risk.

    Returns:
        Signal instance.
    """
    return Signal(
        timestamp=datetime(2026, 1, 15, 11, 0, 0),
        direction=direction,
        entry_price=entry_price,
        stop_price=stop_price,
        target_price=target_price,
        strategy_name=strategy_name,
        setup_type=setup_type,
        day_type=day_type,
        confidence=confidence,
    )
```

### Impulse Bars Factory (For ICT Entry Models)

```python
# packages/rockit-core/tests/conftest.py

def make_impulse_bars_df(
    start: float = 21800.0,
    end: float = 21860.0,
    retrace_to: float = 21835.0,
    n_impulse: int = 5,
    n_retrace: int = 3,
) -> pd.DataFrame:
    """Create a DataFrame showing impulse move then retracement.

    Used for testing ICT models that need to see a swing, then a retrace
    into FVG/OTE zone.

    Args:
        start: Price at beginning of impulse.
        end: Price at peak of impulse.
        retrace_to: Price at bottom of retracement.
        n_impulse: Number of bars in the impulse leg.
        n_retrace: Number of bars in the retracement.

    Returns:
        pd.DataFrame with OHLCV columns.
    """
    impulse = make_bars(n=n_impulse, start_price=start, direction="up",
                        bar_size=(end - start) / n_impulse)
    retrace = make_bars(n=n_retrace, start_price=end, direction="down",
                        bar_size=(end - retrace_to) / n_retrace,
                        start_time=impulse["timestamp"].iloc[-1] + timedelta(minutes=5))
    return pd.concat([impulse, retrace], ignore_index=True)
```

### Mock LLM Factory (For Agent Tests)

```python
# packages/rockit-serve/tests/conftest.py

class MockChatModel:
    """Deterministic mock LLM for agent pipeline tests.

    Returns canned responses based on keyword matching in the prompt.
    Used for testing graph routing and output structure, not LLM quality.

    Args:
        responses: Dict mapping prompt keywords to response strings.
    """

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self._responses = responses or {
            "ADVOCATE": '{"argument": "Strong setup", "conviction": "high"}',
            "SKEPTIC": '{"argument": "Weak delta", "conviction": "medium"}',
            "JUDGE": '{"decision": "TAKE", "reasoning": "Advocate wins"}',
        }

    def invoke(self, messages: list) -> str:
        prompt = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])
        for keyword, response in self._responses.items():
            if keyword in prompt:
                return response
        return '{"decision": "SKIP", "reasoning": "mock default"}'


def make_high_confidence_context() -> dict:
    """Context where deterministic confidence > 0.90 (skips debate)."""
    return {
        "day_type": "trend_up",
        "day_type_confidence": 0.92,
        "signals": [make_signal(confidence="high")],
    }


def make_moderate_confidence_context() -> dict:
    """Context where confidence is moderate (triggers debate)."""
    return {
        "day_type": "trend_up",
        "day_type_confidence": 0.65,
        "signals": [make_signal(confidence="medium")],
    }
```

---

## Avoiding Test Data Bloat

### Rules

1. **No session CSV files larger than 200KB.** If a session has more bars than
   needed, truncate to the relevant window (IB + 2 hours post-IB).

2. **Minimal fixtures for unit tests.** The `make_bar()` and `make_bars()`
   factories create data in memory. Unit tests must not read from disk.

3. **Shared fixtures live in conftest.py.** Do not duplicate factory functions
   across test files. Import from `conftest.py`.

4. **Reference JSONs are auto-generated, not hand-edited.** The
   `generate_references` script produces snapshot references. If you need to
   update them, regenerate rather than editing by hand.

5. **Use pytest markers to separate fast and slow tests.** Unit tests have no
   marker (or `@pytest.mark.unit`). Regression tests use `@pytest.mark.regression`.
   This allows running `pytest -m "not slow"` for fast feedback.

6. **Do not commit the full 259-session dataset to the repo.** The 40 curated
   session fixtures are sufficient for CI. The full dataset is stored in GCS and
   downloaded only for nightly backtest runs.

### Fixture Size Budget

```
Target total fixture size: < 10MB committed to repo

Breakdown:
  40 session CSVs       x ~100KB = ~4MB
  40 reference JSONs    x ~20KB  = ~800KB
  Minimal fixtures      ~         = ~100KB
  Migration references  ~         = ~500KB
  Baselines             ~         = ~100KB
  ─────────────────────────────────────────
  Total                            ~5.5MB
```

### Git LFS

If fixture size grows beyond 10MB, move CSV files to Git LFS:

```gitattributes
# .gitattributes
packages/*/tests/fixtures/sessions/*.csv filter=lfs diff=lfs merge=lfs -text
```

---

## Fixture Lifecycle

```
1. Initial creation:
   - Curate 40 sessions from historical data
   - Run orchestrator to generate reference snapshots
   - Run backtest to generate reference_trades.json
   - Commit all fixtures

2. When code changes alter output:
   - Regression tests fail
   - Developer reviews the diff
   - If intentional: regenerate references, update baseline
   - If unintentional: fix the code

3. When new sessions are added:
   - Add CSV to fixtures/sessions/
   - Generate snapshot reference
   - Add to KNOWN_SESSIONS dict
   - Commit

4. When a strategy is added:
   - Existing fixtures still work (new strategy just has no signals on old data)
   - Add specific fixture sessions where the new strategy should fire
   - Update baseline after backtest confirms new strategy performance
```
