#!/usr/bin/env python3
"""
Trailing Stop Study — All 12 Active Strategies

For each strategy, test multiple ATR(15)-based trailing configs:
  1. Run baseline backtest (no trailing)
  2. Walk forward each trade with trailing stop simulation
  3. Compare PF/WR/PnL per config
  4. Report best config per strategy + recommendation (ENABLE/DISABLE)

Principle: Don't trail too soon — some trades need room to breathe.

Usage:
    .venv/Scripts/python.exe scripts/study_trailing_all12.py
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.config.instruments import get_instrument
from rockit_core.data.features import compute_all_features
from rockit_core.data.manager import SessionDataManager
from rockit_core.engine.backtest import BacktestEngine
from rockit_core.strategies.loader import load_strategies_from_config

TICK_SIZE = 0.25
POINT_VALUE = 20.0
SLIPPAGE_TICKS = 1
COMMISSION_PER_SIDE = 2.05


def compute_atr15(df):
    df = df.copy()
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr_15'] = true_range.rolling(window=15, min_periods=1).mean()
    return df


def find_entry_bar(session_bars, trade):
    entry_time = trade.entry_time
    if entry_time is None:
        return None
    for idx in range(len(session_bars)):
        bar = session_bars.iloc[idx]
        bar_ts = bar.get('timestamp', bar.name if hasattr(bar, 'name') else None)
        if bar_ts is not None and str(bar_ts) == str(entry_time):
            return idx
    bars_held = trade.bars_held
    if bars_held > 0:
        entry_idx = len(session_bars) - 1 - bars_held
        if 0 <= entry_idx < len(session_bars):
            return entry_idx
    return None


def simulate_trail(bars_after_entry, direction, entry_price, stop_price,
                   target_price, activate_dist, trail_dist, slippage_pts):
    hwm = 0.0
    trail_active = False
    current_stop = stop_price

    for bar in bars_after_entry:
        bh, bl = bar['high'], bar['low']

        if direction == 'LONG':
            exc = bh - entry_price
            if exc > hwm:
                hwm = exc
            if not trail_active and hwm >= activate_dist:
                trail_active = True
                current_stop = max(stop_price, entry_price + hwm - trail_dist)
            elif trail_active:
                current_stop = max(current_stop, entry_price + hwm - trail_dist)
            if bl <= current_stop:
                return ('TRAIL_STOP' if trail_active else 'STOP',
                        current_stop - slippage_pts, trail_active)
            if bh >= target_price:
                return 'TARGET', target_price - slippage_pts, trail_active
        else:
            exc = entry_price - bl
            if exc > hwm:
                hwm = exc
            if not trail_active and hwm >= activate_dist:
                trail_active = True
                current_stop = min(stop_price, entry_price - hwm + trail_dist)
            elif trail_active:
                current_stop = min(current_stop, entry_price - hwm + trail_dist)
            if bh >= current_stop:
                return ('TRAIL_STOP' if trail_active else 'STOP',
                        current_stop + slippage_pts, trail_active)
            if bl <= target_price:
                return 'TARGET', target_price + slippage_pts, trail_active

    last_close = bars_after_entry[-1]['close'] if bars_after_entry else entry_price
    ep = last_close - slippage_pts if direction == 'LONG' else last_close + slippage_pts
    return 'EOD', ep, trail_active


def compute_pnl(direction, entry_price, exit_price):
    if direction == 'LONG':
        gross = (exit_price - entry_price) * POINT_VALUE
    else:
        gross = (entry_price - exit_price) * POINT_VALUE
    return gross - (COMMISSION_PER_SIDE * 2)


def metrics(results):
    if not results:
        return 0, 0, 0, 0
    wins = [r for r in results if r > 0]
    losses = [r for r in results if r <= 0]
    wr = len(wins) / len(results) * 100
    gp = sum(wins)
    gl = abs(sum(losses))
    pf = gp / gl if gl > 0 else 99.99
    total = sum(results)
    return len(results), wr, pf, total


CONFIGS = [
    ('act=1.0x trail=0.5x', 1.0, 0.5),
    ('act=1.5x trail=0.5x', 1.5, 0.5),
    ('act=1.5x trail=0.75x', 1.5, 0.75),
    ('act=1.5x trail=1.0x', 1.5, 1.0),
    ('act=2.0x trail=0.75x', 2.0, 0.75),
    ('act=2.0x trail=1.0x', 2.0, 1.0),
    ('act=2.5x trail=1.0x', 2.5, 1.0),
    ('act=3.0x trail=1.0x', 3.0, 1.0),
]


def main():
    print("Loading data...")
    mgr = SessionDataManager()
    df = compute_all_features(mgr.load('NQ'))
    df = compute_atr15(df)
    inst = get_instrument('NQ')

    from rockit_core.research.db import connect as db_connect, query as db_query
    conn = db_connect()
    rows = db_query(conn, "SELECT session_date, bias FROM session_context WHERE bias IS NOT NULL")
    bias = {str(r[0]).split(" ")[0].split("T")[0]: r[1] for r in rows}
    conn.close()

    print("Running baseline backtest...")
    strategies = load_strategies_from_config("configs/strategies.yaml")
    engine = BacktestEngine(instrument=inst, strategies=strategies, session_bias_lookup=bias)
    result = engine.run(df, verbose=False)
    trades = result.trades
    print(f"Baseline: {len(trades)} trades")

    # Index sessions
    sessions = {}
    for sd, group in df.groupby('session_date'):
        key = str(sd).split(' ')[0].split('T')[0]
        sessions[key] = group

    # Match trades to bars
    slippage_pts = SLIPPAGE_TICKS * TICK_SIZE
    matched = []
    for trade in trades:
        sk = str(trade.session_date).split(' ')[0].split('T')[0]
        if sk not in sessions:
            continue
        sb = sessions[sk]
        eidx = find_entry_bar(sb, trade)
        if eidx is None or eidx < 1:
            continue
        remaining = sb.iloc[eidx + 1:].to_dict('records')
        if len(remaining) < 3:
            continue
        entry_bar = sb.iloc[eidx]
        atr15 = entry_bar.get('atr_15')
        if atr15 is None or np.isnan(atr15) or atr15 <= 0:
            continue
        matched.append({
            'trade': trade, 'remaining': remaining, 'atr15': float(atr15),
        })
    print(f"Matched {len(matched)} / {len(trades)} trades ({len(matched)/len(trades)*100:.0f}%)\n")

    strat_names = sorted(set(t['trade'].strategy_name for t in matched))

    # Header
    print(f"{'Strategy':<22s} | {'Config':<25s} | {'Trades':>6s} {'WR':>7s} {'PF':>7s} {'PnL':>10s} {'vs Base':>10s} | {'Rec'}")
    print("=" * 105)

    recommendations = {}

    for strat in strat_names:
        strat_trades = [t for t in matched if t['trade'].strategy_name == strat]
        if len(strat_trades) < 5:
            print(f"{strat:<22s} | Too few trades ({len(strat_trades)})")
            continue

        # Baseline
        base_pnls = [t['trade'].net_pnl for t in strat_trades]
        bn, bwr, bpf, bpnl = metrics(base_pnls)
        print(f"{strat:<22s} | {'BASELINE':<25s} | {bn:>6d} {bwr:>6.1f}% {bpf:>6.2f} ${bpnl:>8,.0f}          |")

        best_cfg = None
        best_pf = bpf
        best_row = None

        for cfg_name, act_mult, trail_mult in CONFIGS:
            pnls = []
            activated_count = 0
            for mt in strat_trades:
                t = mt['trade']
                atr = mt['atr15']
                act_dist = atr * act_mult
                t_dist = atr * trail_mult
                reason, exit_price, activated = simulate_trail(
                    mt['remaining'], t.direction, t.entry_price,
                    t.stop_price, t.target_price, act_dist, t_dist, slippage_pts)
                pnl = compute_pnl(t.direction, t.entry_price, exit_price)
                pnls.append(pnl)
                if activated:
                    activated_count += 1

            n, wr, pf, total = metrics(pnls)
            delta = total - bpnl
            act_pct = activated_count / len(strat_trades) * 100

            marker = ""
            if pf > best_pf and delta > 0:
                best_pf = pf
                best_cfg = cfg_name
                best_row = (n, wr, pf, total, delta, act_pct)
                marker = " <<<"

            print(f"{'':22s} | {cfg_name:<25s} | {n:>6d} {wr:>6.1f}% {pf:>6.2f} ${total:>8,.0f} ${delta:>+8,.0f} |{marker}")

        # Recommendation
        if best_cfg:
            n, wr, pf, total, delta, act_pct = best_row
            rec = f"ENABLE: {best_cfg} (+${delta:,.0f}, {act_pct:.0f}% activate)"
            recommendations[strat] = {'config': best_cfg, 'delta': delta, 'pf': pf, 'enable': True}
        else:
            rec = "DISABLE trailing (baseline is best)"
            recommendations[strat] = {'enable': False}

        print(f"{'':22s} | >>> {rec}")
        print()

    # Summary
    print("\n" + "=" * 105)
    print("TRAILING STOP RECOMMENDATIONS")
    print("=" * 105)
    total_delta = 0
    for strat in strat_names:
        r = recommendations.get(strat)
        if not r:
            continue
        if r['enable']:
            total_delta += r['delta']
            print(f"  ENABLE  {strat:<22s} {r['config']:<25s} PF {r['pf']:.2f}  +${r['delta']:>8,.0f}")
        else:
            print(f"  DISABLE {strat:<22s} (baseline is best)")
    print(f"\n  Total trailing benefit: +${total_delta:,.0f}")


if __name__ == '__main__':
    main()
