#!/usr/bin/env python3
"""
Expert Mode Backtest — compare legacy (9 cards) vs expert (25+ cards) pipeline.

Runs:
  A: No filters (baseline) — core 5 strategies only
  B: Mechanical + Legacy Agent (Run E equivalent)
  C: Mechanical + Expert Agent (9 domain experts, no LLM)
  D: Mechanical + Expert Agent + LLM Debate

Does NOT persist to DuckDB. Saves results to data/results/ with "expert-mode" label.

Usage:
    python scripts/backtest_expert_mode.py --no-merge
    python scripts/backtest_expert_mode.py --no-merge --skip-llm
"""

import argparse
import gc
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
from rockit_core.agents.orchestrator import DeterministicOrchestrator
from rockit_core.agents.pipeline import AgentPipeline
from rockit_core.config.instruments import get_instrument
from rockit_core.data.features import compute_all_features
from rockit_core.data.manager import SessionDataManager
from rockit_core.engine.backtest import BacktestEngine
from rockit_core.filters import (
    BiasAlignmentFilter,
    CompositeFilter,
    DayTypeGateFilter,
)
from rockit_core.strategies.loader import load_strategies_from_config

# Core 5 strategies
CORE_5 = {"Opening Range Rev", "OR Acceptance", "80P Rule", "20P IB Extension", "B-Day"}


def load_core_strategies():
    """Load only the core 5 strategies."""
    all_strats = load_strategies_from_config(project_root / "configs" / "strategies.yaml")
    core = [s for s in all_strats if s.name in CORE_5]
    print(f"Loaded {len(core)} core strategies: {[s.name for s in core]}")
    return core


def get_mechanical_filters():
    """Same mechanical filters as production Run B."""
    bias_rules = [
        {"strategy": "80P Rule", "blocked_day_types": ["neutral", "neutral_range", "Neutral Range"]},
        {"strategy": "B-Day", "blocked_day_types": ["trend_up", "trend_down", "Trend Up", "Trend Down"]},
    ]
    return [
        BiasAlignmentFilter(neutral_passes=True),
        DayTypeGateFilter(rules=bias_rules),
    ]


def get_agent_filter_legacy(enable_debate=False, llm_client=None):
    """Legacy pipeline: ProfileObserver + MomentumObserver (9 cards)."""
    orchestrator = DeterministicOrchestrator(take_threshold=0.3, skip_threshold=0.1)
    pipeline = AgentPipeline(
        orchestrator=orchestrator,
        llm_client=llm_client if enable_debate else None,
        enable_debate=enable_debate,
        preset=AgentPipeline.PRESET_LEGACY,
    )
    return AgentFilter(pipeline=pipeline)


def get_agent_filter_expert(enable_debate=False, llm_client=None):
    """Expert pipeline: 9 domain experts + ConflictDetector (25+ cards)."""
    orchestrator = DeterministicOrchestrator(take_threshold=0.3, skip_threshold=0.1)
    pipeline = AgentPipeline(
        orchestrator=orchestrator,
        llm_client=llm_client if enable_debate else None,
        enable_debate=enable_debate,
        preset=AgentPipeline.PRESET_EXPERTS,
    )
    return AgentFilter(pipeline=pipeline)


def compute_summary(result, instrument):
    """Compute summary metrics from backtest result."""
    trades = result.trades
    if not trades:
        return {"trades": 0, "win_rate": 0, "profit_factor": 0, "net_pnl": 0,
                "sessions": result.sessions_processed, "by_strategy": {},
                "by_direction": {}}

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

        # Direction breakdown
        long_trades = [t for t in strades if t.direction == "LONG"]
        short_trades = [t for t in strades if t.direction == "SHORT"]
        long_wins = [t for t in long_trades if t.net_pnl > 0]
        short_wins = [t for t in short_trades if t.net_pnl > 0]

        by_strategy[sname] = {
            "trades": len(strades), "win_rate": round(s_wr, 1),
            "net_pnl": round(s_pnl, 2),
            "profit_factor": round(s_gp / s_gl, 2) if s_gl > 0 else float("inf"),
            "long_trades": len(long_trades),
            "long_wr": round(len(long_wins) / len(long_trades) * 100, 1) if long_trades else 0,
            "long_pnl": round(sum(t.net_pnl for t in long_trades), 2),
            "short_trades": len(short_trades),
            "short_wr": round(len(short_wins) / len(short_trades) * 100, 1) if short_trades else 0,
            "short_pnl": round(sum(t.net_pnl for t in short_trades), 2),
        }

    return {
        "instrument": instrument, "sessions": result.sessions_processed,
        "trades": len(trades), "win_rate": round(win_rate, 1),
        "profit_factor": round(pf, 2), "net_pnl": round(total_pnl, 2),
        "avg_win": round(avg_win, 2), "avg_loss": round(avg_loss, 2),
        "expectancy": round(expectancy, 2),
        "signals_generated": result.signals_generated,
        "signals_filtered": result.signals_filtered,
        "by_strategy": by_strategy,
    }


def analyze_agent_decisions(agent_filter, label):
    """Print decision breakdown for an agent filter."""
    if not agent_filter or not hasattr(agent_filter, 'decisions'):
        return

    decisions = agent_filter.decisions
    if not decisions:
        return

    take_count = sum(1 for d in decisions if d.decision == "TAKE")
    skip_count = sum(1 for d in decisions if d.decision == "SKIP")
    reduce_count = sum(1 for d in decisions if d.decision == "REDUCE_SIZE")

    print(f"\n  --- {label} Decision Breakdown ---")
    print(f"  TAKE: {take_count}  SKIP: {skip_count}  REDUCE: {reduce_count}")
    print(f"  SKIP rate: {skip_count / len(decisions) * 100:.1f}%")

    # Card count stats
    card_counts = [len(d.evidence_cards) for d in decisions]
    if card_counts:
        print(f"  Cards/signal: avg={np.mean(card_counts):.1f}, min={min(card_counts)}, max={max(card_counts)}")

    # Sample some SKIP reasons
    skips = [d for d in decisions if d.decision == "SKIP"]
    if skips:
        print(f"  Sample SKIP reasons:")
        for d in skips[:3]:
            meta = getattr(d, 'signal_metadata', {})
            strat = meta.get("strategy_name", "?")
            direction = meta.get("signal_direction", "?")
            print(f"    {strat} {direction}: {d.reasoning[:100]}")


def run_one(label, df, instrument, filters, session_bias_lookup, strategies):
    """Run one backtest variant."""
    print(f"\n{'='*70}")
    print(f"  RUN: {label}")
    print(f"{'='*70}")

    inst_spec = get_instrument(instrument)
    engine = BacktestEngine(
        instrument=inst_spec,
        strategies=strategies,
        filters=filters,
        session_bias_lookup=session_bias_lookup,
    )

    result = engine.run(df, verbose=True)
    summary = compute_summary(result, instrument)

    print(f"  Trades: {summary['trades']}, WR: {summary['win_rate']}%, "
          f"PF: {summary['profit_factor']}, Net: ${summary['net_pnl']:,.2f}")
    print(f"  Expectancy: ${summary['expectancy']:,.2f}")
    print(f"  Signals: {summary['signals_generated']} generated, "
          f"{summary['signals_filtered']} filtered")

    return summary, result


def save_results(all_results, instrument):
    """Save all results to a single JSON file."""
    results_dir = project_root / "data" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = {
        "test_type": "expert-mode-comparison",
        "instrument": instrument,
        "timestamp": ts,
        "runs": {}
    }
    for label, (summary, _result) in all_results.items():
        output["runs"][label] = summary

    path = results_dir / f"expert_mode_{instrument}_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nResults saved: {path}")
    return path


def print_comparison_table(results):
    """Print side-by-side comparison of all runs."""
    print(f"\n{'='*120}")
    print("EXPERT MODE COMPARISON — Core 5 Strategies")
    print(f"{'='*120}")

    header = (f"{'Run':50s} {'Trades':>7s} {'WR%':>7s} {'PF':>7s} "
              f"{'Net PnL':>12s} {'Expect':>9s} {'Sig Gen':>8s} {'Sig Filt':>9s} {'$/Trade':>9s}")
    print(header)
    print("-" * 120)

    for label, (s, _) in results.items():
        trades = s["trades"]
        per_trade = s["net_pnl"] / trades if trades > 0 else 0
        print(f"{label:50s} {trades:7d} {s['win_rate']:6.1f}% {s['profit_factor']:7.2f} "
              f"${s['net_pnl']:>10,.2f} ${s['expectancy']:>7,.2f} "
              f"{s.get('signals_generated', 0):8d} {s.get('signals_filtered', 0):9d} ${per_trade:>8,.2f}")

    # Strategy breakdown
    print(f"\n{'='*120}")
    print("STRATEGY BREAKDOWN")
    print(f"{'='*120}")

    run_labels = list(results.keys())
    all_strat_names = set()
    for _, (s, _) in results.items():
        all_strat_names.update(s.get("by_strategy", {}).keys())
    all_strat_names = sorted(all_strat_names)

    for sname in all_strat_names:
        print(f"\n  {sname}:")
        print(f"    {'Run':46s} {'Trades':>7s} {'WR%':>7s} {'PF':>7s} {'PnL':>10s} "
              f"{'L Trades':>8s} {'L WR%':>7s} {'S Trades':>8s} {'S WR%':>7s}")
        print(f"    {'-'*105}")
        for label, (s, _) in results.items():
            strat = s.get("by_strategy", {}).get(sname)
            if strat:
                print(f"    {label:46s} {strat['trades']:7d} {strat['win_rate']:6.1f}% "
                      f"{strat['profit_factor']:7.2f} ${strat['net_pnl']:>9,.2f} "
                      f"{strat.get('long_trades', 0):8d} {strat.get('long_wr', 0):6.1f}% "
                      f"{strat.get('short_trades', 0):8d} {strat.get('short_wr', 0):6.1f}%")
            else:
                print(f"    {label:46s} {'(no trades)':>7s}")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    # Reduce noise from non-essential loggers
    logging.getLogger("rockit_core.data").setLevel(logging.WARNING)
    logging.getLogger("rockit_core.engine").setLevel(logging.WARNING)
    logging.getLogger("rockit_core.strategies").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(description="Expert mode backtest comparison")
    parser.add_argument("--no-merge", action="store_true", help="Skip Google Drive merge")
    parser.add_argument("--instrument", default="NQ")
    parser.add_argument("--skip-llm", action="store_true", help="Skip LLM debate run (faster)")
    parser.add_argument("--max-sessions", type=int, default=0,
                        help="Limit to first N sessions (0 = all)")
    args = parser.parse_args()

    instrument = args.instrument.upper()

    print(f"{'='*70}")
    print(f"EXPERT MODE BACKTEST — {instrument}")
    print(f"Core 5: {', '.join(sorted(CORE_5))}")
    print(f"{'='*70}\n")

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

    # Limit sessions if requested
    if args.max_sessions > 0:
        sessions = sorted(df['session_date'].unique())
        if len(sessions) > args.max_sessions:
            keep = sessions[:args.max_sessions]
            df = df[df['session_date'].isin(keep)]
            print(f"Limited to first {args.max_sessions} sessions (of {len(sessions)})")

    # Load session bias from DuckDB (read-only)
    session_bias_lookup = {}
    try:
        from rockit_core.research.db import connect as db_connect, query as db_query
        conn = db_connect()
        rows = db_query(conn, "SELECT session_date, bias FROM session_context WHERE bias IS NOT NULL")
        session_bias_lookup = {str(r[0]).split(" ")[0]: r[1] for r in rows}
        conn.close()
        print(f"Loaded session bias for {len(session_bias_lookup)} sessions")
    except Exception as e:
        print(f"Warning: Could not load session bias: {e}")

    strategies = load_core_strategies()

    # Set up LLM client (shared)
    llm_client = None
    if not args.skip_llm:
        llm_client = OllamaClient(
            base_url="http://spark-ai:11434/v1",
            model="qwen3.5:35b-a3b",
            timeout=180,
        )
        if not llm_client.is_available():
            print("WARNING: LLM endpoint not reachable — debate runs will be skipped")
            llm_client = None

    # ─── Build run configs ───
    mechanical = get_mechanical_filters()

    # Run A: Baseline — no filters
    # Run B: Mechanical + Legacy Agent (matches previous Run E)
    agent_legacy = get_agent_filter_legacy()
    # Run C: Mechanical + Expert Agent (NEW — this is what we're testing)
    agent_expert = get_agent_filter_expert()

    configs = {
        "A: No filters (baseline)": None,
        "B: Mech + Legacy Agent (9 cards)": CompositeFilter(get_mechanical_filters() + [agent_legacy]),
        "C: Mech + Expert Agent (25+ cards)": CompositeFilter(get_mechanical_filters() + [agent_expert]),
    }

    # Run D: Mechanical + Expert Agent + LLM Debate (optional)
    agent_expert_llm = None
    if llm_client:
        agent_expert_llm = get_agent_filter_expert(enable_debate=True, llm_client=llm_client)
        configs["D: Mech + Expert + LLM Debate"] = CompositeFilter(
            get_mechanical_filters() + [agent_expert_llm]
        )

    # ─── Run all configs ───
    results = {}
    for label, filters in configs.items():
        summary, result = run_one(
            label, df, instrument, filters, session_bias_lookup, strategies
        )
        results[label] = (summary, result)

        # Analyze agent decisions
        if "Legacy" in label:
            analyze_agent_decisions(agent_legacy, "Legacy Agent")
        elif "Expert + LLM" in label:
            analyze_agent_decisions(agent_expert_llm, "Expert + LLM")
        elif "Expert" in label:
            analyze_agent_decisions(agent_expert, "Expert Agent")

        gc.collect()

    # ─── Print comparison ───
    print_comparison_table(results)

    # ─── Save results ───
    save_results(results, instrument)

    print(f"\n{'='*70}")
    print("DONE — Expert Mode Backtest Complete")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
