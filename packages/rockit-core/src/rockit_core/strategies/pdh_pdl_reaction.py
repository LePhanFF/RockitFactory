"""
Strategy: PDH/PDL Reaction — Prior Day High / Prior Day Low

Trades reversals and rejection touches at institutional reference levels
(prior day high / prior day low).

Quant study results (270 NQ sessions):
  - 109 trades, 65.1% WR, PF 1.52, +$10,715
  - Setup A (Failed Auction): best performer
  - Setup B (Continuation): 0% WR — DISABLED in production
  - Setup C (Reaction Touch): solid secondary setup

Production config:
  - setup_modes: [A, C]  (B disabled)
  - stop_mode: spike (spike extreme + 5pt buffer)
  - target_mode: 2r (2x risk)
  - require_bias_alignment: True
  - poke_min: 5
  - Time window: 10:00-14:00 ET

Setup A: Failed Auction (Reversal/Fade)
  - Price spikes above PDH (or below PDL) by >= poke_min pts
  - Within 5 bars: price closes back BELOW PDH (failed breakout)
  - Enter SHORT at close back below PDH (or LONG at close back above PDL)
  - Stop: Above spike high + 5pt buffer
  - Target: 2R

Setup C: Reaction Touch
  - Price HIGH reaches within 3 pts of PDH (touch but not break)
  - Rejection candle: close in bottom 30% of bar range (for PDH touch)
  - Enter SHORT (PDH) / LONG (PDL)
  - Stop: spike + 5pt buffer (Setup A), or level + 10pt (Setup C)
  - Target: 2R

Filters:
  - Time: 10:00-14:00 ET (best hours 10:00-12:00)
  - Max 2 trades per session (1 PDH event, 1 PDL event)
  - Skip if prior day range < 50 pts (levels too close together)
  - Bias alignment: skip counter-bias trades when enabled
"""

from datetime import time as _time
from typing import Optional, List

import pandas as pd
import numpy as np

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal

# ── Parameters ────────────────────────────────────────────────
ENTRY_START = _time(10, 0)         # No entries before 10 AM ET
ENTRY_CUTOFF = _time(12, 0)        # No entries after 12 PM ET (study: 10-12 has 69.5% WR)
MIN_PRIOR_RANGE = 50.0             # Minimum prior day range in pts
MAX_TRADES_PER_SESSION = 2         # 1 PDH + 1 PDL max
POKE_MIN_PTS = 5.0                 # Min spike beyond level (Setup A)
FAILED_AUCTION_BARS = 5            # Bars to close back (Setup A)
TOUCH_PROXIMITY_PTS = 3.0          # How close = "touch" (Setup C)
REJECTION_CLOSE_PCT = 0.30         # Close in bottom 30% = rejection (Setup C)
TOUCH_STOP_PTS = 10.0              # Fixed stop for Setup C
SPIKE_BUFFER_PTS = 5.0             # Buffer above spike high (Setup A)


class PDHPDLReaction(StrategyBase):
    """
    PDH/PDL Reaction: trades reversals and touches at prior day
    high/low levels.

    Configurable via constructor:
      - setup_modes: list of 'A', 'C' to enable (B disabled by default)
      - poke_min: minimum pts beyond level for failed auction (Setup A)
      - stop_mode: 'spike', 'atr2x', 'fixed30'
      - target_mode: '2r', 'poc', 'vwap', 'midpoint'
      - require_bias_alignment: align with session_bias
    """

    def __init__(
        self,
        setup_modes: Optional[List[str]] = None,
        poke_min: float = POKE_MIN_PTS,
        stop_mode: str = 'spike',
        target_mode: str = '2r',
        require_bias_alignment: bool = True,
    ):
        self._setup_modes = set(setup_modes or ['A', 'C'])
        self._poke_min = poke_min
        self._stop_mode = stop_mode
        self._target_mode = target_mode
        self._require_bias = require_bias_alignment

    @property
    def name(self) -> str:
        return "PDH/PDL Reaction"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._ib_high = ib_high
        self._ib_low = ib_low
        self._ib_range = ib_range

        # Prior day levels
        self._pdh = session_context.get('pdh') or session_context.get('prior_session_high')
        self._pdl = session_context.get('pdl') or session_context.get('prior_session_low')

        # Compute prior day range and midpoint
        if self._pdh is not None and self._pdl is not None:
            self._prior_range = self._pdh - self._pdl
            self._prior_mid = (self._pdh + self._pdl) / 2.0
        else:
            self._prior_range = 0
            self._prior_mid = None

        # ATR from session context
        self._atr14 = session_context.get('atr14', 20.0)

        # State tracking
        self._entry_count = 0
        self._pdh_traded = False
        self._pdl_traded = False

        # Setup A tracking: spike detection
        self._pdh_spike_high = None   # Highest price during PDH poke
        self._pdh_poke_bar = -1       # Bar index when poke started
        self._pdl_spike_low = None
        self._pdl_poke_bar = -1

        # Setup C tracking: first touch
        self._pdh_touched = False
        self._pdl_touched = False

    def _process_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        """Core bar processing logic shared by on_bar and on_pre_ib_bar."""
        # Skip if no prior day data
        if self._pdh is None or self._pdl is None:
            return None

        # Skip if prior range too tight
        if self._prior_range < MIN_PRIOR_RANGE:
            return None

        # Max trades check
        if self._entry_count >= MAX_TRADES_PER_SESSION:
            return None

        # Time filter: only 10:00-12:00 ET
        bar_time = session_context.get('bar_time')
        if bar_time is not None:
            if bar_time < ENTRY_START or bar_time >= ENTRY_CUTOFF:
                return None

        current_price = bar['close']
        bar_high = bar['high']
        bar_low = bar['low']
        bar_range = bar_high - bar_low

        # Get session context for filters
        day_type = session_context.get('day_type', '')

        # Bias alignment
        if self._require_bias:
            bias = session_context.get('session_bias') or session_context.get('regime_bias', 'NEUTRAL')
        else:
            bias = None

        vwap = session_context.get('vwap')

        # ── Setup A: Failed Auction at PDH ──────────────────────
        if 'A' in self._setup_modes and not self._pdh_traded:
            signal = self._check_failed_auction_pdh(
                bar, bar_index, current_price, bar_high, bar_low,
                session_context, bias, day_type
            )
            if signal is not None:
                return signal

        # ── Setup A: Failed Auction at PDL ──────────────────────
        if 'A' in self._setup_modes and not self._pdl_traded:
            signal = self._check_failed_auction_pdl(
                bar, bar_index, current_price, bar_high, bar_low,
                session_context, bias, day_type
            )
            if signal is not None:
                return signal

        # ── Setup C: Reaction Touch at PDH ─────────────────────
        if 'C' in self._setup_modes and not self._pdh_traded:
            signal = self._check_reaction_touch_pdh(
                bar, bar_index, current_price, bar_high, bar_low, bar_range,
                session_context, bias, day_type
            )
            if signal is not None:
                return signal

        # ── Setup C: Reaction Touch at PDL ─────────────────────
        if 'C' in self._setup_modes and not self._pdl_traded:
            signal = self._check_reaction_touch_pdl(
                bar, bar_index, current_price, bar_high, bar_low, bar_range,
                session_context, bias, day_type
            )
            if signal is not None:
                return signal

        # Track state for multi-bar setups (Setup A spike tracking)
        self._update_spike_tracking(bar_high, bar_low)

        return None

    def on_pre_ib_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        """Process bars during IB formation (10:00-10:30 window)."""
        return self._process_bar(bar, bar_index, session_context)

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        return self._process_bar(bar, bar_index, session_context)

    # ── Setup A: Failed Auction ─────────────────────────────────

    def _check_failed_auction_pdh(self, bar, bar_index, price, high, low,
                                   ctx, bias, day_type):
        """Short when price pokes above PDH then closes back below."""
        # Phase 1: Detect poke above PDH
        if self._pdh_spike_high is None:
            if high >= self._pdh + self._poke_min:
                self._pdh_spike_high = high
                self._pdh_poke_bar = bar_index
            return None

        # Track highest point during poke
        if high > self._pdh_spike_high:
            self._pdh_spike_high = high

        # Phase 2: Check for close back below PDH within window
        bars_since_poke = bar_index - self._pdh_poke_bar
        if bars_since_poke > FAILED_AUCTION_BARS:
            # Poke expired without failure — no trade, mark PDH as "broken"
            self._pdh_spike_high = None
            return None

        if price < self._pdh:
            # Failed auction confirmed — SHORT
            # Bias check: skip if bullish bias (shorting against the trend)
            if self._require_bias and bias and bias.upper() in ('BULL', 'BULLISH'):
                return None

            entry_price = price
            stop_price = self._compute_stop(entry_price, 'SHORT',
                                             spike_extreme=self._pdh_spike_high)
            target_price = self._compute_target(entry_price, stop_price, 'SHORT', ctx)

            self._pdh_traded = True
            self._entry_count += 1

            return Signal(
                timestamp=self._get_timestamp(bar),
                direction='SHORT',
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                strategy_name=self.name,
                setup_type='PDH_FAILED_AUCTION',
                day_type=day_type,
                trend_strength=ctx.get('trend_strength', ''),
                confidence='high',
                metadata={
                    'level': 'PDH',
                    'setup': 'A',
                    'pdh': self._pdh,
                    'pdl': self._pdl,
                    'spike_high': self._pdh_spike_high,
                    'prior_range': self._prior_range,
                    'poke_pts': self._pdh_spike_high - self._pdh,
                },
            )
        return None

    def _check_failed_auction_pdl(self, bar, bar_index, price, high, low,
                                   ctx, bias, day_type):
        """Long when price pokes below PDL then closes back above."""
        # Phase 1: Detect poke below PDL
        if self._pdl_spike_low is None:
            if low <= self._pdl - self._poke_min:
                self._pdl_spike_low = low
                self._pdl_poke_bar = bar_index
            return None

        # Track lowest point during poke
        if low < self._pdl_spike_low:
            self._pdl_spike_low = low

        # Phase 2: Check for close back above PDL within window
        bars_since_poke = bar_index - self._pdl_poke_bar
        if bars_since_poke > FAILED_AUCTION_BARS:
            self._pdl_spike_low = None
            return None

        if price > self._pdl:
            # Failed auction confirmed — LONG
            # Bias check: skip if bearish bias (buying against the trend)
            if self._require_bias and bias and bias.upper() in ('BEAR', 'BEARISH'):
                return None

            entry_price = price
            stop_price = self._compute_stop(entry_price, 'LONG',
                                             spike_extreme=self._pdl_spike_low)
            target_price = self._compute_target(entry_price, stop_price, 'LONG', ctx)

            self._pdl_traded = True
            self._entry_count += 1

            return Signal(
                timestamp=self._get_timestamp(bar),
                direction='LONG',
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                strategy_name=self.name,
                setup_type='PDL_FAILED_AUCTION',
                day_type=day_type,
                trend_strength=ctx.get('trend_strength', ''),
                confidence='high',
                metadata={
                    'level': 'PDL',
                    'setup': 'A',
                    'pdh': self._pdh,
                    'pdl': self._pdl,
                    'spike_low': self._pdl_spike_low,
                    'prior_range': self._prior_range,
                    'poke_pts': self._pdl - self._pdl_spike_low,
                },
            )
        return None

    # ── Setup C: Reaction Touch ─────────────────────────────────

    def _check_reaction_touch_pdh(self, bar, bar_index, price, high, low,
                                   bar_range, ctx, bias, day_type):
        """Short on touch and rejection at PDH."""
        # Touch: high within proximity but not a full break (poke_min threshold)
        if high >= self._pdh - TOUCH_PROXIMITY_PTS and high < self._pdh + self._poke_min:
            # Rejection: close in bottom 30% of bar range
            if bar_range > 0:
                close_position = (price - low) / bar_range
                if close_position <= REJECTION_CLOSE_PCT:
                    # Bias check: skip if bullish bias
                    if self._require_bias and bias and bias.upper() in ('BULL', 'BULLISH'):
                        return None

                    entry_price = price
                    stop_price = self._compute_stop(entry_price, 'SHORT')
                    target_price = self._compute_target(entry_price, stop_price, 'SHORT', ctx)

                    self._pdh_traded = True
                    self._entry_count += 1

                    return Signal(
                        timestamp=self._get_timestamp(bar),
                        direction='SHORT',
                        entry_price=entry_price,
                        stop_price=stop_price,
                        target_price=target_price,
                        strategy_name=self.name,
                        setup_type='PDH_REACTION_TOUCH',
                        day_type=day_type,
                        trend_strength=ctx.get('trend_strength', ''),
                        confidence='medium',
                        metadata={
                            'level': 'PDH',
                            'setup': 'C',
                            'pdh': self._pdh,
                            'pdl': self._pdl,
                            'close_position': close_position,
                            'prior_range': self._prior_range,
                        },
                    )
        return None

    def _check_reaction_touch_pdl(self, bar, bar_index, price, high, low,
                                   bar_range, ctx, bias, day_type):
        """Long on touch and rejection at PDL."""
        if low <= self._pdl + TOUCH_PROXIMITY_PTS and low > self._pdl - self._poke_min:
            # Rejection: close in top 30% of bar range (price bounced up)
            if bar_range > 0:
                close_position = (price - low) / bar_range
                if close_position >= (1.0 - REJECTION_CLOSE_PCT):
                    # Bias check: skip if bearish bias
                    if self._require_bias and bias and bias.upper() in ('BEAR', 'BEARISH'):
                        return None

                    entry_price = price
                    stop_price = self._compute_stop(entry_price, 'LONG')
                    target_price = self._compute_target(entry_price, stop_price, 'LONG', ctx)

                    self._pdl_traded = True
                    self._entry_count += 1

                    return Signal(
                        timestamp=self._get_timestamp(bar),
                        direction='LONG',
                        entry_price=entry_price,
                        stop_price=stop_price,
                        target_price=target_price,
                        strategy_name=self.name,
                        setup_type='PDL_REACTION_TOUCH',
                        day_type=day_type,
                        trend_strength=ctx.get('trend_strength', ''),
                        confidence='medium',
                        metadata={
                            'level': 'PDL',
                            'setup': 'C',
                            'pdh': self._pdh,
                            'pdl': self._pdl,
                            'close_position': close_position,
                            'prior_range': self._prior_range,
                        },
                    )
        return None

    # ── Stop / Target Computation ───────────────────────────────

    def _compute_stop(self, entry_price, direction, spike_extreme=None):
        """Compute stop price based on stop_mode."""
        if self._stop_mode == 'spike' and spike_extreme is not None:
            if direction == 'SHORT':
                return spike_extreme + SPIKE_BUFFER_PTS
            else:
                return spike_extreme - SPIKE_BUFFER_PTS
        elif self._stop_mode == 'atr2x':
            risk = 2.0 * self._atr14
            if direction == 'SHORT':
                return entry_price + risk
            else:
                return entry_price - risk
        elif self._stop_mode == 'fixed30':
            if direction == 'SHORT':
                return entry_price + 30.0
            else:
                return entry_price - 30.0
        else:
            # Default: level-based fixed stop
            if direction == 'SHORT':
                return entry_price + TOUCH_STOP_PTS
            else:
                return entry_price - TOUCH_STOP_PTS

    def _compute_target(self, entry_price, stop_price, direction, ctx):
        """Compute target price based on target_mode."""
        risk = abs(entry_price - stop_price)

        if self._target_mode == '2r':
            if direction == 'SHORT':
                return entry_price - 2.0 * risk
            else:
                return entry_price + 2.0 * risk

        elif self._target_mode == 'poc':
            poc = ctx.get('prior_va_poc')
            if poc is not None:
                return poc
            return self._prior_mid if self._prior_mid else entry_price

        elif self._target_mode == 'vwap':
            vwap = ctx.get('vwap')
            if vwap is not None:
                return vwap
            return self._prior_mid if self._prior_mid else entry_price

        elif self._target_mode == 'midpoint':
            if self._prior_mid is not None:
                return self._prior_mid
            return entry_price

        # Fallback: 2R
        if direction == 'SHORT':
            return entry_price - 2.0 * risk
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

    def _update_spike_tracking(self, high, low):
        """Update spike extremes for in-progress Setup A tracking."""
        if self._pdh_spike_high is not None and high > self._pdh_spike_high:
            self._pdh_spike_high = high
        if self._pdl_spike_low is not None and low < self._pdl_spike_low:
            self._pdl_spike_low = low
