# Technical Design: Metrics Framework

> **Package:** `rockit-core/metrics/`
> **Type:** NEW — no existing metrics infrastructure
> **Tests:** See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#metrics)

---

## Purpose

Centralized metrics collection across all rockit-core components. Every strategy signal, filter decision, engine event, and module execution emits a `MetricEvent` that is stored in DuckDB. This enables dashboard queries, regression detection, and performance analysis without modifying the core logic.

---

## Directory Structure

```
packages/rockit-core/src/rockit_core/metrics/
├── __init__.py           # Public exports: MetricEvent, MetricsCollector, NullCollector
├── event.py              # MetricEvent dataclass
├── collector.py          # MetricsCollector (DuckDB backend)
├── null_collector.py     # NullCollector (no-op for tests)
└── queries.py            # Pre-built query helpers
```

---

## Interface: MetricEvent

```python
# packages/rockit-core/src/rockit_core/metrics/event.py

from dataclasses import dataclass, field


@dataclass
class MetricEvent:
    """A single metric observation.

    Every component emits MetricEvents via the MetricsCollector.
    Events are append-only and immutable once recorded.

    Attributes:
        timestamp: ISO 8601 timestamp (e.g., "2026-03-01T10:35:00")
        layer: One of the 6 metric layers (see DuckDB schema below)
        component: Source component name (e.g., "trend_bull", "order_flow_filter")
        metric: Metric name (e.g., "signal_emitted", "filter_blocked")
        value: Numeric value (count, duration, price, confidence, etc.)
        context: Arbitrary key-value pairs for drill-down
    """
    timestamp: str
    layer: str              # "strategy" | "filter" | "engine" | "component" | "module" | "infra"
    component: str
    metric: str
    value: float
    context: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        valid_layers = {"strategy", "filter", "engine", "component", "module", "infra"}
        if self.layer not in valid_layers:
            raise ValueError(
                f"Invalid metric layer: {self.layer}. Must be one of {valid_layers}"
            )
```

---

## Interface: MetricsCollector

```python
# packages/rockit-core/src/rockit_core/metrics/collector.py

from pathlib import Path
from typing import Any

import duckdb

from rockit_core.metrics.event import MetricEvent


class MetricsCollector:
    """Metrics collector backed by DuckDB.

    Stores all MetricEvents in a single DuckDB database. Supports
    both in-memory (for backtests) and file-backed (for production)
    modes.

    Usage:
        collector = MetricsCollector(path=":memory:")  # in-memory
        collector = MetricsCollector(path="metrics.duckdb")  # persistent

        collector.record(MetricEvent(
            timestamp="2026-03-01T10:35:00",
            layer="strategy",
            component="trend_bull",
            metric="signal_emitted",
            value=1.0,
            context={"direction": "LONG", "session_date": "2026-03-01"},
        ))

        results = collector.query("SELECT * FROM metrics WHERE layer = 'strategy'")
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        """Initialize collector with DuckDB backend.

        Args:
            path: DuckDB database path. Use ":memory:" for in-memory.
        """
        self._db = duckdb.connect(str(path))
        self._init_tables()
        self._buffer: list[MetricEvent] = []
        self._buffer_size = 100

    def _init_tables(self) -> None:
        """Create metrics tables if they don't exist."""
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                timestamp VARCHAR NOT NULL,
                layer VARCHAR NOT NULL,
                component VARCHAR NOT NULL,
                metric VARCHAR NOT NULL,
                value DOUBLE NOT NULL,
                context JSON
            )
        """)
        # Create per-layer views for convenience
        for layer in ("strategy", "filter", "engine", "component", "module", "infra"):
            self._db.execute(f"""
                CREATE OR REPLACE VIEW metrics_{layer} AS
                SELECT * FROM metrics WHERE layer = '{layer}'
            """)

    def record(self, event: MetricEvent) -> None:
        """Record a single metric event.

        Events are buffered and flushed in batches for performance.

        Args:
            event: MetricEvent to record.
        """
        self._buffer.append(event)
        if len(self._buffer) >= self._buffer_size:
            self.flush()

    def record_many(self, events: list[MetricEvent]) -> None:
        """Record multiple metric events at once.

        Args:
            events: List of MetricEvents to record.
        """
        self._buffer.extend(events)
        if len(self._buffer) >= self._buffer_size:
            self.flush()

    def flush(self) -> None:
        """Flush buffered events to DuckDB."""
        if not self._buffer:
            return
        import json
        rows = [
            (e.timestamp, e.layer, e.component, e.metric, e.value, json.dumps(e.context))
            for e in self._buffer
        ]
        self._db.executemany(
            "INSERT INTO metrics VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        self._buffer.clear()

    def query(self, sql: str) -> list[dict[str, Any]]:
        """Execute a SQL query and return results as list of dicts.

        Always flushes buffer before querying to ensure consistency.

        Args:
            sql: SQL query string.

        Returns:
            List of row dicts.
        """
        self.flush()
        result = self._db.execute(sql)
        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]

    def count(self, layer: str | None = None, component: str | None = None) -> int:
        """Count metric events, optionally filtered.

        Args:
            layer: Filter by metric layer.
            component: Filter by component name.

        Returns:
            Event count.
        """
        self.flush()
        sql = "SELECT COUNT(*) FROM metrics WHERE 1=1"
        if layer:
            sql += f" AND layer = '{layer}'"
        if component:
            sql += f" AND component = '{component}'"
        return self._db.execute(sql).fetchone()[0]

    def close(self) -> None:
        """Flush and close the DuckDB connection."""
        self.flush()
        self._db.close()
```

---

## Interface: NullCollector

```python
# packages/rockit-core/src/rockit_core/metrics/null_collector.py

from rockit_core.metrics.event import MetricEvent


class NullCollector:
    """No-op metrics collector for tests and when metrics are disabled.

    Implements the same interface as MetricsCollector but discards
    all events. Zero overhead.
    """

    def record(self, event: MetricEvent) -> None:
        pass

    def record_many(self, events: list[MetricEvent]) -> None:
        pass

    def flush(self) -> None:
        pass

    def query(self, sql: str) -> list[dict]:
        return []

    def count(self, layer: str | None = None, component: str | None = None) -> int:
        return 0

    def close(self) -> None:
        pass
```

---

## DuckDB Table Schema

```sql
-- Main metrics table (all events)
CREATE TABLE metrics (
    timestamp VARCHAR NOT NULL,       -- ISO 8601
    layer VARCHAR NOT NULL,           -- strategy|filter|engine|component|module|infra
    component VARCHAR NOT NULL,       -- e.g., "trend_bull", "volume_profile"
    metric VARCHAR NOT NULL,          -- e.g., "signal_emitted", "module_duration_ms"
    value DOUBLE NOT NULL,            -- numeric value
    context JSON                      -- {"session_date": "2026-03-01", "direction": "LONG"}
);

-- Per-layer views (created automatically by MetricsCollector)
CREATE VIEW metrics_strategy AS SELECT * FROM metrics WHERE layer = 'strategy';
CREATE VIEW metrics_filter AS SELECT * FROM metrics WHERE layer = 'filter';
CREATE VIEW metrics_engine AS SELECT * FROM metrics WHERE layer = 'engine';
CREATE VIEW metrics_component AS SELECT * FROM metrics WHERE layer = 'component';
CREATE VIEW metrics_module AS SELECT * FROM metrics WHERE layer = 'module';
CREATE VIEW metrics_infra AS SELECT * FROM metrics WHERE layer = 'infra';
```

### Metric Layers

| Layer | Components | Example Metrics |
|-------|-----------|-----------------|
| `strategy` | All 16 strategies | `signal_emitted`, `no_signal`, `day_type_mismatch` |
| `filter` | FilterBase subclasses | `filter_passed`, `filter_blocked`, `filter_error` |
| `engine` | BacktestEngine, PositionManager | `trade_opened`, `trade_closed`, `position_stopped_out` |
| `component` | Entry/Stop/Target models, DayTypeConfidence | `entry_model.detected`, `stop_model.computed` |
| `module` | 38 deterministic modules | `module_duration_ms`, `module_error`, `module_field_count` |
| `infra` | Config loading, data loading | `config.loaded`, `csv_rows_loaded`, `snapshot_validated` |

---

## How Modules Emit Metrics

```python
# Convention: accept optional metrics collector, default to NullCollector

from rockit_core.metrics import MetricsCollector, MetricEvent, NullCollector
from datetime import datetime


class TrendDayBull(StrategyBase):
    def __init__(self, metrics: MetricsCollector | None = None):
        self._metrics = metrics or NullCollector()

    def on_bar(self, bar, bar_index, session_context) -> Signal | None:
        signal = self._evaluate(bar, session_context)

        if signal:
            self._metrics.record(MetricEvent(
                timestamp=datetime.now().isoformat(),
                layer="strategy",
                component=self.name,
                metric="signal_emitted",
                value=1.0,
                context={
                    "direction": signal.direction,
                    "confidence": signal.confidence,
                    "session_date": session_context.get("session_date", ""),
                    "bar_index": bar_index,
                },
            ))
        else:
            self._metrics.record(MetricEvent(
                timestamp=datetime.now().isoformat(),
                layer="strategy",
                component=self.name,
                metric="no_signal",
                value=1.0,
                context={"bar_index": bar_index},
            ))

        return signal
```

```python
# Deterministic module example

import time

def get_volume_profile(df, current_time, metrics=None, **kwargs):
    """Volume profile module with metrics."""
    metrics = metrics or NullCollector()
    start = time.monotonic()

    try:
        result = _compute_volume_profile(df, current_time)
        elapsed = (time.monotonic() - start) * 1000

        metrics.record(MetricEvent(
            timestamp=current_time,
            layer="module",
            component="volume_profile",
            metric="module_duration_ms",
            value=elapsed,
            context={"field_count": len(result)},
        ))
        return result

    except Exception as e:
        metrics.record(MetricEvent(
            timestamp=current_time,
            layer="module",
            component="volume_profile",
            metric="module_error",
            value=1.0,
            context={"error": str(e)},
        ))
        return {"error": str(e), "status": "failed"}
```

---

## Query Patterns

```python
# packages/rockit-core/src/rockit_core/metrics/queries.py

from rockit_core.metrics.collector import MetricsCollector


def strategy_signal_counts(collector: MetricsCollector) -> list[dict]:
    """Signal counts per strategy."""
    return collector.query("""
        SELECT component, COUNT(*) as signals
        FROM metrics_strategy
        WHERE metric = 'signal_emitted'
        GROUP BY component
        ORDER BY signals DESC
    """)


def filter_pass_rates(collector: MetricsCollector) -> list[dict]:
    """Pass/block rates per filter."""
    return collector.query("""
        SELECT
            component,
            SUM(CASE WHEN metric = 'filter_passed' THEN 1 ELSE 0 END) as passed,
            SUM(CASE WHEN metric = 'filter_blocked' THEN 1 ELSE 0 END) as blocked,
            ROUND(
                SUM(CASE WHEN metric = 'filter_passed' THEN 1 ELSE 0 END) * 100.0 /
                NULLIF(COUNT(*), 0), 1
            ) as pass_rate_pct
        FROM metrics_filter
        GROUP BY component
    """)


def module_performance(collector: MetricsCollector) -> list[dict]:
    """Average duration and error rate per deterministic module."""
    return collector.query("""
        SELECT
            component,
            AVG(CASE WHEN metric = 'module_duration_ms' THEN value END) as avg_ms,
            MAX(CASE WHEN metric = 'module_duration_ms' THEN value END) as max_ms,
            SUM(CASE WHEN metric = 'module_error' THEN 1 ELSE 0 END) as errors,
            COUNT(*) as total_calls
        FROM metrics_module
        GROUP BY component
        ORDER BY avg_ms DESC
    """)


def engine_trade_summary(collector: MetricsCollector, session_date: str) -> list[dict]:
    """Trade summary for a specific session."""
    return collector.query(f"""
        SELECT metric, component, value, context
        FROM metrics_engine
        WHERE json_extract_string(context, '$.session_date') = '{session_date}'
        ORDER BY timestamp
    """)
```

---

## Data Flow

```
Strategy.on_bar()  ──► MetricEvent(layer="strategy") ──┐
Filter.should_trade() ──► MetricEvent(layer="filter") ──┤
Engine.run()  ──► MetricEvent(layer="engine")  ──────────┤
EntryModel.detect() ──► MetricEvent(layer="component") ──┤
orchestrator.generate_snapshot() ──► MetricEvent(layer="module") ──┤
config.load_*() ──► MetricEvent(layer="infra") ──────────┤
                                                          │
                                                          ▼
                                                   MetricsCollector
                                                          │
                                                   ┌──────▼──────┐
                                                   │   DuckDB    │
                                                   │  (in-mem    │
                                                   │  or file)   │
                                                   └──────┬──────┘
                                                          │
                                              ┌───────────┼───────────┐
                                              ▼           ▼           ▼
                                        Dashboard    Regression    Export
                                        queries      detection     CSV/JSON
```

---

## Dependencies

| This module | Depends on |
|-------------|-----------|
| `metrics/event.py` | None (stdlib only) |
| `metrics/collector.py` | `duckdb` |
| `metrics/null_collector.py` | None |
| `metrics/queries.py` | `metrics/collector.py` |

---

## Migration Notes

1. **This is entirely new code.** No existing metrics infrastructure exists in any source repo.

2. **Adoption is incremental.** Every module accepts `metrics: MetricsCollector | None = None` and defaults to `NullCollector()`. Existing behavior is preserved when metrics are not injected.

3. **BacktestEngine creates the collector.** The engine instantiates a `MetricsCollector` and passes it to all strategies, filters, and models during construction.

4. **DuckDB was chosen** because it is embedded (no server), handles analytical queries well, and the data volumes are small (hundreds of thousands of events per backtest run, not millions).

---

## Test Contract

1. **MetricEvent validation** — invalid layer raises `ValueError`
2. **MetricsCollector record/query** — record events, query them back, verify correctness
3. **NullCollector** — verify all methods are no-ops, no exceptions
4. **Buffer flush** — verify events appear in query results after flush
5. **Query helpers** — each function in `queries.py` returns expected structure
6. **Close safety** — calling `close()` then `record()` raises appropriate error

See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#metrics)
