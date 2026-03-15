#!/usr/bin/env python3
"""
Backtest new strategies individually — find optimal configs, persist to DuckDB.

Tests each new strategy in isolation with multiple stop/target/filter combos,
then compares results against quant study targets.

Usage:
    uv run python scripts/backtest_new_strategies.py
    uv run python scripts/backtest_new_strategies.py --strategy ndog_gap_fill
    uv run python scripts/backtest_new_strategies.py --no-merge
    uv run python scripts/backtest_new_strategies.py --instrument NQ
"""

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.config.instruments import get_instrument
from rockit_core.data.features import compute_all_features
from rockit_core.data.manager import SessionDataManager
from rockit_core.engine.backtest import BacktestEngine
from rockit_core.strategies.loader import get_strategy_class

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Study targets for each strategy
STUDY_TARGETS = {
    "ndog_gap_fill": {
        "trades": 42, "wr": 88.1, "pf": 12.08, "pnl": 83853,
        "config": "rth_open|gap>=20|fixed_75|full_fill|ts=1300|+VWAP",
    },
    "single_print_gap_fill": {
        "trades": 117, "wr": 69.2, "pf": 4.49, "pnl": 22525,
        "config": "min_10|above_vah|immediate|atr_1x|2R|morning|BOTH",
    },
    "poor_highlow_repair": {
        "trades": 54, "wr": 66.7, "pf": 2.01, "pnl": 8964,
        "config": "A|within_10|accept_3|stop_10pt|target_1R|morning",
    },
    "cvd_divergence": {
        "trades": 33, "wr": 21.2, "pf": 5.05, "pnl": 5300,
        "config": "cvd_div_bb|immediate|adx_lt_25|swing_low|vwap|after_ib|LONG",
    },
    "rth_gap_fill": {
        "trades": 10, "wr": 100.0, "pf": 99.99, "pnl": 12512,
        "config": "gap_50|up_only|rth_open|vwap_confirm|fixed_50pt|half_fill|ts_1100",
    },
}

# All new strategies to test
NEW_STRATEGIES = list(STUDY_TARGETS.keys())


def compute_metrics(trades, instrument):
    """Compute standard metrics from trade list."""
    if not trades:
        return {
            "trades": 0, "win_rate": 0.0, "profit_factor": 0.0,
            "net_pnl": 0.0, "max_drawdown": 0.0, "expectancy": 0.0,
            "avg_win": 0.0, "avg_loss": 0.0,
            "long_trades": 0, "long_wr": 0.0, "long_pnl": 0.0,
            "short_trades": 0, "short_wr": 0.0, "short_pnl": 0.0,
        }

    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl <= 0]
    total_pnl = sum(t.net_pnl for t in trades)
    wr = len(wins) / len(trades) * 100 if trades else 0
    avg_win = float(np.mean([t.net_pnl for t in wins])) if wins else 0
    avg_loss = float(np.mean([t.net_pnl for t in losses])) if losses else 0
    gross_profit = sum(t.net_pnl for t in wins)
    gross_loss = abs(sum(t.net_pnl for t in losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    expectancy = (wr / 100 * avg_win) - ((1 - wr / 100) * abs(avg_loss))

    # Max drawdown
    equity_curve = []
    running = 0
    for t in trades:
        running += t.net_pnl
        equity_curve.append(running)
    peak = 0
    max_dd = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd

    # Direction split
    long_trades = [t for t in trades if t.direction == "LONG"]
    short_trades = [t for t in trades if t.direction == "SHORT"]
    long_wr = (
        len([t for t in long_trades if t.net_pnl > 0]) / len(long_trades) * 100
        if long_trades else 0
    )
    short_wr = (
        len([t for t in short_trades if t.net_pnl > 0]) / len(short_trades) * 100
        if short_trades else 0
    )

    return {
        "trades": len(trades),
        "win_rate": round(wr, 1),
        "profit_factor": round(pf, 2) if pf != float("inf") else 99.99,
        "net_pnl": round(total_pnl, 2),
        "max_drawdown": round(max_dd, 2),
        "expectancy": round(expectancy, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "long_trades": len(long_trades),
        "long_wr": round(long_wr, 1),
        "long_pnl": round(sum(t.net_pnl for t in long_trades), 2),
        "short_trades": len(short_trades),
        "short_wr": round(short_wr, 1),
        "short_pnl": round(sum(t.net_pnl for t in short_trades), 2),
    }


def run_single_strategy_backtest(df, instrument, strategy_key, session_bias=None):
    """Run backtest with only one strategy enabled."""
    cls = get_strategy_class(strategy_key)
    if cls is None:
        log.warning(f"Strategy {strategy_key} not found in registry!")
        return None

    strategy = cls()
    inst = get_instrument(instrument)
    engine = BacktestEngine(
        instrument=inst,
        strategies=[strategy],
        session_bias_lookup=session_bias or {},
    )
    result = engine.run(df, verbose=False)
    return result


def persist_to_duckdb(result, strategy_key, instrument, config_desc, notes, metrics):
    """Persist backtest result to DuckDB."""
    try:
        from rockit_core.research.db import connect as db_connect, persist_backtest_from_result
        conn = db_connect()
        summary = {
            "trades": metrics["trades"],
            "win_rate": metrics["win_rate"],
            "profit_factor": metrics["profit_factor"],
            "net_pnl": metrics["net_pnl"],
            "max_drawdown": metrics["max_drawdown"],
            "avg_win": metrics["avg_win"],
            "avg_loss": metrics["avg_loss"],
            "expectancy": metrics["expectancy"],
        }
        run_id = persist_backtest_from_result(
            conn, result, instrument, summary,
            strategies=[strategy_key],
            config={"config_desc": config_desc},
            notes=notes,
        )
        conn.close()
        log.info(f"  Persisted to DuckDB: {run_id}")
        return run_id
    except Exception as e:
        log.warning(f"  DuckDB persist failed: {e}")
        return None


def compare_to_target(metrics, target, strategy_key):
    """Compare actual metrics to study targets."""
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"  {strategy_key} — Target vs Actual")
    lines.append(f"{'='*60}")
    lines.append(f"  Target config: {target['config']}")
    lines.append("")

    def fmt(label, target_val, actual_val, unit="", higher_better=True):
        diff = actual_val - target_val
        sign = "+" if diff > 0 else ""
        status = "OK" if (diff >= 0) == higher_better else "BELOW"
        if unit == "$":
            return f"  {label:20s} Target: ${target_val:>10,.0f}  Actual: ${actual_val:>10,.0f}  ({sign}{diff:,.0f}) {status}"
        elif unit == "%":
            return f"  {label:20s} Target: {target_val:>8.1f}%  Actual: {actual_val:>8.1f}%  ({sign}{diff:.1f}pp) {status}"
        else:
            return f"  {label:20s} Target: {target_val:>8.2f}   Actual: {actual_val:>8.2f}  ({sign}{diff:.2f}) {status}"

    lines.append(fmt("Trades", target["trades"], metrics["trades"], higher_better=True))
    lines.append(fmt("Win Rate", target["wr"], metrics["win_rate"], "%"))
    lines.append(fmt("Profit Factor", target["pf"], metrics["profit_factor"]))
    lines.append(fmt("Net PnL", target["pnl"], metrics["net_pnl"], "$"))
    lines.append("")
    lines.append(f"  Direction split:")
    lines.append(f"    LONG:  {metrics['long_trades']} trades, {metrics['long_wr']:.1f}% WR, ${metrics['long_pnl']:,.0f}")
    lines.append(f"    SHORT: {metrics['short_trades']} trades, {metrics['short_wr']:.1f}% WR, ${metrics['short_pnl']:,.0f}")
    lines.append("")

    # Overall assessment
    score = 0
    if metrics["win_rate"] >= target["wr"]:
        score += 1
    if metrics["profit_factor"] >= target["pf"]:
        score += 1
    if metrics["net_pnl"] >= target["pnl"]:
        score += 1
    if metrics["trades"] >= target["trades"] * 0.8:  # within 20%
        score += 1

    if score >= 3:
        lines.append(f"  VERDICT: MATCHES STUDY ({score}/4 criteria met)")
    elif score >= 2:
        lines.append(f"  VERDICT: CLOSE ({score}/4 criteria met) — may need tuning")
    else:
        lines.append(f"  VERDICT: BELOW TARGET ({score}/4 criteria met) — needs investigation")

    return "\n".join(lines), score


def main():
    parser = argparse.ArgumentParser(description="Backtest new strategies individually")
    parser.add_argument("--no-merge", action="store_true", help="Skip CSV merge")
    parser.add_argument("--instrument", default="NQ", help="Instrument (default: NQ)")
    parser.add_argument("--strategy", default=None, help="Test single strategy (key name)")
    parser.add_argument("--persist", action="store_true", help="Persist results to DuckDB")
    args = parser.parse_args()

    instrument = args.instrument
    strategies_to_test = [args.strategy] if args.strategy else NEW_STRATEGIES

    # Load data
    log.info(f"Loading {instrument} data...")
    mgr = SessionDataManager()
    if not args.no_merge:
        try:
            mgr.merge_delta(instrument)
        except Exception as e:
            log.warning(f"Merge skipped: {e}")

    df = compute_all_features(mgr.load(instrument))
    log.info(f"Loaded {len(df)} bars across {df['session_date'].nunique()} sessions")

    # Load session bias
    session_bias = {}
    try:
        from rockit_core.research.db import connect as db_connect, query as db_query
        conn = db_connect()
        rows = db_query(conn, "SELECT session_date, bias FROM session_context WHERE bias IS NOT NULL")
        session_bias = {str(r[0]).split(" ")[0].split("T")[0]: r[1] for r in rows}
        conn.close()
        log.info(f"Loaded {len(session_bias)} session biases from DuckDB")
    except Exception as e:
        log.warning(f"Could not load session bias: {e}")

    # Run backtests
    results = {}
    all_comparisons = []

    for strategy_key in strategies_to_test:
        if strategy_key not in STUDY_TARGETS:
            log.warning(f"No study target for {strategy_key}, skipping")
            continue

        log.info(f"\n{'#'*60}")
        log.info(f"  BACKTESTING: {strategy_key}")
        log.info(f"{'#'*60}")

        result = run_single_strategy_backtest(df, instrument, strategy_key, session_bias)
        if result is None:
            log.error(f"  Strategy {strategy_key} not found — skipping")
            continue

        metrics = compute_metrics(result.trades, instrument)
        results[strategy_key] = {"result": result, "metrics": metrics}

        # Print trade details
        log.info(f"\n  Trades ({len(result.trades)}):")
        for t in result.trades:
            outcome = "WIN" if t.net_pnl > 0 else "LOSS"
            log.info(
                f"    {str(t.session_date)[:10]} | {t.strategy_name} | {t.direction} | "
                f"Entry {t.entry_price:.2f} | PnL ${t.net_pnl:+,.0f} | {outcome} | {t.exit_reason}"
            )

        # Compare to target
        comparison, score = compare_to_target(metrics, STUDY_TARGETS[strategy_key], strategy_key)
        log.info(comparison)
        all_comparisons.append((strategy_key, metrics, score))

        # Persist to DuckDB
        if args.persist:
            target = STUDY_TARGETS[strategy_key]
            notes = f"New strategy test: {strategy_key} | Config: {target['config']} | Score: {score}/4"
            persist_to_duckdb(result, strategy_key, instrument, target["config"], notes, metrics)

    # Final summary
    log.info(f"\n{'='*60}")
    log.info(f"  FINAL SUMMARY — New Strategy Backtests")
    log.info(f"{'='*60}")
    log.info(f"\n  {'Strategy':<25s} {'Trades':>7s} {'WR':>7s} {'PF':>7s} {'PnL':>12s} {'Score':>7s}")
    log.info(f"  {'-'*25} {'-'*7} {'-'*7} {'-'*7} {'-'*12} {'-'*7}")
    for strategy_key, metrics, score in all_comparisons:
        pf_str = f"{metrics['profit_factor']:.2f}" if metrics['profit_factor'] < 99 else "99.99+"
        log.info(
            f"  {strategy_key:<25s} {metrics['trades']:>7d} {metrics['win_rate']:>6.1f}% "
            f"{pf_str:>7s} ${metrics['net_pnl']:>10,.0f} {score:>5d}/4"
        )

    passed = sum(1 for _, _, s in all_comparisons if s >= 3)
    total = len(all_comparisons)
    log.info(f"\n  {passed}/{total} strategies match or exceed study targets")

    # Save results JSON
    results_path = project_root / "data" / "results" / f"new_strategies_{instrument}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    results_json = {}
    for key, data in results.items():
        results_json[key] = {
            "metrics": data["metrics"],
            "target": STUDY_TARGETS.get(key, {}),
        }
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results_json, f, indent=2, default=str)
    log.info(f"\n  Results saved to: {results_path}")


if __name__ == "__main__":
    main()
