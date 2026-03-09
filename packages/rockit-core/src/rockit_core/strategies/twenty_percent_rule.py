"""
Strategy: 20P IB Extension Rule — Continuation Entry with Structure Stops

When price breaks beyond the Initial Balance, continuation is likely.
Wait for 3 consecutive 5-min closes beyond IB boundary for acceptance,
then enter in the direction of the extension.

Study targets (strategy-studies/20p-rule/ v2 — structure stops):
  - Frequency: 3.7 trades/month
  - Win Rate: 45.5%
  - Profit Factor: 1.78
  - Monthly P&L: $496 (5 MNQ)
  - Risk/trade: ~32 pts median (2x ATR)
  - Clean exits: 24 stops / 20 targets / 0 EOD

Entry: 3x consecutive 5-min closes beyond IB boundary
  - LONG: 3 consecutive 5-min closes above IBH
  - SHORT: 3 consecutive 5-min closes below IBL
Stop: 2x ATR(14) from entry
Target: 2R (2x the stop distance = 4x ATR from entry)
Max 1 entry per session.
"""

from typing import Optional, List
from datetime import time as _time
import pandas as pd

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal

# ── Parameters ────────────────────────────────────────────────
ACCEPT_5M_BARS = 3               # 3 consecutive 5-min closes for acceptance
ATR_PERIOD = 14
ATR_STOP_MULT = 2.0              # Stop = 2x ATR from entry
TARGET_R_MULTIPLE = 2.0           # 2R target
MAX_ENTRIES_PER_SESSION = 1


def _compute_atr14(df: pd.DataFrame, n: int = ATR_PERIOD) -> float:
    """Compute ATR(14) from OHLC bars."""
    if len(df) < 3:
        return float((df['high'] - df['low']).mean()) if len(df) > 0 else 20.0
    h = df['high']
    l = df['low']
    pc = df['close'].shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(n, min_periods=3).mean().iloc[-1]
    return float(atr) if not pd.isna(atr) else float((h - l).mean())


class TwentyPercentRule(StrategyBase):
    """
    20P Rule: IB Extension Continuation with structure-based stops.

    Watches for 3 consecutive 5-min closes beyond IB boundary.
    When acceptance confirmed, enters in the extension direction
    with 2x ATR stop and 2R target.
    """

    @property
    def name(self) -> str:
        return "20P IB Extension"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # Can fire on any day type

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._ib_high = ib_high
        self._ib_low = ib_low
        self._ib_range = ib_range
        self._triggered = False
        self._entry_count = 0

        # 5-min acceptance tracking (both directions)
        self._consec_above = 0
        self._consec_below = 0
        self._last_5m_bar = -1

        # ATR from IB bars for stop computation
        ib_bars = session_context.get('ib_bars')
        if ib_bars is not None and len(ib_bars) > 0:
            self._atr14 = _compute_atr14(ib_bars)
        else:
            self._atr14 = session_context.get('atr14', 20.0)

        # Prerequisite: session must open outside prior VA
        # Open > prior VAH → LONG only; Open < prior VAL → SHORT only
        self._allowed_direction = None  # None = don't trade this session
        prior_vah = session_context.get('prior_va_vah')
        prior_val = session_context.get('prior_va_val')

        if ib_bars is not None and len(ib_bars) > 0 and prior_vah is not None and prior_val is not None:
            session_open = ib_bars.iloc[0]['open']
            if not pd.isna(prior_vah) and not pd.isna(prior_val) and not pd.isna(session_open):
                if session_open > prior_vah:
                    self._allowed_direction = 'LONG'
                elif session_open < prior_val:
                    self._allowed_direction = 'SHORT'

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        if self._triggered or self._entry_count >= MAX_ENTRIES_PER_SESSION:
            return None

        # Session must open outside prior VA
        if self._allowed_direction is None:
            return None

        # 13:00 ET entry cutoff
        bar_time = session_context.get('bar_time')
        if bar_time and bar_time >= _time(13, 0):
            return None

        current_price = bar['close']

        # Only check at 5-min bar ends (every 5th 1-min bar)
        is_5m_end = ((bar_index + 1) % 5 == 0)
        if not is_5m_end or bar_index <= self._last_5m_bar:
            return None

        self._last_5m_bar = bar_index

        # Track consecutive 5-min closes beyond IB boundary
        if current_price > self._ib_high:
            self._consec_above += 1
            self._consec_below = 0
        elif current_price < self._ib_low:
            self._consec_below += 1
            self._consec_above = 0
        else:
            self._consec_above = 0
            self._consec_below = 0

        # Check for 3-bar acceptance
        if self._consec_above >= ACCEPT_5M_BARS:
            direction = 'LONG'
        elif self._consec_below >= ACCEPT_5M_BARS:
            direction = 'SHORT'
        else:
            return None

        # Direction must match gap (open outside prior VA)
        if direction != self._allowed_direction:
            return None

        # Compute stop and target
        entry_price = current_price
        risk = ATR_STOP_MULT * self._atr14

        if risk <= 0:
            return None

        if direction == 'LONG':
            stop_price = entry_price - risk
            target_price = entry_price + TARGET_R_MULTIPLE * risk
        else:
            stop_price = entry_price + risk
            target_price = entry_price - TARGET_R_MULTIPLE * risk

        self._triggered = True
        self._entry_count += 1

        return Signal(
            timestamp=bar.get('timestamp', bar.name) if hasattr(bar, 'name') else bar.get('timestamp'),
            direction=direction,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            strategy_name=self.name,
            setup_type=f'20P_IB_EXT_{direction}',
            day_type=session_context.get('day_type', ''),
            trend_strength=session_context.get('trend_strength', ''),
            confidence='high',
            metadata={
                'ib_range': self._ib_range,
                'atr14': self._atr14,
                'acceptance_bars': ACCEPT_5M_BARS,
                'risk_pts': risk,
            },
        )
