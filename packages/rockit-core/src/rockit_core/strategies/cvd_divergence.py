"""
Strategy: CVD Divergence (Institutional Exhaustion)
====================================================

CVD (Cumulative Volume Delta) divergence signals institutional exhaustion:
- **Bullish divergence**: Price makes lower low but CVD makes higher low
  (sellers exhausting, institutions absorbing)
- **Bearish divergence**: Price makes higher high but CVD makes lower high
  (buyers exhausting, institutions distributing)

Combined with Bollinger Band extremes for high-probability entries in
range-bound (ADX < 25) environments.

Optimal Config (study results):
  - Trigger: cvd_div_bb (CVD divergence + BB extreme)
  - Confirmation: immediate (market at signal bar close)
  - Filter: ADX < 25 (range-bound)
  - Stop: swing low (lowest low of last 10 bars)
  - Target: VWAP level
  - Window: after_ib only
  - Direction: LONG only
  - 33 trades, 21.2% WR, PF 5.05, $5,300

Also viable as a filter for existing strategies (80P, OR Rev).
"""

from typing import Optional, List

import pandas as pd
import numpy as np

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal


# ── CVD Divergence Constants ──────────────────────────────────
ADX_THRESHOLD = 25.0           # Only trade when ADX < 25 (range-bound)
SWING_LOOKBACK = 10            # Bars to look back for swing low stop
CVD_LOOKBACK = 20              # Bars to detect CVD divergence pattern
MAX_SIGNALS_PER_SESSION = 1    # Study: 1 signal per session
COOLDOWN_BARS = 15             # Minimum bars between signals
MIN_STOP_PTS = 20.0            # Minimum stop distance (NQ needs room)
MAX_STOP_PTS = 100.0           # Maximum stop distance
MIN_RR_RATIO = 2.0             # Minimum reward:risk ratio


class CVDDivergence(StrategyBase):
    """
    CVD Divergence: Bullish CVD divergence + BB lower band extreme
    in range-bound (ADX < 25) environments.

    LONG only — best configuration from study.
    """

    @property
    def name(self) -> str:
        return "CVD Divergence"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types — ADX < 25 gate handles range-bound filtering

    def on_session_start(self, session_date, ib_high, ib_low, ib_range,
                         session_context):
        self._ib_high = ib_high
        self._ib_low = ib_low
        self._ib_range = ib_range
        self._vwap = session_context.get('vwap', None)

        # State tracking
        self._signal_count = 0
        self._last_signal_bar = -COOLDOWN_BARS  # Allow first signal immediately
        self._active = True

        # CVD tracking — accumulate from post-IB bars
        self._cvd = 0.0
        self._price_history = []  # (bar_index, low, cvd)

    def on_bar(self, bar: pd.Series, bar_index: int,
               session_context: dict) -> Optional[Signal]:
        if not self._active:
            return None

        # Max signals check
        if self._signal_count >= MAX_SIGNALS_PER_SESSION:
            return None

        # Cooldown check
        if bar_index - self._last_signal_bar < COOLDOWN_BARS:
            # Still accumulate CVD and price history
            self._update_cvd(bar, bar_index)
            return None

        # ADX filter — require ADX < 25 (range-bound)
        adx = bar.get('adx14', None)
        if adx is None or (isinstance(adx, float) and pd.isna(adx)):
            self._update_cvd(bar, bar_index)
            return None
        if adx >= ADX_THRESHOLD:
            self._update_cvd(bar, bar_index)
            return None

        # Update CVD tracking
        self._update_cvd(bar, bar_index)

        # Need enough history for divergence detection
        if len(self._price_history) < 5:
            return None

        # Check for bullish CVD divergence + BB lower band
        close = float(bar['close'])
        bb_lower = bar.get('bb_lower', None)
        if bb_lower is None or (isinstance(bb_lower, float) and pd.isna(bb_lower)):
            return None

        # BB extreme check: close at or below BB lower
        if close > bb_lower:
            return None

        # Bullish divergence: use pre-computed column if available, else internal detection
        cvd_div = bar.get('cvd_div_bull', None)
        if cvd_div is not None and not pd.isna(cvd_div):
            has_divergence = bool(cvd_div)
        else:
            has_divergence = self._detect_bullish_divergence(bar_index)
        if not has_divergence:
            return None

        # Get VWAP for target
        vwap = bar.get('vwap', self._vwap)
        if vwap is None or (isinstance(vwap, float) and pd.isna(vwap)):
            return None

        # LONG only — target is VWAP (above current price)
        if vwap <= close:
            return None

        # Swing low stop — lowest low of last N bars, with min/max bounds
        swing_low = self._compute_swing_low(bar_index)
        stop = min(close - MIN_STOP_PTS, swing_low)  # At least MIN_STOP_PTS below entry
        if close - stop > MAX_STOP_PTS:
            stop = close - MAX_STOP_PTS  # Cap at MAX_STOP_PTS
        if stop >= close:
            return None

        entry = close
        risk = entry - stop
        # Target: VWAP level (study config: target=vwap)
        target = vwap
        reward = target - entry

        if risk <= 0 or reward <= 0:
            return None

        self._signal_count += 1
        self._last_signal_bar = bar_index

        return Signal(
            timestamp=bar.get('timestamp', bar.name) if hasattr(bar, 'name') else bar.get('timestamp'),
            direction='LONG',
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            strategy_name=self.name,
            setup_type='CVD_DIVERGENCE_BB',
            day_type=session_context.get('day_type', ''),
            trend_strength=session_context.get('trend_strength', ''),
            confidence='high',
            metadata={
                'cvd_divergence_type': 'bullish',
                'adx_value': round(float(adx), 2),
                'bb_position': 'lower',
                'swing_low_level': round(stop, 2),
                'vwap_target': round(target, 2),
                'cvd_at_signal': round(self._cvd, 2),
            },
        )

    def _update_cvd(self, bar: pd.Series, bar_index: int):
        """Accumulate CVD from vol_delta and track price/CVD history."""
        delta = bar.get('delta', bar.get('vol_delta', 0))
        if pd.isna(delta):
            delta = 0
        self._cvd += float(delta)
        self._price_history.append((bar_index, float(bar['low']), self._cvd))

    def _detect_bullish_divergence(self, current_bar_index: int) -> bool:
        """
        Detect bullish divergence: price makes lower low but CVD makes
        higher low over the lookback window.

        Looks for two swing lows where the second has:
        - Lower price low (bearish price action)
        - Higher CVD low (bullish volume divergence)
        """
        if len(self._price_history) < 5:
            return False

        # Use the lookback window
        lookback_start = max(0, len(self._price_history) - CVD_LOOKBACK)
        recent = self._price_history[lookback_start:]

        if len(recent) < 5:
            return False

        # Find the lowest price point in the first half as reference
        mid = len(recent) // 2
        first_half = recent[:mid]
        second_half = recent[mid:]

        if not first_half or not second_half:
            return False

        # Find lowest price low in each half
        first_min = min(first_half, key=lambda x: x[1])
        second_min = min(second_half, key=lambda x: x[1])

        # Bullish divergence: second low is lower in price but higher in CVD
        price_lower_low = second_min[1] < first_min[1]
        cvd_higher_low = second_min[2] > first_min[2]

        return price_lower_low and cvd_higher_low

    def _compute_swing_low(self, current_bar_index: int) -> float:
        """Compute swing low stop from recent price history."""
        lookback = self._price_history[-SWING_LOOKBACK:]
        if not lookback:
            return 0.0
        return min(entry[1] for entry in lookback)
