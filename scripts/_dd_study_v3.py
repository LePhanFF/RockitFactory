"""Double Distribution Trend Continuation — V3 Pullback Entry Study

Instead of entering at detection close, enter on PULLBACK to separation level.
This gives better risk/reward: stop below separation, target = active POC.
"""
import json, os, glob, sys
import numpy as np
import pandas as pd
from datetime import time as dtime

sys.path.insert(0, 'packages/rockit-core/src')

csv_path = 'data/sessions/NQ_Volumetric_1.csv'
df = pd.read_csv(csv_path)
df['timestamp'] = pd.to_datetime(df['timestamp'])
df['session_date'] = df['timestamp'].dt.strftime('%Y-%m-%d')
print(f'Loaded {len(df)} bars, {df["session_date"].nunique()} sessions')

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


def simulate_pullback(post_bars, direction, entry_price, stop_pts, target_price, max_wait=60):
    """
    Wait for pullback to entry_price, then trade with fixed stop and target.
    Returns (filled, pnl, exit_reason, bars_held).
    """
    # Phase 1: Wait for pullback fill
    fill_idx = None
    for i in range(min(max_wait, len(post_bars))):
        bar = post_bars.iloc[i]
        if direction == 'LONG' and bar['low'] <= entry_price:
            fill_idx = i
            break
        elif direction == 'SHORT' and bar['high'] >= entry_price:
            fill_idx = i
            break

    if fill_idx is None:
        return False, 0, 'NO_FILL', 0

    # Phase 2: Manage trade
    stop_price = entry_price - stop_pts if direction == 'LONG' else entry_price + stop_pts
    remaining = post_bars.iloc[fill_idx:]

    for i in range(len(remaining)):
        bar = remaining.iloc[i]
        h, l = bar['high'], bar['low']

        if direction == 'LONG':
            if l <= stop_price:
                return True, -stop_pts, 'STOP', i + 1
            if h >= target_price:
                return True, target_price - entry_price, 'TARGET', i + 1
        else:
            if h >= stop_price:
                return True, -stop_pts, 'STOP', i + 1
            if l <= target_price:
                return True, entry_price - target_price, 'TARGET', i + 1

    # EOD
    last_close = float(remaining.iloc[-1]['close'])
    pnl = (last_close - entry_price) if direction == 'LONG' else (entry_price - last_close)
    return True, pnl, 'EOD', len(remaining)


# Study configurations
POINT_VALUE = 20
results_all = []

for date, dd in sorted(dd_sessions.items()):
    if dd['spread'] < 50:
        continue

    session_df = df[df['session_date'] == date]
    if len(session_df) == 0:
        continue
    times = session_df['timestamp'].dt.time
    rth = session_df[(times >= dtime(9, 30)) & (times <= dtime(16, 0))].copy()
    if len(rth) < 60:
        continue

    detect_time = dd['first_time']
    try:
        detect_h, detect_m = int(detect_time.split(':')[0]), int(detect_time.split(':')[1])
    except:
        continue

    detect_dt = dtime(detect_h, detect_m)
    detect_bars = rth[rth['timestamp'].dt.time >= detect_dt]
    if len(detect_bars) < 2:
        continue

    entry_close = float(rth.loc[detect_bars.index[0], 'close'])
    sep = dd['separation']
    upper_poc = dd['upper_poc']
    lower_poc = dd['lower_poc']

    if entry_close > sep:
        direction = 'LONG'
        target_poc = upper_poc
    else:
        direction = 'SHORT'
        target_poc = lower_poc

    post_bars = rth.loc[detect_bars.index[0]:]

    results_all.append({
        'date': date,
        'direction': direction,
        'detect_time': detect_time,
        'spread': dd['spread'],
        'separation': sep,
        'upper_poc': upper_poc,
        'lower_poc': lower_poc,
        'target_poc': target_poc,
        'entry_close': entry_close,
        'post_bars_idx': detect_bars.index[0],
    })

rdf = pd.DataFrame(results_all)
print(f'Total DD signals (spread >= 50): {len(rdf)}')

# Filter
early = rdf[rdf.detect_time <= '10:30']
print(f'Early (<= 10:30): {len(early)}')

print()
print('=' * 90)
print('PULLBACK TO SEPARATION ENTRY')
print('=' * 90)

for label, sig_set in [
    ('ALL (spread >= 50)', rdf),
    ('Early (<= 10:30)', early),
    ('Early + spread >= 75', rdf[(rdf.detect_time <= '10:30') & (rdf.spread >= 75)]),
    ('Early + spread >= 100', rdf[(rdf.detect_time <= '10:30') & (rdf.spread >= 100)]),
]:
    print(f'\n{"=" * 70}')
    print(f'  {label} ({len(sig_set)} signals)')
    print(f'{"=" * 70}')
    print(f'{"Stop":>6} {"Entry":>12} {"Target":>12} | {"Fills":>5} {"Wins":>5} {"WR":>7} {"PF":>7} {"Net$":>10} {"Avg$":>8} {"EOD":>4}')
    print('-' * 85)

    for stop_pts in [25, 30, 40, 50]:
        for target_mode in ['poc', '50pt', '75pt', '100pt', '150pt']:
            trades = []
            for _, row in sig_set.iterrows():
                session_df = df[df['session_date'] == row['date']]
                times = session_df['timestamp'].dt.time
                rth = session_df[(times >= dtime(9, 30)) & (times <= dtime(16, 0))].copy()
                post_bars = rth.loc[row['post_bars_idx']:]
                if len(post_bars) < 2:
                    continue

                entry_price = row['separation']
                if target_mode == 'poc':
                    target_price = row['target_poc']
                else:
                    pts = int(target_mode.replace('pt', ''))
                    target_price = entry_price + pts if row['direction'] == 'LONG' else entry_price - pts

                filled, pnl, reason, bars = simulate_pullback(
                    post_bars, row['direction'], entry_price, stop_pts, target_price
                )
                if filled:
                    trades.append({
                        'date': row['date'],
                        'pnl_pts': pnl,
                        'pnl_dollar': pnl * POINT_VALUE,
                        'reason': reason,
                        'bars': bars,
                        'direction': row['direction'],
                    })

            if not trades:
                continue
            tdf = pd.DataFrame(trades)
            wins = tdf[tdf.pnl_dollar > 0]
            losses = tdf[tdf.pnl_dollar <= 0]
            wr = 100 * len(wins) / len(tdf) if len(tdf) > 0 else 0
            gw = wins.pnl_dollar.sum() if len(wins) > 0 else 0
            gl = abs(losses.pnl_dollar.sum()) if len(losses) > 0 else 0
            pf = gw / gl if gl > 0 else float('inf')
            net = tdf.pnl_dollar.sum()
            avg = net / len(tdf)
            eod = len(tdf[tdf.reason == 'EOD'])

            print(f'{stop_pts:>5}pt {"sep":>12} {target_mode:>12} | {len(tdf):>5} {len(wins):>5} {wr:>6.1f}% {pf:>7.2f} {net:>10,.0f} {avg:>8,.0f} {eod:>4}')


# === ALTERNATIVE: Entry at detection close, with wider stops ===
print()
print('=' * 90)
print('ENTRY AT DETECTION CLOSE (wider stops, target = POC)')
print('=' * 90)

for label, sig_set in [
    ('Early (<= 10:30)', early),
    ('Early + spread >= 75', rdf[(rdf.detect_time <= '10:30') & (rdf.spread >= 75)]),
]:
    print(f'\n  {label} ({len(sig_set)} signals)')
    print(f'{"Stop":>6} {"Target":>12} | {"Trades":>6} {"Wins":>5} {"WR":>7} {"PF":>7} {"Net$":>10} {"Avg$":>8}')
    print('-' * 70)

    for stop_pts in [50, 60, 75]:
        for target_mode in ['poc', '100pt', '150pt']:
            trades = []
            for _, row in sig_set.iterrows():
                session_df = df[df['session_date'] == row['date']]
                times = session_df['timestamp'].dt.time
                rth = session_df[(times >= dtime(9, 30)) & (times <= dtime(16, 0))].copy()
                post_bars = rth.loc[row['post_bars_idx']:]
                if len(post_bars) < 2:
                    continue

                entry_price = row['entry_close']
                if target_mode == 'poc':
                    target_price = row['target_poc']
                else:
                    pts = int(target_mode.replace('pt', ''))
                    target_price = entry_price + pts if row['direction'] == 'LONG' else entry_price - pts

                stop_price = entry_price - stop_pts if row['direction'] == 'LONG' else entry_price + stop_pts

                pnl = None
                reason = 'EOD'
                bars = len(post_bars)
                for i in range(len(post_bars)):
                    bar = post_bars.iloc[i]
                    if row['direction'] == 'LONG':
                        if bar['low'] <= stop_price:
                            pnl = -stop_pts
                            reason = 'STOP'
                            bars = i + 1
                            break
                        if bar['high'] >= target_price:
                            pnl = target_price - entry_price
                            reason = 'TARGET'
                            bars = i + 1
                            break
                    else:
                        if bar['high'] >= stop_price:
                            pnl = -stop_pts
                            reason = 'STOP'
                            bars = i + 1
                            break
                        if bar['low'] <= target_price:
                            pnl = entry_price - target_price
                            reason = 'TARGET'
                            bars = i + 1
                            break

                if pnl is None:
                    last = float(post_bars.iloc[-1]['close'])
                    pnl = (last - entry_price) if row['direction'] == 'LONG' else (entry_price - last)

                trades.append({
                    'pnl_pts': pnl,
                    'pnl_dollar': pnl * POINT_VALUE,
                    'reason': reason,
                    'direction': row['direction'],
                    'date': row['date'],
                })

            if not trades:
                continue
            tdf = pd.DataFrame(trades)
            wins = tdf[tdf.pnl_dollar > 0]
            losses = tdf[tdf.pnl_dollar <= 0]
            wr = 100 * len(wins) / len(tdf) if len(tdf) > 0 else 0
            gw = wins.pnl_dollar.sum() if len(wins) > 0 else 0
            gl = abs(losses.pnl_dollar.sum()) if len(losses) > 0 else 0
            pf = gw / gl if gl > 0 else float('inf')
            net = tdf.pnl_dollar.sum()
            avg = net / len(tdf)

            print(f'{stop_pts:>5}pt {target_mode:>12} | {len(tdf):>6} {len(wins):>5} {wr:>6.1f}% {pf:>7.2f} {net:>10,.0f} {avg:>8,.0f}')


# === Best config detailed breakdown ===
print()
print('=' * 90)
print('BEST CONFIG: Early, sep pullback, 50pt stop, 150pt target')
print('=' * 90)
sig_set = early
trades = []
for _, row in sig_set.iterrows():
    session_df = df[df['session_date'] == row['date']]
    times = session_df['timestamp'].dt.time
    rth = session_df[(times >= dtime(9, 30)) & (times <= dtime(16, 0))].copy()
    post_bars = rth.loc[row['post_bars_idx']:]
    if len(post_bars) < 2:
        continue

    entry_price = row['separation']
    target_price = entry_price + 150 if row['direction'] == 'LONG' else entry_price - 150
    stop_pts = 50

    filled, pnl, reason, bars = simulate_pullback(
        post_bars, row['direction'], entry_price, stop_pts, target_price
    )
    if filled:
        trades.append({
            'date': row['date'],
            'pnl_pts': pnl,
            'pnl_dollar': pnl * POINT_VALUE,
            'reason': reason,
            'bars': bars,
            'direction': row['direction'],
            'spread': row['spread'],
        })

tdf = pd.DataFrame(trades)
wins = tdf[tdf.pnl_dollar > 0]
losses = tdf[tdf.pnl_dollar <= 0]
print(f'Fills: {len(tdf)}/{len(sig_set)} signals')
print(f'Wins: {len(wins)}, Losses: {len(losses)}')
wr = 100 * len(wins) / len(tdf) if len(tdf) > 0 else 0
print(f'WR: {wr:.1f}%')
gw = wins.pnl_dollar.sum()
gl = abs(losses.pnl_dollar.sum())
pf = gw / gl if gl > 0 else float('inf')
print(f'PF: {pf:.2f}')
print(f'Net: ${tdf.pnl_dollar.sum():,.0f}')

for d in ['LONG', 'SHORT']:
    sub = tdf[tdf.direction == d]
    if len(sub) == 0:
        continue
    sw = sub[sub.pnl_dollar > 0]
    sl = sub[sub.pnl_dollar <= 0]
    wr = 100 * len(sw) / len(sub)
    gw = sw.pnl_dollar.sum() if len(sw) > 0 else 0
    gl = abs(sl.pnl_dollar.sum()) if len(sl) > 0 else 0
    pf = gw / gl if gl > 0 else float('inf')
    print(f'  {d}: {len(sub)} trades, {wr:.1f}% WR, PF {pf:.2f}, ${sub.pnl_dollar.sum():,.0f}')

tdf['month'] = pd.to_datetime(tdf['date']).dt.to_period('M')
monthly = tdf.groupby('month').agg(n=('pnl_dollar', 'count'), pnl=('pnl_dollar', 'sum'))
print('\nMonthly:')
for m, row in monthly.iterrows():
    print(f'  {m}: {row.n:.0f} trades, ${row.pnl:,.0f}')
