#!/usr/bin/env python3
"""
CLI backtest runner — always merges latest data from Google Drive, then runs.

Usage:
    python scripts/run_backtest.py                                    # NQ, merge + backtest
    python scripts/run_backtest.py --instrument ES                    # ES
    python scripts/run_backtest.py --no-merge                         # Skip merge, use existing local data
    python scripts/run_backtest.py --save-baseline                    # Save this run as the new baseline
    python scripts/run_backtest.py --strategies trend_bull,p_day      # Specific strategies only
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

# Add project root to path so we can import rockit_core
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.config.instruments import get_instrument
from rockit_core.data.features import compute_all_features
from rockit_core.data.manager import SessionDataManager
from rockit_core.engine.backtest import BacktestEngine, BacktestResult
from rockit_core.strategies.loader import load_strategies_from_config

# --- Paths ---
RESULTS_DIR = project_root / "data" / "results"
BASELINE_DIR = project_root / "data" / "results" / "baselines"


def parse_args():
    parser = argparse.ArgumentParser(description="Run Rockit backtest")
    parser.add_argument(
        "--instrument", "-i",
        default="NQ",
        choices=["NQ", "ES", "YM"],
        help="Instrument to backtest (default: NQ)",
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Skip merging from Google Drive (use existing local data)",
    )
    parser.add_argument(
        "--baseline-dir",
        type=str,
        default=None,
        help="Path to baseline CSV directory (default: BookMapOrderFlowStudies-2/csv/)",
    )
    parser.add_argument(
        "--delta-dir",
        type=str,
        default=None,
        help="Path to delta CSV directory (default: G:/My Drive/future_data/1min/)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/sessions",
        help="Working directory for merged data (default: data/sessions/)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/strategies.yaml",
        help="Strategy config file (default: configs/strategies.yaml)",
    )
    parser.add_argument(
        "--strategies",
        type=str,
        default=None,
        help="Comma-separated list of strategy keys to run (overrides config enabled flags)",
    )
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Save this run as the new baseline for future comparisons",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip saving results",
    )
    return parser.parse_args()


def compute_summary(result: BacktestResult, instrument: str) -> dict:
    """Compute summary metrics from a backtest result."""
    trades = result.trades
    if not trades:
        return {
            "instrument": instrument,
            "sessions": result.sessions_processed,
            "trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "net_pnl": 0.0,
            "max_drawdown": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "expectancy": 0.0,
            "by_strategy": {},
        }

    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl <= 0]

    total_pnl = sum(t.net_pnl for t in trades)
    win_rate = len(wins) / len(trades) * 100
    avg_win = float(np.mean([t.net_pnl for t in wins])) if wins else 0
    avg_loss = float(np.mean([t.net_pnl for t in losses])) if losses else 0

    gross_profit = sum(t.net_pnl for t in wins)
    gross_loss = abs(sum(t.net_pnl for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    expectancy = (win_rate / 100 * avg_win) - ((1 - win_rate / 100) * abs(avg_loss))

    # Per-strategy breakdown
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
            "trades": len(strades),
            "win_rate": round(s_wr, 1),
            "net_pnl": round(s_pnl, 2),
            "profit_factor": round(s_gp / s_gl, 2) if s_gl > 0 else float("inf"),
        }

    return {
        "instrument": instrument,
        "sessions": result.sessions_processed,
        "trades": len(trades),
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "net_pnl": round(total_pnl, 2),
        "max_drawdown": round(result.equity_curve.max_drawdown_pct, 2) if result.equity_curve else 0,
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy": round(expectancy, 2),
        "signals_generated": result.signals_generated,
        "signals_filtered": result.signals_filtered,
        "by_strategy": by_strategy,
    }


def save_results(result: BacktestResult, instrument: str, summary: dict):
    """Save backtest results and summary to JSON."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save full trade log
    trades_data = []
    for t in result.trades:
        trade_dict = {
            "strategy": t.strategy_name,
            "setup": t.setup_type,
            "day_type": t.day_type,
            "session_date": t.session_date,
            "direction": t.direction,
            "contracts": t.contracts,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "net_pnl": t.net_pnl,
            "exit_reason": t.exit_reason,
            "bars_held": t.bars_held,
        }
        if t.metadata:
            trade_dict["metadata"] = t.metadata
        trades_data.append(trade_dict)

    full_result = {
        "instrument": instrument,
        "timestamp": ts,
        "summary": summary,
        "trades": trades_data,
    }

    output_path = RESULTS_DIR / f"backtest_{instrument}_{ts}.json"
    with open(output_path, "w") as f:
        json.dump(full_result, f, indent=2, default=str)

    print(f"\nResults saved: {output_path}")
    return output_path


def save_baseline(summary: dict, instrument: str):
    """Save summary as the baseline for future comparisons."""
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    baseline_path = BASELINE_DIR / f"baseline_{instrument}.json"

    baseline = {
        "saved_at": datetime.now().isoformat(),
        **summary,
    }

    with open(baseline_path, "w") as f:
        json.dump(baseline, f, indent=2, default=str)

    print(f"Baseline saved: {baseline_path}")


def load_baseline(instrument: str) -> dict | None:
    """Load existing baseline for comparison."""
    baseline_path = BASELINE_DIR / f"baseline_{instrument}.json"
    if not baseline_path.exists():
        return None
    with open(baseline_path) as f:
        return json.load(f)


def compare_to_baseline(current: dict, baseline: dict):
    """Print comparison between current run and baseline."""
    print(f"\n{'='*70}")
    print("BASELINE COMPARISON")
    print(f"{'='*70}")

    metrics = [
        ("Sessions", "sessions", "", False),
        ("Trades", "trades", "", False),
        ("Win Rate", "win_rate", "%", True),
        ("Profit Factor", "profit_factor", "", True),
        ("Net P&L", "net_pnl", "$", True),
        ("Max Drawdown", "max_drawdown", "%", False),  # lower is better
        ("Avg Win", "avg_win", "$", True),
        ("Avg Loss", "avg_loss", "$", False),  # more negative = worse
        ("Expectancy", "expectancy", "$", True),
    ]

    regressions = []

    for label, key, unit, higher_is_better in metrics:
        cur = current.get(key, 0)
        base = baseline.get(key, 0)
        diff = cur - base

        if unit == "$":
            cur_str = f"${cur:,.2f}"
            base_str = f"${base:,.2f}"
            diff_str = f"${diff:+,.2f}"
        elif unit == "%":
            cur_str = f"{cur:.1f}%"
            base_str = f"{base:.1f}%"
            diff_str = f"{diff:+.1f}%"
        else:
            cur_str = f"{cur}"
            base_str = f"{base}"
            diff_str = f"{diff:+.1f}" if isinstance(diff, float) else f"{diff:+d}"

        # Determine if this is a regression
        is_regression = False
        if key == "max_drawdown":
            # For drawdown, an increase > 3% is bad
            if base > 0 and diff > 0 and (diff / base * 100) > 3:
                is_regression = True
        elif higher_is_better and base != 0:
            pct_change = (diff / abs(base)) * 100 if base != 0 else 0
            if pct_change < -5:  # >5% worse
                is_regression = True

        flag = " !! REGRESSION" if is_regression else ""
        print(f"  {label:20s}  {base_str:>12s} -> {cur_str:>12s}  ({diff_str}){flag}")

        if is_regression:
            regressions.append(label)

    # Strategy-level comparison
    base_strats = baseline.get("by_strategy", {})
    cur_strats = current.get("by_strategy", {})
    all_strats = sorted(set(base_strats.keys()) | set(cur_strats.keys()))

    if all_strats:
        print(f"\n--- By Strategy ---")
        print(f"  {'Strategy':25s} {'Base WR':>8s} {'Cur WR':>8s} {'Base PnL':>12s} {'Cur PnL':>12s}")
        for sname in all_strats:
            bs = base_strats.get(sname, {})
            cs = cur_strats.get(sname, {})
            bwr = f"{bs.get('win_rate', 0):.1f}%"
            cwr = f"{cs.get('win_rate', 0):.1f}%"
            bpnl = f"${bs.get('net_pnl', 0):,.2f}"
            cpnl = f"${cs.get('net_pnl', 0):,.2f}"
            print(f"  {sname:25s} {bwr:>8s} {cwr:>8s} {bpnl:>12s} {cpnl:>12s}")

    if regressions:
        print(f"\n  REGRESSIONS DETECTED in: {', '.join(regressions)}")
    else:
        print(f"\n  No regressions detected.")


def main():
    args = parse_args()
    instrument = args.instrument.upper()

    print(f"{'='*70}")
    print(f"ROCKIT BACKTEST -- {instrument}")
    print(f"{'='*70}\n")

    # --- Data: always merge from G drive unless --no-merge ---
    mgr = SessionDataManager(
        data_dir=args.data_dir,
        baseline_dir=args.baseline_dir,
        delta_dir=args.delta_dir,
    )

    if not args.no_merge:
        print("--- Merging latest data from Google Drive ---")
        df = mgr.merge_delta(instrument)
        print()
    else:
        print("--- Loading local data (merge skipped) ---")
        df = mgr.load(instrument)

    mgr.info(instrument)
    print()

    # --- Feature computation ---
    df = compute_all_features(df)
    print()

    # --- Load strategies ---
    config_path = Path(args.config)
    if not config_path.exists():
        config_path = project_root / args.config

    if args.strategies:
        from rockit_core.strategies.loader import get_strategy_class
        strategy_keys = [s.strip() for s in args.strategies.split(",")]
        strategies = []
        for key in strategy_keys:
            cls = get_strategy_class(key)
            if cls:
                strategies.append(cls())
                print(f"  Loaded strategy: {key}")
            else:
                print(f"  WARNING: Unknown strategy '{key}', skipping")
    else:
        strategies = load_strategies_from_config(config_path)

    print(f"\nActive strategies: {len(strategies)}")
    for s in strategies:
        print(f"  - {s.name}")
    print()

    # --- Run backtest ---
    inst_spec = get_instrument(instrument)
    engine = BacktestEngine(
        instrument=inst_spec,
        strategies=strategies,
    )

    result = engine.run(df, verbose=True)

    # --- Compute summary ---
    summary = compute_summary(result, instrument)

    # --- Compare to baseline ---
    baseline = load_baseline(instrument)
    if baseline:
        compare_to_baseline(summary, baseline)
    else:
        print(f"\nNo baseline found for {instrument}. Run with --save-baseline to create one.")

    # --- Save results ---
    if not args.no_save:
        save_results(result, instrument, summary)

    # --- Save as baseline if requested ---
    if args.save_baseline:
        save_baseline(summary, instrument)

    return result


if __name__ == "__main__":
    main()
