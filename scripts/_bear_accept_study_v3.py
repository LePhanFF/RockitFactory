"""Bear Accept study v3 — retest entry after IB break acceptance.

Instead of entering at the acceptance close, wait for price to retest IBL/IBH
(pull back to the level), then enter. This should dramatically reduce MAE.
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


def find_retest(bars_1m, level, direction, max_bars=60):
    """After acceptance, find retest of the level within max_bars.
    For SHORT: price rallies back UP to IBL (bar high >= level)
    For LONG: price pulls back DOWN to IBH (bar low <= level)
    """
    for i in range(min(len(bars_1m), max_bars)):
        bar = bars_1m.iloc[i]
        if direction == 'SHORT' and bar['high'] >= level:
            return i
        if direction == 'LONG' and bar['low'] <= level:
            return i
    return -1


results_bear = []
results_bull = []

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

    # VWAP at IB close
    vwap_at_ib = ib_bars.iloc[-1].get('vwap', None)

    for n_consec in [2, 3]:
        # BEAR: acceptance below IBL, then retest IBL
        accept_idx = find_acceptance(bars_5m, ib_low, 'SHORT', n_consec)
        if accept_idx >= 0 and accept_idx <= 24:  # within 2 hours of IB close
            # Start looking for retest from the bar after acceptance
            accept_1m_end = int(bars_5m.iloc[accept_idx]['bar_idx_end']) + 1
            remaining_1m = post_ib.iloc[accept_1m_end:]

            retest_idx = find_retest(remaining_1m, ib_low, 'SHORT', max_bars=60)
            if retest_idx >= 0:
                # Entry at IBL (limit short at the level)
                entry_price = ib_low
                retest_1m_abs = 60 + accept_1m_end + retest_idx
                after_entry = day.iloc[retest_1m_abs + 1:]

                if len(after_entry) > 0:
                    mae = after_entry['high'].max() - entry_price
                    mfe = entry_price - after_entry['low'].min()

                    vwap_aligned = vwap_at_ib is not None and entry_price < vwap_at_ib

                    results_bear.append({
                        'date': str(date),
                        'ib_range': ib_range,
                        'n_consec': n_consec,
                        'accept_5m_idx': accept_idx,
                        'retest_bars_after': retest_idx,
                        'entry_price': entry_price,
                        'mae': mae,
                        'mfe': mfe,
                        'vwap_aligned': vwap_aligned,
                    })
            break  # only take first acceptance

        # BULL: acceptance above IBH, then retest IBH
        accept_idx = find_acceptance(bars_5m, ib_high, 'LONG', n_consec)
        if accept_idx >= 0 and accept_idx <= 24:
            accept_1m_end = int(bars_5m.iloc[accept_idx]['bar_idx_end']) + 1
            remaining_1m = post_ib.iloc[accept_1m_end:]

            retest_idx = find_retest(remaining_1m, ib_high, 'LONG', max_bars=60)
            if retest_idx >= 0:
                entry_price = ib_high
                retest_1m_abs = 60 + accept_1m_end + retest_idx
                after_entry = day.iloc[retest_1m_abs + 1:]

                if len(after_entry) > 0:
                    mae = entry_price - after_entry['low'].min()
                    mfe = after_entry['high'].max() - entry_price

                    vwap_aligned = vwap_at_ib is not None and entry_price > vwap_at_ib

                    results_bull.append({
                        'date': str(date),
                        'ib_range': ib_range,
                        'n_consec': n_consec,
                        'accept_5m_idx': accept_idx,
                        'retest_bars_after': retest_idx,
                        'entry_price': entry_price,
                        'mae': mae,
                        'mfe': mfe,
                        'vwap_aligned': vwap_aligned,
                    })
            break


def analyze(results, direction):
    if not results:
        print(f'  No {direction} events')
        return

    rdf = pd.DataFrame(results)
    print(f'\n--- {direction} (Retest Entry at IB Level) ---')
    print(f'Events: {len(rdf)}')
    print(f'By n_consec: {rdf["n_consec"].value_counts().to_dict()}')
    print(f'MAE: mean={rdf["mae"].mean():.1f}, median={rdf["mae"].median():.1f}, '
          f'p25={rdf["mae"].quantile(0.25):.1f}, p75={rdf["mae"].quantile(0.75):.1f}, '
          f'p90={rdf["mae"].quantile(0.90):.1f}')
    print(f'MFE: mean={rdf["mfe"].mean():.1f}, median={rdf["mfe"].median():.1f}, '
          f'p25={rdf["mfe"].quantile(0.25):.1f}, p75={rdf["mfe"].quantile(0.75):.1f}, '
          f'p90={rdf["mfe"].quantile(0.90):.1f}')
    print(f'Retest delay: median={rdf["retest_bars_after"].median():.0f} bars')

    best_combos = []
    print(f'\n{"Stop":>6} {"Target":>7} {"Wins":>5} {"Loss":>5} {"EOD":>5} {"Total":>6} {"WR%":>6} {"PF":>6} {"$/trade":>8}')
    for stop_pts in [10, 15, 20, 25, 30, 35, 40, 50]:
        for target_pts in [15, 20, 30, 40, 50, 60, 80]:
            wins = int(((rdf['mfe'] >= target_pts) & (rdf['mae'] < stop_pts)).sum())
            losses = int((rdf['mae'] >= stop_pts).sum())
            eod = len(rdf) - wins - losses
            total = wins + losses
            if total >= 10:
                wr = wins / total * 100
                pf = (wins * target_pts) / (losses * stop_pts) if losses > 0 else float('inf')
                avg_pnl = ((wins * target_pts * 20) - (losses * stop_pts * 20)) / len(rdf)
                marker = ''
                if wr >= 45 and pf >= 1.5:
                    marker = ' ***EDGE***'
                    best_combos.append((stop_pts, target_pts, wins, losses, wr, pf, avg_pnl))
                if pf >= 0.8:
                    print(f'  {stop_pts:>4} {target_pts:>7} {wins:>5} {losses:>5} {eod:>5} {total:>6} {wr:>5.1f}% {pf:>5.2f} ${avg_pnl:>7.0f}{marker}')

    # VWAP filter
    vwap_df = rdf[rdf['vwap_aligned'] == True]
    if len(vwap_df) >= 10:
        print(f'\n  With VWAP alignment ({len(vwap_df)} events):')
        for stop_pts in [15, 20, 25, 30, 35, 40]:
            for target_pts in [20, 30, 40, 50, 60]:
                wins = int(((vwap_df['mfe'] >= target_pts) & (vwap_df['mae'] < stop_pts)).sum())
                losses = int((vwap_df['mae'] >= stop_pts).sum())
                total = wins + losses
                if total >= 8:
                    wr = wins / total * 100
                    pf = (wins * target_pts) / (losses * stop_pts) if losses > 0 else float('inf')
                    avg_pnl = ((wins * target_pts * 20) - (losses * stop_pts * 20)) / len(vwap_df)
                    marker = ' ***EDGE***' if wr >= 45 and pf >= 1.5 else ''
                    if pf >= 0.8:
                        print(f'    Stop={stop_pts}, Target={target_pts}: {wins}W/{losses}L, WR={wr:.1f}%, PF={pf:.2f}, ${avg_pnl:.0f}/event{marker}')

    return best_combos


print('\n' + '='*70)
print('BEAR ACCEPT — Retest Entry at IBL after 2-or-3 bar 5-min acceptance')
print('='*70)
bear_combos = analyze(results_bear, 'BEAR')

print('\n' + '='*70)
print('BULL ACCEPT — Retest Entry at IBH after 2-or-3 bar 5-min acceptance')
print('='*70)
bull_combos = analyze(results_bull, 'BULL')

has_edge = bool(bear_combos) or bool(bull_combos)
print(f'\n{"="*70}')
print(f'CONCLUSION: {"Edge found — proceed to build phase" if has_edge else "No viable edge found (WR>=45% AND PF>=1.5)"}')
print(f'{"="*70}')

if bear_combos:
    print('\nBest BEAR combos:')
    for s, t, w, l, wr, pf, avg in bear_combos:
        print(f'  Stop={s}, Target={t}: {w}W/{l}L, WR={wr:.1f}%, PF={pf:.2f}, ${avg:.0f}/event')
if bull_combos:
    print('\nBest BULL combos:')
    for s, t, w, l, wr, pf, avg in bull_combos:
        print(f'  Stop={s}, Target={t}: {w}W/{l}L, WR={wr:.1f}%, PF={pf:.2f}, ${avg:.0f}/event')
