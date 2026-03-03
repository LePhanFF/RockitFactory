#!/usr/bin/env python3
"""
Debug 80P: Trace every gate across all sessions with RTH-correct IB.
Replicates the exact backtest engine data flow.
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

# --- Load data ---
mgr = SessionDataManager(data_dir="data/sessions")
df = mgr.load("NQ")
df = compute_all_features(df)

sessions = sorted(df['session_date'].unique())

# Gate counters
armed_count = 0
no_prior_va = 0
va_too_narrow = 0
inside_va_at_open = 0
ib_accept_count = 0
postib_accept_count = 0
accept_before_1pm = 0
fill_count = 0
time_killed = 0

ACCEPT_5M_BARS = 5
ACCEPT_5M_PERIODS = 2
MIN_VA_WIDTH = 25.0
ENTRY_CUTOFF = _time(13, 0)
LIMIT_FILL_WINDOW = 30

armed_sessions = []

for session_date in sessions:
    session_df = df[df['session_date'] == session_date].copy()
    if len(session_df) < IB_BARS_1MIN:
        continue

    # --- RTH filtering (same as backtest engine) ---
    if 'timestamp' in session_df.columns:
        bar_times = pd.to_datetime(session_df['timestamp']).dt.time
        rth_mask = (bar_times >= RTH_START) & (bar_times <= RTH_END)
        rth_df = session_df[rth_mask]
    else:
        rth_df = session_df

    if len(rth_df) < IB_BARS_1MIN:
        continue

    ib_df = rth_df.head(IB_BARS_1MIN)  # 9:30-10:29
    post_ib_df = rth_df.iloc[IB_BARS_1MIN:]  # 10:30-16:00

    if len(post_ib_df) == 0:
        continue

    # --- Read prior VA from last IB bar (same as backtest engine) ---
    last_ib = ib_df.iloc[-1]
    prior_vah = last_ib.get('prior_va_vah') if 'prior_va_vah' in last_ib.index else None
    prior_val = last_ib.get('prior_va_val') if 'prior_va_val' in last_ib.index else None
    open_vs_va = last_ib.get('open_vs_va') if 'open_vs_va' in last_ib.index else None

    # Handle NaN
    if prior_vah is not None and (isinstance(prior_vah, float) and pd.isna(prior_vah)):
        prior_vah = None
    if prior_val is not None and (isinstance(prior_val, float) and pd.isna(prior_val)):
        prior_val = None
    if open_vs_va is not None and (isinstance(open_vs_va, float) and pd.isna(open_vs_va)):
        open_vs_va = None

    if prior_vah is None or prior_val is None:
        no_prior_va += 1
        continue

    va_width = prior_vah - prior_val
    if va_width < MIN_VA_WIDTH:
        va_too_narrow += 1
        continue

    if open_vs_va not in ('ABOVE_VAH', 'BELOW_VAL'):
        inside_va_at_open += 1
        continue

    direction = 'LONG' if open_vs_va == 'BELOW_VAL' else 'SHORT'
    armed_count += 1

    # Compute limit/stop
    if direction == 'LONG':
        limit_price = prior_val + va_width * 0.5
        stop_price = prior_val - 10.0
    else:
        limit_price = prior_vah - va_width * 0.5
        stop_price = prior_vah + 10.0

    # --- Check IB acceptance ---
    ib_accepted = False
    ib_consecutive = 0
    for i in range(len(ib_df)):
        is_5m_end = ((i + 1) % ACCEPT_5M_BARS == 0)
        if is_5m_end:
            close = ib_df.iloc[i]['close']
            if prior_val <= close <= prior_vah:
                ib_consecutive += 1
            else:
                ib_consecutive = 0
            if ib_consecutive >= ACCEPT_5M_PERIODS:
                ib_accepted = True
                ib_accept_count += 1
                break

    # --- Check post-IB acceptance ---
    postib_accepted = False
    acceptance_bar = -1
    postib_consecutive = 0
    for bar_idx in range(len(post_ib_df)):
        bar = post_ib_df.iloc[bar_idx]
        bar_time = pd.to_datetime(bar['timestamp']).time() if 'timestamp' in bar.index else None

        # Time gate
        if bar_time and bar_time >= ENTRY_CUTOFF:
            if not ib_accepted and not postib_accepted:
                time_killed += 1
            break

        is_5m_end = ((bar_idx + 1) % ACCEPT_5M_BARS == 0)
        if is_5m_end:
            close = bar['close']
            if prior_val <= close <= prior_vah:
                postib_consecutive += 1
            else:
                postib_consecutive = 0
            if postib_consecutive >= ACCEPT_5M_PERIODS:
                postib_accepted = True
                acceptance_bar = bar_idx
                postib_accept_count += 1
                break

    accepted = ib_accepted or postib_accepted

    if accepted:
        accept_before_1pm += 1

    # --- Check limit fill ---
    filled = False
    if accepted:
        # If IB accepted, start fill check from first post-IB bar
        fill_start = 0 if ib_accepted else (acceptance_bar + 1)
        fill_end = min(fill_start + LIMIT_FILL_WINDOW, len(post_ib_df))
        for i in range(fill_start, fill_end):
            bar = post_ib_df.iloc[i]
            bar_time = pd.to_datetime(bar['timestamp']).time() if 'timestamp' in bar.index else None
            if bar_time and bar_time >= ENTRY_CUTOFF:
                break
            if direction == 'LONG' and bar['low'] <= limit_price:
                filled = True
                break
            elif direction == 'SHORT' and bar['high'] >= limit_price:
                filled = True
                break

    if filled:
        fill_count += 1

    armed_sessions.append({
        'date': str(session_date)[:10],
        'direction': direction,
        'vah': round(prior_vah, 1),
        'val': round(prior_val, 1),
        'va_width': round(va_width, 1),
        'ib_accepted': ib_accepted,
        'postib_accepted': postib_accepted,
        'filled': filled,
        'limit': round(limit_price, 1),
    })

print()
print("=" * 70)
print("80P DIAGNOSTIC (RTH-correct IB)")
print("=" * 70)
print(f"Total sessions:        {len(sessions)}")
print(f"No prior VA:           {no_prior_va}")
print(f"VA too narrow (<25):   {va_too_narrow}")
print(f"Open inside VA:        {inside_va_at_open}")
print(f"Setup armed:           {armed_count}")
print(f"IB acceptance:         {ib_accept_count}")
print(f"Post-IB acceptance:    {postib_accept_count}")
print(f"Total accepted:        {accept_before_1pm}")
print(f"Time killed (1PM):     {time_killed}")
print(f"Limit filled:          {fill_count}")

print(f"\n--- Armed sessions (first 20) ---")
for d in armed_sessions[:20]:
    ib = "IB_ACC" if d['ib_accepted'] else ""
    post = "POST_ACC" if d['postib_accepted'] else ""
    fill = "FILL" if d['filled'] else ""
    status = fill or post or ib or "NO_ACCEPT"
    print(f"  {d['date']} {d['direction']:5s} VA:{d['val']:.0f}-{d['vah']:.0f} "
          f"(w={d['va_width']:.0f}) limit={d['limit']:.0f} -> {status}")

# Show some IB bar details for first 3 armed sessions
print(f"\n--- IB bar detail for first 3 armed sessions ---")
shown = 0
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
    last_ib = ib_df.iloc[-1]
    prior_vah = last_ib.get('prior_va_vah') if 'prior_va_vah' in last_ib.index else None
    prior_val = last_ib.get('prior_va_val') if 'prior_va_val' in last_ib.index else None
    open_vs_va = last_ib.get('open_vs_va') if 'open_vs_va' in last_ib.index else None

    if prior_vah is None or prior_val is None or pd.isna(prior_vah) or pd.isna(prior_val):
        continue
    va_width = prior_vah - prior_val
    if va_width < MIN_VA_WIDTH:
        continue
    if open_vs_va not in ('ABOVE_VAH', 'BELOW_VAL'):
        continue

    shown += 1
    direction = 'LONG' if open_vs_va == 'BELOW_VAL' else 'SHORT'
    print(f"\n  Session {str(session_date)[:10]} ({direction}):")
    print(f"    VAH={prior_vah:.1f}, VAL={prior_val:.1f}, Width={va_width:.1f}")
    print(f"    5-min close checks during IB (12 periods):")
    for i in range(len(ib_df)):
        is_5m_end = ((i + 1) % ACCEPT_5M_BARS == 0)
        if is_5m_end:
            close = ib_df.iloc[i]['close']
            ts = ib_df.iloc[i]['timestamp']
            inside = prior_val <= close <= prior_vah
            print(f"      {ts} close={close:.1f} inside_va={inside} "
                  f"(VAL={prior_val:.1f} <= {close:.1f} <= VAH={prior_vah:.1f})")

    if shown >= 3:
        break
