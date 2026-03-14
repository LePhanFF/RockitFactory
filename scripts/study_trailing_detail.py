#!/usr/bin/env python3
"""
Trailing Stop Study — Per-Strategy Deep Dive

Runs the most promising trailing configs and breaks down:
  - Per-strategy: WR, PF, PnL, trail activation rate
  - Winner analysis: did trailing HELP or HURT big winners?
  - Loser analysis: did trailing SAVE losers (turn stops into small wins)?

Usage:
    python scripts/study_trailing_detail.py --no-merge
"""

import argparse
import gc
import sys
from pathlib import Path

import numpy as np
import pandas as pd

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.config.instruments import get_instrument
from rockit_core.data.features import compute_all_features
from rockit_core.data.manager import SessionDataManager
from rockit_core.engine.backtest import BacktestEngine
from rockit_core.strategies.loader import load_strategies_from_config

CORE_5 = {"Opening Range Rev", "OR Acceptance", "80P Rule", "20P IB Extension", "B-Day"}

TICK_SIZE = 0.25
POINT_VALUE = 20.0
SLIPPAGE_TICKS = 1
COMMISSION_PER_SIDE = 2.05

ATR_PERIODS = [5, 15, 30, 60]

# Configs to test — focus on "let it breathe" range
# (activate_mult, trail_mult) — activate after decent move, trail not too tight
CONFIGS = [
    # label, atr_period, activate_mult, trail_mult
    ("ATR(5) act=1.0x trail=0.5x", 5, 1.0, 0.5),
    ("ATR(5) act=1.5x trail=0.75x", 5, 1.5, 0.75),
    ("ATR(5) act=2.0x trail=1.0x", 5, 2.0, 1.0),
    ("ATR(15) act=1.0x trail=0.5x", 15, 1.0, 0.5),
    ("ATR(15) act=1.0x trail=0.75x", 15, 1.0, 0.75),
    ("ATR(15) act=1.5x trail=0.5x", 15, 1.5, 0.5),
    ("ATR(15) act=1.5x trail=0.75x", 15, 1.5, 0.75),
    ("ATR(15) act=1.5x trail=1.0x", 15, 1.5, 1.0),
    ("ATR(15) act=2.0x trail=0.75x", 15, 2.0, 0.75),
    ("ATR(15) act=2.0x trail=1.0x", 15, 2.0, 1.0),
    ("ATR(30) act=1.0x trail=0.75x", 30, 1.0, 0.75),
    ("ATR(30) act=1.5x trail=0.75x", 30, 1.5, 0.75),
    ("ATR(30) act=1.5x trail=1.0x", 30, 1.5, 1.0),
    ("ATR(30) act=2.0x trail=1.0x", 30, 2.0, 1.0),
    ("ATR(60) act=1.5x trail=0.75x", 60, 1.5, 0.75),
    ("ATR(60) act=2.0x trail=1.0x", 60, 2.0, 1.0),
]


def compute_multi_atr(df):
    df = df.copy()
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    for period in ATR_PERIODS:
        df[f'atr_{period}'] = true_range.rolling(window=period, min_periods=1).mean()
    return df


def find_entry_bar(session_bars, trade):
    entry_time = trade.entry_time
    if entry_time is not None:
        for idx in range(len(session_bars)):
            bar_ts = session_bars.iloc[idx].get('timestamp', session_bars.iloc[idx].name if hasattr(session_bars.iloc[idx], 'name') else None)
            if bar_ts is not None and str(bar_ts) == str(entry_time):
                return idx
    bars_held = trade.bars_held
    if bars_held > 0:
        entry_idx = len(session_bars) - 1 - bars_held
        if 0 <= entry_idx < len(session_bars):
            return entry_idx
    return None


def simulate_with_trail(bars_after, direction, entry, stop, target,
                        act_dist, trail_dist, slippage):
    hwm = 0.0
    trail_active = False
    current_stop = stop
    mfe = 0.0
    mae = 0.0

    for i, bar in enumerate(bars_after):
        bh, bl = bar['high'], bar['low']

        if direction == 'LONG':
            exc = bh - entry
            if exc > hwm:
                hwm = exc
            if not trail_active and hwm >= act_dist:
                trail_active = True
                current_stop = max(stop, entry + hwm - trail_dist)
            elif trail_active:
                current_stop = max(current_stop, entry + hwm - trail_dist)
            if bl <= current_stop:
                ep = current_stop - slippage
                r = 'TRAIL_STOP' if trail_active else 'STOP'
                return r, ep, i, max(mfe, exc), mae, trail_active, current_stop
            if bh >= target:
                ep = target - slippage
                return 'TARGET', ep, i, max(mfe, exc), mae, trail_active, current_stop
            mfe = max(mfe, exc)
            mae = max(mae, entry - bl)
        else:
            exc = entry - bl
            if exc > hwm:
                hwm = exc
            if not trail_active and hwm >= act_dist:
                trail_active = True
                current_stop = min(stop, entry - hwm + trail_dist)
            elif trail_active:
                current_stop = min(current_stop, entry - hwm + trail_dist)
            if bh >= current_stop:
                ep = current_stop + slippage
                r = 'TRAIL_STOP' if trail_active else 'STOP'
                return r, ep, i, max(mfe, exc), mae, trail_active, current_stop
            if bl <= target:
                ep = target + slippage
                return 'TARGET', ep, i, max(mfe, exc), mae, trail_active, current_stop
            mfe = max(mfe, exc)
            mae = max(mae, bh - entry)

    lc = bars_after[-1]['close'] if bars_after else entry
    ep = lc - slippage if direction == 'LONG' else lc + slippage
    return 'EOD', ep, len(bars_after) - 1, mfe, mae, trail_active, current_stop


def pnl(direction, entry, exit_price):
    if direction == 'LONG':
        g = (exit_price - entry) * POINT_VALUE
    else:
        g = (entry - exit_price) * POINT_VALUE
    return g - COMMISSION_PER_SIDE * 2


def metrics(pnl_list):
    if not pnl_list:
        return {'n': 0, 'wr': 0, 'pf': 0, 'net': 0, 'avg': 0, 'avg_win': 0, 'avg_loss': 0}
    n = len(pnl_list)
    wins = [p for p in pnl_list if p > 0]
    losses = [p for p in pnl_list if p <= 0]
    wr = len(wins) / n * 100
    gp = sum(wins) if wins else 0
    gl = abs(sum(losses)) if losses else 0
    pf = gp / gl if gl > 0 else float('inf')
    net = sum(pnl_list)
    avg_w = np.mean(wins) if wins else 0
    avg_l = np.mean(losses) if losses else 0
    return {'n': n, 'wr': wr, 'pf': pf, 'net': net, 'avg': net / n,
            'avg_win': avg_w, 'avg_loss': avg_l}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-merge", action="store_true")
    parser.add_argument("--instrument", default="NQ")
    args = parser.parse_args()
    instrument = args.instrument.upper()

    print(f"{'='*70}")
    print(f"TRAILING STOP DEEP DIVE — {instrument}")
    print(f"{'='*70}\n")

    mgr = SessionDataManager(data_dir="data/sessions")
    df = mgr.load(instrument) if args.no_merge else mgr.merge_delta(instrument)
    gc.collect()
    df = compute_all_features(df)
    gc.collect()
    df = compute_multi_atr(df)

    # Run baseline
    all_strats = load_strategies_from_config(project_root / "configs" / "strategies.yaml")
    strategies = [s for s in all_strats if s.name in CORE_5]
    print(f"Strategies: {[s.name for s in strategies]}")

    session_bias_lookup = {}
    try:
        from rockit_core.research.db import connect as db_connect, query as db_query
        conn = db_connect()
        rows = db_query(conn, "SELECT session_date, bias FROM session_context WHERE bias IS NOT NULL")
        session_bias_lookup = {str(r[0]).split(" ")[0]: r[1] for r in rows}
        conn.close()
    except Exception:
        pass

    inst_spec = get_instrument(instrument)
    engine = BacktestEngine(instrument=inst_spec, strategies=strategies,
                            session_bias_lookup=session_bias_lookup)
    result = engine.run(df, verbose=False)
    trades = result.trades
    print(f"Baseline: {len(trades)} trades\n")

    # Index sessions
    sessions = {}
    for sd, group in df.groupby('session_date'):
        sessions[str(sd).split(' ')[0].split('T')[0]] = group

    # Match trades to bars
    slippage = SLIPPAGE_TICKS * TICK_SIZE
    matched = []
    for t in trades:
        sk = str(t.session_date).split(' ')[0].split('T')[0]
        if sk not in sessions:
            continue
        sb = sessions[sk]
        idx = find_entry_bar(sb, t)
        if idx is None or idx < 1:
            continue
        remaining = sb.iloc[idx + 1:].to_dict('records')
        if len(remaining) < 3:
            continue
        entry_bar = sb.iloc[idx]
        atr_vals = {}
        for p in ATR_PERIODS:
            v = entry_bar.get(f'atr_{p}')
            if v is not None and not np.isnan(v) and v > 0:
                atr_vals[p] = v
        ib_h = sb.iloc[:61]['high'].max() if len(sb) > 60 else None
        ib_l = sb.iloc[:61]['low'].min() if len(sb) > 60 else None
        ib_range = (ib_h - ib_l) if ib_h and ib_l else None
        matched.append({'trade': t, 'remaining': remaining, 'atr': atr_vals, 'ib': ib_range})

    print(f"Matched: {len(matched)} / {len(trades)} trades\n")

    # Simulate baseline (no trail)
    baseline_data = []
    for m in matched:
        t = m['trade']
        sim = simulate_with_trail(m['remaining'], t.direction, t.entry_price,
                                  t.stop_price, t.target_price, 999999, 0, slippage)
        p = pnl(t.direction, t.entry_price, sim[1])
        baseline_data.append({
            'strategy': t.strategy_name, 'direction': t.direction,
            'pnl': p, 'outcome': sim[0], 'mfe': sim[3], 'mae': sim[4],
            'risk': t.risk_points, 'entry': t.entry_price,
            'original_target': t.target_price, 'original_stop': t.stop_price,
        })

    # For each config, simulate and collect per-trade results
    for label, atr_period, act_mult, trail_mult in CONFIGS:
        trail_data = []
        for i, m in enumerate(matched):
            t = m['trade']
            atr = m['atr'].get(atr_period)
            if atr is None:
                # No trail possible — use baseline
                trail_data.append({**baseline_data[i], 'trail_activated': False,
                                   'trail_stop_price': t.stop_price,
                                   'act_dist': 0, 'trail_dist': 0})
                continue

            act_dist = atr * act_mult
            t_dist = atr * trail_mult

            sim = simulate_with_trail(m['remaining'], t.direction, t.entry_price,
                                      t.stop_price, t.target_price, act_dist, t_dist, slippage)
            p = pnl(t.direction, t.entry_price, sim[1])
            trail_data.append({
                'strategy': t.strategy_name, 'direction': t.direction,
                'pnl': p, 'outcome': sim[0], 'mfe': sim[3], 'mae': sim[4],
                'risk': t.risk_points, 'trail_activated': sim[5],
                'trail_stop_price': sim[6], 'act_dist': act_dist, 'trail_dist': t_dist,
                'entry': t.entry_price, 'exit': sim[1],
                'baseline_pnl': baseline_data[i]['pnl'],
                'baseline_outcome': baseline_data[i]['outcome'],
            })

        # --- Print per-strategy breakdown ---
        print(f"\n{'='*140}")
        print(f"  {label}")
        avg_act = np.mean([d['act_dist'] for d in trail_data if d['act_dist'] > 0])
        avg_trail = np.mean([d['trail_dist'] for d in trail_data if d['trail_dist'] > 0])
        print(f"  Avg activation distance: {avg_act:.1f}pts, Avg trail distance: {avg_trail:.1f}pts")
        print(f"{'='*140}")

        strat_names = sorted(set(d['strategy'] for d in trail_data))

        print(f"\n  {'Strategy':25s} | {'':^55s} | {'':^55s} |")
        print(f"  {'':25s} | {'TRAILING':^55s} | {'BASELINE':^55s} | {'DELTA':^20s}")
        print(f"  {'':25s} | {'Trades':>6s} {'WR%':>6s} {'PF':>6s} {'Net':>10s} {'AvgW':>8s} {'AvgL':>8s} {'Trails':>8s} | "
              f"{'Trades':>6s} {'WR%':>6s} {'PF':>6s} {'Net':>10s} {'AvgW':>8s} {'AvgL':>8s} | {'PF':>6s} {'PnL':>10s}")
        print(f"  {'-'*25}-┼-{'-'*55}-┼-{'-'*55}-┼-{'-'*20}")

        total_trail_pnls = []
        total_base_pnls = []

        for sname in strat_names:
            s_trail = [d for d in trail_data if d['strategy'] == sname]
            s_base = [d for d in baseline_data if d['strategy'] == sname]

            t_pnls = [d['pnl'] for d in s_trail]
            b_pnls = [d['pnl'] for d in s_base]
            total_trail_pnls.extend(t_pnls)
            total_base_pnls.extend(b_pnls)

            tm = metrics(t_pnls)
            bm = metrics(b_pnls)
            trails_n = sum(1 for d in s_trail if d.get('trail_activated'))

            dpf = tm['pf'] - bm['pf']
            dpnl = tm['net'] - bm['net']

            print(f"  {sname:25s} | {tm['n']:6d} {tm['wr']:5.1f}% {tm['pf']:6.2f} ${tm['net']:>8,.0f} "
                  f"${tm['avg_win']:>6,.0f} ${tm['avg_loss']:>6,.0f} {trails_n:5d}({trails_n/max(tm['n'],1)*100:2.0f}%) | "
                  f"{bm['n']:6d} {bm['wr']:5.1f}% {bm['pf']:6.2f} ${bm['net']:>8,.0f} "
                  f"${bm['avg_win']:>6,.0f} ${bm['avg_loss']:>6,.0f} | {dpf:+5.2f} ${dpnl:>+9,.0f}")

        # Totals
        tm_all = metrics(total_trail_pnls)
        bm_all = metrics(total_base_pnls)
        trails_total = sum(1 for d in trail_data if d.get('trail_activated'))
        print(f"  {'-'*25}-┼-{'-'*55}-┼-{'-'*55}-┼-{'-'*20}")
        print(f"  {'TOTAL':25s} | {tm_all['n']:6d} {tm_all['wr']:5.1f}% {tm_all['pf']:6.2f} ${tm_all['net']:>8,.0f} "
              f"${tm_all['avg_win']:>6,.0f} ${tm_all['avg_loss']:>6,.0f} {trails_total:5d}({trails_total/max(tm_all['n'],1)*100:2.0f}%) | "
              f"{bm_all['n']:6d} {bm_all['wr']:5.1f}% {bm_all['pf']:6.2f} ${bm_all['net']:>8,.0f} "
              f"${bm_all['avg_win']:>6,.0f} ${bm_all['avg_loss']:>6,.0f} | {tm_all['pf']-bm_all['pf']:+5.2f} ${tm_all['net']-bm_all['net']:>+9,.0f}")

        # --- Winner impact analysis ---
        print(f"\n  Winner Impact (trades that were winners in BASELINE):")
        base_winners = [i for i, d in enumerate(baseline_data) if d['pnl'] > 0]
        if base_winners:
            helped = 0  # trailing PnL > baseline PnL
            hurt = 0    # trailing PnL < baseline PnL (cut winner short)
            saved_pnl = 0
            lost_pnl = 0
            for idx in base_winners:
                bp = baseline_data[idx]['pnl']
                tp = trail_data[idx]['pnl']
                if tp >= bp:
                    helped += 1
                    saved_pnl += (tp - bp)
                else:
                    hurt += 1
                    lost_pnl += (bp - tp)
            print(f"    {len(base_winners)} baseline winners → {helped} helped (gained ${saved_pnl:,.0f}), "
                  f"{hurt} hurt (lost ${lost_pnl:,.0f})")

        # --- Loser save analysis ---
        print(f"\n  Loser Save (trades that were losers in BASELINE):")
        base_losers = [i for i, d in enumerate(baseline_data) if d['pnl'] <= 0]
        if base_losers:
            saved = 0   # trail turned loss into win or smaller loss
            worse = 0   # trail made loss bigger
            saved_amt = 0
            worse_amt = 0
            for idx in base_losers:
                bp = baseline_data[idx]['pnl']
                tp = trail_data[idx]['pnl']
                if tp > bp:
                    saved += 1
                    saved_amt += (tp - bp)
                elif tp < bp:
                    worse += 1
                    worse_amt += (bp - tp)
            flipped = sum(1 for idx in base_losers if trail_data[idx]['pnl'] > 0)
            print(f"    {len(base_losers)} baseline losers → {saved} improved (saved ${saved_amt:,.0f}), "
                  f"{worse} worsened (lost ${worse_amt:,.0f}), {flipped} flipped to winners")

        # --- Exit reason breakdown ---
        print(f"\n  Exit Reasons:")
        reasons = {}
        for d in trail_data:
            r = d['outcome']
            reasons[r] = reasons.get(r, 0) + 1
        base_reasons = {}
        for d in baseline_data:
            r = d['outcome']
            base_reasons[r] = base_reasons.get(r, 0) + 1
        print(f"    Trail: {reasons}")
        print(f"    Base:  {base_reasons}")


if __name__ == "__main__":
    main()
