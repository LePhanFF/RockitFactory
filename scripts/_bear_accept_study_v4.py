"""Bear Accept study v4 — with delta, momentum, and day type filters.

Final attempt: layer on every reasonable filter to find a viable subset.
"""
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, 'packages/rockit-core/src')
from rockit_core.data.manager import SessionDataManager
from rockit_core.data.features import compute_all_features

mgr = SessionDataManager()
df = compute_all_features(mgr.load('NQ'))

df['session_date'] = df['timestamp'].dt.date if 'timestamp' in df.columns else df.index.date
dates = sorted(df['session_date'].unique())
print(f'Total sessions: {len(dates)}')


def resample_5m(bars):
    groups = []
    for i in range(0, len(bars), 5):
        chunk = bars.iloc[i:i+5]
        if len(chunk) < 5:
            break
        groups.append({
            'open': chunk.iloc[0]['open'],
            'high': chunk['high'].max(),
            'low': chunk['low'].min(),
            'close': chunk.iloc[-1]['close'],
            'bar_idx_end': i + 4,
            'delta_sum': chunk['vol_delta'].sum() if 'vol_delta' in chunk.columns else 0,
        })
    return pd.DataFrame(groups)


def find_acceptance(bars_5m, level, direction, n_consec):
    consec = 0
    for i in range(len(bars_5m)):
        close = bars_5m.iloc[i]['close']
        if direction == 'SHORT' and close < level:
            consec += 1
        elif direction == 'LONG' and close > level:
            consec += 1
        else:
            consec = 0
        if consec >= n_consec:
            return i
    return -1


results_all = []

for date in dates:
    day = df[df['session_date'] == date].copy()
    if len(day) < 72:
        continue

    ib_bars = day.iloc[:60]
    ib_high = ib_bars['high'].max()
    ib_low = ib_bars['low'].min()
    ib_range = ib_high - ib_low

    if ib_range < 20:
        continue

    post_ib = day.iloc[60:]
    if len(post_ib) < 15:
        continue

    bars_5m = resample_5m(post_ib)

    # Context for filters
    vwap = ib_bars.iloc[-1].get('vwap', None)
    ema20 = ib_bars.iloc[-1].get('ema20', None) if 'ema20' in ib_bars.columns else None
    ema50 = ib_bars.iloc[-1].get('ema50', None) if 'ema50' in ib_bars.columns else None
    day_type = ib_bars.iloc[-1].get('day_type', '') if 'day_type' in ib_bars.columns else ''
    ib_close = ib_bars.iloc[-1]['close']

    # Cumulative delta during IB
    ib_delta = ib_bars['vol_delta'].sum() if 'vol_delta' in ib_bars.columns else 0

    for direction in ['BEAR', 'SHORT'], ['BULL', 'LONG']:
        dir_label, dir_code = direction
        level = ib_low if dir_label == 'BEAR' else ib_high

        for n_consec in [2, 3]:
            accept_idx = find_acceptance(bars_5m, level, dir_code, n_consec)
            if accept_idx < 0 or accept_idx > 24:
                continue

            accept_bar = bars_5m.iloc[accept_idx]
            entry_price = accept_bar['close']

            # Delta during acceptance bars
            accept_start = max(0, accept_idx - n_consec + 1)
            accept_delta = bars_5m.iloc[accept_start:accept_idx+1]['delta_sum'].sum()

            accept_1m_end = 60 + int(accept_bar['bar_idx_end']) + 1
            remaining = day.iloc[accept_1m_end:]

            if len(remaining) < 5:
                continue

            if dir_label == 'BEAR':
                mae = remaining['high'].max() - entry_price
                mfe = entry_price - remaining['low'].min()
                delta_confirms = accept_delta < 0  # negative delta confirms selling
                vwap_aligned = vwap is not None and entry_price < vwap
                ema_aligned = ema20 is not None and ema50 is not None and ema20 < ema50
                ib_close_confirms = ib_close < (ib_low + ib_range * 0.3)
            else:
                mae = entry_price - remaining['low'].min()
                mfe = remaining['high'].max() - entry_price
                delta_confirms = accept_delta > 0
                vwap_aligned = vwap is not None and entry_price > vwap
                ema_aligned = ema20 is not None and ema50 is not None and ema20 > ema50
                ib_close_confirms = ib_close > (ib_high - ib_range * 0.3)

            results_all.append({
                'date': str(date),
                'direction': dir_label,
                'n_consec': n_consec,
                'ib_range': ib_range,
                'entry_price': entry_price,
                'mae': mae,
                'mfe': mfe,
                'delta_confirms': delta_confirms,
                'vwap_aligned': vwap_aligned,
                'ema_aligned': ema_aligned,
                'ib_close_confirms': ib_close_confirms,
                'accept_5m_idx': accept_idx,
                'ib_delta': ib_delta,
                'accept_delta': accept_delta,
            })
            break  # only first acceptance per direction per session

rdf = pd.DataFrame(results_all)
print(f'\nTotal events: {len(rdf)}')
print(f'By direction: {rdf["direction"].value_counts().to_dict()}')


def score_subset(subset_df, label):
    """Score a subset of events."""
    if len(subset_df) < 10:
        return None

    best = None
    for stop_pts in [15, 20, 25, 30, 35, 40, 50]:
        for target_pts in [20, 30, 40, 50, 60, 80]:
            wins = int(((subset_df['mfe'] >= target_pts) & (subset_df['mae'] < stop_pts)).sum())
            losses = int((subset_df['mae'] >= stop_pts).sum())
            total = wins + losses
            if total >= 8 and losses > 0:
                wr = wins / total * 100
                pf = (wins * target_pts) / (losses * stop_pts)
                avg_pnl = ((wins * target_pts * 20) - (losses * stop_pts * 20)) / len(subset_df)
                if pf > (best[5] if best else 0):
                    best = (stop_pts, target_pts, wins, losses, wr, pf, avg_pnl, total)
    return best


# Test all filter combinations
filters = {
    'all': rdf,
    'delta': rdf[rdf['delta_confirms']],
    'vwap': rdf[rdf['vwap_aligned']],
    'ema': rdf[rdf['ema_aligned']],
    'ib_close': rdf[rdf['ib_close_confirms']],
    'delta+vwap': rdf[rdf['delta_confirms'] & rdf['vwap_aligned']],
    'delta+ema': rdf[rdf['delta_confirms'] & rdf['ema_aligned']],
    'vwap+ema': rdf[rdf['vwap_aligned'] & rdf['ema_aligned']],
    'delta+vwap+ema': rdf[rdf['delta_confirms'] & rdf['vwap_aligned'] & rdf['ema_aligned']],
    'all_filters': rdf[rdf['delta_confirms'] & rdf['vwap_aligned'] & rdf['ema_aligned'] & rdf['ib_close_confirms']],
    '3_consec': rdf[rdf['n_consec'] == 3],
    '3_consec+delta': rdf[(rdf['n_consec'] == 3) & rdf['delta_confirms']],
    'ib_range>=40': rdf[rdf['ib_range'] >= 40],
    'ib_range>=40+delta': rdf[(rdf['ib_range'] >= 40) & rdf['delta_confirms']],
}

print(f'\n{"Filter":<25} {"N":>4} {"Stop":>5} {"Tgt":>5} {"W":>3} {"L":>3} {"Tot":>4} {"WR%":>6} {"PF":>5} {"$/evt":>7}')
print('-' * 80)

for direction in ['BEAR', 'BULL']:
    print(f'\n  --- {direction} ---')
    for name, subset in filters.items():
        dir_df = subset[subset['direction'] == direction]
        result = score_subset(dir_df, f'{direction}_{name}')
        if result:
            s, t, w, l, wr, pf, avg, tot = result
            marker = ' <-- EDGE' if wr >= 45 and pf >= 1.5 else ''
            print(f'  {name:<23} {len(dir_df):>4} {s:>5} {t:>5} {w:>3} {l:>3} {tot:>4} {wr:>5.1f}% {pf:>4.2f} ${avg:>6.0f}{marker}')
        else:
            print(f'  {name:<23} {len(dir_df):>4}  (insufficient data or no PF>0)')

# Combined (both directions)
print(f'\n  --- COMBINED ---')
for name, subset in filters.items():
    result = score_subset(subset, f'COMBINED_{name}')
    if result:
        s, t, w, l, wr, pf, avg, tot = result
        marker = ' <-- EDGE' if wr >= 45 and pf >= 1.5 else ''
        print(f'  {name:<23} {len(subset):>4} {s:>5} {t:>5} {w:>3} {l:>3} {tot:>4} {wr:>5.1f}% {pf:>4.2f} ${avg:>6.0f}{marker}')
    else:
        print(f'  {name:<23} {len(subset):>4}  (insufficient data or no PF>0)')

print(f'\n{"="*70}')
print('FINAL VERDICT')
print(f'{"="*70}')

# Check if any filter combo found an edge
any_edge = False
for direction in ['BEAR', 'BULL']:
    for name, subset in filters.items():
        dir_df = subset[subset['direction'] == direction]
        result = score_subset(dir_df, f'{direction}_{name}')
        if result:
            s, t, w, l, wr, pf, avg, tot = result
            if wr >= 45 and pf >= 1.5:
                any_edge = True
                print(f'  EDGE: {direction} + {name}: Stop={s}, Target={t}, {w}W/{l}L, WR={wr:.1f}%, PF={pf:.2f}')

if not any_edge:
    print('  No viable edge found across any filter combination.')
    print('  IB acceptance (30-min or 5-min multi-bar) does not produce a reliable')
    print('  signal in NQ. The median MAE is too high relative to any reasonable stop.')
    print('  Recommendation: DO NOT BUILD this strategy.')
