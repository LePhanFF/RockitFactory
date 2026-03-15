#!/usr/bin/env python3
"""
Populate trade_assessments and observations tables in DuckDB.

Programmatic assessment of all trades from the latest backtest run:
- Evaluates outcome quality (strong_win, lucky_win, expected_loss, etc.)
- Captures pre-signal tape context
- Records 15 pattern-level observations from Phase 4 analysis

Usage:
    python scripts/populate_assessments.py
    python scripts/populate_assessments.py --run-id NQ_20260308_215525
"""

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.research.db import (
    connect as db_connect,
    persist_assessment,
    persist_observation,
    query,
    query_df,
)

# Bias alignment helpers
_LONG_ALIGNED = {"Bullish", "BULL", "Very Bullish"}
_SHORT_ALIGNED = {"Bearish", "BEAR", "Very Bearish"}
_NEUTRAL_BIAS = {"Flat", "NEUTRAL", "Neutral", "", None}


def _is_aligned(direction: str, bias: str) -> bool:
    """Check if trade direction aligns with bias."""
    if not bias or bias in _NEUTRAL_BIAS:
        return False  # neutral = neither aligned nor counter
    if direction == "LONG":
        return bias in _LONG_ALIGNED
    return bias in _SHORT_ALIGNED


def _is_counter(direction: str, bias: str) -> bool:
    """Check if trade direction opposes bias."""
    if not bias or bias in _NEUTRAL_BIAS:
        return False
    if direction == "LONG":
        return bias in _SHORT_ALIGNED
    return bias in _LONG_ALIGNED


def _is_neutral_bias(bias: str) -> bool:
    return not bias or bias in _NEUTRAL_BIAS


def assess_trade(trade: dict, tape: dict) -> dict:
    """Programmatically assess a single trade.

    Args:
        trade: Row from v_trade_context (trade + session context)
        tape: Row from v_trade_tape (trade + nearest tape snapshot)

    Returns:
        Assessment dict ready for persist_assessment()
    """
    direction = trade.get("direction", "")
    net_pnl = trade.get("net_pnl", 0)
    exit_reason = trade.get("exit_reason", "")
    strategy = trade.get("strategy_name", "")
    session_bias = trade.get("ctx_bias", "")
    tape_bias = tape.get("tape_bias", "") if tape else ""
    tape_day_type = tape.get("tape_day_type", "") if tape else ""
    ctx_day_type = trade.get("ctx_day_type", "")
    tpo_shape = tape.get("tape_tpo_shape", "") if tape else ""
    cri_status = tape.get("tape_cri_status", "") if tape else ""
    dpoc_migration = tape.get("tape_dpoc_migration", "") if tape else ""

    is_win = net_pnl > 0
    bias_aligned = _is_aligned(direction, session_bias)
    bias_counter = _is_counter(direction, session_bias)
    tape_aligned = _is_aligned(direction, tape_bias)
    tape_counter = _is_counter(direction, tape_bias)

    # --- Outcome quality ---
    outcome_quality = "normal_loss"
    reasons = []  # avoidable-loss reasons (used in improvement_suggestion)
    if is_win:
        avg_win = 500  # approximate portfolio avg win
        if exit_reason == "TARGET" and bias_aligned:
            outcome_quality = "strong_win"
        elif bias_counter:
            outcome_quality = "lucky_win"
        elif net_pnl < avg_win * 0.3:
            outcome_quality = "barely_profitable"
        else:
            outcome_quality = "strong_win"
    else:
        # Determine if avoidable
        avoidable = False

        if bias_counter:
            avoidable = True
            reasons.append("counter-session-bias")

        if strategy == "80P Rule" and ctx_day_type in ("neutral", "neutral_range", "Neutral Range"):
            avoidable = True
            reasons.append("80P_on_neutral_range")

        if strategy == "80P Rule" and direction == "LONG" and tape_bias in _LONG_ALIGNED:
            avoidable = True
            reasons.append("80P_long_chasing_bullish")

        if strategy == "B-Day" and ctx_day_type in ("trend_down", "trend_up", "Trend Down", "Trend Up"):
            avoidable = True
            reasons.append("bday_on_trend")

        if strategy == "Opening Range Rev" and tape_counter:
            avoidable = True
            reasons.append("or_rev_counter_tape")

        if avoidable:
            outcome_quality = "avoidable_loss"
        elif bias_counter:
            outcome_quality = "expected_loss"
        else:
            outcome_quality = "normal_loss"

    # --- Why worked / why failed ---
    why_worked = None
    why_failed = None

    if is_win:
        parts = []
        if bias_aligned:
            parts.append("bias_aligned")
        if tpo_shape in ("B_shape",):
            parts.append("favorable_tpo_B_shape")
        if exit_reason == "TARGET":
            parts.append("hit_target")
        elif exit_reason == "EOD":
            parts.append("profitable_eod_close")
        why_worked = "; ".join(parts) if parts else "setup_valid"
    else:
        parts = reasons if reasons else []
        if tape_counter:
            parts.append("tape_counter_at_entry")
        if tpo_shape in ("p_shape", "D_shape", "b_shape"):
            parts.append(f"adverse_tpo_{tpo_shape}")
        why_failed = "; ".join(parts) if parts else "normal_market_risk"

    # --- Deterministic support / warning ---
    support_parts = []
    warning_parts = []

    if cri_status and cri_status not in ("unknown", ""):
        if "ready" in str(cri_status).lower():
            support_parts.append(f"CRI_ready:{cri_status}")
        else:
            warning_parts.append(f"CRI_not_ready:{cri_status}")

    if dpoc_migration and dpoc_migration not in ("none", ""):
        if (direction == "LONG" and "up" in str(dpoc_migration).lower()) or \
           (direction == "SHORT" and "down" in str(dpoc_migration).lower()):
            support_parts.append(f"DPOC_migrating:{dpoc_migration}")
        elif "up" in str(dpoc_migration).lower() or "down" in str(dpoc_migration).lower():
            warning_parts.append(f"DPOC_against:{dpoc_migration}")

    if bias_aligned:
        support_parts.append("session_bias_aligned")
    elif bias_counter:
        warning_parts.append("session_bias_counter")

    if tape_aligned:
        support_parts.append("tape_bias_aligned")
    elif tape_counter:
        warning_parts.append("tape_bias_counter")

    # --- Pre-signal context ---
    pre_signal_context = {}
    if tape:
        pre_signal_context = {
            "tape_time": tape.get("tape_time", ""),
            "tape_bias": tape_bias,
            "tape_day_type": tape_day_type,
            "tape_tpo_shape": tpo_shape,
            "tape_cri_status": cri_status,
            "tape_confidence": tape.get("tape_confidence"),
            "tape_dpoc_migration": dpoc_migration,
            "tape_composite_regime": tape.get("tape_composite_regime", ""),
            "tape_close": tape.get("tape_close"),
            "tape_vwap": tape.get("tape_vwap"),
        }

    return {
        "outcome_quality": outcome_quality,
        "why_worked": why_worked,
        "why_failed": why_failed,
        "deterministic_support": "; ".join(support_parts) if support_parts else None,
        "deterministic_warning": "; ".join(warning_parts) if warning_parts else None,
        "improvement_suggestion": "; ".join(reasons) if reasons else None,
        "pre_signal_context": pre_signal_context if pre_signal_context else None,
    }


def get_phase4_observations(run_id: str) -> list:
    """Return the 15 pattern-level observations from Phase 4 analysis."""
    return [
        {
            "obs_id": "p4_01_bias_alignment",
            "scope": "portfolio",
            "run_id": run_id,
            "observation": "Bias alignment is #1 predictor: aligned trades 62.2% WR ($499/trade avg) vs counter-bias 47.7% WR ($224/trade avg)",
            "evidence": "251 aligned trades, 149 counter-bias trades, 14.5pp WR difference, 2.2x avg PnL difference",
            "source": "phase4_analysis",
            "confidence": 0.95,
        },
        {
            "obs_id": "p4_02_or_rev_b_shape",
            "scope": "strategy",
            "strategy": "Opening Range Rev",
            "run_id": run_id,
            "observation": "OR Rev + B_shape TPO at entry = 76.8% WR (highest confidence setup with large sample)",
            "evidence": "56 trades with B_shape TPO, 76.8% WR, +$60,250 PnL",
            "source": "phase4_analysis",
            "confidence": 0.90,
        },
        {
            "obs_id": "p4_03_or_rev_counter_tape",
            "scope": "strategy",
            "strategy": "Opening Range Rev",
            "run_id": run_id,
            "observation": "OR Rev counter-tape-bias = 21.4% WR — hard filter: skip these trades",
            "evidence": "14 trades where tape bias opposed trade direction, only 3 wins, -$1,975 net",
            "source": "phase4_analysis",
            "confidence": 0.85,
        },
        {
            "obs_id": "p4_04_80p_long_bullish",
            "scope": "strategy",
            "strategy": "80P Rule",
            "run_id": run_id,
            "observation": "80P LONG + Bullish tape = 12.5% WR — chasing overbought, clear anti-pattern",
            "evidence": "8 trades, 1 win, -$4,215 net. 80P is reversion — works when market NOT committed",
            "source": "phase4_analysis",
            "confidence": 0.85,
        },
        {
            "obs_id": "p4_05_80p_neutral_range",
            "scope": "strategy",
            "strategy": "80P Rule",
            "run_id": run_id,
            "observation": "80P on Neutral Range sessions = 35.6% WR, net negative (-$2,665)",
            "evidence": "45 trades on neutral sessions, below breakeven. Only works on Trend Down (66.7%) and Balance (75%)",
            "source": "phase4_analysis",
            "confidence": 0.90,
        },
        {
            "obs_id": "p4_06_80p_high_vol_trend",
            "scope": "strategy",
            "strategy": "80P Rule",
            "run_id": run_id,
            "observation": "80P on high_vol_trend regime = 55.0% WR, +$19,646 — best regime for 80P",
            "evidence": "20 trades in high_vol_trend composite regime",
            "source": "phase4_analysis",
            "confidence": 0.80,
        },
        {
            "obs_id": "p4_07_bday_trend_zero",
            "scope": "strategy",
            "strategy": "B-Day",
            "run_id": run_id,
            "observation": "B-Day on Trend Down = 0% WR — balance play should never fire on trend days",
            "evidence": "4 trades, 0 wins, -$3,796 net. All LONG trades into bearish trend",
            "source": "phase4_analysis",
            "confidence": 0.75,
        },
        {
            "obs_id": "p4_08_or_accept_aligned",
            "scope": "strategy",
            "strategy": "OR Acceptance",
            "run_id": run_id,
            "observation": "OR Acceptance + aligned bias = 67.1% WR vs 51.0% counter",
            "evidence": "85 aligned trades at 67.1% WR, 49 counter trades at 51.0% WR",
            "source": "phase4_analysis",
            "confidence": 0.90,
        },
        {
            "obs_id": "p4_09_combo_filter_pf",
            "scope": "portfolio",
            "run_id": run_id,
            "observation": "Combo filter (bias + day_type_gate + anti_chase) lifts PF from 2.45 to 3.61, reduces trades 408 -> 229",
            "evidence": "What-if: remove counter-bias + 80P neutral + B-Day trend = 63.3% WR, PF 3.61, $535/trade expectancy",
            "source": "phase4_analysis",
            "confidence": 0.85,
        },
        {
            "obs_id": "p4_10_first_hour_dominates",
            "scope": "portfolio",
            "run_id": run_id,
            "observation": "First hour (10:30 IB close) dominates: 240 trades, 61.3% WR, $456 avg PnL. After 11:00 degrades sharply",
            "evidence": "77% of trades fire at IB close. WR drops monotonically: 61.3% -> 44.6% -> 52.1% -> 52.4%",
            "source": "phase4_analysis",
            "confidence": 0.95,
        },
        {
            "obs_id": "p4_11_bday_wide_ib",
            "scope": "strategy",
            "strategy": "B-Day",
            "run_id": run_id,
            "observation": "B-Day + Q4 (wide 240-471pt) IB range = 75% WR, +$10,565",
            "evidence": "12 trades in Q4 IB width. Wider IB = more room for mean reversion within range",
            "source": "phase4_analysis",
            "confidence": 0.70,
        },
        {
            "obs_id": "p4_12_20p_elevated_vix",
            "scope": "strategy",
            "strategy": "20P IB Extension",
            "run_id": run_id,
            "observation": "20P IB Extension + elevated VIX = 80% WR, +$11,665. High VIX collapses to 20%",
            "evidence": "10 trades in elevated VIX. Sweet spot of 'moderate fear' makes IB extensions reliable",
            "source": "phase4_analysis",
            "confidence": 0.70,
        },
        {
            "obs_id": "p4_13_80p_flat_tape",
            "scope": "strategy",
            "strategy": "80P Rule",
            "run_id": run_id,
            "observation": "80P Rule + Flat tape bias = 52.5% WR, $529 avg. Contrarian — works when market undecided",
            "evidence": "40 trades with Flat tape bias vs 26.3% when aligned. Opposite of all other strategies",
            "source": "phase4_analysis",
            "confidence": 0.85,
        },
        {
            "obs_id": "p4_14_prior_normal_down",
            "scope": "portfolio",
            "run_id": run_id,
            "observation": "After prior normal_down day: 68.8% WR. After p_day_down: 39.5% WR",
            "evidence": "64 trades after normal_down, 43 after p_day_down. Clean prior selling > P-Day exhaustion",
            "source": "phase4_analysis",
            "confidence": 0.80,
        },
        {
            "obs_id": "p4_15_80p_low_vol_balance",
            "scope": "strategy",
            "strategy": "80P Rule",
            "run_id": run_id,
            "observation": "80P on low_vol_balance regime = 22.2% WR, -$3,619 — kill zone",
            "evidence": "9 trades in low_vol_balance composite regime. Insufficient volatility for reversion targets",
            "source": "phase4_analysis",
            "confidence": 0.70,
        },
    ]


def main():
    parser = argparse.ArgumentParser(description="Populate trade assessments and observations")
    parser.add_argument("--run-id", default=None, help="Specific run_id (default: latest)")
    args = parser.parse_args()

    conn = db_connect()

    # Find the run to assess
    if args.run_id:
        run_id = args.run_id
    else:
        rows = query(conn, "SELECT run_id FROM backtest_runs ORDER BY timestamp DESC LIMIT 1")
        if not rows:
            print("No backtest runs found in DuckDB.")
            return
        run_id = rows[0][0]

    print(f"Assessing trades for run: {run_id}")

    # Get trades with session context
    trades_df = query_df(conn, """
        SELECT * FROM v_trade_context WHERE run_id = ?
    """, [run_id])

    if trades_df.empty:
        print("No trades found for this run.")
        return

    print(f"Found {len(trades_df)} trades")

    # Get trades with tape context
    tape_df = query_df(conn, """
        SELECT * FROM v_trade_tape WHERE run_id = ?
    """, [run_id])

    # Build tape lookup by (trade_id, run_id)
    tape_lookup = {}
    if not tape_df.empty:
        for _, row in tape_df.iterrows():
            key = (row["trade_id"], row["run_id"])
            tape_lookup[key] = row.to_dict()

    # Assess each trade
    assessed = 0
    for _, trade in trades_df.iterrows():
        trade_dict = trade.to_dict()
        trade_id = trade_dict["trade_id"]
        tape = tape_lookup.get((trade_id, run_id), {})

        assessment = assess_trade(trade_dict, tape)
        persist_assessment(conn, trade_id, run_id, assessment)
        assessed += 1

    print(f"Assessed {assessed} trades")

    # Populate observations
    observations = get_phase4_observations(run_id)
    for obs in observations:
        persist_observation(conn, obs)

    print(f"Recorded {len(observations)} observations")

    # Verify
    counts = query(conn, """
        SELECT
            (SELECT COUNT(*) FROM trade_assessments WHERE run_id = ?) as assessments,
            (SELECT COUNT(*) FROM observations) as observations
    """, [run_id])
    print(f"\nVerification: {counts[0][0]} assessments, {counts[0][1]} observations")

    # Summary by outcome quality
    quality_df = query_df(conn, """
        SELECT outcome_quality, COUNT(*) as count
        FROM trade_assessments WHERE run_id = ?
        GROUP BY outcome_quality ORDER BY count DESC
    """, [run_id])
    print(f"\nOutcome quality distribution:")
    for _, row in quality_df.iterrows():
        print(f"  {row['outcome_quality']:20s}: {row['count']}")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
