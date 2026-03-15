#!/usr/bin/env python3
"""
Per-Strategy A/B Test: Deterministic vs LLM Debate

For each strategy, runs:
  A: Mechanical filters only (deterministic baseline)
  B: Mechanical filters + LLM Advocate/Skeptic debate

Persists both runs to DuckDB with labeled run_ids.
Outputs comparison table per strategy.

Usage:
    .venv/Scripts/python.exe scripts/backtest_strategy_ab.py --strategies "OR Acceptance,Opening Range Rev"
    .venv/Scripts/python.exe scripts/backtest_strategy_ab.py --strategies "80P Rule,20P IB Extension,VA Edge Fade,NWOG Gap Fill"
    .venv/Scripts/python.exe scripts/backtest_strategy_ab.py --all
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.agents.agent_filter import AgentFilter
from rockit_core.agents.llm_client import OllamaClient
from rockit_core.agents.pipeline import AgentPipeline
from rockit_core.config.instruments import get_instrument
from rockit_core.data.features import compute_all_features
from rockit_core.data.manager import SessionDataManager
from rockit_core.engine.backtest import BacktestEngine
from rockit_core.filters import BiasAlignmentFilter, CompositeFilter, DayTypeGateFilter
from rockit_core.strategies.loader import get_strategy_class, load_trail_configs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

ALL_12 = [
    "or_reversal", "or_acceptance", "eighty_percent_rule", "twenty_percent_rule",
    "b_day", "trend_bull", "trend_bear", "nwog_gap_fill", "ndog_gap_fill",
    "pdh_pdl_reaction", "va_edge_fade", "ib_edge_fade",
]


def compute_metrics(trades):
    if not trades:
        return {"trades": 0, "win_rate": 0, "profit_factor": 0, "net_pnl": 0,
                "avg_win": 0, "avg_loss": 0, "expectancy": 0}
    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl <= 0]
    wr = len(wins) / len(trades) * 100
    gp = sum(t.net_pnl for t in wins)
    gl = abs(sum(t.net_pnl for t in losses))
    pf = gp / gl if gl > 0 else 99.99
    total = sum(t.net_pnl for t in trades)
    avg_w = float(np.mean([t.net_pnl for t in wins])) if wins else 0
    avg_l = float(np.mean([t.net_pnl for t in losses])) if losses else 0
    exp = (wr / 100 * avg_w) - ((1 - wr / 100) * abs(avg_l))
    return {"trades": len(trades), "win_rate": round(wr, 1), "profit_factor": round(pf, 2),
            "net_pnl": round(total, 2), "avg_win": round(avg_w, 2),
            "avg_loss": round(avg_l, 2), "expectancy": round(exp, 2)}


def run_single_strategy(df, instrument, strategy_key, session_bias, trail_configs,
                        use_debate=False):
    """Run backtest for a single strategy with optional LLM debate."""
    cls = get_strategy_class(strategy_key)
    if cls is None:
        log.warning(f"Strategy {strategy_key} not found")
        return None

    strategy = cls()
    inst = get_instrument(instrument)

    # Build mechanical filters (BiasAlignment only — DayTypeGate needs YAML rules)
    filters = CompositeFilter([
        BiasAlignmentFilter(),
    ])

    # Add agent filter with LLM debate if requested
    if use_debate:
        try:
            llm_client = OllamaClient()  # spark-ai:11434, qwen3.5:35b-a3b
            pipeline = AgentPipeline(enable_debate=True, llm_client=llm_client)
            agent_filter = AgentFilter(pipeline=pipeline)
            filters = CompositeFilter([
                BiasAlignmentFilter(),
                agent_filter,
            ])
        except Exception as e:
            log.warning(f"LLM debate setup failed: {e}. Falling back to deterministic.")

    # Only pass trail config for this strategy
    strat_trail = {}
    if strategy.name in trail_configs:
        strat_trail[strategy.name] = trail_configs[strategy.name]

    engine = BacktestEngine(
        instrument=inst,
        strategies=[strategy],
        filters=filters,
        session_bias_lookup=session_bias or {},
        trail_configs=strat_trail,
    )
    result = engine.run(df, verbose=False)
    return result


def persist_to_duckdb(result, strategy_key, run_label, instrument, metrics):
    """Persist backtest result to DuckDB."""
    try:
        from rockit_core.research.db import connect as db_connect, persist_backtest_from_result
        conn = db_connect()
        run_id = f"ab_{strategy_key}_{run_label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        summary = {
            "trades": metrics["trades"],
            "win_rate": metrics["win_rate"],
            "profit_factor": metrics["profit_factor"],
            "net_pnl": metrics["net_pnl"],
            "max_drawdown": 0,
            "avg_win": metrics["avg_win"],
            "avg_loss": metrics["avg_loss"],
            "expectancy": metrics["expectancy"],
        }
        persist_backtest_from_result(
            conn, result, instrument, summary,
            strategies=[strategy_key],
            config={"run_label": run_label, "debate": run_label == "B_LLM"},
            notes=f"A/B test: {run_label} for {strategy_key}",
        )
        conn.close()
        log.info(f"  Persisted: {run_id}")
        return run_id
    except Exception as e:
        log.warning(f"  DuckDB persist failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategies", default=None, help="Comma-separated strategy keys")
    parser.add_argument("--all", action="store_true", help="Run all 12 strategies")
    parser.add_argument("--instrument", default="NQ")
    parser.add_argument("--no-merge", action="store_true")
    parser.add_argument("--baseline-only", action="store_true", help="Only run A (no LLM)")
    args = parser.parse_args()

    if args.all:
        strategy_keys = ALL_12
    elif args.strategies:
        strategy_keys = [s.strip() for s in args.strategies.split(",")]
    else:
        parser.error("Must specify --strategies or --all")

    # Load data
    log.info(f"Loading {args.instrument} data...")
    mgr = SessionDataManager()
    if not args.no_merge:
        try:
            mgr.merge_delta(args.instrument)
        except Exception:
            pass
    df = compute_all_features(mgr.load(args.instrument))
    log.info(f"Loaded {len(df)} bars, {df['session_date'].nunique()} sessions")

    # Load bias
    session_bias = {}
    try:
        from rockit_core.research.db import connect as db_connect, query as db_query
        conn = db_connect()
        rows = db_query(conn, "SELECT session_date, bias FROM session_context WHERE bias IS NOT NULL")
        session_bias = {str(r[0]).split(" ")[0].split("T")[0]: r[1] for r in rows}
        conn.close()
    except Exception:
        pass

    # Load trail configs
    trail_configs = {}
    try:
        from rockit_core.strategies.loader import load_trail_configs
        trail_configs = load_trail_configs(project_root / "configs" / "strategies.yaml")
    except Exception:
        pass

    # Results
    results = []

    for key in strategy_keys:
        cls = get_strategy_class(key)
        if cls is None:
            log.warning(f"Unknown strategy: {key}")
            continue
        strat_name = cls().name

        log.info(f"\n{'='*60}")
        log.info(f"  {strat_name} ({key})")
        log.info(f"{'='*60}")

        # Run A: Deterministic baseline
        log.info(f"  Run A: Mechanical filters only...")
        result_a = run_single_strategy(df, args.instrument, key, session_bias,
                                       trail_configs, use_debate=False)
        if result_a is None:
            continue
        metrics_a = compute_metrics(result_a.trades)
        log.info(f"  A: {metrics_a['trades']}t, {metrics_a['win_rate']}% WR, "
                 f"PF {metrics_a['profit_factor']}, ${metrics_a['net_pnl']:,.0f}")
        persist_to_duckdb(result_a, key, "A_deterministic", args.instrument, metrics_a)

        # Run B: With LLM debate
        metrics_b = None
        if not args.baseline_only:
            log.info(f"  Run B: Mechanical + LLM debate...")
            result_b = run_single_strategy(df, args.instrument, key, session_bias,
                                           trail_configs, use_debate=True)
            if result_b:
                metrics_b = compute_metrics(result_b.trades)
                log.info(f"  B: {metrics_b['trades']}t, {metrics_b['win_rate']}% WR, "
                         f"PF {metrics_b['profit_factor']}, ${metrics_b['net_pnl']:,.0f}")
                persist_to_duckdb(result_b, key, "B_LLM", args.instrument, metrics_b)

        results.append({
            "strategy": strat_name,
            "key": key,
            "A": metrics_a,
            "B": metrics_b,
        })

    # Summary table
    log.info(f"\n{'='*80}")
    log.info(f"  A/B TEST SUMMARY")
    log.info(f"{'='*80}")
    log.info(f"  {'Strategy':<22s} | {'A: Deterministic':^30s} | {'B: LLM Debate':^30s} | Delta PnL")
    log.info(f"  {'':<22s} | {'Trades WR%   PF     PnL':^30s} | {'Trades WR%   PF     PnL':^30s} |")
    log.info(f"  {'-'*22}-+-{'-'*30}-+-{'-'*30}-+-{'-'*10}")

    total_a = 0
    total_b = 0
    for r in results:
        a = r["A"]
        b = r["B"]
        total_a += a["net_pnl"]

        a_str = f"{a['trades']:>4d} {a['win_rate']:>5.1f}% {a['profit_factor']:>5.2f} ${a['net_pnl']:>8,.0f}"

        if b:
            total_b += b["net_pnl"]
            b_str = f"{b['trades']:>4d} {b['win_rate']:>5.1f}% {b['profit_factor']:>5.2f} ${b['net_pnl']:>8,.0f}"
            delta = b["net_pnl"] - a["net_pnl"]
            d_str = f"${delta:>+8,.0f}"
        else:
            b_str = "  (not run)"
            d_str = ""

        log.info(f"  {r['strategy']:<22s} | {a_str} | {b_str} | {d_str}")

    if total_b > 0:
        log.info(f"\n  Total A: ${total_a:,.0f}  |  Total B: ${total_b:,.0f}  |  Delta: ${total_b - total_a:>+,.0f}")

    # Save JSON
    out_path = project_root / "data" / "results" / f"ab_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    log.info(f"\nResults saved: {out_path}")


if __name__ == "__main__":
    main()
