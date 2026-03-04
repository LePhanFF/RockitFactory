#!/usr/bin/env python3
"""
Validate deterministic JSONL snapshot files.

Time-aware validation: modules have expected sparse output before their data
window (e.g., DPOC migration needs >=2 completed 30-min slices after 10:30).

Classifies issues as:
  ERROR   — Data that should be present is missing or corrupted
  WARNING — NaN, Infinity, or suspicious values
  INFO    — Expected sparse output for the time (not a bug)

Usage:
    uv run python scripts/validate_jsonl.py data/json_snapshots/deterministic_2026-02-27.jsonl
    uv run python scripts/validate_jsonl.py data/json_snapshots/*.jsonl
    uv run python scripts/validate_jsonl.py data/json_snapshots/ --summary
    uv run python scripts/validate_jsonl.py data/json_snapshots/ --errors-only
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.deterministic.modules.schema_validator import validate_snapshot


def parse_time(time_str):
    """Parse HH:MM to (hour, minute) tuple."""
    if ":" not in time_str:
        return (-1, -1)
    parts = time_str.split(":")
    return (int(parts[0]), int(parts[1]))


def time_minutes(hour, minute):
    """Convert to minutes since midnight for easy comparison."""
    return hour * 60 + minute


def find_bad_floats(obj, path=""):
    """Find NaN and Infinity values."""
    bad = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            bad.extend(find_bad_floats(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad.extend(find_bad_floats(v, f"{path}[{i}]"))
    elif isinstance(obj, float):
        if math.isnan(obj):
            bad.append((f"{path}", "NaN"))
        elif math.isinf(obj):
            bad.append((f"{path}", "Infinity"))
    return bad


def is_error_stub(val):
    """Check if a module output is an error stub."""
    return isinstance(val, dict) and val.get("status") == "failed"


def is_note_only(val):
    """Check if module returned only a note (placeholder)."""
    return isinstance(val, dict) and set(val.keys()) <= {"note", "migration_status"}


# ---------------------------------------------------------------------------
# Time-aware module key expectations
# ---------------------------------------------------------------------------
# Each entry: (module_path, required_keys, min_time_minutes, description)
# min_time_minutes: keys are only required AFTER this time
# Use 0 for "always required"

MODULE_EXPECTATIONS = [
    # Premarket: always available (uses prior day data)
    ("premarket", ["asia_high", "asia_low", "overnight_high", "overnight_low",
                    "previous_day_high", "previous_day_low"], 0,
     "premarket levels"),

    # IB: requires data after 09:30, full IB after 10:30
    ("intraday.ib", ["ib_status"], 9 * 60 + 31, "IB status"),
    ("intraday.ib", ["ib_high", "ib_low", "ib_range", "current_close", "atr14"],
     10 * 60 + 30, "full IB data"),

    # Volume profile: available from RTH open (includes 5/10-day composites)
    ("intraday.volume_profile", ["current_session", "previous_5_days", "previous_10_days"],
     9 * 60 + 35, "volume profile"),

    # TPO profile: needs ~30 min of data
    ("intraday.tpo_profile", ["current_poc", "current_vah", "current_val", "tpo_shape"],
     10 * 60, "TPO profile"),

    # DPOC migration: needs >=2 completed 30-min slices (earliest ~11:00)
    ("intraday.dpoc_migration", ["direction", "dpoc_regime", "dpoc_history"],
     11 * 60 + 5, "DPOC migration full analysis"),

    # Core confluences: needs IB + volume profile + TPO
    ("core_confluences", ["ib_acceptance", "dpoc_vs_ib", "dpoc_compression",
                           "price_location", "tpo_signals", "migration"],
     10 * 60 + 30, "core confluences"),

    # Inference: needs core confluences
    ("inference", ["day_type", "bias"], 10 * 60 + 30, "inference engine"),

    # SMT detection: needs ES/YM data + RTH bars
    ("intraday.smt_detection", ["active_divergences"], 9 * 60 + 35,
     "SMT detection"),

    # IB enhanced: width class + extension magnitude (post-IB)
    ("intraday.ib", ["ib_atr_ratio", "ib_width_class", "extension_pts",
                      "extension_direction", "extension_multiple"],
     10 * 60 + 30, "IB width class + extension magnitude"),

    # Market structure modules (registry-based)
    ("market_structure.prior_va_analysis", [], 0, "prior VA analysis"),
    ("market_structure.ib_extension", [], 10 * 60 + 30, "IB extension"),
    ("market_structure.va_poke", [], 10 * 60 + 30, "VA poke analysis"),

    # Balance type skew + morph (post-IB)
    ("market_structure.balance_type", ["skew", "skew_strength", "skew_factors",
                                        "seam_level", "seam_description", "morph"],
     10 * 60 + 30, "balance type skew + morph"),
]


def validate_line(snap, line_num):
    """Validate a single snapshot. Returns list of (level, message) tuples."""
    issues = []  # (level, message)
    time_str = snap.get("current_et_time", "??:??")
    hour, minute = parse_time(time_str)
    t_min = time_minutes(hour, minute)
    prefix = f"L{line_num} ({time_str})"

    # 1. Required top-level keys (always)
    for key in ["session_date", "current_et_time", "premarket", "intraday", "core_confluences", "market_structure"]:
        if key not in snap:
            issues.append(("ERROR", f"{prefix}: missing top-level key '{key}'"))

    # 2. Schema validation
    try:
        validate_snapshot(snap)
    except ValueError as e:
        issues.append(("ERROR", f"{prefix}: schema fail: {e}"))

    # 3. Module population — check for error stubs
    for mod in ["premarket", "intraday", "core_confluences", "inference",
                "market_structure"]:
        val = snap.get(mod)
        if is_error_stub(val):
            issues.append(("ERROR", f"{prefix}: {mod} FAILED: {val.get('error', '?')[:80]}"))

    # 4. Time-aware inner key checks
    for path, keys, min_time, desc in MODULE_EXPECTATIONS:
        parts = path.split(".")
        val = snap
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p, {})
            else:
                val = {}
                break

        if not isinstance(val, dict) or not val:
            continue

        if is_error_stub(val):
            continue  # Already reported above

        for key in keys:
            if key not in val:
                if t_min >= min_time:
                    issues.append(("ERROR", f"{prefix}: {path} missing '{key}' ({desc})"))
                else:
                    issues.append(("INFO", f"{prefix}: {path} missing '{key}' (expected before {min_time // 60:02d}:{min_time % 60:02d})"))

    # 5. NaN/Infinity check
    bad_floats = find_bad_floats(snap)
    for path, kind in bad_floats:
        issues.append(("WARNING", f"{prefix}: {kind} at {path}"))

    # 6. Numeric sanity (post-IB only)
    is_post_ib = t_min >= 10 * 60 + 30
    if is_post_ib:
        intraday = snap.get("intraday", {})
        ib = intraday.get("ib", {})
        ib_range = ib.get("ib_range")
        if isinstance(ib_range, (int, float)) and ib_range <= 0:
            issues.append(("ERROR", f"{prefix}: ib_range={ib_range} (expected > 0 post-IB)"))

        ib_high = ib.get("ib_high")
        ib_low = ib.get("ib_low")
        if isinstance(ib_high, (int, float)) and isinstance(ib_low, (int, float)):
            if ib_high <= ib_low:
                issues.append(("ERROR", f"{prefix}: ib_high={ib_high} <= ib_low={ib_low}"))

    return issues


def validate_file(filepath):
    """Validate JSONL file. Returns (total, errors, warnings, infos, issue_list)."""
    all_issues = []
    total = 0

    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            total += 1
            line = line.strip()
            if not line:
                continue

            try:
                snap = json.loads(line)
            except json.JSONDecodeError as e:
                all_issues.append(("ERROR", f"L{i}: invalid JSON: {e}"))
                continue

            if "error" in snap and len(snap) <= 3:
                all_issues.append(("ERROR", f"L{i}: orchestrator error: {snap['error'][:80]}"))
                continue

            all_issues.extend(validate_line(snap, i))

    errors = sum(1 for lvl, _ in all_issues if lvl == "ERROR")
    warnings = sum(1 for lvl, _ in all_issues if lvl == "WARNING")
    infos = sum(1 for lvl, _ in all_issues if lvl == "INFO")

    return total, errors, warnings, infos, all_issues


def main():
    parser = argparse.ArgumentParser(description="Validate deterministic JSONL files")
    parser.add_argument("paths", nargs="+", help="JSONL files or directories to validate")
    parser.add_argument("--summary", action="store_true", help="Summary only, skip per-line details")
    parser.add_argument("--errors-only", action="store_true", help="Show only ERROR level issues")
    parser.add_argument("--no-info", action="store_true", help="Hide INFO level (expected sparse data)")
    args = parser.parse_args()

    files = []
    for p in args.paths:
        path = Path(p)
        if path.is_dir():
            files.extend(sorted(path.glob("*.jsonl")))
        elif path.exists():
            files.append(path)
        else:
            print(f"WARNING: {p} not found, skipping")

    if not files:
        print("No JSONL files found")
        sys.exit(1)

    grand_total = 0
    grand_errors = 0
    grand_warnings = 0
    grand_infos = 0

    for filepath in files:
        total, errors, warnings, infos, issues = validate_file(filepath)
        grand_total += total
        grand_errors += errors
        grand_warnings += warnings
        grand_infos += infos

        status = "PASS" if errors == 0 and warnings == 0 else f"{errors} errors, {warnings} warnings"
        print(f"{filepath.name}: {total} snapshots | {status} | {infos} info")

        if not args.summary:
            for level, msg in issues:
                if args.errors_only and level != "ERROR":
                    continue
                if args.no_info and level == "INFO":
                    continue
                marker = {"ERROR": "!!", "WARNING": "??", "INFO": ".."}[level]
                print(f"  {marker} {msg}")

    print()
    print(f"Total: {grand_total} snapshots across {len(files)} files")
    print(f"  Errors:   {grand_errors}")
    print(f"  Warnings: {grand_warnings}")
    print(f"  Info:     {grand_infos} (expected sparse data at early times)")
    sys.exit(1 if grand_errors > 0 else 0)


if __name__ == "__main__":
    main()
