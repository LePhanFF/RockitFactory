#!/usr/bin/env python3
"""
Quant Study: ATR-Based Profit Targets vs Fixed Targets

For each historical trade from the core 5 strategies, simulate:
  - What if target was X * ATR(N) instead of the fixed target?
  - Walk forward bar-by-bar: does target or stop get hit first?

ATR timeframes: 5, 15, 30, 60 bars (1-min data = 5min, 15min, 30min, 60min ATR)
ATR multiples:  0.5x, 0.75x, 1.0x, 1.25x, 1.5x, 2.0x, 2.5x, 3.0x
Also test IB-range multiples: 0.25x, 0.5x, 0.75x, 1.0x, 1.5x IB

Compare: WR, PF, avg PnL, total PnL for each combo vs current fixed targets.

Usage:
    python scripts/study_atr_targets.py --no-merge
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
ATR_PERIODS = [5, 15, 30, 60]
ATR_MULTIPLES = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
IB_MULTIPLES = [0.25, 0.5, 0.75, 1.0, 1.5]

# NQ specs
TICK_SIZE = 0.25
POINT_VALUE = 20.0
SLIPPAGE_TICKS = 1
COMMISSION_PER_SIDE = 2.05


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


def simulate_trade(bars_after_entry, direction, entry_price, stop_price,
                   target_price, slippage_pts):
    """Walk forward through bars and determine outcome with given target.

    Returns: (outcome, exit_price, exit_bar_idx, exit_reason, mfe_pts, mae_pts)
    """
    mfe_pts = 0.0
    mae_pts = 0.0

    for i, bar in enumerate(bars_after_entry):
        bar_high = bar['high']
        bar_low = bar['low']
        bar_close = bar['close']

        if direction == 'LONG':
            # Check stop first (conservative)
            if bar_low <= stop_price:
                exit_price = stop_price - slippage_pts
                return ('STOP', exit_price, i, 'STOP', mfe_pts, mae_pts)
            # Check target
            if bar_high >= target_price:
                exit_price = target_price - slippage_pts
                return ('TARGET', exit_price, i, 'TARGET', max(mfe_pts, bar_high - entry_price), mae_pts)
            # Update MFE/MAE
            mfe_pts = max(mfe_pts, bar_high - entry_price)
            mae_pts = max(mae_pts, entry_price - bar_low)
        else:  # SHORT
            # Check stop first
            if bar_high >= stop_price:
                exit_price = stop_price + slippage_pts
                return ('STOP', exit_price, i, 'STOP', mfe_pts, mae_pts)
            # Check target
            if bar_low <= target_price:
                exit_price = target_price + slippage_pts
                return ('TARGET', exit_price, i, 'TARGET', max(mfe_pts, entry_price - bar_low), mae_pts)
            # Update MFE/MAE
            mfe_pts = max(mfe_pts, entry_price - bar_low)
            mae_pts = max(mae_pts, bar_high - entry_price)

    # EOD — close at last bar close
    last_close = bars_after_entry[-1]['close'] if len(bars_after_entry) > 0 else entry_price
    if direction == 'LONG':
        exit_price = last_close - slippage_pts
    else:
        exit_price = last_close + slippage_pts
    return ('EOD', exit_price, len(bars_after_entry) - 1, 'EOD', mfe_pts, mae_pts)


def compute_pnl(direction, entry_price, exit_price):
    """Compute net PnL for a trade."""
    if direction == 'LONG':
        gross = (exit_price - entry_price) * POINT_VALUE
    else:
        gross = (entry_price - exit_price) * POINT_VALUE
    return gross - (COMMISSION_PER_SIDE * 2)


def run_study(df: pd.DataFrame, instrument: str):
    """Run the ATR target study."""

    # Step 1: Run baseline backtest to get actual trades
    print("Step 1: Running baseline backtest to collect trades...")
    all_strats = load_strategies_from_config(project_root / "configs" / "strategies.yaml")
    strategies = [s for s in all_strats if s.name in CORE_5]
    print(f"  Core 5 strategies: {[s.name for s in strategies]}")

    # Load session bias
    session_bias_lookup = {}
    try:
        from rockit_core.research.db import connect as db_connect, query as db_query
        conn = db_connect()
        rows = db_query(conn, "SELECT session_date, bias FROM session_context WHERE bias IS NOT NULL")
        session_bias_lookup = {str(r[0]).split(" ")[0]: r[1] for r in rows}
        conn.close()
        print(f"  Loaded bias for {len(session_bias_lookup)} sessions")
    except Exception as e:
        print(f"  Warning: no bias data: {e}")

    inst_spec = get_instrument(instrument)
    engine = BacktestEngine(
        instrument=inst_spec,
        strategies=strategies,
        session_bias_lookup=session_bias_lookup,
    )
    result = engine.run(df, verbose=False)
    baseline_trades = result.trades
    print(f"  Baseline: {len(baseline_trades)} trades, "
          f"WR={sum(1 for t in baseline_trades if t.net_pnl > 0)/len(baseline_trades)*100:.1f}%")

    # Step 2: Compute multi-timeframe ATR
    print("\nStep 2: Computing multi-timeframe ATR...")
    df = compute_multi_atr(df)

    # Build session lookup: session_date → bars DataFrame
    sessions = {}
    for session_date, group in df.groupby('session_date'):
        session_key = str(session_date).split(' ')[0].split('T')[0]
        sessions[session_key] = group.reset_index(drop=True)
    print(f"  {len(sessions)} sessions indexed")

    # Step 3: For each trade, simulate with different ATR targets
    print("\nStep 3: Simulating ATR-based targets...")

    slippage_pts = SLIPPAGE_TICKS * TICK_SIZE
    results = []  # list of dicts

    for trade in baseline_trades:
        session_key = str(trade.session_date).split(' ')[0].split('T')[0]
        if session_key not in sessions:
            continue

        session_bars = sessions[session_key]

        # Find entry bar index (approximate by matching entry price and time)
        # Use bars_held to find where entry happened: entry_bar = (total_bars - bars_held)
        # More reliable: find the bar closest to entry_price after IB close
        entry_price = trade.entry_price
        direction = trade.direction
        stop_price = trade.stop_price if hasattr(trade, 'stop_price') else None
        original_target = trade.target_price if hasattr(trade, 'target_price') else None
        strategy = trade.strategy_name

        if stop_price is None or original_target is None:
            continue

        # Find entry bar: look for bar where close is near entry_price
        # Use the signal timestamp if available
        entry_bar_idx = None
        bars_held = trade.bars_held if hasattr(trade, 'bars_held') else 0

        # Estimate entry bar from total bars and bars_held
        total_bars = len(session_bars)
        if bars_held > 0 and bars_held < total_bars:
            entry_bar_idx = total_bars - bars_held - 1
        else:
            # Fallback: find bar closest to entry price in IB-close region (bar 60-120)
            for idx in range(60, min(total_bars, 300)):
                bar = session_bars.iloc[idx]
                if direction == 'LONG' and abs(bar['low'] - entry_price) < 5:
                    entry_bar_idx = idx
                    break
                elif direction == 'SHORT' and abs(bar['high'] - entry_price) < 5:
                    entry_bar_idx = idx
                    break

        if entry_bar_idx is None or entry_bar_idx < 5:
            continue

        # Get bars after entry
        remaining_bars = session_bars.iloc[entry_bar_idx + 1:].to_dict('records')
        if len(remaining_bars) < 3:
            continue

        # Get ATR values at entry time
        entry_bar = session_bars.iloc[entry_bar_idx]
        atr_values = {}
        for period in ATR_PERIODS:
            col = f'atr_{period}'
            val = entry_bar.get(col)
            if val is not None and not np.isnan(val) and val > 0:
                atr_values[period] = val

        # Get IB range
        ib_high = session_bars.iloc[:61]['high'].max() if total_bars > 60 else None
        ib_low = session_bars.iloc[:61]['low'].min() if total_bars > 60 else None
        ib_range = (ib_high - ib_low) if ib_high and ib_low else None

        # Baseline: simulate with original target
        original_risk = abs(entry_price - stop_price)
        baseline_result = simulate_trade(
            remaining_bars, direction, entry_price, stop_price,
            original_target, slippage_pts
        )
        baseline_pnl = compute_pnl(direction, entry_price, baseline_result[1])

        trade_info = {
            'session': session_key,
            'strategy': strategy,
            'direction': direction,
            'entry_price': entry_price,
            'original_stop': stop_price,
            'original_target': original_target,
            'original_risk': original_risk,
            'ib_range': ib_range,
            'baseline_outcome': baseline_result[0],
            'baseline_pnl': baseline_pnl,
            'baseline_mfe': baseline_result[4],
            'baseline_mae': baseline_result[5],
            'baseline_bars': baseline_result[2],
        }

        # Add ATR values
        for period in ATR_PERIODS:
            trade_info[f'atr_{period}'] = atr_values.get(period, np.nan)

        # Simulate with ATR-based targets (same stop as original)
        for period in ATR_PERIODS:
            atr_val = atr_values.get(period)
            if atr_val is None:
                continue

            for mult in ATR_MULTIPLES:
                target_dist = atr_val * mult
                if direction == 'LONG':
                    new_target = entry_price + target_dist
                else:
                    new_target = entry_price - target_dist

                sim = simulate_trade(
                    remaining_bars, direction, entry_price, stop_price,
                    new_target, slippage_pts
                )
                pnl = compute_pnl(direction, entry_price, sim[1])

                key = f'atr{period}_{mult}x'
                trade_info[f'{key}_outcome'] = sim[0]
                trade_info[f'{key}_pnl'] = pnl
                trade_info[f'{key}_bars'] = sim[2]
                trade_info[f'{key}_target_dist'] = target_dist

        # Simulate with IB-range targets
        if ib_range and ib_range > 5:
            for mult in IB_MULTIPLES:
                target_dist = ib_range * mult
                if direction == 'LONG':
                    new_target = entry_price + target_dist
                else:
                    new_target = entry_price - target_dist

                sim = simulate_trade(
                    remaining_bars, direction, entry_price, stop_price,
                    new_target, slippage_pts
                )
                pnl = compute_pnl(direction, entry_price, sim[1])

                key = f'ib_{mult}x'
                trade_info[f'{key}_outcome'] = sim[0]
                trade_info[f'{key}_pnl'] = pnl
                trade_info[f'{key}_bars'] = sim[2]
                trade_info[f'{key}_target_dist'] = target_dist

        results.append(trade_info)

    print(f"  Simulated {len(results)} trades")
    return results


def analyze_results(results: list[dict]):
    """Analyze and print comparison tables."""
    if not results:
        print("No results to analyze.")
        return

    df = pd.DataFrame(results)
    n_trades = len(df)

    print(f"\n{'='*130}")
    print(f"ATR TARGET STUDY — {n_trades} trades from Core 5 strategies")
    print(f"{'='*130}")

    # Baseline stats
    baseline_wins = (df['baseline_pnl'] > 0).sum()
    baseline_wr = baseline_wins / n_trades * 100
    baseline_pnl = df['baseline_pnl'].sum()
    baseline_gp = df.loc[df['baseline_pnl'] > 0, 'baseline_pnl'].sum()
    baseline_gl = abs(df.loc[df['baseline_pnl'] <= 0, 'baseline_pnl'].sum())
    baseline_pf = baseline_gp / baseline_gl if baseline_gl > 0 else float('inf')
    baseline_avg = df['baseline_pnl'].mean()

    print(f"\nBASELINE (current fixed targets):")
    print(f"  Trades: {n_trades}, WR: {baseline_wr:.1f}%, PF: {baseline_pf:.2f}, "
          f"Net: ${baseline_pnl:,.0f}, Avg: ${baseline_avg:,.0f}/trade")
    print(f"  Avg MFE: {df['baseline_mfe'].mean():.1f}pts, Avg MAE: {df['baseline_mae'].mean():.1f}pts")

    # ATR-based results
    print(f"\n{'='*130}")
    print(f"ATR-BASED TARGETS (same stop as baseline)")
    print(f"{'='*130}")

    header = f"{'Target':20s} {'Trades':>6s} {'WR%':>7s} {'PF':>7s} {'Net PnL':>12s} {'Avg/Trade':>10s} {'Avg Dist':>9s} {'vs Base':>10s}"
    print(header)
    print("-" * 130)

    # Baseline row
    print(f"{'BASELINE (fixed)':20s} {n_trades:6d} {baseline_wr:6.1f}% {baseline_pf:7.2f} "
          f"${baseline_pnl:>10,.0f} ${baseline_avg:>8,.0f} {'—':>9s} {'—':>10s}")

    all_combos = []

    for period in ATR_PERIODS:
        for mult in ATR_MULTIPLES:
            key = f'atr{period}_{mult}x'
            pnl_col = f'{key}_pnl'
            outcome_col = f'{key}_outcome'
            dist_col = f'{key}_target_dist'

            if pnl_col not in df.columns:
                continue

            valid = df[pnl_col].notna()
            if valid.sum() == 0:
                continue

            subset = df[valid]
            wins = (subset[pnl_col] > 0).sum()
            total = len(subset)
            wr = wins / total * 100
            total_pnl = subset[pnl_col].sum()
            gp = subset.loc[subset[pnl_col] > 0, pnl_col].sum()
            gl = abs(subset.loc[subset[pnl_col] <= 0, pnl_col].sum())
            pf = gp / gl if gl > 0 else float('inf')
            avg_pnl = subset[pnl_col].mean()
            avg_dist = subset[dist_col].mean() if dist_col in subset.columns else 0
            delta = total_pnl - baseline_pnl
            sign = "+" if delta >= 0 else ""

            label = f"ATR({period}) x{mult}"
            print(f"{label:20s} {total:6d} {wr:6.1f}% {pf:7.2f} "
                  f"${total_pnl:>10,.0f} ${avg_pnl:>8,.0f} {avg_dist:8.1f}p {sign}${delta:>8,.0f}")

            all_combos.append({
                'label': label, 'type': 'atr', 'period': period, 'mult': mult,
                'trades': total, 'wr': wr, 'pf': pf, 'net_pnl': total_pnl,
                'avg_pnl': avg_pnl, 'avg_dist': avg_dist, 'delta_vs_baseline': delta,
            })

    # IB-range results
    print(f"\n{'='*130}")
    print(f"IB-RANGE TARGETS (same stop as baseline)")
    print(f"{'='*130}")
    print(header)
    print("-" * 130)
    print(f"{'BASELINE (fixed)':20s} {n_trades:6d} {baseline_wr:6.1f}% {baseline_pf:7.2f} "
          f"${baseline_pnl:>10,.0f} ${baseline_avg:>8,.0f} {'—':>9s} {'—':>10s}")

    for mult in IB_MULTIPLES:
        key = f'ib_{mult}x'
        pnl_col = f'{key}_pnl'
        outcome_col = f'{key}_outcome'
        dist_col = f'{key}_target_dist'

        if pnl_col not in df.columns:
            continue

        valid = df[pnl_col].notna()
        if valid.sum() == 0:
            continue

        subset = df[valid]
        wins = (subset[pnl_col] > 0).sum()
        total = len(subset)
        wr = wins / total * 100
        total_pnl = subset[pnl_col].sum()
        gp = subset.loc[subset[pnl_col] > 0, pnl_col].sum()
        gl = abs(subset.loc[subset[pnl_col] <= 0, pnl_col].sum())
        pf = gp / gl if gl > 0 else float('inf')
        avg_pnl = subset[pnl_col].mean()
        avg_dist = subset[dist_col].mean() if dist_col in subset.columns else 0
        delta = total_pnl - baseline_pnl
        sign = "+" if delta >= 0 else ""

        label = f"IB x{mult}"
        print(f"{label:20s} {total:6d} {wr:6.1f}% {pf:7.2f} "
              f"${total_pnl:>10,.0f} ${avg_pnl:>8,.0f} {avg_dist:8.1f}p {sign}${delta:>8,.0f}")

        all_combos.append({
            'label': label, 'type': 'ib', 'period': 0, 'mult': mult,
            'trades': total, 'wr': wr, 'pf': pf, 'net_pnl': total_pnl,
            'avg_pnl': avg_pnl, 'avg_dist': avg_dist, 'delta_vs_baseline': delta,
        })

    # Per-strategy breakdown for top 5 combos
    if all_combos:
        top5 = sorted(all_combos, key=lambda x: x['pf'], reverse=True)[:5]
        print(f"\n{'='*130}")
        print(f"TOP 5 BY PROFIT FACTOR")
        print(f"{'='*130}")
        for i, c in enumerate(top5, 1):
            print(f"  {i}. {c['label']:20s} PF={c['pf']:.2f}  WR={c['wr']:.1f}%  "
                  f"Net=${c['net_pnl']:,.0f}  Avg Dist={c['avg_dist']:.1f}pts  "
                  f"vs Baseline: ${c['delta_vs_baseline']:+,.0f}")

        # Per-strategy for best combo
        best = top5[0]
        print(f"\n--- Per-Strategy for Best: {best['label']} ---")

        if best['type'] == 'atr':
            key = f"atr{best['period']}_{best['mult']}x"
        else:
            key = f"ib_{best['mult']}x"

        pnl_col = f'{key}_pnl'
        if pnl_col in df.columns:
            for strat in sorted(df['strategy'].unique()):
                sdf = df[df['strategy'] == strat]
                valid = sdf[pnl_col].notna()
                if valid.sum() == 0:
                    continue
                sub = sdf[valid]
                s_wins = (sub[pnl_col] > 0).sum()
                s_total = len(sub)
                s_wr = s_wins / s_total * 100
                s_pnl = sub[pnl_col].sum()
                s_gp = sub.loc[sub[pnl_col] > 0, pnl_col].sum()
                s_gl = abs(sub.loc[sub[pnl_col] <= 0, pnl_col].sum())
                s_pf = s_gp / s_gl if s_gl > 0 else float('inf')

                # Baseline for this strategy
                b_wins = (sub['baseline_pnl'] > 0).sum()
                b_wr = b_wins / s_total * 100
                b_pnl = sub['baseline_pnl'].sum()
                b_gp = sub.loc[sub['baseline_pnl'] > 0, 'baseline_pnl'].sum()
                b_gl = abs(sub.loc[sub['baseline_pnl'] <= 0, 'baseline_pnl'].sum())
                b_pf = b_gp / b_gl if b_gl > 0 else float('inf')

                delta_pf = s_pf - b_pf
                delta_pnl = s_pnl - b_pnl
                print(f"  {strat:25s} {s_total:4d} trades  "
                      f"ATR: {s_wr:5.1f}% WR, PF {s_pf:.2f}, ${s_pnl:>9,.0f}  |  "
                      f"Base: {b_wr:5.1f}% WR, PF {b_pf:.2f}, ${b_pnl:>9,.0f}  |  "
                      f"Delta PF: {delta_pf:+.2f}, PnL: ${delta_pnl:+,.0f}")

    # MFE analysis — how much room is actually available?
    print(f"\n{'='*130}")
    print(f"MFE ANALYSIS — How much room do trades actually have?")
    print(f"{'='*130}")

    for strat in sorted(df['strategy'].unique()):
        sdf = df[df['strategy'] == strat]
        mfe = sdf['baseline_mfe']
        mae = sdf['baseline_mae']
        risk = sdf['original_risk']
        mfe_r = mfe / risk.replace(0, np.nan)

        print(f"\n  {strat} ({len(sdf)} trades):")
        print(f"    MFE:  avg={mfe.mean():.1f}pts  median={mfe.median():.1f}pts  "
              f"p25={mfe.quantile(0.25):.1f}pts  p75={mfe.quantile(0.75):.1f}pts")
        print(f"    MAE:  avg={mae.mean():.1f}pts  median={mae.median():.1f}pts")
        print(f"    Risk: avg={risk.mean():.1f}pts")
        print(f"    MFE/R: avg={mfe_r.mean():.2f}R  median={mfe_r.median():.2f}R  "
              f"p25={mfe_r.quantile(0.25):.2f}R  p75={mfe_r.quantile(0.75):.2f}R")

        # What % of trades reach various R multiples?
        for r_mult in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
            pct = (mfe_r >= r_mult).mean() * 100
            print(f"    Reach {r_mult}R: {pct:.0f}%", end="")
        print()


def main():
    parser = argparse.ArgumentParser(description="ATR Target Study")
    parser.add_argument("--no-merge", action="store_true")
    parser.add_argument("--instrument", default="NQ")
    args = parser.parse_args()

    instrument = args.instrument.upper()
    print(f"{'='*70}")
    print(f"ATR TARGET STUDY — {instrument}")
    print(f"{'='*70}\n")

    mgr = SessionDataManager(data_dir="data/sessions")
    if not args.no_merge:
        df = mgr.merge_delta(instrument)
    else:
        df = mgr.load(instrument)

    gc.collect()
    df = compute_all_features(df)
    gc.collect()

    results = run_study(df, instrument)
    analyze_results(results)


if __name__ == "__main__":
    main()
