"""Quick review of two sessions: 2026-03-11 and 2026-03-12."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "rockit-core" / "src"))

from rockit_core.data.manager import SessionDataManager
from rockit_core.data.features import compute_all_features
from rockit_core.config.instruments import get_instrument
from rockit_core.strategies.loader import load_strategies_from_config
from rockit_core.engine.backtest import BacktestEngine
from rockit_core.filters import BiasAlignmentFilter, DayTypeGateFilter, CompositeFilter

# Load session bias
session_bias = {}
try:
    from rockit_core.research.db import connect, query
    conn = connect()
    rows = query(conn, "SELECT session_date, bias FROM session_context WHERE bias IS NOT NULL")
    session_bias = {str(r[0]).split(" ")[0]: r[1] for r in rows}
    conn.close()
except Exception:
    pass

mgr = SessionDataManager(data_dir="data/sessions")
df = mgr.load("NQ")
df = compute_all_features(df)

inst = get_instrument("NQ")
project_root = Path(__file__).resolve().parent.parent
strats = load_strategies_from_config(project_root / "configs" / "strategies.yaml")

bias_rules = [
    {"strategy": "80P Rule", "blocked_day_types": ["neutral", "neutral_range", "Neutral Range"]},
    {"strategy": "B-Day", "blocked_day_types": ["trend_up", "trend_down", "Trend Up", "Trend Down"]},
]
mech_filters = CompositeFilter([BiasAlignmentFilter(neutral_passes=True), DayTypeGateFilter(rules=bias_rules)])

for date in ["2026-03-11", "2026-03-12"]:
    print(f"\n{'='*70}")
    print(f"  SESSION: {date} (NQ)")
    print(f"{'='*70}")
    session_df = df[df["session_date"].astype(str).str.startswith(date)]
    if len(session_df) == 0:
        print(f"  No data for {date}")
        continue
    print(f"  Rows: {len(session_df)}")
    print(f"  Bias: {session_bias.get(date, 'unknown')}")

    # Pass A: No filters
    engine_a = BacktestEngine(instrument=inst, strategies=strats)
    result_a = engine_a.run(session_df, verbose=False)
    print(f"\n  --- Pass A (No Filters) ---")
    print(f"  Signals: {result_a.signals_generated}, Trades: {len(result_a.trades)}")
    for t in result_a.trades:
        outcome = "WIN" if t.net_pnl > 0 else "LOSS"
        mae = f"MAE={abs(t.entry_price - t.mae_price):.1f}" if t.mae_price else "MAE=?"
        mfe = f"MFE={abs(t.mfe_price - t.entry_price):.1f}" if t.mfe_price else "MFE=?"
        print(f"    {t.strategy_name:20s} | {t.direction:5s} | Entry {t.entry_price:>10.2f} | "
              f"Stop {t.stop_price:>10.2f} | Target {t.target_price:>10.2f} | "
              f"PnL ${t.net_pnl:>+8.0f} | {outcome} | {t.exit_reason} | {mae} {mfe}")

    # Pass B: Mechanical filters
    engine_b = BacktestEngine(instrument=inst, strategies=strats, filters=mech_filters,
                              session_bias_lookup=session_bias)
    result_b = engine_b.run(session_df, verbose=False)
    print(f"\n  --- Pass B (Mechanical Filters) ---")
    print(f"  Signals: {result_b.signals_generated}, Filtered: {result_b.signals_filtered}, "
          f"Trades: {len(result_b.trades)}")
    for t in result_b.trades:
        outcome = "WIN" if t.net_pnl > 0 else "LOSS"
        mae = f"MAE={abs(t.entry_price - t.mae_price):.1f}" if t.mae_price else "MAE=?"
        mfe = f"MFE={abs(t.mfe_price - t.entry_price):.1f}" if t.mfe_price else "MFE=?"
        print(f"    {t.strategy_name:20s} | {t.direction:5s} | Entry {t.entry_price:>10.2f} | "
              f"Stop {t.stop_price:>10.2f} | Target {t.target_price:>10.2f} | "
              f"PnL ${t.net_pnl:>+8.0f} | {outcome} | {t.exit_reason} | {mae} {mfe}")

    # Filtered signals
    a_set = {(t.strategy_name, t.direction) for t in result_a.trades}
    b_set = {(t.strategy_name, t.direction) for t in result_b.trades}
    filtered = a_set - b_set
    if filtered:
        print(f"\n  --- Filtered Out ---")
        for strat, dirn in filtered:
            t = [x for x in result_a.trades if x.strategy_name == strat and x.direction == dirn][0]
            outcome = "WIN" if t.net_pnl > 0 else "LOSS"
            print(f"    {strat:20s} | {dirn:5s} | PnL ${t.net_pnl:>+8.0f} | {outcome} ← BLOCKED by filter")

    pnl_a = sum(t.net_pnl for t in result_a.trades)
    pnl_b = sum(t.net_pnl for t in result_b.trades)
    print(f"\n  Net PnL: Pass A = ${pnl_a:+,.2f}, Pass B = ${pnl_b:+,.2f}")
