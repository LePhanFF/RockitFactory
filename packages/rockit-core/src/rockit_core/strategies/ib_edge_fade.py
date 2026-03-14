"""
Strategy: IB Edge Fade — Initial Balance Edge Rejection

Trades reversals when price tests IB high or IB low boundary and gets
rejected, fading back into the IB range.

Quant study results (260 NQ sessions):
  Best LONG (IBL fade):
    LONG 3pts a2 10%IB 2R — 122 trades, 42.6% WR, PF 1.56, +$27,968
    2nd-touch LONG 5pts a2 0.5ATR IBmid — 95 trades, 37.9% WR, PF 1.67, +$20,630

  Best SHORT (IBH fade):
    SHORT poke a1 0.5ATR 1R — 137 trades, 58.4% WR, PF 1.39, +$7,509

  Day type findings:
    LONG on b_day: 61.5% WR, PF 4.00, +$17,636
    SHORT on b_day: 75.0% WR, PF 2.65, +$2,753
    Trend days are losers for both directions

  IB range impact (SHORT):
    < 100 pts: 28.6% WR, PF 0.41 (avoid)
    100-150: 65.0% WR, PF 1.19
    150-200: 60.5% WR, PF 1.62
    200-300: 66.7% WR, PF 1.86

  Time-of-day (SHORT):
    10:30-11:00: 45.3% WR, PF 0.77 (noisy right after IB)
    11:00-14:00: best performance

Production config (combined best from study):
  - LONG: 3pts poke, 2x accept bars, 10%IB stop, 2R target
  - SHORT: poke (any), 1x accept bar, 0.5ATR stop, 1R target
  - min_ib_range: 100 pts (filter out narrow IB days)
  - time_window: 10:30-14:00 ET
"""

from datetime import time as _time
from typing import Optional, List

import pandas as pd

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal

# ── Parameters ────────────────────────────────────────────────
ENTRY_START = _time(10, 30)        # After IB close
ENTRY_CUTOFF = _time(14, 0)        # No entries after 2 PM ET
SHORT_ENTRY_START = _time(11, 0)   # SHORT: skip 10:30-11:00 (PF 0.77 in study)
MIN_IB_RANGE = 100.0               # Skip narrow IB days (< 100 pts)
# Day types where LONG loses (study: trend_down PF 0.36)
LONG_BLOCKED_DAY_TYPES = {'trend_down', 'Trend Down'}
POKE_MIN_PTS_LONG = 3.0            # Min pts beyond IB edge (LONG)
POKE_MIN_PTS_SHORT = 0.0           # Any poke counts (SHORT — "poke" config)
ACCEPT_BARS_LONG = 2               # Bars confirming fade (LONG)
ACCEPT_BARS_SHORT = 1              # Bars confirming fade (SHORT)
MAX_TOUCH = 1                      # First touch only per edge per session


class IBEdgeFade(StrategyBase):
    """
    IB Edge Fade: trades rejection at IB high/low boundaries.

    Configurable via constructor:
      - poke_min_long: min pts beyond IB edge for LONG setup
      - poke_min_short: min pts beyond IB edge for SHORT setup
      - accept_bars_long: acceptance bars for LONG confirmation
      - accept_bars_short: acceptance bars for SHORT confirmation
      - stop_mode_long: '10pct_ib', '0.5atr', 'fixed_5pt'
      - stop_mode_short: '0.5atr', '10pct_ib', 'fixed_5pt'
      - target_mode_long: '2r', 'ib_mid', '1r'
      - target_mode_short: '1r', 'ib_mid', '2r'
      - min_ib_range: minimum IB range in pts
      - max_touch: max touches per edge per session
    """

    def __init__(
        self,
        poke_min_long: float = POKE_MIN_PTS_LONG,
        poke_min_short: float = POKE_MIN_PTS_SHORT,
        accept_bars_long: int = ACCEPT_BARS_LONG,
        accept_bars_short: int = ACCEPT_BARS_SHORT,
        stop_mode_long: str = '10pct_ib',
        stop_mode_short: str = '0.5atr',
        target_mode_long: str = '2r',
        target_mode_short: str = '1r',
        min_ib_range: float = MIN_IB_RANGE,
        max_touch: int = MAX_TOUCH,
    ):
        self._poke_min_long = poke_min_long
        self._poke_min_short = poke_min_short
        self._accept_bars_long = accept_bars_long
        self._accept_bars_short = accept_bars_short
        self._stop_mode_long = stop_mode_long
        self._stop_mode_short = stop_mode_short
        self._target_mode_long = target_mode_long
        self._target_mode_short = target_mode_short
        self._min_ib_range = min_ib_range
        self._max_touch = max_touch

    @property
    def name(self) -> str:
        return "IB Edge Fade"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types (b_day is best but study didn't restrict)

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._ib_high = ib_high
        self._ib_low = ib_low
        self._ib_range = ib_range
        self._ib_mid = (ib_high + ib_low) / 2.0

        # ATR from session context
        self._atr14 = session_context.get('atr14', 20.0)

        # State: IBH tracking (SHORT setup)
        self._ibh_touch_count = 0
        self._ibh_poke_detected = False
        self._ibh_accept_count = 0
        self._ibh_spike_high = None
        self._ibh_traded = False

        # State: IBL tracking (LONG setup)
        self._ibl_touch_count = 0
        self._ibl_poke_detected = False
        self._ibl_accept_count = 0
        self._ibl_spike_low = None
        self._ibl_traded = False

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        # Skip if IB range too narrow
        if self._ib_range < self._min_ib_range:
            return None

        # Time filter
        bar_time = session_context.get('bar_time')
        if bar_time is not None:
            if bar_time < ENTRY_START or bar_time >= ENTRY_CUTOFF:
                return None

        price = bar['close']
        high = bar['high']
        low = bar['low']
        day_type = session_context.get('day_type', '')

        # ── IBL Fade (LONG) ──────────────────────────────────────
        # Block LONG on trend_down days (study: PF 0.36, -$9,444)
        if not self._ibl_traded and day_type not in LONG_BLOCKED_DAY_TYPES:
            signal = self._check_ibl_fade(bar, bar_index, price, high, low,
                                           session_context, day_type)
            if signal is not None:
                return signal

        # ── IBH Fade (SHORT) — DISABLED ──────────────────────────
        # SHORT side PF=1.20 in backtest, drags combined PF below 1.5.
        # LONG side PF=1.57 is above threshold.
        # SHORT disabled to maintain portfolio-level PF >= 1.5.
        # if not self._ibh_traded:
        #     if bar_time is None or bar_time >= SHORT_ENTRY_START:
        #         signal = self._check_ibh_fade(bar, bar_index, price, high, low,
        #                                        session_context, day_type)
        #         if signal is not None:
        #             return signal

        return None

    def _check_ibh_fade(self, bar, bar_index, price, high, low, ctx, day_type):
        """SHORT when price pokes above IBH and confirms fade back inside."""
        ibh = self._ib_high

        # Phase 1: Detect poke above IBH
        if not self._ibh_poke_detected:
            poke_amount = high - ibh
            if poke_amount >= self._poke_min_short:
                self._ibh_touch_count += 1
                if self._ibh_touch_count > self._max_touch:
                    return None
                self._ibh_poke_detected = True
                self._ibh_spike_high = high
                self._ibh_accept_count = 0
            return None

        # Track spike extreme
        if high > self._ibh_spike_high:
            self._ibh_spike_high = high

        # Phase 2: Acceptance — bar closes below IBH
        if price < ibh:
            self._ibh_accept_count += 1
        else:
            self._ibh_accept_count = 0

        # Phase 3: Confirmed fade
        if self._ibh_accept_count >= self._accept_bars_short:
            entry_price = price
            stop_price = self._compute_stop(entry_price, 'SHORT')
            target_price = self._compute_target(entry_price, stop_price, 'SHORT')

            self._ibh_traded = True

            return Signal(
                timestamp=self._get_timestamp(bar),
                direction='SHORT',
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                strategy_name=self.name,
                setup_type='IBH_EDGE_FADE',
                day_type=day_type,
                trend_strength=ctx.get('trend_strength', ''),
                confidence='medium',
                metadata={
                    'level': 'IBH',
                    'ib_high': self._ib_high,
                    'ib_low': self._ib_low,
                    'ib_range': self._ib_range,
                    'spike_high': self._ibh_spike_high,
                    'poke_pts': self._ibh_spike_high - ibh,
                    'accept_bars': self._ibh_accept_count,
                    'touch_number': self._ibh_touch_count,
                },
            )

        return None

    def _check_ibl_fade(self, bar, bar_index, price, high, low, ctx, day_type):
        """LONG when price pokes below IBL and confirms fade back inside."""
        ibl = self._ib_low

        # Phase 1: Detect poke below IBL
        if not self._ibl_poke_detected:
            poke_amount = ibl - low
            if poke_amount >= self._poke_min_long:
                self._ibl_touch_count += 1
                if self._ibl_touch_count > self._max_touch:
                    return None
                self._ibl_poke_detected = True
                self._ibl_spike_low = low
                self._ibl_accept_count = 0
            return None

        # Track spike extreme
        if low < self._ibl_spike_low:
            self._ibl_spike_low = low

        # Phase 2: Acceptance — bar closes above IBL
        if price > ibl:
            self._ibl_accept_count += 1
        else:
            self._ibl_accept_count = 0

        # Phase 3: Confirmed fade
        if self._ibl_accept_count >= self._accept_bars_long:
            entry_price = price
            stop_price = self._compute_stop(entry_price, 'LONG')
            target_price = self._compute_target(entry_price, stop_price, 'LONG')

            self._ibl_traded = True

            return Signal(
                timestamp=self._get_timestamp(bar),
                direction='LONG',
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                strategy_name=self.name,
                setup_type='IBL_EDGE_FADE',
                day_type=day_type,
                trend_strength=ctx.get('trend_strength', ''),
                confidence='medium',
                metadata={
                    'level': 'IBL',
                    'ib_high': self._ib_high,
                    'ib_low': self._ib_low,
                    'ib_range': self._ib_range,
                    'spike_low': self._ibl_spike_low,
                    'poke_pts': ibl - self._ibl_spike_low,
                    'accept_bars': self._ibl_accept_count,
                    'touch_number': self._ibl_touch_count,
                },
            )

        return None

    # ── Stop / Target Computation ───────────────────────────────

    def _compute_stop(self, entry_price, direction):
        """Compute stop price based on direction-specific stop mode."""
        if direction == 'SHORT':
            mode = self._stop_mode_short
        else:
            mode = self._stop_mode_long

        if mode == '0.5atr':
            risk = 0.5 * self._atr14
            if direction == 'SHORT':
                return entry_price + risk
            else:
                return entry_price - risk
        elif mode == '10pct_ib':
            risk = 0.10 * self._ib_range
            risk = max(risk, 5.0)  # Floor at 5 pts
            if direction == 'SHORT':
                return entry_price + risk
            else:
                return entry_price - risk
        elif mode == 'fixed_5pt':
            if direction == 'SHORT':
                return entry_price + 5.0
            else:
                return entry_price - 5.0
        else:
            # Default: 0.5 ATR
            risk = 0.5 * self._atr14
            if direction == 'SHORT':
                return entry_price + risk
            else:
                return entry_price - risk

    def _compute_target(self, entry_price, stop_price, direction):
        """Compute target price based on direction-specific target mode."""
        risk = abs(entry_price - stop_price)

        if direction == 'SHORT':
            mode = self._target_mode_short
        else:
            mode = self._target_mode_long

        if mode == '1r':
            if direction == 'SHORT':
                return entry_price - risk
            else:
                return entry_price + risk
        elif mode == '2r':
            if direction == 'SHORT':
                return entry_price - 2.0 * risk
            else:
                return entry_price + 2.0 * risk
        elif mode == 'ib_mid':
            return self._ib_mid
        elif mode == 'opp_edge':
            if direction == 'SHORT':
                return self._ib_low
            else:
                return self._ib_high
        else:
            # Default: 2R for LONG, 1R for SHORT
            if direction == 'SHORT':
                return entry_price - risk
            else:
                return entry_price + 2.0 * risk

    # ── Helpers ──────────────────────────────────────────────────

    def _get_timestamp(self, bar):
        """Extract timestamp from bar Series."""
        if 'timestamp' in bar.index:
            return bar['timestamp']
        if hasattr(bar, 'name'):
            return bar.name
        return None
