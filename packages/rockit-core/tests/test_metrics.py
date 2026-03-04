"""Tests for the metrics infrastructure."""

from datetime import datetime

from rockit_core.metrics.collector import MetricsCollector, NullCollector
from rockit_core.metrics.events import MetricCategory, MetricEvent


def test_metric_event_creation():
    event = MetricEvent(
        category=MetricCategory.STRATEGY,
        name="signal_emitted",
        value=1.0,
        tags={"strategy": "trend_bull", "instrument": "NQ"},
    )
    assert event.category == MetricCategory.STRATEGY
    assert event.name == "signal_emitted"
    assert event.value == 1.0
    assert event.tags["strategy"] == "trend_bull"


def test_metrics_collector_record_and_count():
    collector = MetricsCollector(":memory:")
    event = MetricEvent(
        category=MetricCategory.TRADE,
        name="trade_pnl",
        value=150.0,
        timestamp=datetime(2025, 10, 15, 10, 30),
        tags={"strategy": "b_day"},
    )
    collector.record(event)
    assert collector.count() == 1
    assert collector.count(category="trade") == 1
    assert collector.count(category="strategy") == 0
    collector.close()


def test_metrics_collector_query():
    collector = MetricsCollector(":memory:")
    for i in range(5):
        collector.record(
            MetricEvent(
                category=MetricCategory.FILTER,
                name="filter_blocked",
                value=float(i),
            )
        )
    results = collector.query("SELECT SUM(value) FROM metrics")
    assert results[0][0] == 10.0
    collector.close()


def test_null_collector():
    collector = NullCollector()
    event = MetricEvent(
        category=MetricCategory.ENGINE,
        name="session_processed",
        value=1.0,
    )
    collector.record(event)
    assert collector.count() == 0
    assert collector.query("SELECT 1") == []
    collector.close()
