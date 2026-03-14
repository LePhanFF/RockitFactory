"""
Strategy: Double Distribution Trend Continuation — Separation Pullback Entry

Trades trend continuation after a double distribution forms in the TPO profile.
When two distinct value areas separate (LVN between them), the market is migrating
value. Enter on a pullback to the separation level in the direction of migration.

Quant Study (274 NQ sessions, 2025-02 to 2026-03):
  Detection: 98% of sessions show double distribution at some point (very common).
  Meaningful: spread >= 75pts between POCs, detected before 10:30 = 53 fills.
  Best config (pullback to separation, 30pt stop, 75pt target):
    - 41.5% WR, PF 1.77, $14,400 net (53 trades)
  With spread >= 100pts:
    - 46.7% WR, PF 2.19, $11,400 (30 trades)

Pattern:
  1. Compute TPO profile every 5 bars to detect double distribution
  2. Require POC spread >= min_poc_spread (default 75 pts)
  3. Determine direction: price above separation = LONG (upper dist active)
  4. Wait for pullback to separation level (limit fill simulation)
  5. Stop: fixed points below/above separation
  6. Target: fixed points in trend direction

Key constraints:
  - Detection before 10:30 only (early detection has 2x better MFE)
  - Max 1 trade per session
  - Pullback fill window: 60 bars (1 hour)
"""

from datetime import time as _time
from typing import Optional, List, TYPE_CHECKING

import numpy as np
import pandas as pd

from rockit_core.models.signals import Direction, EntrySignal
from rockit_core.models.stop_models import FixedPointsStop
from rockit_core.models.target_models import RMultipleTarget
from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal

if TYPE_CHECKING:
    from rockit_core.models.base import StopModel, TargetModel

# ── Configuration Constants ──────────────────────────────────────
MIN_POC_SPREAD = 75.0        # Minimum spread between upper/lower POC (points)
DETECTION_CUTOFF = _time(10, 30)  # Only detect before this time
PULLBACK_WINDOW = 60         # Max bars to wait for pullback fill
LAST_ENTRY_TIME = _time(14, 0)    # No entries after 2 PM
TPO_COMPUTE_INTERVAL = 5     # Recompute TPO every N bars
TPO_TICK = 0.25              # NQ tick size
TPO_MIN_TICKS = 20           # Min TPO ticks to attempt distribution detection
TPO_MIN_PROFILE_RANGE = 10   # Min profile range (points)

# Default stop/target
DEFAULT_STOP_PTS = 30.0
DEFAULT_TARGET_R = 2.5       # 30pt stop * 2.5 = 75pt target


class DoubleDistributionStrategy(StrategyBase):
    """Double Distribution Trend Continuation with pullback to separation entry.

    Uses on-the-fly TPO computation (every 5 bars) to detect double distributions.
    When a meaningful double distribution forms (POC spread >= threshold), waits
    for price to pull back to the LVN separation level before entering.
    """

    def __init__(
        self,
        stop_model: Optional['StopModel'] = None,
        target_model: Optional['TargetModel'] = None,
        min_poc_spread: float = MIN_POC_SPREAD,
    ):
        self._stop_model = stop_model or FixedPointsStop(DEFAULT_STOP_PTS)
        self._target_model = target_model or RMultipleTarget(DEFAULT_TARGET_R)
        self._min_poc_spread = min_poc_spread

    @property
    def name(self) -> str:
        return "Double Distribution"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._ib_high = ib_high
        self._ib_low = ib_low
        self._ib_range = ib_range

        # State tracking
        self._signal_emitted = False
        self._dd_detected = False
        self._separation = None
        self._upper_poc = None
        self._lower_poc = None
        self._direction = None
        self._waiting_for_pullback = False
        self._detection_bar = None
        self._bars_waiting = 0

        # Accumulate RTH bars for TPO computation
        self._rth_bars = []

        # Cache IB bars for TPO computation (they're part of the session)
        ib_bars = session_context.get('ib_bars')
        if ib_bars is not None:
            for _, bar in ib_bars.iterrows():
                self._rth_bars.append({
                    'high': bar['high'],
                    'low': bar['low'],
                    'close': bar['close'],
                    'timestamp': bar.get('timestamp', bar.name) if hasattr(bar, 'name') else bar.get('timestamp'),
                })

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        if self._signal_emitted:
            return None

        bar_time = session_context.get('bar_time')

        # Accumulate bar for TPO computation
        self._rth_bars.append({
            'high': bar['high'],
            'low': bar['low'],
            'close': bar['close'],
            'timestamp': bar.get('timestamp', bar.name) if hasattr(bar, 'name') else bar.get('timestamp'),
        })

        # Phase 1: Detection — compute TPO every N bars before cutoff
        if not self._dd_detected:
            if bar_time and bar_time > DETECTION_CUTOFF:
                return None  # Past detection window

            if bar_index % TPO_COMPUTE_INTERVAL == 0 and len(self._rth_bars) >= 30:
                dist = self._compute_distributions()
                if dist is not None:
                    spread = abs(dist['upper_poc'] - dist['lower_poc'])
                    if spread >= self._min_poc_spread:
                        self._dd_detected = True
                        self._separation = dist['separation_level']
                        self._upper_poc = dist['upper_poc']
                        self._lower_poc = dist['lower_poc']
                        self._detection_bar = bar_index

                        # Determine direction based on current price vs separation
                        current_price = bar['close']
                        if current_price > self._separation:
                            self._direction = 'LONG'
                        else:
                            self._direction = 'SHORT'

                        self._waiting_for_pullback = True
                        self._bars_waiting = 0

            return None

        # Phase 2: Wait for pullback to separation level
        if self._waiting_for_pullback:
            if bar_time and bar_time >= LAST_ENTRY_TIME:
                self._waiting_for_pullback = False
                return None

            self._bars_waiting += 1
            if self._bars_waiting > PULLBACK_WINDOW:
                self._waiting_for_pullback = False
                return None

            # Check if price touches separation level
            filled = False
            if self._direction == 'LONG' and bar['low'] <= self._separation:
                filled = True
            elif self._direction == 'SHORT' and bar['high'] >= self._separation:
                filled = True

            if filled:
                self._waiting_for_pullback = False
                return self._emit_signal(bar, bar_index, session_context)

        return None

    def _compute_distributions(self) -> Optional[dict]:
        """Compute TPO distribution from accumulated bars.

        Lightweight implementation matching _detect_distributions() logic
        from the deterministic module.
        """
        bars_df = pd.DataFrame(self._rth_bars)
        if len(bars_df) < 30:
            return None

        min_price = bars_df['low'].min()
        max_price = bars_df['high'].max()
        profile_range = max_price - min_price

        if profile_range < TPO_MIN_PROFILE_RANGE:
            return None

        tick = TPO_TICK
        bins = np.arange(min_price - tick, max_price + tick * 2, tick)

        # Build TPO counts using 30-min periods
        tpo_counts = pd.Series(0.0, index=bins)

        # Group bars into 30-min periods
        period_idx = 0
        for i in range(0, len(bars_df), 30):
            chunk = bars_df.iloc[i:i+30]
            for _, row in chunk.iterrows():
                price_range = np.arange(row['low'], row['high'] + tick, tick)
                for p in price_range:
                    if p in tpo_counts.index:
                        tpo_counts.loc[p] += 1
            period_idx += 1

        tpo_counts = tpo_counts[tpo_counts > 0]
        if len(tpo_counts) < TPO_MIN_TICKS:
            return None

        poc = float(tpo_counts.idxmax())

        # Smooth and find valleys
        smoothed = tpo_counts.sort_index().rolling(window=5, center=True, min_periods=1).mean()
        mean_val = smoothed.mean()

        if mean_val == 0:
            return None

        valley_mask = smoothed < (mean_val * 0.3)
        valley_prices = smoothed.index[valley_mask]

        if len(valley_prices) == 0:
            return None

        # Interior valleys only
        profile_mid_low = tpo_counts.index.min() + profile_range * 0.2
        profile_mid_high = tpo_counts.index.max() - profile_range * 0.2
        interior_valleys = valley_prices[
            (valley_prices > profile_mid_low) & (valley_prices < profile_mid_high)
        ]

        if len(interior_valleys) < 3:
            return None

        separation = float(np.mean(interior_valleys.values))

        upper_tpo = tpo_counts[tpo_counts.index > separation]
        lower_tpo = tpo_counts[tpo_counts.index < separation]

        if upper_tpo.empty or lower_tpo.empty:
            return None

        return {
            'count': 2,
            'type': 'double',
            'separation_level': round(separation, 2),
            'upper_poc': round(float(upper_tpo.idxmax()), 2),
            'lower_poc': round(float(lower_tpo.idxmax()), 2),
        }

    def _emit_signal(
        self, bar: pd.Series, bar_index: int, session_context: dict
    ) -> Optional[Signal]:
        """Emit a signal at the separation level pullback."""
        entry_price = self._separation
        direction = self._direction

        model_direction = Direction.LONG if direction == 'LONG' else Direction.SHORT
        entry_signal = EntrySignal(
            model_name=self.name,
            direction=model_direction,
            price=entry_price,
            confidence=0.8,
            setup_type=f'DD_CONTINUATION_{direction}',
        )

        ctx = dict(session_context)
        ctx.setdefault('ib_high', self._ib_high)
        ctx.setdefault('ib_low', self._ib_low)
        ctx.setdefault('ib_range', self._ib_range)

        stop_level = self._stop_model.compute(entry_signal, bar, ctx)
        target_spec = self._target_model.compute(entry_signal, stop_level, bar, ctx)

        # Sanity check: stop must be meaningful
        risk = stop_level.distance_points
        if risk < 5 or risk > 100:
            return None

        self._signal_emitted = True

        timestamp = bar.get('timestamp', bar.name) if hasattr(bar, 'name') else bar.get('timestamp')

        return Signal(
            timestamp=timestamp,
            direction=direction,
            entry_price=entry_price,
            stop_price=stop_level.price,
            target_price=target_spec.price,
            strategy_name=self.name,
            setup_type=f'DD_CONTINUATION_{direction}',
            day_type=session_context.get('day_type', ''),
            trend_strength=session_context.get('trend_strength', ''),
            confidence='high',
            metadata={
                'separation_level': self._separation,
                'upper_poc': self._upper_poc,
                'lower_poc': self._lower_poc,
                'poc_spread': abs(self._upper_poc - self._lower_poc),
                'detection_bar': self._detection_bar,
                'pullback_bars': self._bars_waiting,
                'stop_model': self._stop_model.name,
                'target_model': self._target_model.name,
            },
        )

    def on_session_end(self, session_date) -> None:
        """Cleanup session state."""
        self._rth_bars = []
