#!/usr/bin/env python3
"""
Diagnose why B-Day, 80P Rule, and OR Acceptance generate 0/few trades.
Runs through all sessions and reports gate-by-gate blocking stats.
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

import numpy as np
import pandas as pd

from rockit_core.config.constants import IB_BARS_1MIN
from rockit_core.data.features import compute_all_features
from rockit_core.strategies.day_type import classify_day_type, classify_trend_strength, TrendStrength
from rockit_core.strategies.day_confidence import DayTypeConfidenceScorer

DATA_DIR = project_root / "data" / "sessions"


def load_data(instrument="NQ"):
    """Load merged session data."""
    files = sorted(DATA_DIR.glob(f"{instrument}_*.csv"))
    if not files:
        print(f"No data files found in {DATA_DIR}")
        sys.exit(1)
    dfs = [pd.read_csv(f) for f in files]
    df = pd.concat(dfs, ignore_index=True)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    if 'session_date' not in df.columns:
        df['session_date'] = df['timestamp'].dt.date
    return df


def diagnose_bday(df: pd.DataFrame):
    """Gate-by-gate diagnosis for B-Day strategy."""
    print("\n" + "=" * 70)
    print("B-DAY STRATEGY DIAGNOSIS")
    print("=" * 70)

    sessions = sorted(df['session_date'].unique())
    ib_range_history = []

    stats = {
        'total_sessions': 0,
        'bars_classified_bday': 0,
        'bars_with_bday_conf_gte_05': 0,
        'sessions_with_bday_bars': 0,
        'regime_low': 0,
        'regime_normal': 0,
        'regime_high': 0,
        'sessions_regime_blocked': 0,
        'sessions_ib_too_wide': 0,
        'sessions_ibl_touched': 0,
        'sessions_ibl_rejected': 0,
        'sessions_delta_positive': 0,
        'sessions_quality_gte_2': 0,
        'b_day_confidences': [],
    }

    for session_date in sessions:
        session_df = df[df['session_date'] == session_date].copy()
        if len(session_df) < IB_BARS_1MIN:
            continue

        stats['total_sessions'] += 1
        ib_df = session_df.head(IB_BARS_1MIN)
        ib_high = ib_df['high'].max()
        ib_low = ib_df['low'].min()
        ib_range = ib_high - ib_low
        ib_mid = (ib_high + ib_low) / 2

        if ib_range <= 0:
            continue

        # Regime classification
        if len(ib_range_history) >= 10:
            median_ib = float(np.median(ib_range_history[-20:]))
            if median_ib < 130:
                regime = 'low'
            elif median_ib < 250:
                regime = 'normal'
            else:
                regime = 'high'
        else:
            regime = 'normal'

        stats[f'regime_{regime}'] += 1

        # Adaptive IB cap
        if len(ib_range_history) >= 5:
            pctl_val = np.percentile(ib_range_history[-20:], 90)
            max_ib = pctl_val * 1.2
        else:
            max_ib = 400.0

        ib_range_history.append(float(ib_range))

        # Confidence scorer
        confidence_scorer = DayTypeConfidenceScorer()
        atr = ib_df.iloc[-1].get('atr14', 0.0) if 'atr14' in ib_df.columns else 0.0
        confidence_scorer.on_session_start(ib_high, ib_low, ib_range, atr)

        post_ib_df = session_df.iloc[IB_BARS_1MIN:]
        if len(post_ib_df) == 0:
            continue

        session_had_bday_bar = False
        session_had_ibl_touch = False
        session_had_ibl_reject = False
        session_had_delta_pos = False
        session_had_quality = False
        session_regime_blocked = (regime == 'low')
        session_ib_too_wide = (ib_range > max_ib)

        if session_regime_blocked:
            stats['sessions_regime_blocked'] += 1
        if session_ib_too_wide:
            stats['sessions_ib_too_wide'] += 1

        for bar_idx in range(len(post_ib_df)):
            bar = post_ib_df.iloc[bar_idx]
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

            day_confidence = confidence_scorer.update(bar, bar_idx)

            if dt.value == 'b_day':
                stats['bars_classified_bday'] += 1
                session_had_bday_bar = True

                bday_conf = day_confidence.b_day
                stats['b_day_confidences'].append(bday_conf)

                if bday_conf >= 0.5:
                    stats['bars_with_bday_conf_gte_05'] += 1

                    # Check IBL touch
                    if bar['low'] <= ib_low:
                        session_had_ibl_touch = True
                        # Check rejection (close above IBL)
                        if current_price > ib_low:
                            session_had_ibl_reject = True
                            delta = bar.get('delta', 0)
                            if pd.isna(delta):
                                delta = 0
                            if delta > 0:
                                session_had_delta_pos = True

        if session_had_bday_bar:
            stats['sessions_with_bday_bars'] += 1
        if session_had_ibl_touch:
            stats['sessions_ibl_touched'] += 1
        if session_had_ibl_reject:
            stats['sessions_ibl_rejected'] += 1
        if session_had_delta_pos:
            stats['sessions_delta_positive'] += 1

    print(f"\n  Total sessions: {stats['total_sessions']}")
    print(f"\n  --- Day Type Classification ---")
    print(f"  Sessions with any B-Day bar: {stats['sessions_with_bday_bars']}")
    print(f"  Total B-Day bars: {stats['bars_classified_bday']}")
    print(f"  B-Day bars with confidence >= 0.5: {stats['bars_with_bday_conf_gte_05']}")

    if stats['b_day_confidences']:
        confs = stats['b_day_confidences']
        print(f"\n  --- B-Day Confidence Distribution ---")
        print(f"  Min: {min(confs):.3f}  Max: {max(confs):.3f}  Mean: {np.mean(confs):.3f}  Median: {np.median(confs):.3f}")
        for threshold in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
            count = sum(1 for c in confs if c >= threshold)
            print(f"  >= {threshold:.1f}: {count} bars ({count/len(confs)*100:.1f}%)")

    print(f"\n  --- Regime Filter ---")
    print(f"  Low vol regime: {stats['regime_low']} sessions")
    print(f"  Normal regime: {stats['regime_normal']} sessions")
    print(f"  High regime: {stats['regime_high']} sessions")
    print(f"  Sessions blocked by regime: {stats['sessions_regime_blocked']}")

    print(f"\n  --- IB Range Cap ---")
    print(f"  Sessions blocked by IB too wide: {stats['sessions_ib_too_wide']}")

    print(f"\n  --- IBL Touch & Rejection ---")
    print(f"  Sessions with IBL touch: {stats['sessions_ibl_touched']}")
    print(f"  Sessions with IBL rejection: {stats['sessions_ibl_rejected']}")
    print(f"  Sessions with delta > 0 at rejection: {stats['sessions_delta_positive']}")


def diagnose_80p(df: pd.DataFrame):
    """Gate-by-gate diagnosis for 80P Rule strategy."""
    print("\n" + "=" * 70)
    print("80P RULE STRATEGY DIAGNOSIS")
    print("=" * 70)

    sessions = sorted(df['session_date'].unique())

    stats = {
        'total_sessions': 0,
        'has_prior_va': 0,
        'va_width_sufficient': 0,
        'opens_outside_va': 0,
        'opens_below_val': 0,
        'opens_above_vah': 0,
        'setup_armed': 0,
        'acceptance_found': 0,
        'limit_filled': 0,
        'va_widths': [],
        'open_vs_va_values': [],
    }

    for session_date in sessions:
        session_df = df[df['session_date'] == session_date].copy()
        if len(session_df) < IB_BARS_1MIN:
            continue

        stats['total_sessions'] += 1
        ib_df = session_df.head(IB_BARS_1MIN)
        last_ib = ib_df.iloc[-1]

        # Check prior VA availability
        prior_vah = last_ib.get('prior_va_vah') if 'prior_va_vah' in ib_df.columns else None
        prior_val = last_ib.get('prior_va_val') if 'prior_va_val' in ib_df.columns else None
        open_vs_va = last_ib.get('open_vs_va') if 'open_vs_va' in ib_df.columns else None

        if prior_vah is not None and prior_val is not None and not pd.isna(prior_vah) and not pd.isna(prior_val):
            stats['has_prior_va'] += 1
            va_width = prior_vah - prior_val
            stats['va_widths'].append(va_width)

            if va_width >= 25:
                stats['va_width_sufficient'] += 1

                if open_vs_va is not None:
                    stats['open_vs_va_values'].append(str(open_vs_va))
                    if open_vs_va == 'BELOW_VAL':
                        stats['opens_below_val'] += 1
                        stats['opens_outside_va'] += 1
                        stats['setup_armed'] += 1
                    elif open_vs_va == 'ABOVE_VAH':
                        stats['opens_above_vah'] += 1
                        stats['opens_outside_va'] += 1
                        stats['setup_armed'] += 1
                    else:
                        pass  # INSIDE_VA
                else:
                    stats['open_vs_va_values'].append('MISSING')
        else:
            pass

    print(f"\n  Total sessions: {stats['total_sessions']}")
    print(f"\n  --- Prior VA Data ---")
    print(f"  Sessions with prior VA data: {stats['has_prior_va']}")
    print(f"  Sessions without prior VA: {stats['total_sessions'] - stats['has_prior_va']}")

    if stats['va_widths']:
        vaw = stats['va_widths']
        print(f"\n  --- VA Width Distribution ---")
        print(f"  Min: {min(vaw):.1f}  Max: {max(vaw):.1f}  Mean: {np.mean(vaw):.1f}  Median: {np.median(vaw):.1f}")
        print(f"  VA width >= 25: {stats['va_width_sufficient']} sessions")

    print(f"\n  --- Open vs VA ---")
    if stats['open_vs_va_values']:
        from collections import Counter
        c = Counter(stats['open_vs_va_values'])
        for val, count in c.most_common():
            print(f"  {val}: {count}")
    print(f"  Opens outside VA (ABOVE_VAH or BELOW_VAL): {stats['opens_outside_va']}")
    print(f"  Setup armed: {stats['setup_armed']}")

    # Now for armed sessions, check acceptance and limit fill
    if stats['setup_armed'] > 0:
        print(f"\n  --- Detailed scan of armed sessions ---")
        _scan_80p_armed_sessions(df, sessions)


def _scan_80p_armed_sessions(df, sessions):
    """For each session where 80P is armed, check acceptance and fill."""
    accept_count = 0
    fill_count = 0
    armed_details = []

    for session_date in sessions:
        session_df = df[df['session_date'] == session_date].copy()
        if len(session_df) < IB_BARS_1MIN:
            continue

        ib_df = session_df.head(IB_BARS_1MIN)
        last_ib = ib_df.iloc[-1]

        prior_vah = last_ib.get('prior_va_vah') if 'prior_va_vah' in ib_df.columns else None
        prior_val = last_ib.get('prior_va_val') if 'prior_va_val' in ib_df.columns else None
        open_vs_va = last_ib.get('open_vs_va') if 'open_vs_va' in ib_df.columns else None

        if (prior_vah is None or prior_val is None or pd.isna(prior_vah) or pd.isna(prior_val)):
            continue

        va_width = prior_vah - prior_val
        if va_width < 25:
            continue

        direction = None
        if open_vs_va == 'BELOW_VAL':
            direction = 'LONG'
        elif open_vs_va == 'ABOVE_VAH':
            direction = 'SHORT'
        else:
            continue

        # Now simulate acceptance check
        post_ib_df = session_df.iloc[IB_BARS_1MIN:]
        if len(post_ib_df) == 0:
            continue

        # 5-min acceptance: 2 consecutive 5-min closes inside VA
        consecutive = 0
        acceptance_bar = -1
        for bar_idx in range(len(post_ib_df)):
            is_5m_end = ((bar_idx + 1) % 5 == 0)
            if not is_5m_end:
                continue
            close = post_ib_df.iloc[bar_idx]['close']
            if prior_val <= close <= prior_vah:
                consecutive += 1
            else:
                consecutive = 0

            if consecutive >= 2:
                acceptance_bar = bar_idx
                break

        got_acceptance = acceptance_bar >= 0
        if got_acceptance:
            accept_count += 1

        # Check limit fill
        got_fill = False
        if got_acceptance:
            limit_price = prior_val + va_width * 0.5 if direction == 'LONG' else prior_vah - va_width * 0.5
            fill_start = acceptance_bar + 1
            fill_end = min(fill_start + 30, len(post_ib_df))
            for i in range(fill_start, fill_end):
                bar = post_ib_df.iloc[i]
                if direction == 'LONG' and bar['low'] <= limit_price:
                    got_fill = True
                    break
                elif direction == 'SHORT' and bar['high'] >= limit_price:
                    got_fill = True
                    break

        if got_fill:
            fill_count += 1

        armed_details.append({
            'date': str(session_date),
            'direction': direction,
            'vah': round(prior_vah, 1),
            'val': round(prior_val, 1),
            'va_width': round(va_width, 1),
            'acceptance': got_acceptance,
            'limit_fill': got_fill,
        })

    print(f"  Armed sessions: {len(armed_details)}")
    print(f"  Got 5-min acceptance: {accept_count}")
    print(f"  Got limit fill: {fill_count}")

    # Show first 10 armed sessions for debugging
    print(f"\n  --- First 10 armed sessions ---")
    for d in armed_details[:10]:
        status = "FILL" if d['limit_fill'] else ("ACCEPT" if d['acceptance'] else "NO_ACCEPT")
        print(f"  {d['date']} | {d['direction']:5s} | VA: {d['val']:.0f}-{d['vah']:.0f} ({d['va_width']:.0f}w) | {status}")


def diagnose_or_acceptance(df: pd.DataFrame):
    """Gate-by-gate diagnosis for OR Acceptance v3 strategy."""
    print("\n" + "=" * 70)
    print("OR ACCEPTANCE v3 STRATEGY DIAGNOSIS")
    print("=" * 70)

    sessions = sorted(df['session_date'].unique())

    stats = {
        'total_sessions': 0,
        'has_ib_bars_gte_30': 0,
        'has_overnight_levels': 0,
        'has_london_levels': 0,
        'has_asia_levels': 0,
        'has_pdh_pdl': 0,
        'has_any_levels': 0,
        'both_filtered': 0,
        'long_acceptance': 0,
        'short_acceptance': 0,
        'long_fill': 0,
        'short_fill': 0,
    }

    for session_date in sessions:
        session_df = df[df['session_date'] == session_date].copy()
        if len(session_df) < IB_BARS_1MIN:
            continue

        stats['total_sessions'] += 1
        ib_df = session_df.head(IB_BARS_1MIN)
        last_ib = ib_df.iloc[-1]

        if len(ib_df) >= 30:
            stats['has_ib_bars_gte_30'] += 1

        # Check level availability
        has_overnight = ('overnight_high' in ib_df.columns and
                        not pd.isna(last_ib.get('overnight_high', np.nan)))
        has_london = ('london_high' in ib_df.columns and
                     not pd.isna(last_ib.get('london_high', np.nan)))
        has_asia = ('asia_high' in ib_df.columns and
                   not pd.isna(last_ib.get('asia_high', np.nan)))
        has_pdh = ('prior_session_high' in session_df.columns or
                  last_ib.get('pdh') is not None if 'pdh' in ib_df.columns else False)

        if has_overnight:
            stats['has_overnight_levels'] += 1
        if has_london:
            stats['has_london_levels'] += 1
        if has_asia:
            stats['has_asia_levels'] += 1
        if has_pdh:
            stats['has_pdh_pdl'] += 1
        if any([has_overnight, has_london, has_asia, has_pdh]):
            stats['has_any_levels'] += 1

    print(f"\n  Total sessions: {stats['total_sessions']}")
    print(f"\n  --- Level Availability ---")
    print(f"  Has IB bars >= 30: {stats['has_ib_bars_gte_30']}")
    print(f"  Has overnight levels: {stats['has_overnight_levels']}")
    print(f"  Has London levels: {stats['has_london_levels']}")
    print(f"  Has Asia levels: {stats['has_asia_levels']}")
    print(f"  Has PDH/PDL: {stats['has_pdh_pdl']}")
    print(f"  Has ANY reference levels: {stats['has_any_levels']}")


def main():
    print("Loading data...")
    df = load_data("NQ")
    print(f"Loaded {len(df)} rows")

    print("\nComputing features...")
    df = compute_all_features(df)

    diagnose_bday(df)
    diagnose_80p(df)
    diagnose_or_acceptance(df)


if __name__ == "__main__":
    main()
