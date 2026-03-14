"""Double Distribution Trend Continuation — V2 Bar-by-Bar Study"""
import json, os, glob, sys
import numpy as np
import pandas as pd
from datetime import time as dtime

sys.path.insert(0, 'packages/rockit-core/src')

# Load price data
csv_path = 'data/sessions/NQ_Volumetric_1.csv'
df = pd.read_csv(csv_path)
df['timestamp'] = pd.to_datetime(df['timestamp'])
df['session_date'] = df['timestamp'].dt.strftime('%Y-%m-%d')
print(f'Loaded {len(df)} bars, {df["session_date"].nunique()} sessions')

# Build snapshot index
snapshot_files = sorted(glob.glob('data/json_snapshots/deterministic_*.jsonl'))

dd_sessions = {}
for fpath in snapshot_files:
    date = os.path.basename(fpath).replace('deterministic_', '').replace('.jsonl', '')
    with open(fpath, encoding='utf-8') as f:
        for line in f:
            try:
                snap = json.loads(line.strip())
            except:
                continue
            et = snap.get('current_et_time', '')
            intraday = snap.get('intraday', {})
            tpo = intraday.get('tpo_profile', {})
            dist = tpo.get('distributions', {})

            if dist.get('count') == 2 and date not in dd_sessions:
                upper = dist.get('upper_poc')
                lower = dist.get('lower_poc')
                sep = dist.get('separation_level')
                if upper and lower and sep:
                    spread = abs(upper - lower)
                    dd_sessions[date] = {
                        'first_time': et,
                        'separation': sep,
                        'upper_poc': upper,
                        'lower_poc': lower,
                        'spread': spread,
                    }

MIN_SPREAD = 50
dd_meaningful = {k: v for k, v in dd_sessions.items() if v['spread'] >= MIN_SPREAD}
print(f'DD sessions with spread >= {MIN_SPREAD}pts: {len(dd_meaningful)}')


def simulate_trade(post_bars, direction, entry_price, stop_pts, target_pts):
    """Bar-by-bar simulation. Returns (pnl, exit_reason, bars_held)."""
    stop_price = entry_price - stop_pts if direction == 'LONG' else entry_price + stop_pts
    target_price = entry_price + target_pts if direction == 'LONG' else entry_price - target_pts

    for i in range(len(post_bars)):
        bar = post_bars.iloc[i]
        h, l = bar['high'], bar['low']

        if direction == 'LONG':
            # Check stop first (conservative)
            if l <= stop_price:
                return -stop_pts, 'STOP', i + 1
            if h >= target_price:
                return target_pts, 'TARGET', i + 1
        else:
            if h >= stop_price:
                return -stop_pts, 'STOP', i + 1
            if l <= target_price:
                return target_pts, 'TARGET', i + 1

    # EOD close
    last_close = float(post_bars.iloc[-1]['close'])
    if direction == 'LONG':
        pnl = last_close - entry_price
    else:
        pnl = entry_price - last_close
    return pnl, 'EOD', len(post_bars)


def run_backtest(rdf_input, stop_pts, target_pts, point_value=20):
    """Run backtest across all signals."""
    trades = []
    for _, row in rdf_input.iterrows():
        session_df = df[df['session_date'] == row['date']].copy()
        times = session_df['timestamp'].dt.time
        rth = session_df[(times >= dtime(9, 30)) & (times <= dtime(16, 0))].copy()

        detect_time = row['detect_time']
        try:
            detect_h, detect_m = int(detect_time.split(':')[0]), int(detect_time.split(':')[1])
        except:
            continue
        detect_dt = dtime(detect_h, detect_m)
        detect_bars = rth[rth['timestamp'].dt.time >= detect_dt]
        if len(detect_bars) < 2:
            continue

        entry_price = float(rth.loc[detect_bars.index[0], 'close'])
        post_bars = rth.loc[detect_bars.index[0]:]

        pnl_pts, reason, bars_held = simulate_trade(
            post_bars, row['direction'], entry_price, stop_pts, target_pts
        )

        trades.append({
            'date': row['date'],
            'direction': row['direction'],
            'entry': entry_price,
            'pnl_pts': pnl_pts,
            'pnl_dollar': pnl_pts * point_value,
            'reason': reason,
            'bars_held': bars_held,
            'spread': row['spread'],
        })

    return pd.DataFrame(trades)


# Build signal list
signals = []
for date, dd in sorted(dd_meaningful.items()):
    session_df = df[df['session_date'] == date]
    if len(session_df) == 0:
        continue
    times = session_df['timestamp'].dt.time
    rth = session_df[(times >= dtime(9, 30)) & (times <= dtime(16, 0))]
    if len(rth) < 60:
        continue

    detect_time = dd['first_time']
    try:
        detect_h, detect_m = int(detect_time.split(':')[0]), int(detect_time.split(':')[1])
    except:
        continue

    detect_dt = dtime(detect_h, detect_m)
    detect_bars = rth[rth['timestamp'].dt.time >= detect_dt]
    if len(detect_bars) == 0:
        continue

    entry_price = float(rth.loc[detect_bars.index[0], 'close'])
    sep = dd['separation']

    if entry_price > sep:
        direction = 'LONG'
    else:
        direction = 'SHORT'

    signals.append({
        'date': date,
        'direction': direction,
        'detect_time': detect_time,
        'spread': dd['spread'],
        'separation': sep,
        'entry_price': entry_price,
    })

sig_df = pd.DataFrame(signals)
print(f'Total signals: {len(sig_df)}')

# Filter: early detection only (<= 10:30)
sig_early = sig_df[sig_df.detect_time <= '10:30'].copy()
print(f'Early signals (<= 10:30): {len(sig_early)}')

# Filter: spread >= 75
sig_75 = sig_df[sig_df.spread >= 75].copy()
print(f'Spread >= 75: {len(sig_75)}')

# Combined: early + spread >= 75
sig_best = sig_df[(sig_df.detect_time <= '10:30') & (sig_df.spread >= 75)].copy()
print(f'Early + spread >= 75: {len(sig_best)}')

print()
print('=' * 80)
print('BAR-BY-BAR BACKTEST RESULTS')
print('=' * 80)

for label, sig_set in [
    ('ALL signals (spread >= 50)', sig_df),
    ('Early only (<= 10:30)', sig_early),
    ('Spread >= 75', sig_75),
    ('Early + Spread >= 75', sig_best),
]:
    print(f'\n{"=" * 60}')
    print(f'  {label} ({len(sig_set)} trades)')
    print(f'{"=" * 60}')
    print(f'{"Stop":>6} {"Tgt":>6} | {"Trades":>6} {"Wins":>5} {"WR":>7} {"PF":>7} {"Net$":>10} {"Avg$/trade":>10} {"EOD":>4}')
    print('-' * 75)

    for stop_pts in [25, 30, 40, 50]:
        for target_pts in [50, 75, 100, 150]:
            trades = run_backtest(sig_set, stop_pts, target_pts)
            if len(trades) == 0:
                continue

            wins = trades[trades.pnl_dollar > 0]
            losses = trades[trades.pnl_dollar <= 0]
            wr = len(wins) / len(trades) * 100
            gross_win = wins.pnl_dollar.sum() if len(wins) > 0 else 0
            gross_loss = abs(losses.pnl_dollar.sum()) if len(losses) > 0 else 0
            pf = gross_win / gross_loss if gross_loss > 0 else float('inf')
            net = trades.pnl_dollar.sum()
            avg = net / len(trades)
            eod = len(trades[trades.reason == 'EOD'])

            print(f'{stop_pts:>5}pt {target_pts:>5}pt | {len(trades):>6} {len(wins):>5} {wr:>6.1f}% {pf:>7.2f} {net:>10,.0f} {avg:>10,.0f} {eod:>4}')

# Final detailed breakdown of best config
print('\n' + '=' * 80)
print('DETAILED: Early + Spread >= 75, Stop=30, Target=75')
print('=' * 80)
if len(sig_best) > 0:
    trades = run_backtest(sig_best, 30, 75)
    wins = trades[trades.pnl_dollar > 0]
    losses = trades[trades.pnl_dollar <= 0]
    print(f'Trades: {len(trades)}')
    print(f'Wins: {len(wins)}, Losses: {len(losses)}')
    print(f'WR: {100*len(wins)/len(trades):.1f}%')
    print(f'Gross Win: ${wins.pnl_dollar.sum():,.0f}')
    print(f'Gross Loss: ${losses.pnl_dollar.sum():,.0f}')
    pf = wins.pnl_dollar.sum() / abs(losses.pnl_dollar.sum()) if losses.pnl_dollar.sum() != 0 else float('inf')
    print(f'PF: {pf:.2f}')
    print(f'Net: ${trades.pnl_dollar.sum():,.0f}')
    print(f'Avg bars held: {trades.bars_held.mean():.0f}')
    print(f'Direction: SHORT={len(trades[trades.direction=="SHORT"])}, LONG={len(trades[trades.direction=="LONG"])}')

    # By direction
    for d in ['SHORT', 'LONG']:
        sub = trades[trades.direction == d]
        if len(sub) == 0:
            continue
        sw = sub[sub.pnl_dollar > 0]
        sl = sub[sub.pnl_dollar <= 0]
        wr = 100 * len(sw) / len(sub) if len(sub) > 0 else 0
        net = sub.pnl_dollar.sum()
        gw = sw.pnl_dollar.sum() if len(sw) > 0 else 0
        gl = abs(sl.pnl_dollar.sum()) if len(sl) > 0 else 0
        pf = gw / gl if gl > 0 else float('inf')
        print(f'  {d}: {len(sub)} trades, {wr:.1f}% WR, PF {pf:.2f}, ${net:,.0f}')

    # Monthly distribution
    trades['month'] = pd.to_datetime(trades['date']).dt.to_period('M')
    monthly = trades.groupby('month').agg(
        n=('pnl_dollar', 'count'),
        pnl=('pnl_dollar', 'sum'),
    )
    print('\nMonthly P&L:')
    for m, row in monthly.iterrows():
        print(f'  {m}: {row.n:.0f} trades, ${row.pnl:,.0f}')
