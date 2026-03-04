#!/usr/bin/env python3
"""
Generate deterministic analysis snapshots at 5-minute intervals.

Produces JSONL files (one JSON object per line) for each trading day,
with a snapshot every 5 minutes from ETH open (18:00) to close (17:00)
or RTH only (09:30-16:00).

Usage:
    uv run python scripts/generate_deterministic_snapshots.py              # Last 1 day
    uv run python scripts/generate_deterministic_snapshots.py --days 5     # Last 5 days
    uv run python scripts/generate_deterministic_snapshots.py --rth-only   # 09:30-16:00 only
    uv run python scripts/generate_deterministic_snapshots.py --days 3 -v  # Verbose output
"""

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.deterministic.orchestrator import generate_snapshot, clean_for_json
from rockit_core.deterministic.modules.dataframe_cache import clear_global_cache, get_global_cache
from rockit_core.deterministic.modules.loader import load_nq_csv


DATA_DIR = project_root / "data" / "sessions"
OUTPUT_DIR = project_root / "data" / "json_snapshots"

NQ_CSV = DATA_DIR / "NQ_Volumetric_1.csv"
ES_CSV = DATA_DIR / "ES_Volumetric_1.csv"
YM_CSV = DATA_DIR / "YM_Volumetric_1.csv"

# ETH: 18:00 previous day to 17:00 current day (23 hours = 276 five-min intervals)
# RTH: 09:30 to 16:00 (6.5 hours = 78 five-min intervals)
ETH_TIMES = []
RTH_TIMES = []


def _build_time_grids():
    """Build the 5-minute time grids for ETH and RTH sessions."""
    global ETH_TIMES, RTH_TIMES

    # ETH: 18:00 -> 23:55, then 00:00 -> 16:55
    for h in range(18, 24):
        for m in range(0, 60, 5):
            ETH_TIMES.append(f"{h:02d}:{m:02d}")
    for h in range(0, 17):
        for m in range(0, 60, 5):
            ETH_TIMES.append(f"{h:02d}:{m:02d}")

    # RTH: 09:30 -> 15:55
    for h in range(9, 16):
        start_min = 30 if h == 9 else 0
        end_min = 60 if h < 16 else 0
        for m in range(start_min, end_min, 5):
            RTH_TIMES.append(f"{h:02d}:{m:02d}")


def get_session_dates(n_days):
    """Get the N most recent session dates from the NQ CSV."""
    df = pd.read_csv(NQ_CSV, usecols=["session_date"])
    dates = sorted(df["session_date"].unique(), reverse=True)
    # Skip the most recent if it's today/incomplete (session_date is next day)
    return dates[:n_days]


def generate_day_snapshots(session_date, times, output_path, verbose=False):
    """Generate snapshots for a single day at each time in the grid.

    Returns (success_count, error_count, elapsed_seconds).
    """
    csv_paths = {"nq": str(NQ_CSV)}
    if ES_CSV.exists():
        csv_paths["es"] = str(ES_CSV)
    if YM_CSV.exists():
        csv_paths["ym"] = str(YM_CSV)

    # Pre-load and cache DataFrames for this session
    cache = get_global_cache()
    cache.clear()

    success = 0
    errors = 0
    t0 = time.time()

    with open(output_path, "w", encoding="utf-8") as f:
        for current_time in times:
            config = {
                "session_date": session_date,
                "current_time": current_time,
                "csv_paths": csv_paths,
                "output_dir": str(output_path.parent / "_tmp"),
            }
            try:
                snapshot = generate_snapshot(config)
                # Write as single JSON line
                f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
                success += 1
                if verbose:
                    print(f"  {current_time} OK")
            except Exception as e:
                errors += 1
                if verbose:
                    print(f"  {current_time} ERROR: {e}")

    elapsed = time.time() - t0

    # Clean up tmp output dir used by orchestrator's file save
    tmp_dir = output_path.parent / "_tmp"
    if tmp_dir.exists():
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return success, errors, elapsed


def main():
    parser = argparse.ArgumentParser(
        description="Generate deterministic snapshots at 5-min intervals"
    )
    parser.add_argument(
        "--days", type=int, default=1,
        help="Number of recent trading days to process (default: 1)"
    )
    parser.add_argument(
        "--rth-only", action="store_true",
        help="RTH only (09:30-16:00), skip overnight session"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print each snapshot time as it completes"
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Output directory (default: data/json_snapshots/)"
    )
    args = parser.parse_args()

    _build_time_grids()
    times = RTH_TIMES if args.rth_only else ETH_TIMES
    session_label = "RTH" if args.rth_only else "ETH"

    out_dir = Path(args.output_dir) if args.output_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {session_label} snapshots ({len(times)} per day) for {args.days} day(s)")
    print(f"Output: {out_dir}")
    print()

    session_dates = get_session_dates(args.days)
    if not session_dates:
        print("ERROR: No session dates found in CSV")
        sys.exit(1)

    total_success = 0
    total_errors = 0
    total_time = 0.0

    for session_date in session_dates:
        output_path = out_dir / f"deterministic_{session_date}.jsonl"
        print(f"Day {session_date} -> {output_path.name}")

        success, errors, elapsed = generate_day_snapshots(
            session_date, times, output_path, verbose=args.verbose
        )

        total_success += success
        total_errors += errors
        total_time += elapsed

        per_snap = elapsed / max(success + errors, 1)
        print(f"  {success} snapshots, {errors} errors, {elapsed:.1f}s ({per_snap:.2f}s/snap)")

    print()
    print(f"Total: {total_success} snapshots, {total_errors} errors, {total_time:.1f}s")
    if total_success > 0:
        print(f"Average: {total_time / total_success:.2f}s per snapshot")


if __name__ == "__main__":
    main()
