"""Double Distribution Trend Continuation — Quant Study"""
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

# Build snapshot index: for each session, find when DD first detected and params
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
                    bal = snap.get('balance_classification', {})
                    morph = bal.get('morph', {})
                    morph_type = morph.get('morph_type', 'none')

                    dd_sessions[date] = {
                        'first_time': et,
                        'separation': sep,
                        'upper_poc': upper,
                        'lower_poc': lower,
                        'spread': spread,
                        'morph_type': morph_type,
                    }

print(f'DD sessions: {len(dd_sessions)}')

# Filter to meaningful spreads (>= 50 pts)
MIN_SPREAD = 50
dd_meaningful = {k: v for k, v in dd_sessions.items() if v['spread'] >= MIN_SPREAD}
print(f'DD sessions with spread >= {MIN_SPREAD}pts: {len(dd_meaningful)}')

# For each DD session, compute edge
results = []

for date, dd in sorted(dd_meaningful.items()):
    session_df = df[df['session_date'] == date].copy()
    if len(session_df) == 0:
        continue

    # Filter to RTH only
    times = session_df['timestamp'].dt.time
    rth = session_df[(times >= dtime(9,30)) & (times <= dtime(16,0))].copy()
    if len(rth) < 60:
        continue

    # Find the bar at detection time
    detect_time = dd['first_time']
    try:
        detect_h, detect_m = int(detect_time.split(':')[0]), int(detect_time.split(':')[1])
    except:
        continue

    detect_dt = dtime(detect_h, detect_m)
    detect_bars = rth[rth['timestamp'].dt.time >= detect_dt]
    if len(detect_bars) == 0:
        continue

    detect_bar_idx = detect_bars.index[0]
    entry_price = float(rth.loc[detect_bar_idx, 'close'])

    sep = dd['separation']
    upper_poc = dd['upper_poc']
    lower_poc = dd['lower_poc']

    # Post-detection bars
    post_detect = rth.loc[detect_bar_idx:]
    if len(post_detect) < 2:
        continue

    # Direction: trade toward the NEWER distribution (continuation)
    # If price is above separation -> market building value higher -> LONG continuation
    # If price is below separation -> market building value lower -> SHORT continuation
    # Wait: "Trend continuation" means: double distribution = market migrating value
    # The NEW distribution is where value is MOVING TO
    # If upper distribution is newer (price above sep), trend = UP, trade LONG
    # If lower distribution is newer (price below sep), trend = DOWN, trade SHORT

    if entry_price > sep:
        # Price above separation = upper distribution is active
        # Trend continuation = LONG (value migrating up)
        direction = 'LONG'
        target_poc = upper_poc  # target is upper POC
        # But also check: can price continue to extend?
        # Alternative: entry on pullback to separation, target = upper POC
    else:
        direction = 'SHORT'
        target_poc = lower_poc

    post_highs = post_detect['high'].values
    post_lows = post_detect['low'].values

    if direction == 'LONG':
        mfe = float(post_highs.max() - entry_price)
        mae = float(entry_price - post_lows.min())
        reached_target = bool(post_highs.max() >= target_poc)

        targets = {}
        for pts in [25, 50, 75, 100, 150, 200]:
            targets[pts] = bool(post_highs.max() >= (entry_price + pts))
    else:
        mfe = float(entry_price - post_lows.min())
        mae = float(post_highs.max() - entry_price)
        reached_target = bool(post_lows.min() <= target_poc)

        targets = {}
        for pts in [25, 50, 75, 100, 150, 200]:
            targets[pts] = bool(post_lows.min() <= (entry_price - pts))

    # Also compute: pullback to separation entry
    # After DD detected, does price come back to separation for a better entry?
    pullback_entry = None
    for i in range(1, min(60, len(post_detect))):  # look 60 bars ahead
        bar = post_detect.iloc[i]
        if direction == 'LONG' and bar['low'] <= sep:
            pullback_entry = sep
            pullback_idx = post_detect.index[i]
            break
        elif direction == 'SHORT' and bar['high'] >= sep:
            pullback_entry = sep
            pullback_idx = post_detect.index[i]
            break

    pullback_mfe = None
    pullback_mae = None
    pullback_reached = None
    if pullback_entry is not None:
        pb_post = rth.loc[pullback_idx:]
        if direction == 'LONG':
            pullback_mfe = float(pb_post['high'].max() - pullback_entry)
            pullback_mae = float(pullback_entry - pb_post['low'].min())
            pullback_reached = bool(pb_post['high'].max() >= target_poc)
        else:
            pullback_mfe = float(pullback_entry - pb_post['low'].min())
            pullback_mae = float(pb_post['high'].max() - pullback_entry)
            pullback_reached = bool(pb_post['low'].min() <= target_poc)

    results.append({
        'date': date,
        'direction': direction,
        'entry_price': entry_price,
        'detect_time': detect_time,
        'spread': dd['spread'],
        'separation': sep,
        'target_poc': target_poc,
        'mfe': mfe,
        'mae': mae,
        'reached_target_poc': reached_target,
        'morph_type': dd['morph_type'],
        'pullback_entry': pullback_entry is not None,
        'pullback_mfe': pullback_mfe,
        'pullback_mae': pullback_mae,
        'pullback_reached': pullback_reached,
        **{f'target_{k}': v for k, v in targets.items()},
    })

print(f'\nAnalyzed {len(results)} sessions')
print()

if not results:
    print('No results to analyze')
    sys.exit(0)

rdf = pd.DataFrame(results)

print('=== OVERALL STATS (Trend Continuation) ===')
print(f'Total signals: {len(rdf)}')
print(f'Direction: SHORT={len(rdf[rdf.direction=="SHORT"])}, LONG={len(rdf[rdf.direction=="LONG"])}')
print(f'Avg spread: {rdf.spread.mean():.1f} pts')
print()

print('=== ENTRY AT DETECTION (close), TARGET = active distribution POC ===')
print(f'Reached target POC: {rdf.reached_target_poc.sum()}/{len(rdf)} = {100*rdf.reached_target_poc.mean():.1f}%')
print()

print('=== MFE/MAE ===')
print(f'MFE: min={rdf.mfe.min():.1f}, p25={rdf.mfe.quantile(0.25):.1f}, median={rdf.mfe.median():.1f}, mean={rdf.mfe.mean():.1f}, p75={rdf.mfe.quantile(0.75):.1f}, max={rdf.mfe.max():.1f}')
print(f'MAE: min={rdf.mae.min():.1f}, p25={rdf.mae.quantile(0.25):.1f}, median={rdf.mae.median():.1f}, mean={rdf.mae.mean():.1f}, p75={rdf.mae.quantile(0.75):.1f}, max={rdf.mae.max():.1f}')
print()

print('=== WIN RATE BY FIXED TARGET (no stop, all trades) ===')
for pts in [25, 50, 75, 100, 150, 200]:
    col = f'target_{pts}'
    wr = rdf[col].mean() * 100
    print(f'  {pts} pts: {rdf[col].sum()}/{len(rdf)} = {wr:.1f}%')

print()

# === PROFIT FACTOR CALCULATION ===
# For each stop/target combination, compute PF
print('=== STOP/TARGET MATRIX (Profit Factor) ===')
print(f'{"Stop":>8} | {"Tgt 50":>8} {"Tgt 75":>8} {"Tgt 100":>8} {"Tgt 150":>8}')
print('-' * 50)
for stop_pts in [25, 40, 50, 60, 75, 100]:
    pf_row = []
    for tgt_pts in [50, 75, 100, 150]:
        wins = 0
        losses = 0
        for _, r in rdf.iterrows():
            # Check if stop hit first or target hit first
            if r['mae'] >= stop_pts:
                # Could have hit target first — check MFE
                if r['mfe'] >= tgt_pts:
                    # Ambiguous — need bar-by-bar. Approximate: if MFE > MAE, likely won
                    if r['mfe'] > r['mae']:
                        wins += tgt_pts
                    else:
                        losses += stop_pts
                else:
                    losses += stop_pts
            elif r['mfe'] >= tgt_pts:
                wins += tgt_pts
            else:
                # Neither hit — EOD close. Approximate as small loss
                losses += stop_pts * 0.3
        pf = wins / losses if losses > 0 else float('inf')
        pf_row.append(pf)
    print(f'{stop_pts:>6}pt | {pf_row[0]:>8.2f} {pf_row[1]:>8.2f} {pf_row[2]:>8.2f} {pf_row[3]:>8.2f}')

print()

# === PULLBACK ENTRY ANALYSIS ===
pb = rdf[rdf.pullback_entry == True]
print(f'=== PULLBACK TO SEPARATION ENTRY ===')
print(f'Sessions with pullback: {len(pb)}/{len(rdf)} = {100*len(pb)/len(rdf):.1f}%')
if len(pb) > 0:
    print(f'Pullback reached target POC: {pb.pullback_reached.sum()}/{len(pb)} = {100*pb.pullback_reached.mean():.1f}%')
    print(f'Pullback MFE median={pb.pullback_mfe.median():.1f}, MAE median={pb.pullback_mae.median():.1f}')

print()

# === SPREAD SIZE ANALYSIS ===
for min_spread in [50, 75, 100]:
    sub = rdf[rdf.spread >= min_spread]
    if len(sub) == 0:
        continue
    print(f'=== Spread >= {min_spread}pts ({len(sub)} trades) ===')
    print(f'  Reached target POC: {100*sub.reached_target_poc.mean():.1f}%')
    print(f'  MFE median={sub.mfe.median():.1f}, MAE median={sub.mae.median():.1f}')
    for pts in [50, 100]:
        col = f'target_{pts}'
        print(f'  Target {pts}pts: {100*sub[col].mean():.1f}%')

print()

# === DETECTION TIME ANALYSIS ===
print('=== BY DETECTION TIME ===')
for time_bucket, label in [('early', '< 10:30'), ('late', '>= 10:30')]:
    if time_bucket == 'early':
        sub = rdf[rdf.detect_time < '10:30']
    else:
        sub = rdf[rdf.detect_time >= '10:30']
    if len(sub) == 0:
        continue
    print(f'{label} ({len(sub)} trades):')
    print(f'  MFE median={sub.mfe.median():.1f}, MAE median={sub.mae.median():.1f}')
    print(f'  Reached POC: {100*sub.reached_target_poc.mean():.1f}%')
    print(f'  Target 50pts: {100*sub.target_50.mean():.1f}%')
    print(f'  Target 100pts: {100*sub.target_100.mean():.1f}%')

print()

# === DIRECTION SPLIT ===
for d in ['SHORT', 'LONG']:
    sub = rdf[rdf.direction == d]
    if len(sub) == 0:
        continue
    print(f'=== {d} ({len(sub)} trades) ===')
    print(f'  Reached target POC: {sub.reached_target_poc.sum()}/{len(sub)} = {100*sub.reached_target_poc.mean():.1f}%')
    print(f'  MFE: median={sub.mfe.median():.1f}, mean={sub.mfe.mean():.1f}')
    print(f'  MAE: median={sub.mae.median():.1f}, mean={sub.mae.mean():.1f}')
    for pts in [25, 50, 75, 100]:
        col = f'target_{pts}'
        print(f'  Target {pts}pts: {100*sub[col].mean():.1f}%')

# === MORPH ANALYSIS ===
print()
print('=== BY MORPH TYPE ===')
for morph in rdf.morph_type.unique():
    sub = rdf[rdf.morph_type == morph]
    print(f'{morph} ({len(sub)} trades): POC WR={100*sub.reached_target_poc.mean():.1f}%, MFE med={sub.mfe.median():.1f}, MAE med={sub.mae.median():.1f}')
