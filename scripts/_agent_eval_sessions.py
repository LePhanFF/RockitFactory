"""Agent evaluation for session review: 2026-03-11 and 2026-03-12."""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "rockit-core" / "src"))

import pandas as pd
from rockit_core.data.manager import SessionDataManager
from rockit_core.data.features import compute_all_features
from rockit_core.config.instruments import get_instrument
from rockit_core.strategies.loader import load_strategies_from_config
from rockit_core.engine.backtest import BacktestEngine
from rockit_core.agents.pipeline import AgentPipeline
from rockit_core.agents.gate import CRIGateAgent
from rockit_core.agents.observers import ProfileObserver, MomentumObserver
from rockit_core.agents.orchestrator import DeterministicOrchestrator

mgr = SessionDataManager()
df = compute_all_features(mgr.load("NQ"))
inst = get_instrument("NQ")
strategies = load_strategies_from_config("configs/strategies.yaml")

def load_tape(date):
    tape = []
    try:
        with open(f"data/json_snapshots/deterministic_{date}.jsonl", "r") as f:
            for line in f:
                tape.append(json.loads(line))
    except Exception:
        pass
    return tape

session_bias = {}
try:
    from rockit_core.research.db import connect, query
    conn = connect()
    rows = query(conn, "SELECT session_date, bias FROM session_context WHERE bias IS NOT NULL")
    session_bias = {str(r[0]).split(" ")[0]: r[1] for r in rows}
    conn.close()
except Exception as e:
    print(f"Bias load error: {e}")

pipeline = AgentPipeline(
    gate=CRIGateAgent(),
    observers=[ProfileObserver(), MomentumObserver()],
    orchestrator=DeterministicOrchestrator(),
)

for date in ["2026-03-11", "2026-03-12"]:
    print(f"\n{'='*70}")
    print(f"  AGENT EVALUATION: {date}")
    print(f"{'='*70}")

    session_df = df[df["session_date"].astype(str).str.startswith(date)]
    if len(session_df) == 0:
        print("  No data")
        continue

    engine = BacktestEngine(instrument=inst, strategies=strategies)
    result = engine.run(session_df, verbose=False)
    tape = load_tape(date)

    for t in result.trades:
        signal_dict = {
            "strategy_name": t.strategy_name,
            "direction": t.direction,
            "entry_price": t.entry_price,
            "stop_price": t.stop_price,
            "target_price": t.target_price,
            "day_type": getattr(t, "day_type", "unknown"),
        }

        bar_dict = {}
        if tape:
            for snap in tape:
                bar_dict = {
                    "close": snap.get("intraday", {}).get("last_price", t.entry_price),
                    "vwap": snap.get("intraday", {}).get("vwap", 0),
                }
                et = snap.get("current_et_time", "")
                if et >= "10:30":
                    break

        session_context = {
            "session_date": date,
            "bias": session_bias.get(date, "unknown"),
            "day_type": getattr(t, "day_type", "unknown"),
        }
        if tape:
            last_snap = tape[-1]
            inf = last_snap.get("inference", {})
            session_context.update({
                "cri_status": inf.get("cri", {}).get("status", "UNKNOWN"),
                "ib_range": last_snap.get("intraday", {}).get("ib_range_pts", 0),
                "tpo_shape": inf.get("tpo_shape", "unknown"),
            })

        try:
            decision = pipeline.evaluate_signal(signal_dict, bar_dict, session_context)
            outcome = "WIN" if t.net_pnl > 0 else "LOSS"
            gate_str = "PASS" if decision.gate_passed else "FAIL"
            conf = decision.confluence
            print(f"\n  Signal: {t.strategy_name} {t.direction} | PnL ${t.net_pnl:+,.0f} | {outcome}")
            print(f"    Gate: {gate_str}")
            print(f"    Decision: {decision.decision} | Conviction: {conf.conviction:.2f} | Dir: {conf.direction}")
            print(f"    Bull={conf.bull_score:.1f} ({conf.bull_cards} cards) vs Bear={conf.bear_score:.1f} ({conf.bear_cards} cards)")
            if decision.evidence_cards:
                for card in decision.evidence_cards:
                    if hasattr(card, "category"):
                        print(f"    Card: {card.category} | {card.direction} | str={card.strength:.1f} | {card.summary}")
                    elif isinstance(card, dict):
                        cat = card.get("category", "?")
                        d = card.get("direction", "?")
                        s = card.get("strength", 0)
                        sm = card.get("summary", "")
                        print(f"    Card: {cat} | {d} | str={s:.1f} | {sm}")
            if decision.reasoning:
                print(f"    Reasoning: {decision.reasoning}")
        except Exception as e:
            print(f"\n  Signal: {t.strategy_name} {t.direction} | ERROR: {e}")
