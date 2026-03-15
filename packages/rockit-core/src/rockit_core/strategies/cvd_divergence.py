"""
Strategy: CVD Divergence — Mean Reversion at Structural Edges

CVD (Cumulative Volume Delta) divergence occurs when price makes a new
high/low but CVD does not confirm. This signals exhaustion — buyers/sellers
are running out of steam at that extreme.

KEY INSIGHT: CVD divergence only works on balance/neutral days at VALUE AREA
EDGES. On trend days, divergence is noise — trend overwhelms the signal.

Detection Logic:
  1. Track rolling price highs/lows and CVD highs/lows over a lookback window
  2. Bearish divergence: price makes new high, CVD makes lower high
  3. Bullish divergence: price makes new low, CVD makes higher low
  4. Must be near a structural edge (VAH, VAL, IB H/L, PDH/PDL)
  5. Day type filter: block trend days

Filters:
  - Day type: allow balance, neutral, b_day, p_day; block trend/super_trend
  - Edge proximity: within EDGE_PROXIMITY_PTS of VAH/VAL/IBH/IBL/PDH/PDL
  - Optional: reversal bar confirmation (close opposite to divergence direction)
  - Entry cutoff: 14:00 ET (need time for mean reversion to develop)
  - Max 1 entry per session

Previous results (no filters): 19.4% WR, PF 0.78
Study best: 21.2% WR, PF 5.05 (few trades, extreme R:R)
"""

from datetime import time as _time
from typing import Optional, List
import pandas as pd
import numpy as np

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal


# ── CVD Divergence Constants ──────────────────────────────────
CVD_LOOKBACK = 20                  # Bars to look back for divergence detection
EDGE_PROXIMITY_PTS = 10.0          # Points proximity to structural edge
ENTRY_CUTOFF = _time(14, 0)        # No new entries after 2 PM ET
MAX_ENTRIES_PER_SESSION = 1
STOP_ATR_MULT = 2.0                # Stop = 2x ATR from entry
MIN_RISK_PTS = 5.0                 # Minimum risk in points

# Day types that allow CVD divergence trading
ALLOWED_DAY_TYPES = {'b_day', 'neutral', 'p_day'}
# Day types that block trading (trend overwhelms divergence)
BLOCKED_DAY_TYPES = {'trend_up', 'trend_down', 'super_trend_up', 'super_trend_down'}

# Target modes
TARGET_2R = '2R'
TARGET_PRIOR_POC = 'prior_poc'
TARGET_VWAP = 'vwap'


class CVDDivergenceStrategy(StrategyBase):
    """
    CVD Divergence: fade exhaustion at structural edges on balance days.

    Detects price/CVD divergence near VAH/VAL/IBH/IBL, enters mean reversion
    trade expecting price to rotate back toward value.
    """

    def __init__(
        self,
        target_mode: str = TARGET_2R,
        require_reversal_bar: bool = False,
        use_edge_filter: bool = True,
        use_day_type_filter: bool = True,
        edge_proximity: float = EDGE_PROXIMITY_PTS,
    ):
        self._target_mode = target_mode
        self._require_reversal_bar = require_reversal_bar
        self._use_edge_filter = use_edge_filter
        self._use_day_type_filter = use_day_type_filter
        self._edge_proximity = edge_proximity

    @property
    def name(self) -> str:
        return "CVD Divergence"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types — we filter internally for dynamic classification

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._ib_high = ib_high
        self._ib_low = ib_low
        self._ib_range = ib_range
        self._ib_mid = (ib_high + ib_low) / 2

        # Structural levels for edge detection
        self._prior_vah = session_context.get('prior_va_vah') or session_context.get('prior_va_high')
        self._prior_val = session_context.get('prior_va_val') or session_context.get('prior_va_low')
        self._prior_poc = session_context.get('prior_va_poc')
        self._pdh = session_context.get('pdh') or session_context.get('prior_session_high')
        self._pdl = session_context.get('pdl') or session_context.get('prior_session_low')

        # Clean NaN values
        for attr in ('_prior_vah', '_prior_val', '_prior_poc', '_pdh', '_pdl'):
            val = getattr(self, attr)
            if val is not None and isinstance(val, float) and pd.isna(val):
                setattr(self, attr, None)

        # ATR for stops
        self._atr = session_context.get('atr14', 20.0)
        if self._atr is None or (isinstance(self._atr, float) and pd.isna(self._atr)):
            self._atr = 20.0

        # VWAP for target
        self._vwap = session_context.get('vwap')

        # State tracking
        self._signal_fired = False
        self._entry_count = 0

        # Rolling price/CVD tracking
        self._price_highs = []
        self._price_lows = []
        self._cvd_at_highs = []
        self._cvd_at_lows = []
        self._cvd_series = []
        self._bar_count = 0

        # Reversal bar state
        self._divergence_detected = None  # 'LONG' or 'SHORT'
        self._divergence_entry = None
        self._divergence_edge = None

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        if self._entry_count >= MAX_ENTRIES_PER_SESSION:
            return None

        # Time gate
        bar_time = session_context.get('bar_time')
        if bar_time and bar_time >= ENTRY_CUTOFF:
            return None

        close = bar['close']
        high = bar['high']
        low = bar['low']

        # Day type filter (dynamic — checked each bar as day type can change)
        if self._use_day_type_filter:
            day_type = session_context.get('day_type', '')
            if day_type in BLOCKED_DAY_TYPES:
                return None
            # On first bars, day_type might be neutral anyway; let it through

        # Update VWAP
        if 'vwap' in bar.index:
            self._vwap = bar['vwap']

        # Get cumulative delta
        delta = bar.get('delta', bar.get('vol_delta', 0))
        if pd.isna(delta):
            delta = 0
        cum_delta = sum(self._cvd_series) + delta
        self._cvd_series.append(delta)

        self._bar_count += 1

        # Track price extremes and CVD at those extremes
        self._price_highs.append(high)
        self._price_lows.append(low)
        self._cvd_at_highs.append(cum_delta if high >= max(self._price_highs[-CVD_LOOKBACK:]) else None)
        self._cvd_at_lows.append(cum_delta if low <= min(self._price_lows[-CVD_LOOKBACK:]) else None)

        # Need enough bars for lookback
        if self._bar_count < 5:
            return None

        # === Check for reversal bar confirmation ===
        if self._require_reversal_bar and self._divergence_detected is not None:
            signal = self._check_reversal_bar(bar, bar_index, session_context, close)
            if signal:
                return signal
            return None

        # === Detect CVD Divergence ===
        lookback = min(CVD_LOOKBACK, len(self._price_highs))

        # Recent price highs and lows
        recent_highs = self._price_highs[-lookback:]
        recent_lows = self._price_lows[-lookback:]

        # --- Bearish Divergence: price new high, CVD lower high ---
        if high >= max(recent_highs):
            # Find previous high's CVD
            prev_cvd_high = self._find_prev_cvd_at_high(lookback)
            if prev_cvd_high is not None and cum_delta < prev_cvd_high:
                # Bearish divergence detected — potential SHORT
                edge_name = self._check_edge_proximity(close, 'SHORT')
                if edge_name is not None or not self._use_edge_filter:
                    if self._require_reversal_bar:
                        self._divergence_detected = 'SHORT'
                        self._divergence_entry = close
                        self._divergence_edge = edge_name
                    else:
                        return self._create_signal(
                            bar, bar_index, session_context, 'SHORT',
                            close, edge_name or 'NO_EDGE',
                        )

        # --- Bullish Divergence: price new low, CVD higher low ---
        if low <= min(recent_lows):
            prev_cvd_low = self._find_prev_cvd_at_low(lookback)
            if prev_cvd_low is not None and cum_delta > prev_cvd_low:
                # Bullish divergence detected — potential LONG
                edge_name = self._check_edge_proximity(close, 'LONG')
                if edge_name is not None or not self._use_edge_filter:
                    if self._require_reversal_bar:
                        self._divergence_detected = 'LONG'
                        self._divergence_entry = close
                        self._divergence_edge = edge_name
                    else:
                        return self._create_signal(
                            bar, bar_index, session_context, 'LONG',
                            close, edge_name or 'NO_EDGE',
                        )

        return None

    def _find_prev_cvd_at_high(self, lookback: int) -> Optional[float]:
        """Find the CVD value at the previous price high within lookback."""
        # Look for the second-highest high in the lookback window
        highs = self._price_highs[-(lookback + 1):-1]  # Exclude current bar
        cvds_at_h = self._cvd_at_highs[-(lookback + 1):-1]

        best_cvd = None
        best_high = -float('inf')
        for i, (h, cvd) in enumerate(zip(highs, cvds_at_h)):
            if cvd is not None and h > best_high:
                best_high = h
                best_cvd = cvd

        return best_cvd

    def _find_prev_cvd_at_low(self, lookback: int) -> Optional[float]:
        """Find the CVD value at the previous price low within lookback."""
        lows = self._price_lows[-(lookback + 1):-1]
        cvds_at_l = self._cvd_at_lows[-(lookback + 1):-1]

        best_cvd = None
        best_low = float('inf')
        for i, (l, cvd) in enumerate(zip(lows, cvds_at_l)):
            if cvd is not None and l < best_low:
                best_low = l
                best_cvd = cvd

        return best_cvd

    def _check_edge_proximity(self, price: float, direction: str) -> Optional[str]:
        """
        Check if price is near a structural edge.

        For SHORT: look for proximity to highs (VAH, IBH, PDH)
        For LONG: look for proximity to lows (VAL, IBL, PDL)
        """
        prox = self._edge_proximity

        if direction == 'SHORT':
            candidates = [
                ('VAH', self._prior_vah),
                ('IBH', self._ib_high),
                ('PDH', self._pdh),
            ]
        else:  # LONG
            candidates = [
                ('VAL', self._prior_val),
                ('IBL', self._ib_low),
                ('PDL', self._pdl),
            ]

        closest_name = None
        closest_dist = float('inf')

        for name, level in candidates:
            if level is None:
                continue
            dist = abs(price - level)
            if dist <= prox and dist < closest_dist:
                closest_dist = dist
                closest_name = name

        return closest_name

    def _check_reversal_bar(self, bar, bar_index, session_context, close) -> Optional[Signal]:
        """
        Wait for reversal bar confirmation after divergence detected.

        Reversal bar: close in the opposite direction of the divergence extreme.
        - For SHORT divergence (at high): need a bar that closes below its open
        - For LONG divergence (at low): need a bar that closes above its open
        """
        bar_open = bar.get('open', close)
        if pd.isna(bar_open):
            bar_open = close

        if self._divergence_detected == 'SHORT' and close < bar_open:
            # Bearish reversal bar confirmed
            signal = self._create_signal(
                bar, bar_index, session_context, 'SHORT',
                close, self._divergence_edge or 'NO_EDGE',
            )
            self._divergence_detected = None
            return signal

        elif self._divergence_detected == 'LONG' and close > bar_open:
            # Bullish reversal bar confirmed
            signal = self._create_signal(
                bar, bar_index, session_context, 'LONG',
                close, self._divergence_edge or 'NO_EDGE',
            )
            self._divergence_detected = None
            return signal

        # Cancel if divergence is more than 5 bars old
        if self._divergence_detected is not None:
            # Simple timeout: if bar count advanced too far, cancel
            self._divergence_detected = None

        return None

    def _create_signal(
        self, bar, bar_index, session_context, direction, entry, edge_name,
    ) -> Optional[Signal]:
        """Create and return a Signal for the CVD divergence trade."""
        atr = self._atr
        if atr <= 0:
            atr = 20.0

        # Stop: ATR-based
        if direction == 'LONG':
            stop = entry - STOP_ATR_MULT * atr
        else:
            stop = entry + STOP_ATR_MULT * atr

        risk = abs(entry - stop)
        if risk < MIN_RISK_PTS:
            return None

        # Target
        target = self._compute_target(direction, entry, stop, risk)
        reward = abs(target - entry)
        if reward <= 0:
            return None

        # Sanity: target must be reachable
        if direction == 'LONG' and target <= entry:
            return None
        if direction == 'SHORT' and target >= entry:
            return None

        self._entry_count += 1

        return Signal(
            timestamp=bar.get('timestamp', bar.name) if hasattr(bar, 'name') else bar.get('timestamp'),
            direction=direction,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            strategy_name=self.name,
            setup_type=f'CVD_DIV_{direction}',
            day_type=session_context.get('day_type', ''),
            trend_strength=session_context.get('trend_strength', ''),
            confidence='medium',
            metadata={
                'edge': edge_name,
                'target_mode': self._target_mode,
                'atr': round(atr, 2),
                'require_reversal_bar': self._require_reversal_bar,
                'use_edge_filter': self._use_edge_filter,
                'use_day_type_filter': self._use_day_type_filter,
            },
        )

    def _compute_target(self, direction: str, entry: float, stop: float, risk: float) -> float:
        """Compute target price based on target mode."""
        if self._target_mode == TARGET_PRIOR_POC:
            if self._prior_poc is not None:
                return self._prior_poc
            # Fallback to IB mid if no POC available
            return self._ib_mid

        if self._target_mode == TARGET_VWAP:
            if self._vwap is not None and not (isinstance(self._vwap, float) and pd.isna(self._vwap)):
                return self._vwap
            return self._ib_mid

        # Default: 2R
        if direction == 'LONG':
            return entry + 2 * risk
        else:
            return entry - 2 * risk
