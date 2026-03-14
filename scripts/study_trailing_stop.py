#!/usr/bin/env python3
"""
Quant Study: Trailing Stop After ATR-Based Activation

For each historical trade from the core 5 strategies:
  1. Keep the original target
  2. After the trade moves X * ATR(N) in your favor, activate a trailing stop
  3. Trail at Y * ATR(N) behind the high-water mark
  4. Compare PF/WR/PnL to baseline (no trail)

Trailing activation thresholds: 0.5x, 1.0x, 1.5x, 2.0x ATR
Trail distance: 0.5x, 0.75x, 1.0x, 1.5x ATR
Also test IB-range based: activate at 0.5x, 1.0x IB; trail at 0.25x, 0.5x IB

Usage:
    python scripts/study_trailing_stop.py --no-merge
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

# ATR periods to test
ATR_PERIODS = [5, 15, 30, 60]

# Trailing configs: (activation_atr_mult, trail_atr_mult)
TRAIL_CONFIGS_ATR = [
    # (activate after Nx ATR move, trail at Mx ATR behind HWM)
    (0.5, 0.5),
    (1.0, 0.5),
    (1.0, 0.75),
    (1.0, 1.0),
    (1.5, 0.5),
    (1.5, 0.75),
    (1.5, 1.0),
    (2.0, 0.75),
    (2.0, 1.0),
    (2.0, 1.5),
]

# IB-range trailing configs: (activate_ib_mult, trail_ib_mult)
TRAIL_CONFIGS_IB = [
    (0.25, 0.15),
    (0.5, 0.25),
    (0.5, 0.5),
    (0.75, 0.25),
    (0.75, 0.5),
    (1.0, 0.5),
    (1.0, 0.75),
]


def compute_multi_atr(df: pd.DataFrame) -> pd.DataFrame:
    """Compute ATR at multiple timeframes on 1-min bar data."""
    df = df.copy()
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    for period in ATR_PERIODS:
        df[f'atr_{period}'] = true_range.rolling(window=period, min_periods=1).mean()
    return df


def find_entry_bar(session_bars, trade):
    """Find entry bar index using entry_time timestamp matching."""
    entry_time = trade.entry_time
    if entry_time is None:
        return None

    # Try exact timestamp match
    for idx in range(len(session_bars)):
        bar = session_bars.iloc[idx]
        bar_ts = bar.get('timestamp', bar.name if hasattr(bar, 'name') else None)
        if bar_ts is not None and str(bar_ts) == str(entry_time):
            return idx

    # Fallback: use bars_held
    bars_held = trade.bars_held
    if bars_held > 0:
        # entry_bar = last_bar_idx - bars_held
        last_idx = len(session_bars) - 1
        entry_idx = last_idx - bars_held
        if 0 <= entry_idx < len(session_bars):
            return entry_idx

    return None


def simulate_trade_with_trail(bars_after_entry, direction, entry_price, stop_price,
                              target_price, activate_dist, trail_dist, slippage_pts):
    """Walk forward bar-by-bar with trailing stop logic.

    Args:
        activate_dist: Distance in points from entry before trail activates
        trail_dist: Distance in points behind high-water mark for trail
    """
    hwm = 0.0  # high water mark (favorable excursion)
    trail_active = False
    current_stop = stop_price
    mfe_pts = 0.0
    mae_pts = 0.0

    for i, bar in enumerate(bars_after_entry):
        bar_high = bar['high']
        bar_low = bar['low']

        if direction == 'LONG':
            # Update HWM
            excursion = bar_high - entry_price
            if excursion > hwm:
                hwm = excursion

            # Check trail activation
            if not trail_active and hwm >= activate_dist:
                trail_active = True
                # Set trail stop: HWM - trail_dist, but never below original stop
                trail_stop = entry_price + hwm - trail_dist
                current_stop = max(stop_price, trail_stop)
            elif trail_active:
                # Update trail stop as HWM advances
                trail_stop = entry_price + hwm - trail_dist
                current_stop = max(current_stop, trail_stop)

            # Check stop (trail or original)
            if bar_low <= current_stop:
                exit_price = current_stop - slippage_pts
                reason = 'TRAIL_STOP' if trail_active else 'STOP'
                return (reason, exit_price, i, reason, max(mfe_pts, excursion), mae_pts, trail_active)

            # Check target
            if bar_high >= target_price:
                exit_price = target_price - slippage_pts
                return ('TARGET', exit_price, i, 'TARGET', max(mfe_pts, excursion), mae_pts, trail_active)

            mfe_pts = max(mfe_pts, excursion)
            mae_pts = max(mae_pts, entry_price - bar_low)

        else:  # SHORT
            excursion = entry_price - bar_low
            if excursion > hwm:
                hwm = excursion

            if not trail_active and hwm >= activate_dist:
                trail_active = True
                trail_stop = entry_price - hwm + trail_dist
                current_stop = min(stop_price, trail_stop)
            elif trail_active:
                trail_stop = entry_price - hwm + trail_dist
                current_stop = min(current_stop, trail_stop)

            if bar_high >= current_stop:
                exit_price = current_stop + slippage_pts
                reason = 'TRAIL_STOP' if trail_active else 'STOP'
                return (reason, exit_price, i, reason, max(mfe_pts, excursion), mae_pts, trail_active)

            if bar_low <= target_price:
                exit_price = target_price + slippage_pts
                return ('TARGET', exit_price, i, 'TARGET', max(mfe_pts, excursion), mae_pts, trail_active)

            mfe_pts = max(mfe_pts, excursion)
            mae_pts = max(mae_pts, bar_high - entry_price)

    # EOD
    last_close = bars_after_entry[-1]['close'] if len(bars_after_entry) > 0 else entry_price
    if direction == 'LONG':
        exit_price = last_close - slippage_pts
    else:
        exit_price = last_close + slippage_pts
    return ('EOD', exit_price, len(bars_after_entry) - 1, 'EOD', mfe_pts, mae_pts, trail_active)


def compute_pnl(direction, entry_price, exit_price):
    if direction == 'LONG':
        gross = (exit_price - entry_price) * POINT_VALUE
    else:
        gross = (entry_price - exit_price) * POINT_VALUE
    return gross - (COMMISSION_PER_SIDE * 2)


def run_study(df, instrument):
    print("Step 1: Running baseline backtest...")
    all_strats = load_strategies_from_config(project_root / "configs" / "strategies.yaml")
    strategies = [s for s in all_strats if s.name in CORE_5]
    print(f"  Strategies: {[s.name for s in strategies]}")

    session_bias_lookup = {}
    try:
        from rockit_core.research.db import connect as db_connect, query as db_query
        conn = db_connect()
        rows = db_query(conn, "SELECT session_date, bias FROM session_context WHERE bias IS NOT NULL")
        session_bias_lookup = {str(r[0]).split(" ")[0]: r[1] for r in rows}
        conn.close()
        print(f"  Loaded bias for {len(session_bias_lookup)} sessions")
    except Exception:
        pass

    inst_spec = get_instrument(instrument)
    engine = BacktestEngine(
        instrument=inst_spec, strategies=strategies,
        session_bias_lookup=session_bias_lookup,
    )
    result = engine.run(df, verbose=False)
    trades = result.trades
    n_total = len(trades)
    print(f"  Baseline: {n_total} trades")

    print("\nStep 2: Computing multi-timeframe ATR...")
    df = compute_multi_atr(df)

    sessions = {}
    for session_date, group in df.groupby('session_date'):
        key = str(session_date).split(' ')[0].split('T')[0]
        sessions[key] = group
    print(f"  {len(sessions)} sessions indexed")

    print("\nStep 3: Matching trades to bars...")
    slippage_pts = SLIPPAGE_TICKS * TICK_SIZE
    matched_trades = []

    for trade in trades:
        session_key = str(trade.session_date).split(' ')[0].split('T')[0]
        if session_key not in sessions:
            continue
        session_bars = sessions[session_key]

        entry_idx = find_entry_bar(session_bars, trade)
        if entry_idx is None or entry_idx < 1:
            continue

        remaining = session_bars.iloc[entry_idx + 1:].to_dict('records')
        if len(remaining) < 3:
            continue

        entry_bar = session_bars.iloc[entry_idx]

        # Get ATR values at entry
        atr_vals = {}
        for p in ATR_PERIODS:
            v = entry_bar.get(f'atr_{p}')
            if v is not None and not np.isnan(v) and v > 0:
                atr_vals[p] = v

        # Get IB range
        ib_high = session_bars.iloc[:61]['high'].max() if len(session_bars) > 60 else None
        ib_low = session_bars.iloc[:61]['low'].min() if len(session_bars) > 60 else None
        ib_range = (ib_high - ib_low) if ib_high is not None and ib_low is not None else None

        matched_trades.append({
            'trade': trade,
            'remaining_bars': remaining,
            'atr_vals': atr_vals,
            'ib_range': ib_range,
            'entry_bar': entry_bar,
        })

    print(f"  Matched {len(matched_trades)} / {n_total} trades ({len(matched_trades)/n_total*100:.0f}%)")
    if len(matched_trades) < n_total * 0.8:
        print(f"  WARNING: Low match rate. Results may be skewed.")

    print("\nStep 4: Simulating trailing stops...")

    # Baseline: no trail
    baseline_pnls = []
    for m in matched_trades:
        t = m['trade']
        sim = simulate_trade_with_trail(
            m['remaining_bars'], t.direction, t.entry_price, t.stop_price,
            t.target_price, activate_dist=999999, trail_dist=0, slippage_pts=slippage_pts
        )
        baseline_pnls.append({
            'strategy': t.strategy_name, 'direction': t.direction,
            'pnl': compute_pnl(t.direction, t.entry_price, sim[1]),
            'outcome': sim[0], 'bars': sim[2], 'mfe': sim[4], 'mae': sim[5],
            'risk': t.risk_points,
        })

    # ATR-based trailing configs
    all_results = {}

    for period in ATR_PERIODS:
        for act_mult, trail_mult in TRAIL_CONFIGS_ATR:
            label = f"ATR({period}) act={act_mult}x trail={trail_mult}x"
            pnls = []
            trail_activated_count = 0

            for m in matched_trades:
                t = m['trade']
                atr = m['atr_vals'].get(period)
                if atr is None:
                    # Use baseline for this trade
                    pnls.append(baseline_pnls[matched_trades.index(m)])
                    continue

                act_dist = atr * act_mult
                t_dist = atr * trail_mult

                sim = simulate_trade_with_trail(
                    m['remaining_bars'], t.direction, t.entry_price, t.stop_price,
                    t.target_price, act_dist, t_dist, slippage_pts
                )
                pnl = compute_pnl(t.direction, t.entry_price, sim[1])
                if sim[6]:  # trail was activated
                    trail_activated_count += 1

                pnls.append({
                    'strategy': t.strategy_name, 'direction': t.direction,
                    'pnl': pnl, 'outcome': sim[0], 'bars': sim[2],
                    'mfe': sim[4], 'mae': sim[5], 'risk': t.risk_points,
                    'trail_activated': sim[6],
                })

            all_results[label] = {
                'pnls': pnls,
                'type': 'atr', 'period': period,
                'act_mult': act_mult, 'trail_mult': trail_mult,
                'trail_activated': trail_activated_count,
            }

    # IB-based trailing configs
    for act_mult, trail_mult in TRAIL_CONFIGS_IB:
        label = f"IB act={act_mult}x trail={trail_mult}x"
        pnls = []
        trail_activated_count = 0

        for m in matched_trades:
            t = m['trade']
            ib = m['ib_range']
            if ib is None or ib < 5:
                pnls.append(baseline_pnls[matched_trades.index(m)])
                continue

            act_dist = ib * act_mult
            t_dist = ib * trail_mult

            sim = simulate_trade_with_trail(
                m['remaining_bars'], t.direction, t.entry_price, t.stop_price,
                t.target_price, act_dist, t_dist, slippage_pts
            )
            pnl = compute_pnl(t.direction, t.entry_price, sim[1])
            if sim[6]:
                trail_activated_count += 1

            pnls.append({
                'strategy': t.strategy_name, 'direction': t.direction,
                'pnl': pnl, 'outcome': sim[0], 'bars': sim[2],
                'mfe': sim[4], 'mae': sim[5], 'risk': t.risk_points,
                'trail_activated': sim[6],
            })

        all_results[label] = {
            'pnls': pnls,
            'type': 'ib',
            'act_mult': act_mult, 'trail_mult': trail_mult,
            'trail_activated': trail_activated_count,
        }

    return baseline_pnls, all_results, matched_trades


def compute_metrics(pnl_list):
    """Compute WR, PF, net PnL from list of pnl dicts."""
    pnls = [p['pnl'] for p in pnl_list]
    n = len(pnls)
    if n == 0:
        return {'trades': 0, 'wr': 0, 'pf': 0, 'net': 0, 'avg': 0}
    wins = sum(1 for p in pnls if p > 0)
    wr = wins / n * 100
    gp = sum(p for p in pnls if p > 0)
    gl = abs(sum(p for p in pnls if p <= 0))
    pf = gp / gl if gl > 0 else float('inf')
    net = sum(pnls)
    return {'trades': n, 'wr': wr, 'pf': pf, 'net': net, 'avg': net / n}


def print_results(baseline_pnls, all_results, matched_trades):
    n = len(baseline_pnls)
    bm = compute_metrics(baseline_pnls)

    print(f"\n{'='*140}")
    print(f"TRAILING STOP STUDY — {n} trades from Core 5 strategies")
    print(f"{'='*140}")

    print(f"\nBASELINE (no trailing, current fixed stop+target):")
    print(f"  Trades: {bm['trades']}, WR: {bm['wr']:.1f}%, PF: {bm['pf']:.2f}, "
          f"Net: ${bm['net']:,.0f}, Avg: ${bm['avg']:,.0f}/trade")

    print(f"\n{'='*140}")
    header = (f"{'Config':42s} {'Trades':>6s} {'WR%':>7s} {'PF':>7s} "
              f"{'Net PnL':>12s} {'Avg/Trade':>10s} {'Trails':>7s} {'vs Base':>12s}")
    print(header)
    print("-" * 140)
    print(f"{'BASELINE (no trail)':42s} {bm['trades']:6d} {bm['wr']:6.1f}% {bm['pf']:7.2f} "
          f"${bm['net']:>10,.0f} ${bm['avg']:>8,.0f} {'—':>7s} {'—':>12s}")

    combos = []
    for label, data in sorted(all_results.items()):
        m = compute_metrics(data['pnls'])
        delta = m['net'] - bm['net']
        sign = "+" if delta >= 0 else ""
        activated = data['trail_activated']
        act_pct = activated / n * 100

        print(f"{label:42s} {m['trades']:6d} {m['wr']:6.1f}% {m['pf']:7.2f} "
              f"${m['net']:>10,.0f} ${m['avg']:>8,.0f} {activated:4d}({act_pct:2.0f}%) "
              f"{sign}${delta:>10,.0f}")

        combos.append({
            'label': label, 'pf': m['pf'], 'wr': m['wr'], 'net': m['net'],
            'avg': m['avg'], 'delta': delta, 'activated': activated,
            'type': data['type'], 'pnls': data['pnls'],
        })

    # Top 5
    top5 = sorted(combos, key=lambda x: x['pf'], reverse=True)[:5]
    print(f"\n{'='*140}")
    print("TOP 5 BY PROFIT FACTOR")
    print(f"{'='*140}")
    for i, c in enumerate(top5, 1):
        print(f"  {i}. {c['label']:42s} PF={c['pf']:.2f}  WR={c['wr']:.1f}%  "
              f"Net=${c['net']:,.0f}  Trails={c['activated']}  vs Base: ${c['delta']:+,.0f}")

    # Per-strategy for best combo
    if top5:
        best = top5[0]
        print(f"\n--- Per-Strategy: {best['label']} ---")

        strat_names = sorted(set(p['strategy'] for p in best['pnls']))
        for sname in strat_names:
            s_pnls = [p for p in best['pnls'] if p['strategy'] == sname]
            b_pnls = [p for p in baseline_pnls if p['strategy'] == sname]
            sm = compute_metrics(s_pnls)
            sbm = compute_metrics(b_pnls)
            dpf = sm['pf'] - sbm['pf']
            dpnl = sm['net'] - sbm['net']
            trails = sum(1 for p in s_pnls if p.get('trail_activated', False))
            print(f"  {sname:25s} {sm['trades']:4d} trades  "
                  f"Trail: {sm['wr']:5.1f}% WR, PF {sm['pf']:.2f}, ${sm['net']:>9,.0f} ({trails} trails)  |  "
                  f"Base: {sbm['wr']:5.1f}% WR, PF {sbm['pf']:.2f}, ${sbm['net']:>9,.0f}  |  "
                  f"Delta: PF {dpf:+.2f}, PnL ${dpnl:+,.0f}")

    # Outcome analysis: what happens when trail activates?
    if top5:
        best = top5[0]
        activated = [p for p in best['pnls'] if p.get('trail_activated')]
        not_activated = [p for p in best['pnls'] if not p.get('trail_activated')]
        if activated:
            am = compute_metrics(activated)
            nm = compute_metrics(not_activated) if not_activated else {'wr': 0, 'pf': 0, 'avg': 0}
            print(f"\n  Trail ACTIVATED ({len(activated)} trades): "
                  f"WR={am['wr']:.1f}%, PF={am['pf']:.2f}, Avg=${am['avg']:,.0f}")
            print(f"  Trail NOT activated ({len(not_activated)} trades): "
                  f"WR={nm['wr']:.1f}%, PF={nm['pf']:.2f}, Avg=${nm['avg']:,.0f}")

            # Exit reason breakdown for activated
            reasons = {}
            for p in activated:
                r = p['outcome']
                reasons[r] = reasons.get(r, 0) + 1
            print(f"  Activated exit reasons: {reasons}")


def main():
    parser = argparse.ArgumentParser(description="Trailing Stop Study")
    parser.add_argument("--no-merge", action="store_true")
    parser.add_argument("--instrument", default="NQ")
    args = parser.parse_args()

    instrument = args.instrument.upper()
    print(f"{'='*70}")
    print(f"TRAILING STOP STUDY — {instrument}")
    print(f"{'='*70}\n")

    mgr = SessionDataManager(data_dir="data/sessions")
    if not args.no_merge:
        df = mgr.merge_delta(instrument)
    else:
        df = mgr.load(instrument)

    gc.collect()
    df = compute_all_features(df)
    gc.collect()

    baseline, results, matched = run_study(df, instrument)
    print_results(baseline, results, matched)


if __name__ == "__main__":
    main()
