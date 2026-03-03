#!/usr/bin/env python3
"""
Debug 80P: Simulate all 71 signals with proper stop/target checking.
Computes actual P&L per trade to understand what R target works.
"""
import sys
from pathlib import Path
from datetime import time as _time

import pandas as pd
import numpy as np

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.config.constants import IB_BARS_1MIN, RTH_START, RTH_END
from rockit_core.data.features import compute_all_features
from rockit_core.data.manager import SessionDataManager

# Load data
mgr = SessionDataManager(data_dir="data/sessions")
df = mgr.load("NQ")
df = compute_all_features(df)
df['timestamp'] = pd.to_datetime(df['timestamp'])

sessions = sorted(df['session_date'].unique())

ACCEPT_5M_BARS = 5
ACCEPT_5M_PERIODS = 2
MIN_VA_WIDTH = 25.0
ENTRY_CUTOFF = _time(13, 0)
LIMIT_FILL_WINDOW = 30
STOP_BUFFER = 10.0
POINT_VALUE = 20.0
SLIPPAGE_TICKS = 1.0
TICK_SIZE = 0.25

# Track max favorable excursion (MFE) and max adverse excursion (MAE)
trades = []

for session_date in sessions:
    session_df = df[df['session_date'] == session_date].copy()
    if len(session_df) < IB_BARS_1MIN:
        continue

    bar_times = pd.to_datetime(session_df['timestamp']).dt.time
    rth_mask = (bar_times >= RTH_START) & (bar_times <= RTH_END)
    rth_df = session_df[rth_mask]

    if len(rth_df) < IB_BARS_1MIN:
        continue

    ib_df = rth_df.head(IB_BARS_1MIN)
    post_ib_df = rth_df.iloc[IB_BARS_1MIN:]

    if len(post_ib_df) == 0:
        continue

    last_ib = ib_df.iloc[-1]
    prior_vah = last_ib.get('prior_va_vah') if 'prior_va_vah' in last_ib.index else None
    prior_val = last_ib.get('prior_va_val') if 'prior_va_val' in last_ib.index else None
    open_vs_va = last_ib.get('open_vs_va') if 'open_vs_va' in last_ib.index else None

    if prior_vah is None or prior_val is None:
        continue
    if isinstance(prior_vah, float) and pd.isna(prior_vah):
        continue
    if isinstance(prior_val, float) and pd.isna(prior_val):
        continue

    va_width = prior_vah - prior_val
    if va_width < MIN_VA_WIDTH:
        continue

    if open_vs_va not in ('ABOVE_VAH', 'BELOW_VAL'):
        continue

    direction = 'LONG' if open_vs_va == 'BELOW_VAL' else 'SHORT'

    # Compute entry/stop
    if direction == 'LONG':
        limit_price = prior_val + va_width * 0.5
        stop_price = prior_val - STOP_BUFFER
    else:
        limit_price = prior_vah - va_width * 0.5
        stop_price = prior_vah + STOP_BUFFER

    risk_pts = abs(limit_price - stop_price)

    # Check acceptance (IB + post-IB)
    accepted = False
    acceptance_bar = -1

    # IB acceptance
    consecutive = 0
    for i in range(len(ib_df)):
        if ((i + 1) % ACCEPT_5M_BARS == 0):
            close = ib_df.iloc[i]['close']
            if prior_val <= close <= prior_vah:
                consecutive += 1
            else:
                consecutive = 0
            if consecutive >= ACCEPT_5M_PERIODS:
                accepted = True
                acceptance_bar = 0
                break

    # Post-IB acceptance
    if not accepted:
        consecutive = 0
        for bar_idx in range(len(post_ib_df)):
            bar = post_ib_df.iloc[bar_idx]
            bar_time = pd.to_datetime(bar['timestamp']).time()
            if bar_time >= ENTRY_CUTOFF:
                break
            if ((bar_idx + 1) % ACCEPT_5M_BARS == 0):
                close = bar['close']
                if prior_val <= close <= prior_vah:
                    consecutive += 1
                else:
                    consecutive = 0
                if consecutive >= ACCEPT_5M_PERIODS:
                    accepted = True
                    acceptance_bar = bar_idx + 1
                    break

    if not accepted:
        continue

    # Check limit fill
    filled = False
    fill_bar = -1
    fill_start = 0 if acceptance_bar == 0 else acceptance_bar
    fill_end = min(fill_start + LIMIT_FILL_WINDOW, len(post_ib_df))

    for i in range(fill_start, fill_end):
        bar = post_ib_df.iloc[i]
        bar_time = pd.to_datetime(bar['timestamp']).time()
        if bar_time >= ENTRY_CUTOFF:
            break
        if direction == 'LONG' and bar['low'] <= limit_price:
            filled = True
            fill_bar = i
            break
        elif direction == 'SHORT' and bar['high'] >= limit_price:
            filled = True
            fill_bar = i
            break

    if not filled:
        continue

    # Simulate trade outcome: check all remaining bars for stop/target
    entry_price = limit_price + (SLIPPAGE_TICKS * TICK_SIZE if direction == 'LONG' else -SLIPPAGE_TICKS * TICK_SIZE)

    # Track MFE (max favorable excursion in R)
    mfe_pts = 0.0
    mae_pts = 0.0
    exit_bar = None
    exit_price = None
    exit_reason = None

    for i in range(fill_bar + 1, len(post_ib_df)):
        bar = post_ib_df.iloc[i]
        bar_time = pd.to_datetime(bar['timestamp']).time()

        if direction == 'LONG':
            favorable = bar['high'] - entry_price
            adverse = entry_price - bar['low']
            # Check stop
            if bar['low'] <= stop_price:
                exit_price = stop_price - SLIPPAGE_TICKS * TICK_SIZE
                exit_reason = 'STOP'
                exit_bar = i
                break
        else:
            favorable = entry_price - bar['low']
            adverse = bar['high'] - entry_price
            if bar['high'] >= stop_price:
                exit_price = stop_price + SLIPPAGE_TICKS * TICK_SIZE
                exit_reason = 'STOP'
                exit_bar = i
                break

        mfe_pts = max(mfe_pts, favorable)
        mae_pts = max(mae_pts, adverse)

    # EOD close if not stopped
    if exit_price is None:
        last_bar = post_ib_df.iloc[-1]
        exit_price = last_bar['close']
        exit_reason = 'EOD'
        exit_bar = len(post_ib_df) - 1

    if direction == 'LONG':
        pnl_pts = exit_price - entry_price
        final_mfe = max(mfe_pts, exit_price - entry_price if exit_price > entry_price else 0)
    else:
        pnl_pts = entry_price - exit_price
        final_mfe = max(mfe_pts, entry_price - exit_price if entry_price > exit_price else 0)

    mfe_r = final_mfe / risk_pts if risk_pts > 0 else 0
    pnl_dollar = pnl_pts * POINT_VALUE

    trades.append({
        'date': str(session_date)[:10],
        'direction': direction,
        'va_width': round(va_width, 1),
        'entry': round(entry_price, 1),
        'stop': round(stop_price, 1),
        'exit': round(exit_price, 1),
        'risk_pts': round(risk_pts, 1),
        'pnl_pts': round(pnl_pts, 1),
        'pnl_dollar': round(pnl_dollar, 2),
        'mfe_r': round(mfe_r, 2),
        'exit_reason': exit_reason,
        'bars_held': exit_bar - fill_bar if exit_bar else 0,
    })

print(f"\n{'='*80}")
print(f"80P TRADE SIMULATION — {len(trades)} trades (no DD limit)")
print(f"{'='*80}")

# Show all trades
wins_by_r = {1.0: 0, 1.5: 0, 2.0: 0, 2.5: 0, 3.0: 0, 4.0: 0}

for t in trades:
    flag = "WIN" if t['pnl_pts'] > 0 else "LOSS"
    print(f"  {t['date']} {t['direction']:5s} VA_w={t['va_width']:6.0f} "
          f"risk={t['risk_pts']:5.0f} pnl={t['pnl_dollar']:>8.0f} "
          f"MFE={t['mfe_r']:.1f}R exit={t['exit_reason']:4s} bars={t['bars_held']:3d} [{flag}]")

    for r_target in wins_by_r:
        if t['mfe_r'] >= r_target:
            wins_by_r[r_target] += 1

# Summary statistics
print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
total = len(trades)
wins = sum(1 for t in trades if t['pnl_pts'] > 0)
losses = sum(1 for t in trades if t['pnl_pts'] <= 0)
net = sum(t['pnl_dollar'] for t in trades)
mfe_values = [t['mfe_r'] for t in trades]

print(f"  Total: {total} trades")
print(f"  Current WR (stop/EOD exit): {wins}/{total} = {wins/total*100:.1f}%")
print(f"  Current net P&L: ${net:,.2f}")
print(f"  MFE distribution (max R reached before exit):")
print(f"    Mean MFE: {np.mean(mfe_values):.2f}R")
print(f"    Median MFE: {np.median(mfe_values):.2f}R")
print(f"    P25/P75: {np.percentile(mfe_values, 25):.2f}R / {np.percentile(mfe_values, 75):.2f}R")
print(f"    Max MFE: {max(mfe_values):.2f}R")

print(f"\n  Win Rate at different R targets:")
for r_target in sorted(wins_by_r):
    wr = wins_by_r[r_target] / total * 100
    # Compute hypothetical PF
    wins_n = wins_by_r[r_target]
    losses_n = total - wins_n
    gross_win = wins_n * r_target  # in R units
    gross_loss = losses_n * 1.0
    pf = gross_win / gross_loss if gross_loss > 0 else float('inf')
    expectancy_r = (wr/100 * r_target) - ((1-wr/100) * 1)
    print(f"    {r_target:.1f}R target: {wins_n}/{total} = {wr:.1f}% WR, "
          f"PF={pf:.2f}, E[R]={expectancy_r:.2f}")

# VA width analysis
print(f"\n  VA Width distribution for trades:")
va_widths = [t['va_width'] for t in trades]
print(f"    Mean: {np.mean(va_widths):.0f} pts")
print(f"    Median: {np.median(va_widths):.0f} pts")
print(f"    P25/P75: {np.percentile(va_widths, 25):.0f} / {np.percentile(va_widths, 75):.0f}")
print(f"    Min/Max: {min(va_widths):.0f} / {max(va_widths):.0f}")

# Win rate by VA width buckets
print(f"\n  Win Rate by VA Width (at 1.5R target):")
for w_lo, w_hi in [(25, 100), (100, 200), (200, 300), (300, 500), (500, 2000)]:
    bucket = [t for t in trades if w_lo <= t['va_width'] < w_hi]
    if bucket:
        bucket_wins = sum(1 for t in bucket if t['mfe_r'] >= 1.5)
        print(f"    {w_lo}-{w_hi}: {len(bucket)} trades, "
              f"{bucket_wins}/{len(bucket)} = {bucket_wins/len(bucket)*100:.1f}% WR at 1.5R")
