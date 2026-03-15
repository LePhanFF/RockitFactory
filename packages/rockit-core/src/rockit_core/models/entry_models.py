"""Concrete entry model implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from rockit_core.models.base import EntryModel
from rockit_core.models.signals import Direction, EntrySignal

if TYPE_CHECKING:
    pass


class OrderFlowCVDEntry(EntryModel):
    """Entry based on Cumulative Volume Delta confirmation."""

    @property
    def name(self) -> str:
        return "orderflow_cvd"

    def evaluate(self, bar: pd.Series, session_context: dict) -> EntrySignal | None:
        delta = bar.get('vol_delta', 0)
        cvd_ema = bar.get('cvd_ema', None)
        close = bar['close']

        if delta is None or cvd_ema is None:
            return None

        # Strong positive delta + price above VWAP = long
        vwap = session_context.get('vwap', close)
        if delta > 0 and close > vwap and bar.get('vol_delta_pct', 0) > 70:
            return EntrySignal(
                model_name=self.name,
                direction=Direction.LONG,
                price=close,
                confidence=0.7,
                setup_type="CVD_MOMENTUM",
                metadata={"delta": delta, "cvd_ema": cvd_ema},
            )

        if delta < 0 and close < vwap and bar.get('vol_delta_pct', 0) > 70:
            return EntrySignal(
                model_name=self.name,
                direction=Direction.SHORT,
                price=close,
                confidence=0.7,
                setup_type="CVD_MOMENTUM",
                metadata={"delta": delta, "cvd_ema": cvd_ema},
            )

        return None


class TPORejectionEntry(EntryModel):
    """Entry based on TPO single print rejection."""

    @property
    def name(self) -> str:
        return "tpo_rejection"

    def evaluate(self, bar: pd.Series, session_context: dict) -> EntrySignal | None:
        ib_high = session_context.get('ib_high', 0)
        ib_low = session_context.get('ib_low', 0)
        close = bar['close']

        # Rejection from IB high (poor high = lack of acceptance)
        if bar['high'] > ib_high and close < ib_high:
            return EntrySignal(
                model_name=self.name,
                direction=Direction.SHORT,
                price=close,
                confidence=0.65,
                setup_type="TPO_HIGH_REJECTION",
            )

        # Rejection from IB low (poor low = lack of acceptance)
        if bar['low'] < ib_low and close > ib_low:
            return EntrySignal(
                model_name=self.name,
                direction=Direction.LONG,
                price=close,
                confidence=0.65,
                setup_type="TPO_LOW_REJECTION",
            )

        return None


class LiquiditySweepEntry(EntryModel):
    """Entry on liquidity sweep (stop hunt) reversal."""

    @property
    def name(self) -> str:
        return "liquidity_sweep"

    def evaluate(self, bar: pd.Series, session_context: dict) -> EntrySignal | None:
        session_high = session_context.get('prior_session_high', 0)
        session_low = session_context.get('prior_session_low', 999999)
        close = bar['close']

        # Sweep above prior session high then close below = short
        if bar['high'] > session_high and close < session_high:
            delta = bar.get('vol_delta', 0)
            if delta is not None and delta < 0:  # Sellers stepping in
                return EntrySignal(
                    model_name=self.name,
                    direction=Direction.SHORT,
                    price=close,
                    confidence=0.7,
                    setup_type="LIQUIDITY_SWEEP_HIGH",
                )

        # Sweep below prior session low then close above = long
        if bar['low'] < session_low and close > session_low:
            delta = bar.get('vol_delta', 0)
            if delta is not None and delta > 0:  # Buyers stepping in
                return EntrySignal(
                    model_name=self.name,
                    direction=Direction.LONG,
                    price=close,
                    confidence=0.7,
                    setup_type="LIQUIDITY_SWEEP_LOW",
                )

        return None


class SMTDivergenceEntry(EntryModel):
    """Entry based on Smart Money Technique divergence (ES vs NQ)."""

    @property
    def name(self) -> str:
        return "smt_divergence"

    def evaluate(self, bar: pd.Series, session_context: dict) -> EntrySignal | None:
        smt = session_context.get('smt_divergence')
        if not smt or not smt.get('active'):
            return None

        close = bar['close']
        direction = smt.get('direction')

        if direction == 'bullish':
            return EntrySignal(
                model_name=self.name,
                direction=Direction.LONG,
                price=close,
                confidence=0.65,
                setup_type="SMT_BULLISH_DIVERGENCE",
                metadata={"correlated_instrument": smt.get('instrument', 'ES')},
            )
        elif direction == 'bearish':
            return EntrySignal(
                model_name=self.name,
                direction=Direction.SHORT,
                price=close,
                confidence=0.65,
                setup_type="SMT_BEARISH_DIVERGENCE",
                metadata={"correlated_instrument": smt.get('instrument', 'ES')},
            )
        return None


class UnicornICTEntry(EntryModel):
    """Entry based on ICT Unicorn model (FVG + breaker block confluence)."""

    @property
    def name(self) -> str:
        return "unicorn_ict"

    def evaluate(self, bar: pd.Series, session_context: dict) -> EntrySignal | None:
        fvg = session_context.get('nearest_fvg')
        breaker = session_context.get('nearest_breaker')
        if not fvg or not breaker:
            return None

        close = bar['close']
        # Unicorn: FVG overlaps with breaker block
        fvg_high = fvg.get('high', 0)
        fvg_low = fvg.get('low', 0)
        breaker_high = breaker.get('high', 0)
        breaker_low = breaker.get('low', 0)

        overlap = min(fvg_high, breaker_high) > max(fvg_low, breaker_low)
        if not overlap:
            return None

        # Price entering the overlap zone
        zone_high = min(fvg_high, breaker_high)
        zone_low = max(fvg_low, breaker_low)

        if fvg.get('direction') == 'bullish' and zone_low <= close <= zone_high:
            return EntrySignal(
                model_name=self.name,
                direction=Direction.LONG,
                price=close,
                confidence=0.75,
                setup_type="UNICORN_BULLISH",
                metadata={"fvg": fvg, "breaker": breaker},
            )
        elif fvg.get('direction') == 'bearish' and zone_low <= close <= zone_high:
            return EntrySignal(
                model_name=self.name,
                direction=Direction.SHORT,
                price=close,
                confidence=0.75,
                setup_type="UNICORN_BEARISH",
                metadata={"fvg": fvg, "breaker": breaker},
            )
        return None


class ThreeDriveEntry(EntryModel):
    """Entry based on three-drive pattern (harmonic reversal)."""

    @property
    def name(self) -> str:
        return "three_drive"

    def evaluate(self, bar: pd.Series, session_context: dict) -> EntrySignal | None:
        pattern = session_context.get('three_drive_pattern')
        if not pattern or not pattern.get('complete'):
            return None

        close = bar['close']
        direction = pattern.get('direction')

        if direction == 'bullish':
            return EntrySignal(
                model_name=self.name,
                direction=Direction.LONG,
                price=close,
                confidence=0.6,
                setup_type="THREE_DRIVE_BULLISH",
            )
        elif direction == 'bearish':
            return EntrySignal(
                model_name=self.name,
                direction=Direction.SHORT,
                price=close,
                confidence=0.6,
                setup_type="THREE_DRIVE_BEARISH",
            )
        return None


class DoubleTopEntry(EntryModel):
    """Entry based on double top/bottom pattern."""

    @property
    def name(self) -> str:
        return "double_top"

    def evaluate(self, bar: pd.Series, session_context: dict) -> EntrySignal | None:
        pattern = session_context.get('double_top_bottom')
        if not pattern or not pattern.get('confirmed'):
            return None

        close = bar['close']
        if pattern.get('type') == 'double_top':
            return EntrySignal(
                model_name=self.name,
                direction=Direction.SHORT,
                price=close,
                confidence=0.6,
                setup_type="DOUBLE_TOP",
            )
        elif pattern.get('type') == 'double_bottom':
            return EntrySignal(
                model_name=self.name,
                direction=Direction.LONG,
                price=close,
                confidence=0.6,
                setup_type="DOUBLE_BOTTOM",
            )
        return None


class TrendlineEntry(EntryModel):
    """Entry based on trendline touch/bounce."""

    @property
    def name(self) -> str:
        return "trendline"

    def evaluate(self, bar: pd.Series, session_context: dict) -> EntrySignal | None:
        tl = session_context.get('trendline')
        if not tl or not tl.get('touch'):
            return None

        close = bar['close']
        if tl.get('direction') == 'up' and close > tl.get('price', 0):
            return EntrySignal(
                model_name=self.name,
                direction=Direction.LONG,
                price=close,
                confidence=0.6,
                setup_type="TRENDLINE_BOUNCE",
            )
        elif tl.get('direction') == 'down' and close < tl.get('price', 999999):
            return EntrySignal(
                model_name=self.name,
                direction=Direction.SHORT,
                price=close,
                confidence=0.6,
                setup_type="TRENDLINE_BOUNCE",
            )
        return None


class TrendlineBacksideEntry(EntryModel):
    """Entry on trendline backside retest (breakout retest)."""

    @property
    def name(self) -> str:
        return "trendline_backside"

    def evaluate(self, bar: pd.Series, session_context: dict) -> EntrySignal | None:
        tl = session_context.get('trendline_backside')
        if not tl or not tl.get('retest'):
            return None

        close = bar['close']
        if tl.get('direction') == 'bullish':
            return EntrySignal(
                model_name=self.name,
                direction=Direction.LONG,
                price=close,
                confidence=0.65,
                setup_type="TRENDLINE_BACKSIDE_LONG",
            )
        elif tl.get('direction') == 'bearish':
            return EntrySignal(
                model_name=self.name,
                direction=Direction.SHORT,
                price=close,
                confidence=0.65,
                setup_type="TRENDLINE_BACKSIDE_SHORT",
            )
        return None


class TickDivergenceEntry(EntryModel):
    """Entry based on $TICK divergence from price."""

    @property
    def name(self) -> str:
        return "tick_divergence"

    def evaluate(self, bar: pd.Series, session_context: dict) -> EntrySignal | None:
        tick = bar.get('tick', None)
        tick_ema = session_context.get('tick_ema', None)
        if tick is None or tick_ema is None:
            return None

        close = bar['close']
        prev_close = session_context.get('prev_close', close)

        # Bearish divergence: price makes new high but TICK doesn't
        if close > prev_close and tick < tick_ema:
            return EntrySignal(
                model_name=self.name,
                direction=Direction.SHORT,
                price=close,
                confidence=0.55,
                setup_type="TICK_BEARISH_DIVERGENCE",
            )

        # Bullish divergence: price makes new low but TICK doesn't
        if close < prev_close and tick > tick_ema:
            return EntrySignal(
                model_name=self.name,
                direction=Direction.LONG,
                price=close,
                confidence=0.55,
                setup_type="TICK_BULLISH_DIVERGENCE",
            )

        return None


class BPREntry(EntryModel):
    """Entry based on Balanced Price Range (overlapping FVGs)."""

    @property
    def name(self) -> str:
        return "bpr"

    def evaluate(self, bar: pd.Series, session_context: dict) -> EntrySignal | None:
        bpr = session_context.get('bpr')
        if not bpr or not bpr.get('active'):
            return None

        close = bar['close']
        bpr_high = bpr.get('high', 0)
        bpr_low = bpr.get('low', 0)

        # Price entering BPR zone
        if bpr_low <= close <= bpr_high:
            direction = bpr.get('direction')
            if direction == 'bullish':
                return EntrySignal(
                    model_name=self.name,
                    direction=Direction.LONG,
                    price=close,
                    confidence=0.7,
                    setup_type="BPR_BULLISH",
                )
            elif direction == 'bearish':
                return EntrySignal(
                    model_name=self.name,
                    direction=Direction.SHORT,
                    price=close,
                    confidence=0.7,
                    setup_type="BPR_BEARISH",
                )
        return None
