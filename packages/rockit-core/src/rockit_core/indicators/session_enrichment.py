"""
Session Context Enrichment — pre-compute per-session features for strategies.
=============================================================================

Adds derived data (single prints, poor extremes) to session context
without modifying the core backtest engine. Called during feature computation.
"""

from typing import Optional

import pandas as pd

from rockit_core.indicators.single_prints import detect_single_print_zones
from rockit_core.indicators.poor_extremes import detect_poor_extremes


def enrich_prior_session_data(
    df: pd.DataFrame,
    tick_size: float = 0.25,
) -> dict[str, dict]:
    """
    Pre-compute per-session enrichment data (single prints, poor extremes)
    mapped to the NEXT session (since strategies use prior-session data).

    Returns:
        Dict mapping session_date_str -> {
            'single_prints': list[dict],  # zones from prior session
            'poor_high': bool,
            'poor_low': bool,
            'session_high': float,
            'session_low': float,
        }
    """
    from datetime import time as _time

    sessions = sorted(df["session_date"].unique())
    result: dict[str, dict] = {}

    for i in range(1, len(sessions)):
        current_session = sessions[i]
        prior_session = sessions[i - 1]

        # Get prior session RTH bars
        prior_bars = df[df["session_date"] == prior_session].copy()
        if "timestamp" in prior_bars.columns:
            bar_times = pd.to_datetime(prior_bars["timestamp"]).dt.time
            rth_mask = (bar_times >= _time(9, 30)) & (bar_times < _time(16, 0))
            prior_bars = prior_bars[rth_mask]

        if prior_bars.empty:
            continue

        # Get prior VA for location classification
        vah = prior_bars.iloc[-1].get("prior_va_vah") if "prior_va_vah" in prior_bars.columns else None
        val = prior_bars.iloc[-1].get("prior_va_val") if "prior_va_val" in prior_bars.columns else None

        # Detect single print zones
        zones = detect_single_print_zones(
            prior_bars,
            tick_size=tick_size,
            vah=float(vah) if vah is not None and pd.notna(vah) else None,
            val=float(val) if val is not None and pd.notna(val) else None,
            min_zone_ticks=10,
        )

        # Detect poor extremes
        poor = detect_poor_extremes(prior_bars, tick_size=tick_size)

        current_key = str(current_session)
        result[current_key] = {
            "single_prints": zones,
            "poor_high": poor.get("poor_high", False),
            "poor_low": poor.get("poor_low", False),
            "prior_poor_high_level": poor.get("session_high") if poor.get("poor_high") else None,
            "prior_poor_low_level": poor.get("session_low") if poor.get("poor_low") else None,
            "high_quality_score": poor.get("high_quality_score", 0.0),
            "low_quality_score": poor.get("low_quality_score", 0.0),
        }

    return result
