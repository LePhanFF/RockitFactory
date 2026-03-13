#!/usr/bin/env python3
"""
Quick 5-session sample test for LLM debate JSON repair validation.

Runs only Run E (debate) on 5 sessions to verify JSON parsing works
before committing to the full 270-session backtest.
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.agents.llm_client import OllamaClient
from rockit_core.agents.orchestrator import DeterministicOrchestrator
from rockit_core.agents.pipeline import AgentPipeline
from rockit_core.agents.agent_filter import AgentFilter
from rockit_core.config.instruments import get_instrument
from rockit_core.data.features import compute_all_features
from rockit_core.data.manager import SessionDataManager
from rockit_core.engine.backtest import BacktestEngine
from rockit_core.filters import (
    AntiChaseFilter, BiasAlignmentFilter, CompositeFilter, DayTypeGateFilter,
)
from rockit_core.strategies.loader import load_strategies_from_config
from rockit_core.research.db import connect as db_connect, query as db_query


def main():
    instrument = "NQ"
    mgr = SessionDataManager(data_dir="data/sessions")
    df = mgr.load(instrument)
    df = compute_all_features(df)

    # Only keep first 5 sessions
    session_dates = sorted(df["session_date"].unique())
    sample_dates = session_dates[:5]
    df_sample = df[df["session_date"].isin(sample_dates)].copy()
    print(f"Sample: {len(sample_dates)} sessions ({sample_dates[0]} to {sample_dates[-1]})")

    # Session bias
    session_bias_lookup = {}
    try:
        conn = db_connect()
        rows = db_query(conn, "SELECT session_date, bias FROM session_context WHERE bias IS NOT NULL")
        session_bias_lookup = {str(r[0]).split(" ")[0]: r[1] for r in rows}
        conn.close()
    except Exception as e:
        print(f"Warning: session bias load failed: {e}")

    # Build debate pipeline
    llm_client = OllamaClient(
        base_url="http://spark-ai:11434/v1",
        model="qwen3.5:35b-a3b",
        timeout=180,
    )
    if not llm_client.is_available():
        print("ERROR: LLM endpoint not reachable. Cannot test debate.")
        sys.exit(1)

    orchestrator = DeterministicOrchestrator(take_threshold=0.3, skip_threshold=0.1)
    pipeline = AgentPipeline(
        orchestrator=orchestrator,
        llm_client=llm_client,
        enable_debate=True,
    )
    agent_filter = AgentFilter(pipeline=pipeline)

    # Mechanical + Agent + Debate
    bias_rules = [
        {"strategy": "80P Rule", "blocked_day_types": ["neutral", "neutral_range", "Neutral Range"]},
        {"strategy": "B-Day", "blocked_day_types": ["trend_up", "trend_down", "Trend Up", "Trend Down"]},
    ]
    anti_chase_rules = [
        {"strategy": "80P Rule",
         "block_long_when_bias": ["Bullish", "BULL", "Very Bullish"],
         "block_short_when_bias": ["Bearish", "BEAR", "Very Bearish"]},
    ]
    filters = CompositeFilter([
        BiasAlignmentFilter(neutral_passes=True),
        DayTypeGateFilter(rules=bias_rules),
        AntiChaseFilter(rules=anti_chase_rules),
        agent_filter,
    ])

    strats = load_strategies_from_config(project_root / "configs" / "strategies.yaml")
    inst_spec = get_instrument(instrument)
    engine = BacktestEngine(
        instrument=inst_spec,
        strategies=strats,
        filters=filters,
        session_bias_lookup=session_bias_lookup,
    )

    print(f"\nRunning 5-session debate test...")
    result = engine.run(df_sample, verbose=True)

    trades = result.trades
    n_trades = len(trades)
    wins = [t for t in trades if t.net_pnl > 0]
    total_pnl = sum(t.net_pnl for t in trades)

    print(f"\n{'='*60}")
    print(f"  SAMPLE TEST RESULTS (5 sessions)")
    print(f"{'='*60}")
    print(f"  Trades: {n_trades}")
    print(f"  Wins: {len(wins)}")
    print(f"  Win Rate: {len(wins)/n_trades*100:.1f}%" if n_trades else "  No trades")
    print(f"  Net PnL: ${total_pnl:,.2f}")
    print(f"  Signals generated: {result.signals_generated}")
    print(f"  Signals filtered: {result.signals_filtered}")

    # Check agent decisions
    n_decisions = len(agent_filter.decisions) if hasattr(agent_filter, 'decisions') else 0
    print(f"  Agent decisions: {n_decisions}")

    for d in (agent_filter.decisions or []):
        dd = d.to_dict()
        reasoning = dd.get("reasoning", "")
        has_debate = "Debate:" in reasoning
        print(f"    - {dd.get('decision', '?')} | debate={'yes' if has_debate else 'no'} | "
              f"conf={dd.get('confidence', '?')} | evidence={len(d.evidence_cards)}")
        print(f"      reasoning: {reasoning[:120]}")

    print(f"\n{'='*60}")
    if n_decisions > 0:
        print("  SUCCESS: Debate pipeline is working!")
    else:
        print("  WARNING: No agent decisions — check if signals were generated")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
