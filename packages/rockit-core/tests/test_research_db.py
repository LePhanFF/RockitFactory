"""
Tests for the research DuckDB package.

All tests use :memory: DuckDB — no disk I/O, no cleanup needed.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import duckdb
import pytest

from rockit_core.research.db import (
    connect,
    persist_backtest_from_json,
    persist_backtest_from_result,
    persist_backtest_run,
    persist_trades,
    query,
    query_df,
    table_counts,
)
from rockit_core.research.deterministic import (
    _extract_session_context,
    _extract_tape_row,
    load_deterministic_tape,
)
from rockit_core.research.schema import create_all_tables, drop_all_tables


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def conn():
    """In-memory DuckDB connection with schema created."""
    c = connect(":memory:")
    yield c
    c.close()


@pytest.fixture
def sample_summary():
    return {
        "instrument": "NQ",
        "sessions": 270,
        "trades": 408,
        "win_rate": 56.1,
        "profit_factor": 2.45,
        "net_pnl": 159331.91,
        "max_drawdown": 2.07,
        "avg_win": 1175.69,
        "avg_loss": -613.97,
        "expectancy": 390.52,
        "by_strategy": {
            "Opening Range Rev": {"trades": 102, "win_rate": 63.7, "net_pnl": 77074.66},
            "80P Rule": {"trades": 71, "win_rate": 42.3, "net_pnl": 21326.0},
        },
    }


@pytest.fixture
def sample_trades():
    return [
        {
            "strategy": "Opening Range Rev",
            "setup": "OR_REVERSAL_SHORT",
            "day_type": "neutral",
            "session_date": "2025-02-20",
            "direction": "SHORT",
            "contracts": 1,
            "entry_price": 23003.25,
            "exit_price": 22931.11,
            "net_pnl": 1428.76,
            "exit_reason": "TARGET",
            "bars_held": 21,
            "metadata": {"level_swept": "ON_HIGH"},
        },
        {
            "strategy": "80P Rule",
            "setup": "80P_LONG",
            "day_type": "neutral",
            "session_date": "2025-02-21",
            "direction": "LONG",
            "contracts": 1,
            "entry_price": 22100.0,
            "exit_price": 22050.0,
            "net_pnl": -1025.0,
            "exit_reason": "STOP",
            "bars_held": 15,
        },
    ]


@pytest.fixture
def sample_snapshot():
    """A minimal deterministic snapshot with the key nested fields."""
    return {
        "session_date": "2025-02-20",
        "current_et_time": "10:30",
        "premarket": {
            "overnight_high": 23200.0,
            "overnight_low": 22900.0,
        },
        "intraday": {
            "ib": {
                "current_close": 23050.0,
                "current_vwap": 23025.0,
                "current_high": 23100.0,
                "current_low": 22950.0,
                "atr14": 5.72,
                "adx14": 17.23,
                "rsi14": 47.46,
                "ib_high": 23128.0,
                "ib_low": 22853.5,
                "ib_range": 274.5,
                "ib_width_class": "extreme",
                "price_vs_ib": "middle",
                "extension_multiple": 0.0,
            },
            "tpo_profile": {
                "tpo_shape": "b_shape",
                "current_poc": 22962.5,
                "current_vah": 23029.25,
                "current_val": 22939.5,
            },
            "dpoc_migration": {
                "migration_status": "neutral",
            },
        },
        "market_structure": {
            "or_analysis": {
                "or_high": 23128.0,
                "or_low": 23090.0,
            },
        },
        "inference": {
            "day_type": {"type": "Neutral Range", "timestamp": "2025-02-20 / 10:30"},
            "bias": "Neutral",
            "confidence": 55,
            "trend_strength": "Weak",
        },
        "cri_readiness": {
            "overall_status": "STAND_DOWN",
        },
        "regime_context": {
            "composite_regime": "unknown",
            "vix_regime": "moderate",
            "atr14_daily": 250.0,
            "prior_day_type": "trend",
        },
    }


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestSchema:
    def test_create_all_tables(self, conn):
        """Tables exist after creation."""
        tables = [r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()]
        assert "backtest_runs" in tables
        assert "trades" in tables
        assert "session_context" in tables
        assert "deterministic_tape" in tables
        assert "observations" in tables
        assert "trade_assessments" in tables

    def test_drop_and_recreate(self, conn):
        """Idempotent rebuild — drop + create succeeds."""
        drop_all_tables(conn)
        # Tables should be gone
        tables = [r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()]
        assert "backtest_runs" not in tables

        create_all_tables(conn)
        tables = [r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()]
        assert "backtest_runs" in tables
        assert "trades" in tables


# ---------------------------------------------------------------------------
# Backtest persistence tests
# ---------------------------------------------------------------------------

class TestBacktestPersistence:
    def test_persist_backtest_run(self, conn, sample_summary):
        """Insert a run and query it back."""
        run_id = persist_backtest_run(
            conn, "test_run_001", "NQ", sample_summary,
            strategies=["Opening Range Rev", "80P Rule"],
        )
        assert run_id == "test_run_001"

        rows = query(conn, "SELECT * FROM backtest_runs WHERE run_id = ?", ["test_run_001"])
        assert len(rows) == 1
        row = rows[0]
        # run_id is first column
        assert row[0] == "test_run_001"

    def test_persist_trades(self, conn, sample_trades):
        """Insert trades and verify count and fields."""
        # Need a run first
        persist_backtest_run(conn, "run_t", "NQ", {"trades": 2}, ["OR Rev"])
        count = persist_trades(conn, "run_t", sample_trades, "NQ")
        assert count == 2

        rows = query(conn, "SELECT strategy_name, direction, net_pnl, outcome FROM trades ORDER BY net_pnl DESC")
        assert len(rows) == 2
        # Winner first
        assert rows[0][0] == "Opening Range Rev"
        assert rows[0][1] == "SHORT"
        assert rows[0][3] == "WIN"
        # Loser
        assert rows[1][0] == "80P Rule"
        assert rows[1][3] == "LOSS"

    def test_persist_backtest_from_result(self, conn, sample_summary):
        """From a live BacktestResult object."""
        from rockit_core.engine.backtest import BacktestResult
        from rockit_core.engine.trade import Trade

        trades = [
            Trade(
                strategy_name="Opening Range Rev",
                setup_type="OR_REVERSAL_SHORT",
                direction="SHORT",
                entry_price=23003.25,
                exit_price=22931.11,
                stop_price=23050.0,
                target_price=22900.0,
                net_pnl=1428.76,
                exit_reason="TARGET",
                session_date="2025-02-20",
                entry_time=datetime(2025, 2, 20, 10, 35),
                exit_time=datetime(2025, 2, 20, 10, 56),
                bars_held=21,
                mae_price=23010.0,
                mfe_price=22920.0,
            ),
        ]
        result = BacktestResult(trades=trades, sessions_processed=1)

        run_id = persist_backtest_from_result(
            conn, result, "NQ", sample_summary,
            strategies=["Opening Range Rev"],
        )
        assert run_id is not None

        # Verify trade preserved MAE/MFE
        rows = query(conn, "SELECT mae_price, mfe_price, signal_price FROM trades")
        assert len(rows) == 1
        assert rows[0][0] == 23010.0  # mae_price
        assert rows[0][1] == 22920.0  # mfe_price

    def test_trade_outcome_column(self, conn, sample_trades):
        """Generated outcome column: WIN / LOSS."""
        persist_backtest_run(conn, "run_o", "NQ", {"trades": 2}, ["OR Rev"])
        persist_trades(conn, "run_o", sample_trades, "NQ")

        rows = query(conn, "SELECT outcome, net_pnl FROM trades ORDER BY net_pnl DESC")
        assert rows[0][0] == "WIN"
        assert rows[1][0] == "LOSS"

    def test_trade_risk_reward_columns(self, conn):
        """Generated risk_points and reward_points columns."""
        persist_backtest_run(conn, "run_rr", "NQ", {"trades": 1}, ["OR Rev"])
        persist_trades(conn, "run_rr", [{
            "strategy": "OR Rev",
            "direction": "LONG",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "target_price": 110.0,
            "exit_price": 110.0,
            "net_pnl": 200.0,
            "session_date": "2025-01-01",
        }], "NQ")

        rows = query(conn, "SELECT risk_points, reward_points FROM trades")
        assert rows[0][0] == pytest.approx(5.0)   # |100 - 95|
        assert rows[0][1] == pytest.approx(10.0)   # |110 - 100|

    def test_duplicate_run_id_rejected(self, conn, sample_summary):
        """Primary key enforcement on backtest_runs."""
        persist_backtest_run(conn, "dup_run", "NQ", sample_summary, ["OR Rev"])
        with pytest.raises(Exception):
            persist_backtest_run(conn, "dup_run", "NQ", sample_summary, ["OR Rev"])


# ---------------------------------------------------------------------------
# Deterministic loader tests
# ---------------------------------------------------------------------------

class TestDeterministicLoaders:
    def test_extract_tape_row(self, sample_snapshot):
        """Flattens nested JSON correctly."""
        row = _extract_tape_row(sample_snapshot)
        assert row is not None
        assert row["session_date"] == "2025-02-20"
        assert row["snapshot_time"] == "10:30"
        assert row["close"] == 23050.0
        assert row["vwap"] == 23025.0
        assert row["atr14"] == 5.72
        assert row["ib_high"] == 23128.0
        assert row["ib_range"] == 274.5
        assert row["tpo_shape"] == "b_shape"
        assert row["day_type"] == "Neutral Range"
        assert row["bias"] == "Neutral"
        assert row["confidence"] == 55.0
        assert row["cri_status"] == "STAND_DOWN"
        assert row["composite_regime"] == "unknown"
        assert row["vix_regime"] == "moderate"
        assert row["atr14_daily"] == 250.0

    def test_extract_tape_row_missing_fields(self):
        """Handles missing top-level keys gracefully."""
        row = _extract_tape_row({"session_date": "2025-01-01", "current_et_time": "09:30"})
        assert row is not None
        assert row["close"] is None
        assert row["tpo_shape"] is None

    def test_extract_tape_row_no_date(self):
        """Returns None when session_date is missing."""
        assert _extract_tape_row({}) is None
        assert _extract_tape_row({"current_et_time": "09:30"}) is None

    def test_extract_session_context(self, sample_snapshot):
        """Extracts session-level summary from final snapshot."""
        ctx = _extract_session_context(sample_snapshot)
        assert ctx is not None
        assert ctx["session_date"] == "2025-02-20"
        assert ctx["ib_high"] == 23128.0
        assert ctx["ib_low"] == 22853.5
        assert ctx["day_type"] == "Neutral Range"
        assert ctx["cri_status"] == "STAND_DOWN"
        assert ctx["prior_day_type"] == "trend"
        assert ctx["or_high"] == 23128.0
        assert ctx["session_close"] == 23050.0
        assert ctx["premarket"]["overnight_high"] == 23200.0

    def test_load_deterministic_tape(self, conn, sample_snapshot):
        """Loads JSONL file into tape + session_context tables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "deterministic_2025-02-20.jsonl"
            # Write 3 snapshots
            snapshots = []
            for time in ["09:30", "09:35", "09:40"]:
                snap = json.loads(json.dumps(sample_snapshot))
                snap["current_et_time"] = time
                snapshots.append(snap)
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for snap in snapshots:
                    f.write(json.dumps(snap) + "\n")

            stats = load_deterministic_tape(conn, tmpdir)

        assert stats["files"] == 1
        assert stats["tape_rows"] == 3
        assert stats["sessions"] == 1

        # Verify tape rows
        tape_count = query(conn, "SELECT COUNT(*) FROM deterministic_tape")[0][0]
        assert tape_count == 3

        # Verify session_context
        ctx_rows = query(conn, "SELECT session_date, day_type, cri_status FROM session_context")
        assert len(ctx_rows) == 1
        assert ctx_rows[0][0] == "2025-02-20"
        assert ctx_rows[0][1] == "Neutral Range"
        assert ctx_rows[0][2] == "STAND_DOWN"

    def test_load_deterministic_tape_idempotent(self, conn, sample_snapshot):
        """Loading the same file twice doesn't duplicate rows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "deterministic_2025-02-20.jsonl"
            with open(jsonl_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(sample_snapshot) + "\n")

            load_deterministic_tape(conn, tmpdir)
            load_deterministic_tape(conn, tmpdir)

        assert query(conn, "SELECT COUNT(*) FROM deterministic_tape")[0][0] == 1
        assert query(conn, "SELECT COUNT(*) FROM session_context")[0][0] == 1


# ---------------------------------------------------------------------------
# View tests
# ---------------------------------------------------------------------------

class TestViews:
    def test_v_trade_context_join(self, conn, sample_trades, sample_snapshot):
        """Trade + session_context join works."""
        # Insert a trade
        persist_backtest_run(conn, "run_v1", "NQ", {"trades": 1}, ["OR Rev"])
        persist_trades(conn, "run_v1", [sample_trades[0]], "NQ")

        # Insert matching session_context
        ctx = _extract_session_context(sample_snapshot)
        conn.execute(
            """INSERT INTO session_context (session_date, instrument, day_type, cri_status, bias)
               VALUES (?, ?, ?, ?, ?)""",
            [ctx["session_date"], "NQ", ctx["day_type"], ctx["cri_status"], ctx["bias"]],
        )

        rows = query(conn, """
            SELECT strategy_name, ctx_day_type, ctx_cri_status, ctx_bias
            FROM v_trade_context WHERE run_id = 'run_v1'
        """)
        assert len(rows) == 1
        assert rows[0][0] == "Opening Range Rev"
        assert rows[0][1] == "Neutral Range"
        assert rows[0][2] == "STAND_DOWN"
        assert rows[0][3] == "Neutral"

    def test_v_trade_context_no_session(self, conn, sample_trades):
        """Trade without session_context still appears (LEFT JOIN)."""
        persist_backtest_run(conn, "run_v2", "NQ", {"trades": 1}, ["OR Rev"])
        persist_trades(conn, "run_v2", [sample_trades[0]], "NQ")

        rows = query(conn, "SELECT strategy_name, ctx_day_type FROM v_trade_context WHERE run_id = 'run_v2'")
        assert len(rows) == 1
        assert rows[0][0] == "Opening Range Rev"
        assert rows[0][1] is None  # No session_context


# ---------------------------------------------------------------------------
# Query tests
# ---------------------------------------------------------------------------

class TestQueries:
    def test_query_win_rate_by_strategy(self, conn, sample_trades):
        """Aggregate query: win rate by strategy."""
        persist_backtest_run(conn, "run_q1", "NQ", {"trades": 2}, ["OR Rev", "80P"])
        persist_trades(conn, "run_q1", sample_trades, "NQ")

        rows = query(conn, """
            SELECT strategy_name,
                   COUNT(*) as trades,
                   SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                   ROUND(SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as wr
            FROM trades WHERE run_id = 'run_q1'
            GROUP BY strategy_name
            ORDER BY wr DESC
        """)
        assert len(rows) == 2
        # OR Rev: 1 win / 1 trade = 100%
        assert rows[0][0] == "Opening Range Rev"
        assert rows[0][3] == 100.0

    def test_query_df_returns_dataframe(self, conn, sample_trades):
        """query_df returns a pandas DataFrame."""
        persist_backtest_run(conn, "run_q2", "NQ", {"trades": 2}, ["OR Rev"])
        persist_trades(conn, "run_q2", sample_trades, "NQ")

        df = query_df(conn, "SELECT strategy_name, net_pnl FROM trades WHERE run_id = 'run_q2'")
        assert hasattr(df, "columns")
        assert len(df) == 2
        assert "strategy_name" in df.columns
        assert "net_pnl" in df.columns

    def test_table_counts(self, conn, sample_trades):
        """table_counts returns correct row counts."""
        persist_backtest_run(conn, "run_tc", "NQ", {"trades": 2}, ["OR Rev"])
        persist_trades(conn, "run_tc", sample_trades, "NQ")

        counts = table_counts(conn)
        assert counts["backtest_runs"] == 1
        assert counts["trades"] == 2
        assert counts["session_context"] == 0
        assert counts["observations"] == 0


# ---------------------------------------------------------------------------
# JSON file persistence test
# ---------------------------------------------------------------------------

class TestJsonFilePersistence:
    def test_persist_backtest_from_json(self, conn, sample_summary, sample_trades):
        """Load a saved backtest JSON file and persist it."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump({
                "instrument": "NQ",
                "timestamp": "20260308_120000",
                "summary": sample_summary,
                "trades": sample_trades,
            }, f)
            tmp_path = f.name

        try:
            run_id = persist_backtest_from_json(conn, tmp_path)
            assert run_id == "NQ_20260308_120000"

            counts = table_counts(conn)
            assert counts["backtest_runs"] == 1
            assert counts["trades"] == 2

            # Loading again should be idempotent (skip existing)
            run_id2 = persist_backtest_from_json(conn, tmp_path)
            assert run_id2 == run_id
            assert table_counts(conn)["backtest_runs"] == 1
        finally:
            os.unlink(tmp_path)
