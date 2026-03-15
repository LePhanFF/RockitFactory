"""Market context endpoints — current state + research DB queries.

These endpoints expose the deterministic analysis data. The research DuckDB
is read-only from the API — never written to by user actions.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from rockit_serve.config import RESEARCH_DB_PATH
from rockit_serve.schemas import MarketContext
from rockit_serve.services.signal_bus import signal_bus

router = APIRouter(prefix="/api/v1/market", tags=["market"])
logger = logging.getLogger(__name__)


@router.get("/context", response_model=MarketContext)
async def get_market_context():
    """Get current market context snapshot.

    Returns the latest deterministic analysis: price, IB, VA, levels, indicators.
    """
    return signal_bus._market


@router.get("/strategies")
async def get_all_strategy_states():
    """Get current state of all 12 strategies."""
    return {sid: state.model_dump() for sid, state in signal_bus._strategies.items()}


@router.get("/research/stats")
async def get_research_stats():
    """Query research DuckDB for aggregate stats (read-only).

    Returns high-level stats about the backtest database.
    """
    db_path = Path(RESEARCH_DB_PATH)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Research database not found")

    try:
        import duckdb
        con = duckdb.connect(str(db_path), read_only=True)
        result = con.execute("""
            SELECT
                count(DISTINCT run_id) as total_runs,
                count(*) as total_trades,
                count(DISTINCT session_date) as total_sessions,
                round(avg(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as avg_win_rate,
                round(sum(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) /
                      nullif(abs(sum(CASE WHEN pnl < 0 THEN pnl ELSE 0 END)), 0), 2) as profit_factor
            FROM trades
        """).fetchone()
        con.close()

        return {
            "total_runs": result[0],
            "total_trades": result[1],
            "total_sessions": result[2],
            "avg_win_rate": result[3],
            "profit_factor": result[4],
        }
    except Exception as e:
        logger.warning(f"DuckDB query failed: {e}")
        raise HTTPException(status_code=500, detail="Research DB query failed")


@router.get("/research/strategy-stats")
async def get_strategy_stats(instrument: str = Query(default="NQ")):
    """Per-strategy performance stats from research DuckDB."""
    db_path = Path(RESEARCH_DB_PATH)
    if not db_path.exists():
        return []

    try:
        import duckdb
        con = duckdb.connect(str(db_path), read_only=True)
        rows = con.execute("""
            SELECT
                strategy,
                count(*) as trades,
                round(avg(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
                round(sum(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) /
                      nullif(abs(sum(CASE WHEN pnl < 0 THEN pnl ELSE 0 END)), 0), 2) as profit_factor,
                round(sum(pnl), 2) as total_pnl
            FROM trades
            WHERE instrument = ?
            GROUP BY strategy
            ORDER BY total_pnl DESC
        """, [instrument]).fetchall()
        con.close()

        return [
            {
                "strategy": r[0],
                "trades": r[1],
                "win_rate": r[2],
                "profit_factor": r[3],
                "total_pnl": r[4],
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning(f"DuckDB query failed: {e}")
        return []
