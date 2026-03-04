"""
Overnight / Pre-market session level computation.

Computes key reference levels from ETH (extended trading hours) data
for use by Opening Range strategies (OR Reversal, OR Acceptance).

Session boundaries (US Eastern):
  - Asia:    18:00 - 02:00 ET (prior evening through early morning)
  - London:  03:00 - 09:30 ET (London open through US RTH open)
  - Overnight (full ETH): 18:00 - 09:30 ET
  - RTH:     09:30 - 16:00 ET
"""

from datetime import time
from typing import Optional

import pandas as pd

# Session boundaries (US Eastern)
ASIA_START = time(18, 0)    # Prior day evening
ASIA_END = time(2, 0)       # Early morning

LONDON_START = time(3, 0)
LONDON_END = time(9, 30)

ETH_START = time(18, 0)     # Prior day
RTH_START = time(9, 30)


def compute_session_levels(session_df: pd.DataFrame) -> dict:
    """Compute overnight, Asia, and London session levels from ETH data.

    Args:
        session_df: DataFrame with all bars for one session_date
                    (including ETH bars starting from prior day 18:00).
                    Must have 'timestamp', 'high', 'low' columns.

    Returns:
        dict with keys:
            overnight_high, overnight_low,
            asia_high, asia_low,
            london_high, london_low,
            pdh, pdl  (prior day RTH high/low — approximated from full session)
    """
    if 'timestamp' not in session_df.columns or len(session_df) == 0:
        return {}

    ts = session_df['timestamp']
    bar_times = ts.dt.time

    # Overnight = all bars before RTH (18:00 previous day -> 09:30)
    # Asia = 18:00 -> 02:00
    # London = 03:00 -> 09:30
    is_pre_rth = bar_times < RTH_START

    # Asia: bars from 18:00+ (previous day) or 00:00-02:00 (current day)
    is_asia = (bar_times >= ASIA_START) | (bar_times < ASIA_END)

    # London: 03:00-09:30
    is_london = (bar_times >= LONDON_START) & (bar_times < LONDON_END)

    levels = {}

    # Overnight levels (all pre-RTH bars)
    overnight = session_df[is_pre_rth]
    if len(overnight) > 0:
        levels['overnight_high'] = float(overnight['high'].max())
        levels['overnight_low'] = float(overnight['low'].min())
    else:
        levels['overnight_high'] = None
        levels['overnight_low'] = None

    # Asia levels
    asia = session_df[is_asia]
    if len(asia) > 0:
        levels['asia_high'] = float(asia['high'].max())
        levels['asia_low'] = float(asia['low'].min())
    else:
        levels['asia_high'] = None
        levels['asia_low'] = None

    # London levels
    london = session_df[is_london]
    if len(london) > 0:
        levels['london_high'] = float(london['high'].max())
        levels['london_low'] = float(london['low'].min())
    else:
        levels['london_high'] = None
        levels['london_low'] = None

    return levels


def add_overnight_levels(df: pd.DataFrame) -> pd.DataFrame:
    """Add overnight level columns to the DataFrame.

    Computes per-session overnight/Asia/London levels and merges them
    as columns so they're available in session_context during backtest.
    """
    if 'session_date' not in df.columns or 'timestamp' not in df.columns:
        return df

    df = df.copy()

    level_cols = [
        'overnight_high', 'overnight_low',
        'asia_high', 'asia_low',
        'london_high', 'london_low',
    ]
    for col in level_cols:
        df[col] = None

    for session_date in df['session_date'].unique():
        mask = df['session_date'] == session_date
        session_df = df[mask]
        levels = compute_session_levels(session_df)

        for col in level_cols:
            if col in levels and levels[col] is not None:
                df.loc[mask, col] = levels[col]

    return df
