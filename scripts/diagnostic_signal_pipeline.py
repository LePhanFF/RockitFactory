#!/usr/bin/env python3
"""
Diagnostic: Signal Pipeline Analysis (Read-Only)

Runs through all sessions and reports:
  1. Day type distribution (histogram)
  2. Per-strategy signal blocking report (which gate kills each signal)
  3. Prior VA data availability
  4. IB extension range histogram
  5. Overnight/London/Asia level availability

No code changes — pure read-only diagnostic to calibrate subsequent work.

Usage:
    python scripts/diagnostic_signal_pipeline.py
    python scripts/diagnostic_signal_pipeline.py --instrument ES
"""

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.config.constants import IB_BARS_1MIN
from rockit_core.data.features import compute_all_features
from rockit_core.data.manager import SessionDataManager
from rockit_core.strategies.day_type import classify_day_type, classify_trend_strength


def parse_args():
    parser = argparse.ArgumentParser(description="Diagnostic signal pipeline analysis")
    parser.add_argument("--instrument", "-i", default="NQ", choices=["NQ", "ES", "YM"])
    parser.add_argument("--no-merge", action="store_true")
    return parser.parse_args()


def analyze_day_types(df: pd.DataFrame):
    """Analyze day type distribution across sessions."""
    print("\n" + "=" * 70)
    print("1. DAY TYPE DISTRIBUTION")
    print("=" * 70)

    day_type_counts = Counter()
    extension_ranges = []
    ib_ranges = []

    for session_date, session_df in df.groupby('session_date'):
        if len(session_df) < IB_BARS_1MIN:
            continue

        ib_data = session_df.head(IB_BARS_1MIN)
        ib_high = ib_data['high'].max()
        ib_low = ib_data['low'].min()
        ib_range = ib_high - ib_low

        if ib_range <= 0:
            continue

        ib_ranges.append(ib_range)

        # Use session close for final classification
        session_close = session_df['close'].iloc[-1]
        ib_mid = (ib_high + ib_low) / 2

        if session_close > ib_mid:
            ext = (session_close - ib_mid) / ib_range
        else:
            ext = (ib_mid - session_close) / ib_range

        extension_ranges.append(ext)
        strength = classify_trend_strength(ext)

        if session_close > ib_high:
            ib_dir = 'BULL'
        elif session_close < ib_low:
            ib_dir = 'BEAR'
        else:
            ib_dir = 'INSIDE'

        day_type = classify_day_type(ib_high, ib_low, session_close, ib_dir, strength)
        day_type_counts[day_type.value] += 1

    total = sum(day_type_counts.values())
    print(f"\nTotal sessions: {total}")
    print(f"\n{'Day Type':25s} {'Count':>6s} {'Pct':>6s}")
    print("-" * 40)
    for dt, count in sorted(day_type_counts.items(), key=lambda x: -x[1]):
        print(f"  {dt:23s} {count:6d} {count/total*100:5.1f}%")

    # Extension histogram
    print(f"\n--- IB Extension Distribution ---")
    bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0, 1.5, 2.0, 5.0]
    hist, _ = np.histogram(extension_ranges, bins=bins)
    for i in range(len(bins) - 1):
        bar = "#" * int(hist[i] / max(1, max(hist)) * 40)
        pct = hist[i] / total * 100
        label = f"{bins[i]:.1f}-{bins[i+1]:.1f}x"
        print(f"  {label:12s} {hist[i]:4d} ({pct:5.1f}%) {bar}")

    # Neutral zone analysis
    neutral_ext = [e for e in extension_ranges if 0.2 <= e < 0.5]
    print(f"\n  NEUTRAL ZONE (0.2-0.5x): {len(neutral_ext)} sessions ({len(neutral_ext)/total*100:.1f}%)")
    print(f"  — These sessions get no strategy signals under current day type rules")

    # IB range stats
    print(f"\n--- IB Range Stats ---")
    print(f"  Median: {np.median(ib_ranges):.1f} pts")
    print(f"  Mean:   {np.mean(ib_ranges):.1f} pts")
    print(f"  P10:    {np.percentile(ib_ranges, 10):.1f} pts")
    print(f"  P90:    {np.percentile(ib_ranges, 90):.1f} pts")
    print(f"  Sessions with IB > 400: {sum(1 for r in ib_ranges if r > 400)}")


def analyze_prior_va(df: pd.DataFrame):
    """Check prior VA data availability."""
    print("\n" + "=" * 70)
    print("2. PRIOR VALUE AREA AVAILABILITY")
    print("=" * 70)

    sessions = sorted(df['session_date'].unique())
    has_va = 0
    no_va = 0
    open_outside = 0

    for session_date in sessions:
        session_df = df[df['session_date'] == session_date]
        if len(session_df) < IB_BARS_1MIN:
            continue

        last_ib = session_df.iloc[IB_BARS_1MIN - 1]
        vah = last_ib.get('prior_va_vah', None)
        val_price = last_ib.get('prior_va_val', None)

        if vah is not None and not pd.isna(vah) and val_price is not None and not pd.isna(val_price):
            has_va += 1
            open_price = session_df.iloc[0]['open']
            if open_price > vah or open_price < val_price:
                open_outside += 1
        else:
            no_va += 1

    total = has_va + no_va
    print(f"\n  Sessions with prior VA:  {has_va}/{total} ({has_va/total*100:.1f}%)")
    print(f"  Sessions without:        {no_va}/{total}")
    print(f"  Open outside VA:         {open_outside}/{has_va} ({open_outside/has_va*100:.1f}% of VA sessions)")
    print(f"  — These are potential 80P Rule setups")


def analyze_overnight_levels(df: pd.DataFrame):
    """Check overnight/London/Asia level availability."""
    print("\n" + "=" * 70)
    print("3. OVERNIGHT / LONDON / ASIA LEVELS")
    print("=" * 70)

    sessions = sorted(df['session_date'].unique())
    counts = {
        'overnight': 0, 'asia': 0, 'london': 0, 'pdh': 0,
    }

    for session_date in sessions:
        session_df = df[df['session_date'] == session_date]
        if len(session_df) < IB_BARS_1MIN:
            continue

        first_bar = session_df.iloc[0]
        if first_bar.get('overnight_high') is not None and not pd.isna(first_bar.get('overnight_high', np.nan)):
            counts['overnight'] += 1
        if first_bar.get('asia_high') is not None and not pd.isna(first_bar.get('asia_high', np.nan)):
            counts['asia'] += 1
        if first_bar.get('london_high') is not None and not pd.isna(first_bar.get('london_high', np.nan)):
            counts['london'] += 1

    total = len(sessions)
    for name, count in counts.items():
        print(f"  {name:15s}: {count}/{total} sessions ({count/total*100:.1f}%)")


def analyze_strategy_blocking(df: pd.DataFrame):
    """Analyze per-strategy signal blocking (which gates prevent signals)."""
    print("\n" + "=" * 70)
    print("4. STRATEGY SIGNAL BLOCKING ANALYSIS")
    print("=" * 70)

    sessions = sorted(df['session_date'].unique())
    total_sessions = 0

    # B-Day blocking analysis
    bday_blocks = Counter()
    bday_potential = 0

    # 80P blocking analysis
    p80_blocks = Counter()
    p80_potential = 0

    for session_date in sessions:
        session_df = df[df['session_date'] == session_date]
        if len(session_df) < IB_BARS_1MIN:
            continue
        total_sessions += 1

        ib_data = session_df.head(IB_BARS_1MIN)
        ib_high = ib_data['high'].max()
        ib_low = ib_data['low'].min()
        ib_range = ib_high - ib_low
        if ib_range <= 0:
            continue

        ib_mid = (ib_high + ib_low) / 2

        # --- B-Day analysis ---
        # Check if any bar after IB touches IBL
        post_ib = session_df.iloc[IB_BARS_1MIN:]
        ibl_touches = post_ib[post_ib['low'] <= ib_low]

        if len(ibl_touches) > 0:
            bday_potential += 1

            # Check each blocking gate
            session_close = post_ib['close'].iloc[-1] if len(post_ib) > 0 else ib_mid
            if session_close > ib_mid:
                ext = (session_close - ib_mid) / ib_range
            else:
                ext = (ib_mid - session_close) / ib_range

            strength = classify_trend_strength(ext)
            if session_close > ib_high:
                ib_dir = 'BULL'
            elif session_close < ib_low:
                ib_dir = 'BEAR'
            else:
                ib_dir = 'INSIDE'

            day_type = classify_day_type(ib_high, ib_low, session_close, ib_dir, strength)
            if day_type.value != 'b_day':
                bday_blocks['day_type_not_bday'] += 1
            if strength.value != 'weak':
                bday_blocks['strength_not_weak'] += 1
            if ib_range > 400:
                bday_blocks['ib_range_too_wide'] += 1

        # --- 80P analysis ---
        last_ib = session_df.iloc[IB_BARS_1MIN - 1]
        vah = last_ib.get('prior_va_vah', None)
        val_price = last_ib.get('prior_va_val', None)

        if vah is not None and not pd.isna(vah) and val_price is not None and not pd.isna(val_price):
            va_width = vah - val_price
            open_price = session_df.iloc[0]['open']

            if open_price > vah or open_price < val_price:
                p80_potential += 1

                if va_width < 25:
                    p80_blocks['va_width_too_narrow'] += 1

                # Check acceptance: do 2 consecutive 30-min closes land inside VA?
                inside_count = 0
                max_consecutive = 0
                for i in range(IB_BARS_1MIN, len(session_df)):
                    if (i + 1) % 30 == 0:
                        price = session_df.iloc[i]['close']
                        if val_price <= price <= vah:
                            inside_count += 1
                            max_consecutive = max(max_consecutive, inside_count)
                        else:
                            inside_count = 0

                if max_consecutive < 2:
                    p80_blocks['no_30min_acceptance'] += 1

                # Check 5-min acceptance alternative
                inside_5m = 0
                max_consecutive_5m = 0
                for i in range(IB_BARS_1MIN, len(session_df)):
                    if (i + 1) % 5 == 0:
                        price = session_df.iloc[i]['close']
                        if val_price <= price <= vah:
                            inside_5m += 1
                            max_consecutive_5m = max(max_consecutive_5m, inside_5m)
                        else:
                            inside_5m = 0

                if max_consecutive_5m < 2:
                    p80_blocks['no_5min_acceptance'] += 1

    print(f"\n--- B-Day IBL Fade ---")
    print(f"  Sessions with IBL touch: {bday_potential}/{total_sessions}")
    for gate, count in sorted(bday_blocks.items(), key=lambda x: -x[1]):
        print(f"  BLOCKED by {gate}: {count}/{bday_potential} ({count/max(1,bday_potential)*100:.1f}%)")

    print(f"\n--- 80P Rule ---")
    print(f"  Sessions with open outside VA: {p80_potential}")
    for gate, count in sorted(p80_blocks.items(), key=lambda x: -x[1]):
        print(f"  BLOCKED by {gate}: {count}/{p80_potential} ({count/max(1,p80_potential)*100:.1f}%)")


def main():
    args = parse_args()
    instrument = args.instrument.upper()

    print(f"{'=' * 70}")
    print(f"DIAGNOSTIC: SIGNAL PIPELINE ANALYSIS — {instrument}")
    print(f"{'=' * 70}")

    mgr = SessionDataManager(data_dir="data/sessions")

    if not args.no_merge:
        print("Merging latest data from Google Drive...")
        df = mgr.merge_delta(instrument)
    else:
        print("Loading local data (merge skipped)...")
        df = mgr.load(instrument)

    mgr.info(instrument)

    print("\nComputing features...")
    df = compute_all_features(df)

    analyze_day_types(df)
    analyze_prior_va(df)
    analyze_overnight_levels(df)
    analyze_strategy_blocking(df)

    print(f"\n{'=' * 70}")
    print("DIAGNOSTIC COMPLETE — No code changes made")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
