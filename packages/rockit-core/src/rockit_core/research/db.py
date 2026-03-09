"""
Core database operations for the Rockit research database.

connect()                     — open/create DuckDB
persist_backtest_run()        — insert run metadata
persist_trades()              — insert trade dicts
persist_backtest_from_result() — from live BacktestResult
query() / query_df()          — raw SQL helpers
table_counts()                — row counts for all tables
"""

import json
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import duckdb

from rockit_core.research.schema import TABLES, create_all_tables

# Default database path
DEFAULT_DB_PATH = Path("data/research.duckdb")


def connect(db_path: Optional[str] = None) -> duckdb.DuckDBPyConnection:
    """Open (or create) the research database. Use ':memory:' for tests."""
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(db_path)
    create_all_tables(conn)
    return conn


def _git_info() -> Dict[str, Optional[str]]:
    """Get current git branch and short commit hash."""
    info: Dict[str, Optional[str]] = {"branch": None, "commit": None}
    try:
        info["branch"] = (
            subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
        info["commit"] = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        pass
    return info


def persist_backtest_run(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
    instrument: str,
    summary: Dict[str, Any],
    strategies: Sequence[str],
    config: Optional[Dict] = None,
    notes: Optional[str] = None,
) -> str:
    """Insert a backtest run record. Returns run_id."""
    git = _git_info()
    conn.execute(
        """
        INSERT INTO backtest_runs (
            run_id, instrument, sessions, total_trades,
            win_rate, profit_factor, net_pnl, max_drawdown,
            avg_win, avg_loss, expectancy,
            strategies, config, by_strategy,
            git_branch, git_commit, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run_id,
            instrument,
            summary.get("sessions", 0),
            summary.get("trades", 0),
            summary.get("win_rate", 0.0),
            summary.get("profit_factor", 0.0),
            summary.get("net_pnl", 0.0),
            summary.get("max_drawdown", 0.0),
            summary.get("avg_win", 0.0),
            summary.get("avg_loss", 0.0),
            summary.get("expectancy", 0.0),
            json.dumps(list(strategies)),
            json.dumps(config) if config else None,
            json.dumps(summary.get("by_strategy", {})),
            git.get("branch"),
            git.get("commit"),
            notes,
        ],
    )
    return run_id


def persist_trades(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
    trades: List[Dict[str, Any]],
    instrument: str = "NQ",
) -> int:
    """Insert trade dicts into the trades table. Returns count inserted."""
    if not trades:
        return 0

    count = 0
    for i, t in enumerate(trades):
        trade_id = t.get("trade_id", f"{run_id}_t{i:04d}")

        # Handle both key names: "strategy" (JSON) and "strategy_name" (Trade)
        strategy_name = t.get("strategy_name") or t.get("strategy", "")
        setup_type = t.get("setup_type") or t.get("setup", "")

        # Normalize session_date — strip " 00:00:00" suffix for join compatibility
        session_date = str(t.get("session_date", "")).split(" ")[0].split("T")[0]

        # Parse entry_time / exit_time if strings
        entry_time = _parse_timestamp(t.get("entry_time"))
        exit_time = _parse_timestamp(t.get("exit_time"))

        # Metadata as JSON
        meta = t.get("metadata")
        meta_json = json.dumps(meta) if meta else None

        conn.execute(
            """
            INSERT INTO trades (
                trade_id, run_id, strategy_name, setup_type,
                day_type, trend_strength, session_date,
                entry_time, exit_time, bars_held,
                direction, contracts,
                signal_price, entry_price, exit_price,
                stop_price, target_price,
                gross_pnl, commission, slippage_cost, net_pnl,
                exit_reason,
                mae_price, mfe_price, mae_bar, mfe_bar,
                instrument, metadata
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?,
                ?, ?, ?, ?,
                ?, ?
            )
            """,
            [
                trade_id,
                run_id,
                strategy_name,
                setup_type,
                t.get("day_type", ""),
                t.get("trend_strength", ""),
                session_date,
                entry_time,
                exit_time,
                t.get("bars_held", 0),
                t.get("direction", ""),
                t.get("contracts", 0),
                t.get("signal_price", 0.0),
                t.get("entry_price", 0.0),
                t.get("exit_price", 0.0),
                t.get("stop_price", 0.0),
                t.get("target_price", 0.0),
                t.get("gross_pnl", 0.0),
                t.get("commission", 0.0),
                t.get("slippage_cost", 0.0),
                t.get("net_pnl", 0.0),
                t.get("exit_reason", ""),
                t.get("mae_price", 0.0),
                t.get("mfe_price", 0.0),
                t.get("mae_bar", 0),
                t.get("mfe_bar", 0),
                instrument,
                meta_json,
            ],
        )
        count += 1
    return count


def persist_backtest_from_result(
    conn: duckdb.DuckDBPyConnection,
    result: Any,  # BacktestResult
    instrument: str,
    summary: Dict[str, Any],
    strategies: Sequence[str],
    config: Optional[Dict] = None,
    notes: Optional[str] = None,
    run_id: Optional[str] = None,
) -> str:
    """Convert a live BacktestResult → dicts → persist run + trades.

    Uses Trade objects directly so all fields (MAE/MFE, signal_price, etc.)
    are preserved — the JSON serialization in save_results() omits many.
    """
    if run_id is None:
        run_id = f"{instrument}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    persist_backtest_run(conn, run_id, instrument, summary, strategies, config, notes)

    trade_dicts = []
    for t in result.trades:
        td = {
            "strategy_name": t.strategy_name,
            "setup_type": t.setup_type,
            "day_type": t.day_type,
            "trend_strength": t.trend_strength,
            "session_date": t.session_date,
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "bars_held": t.bars_held,
            "direction": t.direction,
            "contracts": t.contracts,
            "signal_price": t.signal_price,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "stop_price": t.stop_price,
            "target_price": t.target_price,
            "gross_pnl": t.gross_pnl,
            "commission": t.commission,
            "slippage_cost": t.slippage_cost,
            "net_pnl": t.net_pnl,
            "exit_reason": t.exit_reason,
            "mae_price": t.mae_price,
            "mfe_price": t.mfe_price,
            "mae_bar": t.mae_bar,
            "mfe_bar": t.mfe_bar,
            "metadata": t.metadata,
        }
        trade_dicts.append(td)

    persist_trades(conn, run_id, trade_dicts, instrument)
    return run_id


def persist_backtest_from_json(
    conn: duckdb.DuckDBPyConnection,
    json_path: str,
) -> str:
    """Load a saved backtest JSON file and persist it.

    Returns run_id.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    instrument = data.get("instrument", "NQ")
    ts = data.get("timestamp", "unknown")
    summary = data.get("summary", {})
    trades = data.get("trades", [])

    run_id = f"{instrument}_{ts}"

    # Check if already loaded
    existing = conn.execute(
        "SELECT 1 FROM backtest_runs WHERE run_id = ?", [run_id]
    ).fetchone()
    if existing:
        return run_id

    strategies = list(summary.get("by_strategy", {}).keys())
    persist_backtest_run(conn, run_id, instrument, summary, strategies)
    persist_trades(conn, run_id, trades, instrument)
    return run_id


def query(
    conn: duckdb.DuckDBPyConnection,
    sql: str,
    params: Optional[list] = None,
) -> list:
    """Execute SQL and return rows as list of tuples."""
    if params:
        return conn.execute(sql, params).fetchall()
    return conn.execute(sql).fetchall()


def query_df(
    conn: duckdb.DuckDBPyConnection,
    sql: str,
    params: Optional[list] = None,
):
    """Execute SQL and return a pandas DataFrame."""
    if params:
        return conn.execute(sql, params).fetchdf()
    return conn.execute(sql).fetchdf()


def table_counts(conn: duckdb.DuckDBPyConnection) -> Dict[str, int]:
    """Return row counts for all research tables."""
    counts = {}
    for name in TABLES:
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()
            counts[name] = row[0] if row else 0
        except Exception:
            counts[name] = 0
    return counts


def _parse_timestamp(val: Any) -> Any:
    """Parse a timestamp value — pass through datetimes, parse strings."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
    return None
