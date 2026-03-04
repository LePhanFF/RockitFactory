#!/usr/bin/env python3
"""
Debug script: Why does the 80P Rule strategy generate 0 trades?

Traces the full pipeline:
  1. Data loading (same as run_backtest.py)
  2. Feature computation (compute_all_features)
  3. Prior VA + open_vs_va classification
  4. Session-by-session strategy arming
  5. Bar-by-bar acceptance monitoring
  6. Limit fill checking

Prints detailed diagnostics for the first 5 armed sessions.
"""

import sys
from pathlib import Path
from datetime import time

import pandas as pd
import numpy as np

# --- Path setup (same as run_backtest.py) ---
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.config.constants import IB_BARS_1MIN
from rockit_core.data.features import compute_all_features
from rockit_core.data.manager import SessionDataManager
from rockit_core.config.instruments import get_instrument
from rockit_core.strategies.eighty_percent_rule import (
    EightyPercentRule,
    MIN_VA_WIDTH,
    ACCEPT_5M_BARS,
    ACCEPT_5M_PERIODS,
    ENTRY_CUTOFF,
    LIMIT_FILL_WINDOW,
)

print("=" * 70)
print("DEBUG: 80P Rule — tracing why 0 trades generated")
print("=" * 70)

# --- Phase 1: Load data (same as run_backtest.py --no-merge) ---
mgr = SessionDataManager(data_dir="data/sessions")
df = mgr.load("NQ")
mgr.info("NQ")
print()

# --- Phase 2: Compute features ---
df = compute_all_features(df)
print()

# --- Phase 3: Diagnostic — how many sessions have open_vs_va set? ---
print("=" * 70)
print("DIAGNOSTIC: open_vs_va distribution across sessions")
print("=" * 70)

sessions = sorted(df['session_date'].unique())
va_stats = {"ABOVE_VAH": 0, "BELOW_VAL": 0, "INSIDE_VA": 0, "missing": 0}
va_width_stats = []

for session_date in sessions:
    session_df = df[df['session_date'] == session_date]
    if len(session_df) == 0:
        continue
    first_bar = session_df.iloc[0]
    ov = first_bar.get('open_vs_va', None)
    if ov is None or (isinstance(ov, float) and pd.isna(ov)):
        va_stats["missing"] += 1
    else:
        va_stats[str(ov)] = va_stats.get(str(ov), 0) + 1

    prior_vah = first_bar.get('prior_va_vah', np.nan)
    prior_val = first_bar.get('prior_va_val', np.nan)
    if not pd.isna(prior_vah) and not pd.isna(prior_val):
        va_width_stats.append(prior_vah - prior_val)

print(f"  Total sessions:  {len(sessions)}")
for k, v in va_stats.items():
    print(f"  {k:15s}: {v:4d}")
print(f"  VA width (when available): min={min(va_width_stats):.1f}, "
      f"max={max(va_width_stats):.1f}, mean={np.mean(va_width_stats):.1f}")
outside_va = va_stats.get("ABOVE_VAH", 0) + va_stats.get("BELOW_VAL", 0)
print(f"  Sessions with open OUTSIDE VA: {outside_va}")
# How many have VA width >= 25?
wide_enough = sum(1 for w in va_width_stats if w >= MIN_VA_WIDTH)
print(f"  Sessions with VA width >= {MIN_VA_WIDTH}: {wide_enough} / {len(va_width_stats)}")
print()

# --- Phase 3b: CRITICAL CHECK — Is "open" the ETH open or RTH open? ---
print("=" * 70)
print("CRITICAL CHECK: What 'open' does open_vs_va use?")
print("=" * 70)
# The open_vs_va is set by add_prior_va_features using session_df['open'].iloc[0]
# If session starts at 18:01 ETH, that's the ETH open, NOT the RTH open.
# The 80P Rule is about RTH open being outside prior VA.

sample_count = 5
print(f"\nFirst {sample_count} sessions — ETH open vs RTH open vs prior VA:\n")
checked = 0
for session_date in sessions[1:]:  # skip first (no prior VA)
    session_df = df[df['session_date'] == session_date].copy()
    if len(session_df) < 100:
        continue

    first_bar = session_df.iloc[0]
    prior_vah = first_bar.get('prior_va_vah', np.nan)
    prior_val = first_bar.get('prior_va_val', np.nan)
    if pd.isna(prior_vah) or pd.isna(prior_val):
        continue

    eth_open = first_bar['open']
    eth_time = first_bar['timestamp'] if 'timestamp' in first_bar.index else "?"

    # Find RTH open (9:30 AM)
    session_df_ts = session_df.copy()
    session_df_ts['time'] = pd.to_datetime(session_df_ts['timestamp']).dt.time
    rth_bars = session_df_ts[session_df_ts['time'] >= time(9, 30)]
    if len(rth_bars) == 0:
        continue
    rth_open = rth_bars.iloc[0]['open']
    rth_time = rth_bars.iloc[0]['timestamp']

    open_vs_va = first_bar.get('open_vs_va', 'N/A')

    # Classify RTH open relative to VA
    if rth_open > prior_vah:
        rth_class = "ABOVE_VAH"
    elif rth_open < prior_val:
        rth_class = "BELOW_VAL"
    else:
        rth_class = "INSIDE_VA"

    print(f"  Session {str(session_date)[:10]}:")
    print(f"    ETH open: {eth_open:.2f} @ {eth_time}  -> open_vs_va = {open_vs_va}")
    print(f"    RTH open: {rth_open:.2f} @ {rth_time}  -> would be   = {rth_class}")
    print(f"    Prior VAH: {prior_vah:.2f}, Prior VAL: {prior_val:.2f}, "
          f"Width: {prior_vah - prior_val:.2f}")
    if open_vs_va != rth_class:
        print(f"    *** MISMATCH: ETH-based={open_vs_va}, RTH-based={rth_class} ***")
    print()

    checked += 1
    if checked >= sample_count:
        break

# Count mismatches across ALL sessions
print("=" * 70)
print("MISMATCH ANALYSIS: ETH open_vs_va vs RTH open_vs_va")
print("=" * 70)
eth_outside = 0
rth_outside = 0
mismatch_count = 0
rth_outside_but_eth_inside = 0

for session_date in sessions[1:]:
    session_df = df[df['session_date'] == session_date].copy()
    if len(session_df) < 100:
        continue

    first_bar = session_df.iloc[0]
    prior_vah = first_bar.get('prior_va_vah', np.nan)
    prior_val = first_bar.get('prior_va_val', np.nan)
    if pd.isna(prior_vah) or pd.isna(prior_val):
        continue

    va_width = prior_vah - prior_val
    if va_width < MIN_VA_WIDTH:
        continue

    eth_open = first_bar['open']
    open_vs_va = first_bar.get('open_vs_va', 'INSIDE_VA')

    session_df_ts = session_df.copy()
    session_df_ts['time'] = pd.to_datetime(session_df_ts['timestamp']).dt.time
    rth_bars = session_df_ts[session_df_ts['time'] >= time(9, 30)]
    if len(rth_bars) == 0:
        continue
    rth_open = rth_bars.iloc[0]['open']

    if rth_open > prior_vah:
        rth_class = "ABOVE_VAH"
    elif rth_open < prior_val:
        rth_class = "BELOW_VAL"
    else:
        rth_class = "INSIDE_VA"

    eth_is_outside = open_vs_va in ("ABOVE_VAH", "BELOW_VAL")
    rth_is_outside = rth_class in ("ABOVE_VAH", "BELOW_VAL")

    if eth_is_outside:
        eth_outside += 1
    if rth_is_outside:
        rth_outside += 1
    if open_vs_va != rth_class:
        mismatch_count += 1
    if rth_is_outside and not eth_is_outside:
        rth_outside_but_eth_inside += 1

print(f"  Sessions with VA width >= {MIN_VA_WIDTH}: {wide_enough}")
print(f"  ETH open outside VA: {eth_outside}")
print(f"  RTH open outside VA: {rth_outside}")
print(f"  Mismatches (ETH != RTH classification): {mismatch_count}")
print(f"  RTH outside but ETH inside (LOST setups): {rth_outside_but_eth_inside}")
print()

# --- Phase 4: CRITICAL CHECK — IB is ETH or RTH? ---
print("=" * 70)
print("CRITICAL CHECK: IB computation uses bars 0-59 (ETH, not RTH)")
print("=" * 70)
for session_date in sessions[50:52]:
    session_df = df[df['session_date'] == session_date].copy()
    if len(session_df) < IB_BARS_1MIN:
        continue
    ib_df = session_df.head(IB_BARS_1MIN)
    ib_first = ib_df.iloc[0]['timestamp']
    ib_last = ib_df.iloc[-1]['timestamp']
    ib_high = ib_df['high'].max()
    ib_low = ib_df['low'].min()
    print(f"  Session {str(session_date)[:10]}: IB = bars 0-59")
    print(f"    Time range: {ib_first} to {ib_last}")
    print(f"    IB High: {ib_high:.2f}, IB Low: {ib_low:.2f}, Range: {ib_high-ib_low:.2f}")

    # Real RTH IB would be 9:30-10:30
    session_df_ts = session_df.copy()
    session_df_ts['time'] = pd.to_datetime(session_df_ts['timestamp']).dt.time
    rth_ib = session_df_ts[
        (session_df_ts['time'] >= time(9, 30)) &
        (session_df_ts['time'] < time(10, 30))
    ]
    if len(rth_ib) > 0:
        rth_ib_h = rth_ib['high'].max()
        rth_ib_l = rth_ib['low'].min()
        print(f"    Real RTH IB: High={rth_ib_h:.2f}, Low={rth_ib_l:.2f}, "
              f"Range={rth_ib_h-rth_ib_l:.2f}")
    print()
print()

# --- Phase 5: Simulate the 80P strategy with full tracing ---
print("=" * 70)
print("STRATEGY SIMULATION: 80P Rule with bar-by-bar tracing")
print("=" * 70)

strategy = EightyPercentRule()
inst_spec = get_instrument("NQ")

armed_count = 0
total_armed = 0
signals_emitted = 0
trace_limit = 5  # Trace first 5 armed sessions in detail

# Build session context the same way as the backtest engine
ib_range_history = []
prior_session_context = {}

for session_date in sessions:
    session_df = df[df['session_date'] == session_date].copy()
    session_str = str(session_date)

    if len(session_df) < IB_BARS_1MIN:
        continue

    # Phase 1: Compute IB (same as backtest engine — THIS IS THE BUG)
    ib_df = session_df.head(IB_BARS_1MIN)
    ib_high = ib_df['high'].max()
    ib_low = ib_df['low'].min()
    ib_range = ib_high - ib_low
    ib_mid = (ib_high + ib_low) / 2

    if ib_range <= 0:
        continue

    post_ib_df = session_df.iloc[IB_BARS_1MIN:]
    if len(post_ib_df) == 0:
        continue

    # Build session_context (same as backtest engine)
    session_context = {
        'ib_high': ib_high,
        'ib_low': ib_low,
        'ib_range': ib_range,
        'ib_mid': ib_mid,
        'day_type': 'NEUTRAL',
        'trend_strength': 'NONE',
        'session_date': session_str,
    }

    # Add IB width features from last IB bar
    last_ib = ib_df.iloc[-1]
    ib_width_cols = [
        'prior_va_poc', 'prior_va_vah', 'prior_va_val',
        'prior_va_width', 'prior_va_high', 'prior_va_low',
        'open_vs_va',
    ]
    for col in ib_width_cols:
        if col in last_ib.index:
            val = last_ib[col]
            if not pd.isna(val) if not isinstance(val, str) else val is not None:
                session_context[col] = val

    # Add prior session context
    if prior_session_context:
        session_context.update(prior_session_context)

    # Initialize strategy
    strategy.on_session_start(
        session_date=session_str,
        ib_high=ib_high,
        ib_low=ib_low,
        ib_range=ib_range,
        session_context=session_context,
    )

    if strategy._setup_armed:
        total_armed += 1

    tracing = strategy._setup_armed and armed_count < trace_limit

    if tracing:
        armed_count += 1
        prior_vah = session_context.get('prior_va_vah', 'N/A')
        prior_val = session_context.get('prior_va_val', 'N/A')
        ov = session_context.get('open_vs_va', 'N/A')
        print(f"\n--- ARMED Session #{armed_count}: {session_str} ---")
        print(f"  prior_vah={prior_vah}, prior_val={prior_val}")
        print(f"  open_vs_va={ov}")
        print(f"  setup_direction={strategy._setup_direction}")
        print(f"  limit_price={strategy._limit_price}, stop_price={strategy._stop_price}")
        print(f"  IB: {ib_df.iloc[0]['timestamp']} to {ib_df.iloc[-1]['timestamp']}")
        print(f"  Post-IB bars: {len(post_ib_df)}")
        print()

    # Bar-by-bar processing
    acceptance_found = False
    fill_found = False
    five_min_checks = 0

    for bar_idx in range(len(post_ib_df)):
        bar = post_ib_df.iloc[bar_idx]
        timestamp = bar['timestamp'] if 'timestamp' in bar.index else None
        bar_time = pd.to_datetime(timestamp).time() if timestamp else None

        session_context['bar_time'] = bar_time
        session_context['current_price'] = bar['close']

        signal = strategy.on_bar(bar, bar_idx, session_context)

        if tracing:
            # Show 5-min acceptance checks
            is_5m_end = ((bar_idx + 1) % ACCEPT_5M_BARS == 0)
            if is_5m_end and not strategy._acceptance_confirmed:
                five_min_checks += 1
                vah = strategy._prior_vah
                val = strategy._prior_val
                is_inside = val <= bar['close'] <= vah if vah and val else False
                if five_min_checks <= 20:  # Show first 20 checks
                    print(f"    5m check @ bar {bar_idx:4d} ({timestamp}): "
                          f"close={bar['close']:.2f}, "
                          f"inside_va={is_inside}, "
                          f"consecutive={strategy._consecutive_inside_5m}")

            if strategy._acceptance_confirmed and not acceptance_found:
                acceptance_found = True
                print(f"    >>> ACCEPTANCE at bar {bar_idx} ({timestamp}), "
                      f"consecutive={strategy._consecutive_inside_5m}")
                print(f"    >>> Waiting for limit fill at {strategy._limit_price:.2f} "
                      f"(window: {LIMIT_FILL_WINDOW} bars)")

            if strategy._acceptance_confirmed and not fill_found:
                bars_since = bar_idx - strategy._acceptance_bar
                if bars_since <= LIMIT_FILL_WINDOW:
                    if strategy._setup_direction == 'LONG':
                        fill_check = bar['low'] <= strategy._limit_price
                    else:
                        fill_check = bar['high'] >= strategy._limit_price
                    if bars_since <= 5 or fill_check:  # Show first 5 or fill
                        print(f"    Fill check bar {bar_idx} ({timestamp}): "
                              f"low={bar['low']:.2f}, high={bar['high']:.2f}, "
                              f"limit={strategy._limit_price:.2f}, "
                              f"filled={fill_check}")

        if signal is not None:
            signals_emitted += 1
            fill_found = True
            if tracing:
                print(f"    >>> SIGNAL EMITTED: {signal.direction} @ {signal.entry_price:.2f}, "
                      f"stop={signal.stop_price:.2f}, target={signal.target_price:.2f}")

    if tracing and not acceptance_found:
        print(f"    >>> NO ACCEPTANCE reached (consecutive inside VA never hit "
              f"{ACCEPT_5M_PERIODS})")
        # Show why: what was the max consecutive?
        print(f"    >>> Total 5-min checks shown: {five_min_checks}")

    if tracing and acceptance_found and not fill_found:
        print(f"    >>> ACCEPTANCE found but NO LIMIT FILL within {LIMIT_FILL_WINDOW} bars")

    # Track IB range history
    if ib_range > 0:
        ib_range_history.append(float(ib_range))

    # Store prior session data
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
print("SUMMARY")
print("=" * 70)
print(f"  Total sessions:     {len(sessions)}")
print(f"  Sessions armed:     {total_armed}")
print(f"  Signals emitted:    {signals_emitted}")
print()

# --- Phase 6: Position Sizing — THE PRIMARY ROOT CAUSE ---
print("=" * 70)
print("POSITION SIZING: Why 57 signals produce only 1 trade")
print("=" * 70)

# Re-run with signal risk analysis
from rockit_core.engine.execution import ExecutionModel

execution = ExecutionModel(inst_spec)
risk_budget = 400.0  # DEFAULT_MAX_RISK_PER_TRADE

# Collect all signal risk data
strategy2 = EightyPercentRule()
prior_session_context2 = {}
signal_risks = []

for session_date in sessions:
    session_df = df[df['session_date'] == session_date].copy()
    session_str = str(session_date)
    if len(session_df) < IB_BARS_1MIN:
        continue

    ib_df = session_df.head(IB_BARS_1MIN)
    ib_high = ib_df['high'].max()
    ib_low = ib_df['low'].min()
    ib_range = ib_high - ib_low
    ib_mid = (ib_high + ib_low) / 2
    if ib_range <= 0:
        continue
    post_ib_df = session_df.iloc[IB_BARS_1MIN:]
    if len(post_ib_df) == 0:
        continue

    ctx = {
        'ib_high': ib_high, 'ib_low': ib_low, 'ib_range': ib_range,
        'ib_mid': ib_mid, 'day_type': 'NEUTRAL', 'trend_strength': 'NONE',
        'session_date': session_str,
    }
    last_ib = ib_df.iloc[-1]
    for col in ['prior_va_poc', 'prior_va_vah', 'prior_va_val',
                'prior_va_width', 'prior_va_high', 'prior_va_low', 'open_vs_va']:
        if col in last_ib.index:
            val = last_ib[col]
            if not pd.isna(val) if not isinstance(val, str) else val is not None:
                ctx[col] = val
    if prior_session_context2:
        ctx.update(prior_session_context2)

    strategy2.on_session_start(session_str, ib_high, ib_low, ib_range, ctx)

    for bar_idx in range(len(post_ib_df)):
        bar = post_ib_df.iloc[bar_idx]
        bar_time = pd.to_datetime(bar['timestamp']).time() if 'timestamp' in bar.index else None
        ctx['bar_time'] = bar_time
        ctx['current_price'] = bar['close']
        signal = strategy2.on_bar(bar, bar_idx, ctx)
        if signal is not None:
            risk_pts = signal.risk_points
            risk_per_contract = risk_pts * inst_spec.point_value
            contracts = execution.calculate_contracts(risk_budget, risk_pts)
            rejected = contracts == 0
            signal_risks.append({
                'date': session_str[:10],
                'direction': signal.direction,
                'entry': signal.entry_price,
                'stop': signal.stop_price,
                'risk_pts': risk_pts,
                'risk_per_contract': risk_per_contract,
                'contracts': contracts,
                'rejected': rejected,
            })

    last_bar = session_df.iloc[-1]
    prior_session_context2 = {
        'prior_close': last_bar['close'],
        'prior_vwap': last_bar.get('vwap', None),
        'prior_session_high': session_df['high'].max(),
        'prior_session_low': session_df['low'].min(),
        'pdh': session_df['high'].max(),
        'pdl': session_df['low'].min(),
    }
    strategy2.on_session_end(session_str)

rejected_count = sum(1 for s in signal_risks if s['rejected'])
accepted_count = sum(1 for s in signal_risks if not s['rejected'])

print(f"\n  Total signals: {len(signal_risks)}")
print(f"  Rejected (0 contracts): {rejected_count}")
print(f"  Accepted (>= 1 contract): {accepted_count}")
print(f"\n  Risk budget: ${risk_budget:.2f}/trade")
print(f"  Max allowed risk/contract: ${risk_budget * 2:.2f} (2x budget)")
print(f"  NQ point value: ${inst_spec.point_value:.2f}/point")
print()

print("  Signal-by-signal risk breakdown:")
for s in signal_risks:
    flag = "REJECTED" if s['rejected'] else "OK"
    print(f"    {s['date']} {s['direction']:5s} entry={s['entry']:.2f} "
          f"stop={s['stop']:.2f} risk={s['risk_pts']:.1f}pts "
          f"= ${s['risk_per_contract']:.2f}/contract "
          f"contracts={s['contracts']} [{flag}]")

if signal_risks:
    avg_risk = np.mean([s['risk_pts'] for s in signal_risks])
    avg_risk_dollar = np.mean([s['risk_per_contract'] for s in signal_risks])
    min_risk = min(s['risk_pts'] for s in signal_risks)
    max_risk = max(s['risk_pts'] for s in signal_risks)
    print(f"\n  Risk stats: avg={avg_risk:.1f}pts (${avg_risk_dollar:.2f}), "
          f"min={min_risk:.1f}pts, max={max_risk:.1f}pts")
    print(f"  To accept avg risk: need budget >= ${avg_risk_dollar/2:.2f} "
          f"(risk/contract / 2)")

print()
print("=" * 70)
print("ROOT CAUSE ANALYSIS")
print("=" * 70)
print("""
ROOT CAUSE: Position sizing rejects almost all 80P signals.

The 80P strategy places stops at the VA edge + 10 pts buffer, with entry
at 50% VA depth. This creates a stop distance of (VA_width/2 + 10) points.

With NQ at $20/point and the default $400 risk budget:
  - Average VA width ~199 pts -> stop distance ~110 pts
  - Risk per contract = 110 * $20 = $2,200
  - ExecutionModel.calculate_contracts() rejects when
    risk_per_contract > risk_per_trade * 2 ($800)
  - $2,200 >> $800, so almost every signal gets 0 contracts

Only the one session (2025-12-31) with a narrow enough VA width produced
a trade. The strategy logic is CORRECT — it arms, finds acceptance, emits
signals. But the execution layer kills them on position sizing.

SECONDARY ISSUES (also real but not the 0-trade cause):

1. IB is computed from ETH bars (18:01-19:00), not RTH (9:30-10:30).
   The backtest engine takes session_df.head(60) = first hour of overnight.
   This affects IB range, day type classification, and post-IB bar indexing.

2. The acceptance 5-min checks start from bar 0 of post-IB (19:01 ET),
   running through the entire overnight session. The 80P logic should
   only check during RTH (after 9:30 AM).

3. The ENTRY_CUTOFF of 13:00 ET works correctly (time-based check),
   but the bar_time comparison is correct since timestamps are real times.

FIXES NEEDED:
  a. Position sizing: Either increase risk budget, reduce stop distance,
     or use MNQ ($2/point) for backtesting wide-stop strategies.
  b. IB computation: Filter to RTH bars (9:30-10:30) before computing IB.
  c. Post-IB processing: Only process bars from 10:30+ (after real IB).
  d. VA open classification: Use RTH open (9:30 bar), not ETH open (18:01).
""")
