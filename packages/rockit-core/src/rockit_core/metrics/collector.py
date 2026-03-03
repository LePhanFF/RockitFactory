"""Metrics collectors with DuckDB backend."""

from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb

if TYPE_CHECKING:
    from rockit_core.metrics.events import MetricEvent


class MetricsCollector:
    """Records MetricEvents to a DuckDB database for analysis.

    Args:
        db_path: Path to DuckDB file. Use ":memory:" for in-memory (tests).
    """

    def __init__(self, db_path: str = ":memory:"):
        self._conn = duckdb.connect(db_path)
        self._setup_schema()

    def _setup_schema(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                category VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                value DOUBLE NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                tags JSON
            )
        """)

    def record(self, event: MetricEvent) -> None:
        """Record a single metric event."""
        import json

        self._conn.execute(
            "INSERT INTO metrics VALUES (?, ?, ?, ?, ?)",
            [
                event.category.value,
                event.name,
                event.value,
                event.timestamp,
                json.dumps(event.tags),
            ],
        )

    def query(self, sql: str) -> list[tuple]:
        """Run an arbitrary SQL query against the metrics table."""
        return self._conn.execute(sql).fetchall()

    def count(self, category: str | None = None, name: str | None = None) -> int:
        """Count events, optionally filtered by category and/or name."""
        where_clauses = []
        params = []
        if category:
            where_clauses.append("category = ?")
            params.append(category)
        if name:
            where_clauses.append("name = ?")
            params.append(name)
        where = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        result = self._conn.execute(f"SELECT COUNT(*) FROM metrics{where}", params).fetchone()
        return result[0] if result else 0

    def close(self):
        self._conn.close()


class NullCollector:
    """No-op collector for tests and contexts that don't need metrics."""

    def record(self, event: MetricEvent) -> None:
        pass

    def query(self, sql: str) -> list[tuple]:
        return []

    def count(self, category: str | None = None, name: str | None = None) -> int:
        return 0

    def close(self):
        pass
