#!/usr/bin/env python3
"""
Generate deterministic analysis tape for all sessions.

Enhanced version of generate_deterministic_snapshots.py that:
- Processes ALL available sessions (not just recent N)
- Validates each snapshot with domain-specific checks
- Reports validation stats (errors, warnings)
- Skips already-generated sessions (--force to regenerate)
- RTH-only by default (78 snapshots per day)

Usage:
    uv run python scripts/generate_deterministic_tape.py                  # All sessions, skip existing
    uv run python scripts/generate_deterministic_tape.py --force          # Regenerate all
    uv run python scripts/generate_deterministic_tape.py --days 5         # Last 5 days only
    uv run python scripts/generate_deterministic_tape.py --date 2025-06-15  # Single date
    uv run python scripts/generate_deterministic_tape.py -v               # Verbose output
"""

import argparse
import json
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
from rockit_core.deterministic.modules.data_validator import validate_snapshot_data


DATA_DIR = project_root / "data" / "sessions"
OUTPUT_DIR = project_root / "data" / "json_snapshots"

NQ_CSV = DATA_DIR / "NQ_Volumetric_1.csv"
ES_CSV = DATA_DIR / "ES_Volumetric_1.csv"
YM_CSV = DATA_DIR / "YM_Volumetric_1.csv"


def build_rth_times():
    """Build 5-minute RTH time grid (09:30-15:55)."""
    times = []
    for h in range(9, 16):
        start_min = 30 if h == 9 else 0
        end_min = 60 if h < 16 else 0
        for m in range(start_min, end_min, 5):
            times.append(f"{h:02d}:{m:02d}")
    return times


def get_all_session_dates():
    """Get all unique session dates from the NQ CSV, sorted ascending."""
    df = pd.read_csv(NQ_CSV, usecols=["session_date"])
    dates = sorted(df["session_date"].unique())
    return dates


def generate_session_tape(session_date, times, output_path, verbose=False):
    """Generate snapshots for a single session.

    Returns dict with stats: success, errors, warnings, elapsed.
    """
    csv_paths = {"nq": str(NQ_CSV)}
    if ES_CSV.exists():
        csv_paths["es"] = str(ES_CSV)
    if YM_CSV.exists():
        csv_paths["ym"] = str(YM_CSV)

    cache = get_global_cache()
    cache.clear()

    stats = {
        "session_date": session_date,
        "success": 0,
        "errors": 0,
        "validation_errors": 0,
        "validation_warnings": 0,
        "error_details": [],
    }

    t0 = time.time()
    tmp_dir = output_path.parent / "_tmp"

    with open(output_path, "w", encoding="utf-8") as f:
        for current_time in times:
            config = {
                "session_date": session_date,
                "current_time": current_time,
                "csv_paths": csv_paths,
                "output_dir": str(tmp_dir),
            }
            try:
                snapshot = generate_snapshot(config)

                # Count validation results
                validation = snapshot.get("_validation", {})
                stats["validation_errors"] += validation.get("error_count", 0)
                stats["validation_warnings"] += validation.get("warning_count", 0)

                # Write as single JSON line
                f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
                stats["success"] += 1

                if verbose:
                    v_err = validation.get("error_count", 0)
                    v_warn = validation.get("warning_count", 0)
                    suffix = ""
                    if v_err > 0:
                        suffix = f" [{v_err} validation errors]"
                    elif v_warn > 0:
                        suffix = f" [{v_warn} warnings]"
                    print(f"  {current_time} OK{suffix}")

            except Exception as e:
                stats["errors"] += 1
                stats["error_details"].append({
                    "time": current_time,
                    "error": str(e)[:200],
                })
                if verbose:
                    print(f"  {current_time} ERROR: {e}")

    stats["elapsed"] = time.time() - t0

    # Clean up tmp output dir
    if tmp_dir.exists():
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Generate deterministic tape for all sessions"
    )
    parser.add_argument(
        "--days", type=int, default=None,
        help="Process last N days only (default: all)"
    )
    parser.add_argument(
        "--date", type=str, default=None,
        help="Process single date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Regenerate even if output file already exists"
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

    out_dir = Path(args.output_dir) if args.output_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    times = build_rth_times()

    # Determine which sessions to process
    if args.date:
        session_dates = [args.date]
    else:
        all_dates = get_all_session_dates()
        if args.days:
            session_dates = all_dates[-args.days:]
        else:
            session_dates = all_dates

    # Filter out already-generated unless --force
    if not args.force:
        remaining = []
        for d in session_dates:
            output_path = out_dir / f"deterministic_{d}.jsonl"
            if not output_path.exists():
                remaining.append(d)
            elif args.verbose:
                print(f"  Skipping {d} (already exists, use --force to regenerate)")
        skipped = len(session_dates) - len(remaining)
        if skipped > 0:
            print(f"Skipping {skipped} already-generated sessions")
        session_dates = remaining

    if not session_dates:
        print("No sessions to process.")
        return

    print(f"Generating RTH tape ({len(times)} snapshots/day) for {len(session_dates)} session(s)")
    print(f"Output: {out_dir}")
    print()

    # Aggregate stats
    total_stats = {
        "sessions": 0,
        "snapshots": 0,
        "errors": 0,
        "validation_errors": 0,
        "validation_warnings": 0,
        "elapsed": 0.0,
        "failed_sessions": [],
    }

    for i, session_date in enumerate(session_dates, 1):
        output_path = out_dir / f"deterministic_{session_date}.jsonl"
        print(f"[{i}/{len(session_dates)}] {session_date} -> {output_path.name}", end="")

        try:
            stats = generate_session_tape(
                session_date, times, output_path, verbose=args.verbose
            )

            total_stats["sessions"] += 1
            total_stats["snapshots"] += stats["success"]
            total_stats["errors"] += stats["errors"]
            total_stats["validation_errors"] += stats["validation_errors"]
            total_stats["validation_warnings"] += stats["validation_warnings"]
            total_stats["elapsed"] += stats["elapsed"]

            per_snap = stats["elapsed"] / max(stats["success"] + stats["errors"], 1)
            v_info = ""
            if stats["validation_errors"] > 0:
                v_info = f", {stats['validation_errors']} v-errors"
            elif stats["validation_warnings"] > 0:
                v_info = f", {stats['validation_warnings']} warnings"

            if not args.verbose:
                print(f" — {stats['success']} ok, {stats['errors']} err{v_info}, {stats['elapsed']:.1f}s")
            else:
                print(f"\n  Summary: {stats['success']} ok, {stats['errors']} err{v_info}, "
                      f"{stats['elapsed']:.1f}s ({per_snap:.2f}s/snap)")

            if stats["errors"] > 0:
                total_stats["failed_sessions"].append(session_date)

        except Exception as e:
            print(f" — FATAL: {e}")
            total_stats["failed_sessions"].append(session_date)

    # Final summary
    print()
    print("=" * 60)
    print(f"TAPE GENERATION COMPLETE")
    print(f"  Sessions:    {total_stats['sessions']}")
    print(f"  Snapshots:   {total_stats['snapshots']}")
    print(f"  Errors:      {total_stats['errors']}")
    print(f"  V-Errors:    {total_stats['validation_errors']}")
    print(f"  V-Warnings:  {total_stats['validation_warnings']}")
    print(f"  Time:        {total_stats['elapsed']:.1f}s")
    if total_stats["snapshots"] > 0:
        print(f"  Avg:         {total_stats['elapsed'] / total_stats['snapshots']:.2f}s/snapshot")
    if total_stats["failed_sessions"]:
        print(f"  Failed:      {', '.join(total_stats['failed_sessions'])}")
    print("=" * 60)

    # Save summary report
    report_path = out_dir / "tape_generation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(total_stats, f, indent=2)
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
