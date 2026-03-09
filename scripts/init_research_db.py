#!/usr/bin/env python3
"""
Initialize the Rockit research DuckDB database.

Drops and recreates all tables, then loads:
  1. Backtest result JSON files → backtest_runs + trades
  2. Deterministic JSONL snapshots → deterministic_tape + session_context

Usage:
    python scripts/init_research_db.py                          # Full rebuild
    python scripts/init_research_db.py --skip-deterministic     # Backtest data only
    python scripts/init_research_db.py --db-path /tmp/test.db   # Custom DB path
"""

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.research.db import connect, persist_backtest_from_json, table_counts
from rockit_core.research.deterministic import load_deterministic_tape
from rockit_core.research.schema import create_all_tables, drop_all_tables


def parse_args():
    parser = argparse.ArgumentParser(description="Initialize Rockit research database")
    parser.add_argument(
        "--db-path",
        default=str(project_root / "data" / "research.duckdb"),
        help="Path to DuckDB file (default: data/research.duckdb)",
    )
    parser.add_argument(
        "--skip-deterministic",
        action="store_true",
        help="Skip loading deterministic JSONL snapshots",
    )
    parser.add_argument(
        "--results-dir",
        default=str(project_root / "data" / "results"),
        help="Directory containing backtest_*.json files",
    )
    parser.add_argument(
        "--snapshots-dir",
        default=str(project_root / "data" / "json_snapshots"),
        help="Directory containing deterministic_*.jsonl files",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("ROCKIT RESEARCH DATABASE INIT")
    print("=" * 60)
    print(f"  DB path: {args.db_path}")
    print()

    # Connect and rebuild schema
    conn = connect(args.db_path)
    print("Dropping all tables (clean rebuild)...")
    drop_all_tables(conn)
    print("Creating schema...")
    create_all_tables(conn)
    print()

    # --- Load backtest results ---
    results_dir = Path(args.results_dir)
    json_files = sorted(results_dir.glob("backtest_*.json")) if results_dir.exists() else []
    print(f"Loading {len(json_files)} backtest result files...")

    loaded = 0
    for fpath in json_files:
        try:
            run_id = persist_backtest_from_json(conn, str(fpath))
            loaded += 1
        except Exception as e:
            print(f"  WARN: {fpath.name}: {e}")

    print(f"  Loaded {loaded} backtest runs")
    print()

    # --- Load deterministic snapshots ---
    if args.skip_deterministic:
        print("Skipping deterministic JSONL (--skip-deterministic)")
    else:
        snapshots_dir = Path(args.snapshots_dir)
        if snapshots_dir.exists():
            print("Loading deterministic JSONL snapshots...")
            stats = load_deterministic_tape(conn, str(snapshots_dir))
            print(f"  Files: {stats['files']}")
            print(f"  Tape rows: {stats['tape_rows']}")
            print(f"  Sessions: {stats['sessions']}")
        else:
            print(f"Snapshots dir not found: {snapshots_dir}")
    print()

    # --- Print summary ---
    counts = table_counts(conn)
    print("=" * 60)
    print("TABLE COUNTS")
    print("=" * 60)
    for name, count in counts.items():
        print(f"  {name:25s} {count:>8,d} rows")

    conn.close()
    print(f"\nDone. Database at: {args.db_path}")


if __name__ == "__main__":
    main()
