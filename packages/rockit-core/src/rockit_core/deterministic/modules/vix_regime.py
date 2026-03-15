"""
VIX regime classification from CBOE historical data.

Data source: https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv
- 9,000+ daily rows from 1990 to present, updated daily
- Columns: DATE, OPEN, HIGH, LOW, CLOSE

Regime buckets:
  - low:      VIX < 15  (calm, tight stops work)
  - moderate: 15 <= VIX < 20  (normal)
  - elevated: 20 <= VIX < 25  (increased vol, wider stops needed)
  - high:     25 <= VIX < 35  (volatile, trade smaller)
  - extreme:  VIX >= 35  (crisis, reduce exposure)
"""

import os
from pathlib import Path
from typing import Optional

import pandas as pd

# Default path relative to project root
_DEFAULT_VIX_PATH = Path(__file__).resolve().parents[6] / "data" / "vix" / "VIX_History.csv"

# Module-level cache
_vix_df: Optional[pd.DataFrame] = None


def _load_vix_data(csv_path: Optional[str] = None) -> pd.DataFrame:
    """Load and cache VIX daily data from CBOE CSV."""
    global _vix_df
    if _vix_df is not None:
        return _vix_df

    path = Path(csv_path) if csv_path else _DEFAULT_VIX_PATH
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path, parse_dates=['DATE'], encoding='utf-8')
    df['date_str'] = df['DATE'].dt.strftime('%Y-%m-%d')
    df = df.set_index('date_str')
    _vix_df = df
    return df


def clear_cache():
    """Clear the module-level VIX cache (for testing)."""
    global _vix_df
    _vix_df = None


def classify_vix(vix_close: float) -> str:
    """Classify VIX level into regime bucket."""
    if vix_close < 15:
        return 'low'
    elif vix_close < 20:
        return 'moderate'
    elif vix_close < 25:
        return 'elevated'
    elif vix_close < 35:
        return 'high'
    else:
        return 'extreme'


def get_vix_regime(session_date: str, csv_path: Optional[str] = None) -> dict:
    """
    Get VIX data and regime classification for a session date.

    Args:
        session_date: Date string 'YYYY-MM-DD'
        csv_path: Optional path to VIX CSV (uses default if not provided)

    Returns:
        dict with vix_open, vix_high, vix_low, vix_close, vix_regime,
        vix_prior_close, vix_5d_avg, vix_change_pct
    """
    df = _load_vix_data(csv_path)

    result = {
        'vix_open': None,
        'vix_high': None,
        'vix_low': None,
        'vix_close': None,
        'vix_regime': 'unknown',
        'vix_prior_close': None,
        'vix_5d_avg': None,
        'vix_change_pct': None,
    }

    if df.empty:
        return result

    if session_date not in df.index:
        # Try to find the most recent prior date (weekends/holidays)
        all_dates = df['DATE'].sort_values()
        target = pd.to_datetime(session_date)
        prior = all_dates[all_dates <= target]
        if prior.empty:
            return result
        nearest_date = prior.iloc[-1].strftime('%Y-%m-%d')
        if nearest_date not in df.index:
            return result
        row = df.loc[nearest_date]
    else:
        row = df.loc[session_date]

    # Handle duplicate dates (take first row)
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]

    vix_close = float(row['CLOSE'])
    result['vix_open'] = float(row['OPEN'])
    result['vix_high'] = float(row['HIGH'])
    result['vix_low'] = float(row['LOW'])
    result['vix_close'] = vix_close
    result['vix_regime'] = classify_vix(vix_close)

    # Prior close and 5-day average
    sorted_dates = df['DATE'].sort_values()
    target_dt = pd.to_datetime(session_date)
    prior_dates = sorted_dates[sorted_dates < target_dt]

    if len(prior_dates) >= 1:
        prior_date_str = prior_dates.iloc[-1].strftime('%Y-%m-%d')
        if prior_date_str in df.index:
            prior_row = df.loc[prior_date_str]
            if isinstance(prior_row, pd.DataFrame):
                prior_row = prior_row.iloc[0]
            result['vix_prior_close'] = float(prior_row['CLOSE'])
            result['vix_change_pct'] = round(
                (vix_close - result['vix_prior_close']) / result['vix_prior_close'] * 100, 2
            )

    if len(prior_dates) >= 5:
        last_5 = prior_dates.iloc[-5:]
        closes = []
        for dt in last_5:
            ds = dt.strftime('%Y-%m-%d')
            if ds in df.index:
                r = df.loc[ds]
                if isinstance(r, pd.DataFrame):
                    r = r.iloc[0]
                closes.append(float(r['CLOSE']))
        if closes:
            result['vix_5d_avg'] = round(sum(closes) / len(closes), 2)

    return result
