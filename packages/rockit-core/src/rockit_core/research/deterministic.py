"""
Deterministic JSONL → DuckDB loaders.

Reads deterministic_{date}.jsonl files and inserts into:
  - deterministic_tape  (every 5-min snapshot, flattened key fields)
  - session_context     (final snapshot per session, session-level summary)
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb


def load_deterministic_tape(
    conn: duckdb.DuckDBPyConnection,
    jsonl_dir: str = "data/json_snapshots",
    instrument: str = "NQ",
) -> Dict[str, int]:
    """Load all deterministic_*.jsonl files into DuckDB.

    Returns dict with counts: {"tape_rows": N, "sessions": N, "files": N}
    """
    jsonl_path = Path(jsonl_dir)
    files = sorted(jsonl_path.glob("deterministic_*.jsonl"))

    stats = {"tape_rows": 0, "sessions": 0, "files": 0}
    if not files:
        return stats

    for fpath in files:
        snapshots = _read_jsonl(fpath)
        if not snapshots:
            continue

        stats["files"] += 1
        session_date = None

        for snap in snapshots:
            row = _extract_tape_row(snap)
            if not row:
                continue

            session_date = row["session_date"]

            # Skip if already loaded
            existing = conn.execute(
                "SELECT 1 FROM deterministic_tape WHERE session_date = ? AND snapshot_time = ?",
                [row["session_date"], row["snapshot_time"]],
            ).fetchone()
            if existing:
                continue

            conn.execute(
                """
                INSERT INTO deterministic_tape (
                    session_date, snapshot_time, instrument,
                    close, vwap, atr14, adx14, rsi14,
                    ib_high, ib_low, ib_range, ib_width_class,
                    price_vs_ib, extension_multiple,
                    tpo_shape, current_poc, current_vah, current_val,
                    dpoc_migration, day_type, bias, confidence,
                    trend_strength, cri_status,
                    composite_regime, vix_regime, atr14_daily,
                    snapshot_json
                ) VALUES (
                    ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?
                )
                """,
                [
                    row["session_date"],
                    row["snapshot_time"],
                    instrument,
                    row.get("close"),
                    row.get("vwap"),
                    row.get("atr14"),
                    row.get("adx14"),
                    row.get("rsi14"),
                    row.get("ib_high"),
                    row.get("ib_low"),
                    row.get("ib_range"),
                    row.get("ib_width_class"),
                    row.get("price_vs_ib"),
                    row.get("extension_multiple"),
                    row.get("tpo_shape"),
                    row.get("current_poc"),
                    row.get("current_vah"),
                    row.get("current_val"),
                    row.get("dpoc_migration"),
                    row.get("day_type"),
                    row.get("bias"),
                    row.get("confidence"),
                    row.get("trend_strength"),
                    row.get("cri_status"),
                    row.get("composite_regime"),
                    row.get("vix_regime"),
                    row.get("atr14_daily"),
                    json.dumps(snap),
                ],
            )
            stats["tape_rows"] += 1

        # Insert session_context from the final snapshot
        if snapshots and session_date:
            final_snap = snapshots[-1]
            ctx = _extract_session_context(final_snap)
            if ctx:
                existing = conn.execute(
                    "SELECT 1 FROM session_context WHERE session_date = ?",
                    [ctx["session_date"]],
                ).fetchone()
                if not existing:
                    conn.execute(
                        """
                        INSERT INTO session_context (
                            session_date, instrument,
                            ib_high, ib_low, ib_range, ib_width_class,
                            day_type, trend_strength, bias, confidence,
                            composite_regime, vix_regime, atr14_daily,
                            prior_day_type, tpo_shape,
                            current_poc, current_vah, current_val,
                            dpoc_migration, cri_status,
                            session_high, session_low, session_close,
                            or_high, or_low,
                            premarket_json, snapshot_json
                        ) VALUES (
                            ?, ?,
                            ?, ?, ?, ?,
                            ?, ?, ?, ?,
                            ?, ?, ?,
                            ?, ?,
                            ?, ?, ?,
                            ?, ?,
                            ?, ?, ?,
                            ?, ?,
                            ?, ?
                        )
                        """,
                        [
                            ctx["session_date"],
                            instrument,
                            ctx.get("ib_high"),
                            ctx.get("ib_low"),
                            ctx.get("ib_range"),
                            ctx.get("ib_width_class"),
                            ctx.get("day_type"),
                            ctx.get("trend_strength"),
                            ctx.get("bias"),
                            ctx.get("confidence"),
                            ctx.get("composite_regime"),
                            ctx.get("vix_regime"),
                            ctx.get("atr14_daily"),
                            ctx.get("prior_day_type"),
                            ctx.get("tpo_shape"),
                            ctx.get("current_poc"),
                            ctx.get("current_vah"),
                            ctx.get("current_val"),
                            ctx.get("dpoc_migration"),
                            ctx.get("cri_status"),
                            ctx.get("session_high"),
                            ctx.get("session_low"),
                            ctx.get("session_close"),
                            ctx.get("or_high"),
                            ctx.get("or_low"),
                            json.dumps(ctx.get("premarket")) if ctx.get("premarket") else None,
                            json.dumps(final_snap),
                        ],
                    )
                    stats["sessions"] += 1

    return stats


def _extract_tape_row(snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract flattened key fields from a snapshot for the tape table."""
    session_date = snapshot.get("session_date")
    snapshot_time = snapshot.get("current_et_time")
    if not session_date or not snapshot_time:
        return None

    ib = snapshot.get("intraday", {}).get("ib", {})
    tpo = snapshot.get("intraday", {}).get("tpo_profile", {})
    dpoc = snapshot.get("intraday", {}).get("dpoc_migration", {})
    inference = snapshot.get("inference", {})
    cri = snapshot.get("cri_readiness", {})
    regime = snapshot.get("regime_context", {})

    # day_type is either {"type": "...", "timestamp": "..."} or a string
    day_type_val = inference.get("day_type")
    if isinstance(day_type_val, dict):
        day_type = day_type_val.get("type")
    else:
        day_type = day_type_val

    return {
        "session_date": session_date,
        "snapshot_time": snapshot_time,
        "close": _safe_float(ib.get("current_close")),
        "vwap": _safe_float(ib.get("current_vwap")),
        "atr14": _safe_float(ib.get("atr14")),
        "adx14": _safe_float(ib.get("adx14")),
        "rsi14": _safe_float(ib.get("rsi14")),
        "ib_high": _safe_float(ib.get("ib_high")),
        "ib_low": _safe_float(ib.get("ib_low")),
        "ib_range": _safe_float(ib.get("ib_range")),
        "ib_width_class": ib.get("ib_width_class"),
        "price_vs_ib": ib.get("price_vs_ib"),
        "extension_multiple": _safe_float(ib.get("extension_multiple")),
        "tpo_shape": tpo.get("tpo_shape"),
        "current_poc": _safe_float(tpo.get("current_poc")),
        "current_vah": _safe_float(tpo.get("current_vah")),
        "current_val": _safe_float(tpo.get("current_val")),
        "dpoc_migration": dpoc.get("migration_status"),
        "day_type": day_type,
        "bias": inference.get("bias"),
        "confidence": _safe_float(inference.get("confidence")),
        "trend_strength": inference.get("trend_strength"),
        "cri_status": cri.get("overall_status"),
        "composite_regime": regime.get("composite_regime"),
        "vix_regime": regime.get("vix_regime"),
        "atr14_daily": _safe_float(regime.get("atr14_daily")),
    }


def _extract_session_context(snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract session-level summary from the final snapshot of a day."""
    session_date = snapshot.get("session_date")
    if not session_date:
        return None

    ib = snapshot.get("intraday", {}).get("ib", {})
    tpo = snapshot.get("intraday", {}).get("tpo_profile", {})
    dpoc = snapshot.get("intraday", {}).get("dpoc_migration", {})
    inference = snapshot.get("inference", {})
    cri = snapshot.get("cri_readiness", {})
    regime = snapshot.get("regime_context", {})
    premarket = snapshot.get("premarket", {})
    or_analysis = snapshot.get("market_structure", {}).get("or_analysis", {})

    day_type_val = inference.get("day_type")
    if isinstance(day_type_val, dict):
        day_type = day_type_val.get("type")
    else:
        day_type = day_type_val

    return {
        "session_date": session_date,
        "ib_high": _safe_float(ib.get("ib_high")),
        "ib_low": _safe_float(ib.get("ib_low")),
        "ib_range": _safe_float(ib.get("ib_range")),
        "ib_width_class": ib.get("ib_width_class"),
        "day_type": day_type,
        "trend_strength": inference.get("trend_strength"),
        "bias": inference.get("bias"),
        "confidence": _safe_float(inference.get("confidence")),
        "composite_regime": regime.get("composite_regime"),
        "vix_regime": regime.get("vix_regime"),
        "atr14_daily": _safe_float(regime.get("atr14_daily")),
        "prior_day_type": regime.get("prior_day_type"),
        "tpo_shape": tpo.get("tpo_shape"),
        "current_poc": _safe_float(tpo.get("current_poc")),
        "current_vah": _safe_float(tpo.get("current_vah")),
        "current_val": _safe_float(tpo.get("current_val")),
        "dpoc_migration": dpoc.get("migration_status"),
        "cri_status": cri.get("overall_status"),
        "session_high": _safe_float(ib.get("current_high")),
        "session_low": _safe_float(ib.get("current_low")),
        "session_close": _safe_float(ib.get("current_close")),
        "or_high": _safe_float(or_analysis.get("or_high")),
        "or_low": _safe_float(or_analysis.get("or_low")),
        "premarket": premarket,
    }


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read a JSONL file, returning list of dicts."""
    snapshots = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                snapshots.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return snapshots


def _safe_float(val: Any) -> Optional[float]:
    """Convert to float, returning None for non-numeric values."""
    if val is None:
        return None
    try:
        result = float(val)
        # Check for NaN/Inf
        if result != result or result == float("inf") or result == float("-inf"):
            return None
        return result
    except (ValueError, TypeError):
        return None
