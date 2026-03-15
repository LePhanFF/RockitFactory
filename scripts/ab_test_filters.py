#!/usr/bin/env python3
"""
A/B test combo filters — runs 4 backtests with different filter configs.

Runs:
  A: Baseline (no combo filters)
  B: Bias alignment only
  C: Full combo (bias + day_type_gate + anti_chase)
  D: Full combo + RegimeFilter(block_counter_trend=True)

Usage:
    python scripts/ab_test_filters.py
    python scripts/ab_test_filters.py --no-merge
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.config.instruments import get_instrument
from rockit_core.data.features import compute_all_features
from rockit_core.data.manager import SessionDataManager
from rockit_core.engine.backtest import BacktestEngine
from rockit_core.filters import (
    BiasAlignmentFilter,
    CompositeFilter,
    DayTypeGateFilter,
    AntiChaseFilter,
    RegimeFilter,
)
from rockit_core.research.db import connect as db_connect, persist_backtest_from_result
from rockit_core.strategies.loader import load_strategies_from_config


def compute_summary(result, instrument):
    """Compute summary metrics."""
    trades = result.trades
    if not trades:
        return {"trades": 0, "win_rate": 0, "profit_factor": 0, "net_pnl": 0,
                "max_drawdown": 0, "expectancy": 0, "sessions": result.sessions_processed}

    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl <= 0]
    total_pnl = sum(t.net_pnl for t in trades)
    win_rate = len(wins) / len(trades) * 100
    avg_win = float(np.mean([t.net_pnl for t in wins])) if wins else 0
    avg_loss = float(np.mean([t.net_pnl for t in losses])) if losses else 0
    gross_profit = sum(t.net_pnl for t in wins)
    gross_loss = abs(sum(t.net_pnl for t in losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    expectancy = (win_rate / 100 * avg_win) - ((1 - win_rate / 100) * abs(avg_loss))

    by_strategy = {}
    strat_trades = {}
    for t in trades:
        strat_trades.setdefault(t.strategy_name, []).append(t)
    for sname, strades in strat_trades.items():
        s_wins = [t for t in strades if t.net_pnl > 0]
        s_losses = [t for t in strades if t.net_pnl <= 0]
        s_pnl = sum(t.net_pnl for t in strades)
        s_wr = len(s_wins) / len(strades) * 100
        s_gp = sum(t.net_pnl for t in s_wins)
        s_gl = abs(sum(t.net_pnl for t in s_losses))
        by_strategy[sname] = {
            "trades": len(strades), "win_rate": round(s_wr, 1),
            "net_pnl": round(s_pnl, 2),
            "profit_factor": round(s_gp / s_gl, 2) if s_gl > 0 else float("inf"),
        }

    return {
        "instrument": instrument, "sessions": result.sessions_processed,
        "trades": len(trades), "win_rate": round(win_rate, 1),
        "profit_factor": round(pf, 2), "net_pnl": round(total_pnl, 2),
        "max_drawdown": round(result.equity_curve.max_drawdown_pct, 2) if result.equity_curve else 0,
        "avg_win": round(avg_win, 2), "avg_loss": round(avg_loss, 2),
        "expectancy": round(expectancy, 2),
        "signals_generated": result.signals_generated,
        "signals_filtered": result.signals_filtered,
        "by_strategy": by_strategy,
    }


def run_one(label, df, strategies, instrument, filters, session_bias_lookup, conn):
    """Run one backtest variant and persist to DuckDB."""
    print(f"\n{'='*70}")
    print(f"  RUN: {label}")
    print(f"{'='*70}")

    inst_spec = get_instrument(instrument)

    # Fresh strategies each run (reset state)
    from rockit_core.strategies.loader import load_strategies_from_config
    strats = load_strategies_from_config(project_root / "configs" / "strategies.yaml")

    engine = BacktestEngine(
        instrument=inst_spec,
        strategies=strats,
        filters=filters,
        session_bias_lookup=session_bias_lookup,
    )

    result = engine.run(df, verbose=False)
    summary = compute_summary(result, instrument)

    # Build config dict
    filter_names = []
    if filters:
        if hasattr(filters, '_filters'):
            filter_names = [f.name for f in filters._filters]
        else:
            filter_names = [filters.name]

    config = {
        "strategies": {s.name: {"enabled": True} for s in strats},
        "filters": filter_names,
        "instrument": instrument,
        "bias_sessions_loaded": len(session_bias_lookup),
        "ab_test_label": label,
    }

    run_id = persist_backtest_from_result(
        conn, result, instrument, summary,
        [s.name for s in strats],
        config=config,
        notes=f"A/B filter test: {label}",
    )

    print(f"  Trades: {summary['trades']}, WR: {summary['win_rate']}%, "
          f"PF: {summary['profit_factor']}, Net: ${summary['net_pnl']:,.2f}, "
          f"MaxDD: {summary['max_drawdown']}%")
    print(f"  Persisted: {run_id}")

    return summary, run_id


def main():
    parser = argparse.ArgumentParser(description="A/B test filter combos")
    parser.add_argument("--no-merge", action="store_true")
    parser.add_argument("--instrument", default="NQ")
    args = parser.parse_args()

    instrument = args.instrument.upper()

    # Load data
    mgr = SessionDataManager(data_dir="data/sessions")
    if not args.no_merge:
        print("Merging latest data...")
        df = mgr.merge_delta(instrument)
    else:
        df = mgr.load(instrument)

    df = compute_all_features(df)

    # Load session bias
    session_bias_lookup = {}
    try:
        conn = db_connect()
        from rockit_core.research.db import query as _q
        rows = _q(conn, "SELECT session_date, bias FROM session_context WHERE bias IS NOT NULL")
        session_bias_lookup = {str(r[0]).split(" ")[0]: r[1] for r in rows}
        print(f"Loaded session bias for {len(session_bias_lookup)} sessions")
    except Exception as e:
        print(f"Warning: {e}")
        conn = db_connect()

    # Define filter configs
    bias_rules = [
        {"strategy": "80P Rule", "blocked_day_types": ["neutral", "neutral_range", "Neutral Range"]},
        {"strategy": "B-Day", "blocked_day_types": ["trend_up", "trend_down", "Trend Up", "Trend Down"]},
    ]
    anti_chase_rules = [
        {"strategy": "80P Rule",
         "block_long_when_bias": ["Bullish", "BULL", "Very Bullish"],
         "block_short_when_bias": ["Bearish", "BEAR", "Very Bearish"]},
    ]

    configs = {
        "A: Baseline (no filters)": None,
        "B: Bias alignment only": CompositeFilter([BiasAlignmentFilter(neutral_passes=True)]),
        "C: Full combo": CompositeFilter([
            BiasAlignmentFilter(neutral_passes=True),
            DayTypeGateFilter(rules=bias_rules),
            AntiChaseFilter(rules=anti_chase_rules),
        ]),
        "D: Full combo + RegimeFilter": CompositeFilter([
            BiasAlignmentFilter(neutral_passes=True),
            DayTypeGateFilter(rules=bias_rules),
            AntiChaseFilter(rules=anti_chase_rules),
            RegimeFilter(block_counter_trend=True),
        ]),
    }

    results = {}
    for label, filters in configs.items():
        summary, run_id = run_one(label, df, None, instrument, filters, session_bias_lookup, conn)
        results[label] = summary

    # Print comparison table
    print(f"\n{'='*70}")
    print("A/B TEST COMPARISON")
    print(f"{'='*70}")
    print(f"{'Run':40s} {'Trades':>7s} {'WR%':>7s} {'PF':>7s} {'Net PnL':>12s} {'MaxDD':>7s} {'$/Trade':>9s}")
    print("-" * 90)
    for label, s in results.items():
        trades = s["trades"]
        per_trade = s["net_pnl"] / trades if trades > 0 else 0
        print(f"{label:40s} {trades:7d} {s['win_rate']:6.1f}% {s['profit_factor']:7.2f} "
              f"${s['net_pnl']:>10,.2f} {s['max_drawdown']:6.2f}% ${per_trade:>8,.2f}")

    conn.close()
    print("\nDone. All runs persisted to DuckDB.")


if __name__ == "__main__":
    main()
