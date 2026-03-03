#!/usr/bin/env python3
"""
Deep Backtest Analysis — standalone analysis of backtest results JSON.

Produces:
  1. Exit reason distribution per strategy
  2. Day type × strategy performance matrix
  3. Loser deep dive (patterns in losing trades)
  4. Win/loss streaks and equity curve shape
  5. Reflection report saved to data/results/reflections/

Usage:
    python scripts/analyze_backtest.py data/results/backtest_NQ_20260302_143021.json
    python scripts/analyze_backtest.py --latest NQ
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

project_root = Path(__file__).resolve().parent.parent
RESULTS_DIR = project_root / "data" / "results"
REFLECTIONS_DIR = project_root / "data" / "results" / "reflections"


def parse_args():
    parser = argparse.ArgumentParser(description="Deep backtest analysis")
    parser.add_argument("results_file", nargs="?", help="Path to backtest results JSON")
    parser.add_argument("--latest", type=str, help="Load latest results for instrument (NQ/ES/YM)")
    return parser.parse_args()


def load_results(args) -> dict:
    """Load backtest results from JSON."""
    if args.results_file:
        path = Path(args.results_file)
    elif args.latest:
        instrument = args.latest.upper()
        files = sorted(RESULTS_DIR.glob(f"backtest_{instrument}_*.json"))
        if not files:
            print(f"No results found for {instrument}")
            sys.exit(1)
        path = files[-1]
    else:
        files = sorted(RESULTS_DIR.glob("backtest_*.json"))
        if not files:
            print("No results found")
            sys.exit(1)
        path = files[-1]

    print(f"Loading: {path}")
    with open(path) as f:
        return json.load(f)


def analyze_exit_reasons(trades: list):
    """Exit reason distribution per strategy."""
    print(f"\n{'='*70}")
    print("1. EXIT REASON DISTRIBUTION")
    print(f"{'='*70}")

    by_strategy = defaultdict(lambda: defaultdict(int))
    overall = Counter()

    for t in trades:
        by_strategy[t['strategy']][t['exit_reason']] += 1
        overall[t['exit_reason']] += 1

    # Overall
    total = len(trades)
    print(f"\nOverall ({total} trades):")
    for reason, count in sorted(overall.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        bar = "#" * int(pct / 2)
        print(f"  {reason:20s} {count:4d} ({pct:5.1f}%) {bar}")

    # Per strategy
    for strat in sorted(by_strategy.keys()):
        reasons = by_strategy[strat]
        strat_total = sum(reasons.values())
        print(f"\n  {strat} ({strat_total} trades):")
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            pct = count / strat_total * 100
            print(f"    {reason:18s} {count:3d} ({pct:5.1f}%)")


def analyze_day_type_matrix(trades: list):
    """Day type × strategy performance matrix."""
    print(f"\n{'='*70}")
    print("2. DAY TYPE × STRATEGY PERFORMANCE MATRIX")
    print(f"{'='*70}")

    # Group by (strategy, day_type)
    matrix = defaultdict(lambda: {'trades': 0, 'wins': 0, 'pnl': 0.0})

    strategies = set()
    day_types = set()

    for t in trades:
        key = (t['strategy'], t.get('day_type', 'unknown'))
        matrix[key]['trades'] += 1
        if t['net_pnl'] > 0:
            matrix[key]['wins'] += 1
        matrix[key]['pnl'] += t['net_pnl']
        strategies.add(t['strategy'])
        day_types.add(t.get('day_type', 'unknown'))

    # Print matrix
    strategies = sorted(strategies)
    day_types = sorted(day_types)

    # Header
    col_width = 14
    print(f"\n  {'Strategy':25s}", end="")
    for dt in day_types:
        print(f" {dt:>{col_width}s}", end="")
    print()
    print("  " + "-" * (25 + len(day_types) * (col_width + 1)))

    for strat in strategies:
        print(f"  {strat:25s}", end="")
        for dt in day_types:
            key = (strat, dt)
            data = matrix[key]
            if data['trades'] == 0:
                print(f" {'—':>{col_width}s}", end="")
            else:
                wr = data['wins'] / data['trades'] * 100
                cell = f"{data['trades']}t/{wr:.0f}%/${data['pnl']:+.0f}"
                print(f" {cell:>{col_width}s}", end="")
        print()


def analyze_losers(trades: list):
    """Deep dive into losing trades."""
    print(f"\n{'='*70}")
    print("3. LOSER DEEP DIVE")
    print(f"{'='*70}")

    losers = [t for t in trades if t['net_pnl'] <= 0]
    winners = [t for t in trades if t['net_pnl'] > 0]

    if not losers:
        print("  No losing trades!")
        return

    print(f"\n  Total losers: {len(losers)} / {len(trades)} ({len(losers)/len(trades)*100:.1f}%)")
    print(f"  Total loss: ${sum(t['net_pnl'] for t in losers):,.2f}")
    print(f"  Avg loss:   ${np.mean([t['net_pnl'] for t in losers]):,.2f}")
    print(f"  Worst loss: ${min(t['net_pnl'] for t in losers):,.2f}")

    # By strategy
    print(f"\n  --- Losers by Strategy ---")
    strat_losers = defaultdict(list)
    for t in losers:
        strat_losers[t['strategy']].append(t)

    for strat in sorted(strat_losers.keys()):
        l = strat_losers[strat]
        print(f"  {strat:25s}: {len(l)} losers, ${sum(t['net_pnl'] for t in l):+,.2f}")

    # By exit reason
    print(f"\n  --- Losers by Exit Reason ---")
    exit_losers = Counter()
    for t in losers:
        exit_losers[t['exit_reason']] += 1
    for reason, count in sorted(exit_losers.items(), key=lambda x: -x[1]):
        print(f"  {reason:20s}: {count} ({count/len(losers)*100:.1f}%)")

    # By day type
    print(f"\n  --- Losers by Day Type ---")
    dt_losers = Counter()
    for t in losers:
        dt_losers[t.get('day_type', 'unknown')] += 1
    for dt, count in sorted(dt_losers.items(), key=lambda x: -x[1]):
        pct = count / len(losers) * 100
        print(f"  {dt:20s}: {count} ({pct:.1f}%)")

    # Bars held comparison
    avg_bars_losers = np.mean([t['bars_held'] for t in losers]) if losers else 0
    avg_bars_winners = np.mean([t['bars_held'] for t in winners]) if winners else 0
    print(f"\n  Avg bars held (losers):  {avg_bars_losers:.1f}")
    print(f"  Avg bars held (winners): {avg_bars_winners:.1f}")

    # Worst 5 trades
    print(f"\n  --- Worst 5 Trades ---")
    worst = sorted(losers, key=lambda t: t['net_pnl'])[:5]
    for t in worst:
        print(f"  {t['session_date']} | {t['strategy']:20s} | {t['direction']:5s} | "
              f"${t['net_pnl']:+8,.2f} | {t['exit_reason']:10s} | {t.get('day_type', '?'):12s} | "
              f"{t['bars_held']}bars")


def analyze_streaks(trades: list):
    """Win/loss streaks and equity curve shape."""
    print(f"\n{'='*70}")
    print("4. WIN/LOSS STREAKS & EQUITY CURVE")
    print(f"{'='*70}")

    if not trades:
        print("  No trades to analyze.")
        return

    # Compute streaks
    current_streak = 0
    max_win_streak = 0
    max_loss_streak = 0
    streaks = []

    for t in trades:
        if t['net_pnl'] > 0:
            if current_streak > 0:
                current_streak += 1
            else:
                if current_streak < 0:
                    streaks.append(current_streak)
                current_streak = 1
        else:
            if current_streak < 0:
                current_streak -= 1
            else:
                if current_streak > 0:
                    streaks.append(current_streak)
                current_streak = -1

        if current_streak > 0:
            max_win_streak = max(max_win_streak, current_streak)
        else:
            max_loss_streak = max(max_loss_streak, abs(current_streak))

    if current_streak != 0:
        streaks.append(current_streak)

    print(f"\n  Max win streak:  {max_win_streak}")
    print(f"  Max loss streak: {max_loss_streak}")

    # Equity curve
    equity = [0]
    for t in trades:
        equity.append(equity[-1] + t['net_pnl'])

    peak = 0
    max_dd = 0
    for e in equity:
        if e > peak:
            peak = e
        dd = peak - e
        if dd > max_dd:
            max_dd = dd

    print(f"\n  Peak equity:     ${max(equity):+,.2f}")
    print(f"  Final equity:    ${equity[-1]:+,.2f}")
    print(f"  Max drawdown:    ${max_dd:,.2f}")

    # Monthly P&L estimation
    sessions = set()
    for t in trades:
        sessions.add(t.get('session_date', ''))
    n_sessions = len(sessions)
    if n_sessions > 0:
        months = n_sessions / 21  # ~21 trading days per month
        if months > 0:
            monthly_pnl = equity[-1] / months
            monthly_trades = len(trades) / months
            print(f"\n  Est. monthly P&L:    ${monthly_pnl:+,.2f}")
            print(f"  Est. trades/month:   {monthly_trades:.1f}")


def save_reflection(results: dict, trades: list):
    """Save reflection report."""
    REFLECTIONS_DIR.mkdir(parents=True, exist_ok=True)

    instrument = results.get('instrument', 'NQ')
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REFLECTIONS_DIR / f"reflection_{instrument}_{ts}.md"

    losers = [t for t in trades if t['net_pnl'] <= 0]
    winners = [t for t in trades if t['net_pnl'] > 0]

    lines = [
        f"# Backtest Reflection — {instrument} ({ts})",
        f"",
        f"## Summary",
        f"- Trades: {len(trades)}",
        f"- Win Rate: {len(winners)/len(trades)*100:.1f}%" if trades else "- Win Rate: N/A",
        f"- Net P&L: ${sum(t['net_pnl'] for t in trades):,.2f}" if trades else "- Net P&L: $0",
        f"- Losers: {len(losers)}",
        f"",
        f"## Worst Trades",
    ]

    worst = sorted(losers, key=lambda t: t['net_pnl'])[:10]
    for t in worst:
        lines.append(
            f"- **{t['session_date']}** {t['strategy']} {t['direction']} "
            f"${t['net_pnl']:+,.2f} ({t['exit_reason']}, {t.get('day_type', '?')}, {t['bars_held']} bars)"
        )

    lines.append("")
    lines.append("## Questions for Next Iteration")
    lines.append("- [ ] Are the worst strategies worth keeping?")
    lines.append("- [ ] Are stops too tight or too wide?")
    lines.append("- [ ] Which day types produce the most losers?")
    lines.append("- [ ] Are there time-of-day patterns in losers?")

    with open(path, 'w') as f:
        f.write("\n".join(lines))

    print(f"\nReflection saved: {path}")


def main():
    args = parse_args()
    results = load_results(args)

    trades = results.get('trades', [])
    summary = results.get('summary', {})

    print(f"\n{'='*70}")
    print(f"DEEP BACKTEST ANALYSIS — {results.get('instrument', '?')}")
    print(f"{'='*70}")
    print(f"Sessions: {summary.get('sessions', '?')}")
    print(f"Trades:   {len(trades)}")
    print(f"WR:       {summary.get('win_rate', 0):.1f}%")
    print(f"PF:       {summary.get('profit_factor', 0):.2f}")
    print(f"Net P&L:  ${summary.get('net_pnl', 0):,.2f}")

    if not trades:
        print("\nNo trades to analyze.")
        return

    analyze_exit_reasons(trades)
    analyze_day_type_matrix(trades)
    analyze_losers(trades)
    analyze_streaks(trades)
    save_reflection(results, trades)

    print(f"\n{'='*70}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
