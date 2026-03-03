"""Metric event definitions for the Rockit platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MetricCategory(Enum):
    STRATEGY = "strategy"
    FILTER = "filter"
    INDICATOR = "indicator"
    ENGINE = "engine"
    TRADE = "trade"
    AGENT = "agent"


@dataclass(frozen=True)
class MetricEvent:
    """A single metric observation.

    Attributes:
        category: Which subsystem produced this metric.
        name: Metric name (e.g., "signal_emitted", "filter_blocked", "trade_pnl").
        value: Numeric value of the metric.
        timestamp: When the event occurred.
        tags: Arbitrary key-value pairs for filtering (strategy name, instrument, etc.).
    """

    category: MetricCategory
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: dict[str, Any] = field(default_factory=dict)
