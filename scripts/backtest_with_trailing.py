#!/usr/bin/env python3
"""
Backtest core 5 strategies WITH per-strategy ATR trailing stops.

Compares: baseline (no trail) vs trailing (OR Rev + OR Accept trail enabled).

Usage:
    python scripts/backtest_with_trailing.py --no-merge
"""

import argparse
import gc
import json
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
from rockit_core.strategies.loader import load_strategies_from_config, load_trail_configs

CORE_5 = {"Opening Range Rev", "OR Acceptance", "80P Rule", "20P IB Extension", "B-Day"}


def compute_summary(result, instrument):
    trades = result.trades
    if not trades:
        return {"trades": 0, "win_rate": 0, "profit_factor": 0, "net_pnl": 0}
    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl <= 0]
    total_pnl = sum(t.net_pnl for t in trades)
    win_rate = len(wins) / len(trades) * 100
    avg_win = float(np.mean([t.net_pnl for t in wins])) if wins else 0
    avg_loss = float(np.mean([t.net_pnl for t in losses])) if losses else 0
    gross_profit = sum(t.net_pnl for t in wins)
    gross_loss = abs(sum(t.net_pnl for t in losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")

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
        s_avg_w = float(np.mean([t.net_pnl for t in s_wins])) if s_wins else 0
        s_avg_l = float(np.mean([t.net_pnl for t in s_losses])) if s_losses else 0

        # Exit reason breakdown
        reasons = {}
        for t in strades:
            reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1

        by_strategy[sname] = {
            "trades": len(strades), "win_rate": round(s_wr, 1),
            "net_pnl": round(s_pnl, 2),
            "profit_factor": round(s_gp / s_gl, 2) if s_gl > 0 else float("inf"),
            "avg_win": round(s_avg_w, 2), "avg_loss": round(s_avg_l, 2),
            "exit_reasons": reasons,
        }

    return {
        "instrument": instrument, "sessions": result.sessions_processed,
        "trades": len(trades), "win_rate": round(win_rate, 1),
        "profit_factor": round(pf, 2), "net_pnl": round(total_pnl, 2),
        "avg_win": round(avg_win, 2), "avg_loss": round(avg_loss, 2),
        "by_strategy": by_strategy,
    }


def run_backtest(label, df, instrument, strategies, session_bias, trail_configs=None):
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    if trail_configs:
        for sname, cfg in trail_configs.items():
            print(f"  Trail: {sname} -> ATR({cfg['atr_period']}) "
                  f"act={cfg['activate_mult']}x trail={cfg['trail_mult']}x")

    inst_spec = get_instrument(instrument)
    engine = BacktestEngine(
        instrument=inst_spec, strategies=strategies,
        session_bias_lookup=session_bias,
        trail_configs=trail_configs or {},
    )
    result = engine.run(df, verbose=True)
    summary = compute_summary(result, instrument)

    print(f"\n  Total: {summary['trades']} trades, WR={summary['win_rate']}%, "
          f"PF={summary['profit_factor']}, Net=${summary['net_pnl']:,.0f}")
    return summary, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-merge", action="store_true")
    parser.add_argument("--instrument", default="NQ")
    parser.add_argument("--max-sessions", type=int, default=0,
                        help="Limit to first N sessions (0 = all)")
    parser.add_argument("--with-llm", action="store_true",
                        help="Add Run C: Mech + Agent + LLM Debate + Trailing")
    args = parser.parse_args()
    instrument = args.instrument.upper()

    print(f"{'='*70}")
    print(f"TRAILING STOP BACKTEST - {instrument}")
    print(f"{'='*70}\n")

    mgr = SessionDataManager(data_dir="data/sessions")
    df = mgr.load(instrument) if args.no_merge else mgr.merge_delta(instrument)
    gc.collect()
    df = compute_all_features(df)
    gc.collect()

    # Limit sessions if requested
    if args.max_sessions > 0:
        sessions = sorted(df['session_date'].unique())
        if len(sessions) > args.max_sessions:
            keep = sessions[:args.max_sessions]
            df = df[df['session_date'].isin(keep)]
            print(f"Limited to first {args.max_sessions} sessions (of {len(sessions)})")

    session_bias = {}
    try:
        from rockit_core.research.db import connect as db_connect, query as db_query
        conn = db_connect()
        rows = db_query(conn, "SELECT session_date, bias FROM session_context WHERE bias IS NOT NULL")
        session_bias = {str(r[0]).split(" ")[0]: r[1] for r in rows}
        conn.close()
        print(f"Loaded bias for {len(session_bias)} sessions")
    except Exception:
        pass

    # Load core 5 only
    all_strats = load_strategies_from_config(project_root / "configs" / "strategies.yaml")
    strategies = [s for s in all_strats if s.name in CORE_5]
    print(f"Core 5: {[s.name for s in strategies]}")

    # Load trail configs from YAML
    trail_configs = load_trail_configs(project_root / "configs" / "strategies.yaml")
    print(f"Trail configs: {list(trail_configs.keys())}")

    # Run A: Baseline (no trailing)
    summary_a, result_a = run_backtest(
        "A: Baseline (no trailing)", df, instrument, strategies, session_bias,
        trail_configs=None)

    # Run B: With per-strategy trailing
    summary_b, result_b = run_backtest(
        "B: Per-Strategy ATR Trailing", df, instrument, strategies, session_bias,
        trail_configs=trail_configs)

    # Run C: Mechanical + Agent + LLM Debate + Trailing (optional)
    summary_c = None
    if args.with_llm:
        import logging
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
        logging.getLogger("rockit_core.data").setLevel(logging.WARNING)
        logging.getLogger("rockit_core.engine").setLevel(logging.WARNING)
        logging.getLogger("rockit_core.strategies").setLevel(logging.WARNING)

        from rockit_core.agents.agent_filter import AgentFilter
        from rockit_core.agents.llm_client import OllamaClient
        from rockit_core.agents.orchestrator import DeterministicOrchestrator
        from rockit_core.agents.pipeline import AgentPipeline
        from rockit_core.filters import BiasAlignmentFilter, CompositeFilter, DayTypeGateFilter

        # Mechanical filters
        bias_rules = [
            {"strategy": "80P Rule", "blocked_day_types": ["neutral", "neutral_range", "Neutral Range"]},
            {"strategy": "B-Day", "blocked_day_types": ["trend_up", "trend_down", "Trend Up", "Trend Down"]},
        ]
        mech_filters = [
            BiasAlignmentFilter(neutral_passes=True),
            DayTypeGateFilter(rules=bias_rules),
        ]

        # Agent + LLM debate
        llm_client = OllamaClient(
            base_url="http://spark-ai:11434/v1",
            model="qwen3.5:35b-a3b",
            timeout=180,
        )
        if not llm_client.is_available():
            print("WARNING: LLM endpoint not reachable — skipping Run C")
        else:
            orchestrator = DeterministicOrchestrator(take_threshold=0.3, skip_threshold=0.1)
            pipeline = AgentPipeline(
                orchestrator=orchestrator,
                llm_client=llm_client,
                enable_debate=True,
            )
            agent_filter = AgentFilter(pipeline=pipeline)
            filters = CompositeFilter(mech_filters + [agent_filter])

            # Run C needs its own engine with filters + trailing
            print(f"\n{'='*70}")
            print(f"  C: Mech + Agent + LLM Debate + Trailing")
            print(f"{'='*70}")
            for sname, cfg in trail_configs.items():
                print(f"  Trail: {sname} -> ATR({cfg['atr_period']}) "
                      f"act={cfg['activate_mult']}x trail={cfg['trail_mult']}x")

            inst_spec = get_instrument(instrument)
            engine_c = BacktestEngine(
                instrument=inst_spec, strategies=strategies,
                filters=filters,
                session_bias_lookup=session_bias,
                trail_configs=trail_configs,
            )
            result_c = engine_c.run(df, verbose=True)
            summary_c = compute_summary(result_c, instrument)
            print(f"\n  Total: {summary_c['trades']} trades, WR={summary_c['win_rate']}%, "
                  f"PF={summary_c['profit_factor']}, Net=${summary_c['net_pnl']:,.0f}")

    # Comparison
    print(f"\n{'='*120}")
    print("COMPARISON: Baseline vs Per-Strategy Trailing")
    print(f"{'='*120}")

    print(f"\n  {'':25s} {'BASELINE':>50s}    {'TRAILING':>50s}    {'DELTA':>20s}")
    print(f"  {'Strategy':25s} {'Trades':>6s} {'WR%':>6s} {'PF':>6s} {'Net':>10s} {'AvgW':>7s} {'AvgL':>7s}    "
          f"{'Trades':>6s} {'WR%':>6s} {'PF':>6s} {'Net':>10s} {'AvgW':>7s} {'AvgL':>7s}    {'PF':>6s} {'PnL':>10s}")
    print(f"  {'-'*120}")

    all_strat_names = sorted(set(
        list(summary_a['by_strategy'].keys()) + list(summary_b['by_strategy'].keys())
    ))

    for sname in all_strat_names:
        a = summary_a['by_strategy'].get(sname, {})
        b = summary_b['by_strategy'].get(sname, {})
        trailed = "(*)" if sname in trail_configs else "   "

        a_t = a.get('trades', 0)
        a_wr = a.get('win_rate', 0)
        a_pf = a.get('profit_factor', 0)
        a_pnl = a.get('net_pnl', 0)
        a_aw = a.get('avg_win', 0)
        a_al = a.get('avg_loss', 0)

        b_t = b.get('trades', 0)
        b_wr = b.get('win_rate', 0)
        b_pf = b.get('profit_factor', 0)
        b_pnl = b.get('net_pnl', 0)
        b_aw = b.get('avg_win', 0)
        b_al = b.get('avg_loss', 0)

        dpf = b_pf - a_pf
        dpnl = b_pnl - a_pnl

        print(f"{trailed}{sname:22s} {a_t:6d} {a_wr:5.1f}% {a_pf:6.2f} ${a_pnl:>8,.0f} ${a_aw:>5,.0f} ${a_al:>5,.0f}    "
              f"{b_t:6d} {b_wr:5.1f}% {b_pf:6.2f} ${b_pnl:>8,.0f} ${b_aw:>5,.0f} ${b_al:>5,.0f}    {dpf:+5.2f} ${dpnl:>+9,.0f}")

    print(f"  {'-'*120}")
    dpf_t = summary_b['profit_factor'] - summary_a['profit_factor']
    dpnl_t = summary_b['net_pnl'] - summary_a['net_pnl']
    print(f"   {'TOTAL':22s} {summary_a['trades']:6d} {summary_a['win_rate']:5.1f}% {summary_a['profit_factor']:6.2f} "
          f"${summary_a['net_pnl']:>8,.0f} ${summary_a['avg_win']:>5,.0f} ${summary_a['avg_loss']:>5,.0f}    "
          f"{summary_b['trades']:6d} {summary_b['win_rate']:5.1f}% {summary_b['profit_factor']:6.2f} "
          f"${summary_b['net_pnl']:>8,.0f} ${summary_b['avg_win']:>5,.0f} ${summary_b['avg_loss']:>5,.0f}    "
          f"{dpf_t:+5.2f} ${dpnl_t:>+9,.0f}")

    print(f"\n  (*) = trailing enabled for this strategy")

    # Run C summary if available
    if summary_c:
        print(f"\n  {'='*120}")
        print(f"  Run C: Mech + Agent + LLM Debate + Trailing")
        print(f"  {'='*120}")
        print(f"  {'Strategy':25s} {'Trades':>6s} {'WR%':>6s} {'PF':>6s} {'Net':>10s}    vs B(Trail) PF     vs B(Trail) PnL")
        print(f"  {'-'*100}")
        for sname in sorted(summary_c['by_strategy'].keys()):
            c = summary_c['by_strategy'][sname]
            b = summary_b['by_strategy'].get(sname, {})
            dpf = c.get('profit_factor', 0) - b.get('profit_factor', 0)
            dpnl = c.get('net_pnl', 0) - b.get('net_pnl', 0)
            trailed = "(*)" if sname in trail_configs else "   "
            print(f"{trailed}{sname:22s} {c['trades']:6d} {c['win_rate']:5.1f}% {c['profit_factor']:6.2f} "
                  f"${c['net_pnl']:>8,.0f}    {dpf:+6.2f}          ${dpnl:>+9,.0f}")
        print(f"  {'-'*100}")
        print(f"   {'TOTAL':22s} {summary_c['trades']:6d} {summary_c['win_rate']:5.1f}% {summary_c['profit_factor']:6.2f} "
              f"${summary_c['net_pnl']:>8,.0f}    "
              f"{summary_c['profit_factor'] - summary_b['profit_factor']:+6.2f}          "
              f"${summary_c['net_pnl'] - summary_b['net_pnl']:>+9,.0f}")

    # Exit reason comparison for trailed strategies
    print(f"\n  Exit Reasons (trailed strategies only):")
    for sname in trail_configs:
        a_reasons = summary_a['by_strategy'].get(sname, {}).get('exit_reasons', {})
        b_reasons = summary_b['by_strategy'].get(sname, {}).get('exit_reasons', {})
        print(f"    {sname}:")
        print(f"      Baseline: {a_reasons}")
        print(f"      Trailing: {b_reasons}")
        if summary_c:
            c_reasons = summary_c['by_strategy'].get(sname, {}).get('exit_reasons', {})
            print(f"      LLM+Trail: {c_reasons}")

    # Save results
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = {"baseline": summary_a, "trailing": summary_b, "trail_configs": trail_configs}
    if summary_c:
        out["llm_trailing"] = summary_c
    path = project_root / "data" / "results" / f"trailing_test_{instrument}_{ts}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()
