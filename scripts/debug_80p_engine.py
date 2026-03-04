#!/usr/bin/env python3
"""
Debug 80P: Run through EXACT backtest engine flow with debug output.
Traces each armed session's acceptance and fill gates.
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
from rockit_core.strategies.eighty_percent_rule import (
    EightyPercentRule, ACCEPT_5M_BARS, ACCEPT_5M_PERIODS,
    ENTRY_CUTOFF, LIMIT_FILL_WINDOW, MIN_VA_WIDTH,
)
from rockit_core.strategies.day_type import classify_day_type, classify_trend_strength
from rockit_core.strategies.day_confidence import DayTypeConfidenceScorer

# --- Load data (same as run_backtest.py) ---
mgr = SessionDataManager(data_dir="data/sessions")
df = mgr.load("NQ")
df = compute_all_features(df)

# Ensure timestamps are datetime
df['timestamp'] = pd.to_datetime(df['timestamp'])

sessions = sorted(df['session_date'].unique())

strategy = EightyPercentRule()
ib_range_history = []
prior_session_context = {}
signal_count = 0
armed_trace = []

for session_date in sessions:
    session_df = df[df['session_date'] == session_date].copy()
    session_str = str(session_date)

    if len(session_df) < IB_BARS_1MIN:
        continue

    # --- RTH filtering (EXACT match of backtest engine) ---
    bar_times = pd.to_datetime(session_df['timestamp']).dt.time
    rth_mask = (bar_times >= RTH_START) & (bar_times <= RTH_END)
    rth_df = session_df[rth_mask]

    if len(rth_df) < IB_BARS_1MIN:
        continue

    ib_df = rth_df.head(IB_BARS_1MIN)
    post_ib_df = rth_df.iloc[IB_BARS_1MIN:]

    if len(post_ib_df) == 0:
        continue

    ib_high = ib_df['high'].max()
    ib_low = ib_df['low'].min()
    ib_range = ib_high - ib_low
    ib_mid = (ib_high + ib_low) / 2

    if ib_range <= 0:
        continue

    # --- Build session_context (EXACT match of backtest engine) ---
    last_ib_close = ib_df['close'].iloc[-1]
    ext_mult = 0.0
    if last_ib_close > ib_high:
        ext_mult = (last_ib_close - ib_mid) / ib_range
    elif last_ib_close < ib_low:
        ext_mult = (ib_mid - last_ib_close) / ib_range
    trend_strength = classify_trend_strength(ext_mult)

    session_context = {
        'ib_high': ib_high,
        'ib_low': ib_low,
        'ib_range': ib_range,
        'ib_mid': ib_mid,
        'day_type': 'neutral',
        'trend_strength': trend_strength.value,
        'session_date': session_str,
        'ib_bars': ib_df,  # critical for IB acceptance
        'ib_range_history': list(ib_range_history),
    }

    # Add indicator values from last IB bar
    last_ib = ib_df.iloc[-1]
    ib_width_cols = [
        'ib_width_class', 'ib_atr_ratio',
        'prior_va_poc', 'prior_va_vah', 'prior_va_val',
        'prior_va_width', 'prior_va_high', 'prior_va_low',
        'open_vs_va',
        'overnight_high', 'overnight_low',
        'asia_high', 'asia_low',
        'london_high', 'london_low',
    ]
    for col in ib_width_cols:
        if col in last_ib.index:
            val = last_ib[col]
            if not pd.isna(val) if not isinstance(val, str) else val is not None:
                session_context[col] = val

    # Add prior session context
    if prior_session_context:
        session_context.update(prior_session_context)

    # Confidence scorer
    confidence_scorer = DayTypeConfidenceScorer()
    atr = session_context.get('atr14', 0.0)
    confidence_scorer.on_session_start(ib_high, ib_low, ib_range, atr)

    # --- Init strategy ---
    strategy.on_session_start(
        session_date=session_str,
        ib_high=ib_high,
        ib_low=ib_low,
        ib_range=ib_range,
        session_context=session_context,
    )

    is_armed = strategy._setup_armed
    ib_accepted = strategy._acceptance_confirmed

    if is_armed:
        trace = {
            'date': session_str[:10],
            'direction': strategy._setup_direction,
            'vah': strategy._prior_vah,
            'val': strategy._prior_val,
            'open_vs_va': session_context.get('open_vs_va'),
            'limit': strategy._limit_price,
            'stop': strategy._stop_price,
            'ib_accepted': ib_accepted,
            'postib_accepted': False,
            'accept_bar': None,
            'accept_time': None,
            'filled': False,
            'fill_bar': None,
            'fill_time': None,
            'time_killed': False,
            'window_expired': False,
            'signal': None,
        }

        # --- Bar-by-bar (EXACT match of backtest engine) ---
        for bar_idx in range(len(post_ib_df)):
            bar = post_ib_df.iloc[bar_idx]
            timestamp = bar['timestamp']
            bar_time = timestamp.time() if hasattr(timestamp, 'time') else None

            # Update session_context (same as backtest engine)
            current_price = bar['close']
            if current_price > ib_high:
                ib_direction = 'BULL'
                ext = (current_price - ib_mid) / ib_range
            elif current_price < ib_low:
                ib_direction = 'BEAR'
                ext = (ib_mid - current_price) / ib_range
            else:
                ib_direction = 'INSIDE'
                ext = 0.0

            ts = classify_trend_strength(ext)
            dt = classify_day_type(ib_high, ib_low, current_price, ib_direction, ts)

            session_context['day_type'] = dt.value
            session_context['trend_strength'] = ts.value
            session_context['ib_direction'] = ib_direction
            session_context['current_price'] = current_price
            session_context['bar_time'] = bar_time

            day_confidence = confidence_scorer.update(bar, bar_idx)
            session_context['day_confidence'] = day_confidence
            session_context['b_day_confidence'] = day_confidence.b_day

            signal = strategy.on_bar(bar, bar_idx, session_context)

            # Track acceptance
            if strategy._acceptance_confirmed and not trace['postib_accepted'] and not trace['ib_accepted']:
                trace['postib_accepted'] = True
                trace['accept_bar'] = bar_idx
                trace['accept_time'] = str(timestamp)

            if signal is not None:
                signal_count += 1
                trace['filled'] = True
                trace['fill_bar'] = bar_idx
                trace['fill_time'] = str(timestamp)
                trace['signal'] = f"{signal.direction} @ {signal.entry_price:.1f}"

            # Check what killed it
            if strategy._triggered and not trace['filled']:
                if bar_time and bar_time >= ENTRY_CUTOFF:
                    trace['time_killed'] = True
                else:
                    trace['window_expired'] = True
                break

        armed_trace.append(trace)

    # Track IB range history
    if ib_range > 0:
        ib_range_history.append(float(ib_range))

    # Store prior session context
    last_bar = session_df.iloc[-1]
    prior_session_context = {
        'prior_close': last_bar['close'],
        'prior_vwap': last_bar.get('vwap', None),
        'prior_session_high': session_df['high'].max(),
        'prior_session_low': session_df['low'].min(),
        'pdh': session_df['high'].max(),
        'pdl': session_df['low'].min(),
    }

    strategy.on_session_end(session_str)


print()
print("=" * 70)
print(f"80P ENGINE DEBUG — {signal_count} signals from {len(armed_trace)} armed sessions")
print("=" * 70)

# Categorize outcomes
ib_acc = sum(1 for t in armed_trace if t['ib_accepted'])
post_acc = sum(1 for t in armed_trace if t['postib_accepted'])
filled = sum(1 for t in armed_trace if t['filled'])
time_killed = sum(1 for t in armed_trace if t['time_killed'])
window_expired = sum(1 for t in armed_trace if t['window_expired'])
no_accept = sum(1 for t in armed_trace if not t['ib_accepted'] and not t['postib_accepted'] and not t['filled'])

print(f"  Armed:            {len(armed_trace)}")
print(f"  IB accepted:      {ib_acc}")
print(f"  Post-IB accepted: {post_acc}")
print(f"  Filled (signal):  {filled}")
print(f"  Time killed:      {time_killed}")
print(f"  Window expired:   {window_expired}")
print(f"  No acceptance:    {no_accept}")

print(f"\n--- All armed sessions ---")
for t in armed_trace:
    status = ""
    if t['filled']:
        status = f"SIGNAL: {t['signal']}"
    elif t['ib_accepted']:
        if t['window_expired']:
            status = f"IB_ACC -> WINDOW_EXPIRED (acc_bar=0)"
        elif t['time_killed']:
            status = f"IB_ACC -> TIME_KILLED"
        else:
            status = f"IB_ACC -> NO_FILL"
    elif t['postib_accepted']:
        if t['window_expired']:
            status = f"POST_ACC@bar{t['accept_bar']} -> WINDOW_EXPIRED"
        elif t['time_killed']:
            status = f"POST_ACC@bar{t['accept_bar']} -> TIME_KILLED"
        else:
            status = f"POST_ACC@bar{t['accept_bar']} -> NO_FILL"
    else:
        status = "NO_ACCEPT"

    va_w = (t['vah'] - t['val']) if t['vah'] and t['val'] else 0
    print(f"  {t['date']} {t['direction']:5s} VA:{t['val']:.0f}-{t['vah']:.0f} (w={va_w:.0f}) "
          f"limit={t['limit']:.0f} -> {status}")
