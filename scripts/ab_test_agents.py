#!/usr/bin/env python3
"""
A/B test agents vs mechanical filters — runs 4-5 backtests.

Runs:
  A: No filters (baseline)
  B: Mechanical filters only (bias + day_type_gate + anti_chase)
  C: Mechanical + Agent filter
  D: Agent filter only
  E: Mechanical + Agent + LLM debate (--enable-debate)

Also persists agent decisions to DuckDB and backfills actual outcomes.

Usage:
    python scripts/ab_test_agents.py
    python scripts/ab_test_agents.py --no-merge
    python scripts/ab_test_agents.py --instrument ES
    python scripts/ab_test_agents.py --no-merge --enable-debate
"""

import argparse
import gc
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.agents.agent_filter import AgentFilter
from rockit_core.agents.llm_client import OllamaClient
from rockit_core.agents.orchestrator import DeterministicOrchestrator
from rockit_core.agents.pipeline import AgentPipeline
from rockit_core.config.instruments import get_instrument
from rockit_core.data.features import compute_all_features
from rockit_core.data.manager import SessionDataManager
from rockit_core.engine.backtest import BacktestEngine
from rockit_core.filters import (
    AntiChaseFilter,
    BiasAlignmentFilter,
    CompositeFilter,
    DayTypeGateFilter,
)
from rockit_core.research.db import (
    connect as db_connect,
    persist_agent_decision,
    persist_backtest_from_result,
    query as db_query,
)


def compute_summary(result, instrument):
    """Compute summary metrics from backtest result."""
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

    # MAE/MFE stats
    mae_pts = [abs(t.entry_price - t.mae_price) for t in trades if t.mae_price]
    mfe_pts = [abs(t.mfe_price - t.entry_price) for t in trades if t.mfe_price]
    avg_mae = float(np.mean(mae_pts)) if mae_pts else 0
    avg_mfe = float(np.mean(mfe_pts)) if mfe_pts else 0

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
        "avg_mae": round(avg_mae, 2), "avg_mfe": round(avg_mfe, 2),
        "signals_generated": result.signals_generated,
        "signals_filtered": result.signals_filtered,
        "by_strategy": by_strategy,
    }


def get_mechanical_filters():
    """Build the mechanical filter combo (same as production Run B)."""
    bias_rules = [
        {"strategy": "80P Rule", "blocked_day_types": ["neutral", "neutral_range", "Neutral Range"]},
        {"strategy": "B-Day", "blocked_day_types": ["trend_up", "trend_down", "Trend Up", "Trend Down"]},
    ]
    # AntiChase removed for 80P — investigation showed it killed 53/72 signals
    # including profitable SHORT+Bearish setups (67% WR, +$27K in baseline).
    # 80P is a mean-reversion strategy; trading WITH bias is legitimate, not chasing.
    return [
        BiasAlignmentFilter(neutral_passes=True),
        DayTypeGateFilter(rules=bias_rules),
    ]


def get_agent_filter(enable_debate=False):
    """Build the agent filter with default pipeline.

    Args:
        enable_debate: If True, enables LLM Advocate/Skeptic debate layer.
    """
    orchestrator = DeterministicOrchestrator(
        take_threshold=0.3,
        skip_threshold=0.1,
    )

    llm_client = None
    if enable_debate:
        llm_client = OllamaClient(
            base_url="http://spark-ai:11434/v1",
            model="qwen3.5:35b-a3b",
            timeout=180,
        )
        if not llm_client.is_available():
            print("WARNING: LLM endpoint not reachable — debate will be disabled")
            llm_client = None

    pipeline = AgentPipeline(
        orchestrator=orchestrator,
        llm_client=llm_client,
        enable_debate=enable_debate,
    )
    return AgentFilter(pipeline=pipeline)


def run_one(label, df, instrument, filters, session_bias_lookup, conn):
    """Run one backtest variant and persist to DuckDB."""
    print(f"\n{'='*70}")
    print(f"  RUN: {label}")
    print(f"{'='*70}")

    inst_spec = get_instrument(instrument)
    strats = load_strategies()

    engine = BacktestEngine(
        instrument=inst_spec,
        strategies=strats,
        filters=filters,
        session_bias_lookup=session_bias_lookup,
    )

    result = engine.run(df, verbose=True)
    summary = compute_summary(result, instrument)

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
        "test_type": "agent_ab_test",
    }

    run_id = persist_backtest_from_result(
        conn, result, instrument, summary,
        [s.name for s in strats],
        config=config,
        notes=f"Agent A/B test: {label}",
    )

    print(f"  Trades: {summary['trades']}, WR: {summary['win_rate']}%, "
          f"PF: {summary['profit_factor']}, Net: ${summary['net_pnl']:,.2f}")
    print(f"  Expectancy: ${summary['expectancy']:,.2f}, "
          f"MAE: {summary['avg_mae']:.1f}pts, MFE: {summary['avg_mfe']:.1f}pts")
    print(f"  Signals: {summary['signals_generated']} generated, "
          f"{summary['signals_filtered']} filtered")
    print(f"  Persisted: {run_id}")

    return summary, run_id, result


def persist_agent_decisions_with_outcomes(conn, agent_filter, run_id, result,
                                          baseline_result=None):
    """Match agent decisions to actual trade outcomes and persist.

    For TAKE decisions: match against result.trades (what actually happened).
    For SKIP decisions: match against baseline_result.trades (what WOULD have happened
    if the signal wasn't filtered). This is critical for evaluating skip quality.
    """
    if not agent_filter or not hasattr(agent_filter, 'decisions'):
        return 0

    # Build trade lookup by (strategy, session_date) for outcome matching
    trade_lookup = {}
    for t in result.trades:
        key = (t.strategy_name, str(t.session_date).split(' ')[0].split('T')[0])
        trade_lookup.setdefault(key, []).append(t)

    # Build baseline lookup for SKIP outcome matching
    baseline_lookup = {}
    if baseline_result:
        for t in baseline_result.trades:
            key = (t.strategy_name, str(t.session_date).split(' ')[0].split('T')[0])
            baseline_lookup.setdefault(key, []).append(t)

    count = 0
    for decision in agent_filter.decisions:
        dec_dict = decision.to_dict()

        # Extract signal metadata (attached by AgentFilter.should_trade)
        meta = getattr(decision, 'signal_metadata', {})
        strategy = meta.get("strategy_name", "unknown")
        session_date = meta.get("session_date", "")
        signal_dir = meta.get("signal_direction", "")
        signal_time = meta.get("signal_time", "")

        # Normalize session_date for matching
        session_date_norm = str(session_date).split(' ')[0].split('T')[0]

        dec_dict["strategy_name"] = strategy
        dec_dict["session_date"] = session_date
        dec_dict["signal_direction"] = signal_dir
        dec_dict["signal_time"] = signal_time
        dec_dict["setup_type"] = meta.get("setup_type", "")

        actual_outcome = None
        actual_pnl = None
        was_correct = None
        trade_key = (strategy, session_date_norm)

        if decision.decision in ("TAKE", "REDUCE_SIZE"):
            # For TAKE: look in this run's actual trades
            if trade_key in trade_lookup and trade_lookup[trade_key]:
                trade = trade_lookup[trade_key][0]
                actual_outcome = "WIN" if trade.net_pnl > 0 else "LOSS"
                actual_pnl = trade.net_pnl
                was_correct = trade.net_pnl > 0
                dec_dict["trade_id"] = trade.trade_id
        elif decision.decision == "SKIP":
            # For SKIP: look in baseline (what WOULD have happened)
            if trade_key in baseline_lookup and baseline_lookup[trade_key]:
                trade = baseline_lookup[trade_key][0]
                actual_outcome = "WIN" if trade.net_pnl > 0 else "LOSS"
                actual_pnl = trade.net_pnl
                was_correct = trade.net_pnl <= 0  # Correct skip = avoided a loss
                dec_dict["trade_id"] = trade.trade_id
            elif trade_key in trade_lookup and trade_lookup[trade_key]:
                # Fallback: check current run trades
                trade = trade_lookup[trade_key][0]
                actual_outcome = "WIN" if trade.net_pnl > 0 else "LOSS"
                actual_pnl = trade.net_pnl
                was_correct = trade.net_pnl <= 0

        dec_dict["actual_outcome"] = actual_outcome
        dec_dict["actual_pnl"] = actual_pnl
        dec_dict["was_correct"] = was_correct

        decision_id = f"{run_id}_{uuid.uuid4().hex[:8]}"
        persist_agent_decision(conn, decision_id, run_id, dec_dict)
        count += 1

    return count


def load_strategies():
    """Load strategies from config."""
    from rockit_core.strategies.loader import load_strategies_from_config
    return load_strategies_from_config(project_root / "configs" / "strategies.yaml")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="A/B test agents vs mechanical filters")
    parser.add_argument("--no-merge", action="store_true")
    parser.add_argument("--instrument", default="NQ")
    parser.add_argument("--enable-debate", action="store_true",
                        help="Add Run E with LLM Advocate/Skeptic debate (~30s/signal)")
    parser.add_argument("--debate-only", action="store_true",
                        help="Only run E (LLM debate), skip A-D")
    args = parser.parse_args()

    instrument = args.instrument.upper()

    # Load data
    mgr = SessionDataManager(data_dir="data/sessions")
    if not args.no_merge:
        print("Merging latest data...")
        df = mgr.merge_delta(instrument)
    else:
        df = mgr.load(instrument)

    gc.collect()
    df = compute_all_features(df)
    gc.collect()

    # Load session bias from DuckDB
    session_bias_lookup = {}
    try:
        conn = db_connect()
        rows = db_query(conn, "SELECT session_date, bias FROM session_context WHERE bias IS NOT NULL")
        session_bias_lookup = {str(r[0]).split(" ")[0]: r[1] for r in rows}
        print(f"Loaded session bias for {len(session_bias_lookup)} sessions")
    except Exception as e:
        print(f"Warning: Could not load session bias: {e}")
        conn = db_connect()

    # Build filter configs for each run
    mechanical = get_mechanical_filters()
    agent_c = get_agent_filter()
    agent_d = get_agent_filter()

    if args.debate_only:
        agent_e = get_agent_filter(enable_debate=True)
        configs = {
            "A: No filters (baseline)": None,  # Always run baseline for SKIP outcome matching
            "E: Mech + Agent + LLM Debate": CompositeFilter(get_mechanical_filters() + [agent_e]),
        }
    else:
        configs = {
            "A: No filters (baseline)": None,
            "B: Mechanical only": CompositeFilter(mechanical),
            "C: Mechanical + Agent": CompositeFilter(get_mechanical_filters() + [agent_c]),
            "D: Agent only": CompositeFilter([agent_d]),
        }

        if args.enable_debate:
            agent_e = get_agent_filter(enable_debate=True)
            configs["E: Mech + Agent + LLM Debate"] = CompositeFilter(
                get_mechanical_filters() + [agent_e]
            )

    results = {}
    run_results = {}  # Store BacktestResult objects for cross-referencing
    baseline_result = None
    for label, filters in configs.items():
        summary, run_id, result = run_one(
            label, df, instrument, filters, session_bias_lookup, conn
        )
        results[label] = summary
        run_results[label] = result

        # Track baseline for SKIP outcome matching
        if "A:" in label or "baseline" in label.lower():
            baseline_result = result

        # Persist agent decisions for runs C, D, E
        if "Agent" in label or "Debate" in label:
            if "E:" in label:
                af = agent_e
            elif "C:" in label:
                af = agent_c
            else:
                af = agent_d
            n = persist_agent_decisions_with_outcomes(
                conn, af, run_id, result, baseline_result=baseline_result
            )
            if n:
                print(f"  Agent decisions persisted: {n}")

    # Comparison table
    print(f"\n{'='*100}")
    print("AGENT A/B TEST COMPARISON")
    print(f"{'='*100}")
    header = (f"{'Run':40s} {'Trades':>7s} {'WR%':>7s} {'PF':>7s} "
              f"{'Net PnL':>12s} {'Expect':>9s} {'MAE':>7s} {'MFE':>7s} {'$/Trade':>9s}")
    print(header)
    print("-" * 100)
    for label, s in results.items():
        trades = s["trades"]
        per_trade = s["net_pnl"] / trades if trades > 0 else 0
        print(f"{label:40s} {trades:7d} {s['win_rate']:6.1f}% {s['profit_factor']:7.2f} "
              f"${s['net_pnl']:>10,.2f} ${s['expectancy']:>7,.2f} "
              f"{s.get('avg_mae', 0):6.1f} {s.get('avg_mfe', 0):6.1f} ${per_trade:>8,.2f}")

    # Strategy breakdown for runs B vs C
    print(f"\n{'='*100}")
    print("STRATEGY BREAKDOWN: B (Mechanical) vs C (Mechanical + Agent)")
    print(f"{'='*100}")
    b_strats = results.get("B: Mechanical only", {}).get("by_strategy", {})
    c_strats = results.get("C: Mechanical + Agent", {}).get("by_strategy", {})
    all_strat_names = sorted(set(list(b_strats.keys()) + list(c_strats.keys())))

    print(f"{'Strategy':25s} {'B Trades':>8s} {'B WR%':>7s} {'B PF':>7s} "
          f"{'C Trades':>8s} {'C WR%':>7s} {'C PF':>7s} {'Delta WR':>9s}")
    print("-" * 90)
    for sname in all_strat_names:
        b = b_strats.get(sname, {"trades": 0, "win_rate": 0, "profit_factor": 0})
        c = c_strats.get(sname, {"trades": 0, "win_rate": 0, "profit_factor": 0})
        delta_wr = c["win_rate"] - b["win_rate"] if b["trades"] > 0 else 0
        sign = "+" if delta_wr >= 0 else ""
        print(f"{sname:25s} {b['trades']:8d} {b['win_rate']:6.1f}% {b['profit_factor']:7.2f} "
              f"{c['trades']:8d} {c['win_rate']:6.1f}% {c['profit_factor']:7.2f} "
              f"{sign}{delta_wr:7.1f}%")

    conn.close()
    print("\nDone. All runs persisted to DuckDB.")


if __name__ == "__main__":
    main()
