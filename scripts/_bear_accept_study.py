"""Bear Accept / Bull Accept quant study — IBL/IBH 30-min acceptance."""
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, 'packages/rockit-core/src')
from rockit_core.data.manager import SessionDataManager
from rockit_core.data.features import compute_all_features

mgr = SessionDataManager()
df = compute_all_features(mgr.load('NQ'))

# Get unique session dates
df['session_date'] = df['timestamp'].dt.date if 'timestamp' in df.columns else df.index.date
dates = sorted(df['session_date'].unique())
print(f'Total sessions: {len(dates)}')

results_bear = []
results_bull = []

for date in dates:
    day = df[df['session_date'] == date].copy()
    if len(day) < 60:
        continue

    # IB bars (first 60 1-min bars of RTH)
    ib_bars = day.iloc[:60]
    ib_high = ib_bars['high'].max()
    ib_low = ib_bars['low'].min()
    ib_range = ib_high - ib_low

    if ib_range < 10:  # skip tiny IB
        continue

    post_ib = day.iloc[60:]  # bars after IB
    if len(post_ib) < 6:
        continue

    # Build 30-min candles from IB bar 30 onwards (10:00 ET)
    all_bars_from_10am = day.iloc[30:]  # starting at bar 30 = 10:00

    bear_found = False
    bull_found = False

    for candle_start in range(0, min(len(all_bars_from_10am), 180), 30):  # up to 13:30
        candle = all_bars_from_10am.iloc[candle_start:candle_start + 30]
        if len(candle) < 30:
            break

        candle_close = candle.iloc[-1]['close']

        # BEAR: 30-min close below IBL
        if not bear_found and candle_close < ib_low:
            entry_price = candle_close
            remaining_idx = 30 + candle_start + 30  # offset in day df
            remaining = day.iloc[remaining_idx:]

            if len(remaining) > 0:
                subsequent_low = remaining['low'].min()
                subsequent_high = remaining['high'].max()
                mae = subsequent_high - entry_price
                mfe = entry_price - subsequent_low

                results_bear.append({
                    'date': str(date),
                    'ib_high': ib_high,
                    'ib_low': ib_low,
                    'ib_range': ib_range,
                    'accept_bar_offset': candle_start,
                    'entry_price': entry_price,
                    'subsequent_low': subsequent_low,
                    'subsequent_high': subsequent_high,
                    'mae': mae,
                    'mfe': mfe,
                })
                bear_found = True

        # BULL: 30-min close above IBH
        if not bull_found and candle_close > ib_high:
            entry_price = candle_close
            remaining_idx = 30 + candle_start + 30
            remaining = day.iloc[remaining_idx:]

            if len(remaining) > 0:
                subsequent_low = remaining['low'].min()
                subsequent_high = remaining['high'].max()
                mae = entry_price - subsequent_low
                mfe = subsequent_high - entry_price

                results_bull.append({
                    'date': str(date),
                    'ib_high': ib_high,
                    'ib_low': ib_low,
                    'ib_range': ib_range,
                    'accept_bar_offset': candle_start,
                    'entry_price': entry_price,
                    'subsequent_low': subsequent_low,
                    'subsequent_high': subsequent_high,
                    'mae': mae,
                    'mfe': mfe,
                })
                bull_found = True

print(f'\n=== BEAR ACCEPT (IBL Acceptance Short) ===')
print(f'Sessions with IBL acceptance: {len(results_bear)} / {len(dates)} ({100*len(results_bear)/len(dates):.1f}%)')

if results_bear:
    bear_df = pd.DataFrame(results_bear)
    print(f'\nMAE (adverse excursion above entry):')
    print(f'  Mean: {bear_df["mae"].mean():.1f} pts')
    print(f'  Median: {bear_df["mae"].median():.1f} pts')
    print(f'  25th pctl: {bear_df["mae"].quantile(0.25):.1f} pts')
    print(f'  75th pctl: {bear_df["mae"].quantile(0.75):.1f} pts')
    print(f'  90th pctl: {bear_df["mae"].quantile(0.90):.1f} pts')

    print(f'\nMFE (favorable excursion below entry):')
    print(f'  Mean: {bear_df["mfe"].mean():.1f} pts')
    print(f'  Median: {bear_df["mfe"].median():.1f} pts')
    print(f'  25th pctl: {bear_df["mfe"].quantile(0.25):.1f} pts')
    print(f'  75th pctl: {bear_df["mfe"].quantile(0.75):.1f} pts')
    print(f'  90th pctl: {bear_df["mfe"].quantile(0.90):.1f} pts')

    print(f'\nIB Range stats:')
    print(f'  Mean: {bear_df["ib_range"].mean():.1f} pts')
    print(f'  Median: {bear_df["ib_range"].median():.1f} pts')

    print(f'\nAcceptance timing (bar offset from 10:00):')
    print(f'  0=10:00-10:30, 30=10:30-11:00, 60=11:00-11:30, 90=11:30-12:00')
    print(bear_df['accept_bar_offset'].value_counts().sort_index().to_string())

    print(f'\n=== Win Rate Analysis (BEAR) ===')
    print(f'{"Stop":>6} {"Target":>7} {"Wins":>5} {"Loss":>5} {"Total":>6} {"WR%":>6} {"PF":>6}')
    for stop_pts in [20, 25, 30, 35, 40, 50]:
        for target_pts in [20, 30, 40, 50, 60, 80]:
            wins = ((bear_df['mfe'] >= target_pts) & (bear_df['mae'] < stop_pts)).sum()
            losses = (bear_df['mae'] >= stop_pts).sum()
            total = wins + losses
            if total > 0:
                wr = wins / total * 100
                pf = (wins * target_pts) / (losses * stop_pts) if losses > 0 else float('inf')
                if total >= 15:
                    print(f'  {stop_pts:>4} {target_pts:>7} {wins:>5} {losses:>5} {total:>6} {wr:>5.1f}% {pf:>5.2f}')

print(f'\n=== BULL ACCEPT (IBH Acceptance Long) ===')
print(f'Sessions with IBH acceptance: {len(results_bull)} / {len(dates)} ({100*len(results_bull)/len(dates):.1f}%)')

if results_bull:
    bull_df = pd.DataFrame(results_bull)
    print(f'\nMAE (adverse excursion below entry):')
    print(f'  Mean: {bull_df["mae"].mean():.1f} pts')
    print(f'  Median: {bull_df["mae"].median():.1f} pts')
    print(f'  25th pctl: {bull_df["mae"].quantile(0.25):.1f} pts')
    print(f'  75th pctl: {bull_df["mae"].quantile(0.75):.1f} pts')
    print(f'  90th pctl: {bull_df["mae"].quantile(0.90):.1f} pts')

    print(f'\nMFE (favorable excursion above entry):')
    print(f'  Mean: {bull_df["mfe"].mean():.1f} pts')
    print(f'  Median: {bull_df["mfe"].median():.1f} pts')
    print(f'  25th pctl: {bull_df["mfe"].quantile(0.25):.1f} pts')
    print(f'  75th pctl: {bull_df["mfe"].quantile(0.75):.1f} pts')
    print(f'  90th pctl: {bull_df["mfe"].quantile(0.90):.1f} pts')

    print(f'\nIB Range stats:')
    print(f'  Mean: {bull_df["ib_range"].mean():.1f} pts')
    print(f'  Median: {bull_df["ib_range"].median():.1f} pts')

    print(f'\nAcceptance timing (bar offset from 10:00):')
    print(bull_df['accept_bar_offset'].value_counts().sort_index().to_string())

    print(f'\n=== Win Rate Analysis (BULL) ===')
    print(f'{"Stop":>6} {"Target":>7} {"Wins":>5} {"Loss":>5} {"Total":>6} {"WR%":>6} {"PF":>6}')
    for stop_pts in [20, 25, 30, 35, 40, 50]:
        for target_pts in [20, 30, 40, 50, 60, 80]:
            wins = ((bull_df['mfe'] >= target_pts) & (bull_df['mae'] < stop_pts)).sum()
            losses = (bull_df['mae'] >= stop_pts).sum()
            total = wins + losses
            if total > 0:
                wr = wins / total * 100
                pf = (wins * target_pts) / (losses * stop_pts) if losses > 0 else float('inf')
                if total >= 15:
                    print(f'  {stop_pts:>4} {target_pts:>7} {wins:>5} {losses:>5} {total:>6} {wr:>5.1f}% {pf:>5.2f}')

# Combined summary
print(f'\n=== COMBINED SUMMARY ===')
print(f'Bear Accept events: {len(results_bear)} ({100*len(results_bear)/len(dates):.1f}% of sessions)')
print(f'Bull Accept events: {len(results_bull)} ({100*len(results_bull)/len(dates):.1f}% of sessions)')
if results_bear:
    print(f'Bear median MFE: {bear_df["mfe"].median():.1f} pts, median MAE: {bear_df["mae"].median():.1f} pts')
if results_bull:
    print(f'Bull median MFE: {bull_df["mfe"].median():.1f} pts, median MAE: {bull_df["mae"].median():.1f} pts')
