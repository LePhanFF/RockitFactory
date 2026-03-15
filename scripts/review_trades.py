#!/usr/bin/env python3
"""
Batch-review trades using LLM-powered TradeReviewer.

Reviews each trade with Qwen3.5 and persists structured assessments
+ observations to DuckDB. Results feed into future Advocate/Skeptic debates.

Usage:
    uv run python scripts/review_trades.py --date 2026-03-10
    uv run python scripts/review_trades.py --run-id NQ_20260310_123456_abc123
    uv run python scripts/review_trades.py --date 2026-03-10 --dry-run
    uv run python scripts/review_trades.py --date 2026-03-10 --limit 5
"""

import argparse
import json
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.agents.llm_client import OllamaClient
from rockit_core.agents.trade_reviewer import TradeReviewer
from rockit_core.research.db import connect as db_connect, query


def get_trades(conn, run_id: str | None = None, date: str | None = None, limit: int = 0):
    """Fetch trades from DuckDB, optionally filtered by run_id or date."""
    if run_id:
        sql = "SELECT * FROM trades WHERE run_id = ? ORDER BY entry_time"
        rows = conn.execute(sql, [run_id]).fetchdf()
    elif date:
        sql = "SELECT * FROM trades WHERE session_date = ? ORDER BY entry_time"
        rows = conn.execute(sql, [date]).fetchdf()
    else:
        print("ERROR: Must specify --run-id or --date")
        sys.exit(1)

    if limit > 0:
        rows = rows.head(limit)

    return rows


def get_session_context(conn, session_date: str) -> dict:
    """Fetch session context from DuckDB."""
    rows = query(conn, "SELECT * FROM session_context WHERE session_date = ?", [session_date])
    if not rows:
        return {}

    cols = conn.execute("SELECT * FROM session_context LIMIT 0").description
    col_names = [c[0] for c in cols]
    return dict(zip(col_names, rows[0]))


def get_deterministic_at_signal(conn, session_date: str, signal_time: str) -> dict:
    """Fetch nearest deterministic snapshot at or before signal time."""
    # Extract HH:MM from signal_time
    if signal_time and ":" in str(signal_time):
        time_str = str(signal_time)
        # Handle datetime strings like "2026-03-10 10:30:00"
        if " " in time_str:
            time_str = time_str.split(" ")[1]
        # Round down to nearest 5-min
        parts = time_str.split(":")
        hour, minute = int(parts[0]), int(parts[1])
        rounded = f"{hour:02d}:{(minute // 5) * 5:02d}"
    else:
        rounded = "10:30"

    rows = query(
        conn,
        """
        SELECT snapshot_json FROM deterministic_tape
        WHERE session_date = ? AND snapshot_time <= ?
        ORDER BY snapshot_time DESC LIMIT 1
        """,
        [session_date, rounded],
    )
    if rows and rows[0][0]:
        try:
            return json.loads(rows[0][0]) if isinstance(rows[0][0], str) else rows[0][0]
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def main():
    parser = argparse.ArgumentParser(description="Batch-review trades with LLM")
    parser.add_argument("--run-id", help="Review trades from a specific backtest run")
    parser.add_argument("--date", help="Review trades from a specific date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=0, help="Max trades to review (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Show trades without calling LLM")
    parser.add_argument(
        "--ollama-url", default="http://spark-ai:11434/v1", help="Ollama base URL"
    )
    args = parser.parse_args()

    conn = db_connect()

    # Fetch trades
    trades_df = get_trades(conn, args.run_id, args.date, args.limit)
    if trades_df.empty:
        print(f"No trades found for {'run_id=' + args.run_id if args.run_id else 'date=' + args.date}")
        return

    print(f"Found {len(trades_df)} trades to review")
    print()

    if args.dry_run:
        for _, row in trades_df.iterrows():
            outcome = "WIN" if row.get("net_pnl", 0) > 0 else "LOSS"
            print(
                f"  {row.get('strategy_name', '?'):20s} | {row.get('direction', '?'):5s} | "
                f"${row.get('net_pnl', 0):+8,.0f} | {outcome}"
            )
        print(f"\nDry run — {len(trades_df)} trades would be reviewed. Use without --dry-run to proceed.")
        conn.close()
        return

    # Check LLM availability
    client = OllamaClient(base_url=args.ollama_url)
    if not client.is_available():
        print(f"ERROR: LLM not reachable at {args.ollama_url}")
        print("Start Ollama or specify --ollama-url")
        conn.close()
        sys.exit(1)

    reviewer = TradeReviewer(client)
    run_id = args.run_id or f"review_{args.date}"

    reviewed = 0
    errors = 0
    total_start = time.time()

    for i, (_, row) in enumerate(trades_df.iterrows()):
        trade = row.to_dict()
        session_date = str(trade.get("session_date", "")).split(" ")[0].split("T")[0]
        trade_id = trade.get("trade_id", f"t_{i}")

        # Get context
        session_ctx = get_session_context(conn, session_date)
        det_data = get_deterministic_at_signal(
            conn, session_date, str(trade.get("entry_time", ""))
        )

        outcome = "WIN" if trade.get("net_pnl", 0) > 0 else "LOSS"
        strategy = trade.get("strategy_name", "?")
        print(f"[{i+1}/{len(trades_df)}] {strategy:20s} | {trade.get('direction', '?'):5s} | "
              f"${trade.get('net_pnl', 0):+8,.0f} | {outcome} ... ", end="", flush=True)

        start = time.time()
        result = reviewer.review_and_persist(
            trade, run_id, session_ctx, det_data, conn
        )
        elapsed = time.time() - start

        if result.get("error"):
            print(f"ERROR ({elapsed:.1f}s): {result['error']}")
            errors += 1
        else:
            quality = result.get("setup_quality", "?")
            timing = result.get("entry_timing", "?")
            print(f"quality={quality} timing={timing} ({elapsed:.1f}s)")
            reviewed += 1

    total_elapsed = time.time() - total_start
    print(f"\nDone: {reviewed} reviewed, {errors} errors in {total_elapsed:.0f}s")
    print(f"Avg: {total_elapsed / max(reviewed + errors, 1):.1f}s per trade")

    conn.close()


if __name__ == "__main__":
    main()
