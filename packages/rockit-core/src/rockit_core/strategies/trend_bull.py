"""
Strategy: Trend Day Bull — EMA-aligned pullback entries (LONG)

Re-optimized from quant study (2026-03-13, 274 NQ sessions):
  - 15-min EMA20 > EMA50 alignment filter (trend confirmation)
  - ADX(14) on 15-min >= 25 (strong trend gate)
  - Entry: EMA20 (1-min) pullback or VWAP pullback after acceptance above IBH
  - Delta confirmation required (buyers present)
  - Fixed 40pt stop / 100pt target (2.5:1 R:R)
  - No day_type gate — alignment + acceptance IS the filter

Study results (ADX>=25 + delta confirmation):
  69 trades, 46.4% WR, PF 1.79, $23,310 net (combined bull+bear)
  LONG component: ~35 trades, ~47% WR

Design principle: Strategies EMIT SIGNALS, they do NOT manage positions.
"""

from datetime import time
from typing import Optional, List
import pandas as pd

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal
from rockit_core.config.constants import (
    ACCEPTANCE_MIN_BARS,
    PM_SESSION_START,
)

# ── Study-optimized parameters ──
STOP_FIXED_PTS = 40.0         # Fixed 40pt stop (winner MAE P80 = 35.7pt)
TARGET_FIXED_PTS = 100.0      # Fixed 100pt target (2.5:1 R:R)
ADX_THRESHOLD = 28.0          # 15-min ADX >= 28 (optimal: 48.5% WR, PF 1.82)
VWAP_PROXIMITY = 0.40         # Within 40% of IB range from VWAP
EMA_PROXIMITY = 0.20          # Within 20% of IB range from EMA20
ENTRY_CUTOFF = time(13, 0)    # No entries after 13:00 (13:00 hour has PF 0.63)


class TrendDayBull(StrategyBase):

    @property
    def name(self) -> str:
        return "Trend Day Bull"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types — alignment + acceptance is the filter

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._ib_high = ib_high
        self._ib_low = ib_low
        self._ib_range = ib_range

        self._acceptance_confirmed = False
        self._consecutive_above = 0
        self._signal_fired = False

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        current_price = bar['close']
        bar_time = session_context.get('bar_time')

        # ── Phase 1: Track acceptance above IBH (2 consecutive bars) ──
        if not self._acceptance_confirmed:
            if current_price > self._ib_high:
                self._consecutive_above += 1
            else:
                self._consecutive_above = 0

            if self._consecutive_above >= ACCEPTANCE_MIN_BARS:
                self._acceptance_confirmed = True

            return None

        # Already fired for this session
        if self._signal_fired:
            return None

        # Time gate
        if bar_time and bar_time >= ENTRY_CUTOFF:
            return None

        # ── Phase 2: Bias alignment ──
        # Skip LONG if session bias is bearish (counter-trend)
        bias = session_context.get('session_bias') or session_context.get('regime_bias', 'NEUTRAL')
        if bias and bias.upper() in ('BEAR', 'BEARISH'):
            return None

        # NOTE: day_type gate removed — by the time this strategy fires
        # (acceptance above IBH + ADX + EMA alignment), the engine has already
        # classified the day as directional (p_day/trend_up).
        # DuckDB "Neutral Range" is the session-level FINAL classification.

        # ── Phase 3: Check 15-min EMA alignment (bull) ──
        ema20_15m = bar.get('ema20_15m')
        ema50_15m = bar.get('ema50_15m')
        adx_15m = bar.get('adx14_15m')

        if ema20_15m is None or pd.isna(ema20_15m):
            return None
        if ema50_15m is None or pd.isna(ema50_15m):
            return None

        # Bull alignment: price > EMA20 > EMA50
        if not (current_price > ema20_15m > ema50_15m):
            return None

        # ADX gate: strong trend only (raised from 25 to 28 for quality)
        if adx_15m is None or pd.isna(adx_15m) or adx_15m < ADX_THRESHOLD:
            return None

        # Price must still be above IBH
        if current_price <= self._ib_high:
            return None

        # ── Phase 4: Delta confirmation ──
        delta = bar.get('delta', 0)
        if pd.isna(delta):
            delta = 0
        if delta <= 0:
            return None

        # ── Phase 5: Entry hierarchy ──
        entry_type = None

        # 1. VWAP pullback (strongest level)
        vwap = bar.get('vwap')
        if vwap is not None and not pd.isna(vwap) and self._ib_range > 0:
            vwap_dist = abs(current_price - vwap) / self._ib_range
            if vwap_dist < VWAP_PROXIMITY and current_price > vwap:
                entry_type = 'VWAP_PULLBACK'

        # 2. EMA20 (1-min) pullback
        if entry_type is None:
            ema20_1m = bar.get('ema20')
            if ema20_1m is not None and not pd.isna(ema20_1m) and self._ib_range > 0:
                ema_dist = abs(current_price - ema20_1m) / self._ib_range
                if ema_dist < EMA_PROXIMITY and current_price > ema20_1m:
                    entry_type = 'EMA20_PULLBACK'

        if entry_type is None:
            return None

        # ── Build signal ──
        self._signal_fired = True

        stop_price = current_price - STOP_FIXED_PTS
        target_price = current_price + TARGET_FIXED_PTS

        return Signal(
            timestamp=bar.get('timestamp', bar.name) if hasattr(bar, 'name') else bar.get('timestamp'),
            direction='LONG',
            entry_price=current_price,
            stop_price=stop_price,
            target_price=target_price,
            strategy_name=self.name,
            setup_type=entry_type,
            day_type=session_context.get('day_type', 'neutral'),
            trend_strength=session_context.get('trend_strength', 'moderate'),
            confidence='high',
            metadata={
                'ema20_15m': float(ema20_15m),
                'ema50_15m': float(ema50_15m),
                'adx14_15m': float(adx_15m),
                'delta': float(delta),
            },
        )
