"""
Signal-time TPO snapshot generator.

Thin wrapper around the deterministic TPO profile module that captures
the full TPO structural state at the moment a strategy emits a signal.
This enables post-hoc correlation analysis: "Do trades at LVN entries
with p-shape TPO win more?"

Performance: ~408 trades / 266 sessions = ~1.5 signals/session.
get_tpo_profile() on 60-120 bars is <50ms. Negligible backtest impact.
"""

import pandas as pd


def generate_signal_tpo_snapshot(
    session_bars: pd.DataFrame,
    signal_time: str,
    prior_day: dict | None = None,
) -> dict:
    """Generate TPO snapshot at signal time for trade correlation.

    Args:
        session_bars: All 1-min RTH bars for the session (may have 'timestamp'
            column or DatetimeIndex).
        signal_time: HH:MM format (e.g. '10:35').
        prior_day: Prior day profile levels (poc, vah, val, high, low) for
            naked level analysis.

    Returns:
        dict with TPO structural fields at signal time.
    """
    from rockit_core.deterministic.modules.tpo_profile import get_tpo_profile

    # get_tpo_profile expects a DatetimeIndex — adapt if needed
    df = session_bars.copy()
    if 'timestamp' in df.columns and not isinstance(df.index, pd.DatetimeIndex):
        df = df.set_index(pd.to_datetime(df['timestamp']))

    tpo_result = get_tpo_profile(df, signal_time, prior_day)

    # Extract the fields we want to store alongside trades
    keys = [
        'tpo_shape', 'current_poc', 'current_vah', 'current_val',
        'excess_high', 'excess_low', 'poor_high', 'poor_low',
        'otf_bias', 'width_trend', 'fattening_zone',
        'distributions', 'single_print_ranges',
        'hvn_nodes', 'lvn_nodes', 'period_ranges',
        'otf_sequence', 'naked_levels',
        'rejection_at_high', 'rejection_at_low', 'note',
    ]

    snapshot = {'signal_time': signal_time}
    for key in keys:
        snapshot[key] = tpo_result.get(key)

    return snapshot
