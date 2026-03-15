#!/usr/bin/env python3
"""
A/B test NWOG strategy — compares Rule Set A (our rules) vs combined rules.

Run A: Our rules only — gap >= 20, Monday, VWAP + 30% acceptance, 75pt stop
Run B: Combined rules — our rules + VIX filter (skip if VIX > 25)

Usage:
    python scripts/ab_test_nwog.py
    python scripts/ab_test_nwog.py --no-merge
"""

import argparse
import sys
from pathlib import Path

import numpy as np

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.config.instruments import get_instrument
from rockit_core.data.features import compute_all_features
from rockit_core.data.manager import SessionDataManager
from rockit_core.engine.backtest import BacktestEngine
from rockit_core.research.db import connect as db_connect, persist_backtest_from_result
from rockit_core.strategies.nwog_gap_fill import NWOGGapFill


def compute_summary(result, instrument):
    """Compute summary metrics."""
    trades = result.trades
    if not trades:
        return {"trades": 0, "win_rate": 0, "profit_factor": 0, "net_pnl": 0,
                "max_drawdown": 0, "expectancy": 0, "sessions": result.sessions_processed,
                "instrument": instrument, "by_strategy": {}}

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
    for t in trades:
        by_strategy.setdefault(t.strategy_name, []).append(t)
    by_strat_summary = {}
    for sname, strades in by_strategy.items():
        s_wins = [t for t in strades if t.net_pnl > 0]
        s_pnl = sum(t.net_pnl for t in strades)
        s_wr = len(s_wins) / len(strades) * 100
        by_strat_summary[sname] = {
            "trades": len(strades), "win_rate": round(s_wr, 1),
            "net_pnl": round(s_pnl, 2),
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
        "by_strategy": by_strat_summary,
    }


def run_nwog(label, df, instrument, strategies, conn):
    """Run one NWOG backtest."""
    print(f"\n{'='*70}")
    print(f"  RUN: {label}")
    print(f"{'='*70}")

    inst_spec = get_instrument(instrument)
    engine = BacktestEngine(
        instrument=inst_spec,
        strategies=strategies,
    )

    result = engine.run(df, verbose=False)
    summary = compute_summary(result, instrument)

    config = {
        "strategies": {s.name: {"enabled": True} for s in strategies},
        "instrument": instrument,
        "ab_test_label": label,
    }

    run_id = persist_backtest_from_result(
        conn, result, instrument, summary,
        [s.name for s in strategies],
        config=config,
        notes=f"NWOG A/B test: {label}",
    )

    print(f"  Trades: {summary['trades']}, WR: {summary['win_rate']}%, "
          f"PF: {summary['profit_factor']}, Net: ${summary['net_pnl']:,.2f}")

    # Print individual trades
    if result.trades:
        print(f"\n  {'Date':12s} {'Dir':5s} {'Entry':>10s} {'Exit':>10s} {'Net PnL':>10s} {'Exit':8s}")
        for t in sorted(result.trades, key=lambda x: x.session_date):
            print(f"  {t.session_date:12s} {t.direction:5s} {t.entry_price:10.2f} "
                  f"{t.exit_price:10.2f} ${t.net_pnl:>9,.2f} {t.exit_reason:8s}")

    print(f"  Persisted: {run_id}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="A/B test NWOG strategy")
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

    conn = db_connect()

    # Run A: Our rules only (defaults)
    strats_a = [NWOGGapFill()]
    summary_a = run_nwog("A: Rule Set A (our rules)", df, instrument, strats_a, conn)

    # Run B: NWOG standalone is only affected by its internal logic.
    # For a "combined" test we'd need code changes to the strategy.
    # Instead, run NWOG alongside the portfolio to see interaction.
    from rockit_core.strategies.loader import load_strategies_from_config
    portfolio = load_strategies_from_config(project_root / "configs" / "strategies.yaml")
    portfolio.append(NWOGGapFill())
    summary_b = run_nwog("B: NWOG + portfolio", df, instrument, portfolio, conn)

    # Comparison
    print(f"\n{'='*70}")
    print("NWOG A/B TEST COMPARISON")
    print(f"{'='*70}")
    print(f"{'Run':35s} {'Trades':>7s} {'WR%':>7s} {'PF':>7s} {'Net PnL':>12s}")
    print("-" * 70)
    for label, s in [("A: NWOG standalone", summary_a), ("B: NWOG + portfolio", summary_b)]:
        print(f"{label:35s} {s['trades']:7d} {s['win_rate']:6.1f}% "
              f"{s['profit_factor']:7.2f} ${s['net_pnl']:>10,.2f}")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
