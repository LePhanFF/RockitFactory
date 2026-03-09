"""
Strategy: Opening Range Reversal (LONG and SHORT) — Judas Swing

Trades the ICT "Judas Swing" at market open. In the first 30 minutes
(9:30-10:00), price makes a false move to sweep pre-market liquidity
(overnight H/L, PDH/PDL, London H/L), then reverses. Enter on the reversal.

Study targets (strategy-studies/exploratory/):
  - Frequency: 9.6 trades/month
  - Win Rate: 60.9%
  - Profit Factor: 2.96
  - Monthly P&L: $2,720 (5 MNQ)
  - LONG direction dominates (75% WR)

Detection logic:
  1. OR = first 15 bars (9:30-9:44), EOR = first 30 bars (9:30-9:59)
  2. Sweep: EOR high/low near a key level (closest match, max dist = EOR range)
  3. Dual-sweep: if both high and low swept, pick deeper penetration
  4. Reversal: after the extreme bar, price closes beyond OR mid
  5. Entry on RETEST of 50% level (FVG zone) after reversal confirmed
  6. Stop: 2 ATR from entry (not swept level + buffer)
  7. Target: 2R
  8. Delta OR CVD divergence for confirmation
  9. All drives allowed (Judas swing is the drive + sweep pattern)

Implementation: Scans IB bars during on_session_start(), caches signal,
emits on first post-IB on_bar() call.
"""

from datetime import time as _time
from typing import Optional, List, Tuple
import pandas as pd
import numpy as np

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal

# Constants
OR_BARS = 15                      # First 15 bars = Opening Range (9:30-9:44)
EOR_BARS = 30                     # First 30 bars = Extended OR (9:30-9:59)
SWEEP_THRESHOLD_RATIO = 0.17      # Level proximity = 17% of EOR range
VWAP_ALIGNED_RATIO = 0.17         # VWAP proximity = 17% of EOR range
MIN_RISK_RATIO = 0.03             # Minimum risk = 3% of EOR range
MAX_RISK_RATIO = 1.3              # Maximum risk = 1.3x EOR range
DRIVE_THRESHOLD = 0.4             # Opening drive classification threshold
ATR_PERIOD = 14
ATR_STOP_MULT = 2.0               # Stop = entry ± 2 * ATR14


def _find_closest_swept_level(
    eor_extreme: float,
    candidates: List[Tuple[str, float]],
    sweep_threshold: float,
    eor_range: float,
    direction: str = "high",
) -> Tuple[Optional[float], Optional[str]]:
    """
    Find the closest swept level from candidates that was actually breached.

    A sweep requires price to EXCEED the level (Judas swing / liquidity grab):
      - High sweep: eor_high >= level (price breached above)
      - Low sweep: eor_low <= level (price breached below)
    """
    best_level = None
    best_name = None
    best_dist = float('inf')

    for name, lvl in candidates:
        if lvl is None:
            continue
        dist = abs(eor_extreme - lvl)
        if dist < sweep_threshold and dist < best_dist:
            best_dist = dist
            best_level = lvl
            best_name = name
    return best_level, best_name


def _compute_atr14(bars: pd.DataFrame, n: int = ATR_PERIOD) -> float:
    """Compute ATR(14) from OHLC bars."""
    if len(bars) < 3:
        return float((bars['high'] - bars['low']).mean()) if len(bars) > 0 else 20.0
    h = bars['high']
    l = bars['low']
    pc = bars['close'].shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(n, min_periods=3).mean().iloc[-1]
    return float(atr) if not pd.isna(atr) else float((h - l).mean())


class OpeningRangeReversal(StrategyBase):
    """
    Opening Range Reversal: fade the Judas Swing at the open.

    Scans the IB bars for OR reversal setups during on_session_start().
    """

    @property
    def name(self) -> str:
        return "Opening Range Rev"

    @property
    def applicable_day_types(self) -> List[str]:
        return []  # All day types

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._cached_signal = None
        self._signal_emitted = False
        self._ib_range = ib_range

        ib_bars = session_context.get('ib_bars')
        if ib_bars is None or len(ib_bars) < EOR_BARS:
            return

        # OR = first 15 bars (9:30-9:44)
        or_bars = ib_bars.iloc[:OR_BARS]
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()
        or_mid = (or_high + or_low) / 2

        # EOR = first 30 bars (9:30-9:59)
        eor_bars = ib_bars.iloc[:EOR_BARS]
        eor_high = eor_bars['high'].max()
        eor_low = eor_bars['low'].min()
        eor_range = eor_high - eor_low

        if eor_range < ib_range * 0.05 if ib_range > 0 else eor_range < 10:
            return

        # Proximity thresholds scaled to EOR range
        sweep_threshold = eor_range * SWEEP_THRESHOLD_RATIO
        max_risk = eor_range * MAX_RISK_RATIO

        # Classify opening drive from first 5 bars
        first_5 = ib_bars.iloc[:5]
        open_price = first_5.iloc[0]['open']
        close_5th = first_5.iloc[4]['close']
        drive_range = first_5['high'].max() - first_5['low'].min()
        drive_pct = (close_5th - open_price) / drive_range if drive_range > 0 else 0

        if drive_pct > DRIVE_THRESHOLD:
            opening_drive = 'DRIVE_UP'
        elif drive_pct < -DRIVE_THRESHOLD:
            opening_drive = 'DRIVE_DOWN'
        else:
            opening_drive = 'ROTATION'

        # Get overnight levels from session context
        overnight_high = session_context.get('overnight_high') or session_context.get('prior_session_high')
        overnight_low = session_context.get('overnight_low') or session_context.get('prior_session_low')

        if overnight_high is None or overnight_low is None:
            return

        pdh = session_context.get('pdh') or session_context.get('prior_session_high')
        pdl = session_context.get('pdl') or session_context.get('prior_session_low')
        asia_high = session_context.get('asia_high')
        asia_low = session_context.get('asia_low')
        london_high = session_context.get('london_high')
        london_low = session_context.get('london_low')

        # Build named candidate lists for sweep detection
        high_candidates = [('ON_HIGH', overnight_high)]
        if pdh:
            high_candidates.append(('PDH', pdh))
        if asia_high:
            high_candidates.append(('ASIA_HIGH', asia_high))
        if london_high:
            high_candidates.append(('LDN_HIGH', london_high))

        low_candidates = [('ON_LOW', overnight_low)]
        if pdl:
            low_candidates.append(('PDL', pdl))
        if asia_low:
            low_candidates.append(('ASIA_LOW', asia_low))
        if london_low:
            low_candidates.append(('LDN_LOW', london_low))

        # Sweep detection: pick CLOSEST level actually breached
        swept_high_level, swept_high_name = _find_closest_swept_level(
            eor_high, high_candidates, sweep_threshold, eor_range, direction="high")
        swept_low_level, swept_low_name = _find_closest_swept_level(
            eor_low, low_candidates, sweep_threshold, eor_range, direction="low")

        if swept_high_level is None and swept_low_level is None:
            return

        # Dual-sweep: if BOTH sides swept, keep deeper penetration
        if swept_high_level is not None and swept_low_level is not None:
            high_depth = eor_high - swept_high_level
            low_depth = swept_low_level - eor_low
            if high_depth >= low_depth:
                swept_low_level = None
                swept_low_name = None
            else:
                swept_high_level = None
                swept_high_name = None

        # Find extreme bars in EOR
        high_bar_idx = eor_bars['high'].idxmax()
        low_bar_idx = eor_bars['low'].idxmin()

        # Compute CVD for divergence check
        deltas = ib_bars['delta'] if 'delta' in ib_bars.columns else ib_bars.get('vol_delta', pd.Series(dtype=float))
        if deltas is not None and len(deltas) > 0:
            deltas = deltas.fillna(0)
            cvd_series = deltas.cumsum()
        else:
            cvd_series = None

        # === SHORT SETUP: Judas swing UP, then reversal DOWN ===
        if swept_high_level is not None:
            cvd_at_extreme = cvd_series.loc[high_bar_idx] if cvd_series is not None else None
            post_high = ib_bars.loc[high_bar_idx:]
            atr14 = _compute_atr14(ib_bars)

            # 50% retest level between sweep extreme and reversal low
            post_closes = post_high['close']
            reversal_low = float(post_closes.min()) if len(post_closes) > 1 else eor_high
            fifty_pct = reversal_low + (eor_high - reversal_low) * 0.50

            in_reversal = False
            for j in range(1, min(40, len(post_high))):
                bar = post_high.iloc[j]
                price = bar['close']
                prev_price = post_high.iloc[j - 1]['close']

                # Phase 1: wait for reversal below OR mid
                if price < or_mid:
                    in_reversal = True
                if not in_reversal:
                    continue

                # Phase 2: entry on RETEST of 50% level
                entry_lo = fifty_pct - atr14 * 0.5
                entry_hi = fifty_pct + atr14 * 0.5
                if not (entry_lo <= price <= entry_hi):
                    continue

                # Must be turning down (retest failing)
                if price >= prev_price:
                    continue

                # Delta OR CVD divergence confirmation
                delta = bar.get('delta', bar.get('vol_delta', 0))
                if pd.isna(delta):
                    delta = 0
                cvd_at_entry = cvd_series.loc[post_high.index[j]] if cvd_series is not None else None
                cvd_declining = (cvd_at_entry is not None and cvd_at_extreme is not None
                                 and cvd_at_entry < cvd_at_extreme)
                if delta >= 0 and not cvd_declining:
                    continue

                # Stop: 2 ATR above entry
                stop = price + ATR_STOP_MULT * atr14
                risk = stop - price
                if risk < eor_range * MIN_RISK_RATIO or risk > max_risk:
                    continue
                target = price - 2 * risk

                bar_ts = bar.get('timestamp', bar.name) if hasattr(bar, 'name') else bar.get('timestamp')
                self._cached_signal = Signal(
                    timestamp=bar_ts,
                    direction='SHORT',
                    entry_price=price,
                    stop_price=stop,
                    target_price=target,
                    strategy_name=self.name,
                    setup_type='OR_REVERSAL_SHORT',
                    day_type='neutral',
                    trend_strength='moderate',
                    confidence='high',
                    metadata={
                        'level_swept': swept_high_name,
                        'swept_level_price': swept_high_level,
                        'sweep_depth': eor_high - swept_high_level,
                        'fifty_pct_level': fifty_pct,
                        'atr14': atr14,
                        'opening_drive': opening_drive,
                        'cvd_declining': cvd_declining,
                    },
                )
                return

        # === LONG SETUP: Judas swing DOWN, then reversal UP ===
        if swept_low_level is not None:
            cvd_at_extreme = cvd_series.loc[low_bar_idx] if cvd_series is not None else None
            post_low = ib_bars.loc[low_bar_idx:]
            atr14 = _compute_atr14(ib_bars)

            # 50% retest level between sweep extreme and reversal high
            post_closes = post_low['close']
            reversal_high = float(post_closes.max()) if len(post_closes) > 1 else eor_low
            fifty_pct = reversal_high - (reversal_high - eor_low) * 0.50

            in_reversal = False
            for j in range(1, min(40, len(post_low))):
                bar = post_low.iloc[j]
                price = bar['close']
                prev_price = post_low.iloc[j - 1]['close']

                # Phase 1: wait for reversal above OR mid
                if price > or_mid:
                    in_reversal = True
                if not in_reversal:
                    continue

                # Phase 2: entry on RETEST of 50% level
                entry_lo = fifty_pct - atr14 * 0.5
                entry_hi = fifty_pct + atr14 * 0.5
                if not (entry_lo <= price <= entry_hi):
                    continue

                # Must be turning up (retest holding)
                if price <= prev_price:
                    continue

                # Delta OR CVD divergence confirmation
                delta = bar.get('delta', bar.get('vol_delta', 0))
                if pd.isna(delta):
                    delta = 0
                cvd_at_entry = cvd_series.loc[post_low.index[j]] if cvd_series is not None else None
                cvd_rising = (cvd_at_entry is not None and cvd_at_extreme is not None
                              and cvd_at_entry > cvd_at_extreme)
                if delta <= 0 and not cvd_rising:
                    continue

                # Stop: 2 ATR below entry
                stop = price - ATR_STOP_MULT * atr14
                risk = price - stop
                if risk < eor_range * MIN_RISK_RATIO or risk > max_risk:
                    continue
                target = price + 2 * risk

                bar_ts = bar.get('timestamp', bar.name) if hasattr(bar, 'name') else bar.get('timestamp')
                self._cached_signal = Signal(
                    timestamp=bar_ts,
                    direction='LONG',
                    entry_price=price,
                    stop_price=stop,
                    target_price=target,
                    strategy_name=self.name,
                    setup_type='OR_REVERSAL_LONG',
                    day_type='neutral',
                    trend_strength='moderate',
                    confidence='high',
                    metadata={
                        'level_swept': swept_low_name,
                        'swept_level_price': swept_low_level,
                        'sweep_depth': swept_low_level - eor_low,
                        'fifty_pct_level': fifty_pct,
                        'atr14': atr14,
                        'opening_drive': opening_drive,
                        'cvd_rising': cvd_rising,
                    },
                )
                return

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        # Emit cached signal on first bar after IB
        if self._cached_signal is not None and not self._signal_emitted:
            self._signal_emitted = True
            signal = self._cached_signal
            self._cached_signal = None
            return signal
        return None
