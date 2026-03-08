"""Combo backtest report generation."""

from __future__ import annotations

from typing import List

import pandas as pd

from rockit_core.execution.combo_runner import ComboResult


def combo_report(results: List[ComboResult]) -> pd.DataFrame:
    """Build a comparison DataFrame from ComboResults.

    Returns a DataFrame with columns:
        Strategy, Stop, Target, Trades, WR%, PF, Net P&L, Avg R
    Sorted by Net P&L descending.
    """
    rows = []
    for r in results:
        rows.append({
            'Strategy': r.strategy_name,
            'Stop': r.stop_model_name,
            'Target': r.target_model_name,
            'Trades': r.trades,
            'WR%': round(r.win_rate, 1),
            'PF': round(r.profit_factor, 2),
            'Net P&L': round(r.net_pnl, 2),
            'Avg R': round(r.avg_r, 2),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values('Net P&L', ascending=False).reset_index(drop=True)
    return df
