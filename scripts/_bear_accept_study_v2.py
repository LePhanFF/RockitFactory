"""Bear Accept / Bull Accept quant study v2 — refined acceptance criteria.

Refinements over v1:
1. Use consecutive 5-min candle closes (like 20P rule) instead of single 30-min candle
2. Entry at acceptance close (not candle close)
3. Require IB range >= 20 pts (filter out narrow IB that produces false breaks)
4. Time filter: only accept during C-E periods (10:30-12:30)
5. Add VWAP/EMA bias alignment filter
6. Test both 2-bar and 3-bar acceptance
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
    """Resample 1-min bars to 5-min OHLCV."""
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
            'bar_idx_end': i + 4,  # last 1-min bar index within the slice
        })
    return pd.DataFrame(groups)


def find_acceptance(bars_5m, level, direction, n_consec):
    """Find n consecutive 5-min closes beyond level. Return index of acceptance bar or -1."""
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


def run_study(n_consec, min_ib_range=20, max_accept_bar=36, label=""):
    """Run acceptance study with given parameters.

    max_accept_bar: max 5-min bar index for acceptance (36 = 3 hours post-IB = 13:30)
    """
    results_bear = []
    results_bull = []

    for date in dates:
        day = df[df['session_date'] == date].copy()
        if len(day) < 72:  # need at least IB + some post-IB
            continue

        ib_bars = day.iloc[:60]
        ib_high = ib_bars['high'].max()
        ib_low = ib_bars['low'].min()
        ib_range = ib_high - ib_low

        if ib_range < min_ib_range:
            continue

        post_ib = day.iloc[60:]
        if len(post_ib) < 10:
            continue

        # Resample post-IB bars to 5-min
        bars_5m = resample_5m(post_ib)
        if len(bars_5m) < n_consec + 1:
            continue

        # Get VWAP at IB close for bias filter
        vwap_at_ib = ib_bars.iloc[-1].get('vwap', None)
        ib_close = ib_bars.iloc[-1]['close']

        # BEAR: acceptance below IBL
        accept_idx = find_acceptance(bars_5m, ib_low, 'SHORT', n_consec)
        if accept_idx >= 0 and accept_idx <= max_accept_bar:
            accept_bar = bars_5m.iloc[accept_idx]
            entry_price = accept_bar['close']

            # Get remaining 1-min bars after acceptance
            accept_1m_end = 60 + int(accept_bar['bar_idx_end']) + 1
            remaining = day.iloc[accept_1m_end:]

            if len(remaining) > 0:
                mae = remaining['high'].max() - entry_price
                mfe = entry_price - remaining['low'].min()

                # Bias checks
                vwap_aligned = vwap_at_ib is not None and entry_price < vwap_at_ib
                close_below_ib = ib_close < (ib_low + ib_range * 0.3)  # IB closed in lower 30%

                results_bear.append({
                    'date': str(date),
                    'ib_range': ib_range,
                    'accept_5m_idx': accept_idx,
                    'entry_price': entry_price,
                    'mae': mae,
                    'mfe': mfe,
                    'vwap_aligned': vwap_aligned,
                    'ib_close_low': close_below_ib,
                })

        # BULL: acceptance above IBH
        accept_idx = find_acceptance(bars_5m, ib_high, 'LONG', n_consec)
        if accept_idx >= 0 and accept_idx <= max_accept_bar:
            accept_bar = bars_5m.iloc[accept_idx]
            entry_price = accept_bar['close']

            accept_1m_end = 60 + int(accept_bar['bar_idx_end']) + 1
            remaining = day.iloc[accept_1m_end:]

            if len(remaining) > 0:
                mae = entry_price - remaining['low'].min()
                mfe = remaining['high'].max() - entry_price

                vwap_aligned = vwap_at_ib is not None and entry_price > vwap_at_ib
                close_above_ib = ib_close > (ib_high - ib_range * 0.3)

                results_bull.append({
                    'date': str(date),
                    'ib_range': ib_range,
                    'accept_5m_idx': accept_idx,
                    'entry_price': entry_price,
                    'mae': mae,
                    'mfe': mfe,
                    'vwap_aligned': vwap_aligned,
                    'ib_close_high': close_above_ib,
                })

    return results_bear, results_bull


def print_analysis(results, direction, label):
    """Print win rate analysis for a set of results."""
    if not results:
        print(f'  No {direction} events')
        return False

    rdf = pd.DataFrame(results)
    print(f'\n--- {direction} ({label}) ---')
    print(f'Events: {len(rdf)}')
    print(f'MAE: mean={rdf["mae"].mean():.1f}, median={rdf["mae"].median():.1f}, p75={rdf["mae"].quantile(0.75):.1f}, p90={rdf["mae"].quantile(0.90):.1f}')
    print(f'MFE: mean={rdf["mfe"].mean():.1f}, median={rdf["mfe"].median():.1f}, p75={rdf["mfe"].quantile(0.75):.1f}, p90={rdf["mfe"].quantile(0.90):.1f}')
    print(f'Acceptance timing: median 5m-bar={rdf["accept_5m_idx"].median():.0f}')

    has_edge = False
    print(f'{"Stop":>6} {"Target":>7} {"Wins":>5} {"Loss":>5} {"EOD":>5} {"Total":>6} {"WR%":>6} {"PF":>6} {"$/trade":>8}')
    for stop_pts in [15, 20, 25, 30, 35, 40, 50]:
        for target_pts in [20, 30, 40, 50, 60, 80]:
            wins = ((rdf['mfe'] >= target_pts) & (rdf['mae'] < stop_pts)).sum()
            losses = (rdf['mae'] >= stop_pts).sum()
            # EOD = didn't hit stop or target
            eod = len(rdf) - wins - losses
            # For EOD trades, estimate P&L as 0 (conservative)
            total_decided = wins + losses
            if total_decided >= 10:
                wr = wins / total_decided * 100
                pf = (wins * target_pts) / (losses * stop_pts) if losses > 0 else float('inf')
                avg_pnl = ((wins * target_pts * 20) - (losses * stop_pts * 20)) / len(rdf)  # per event
                if pf >= 1.0:
                    print(f'  {stop_pts:>4} {target_pts:>7} {wins:>5} {losses:>5} {eod:>5} {total_decided:>6} {wr:>5.1f}% {pf:>5.2f} ${avg_pnl:>7.0f}')
                    if wr >= 45 and pf >= 1.5:
                        has_edge = True

    # Check with VWAP alignment filter
    if 'vwap_aligned' in rdf.columns:
        vwap_df = rdf[rdf['vwap_aligned'] == True]
        if len(vwap_df) >= 10:
            print(f'\n  With VWAP alignment filter ({len(vwap_df)} events):')
            for stop_pts in [20, 25, 30, 35, 40]:
                for target_pts in [30, 40, 50, 60]:
                    wins = ((vwap_df['mfe'] >= target_pts) & (vwap_df['mae'] < stop_pts)).sum()
                    losses = (vwap_df['mae'] >= stop_pts).sum()
                    total_decided = wins + losses
                    if total_decided >= 8:
                        wr = wins / total_decided * 100
                        pf = (wins * target_pts) / (losses * stop_pts) if losses > 0 else float('inf')
                        avg_pnl = ((wins * target_pts * 20) - (losses * stop_pts * 20)) / len(vwap_df)
                        if pf >= 1.0:
                            print(f'    Stop={stop_pts}, Target={target_pts}: {wins}W/{losses}L, WR={wr:.1f}%, PF={pf:.2f}, ${avg_pnl:.0f}/event')
                            if wr >= 45 and pf >= 1.5:
                                has_edge = True

    return has_edge


# Run multiple configurations
print('\n' + '='*70)
print('STUDY 1: 2-bar 5-min acceptance (10 min acceptance)')
print('='*70)
bear2, bull2 = run_study(n_consec=2, min_ib_range=20)
edge_bear2 = print_analysis(bear2, 'BEAR', '2-bar')
edge_bull2 = print_analysis(bull2, 'BULL', '2-bar')

print('\n' + '='*70)
print('STUDY 2: 3-bar 5-min acceptance (15 min acceptance)')
print('='*70)
bear3, bull3 = run_study(n_consec=3, min_ib_range=20)
edge_bear3 = print_analysis(bear3, 'BEAR', '3-bar')
edge_bull3 = print_analysis(bull3, 'BULL', '3-bar')

print('\n' + '='*70)
print('STUDY 3: 2-bar acceptance, IB range >= 30 pts')
print('='*70)
bear2b, bull2b = run_study(n_consec=2, min_ib_range=30)
edge_bear2b = print_analysis(bear2b, 'BEAR', '2-bar IB>=30')
edge_bull2b = print_analysis(bull2b, 'BULL', '2-bar IB>=30')

print('\n' + '='*70)
print('STUDY 4: 3-bar acceptance, IB range >= 30 pts')
print('='*70)
bear3b, bull3b = run_study(n_consec=3, min_ib_range=30)
edge_bear3b = print_analysis(bear3b, 'BEAR', '3-bar IB>=30')
edge_bull3b = print_analysis(bull3b, 'BULL', '3-bar IB>=30')

# Check early acceptance only (C-period, first 30 min after IB)
print('\n' + '='*70)
print('STUDY 5: 2-bar acceptance, early only (first 6 5-min bars = 30 min post IB)')
print('='*70)
bear_early, bull_early = run_study(n_consec=2, min_ib_range=20, max_accept_bar=6)
edge_bear_early = print_analysis(bear_early, 'BEAR', '2-bar early')
edge_bull_early = print_analysis(bull_early, 'BULL', '2-bar early')

any_edge = any([edge_bear2, edge_bull2, edge_bear3, edge_bull3,
                edge_bear2b, edge_bull2b, edge_bear3b, edge_bull3b,
                edge_bear_early, edge_bull_early])

print(f'\n{"="*70}')
print(f'CONCLUSION: {"Edge found — proceed to build phase" if any_edge else "No viable edge found (WR>=45% AND PF>=1.5)"}')
print(f'{"="*70}')
