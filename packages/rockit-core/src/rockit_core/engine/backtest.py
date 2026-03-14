"""
Unified Backtest Engine.

Replaces: backtest_engine.py, dalton_playbook_engine.py,
          trend_following_engine.py, and the _simulate_trade()
          methods embedded in playbook_strategies.py.

Pipeline: data -> session grouping -> IB detection -> day type classification
       -> strategy signals -> filter chain -> execution -> position management
       -> equity tracking -> results
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from rockit_core.config.constants import (
    DEFAULT_MAX_CONTRACTS,
    DEFAULT_MAX_RISK_PER_TRADE,
    EOD_CUTOFF,
    IB_BARS_1MIN,
    PM_SESSION_START,
    VWAP_BREACH_POINTS,
)
from rockit_core.config.instruments import InstrumentSpec
from rockit_core.engine.equity import EquityCurve
from rockit_core.engine.execution import ExecutionModel
from rockit_core.engine.position import OpenPosition, PositionManager
from rockit_core.engine.trade import Trade
from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.day_confidence import DayTypeConfidenceScorer
from rockit_core.strategies.day_type import DayType, classify_day_type, classify_trend_strength
from rockit_core.strategies.signal import Signal


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    trades: List[Trade] = field(default_factory=list)
    equity_curve: Optional[EquityCurve] = None
    sessions_processed: int = 0
    signals_generated: int = 0
    signals_filtered: int = 0
    signals_executed: int = 0


class BacktestEngine:
    """
    Unified bar-by-bar backtest engine.

    For each session:
      1. Compute IB from first 60 1-min bars
      2. Classify day type + trend strength
      3. Build session_context dict
      4. Notify strategies via on_session_start()
      5. For each bar after IB:
         a. Manage open positions (check stop/target hit)
         b. PM management (trail to BE after 1PM, VWAP breach exit)
         c. Check PositionManager limits
         d. If daily loss exceeded: force close all open positions
         e. Ask each active strategy: on_bar() -> Signal?
         f. Apply filter chain to signal
         g. If passes: execute via ExecutionModel
      6. Force close any open positions at EOD
      7. Notify strategies via on_session_end()
    """

    def __init__(
        self,
        instrument: InstrumentSpec,
        strategies: List[StrategyBase],
        filters=None,
        execution: Optional[ExecutionModel] = None,
        position_mgr: Optional[PositionManager] = None,
        risk_per_trade: float = DEFAULT_MAX_RISK_PER_TRADE,
        max_contracts: int = DEFAULT_MAX_CONTRACTS,
        session_bias_lookup: Optional[Dict[str, str]] = None,
        trail_configs: Optional[Dict[str, dict]] = None,
    ):
        self.instrument = instrument
        self.strategies = strategies
        self.filters = filters
        self.execution = execution or ExecutionModel(instrument)
        self.position_mgr = position_mgr or PositionManager()
        self.risk_per_trade = risk_per_trade
        self.max_contracts = max_contracts
        self.session_bias_lookup = session_bias_lookup or {}
        self.trail_configs = trail_configs or {}

    def run(self, df: pd.DataFrame, verbose: bool = True) -> BacktestResult:
        """Run the backtest on the provided DataFrame."""
        result = BacktestResult()
        result.equity_curve = EquityCurve(self.position_mgr.equity)

        # Ensure we have a timestamp-based index or column
        if 'timestamp' in df.columns:
            df = df.copy()
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        elif isinstance(df.index, pd.DatetimeIndex):
            df = df.copy()
            df['timestamp'] = df.index

        # Get session grouping
        if 'session_date' not in df.columns:
            df['session_date'] = df['timestamp'].dt.date

        sessions = sorted(df['session_date'].unique())

        if verbose:
            print(f"Backtest: {len(sessions)} sessions, {len(self.strategies)} strategies")
            print(f"  Instrument: {self.instrument.symbol}")
            print(f"  Risk/trade: ${self.risk_per_trade}")
            print(f"  Slippage: {self.execution.slippage_ticks} ticks/side")
            print(f"  Commission: ${self.execution.commission}/side")
            print()

        prior_session_context = {}  # Tracks prior session info for context
        self._ib_range_history = []  # Rolling IB ranges for adaptive thresholds

        # Pre-compute session enrichment data (single prints, etc.)
        try:
            from rockit_core.indicators.session_enrichment import enrich_prior_session_data
            self._session_enrichment = enrich_prior_session_data(df)
        except Exception:
            self._session_enrichment = {}

        total_sessions = len(sessions)
        for idx, session_date in enumerate(sessions):
            session_df = df[df['session_date'] == session_date].copy()
            session_str = str(session_date)

            if len(session_df) < IB_BARS_1MIN:
                continue

            if verbose and idx % 25 == 0:
                print(f"  [{idx+1}/{total_sessions}] Processing {session_str}...")

            self._process_session(
                session_df, session_str, result, verbose,
                prior_session_context=prior_session_context,
            )
            result.sessions_processed += 1

            # Track IB range history for adaptive thresholds (use RTH IB)
            from rockit_core.config.constants import RTH_START, RTH_END
            if 'timestamp' in session_df.columns:
                _times = pd.to_datetime(session_df['timestamp']).dt.time
                _rth = session_df[(_times >= RTH_START) & (_times <= RTH_END)]
            else:
                _rth = session_df
            if len(_rth) >= IB_BARS_1MIN:
                _ib_df = _rth.head(IB_BARS_1MIN)
                _ib_r = _ib_df['high'].max() - _ib_df['low'].min()
                if _ib_r > 0:
                    self._ib_range_history.append(float(_ib_r))

            # Store prior session data for next session
            last_bar = session_df.iloc[-1]
            prior_session_context = {
                'prior_close': last_bar['close'],
                'prior_vwap': last_bar.get('vwap', None),
                'prior_session_high': session_df['high'].max(),
                'prior_session_low': session_df['low'].min(),
                'pdh': session_df['high'].max(),
                'pdl': session_df['low'].min(),
            }

            # Record equity snapshot at session end
            result.equity_curve.record(
                timestamp=session_df['timestamp'].iloc[-1],
                equity=self.position_mgr.equity,
                daily_pnl=self.position_mgr.daily_pnl.get(session_str, 0),
                trade_count=self.position_mgr.daily_trade_count.get(session_str, 0),
                session_date=session_str,
            )

        if verbose:
            self._print_summary(result)

        return result

    def _process_session(
        self, session_df: pd.DataFrame, session_str: str,
        result: BacktestResult, verbose: bool,
        prior_session_context: Optional[Dict] = None,
    ) -> None:
        """Process a single trading session."""
        # --- Phase 1: Compute IB from RTH bars (9:30-10:29), not ETH ---
        # Sessions contain full ETH data (18:01 prior day -> 17:00 current day).
        # We need to find RTH start and compute IB from there.
        from rockit_core.config.constants import RTH_START, RTH_END
        if 'timestamp' in session_df.columns:
            bar_times = pd.to_datetime(session_df['timestamp']).dt.time
        elif isinstance(session_df.index, pd.DatetimeIndex):
            bar_times = session_df.index.time
        else:
            bar_times = None

        if bar_times is not None:
            rth_mask = (bar_times >= RTH_START) & (bar_times <= RTH_END)
            rth_df = session_df[rth_mask]
        else:
            rth_df = session_df

        if len(rth_df) < IB_BARS_1MIN:
            return

        ib_df = rth_df.head(IB_BARS_1MIN)
        ib_high = ib_df['high'].max()
        ib_low = ib_df['low'].min()
        ib_range = ib_high - ib_low
        ib_mid = (ib_high + ib_low) / 2

        if ib_range <= 0:
            return

        # --- Phase 2: Classify day type ---
        # Use end-of-IB price for initial classification
        # Post-IB = bars after the first 60 RTH bars (i.e., after 10:29)
        rth_post_ib = rth_df.iloc[IB_BARS_1MIN:]
        post_ib_df = rth_post_ib
        if len(post_ib_df) == 0:
            return

        last_ib_close = ib_df['close'].iloc[-1]
        ext_mult = 0.0
        if last_ib_close > ib_high:
            ext_mult = (last_ib_close - ib_mid) / ib_range
        elif last_ib_close < ib_low:
            ext_mult = (ib_mid - last_ib_close) / ib_range

        trend_strength = classify_trend_strength(ext_mult)

        # We'll reclassify dynamically as session progresses
        ib_direction = 'INSIDE'

        # --- Phase 3: Build session context ---
        session_context = {
            'ib_high': ib_high,
            'ib_low': ib_low,
            'ib_range': ib_range,
            'ib_mid': ib_mid,
            'day_type': DayType.NEUTRAL.value,
            'trend_strength': trend_strength.value,
            'session_date': session_str,
        }

        # Pass IB bars to strategies (needed by OR Reversal, OR Acceptance)
        session_context['ib_bars'] = ib_df

        # IB range history for adaptive thresholds (B-Day strategy)
        session_context['ib_range_history'] = list(self._ib_range_history)

        # Regime volatility classification based on rolling IB median
        if len(self._ib_range_history) >= 10:
            median_ib = float(np.median(self._ib_range_history[-20:]))
            if median_ib < 130:
                session_context['regime_volatility'] = 'low'
            elif median_ib < 250:
                session_context['regime_volatility'] = 'normal'
            else:
                session_context['regime_volatility'] = 'high'
        else:
            session_context['regime_volatility'] = 'normal'

        # Add latest indicator values from IB end
        last_ib = ib_df.iloc[-1]
        for col in ['vwap', 'ema20', 'ema50', 'atr14', 'rsi14', 'adx14']:
            if col in last_ib.index:
                session_context[col] = last_ib[col]

        # Add IB width classification features (from data pipeline)
        ib_width_cols = [
            'ib_width_class', 'ib_atr_ratio',
            'a_period_high', 'a_period_low', 'a_period_range',
            'b_period_high', 'b_period_low', 'b_period_range',
            'c_period_bias', 'is_nr4', 'is_nr7',
            'ext_1_0_high', 'ext_1_0_low',
            'ext_1_5_high', 'ext_1_5_low',
            'ext_2_0_high', 'ext_2_0_low',
            'ext_3_0_high', 'ext_3_0_low',
            # Prior day Value Area (for 80P strategy)
            'prior_va_poc', 'prior_va_vah', 'prior_va_val',
            'prior_va_width', 'prior_va_high', 'prior_va_low',
            'open_vs_va',
            # Overnight/London/Asia levels (for OR strategies)
            'overnight_high', 'overnight_low',
            'asia_high', 'asia_low',
            'london_high', 'london_low',
        ]
        for col in ib_width_cols:
            if col in last_ib.index:
                val = last_ib[col]
                if not pd.isna(val) if not isinstance(val, str) else val is not None:
                    session_context[col] = val

        # Add prior session context
        if prior_session_context:
            session_context.update(prior_session_context)
            # Compute prior session bias: close above/below VWAP
            pc = prior_session_context.get('prior_close')
            pv = prior_session_context.get('prior_vwap')
            if pc is not None and pv is not None and not pd.isna(pv):
                session_context['prior_session_bullish'] = pc > pv
            else:
                session_context['prior_session_bullish'] = None

        # Inject precomputed session bias from deterministic tape (if available)
        # Normalize session key — session_str may be '2025-02-20 00:00:00' or '2025-02-20'
        bias_key = session_str.split(" ")[0].split("T")[0]
        session_context['session_bias'] = self.session_bias_lookup.get(bias_key, 'NEUTRAL')

        # Compute real-time regime_bias from available indicators (3-vote system)
        regime_bias = self._compute_regime_bias(session_context)
        session_context['regime_bias'] = regime_bias

        # --- Phase 3a2: Store RTH bars + prior day context for TPO snapshot ---
        self._current_rth_df = rth_df
        self._prior_day_for_tpo = {
            'poc': session_context.get('prior_va_poc'),
            'vah': session_context.get('prior_va_vah'),
            'val': session_context.get('prior_va_val'),
            'high': session_context.get('pdh'),
            'low': session_context.get('pdl'),
        }

        # --- Phase 3b: Initialize day type confidence scorer ---
        confidence_scorer = DayTypeConfidenceScorer()
        atr = session_context.get('atr14', 0.0)
        confidence_scorer.on_session_start(ib_high, ib_low, ib_range, atr)

        # --- Phase 3c: Inject session enrichment (single prints, etc.) ---
        # Try both normalized and raw key formats
        enrichment_key = session_str.split(" ")[0].split("T")[0]
        enrichment = self._session_enrichment.get(enrichment_key) or self._session_enrichment.get(session_str, {})
        if enrichment:
            session_context.setdefault('prior_day', {})
            if isinstance(session_context['prior_day'], dict):
                session_context['prior_day'].update(enrichment)
            # Also put in tpo_data for backward compat
            session_context.setdefault('tpo_data', {})
            if isinstance(session_context['tpo_data'], dict):
                session_context['tpo_data'].update(enrichment)

        # --- Phase 4: Notify strategies ---
        active_strategies = []
        for strategy in self.strategies:
            strategy.on_session_start(
                session_date=session_str,
                ib_high=ib_high,
                ib_low=ib_low,
                ib_range=ib_range,
                session_context=session_context,
            )
            active_strategies.append(strategy)

        # Track session high/low for trailing stops
        session_high = ib_high
        session_low = ib_low

        # --- Phase 4b: Pre-IB bar signals (gap fill strategies enter during IB) ---
        self._process_pre_ib_bars(
            ib_df, active_strategies, session_context, session_str,
            result, session_high, session_low, ib_range,
        )

        # --- Phase 5: Bar-by-bar after IB ---
        for bar_idx in range(len(post_ib_df)):
            bar = post_ib_df.iloc[bar_idx]
            timestamp = bar['timestamp'] if 'timestamp' in bar.index else post_ib_df.index[bar_idx]
            bar_time = timestamp.time() if hasattr(timestamp, 'time') else None

            # Track session extremes
            if bar['high'] > session_high:
                session_high = bar['high']
            if bar['low'] < session_low:
                session_low = bar['low']

            # 5a: Update dynamic session context
            current_price = bar['close']
            if current_price > ib_high:
                ib_direction = 'BULL'
                ext = (current_price - ib_mid) / ib_range
            elif current_price < ib_low:
                ib_direction = 'BEAR'
                ext = (ib_mid - current_price) / ib_range
            else:
                ib_direction = 'INSIDE'
                ext = 0.0

            trend_strength = classify_trend_strength(ext)
            day_type = classify_day_type(ib_high, ib_low, current_price, ib_direction, trend_strength)

            session_context['day_type'] = day_type.value
            session_context['trend_strength'] = trend_strength.value
            session_context['ib_direction'] = ib_direction
            session_context['current_price'] = current_price
            session_context['bar_time'] = bar_time

            # Update VWAP if available
            if 'vwap' in bar.index:
                session_context['vwap'] = bar['vwap']

            # Refresh regime_bias per bar (uses current price + VWAP)
            session_context['regime_bias'] = self._compute_regime_bias(session_context)

            # 5a2: Update day type confidence scorer
            day_confidence = confidence_scorer.update(bar, bar_idx)
            session_context['day_confidence'] = day_confidence
            session_context['trend_bull_confidence'] = day_confidence.trend_bull
            session_context['trend_bear_confidence'] = day_confidence.trend_bear
            session_context['p_day_bull_confidence'] = day_confidence.p_day_bull
            session_context['p_day_bear_confidence'] = day_confidence.p_day_bear
            session_context['b_day_confidence'] = day_confidence.b_day

            # 5b: Manage open positions
            closed_trades = self._manage_positions(
                bar, timestamp, session_str, bar_time,
                session_high=session_high, session_low=session_low, ib_range=ib_range,
            )
            for trade in closed_trades:
                result.trades.append(trade)

            # 5c: Check if daily loss exceeded -> force close
            if self.position_mgr.daily_loss_exceeded(session_str):
                force_closed = self._force_close_all(bar, timestamp, session_str, 'DAILY_LOSS')
                result.trades.extend(force_closed)
                continue

            # 5d: Skip if can't open new trades
            if not self.position_mgr.can_open_trade(session_str):
                continue

            # 5e: Check contract limits
            open_contracts = self.position_mgr.get_open_contracts()
            if open_contracts >= self.max_contracts:
                continue

            # 5f: Get signals from active strategies
            # Note: ALL strategies receive on_bar() calls so they can track
            # state (acceptance, wick counts, etc.) across day-type transitions.
            # Each strategy checks day_type internally and only emits signals
            # when conditions match.
            for strategy in active_strategies:
                signal = strategy.on_bar(bar, bar_idx, session_context)
                if signal is None:
                    continue

                # Attach TPO snapshot at signal time
                from rockit_core.engine.tpo_snapshot import generate_signal_tpo_snapshot
                bar_time_str = bar_time.strftime('%H:%M') if bar_time else '10:30'
                try:
                    tpo_snap = generate_signal_tpo_snapshot(
                        self._current_rth_df,
                        bar_time_str,
                        self._prior_day_for_tpo,
                    )
                    signal.metadata['tpo_at_entry'] = tpo_snap
                except Exception:
                    pass  # Don't let TPO failure block signal execution

                result.signals_generated += 1

                # 5g: Apply filters
                if self.filters is not None:
                    if not self.filters.should_trade(signal, bar, session_context):
                        result.signals_filtered += 1
                        continue

                # 5h: Execute
                trade = self._execute_signal(signal, bar, timestamp, session_str)
                if trade is not None:
                    result.signals_executed += 1

        # --- Phase 6: Force close EOD ---
        if self.position_mgr.has_open_positions():
            last_bar = post_ib_df.iloc[-1]
            last_ts = last_bar['timestamp'] if 'timestamp' in last_bar.index else post_ib_df.index[-1]
            eod_trades = self._force_close_all(last_bar, last_ts, session_str, 'EOD')
            result.trades.extend(eod_trades)

        # --- Phase 7: Notify strategies ---
        for strategy in active_strategies:
            strategy.on_session_end(session_str)

    def _process_pre_ib_bars(
        self,
        ib_df: pd.DataFrame,
        active_strategies: List[StrategyBase],
        session_context: dict,
        session_str: str,
        result: BacktestResult,
        session_high: float,
        session_low: float,
        ib_range: float,
    ) -> None:
        """Process IB bars through on_pre_ib_bar() for early-entry strategies.

        Called after on_session_start() but before the post-IB bar loop.
        Strategies that need to enter before IB close (e.g., gap fill)
        implement on_pre_ib_bar() and return a Signal.

        Signal processing (filters, execution) mirrors the post-IB logic.
        Position management also runs on each pre-IB bar so stops/targets
        are checked if a pre-IB entry was made.
        """
        for bar_idx in range(len(ib_df)):
            bar = ib_df.iloc[bar_idx]
            timestamp = bar['timestamp'] if 'timestamp' in bar.index else ib_df.index[bar_idx]
            bar_time = timestamp.time() if hasattr(timestamp, 'time') else None

            # Build a partial session context for pre-IB bars
            pre_ib_ctx = dict(session_context)
            pre_ib_ctx['bar_time'] = bar_time
            pre_ib_ctx['current_price'] = bar['close']
            if 'vwap' in bar.index:
                pre_ib_ctx['vwap'] = bar['vwap']

            # Manage any positions opened by earlier pre-IB signals
            if self.position_mgr.has_open_positions():
                closed_trades = self._manage_positions(
                    bar, timestamp, session_str, bar_time,
                    session_high=session_high, session_low=session_low,
                    ib_range=ib_range,
                )
                for trade in closed_trades:
                    result.trades.append(trade)

            # Check daily loss / trade limits before soliciting signals
            if self.position_mgr.daily_loss_exceeded(session_str):
                force_closed = self._force_close_all(bar, timestamp, session_str, 'DAILY_LOSS')
                result.trades.extend(force_closed)
                continue

            if not self.position_mgr.can_open_trade(session_str):
                continue

            open_contracts = self.position_mgr.get_open_contracts()
            if open_contracts >= self.max_contracts:
                continue

            # Ask each strategy for a pre-IB signal
            for strategy in active_strategies:
                signal = strategy.on_pre_ib_bar(bar, bar_idx, pre_ib_ctx)
                if signal is None:
                    continue

                # Attach TPO snapshot at signal time
                from rockit_core.engine.tpo_snapshot import generate_signal_tpo_snapshot
                bar_time_str = bar_time.strftime('%H:%M') if bar_time else '09:30'
                try:
                    tpo_snap = generate_signal_tpo_snapshot(
                        self._current_rth_df,
                        bar_time_str,
                        self._prior_day_for_tpo,
                    )
                    signal.metadata['tpo_at_entry'] = tpo_snap
                except Exception:
                    pass

                result.signals_generated += 1

                # Apply filters
                if self.filters is not None:
                    if not self.filters.should_trade(signal, bar, pre_ib_ctx):
                        result.signals_filtered += 1
                        continue

                # Execute
                trade = self._execute_signal(signal, bar, timestamp, session_str)
                if trade is not None:
                    result.signals_executed += 1

    @staticmethod
    def _compute_regime_bias(ctx: dict) -> str:
        """Compute regime bias from available indicators (3-vote system).

        Votes:
          - EMA20 vs EMA50 (2x weight): BULL if ema20 > ema50
          - Prior session bullish (1x): BULL if prior close > prior VWAP
          - Price vs VWAP (1x): BULL if current price > VWAP
        Returns: 'BULL', 'BEAR', or 'NEUTRAL'
        """
        bull_votes = 0
        bear_votes = 0

        ema20 = ctx.get('ema20')
        ema50 = ctx.get('ema50')
        if ema20 is not None and ema50 is not None:
            if not (isinstance(ema20, float) and np.isnan(ema20)) and \
               not (isinstance(ema50, float) and np.isnan(ema50)):
                if ema20 > ema50:
                    bull_votes += 2
                elif ema50 > ema20:
                    bear_votes += 2

        prior_bullish = ctx.get('prior_session_bullish')
        if prior_bullish is True:
            bull_votes += 1
        elif prior_bullish is False:
            bear_votes += 1

        price = ctx.get('current_price')
        vwap = ctx.get('vwap')
        if price is not None and vwap is not None:
            if not (isinstance(vwap, float) and np.isnan(vwap)):
                if price > vwap:
                    bull_votes += 1
                elif price < vwap:
                    bear_votes += 1

        if bull_votes > bear_votes:
            return 'BULL'
        elif bear_votes > bull_votes:
            return 'BEAR'
        return 'NEUTRAL'

    def _manage_positions(
        self, bar: pd.Series, timestamp, session_str: str, bar_time,
        session_high: float = 0, session_low: float = 0, ib_range: float = 0,
    ) -> List[Trade]:
        """Check open positions for stop/target hit and PM management."""
        closed_trades = []
        positions_to_close = []

        trend_strategies = ('Trend Day Bull', 'Trend Day Bear',
                           'Super Trend Bull', 'Super Trend Bear',
                           'Morph to Trend')

        # 80P is mean-reversion to VA — exempt from VWAP breach PM exit
        # and trend trailing. Its stop/target handle exits.
        mean_reversion_strategies = ('80P Rule',)

        for pos in self.position_mgr.open_positions:
            pos.bars_held += 1

            # Update MAE/MFE before checking stop/target
            pos.update_excursions(bar['low'], bar['high'])

            # ATR-based trailing stop (per-strategy config from strategies.yaml)
            trail_cfg = self.trail_configs.get(pos.strategy_name)
            if trail_cfg:
                atr_col = f"atr_{trail_cfg['atr_period']}"
                atr_val = bar.get(atr_col) if atr_col in bar.index else bar.get('atr14')
                if atr_val and not pd.isna(atr_val) and atr_val > 0:
                    act_dist = atr_val * trail_cfg['activate_mult']
                    trail_dist = atr_val * trail_cfg['trail_mult']
                    pos.trail_by_atr(bar['high'], bar['low'], act_dist, trail_dist)

            # Trend strategy trailing: trail by 1.0x IB range from session extreme
            # This locks in profit as the trend extends while giving enough room
            if pos.strategy_name in trend_strategies and ib_range > 0:
                if pos.bars_held >= 20 and pos.unrealized_pnl_points(bar['close']) > ib_range * 0.5:
                    trail_dist = ib_range * 1.0  # trail 1 IB range behind extreme
                    pos.trail_by_session_extreme(session_high, session_low, trail_dist)

            # PM Management: trail to breakeven after 1 PM
            # Only trail to BE when profit exceeds a meaningful threshold.
            # Trailing at any tiny profit caused 23 premature BE stops (-$2.74).
            # Require at least 0.3x IB range profit before activating BE trail.
            if bar_time and bar_time >= PM_SESSION_START:
                min_be_profit = ib_range * 0.3 if ib_range > 0 else 20.0
                if pos.unrealized_pnl_points(bar['close']) > min_be_profit:
                    pos.trail_to_breakeven()

                # VWAP breach in PM = trend failure
                # Only apply to non-trend and non-mean-reversion strategies.
                # Trend day entries with acceptance hold through PM; their stop handles exits.
                # 80P mean-reversion trades target VA traverse, not VWAP alignment.
                if pos.strategy_name not in trend_strategies and pos.strategy_name not in mean_reversion_strategies:
                    if 'vwap' in bar.index:
                        vwap = bar['vwap']
                        if pos.direction == 'LONG' and bar['close'] < vwap - VWAP_BREACH_POINTS:
                            positions_to_close.append((pos, 'VWAP_BREACH_PM', bar['close']))
                            continue
                        elif pos.direction == 'SHORT' and bar['close'] > vwap + VWAP_BREACH_POINTS:
                            positions_to_close.append((pos, 'VWAP_BREACH_PM', bar['close']))
                            continue

            # EOD cutoff
            if bar_time and bar_time >= EOD_CUTOFF:
                positions_to_close.append((pos, 'EOD', bar['close']))
                continue

            # Check stop
            if pos.check_stop_hit(bar['low'], bar['high']):
                exit_price = pos.trailing_stop
                positions_to_close.append((pos, 'STOP', exit_price))
                continue

            # Check target
            if pos.check_target_hit(bar['low'], bar['high']):
                exit_price = pos.target_price
                positions_to_close.append((pos, 'TARGET', exit_price))
                continue

        # Close positions
        for pos, reason, exit_price in positions_to_close:
            trade = self._close_position(pos, exit_price, timestamp, session_str, reason)
            closed_trades.append(trade)
            self.position_mgr.remove_position(pos)

        return closed_trades

    def _force_close_all(
        self, bar: pd.Series, timestamp, session_str: str, reason: str,
    ) -> List[Trade]:
        """Force close all open positions."""
        trades = []
        positions = self.position_mgr.close_all_positions()
        for pos in positions:
            trade = self._close_position(pos, bar['close'], timestamp, session_str, reason)
            trades.append(trade)
        return trades

    def _close_position(
        self, pos: OpenPosition, raw_exit_price: float,
        timestamp, session_str: str, reason: str,
    ) -> Trade:
        """Close a position and create a Trade record."""
        exit_fill = self.execution.fill_exit(pos.direction, raw_exit_price)

        gross, comm, slip, net = self.execution.calculate_net_pnl(
            pos.direction, pos.entry_price, exit_fill, pos.contracts,
        )

        self.position_mgr.record_trade_pnl(session_str, net)

        return Trade(
            strategy_name=pos.strategy_name,
            setup_type=pos.setup_type,
            day_type=pos.day_type,
            trend_strength=pos.trend_strength,
            session_date=session_str,
            entry_time=pos.entry_time,
            exit_time=timestamp,
            bars_held=pos.bars_held,
            direction=pos.direction,
            contracts=pos.contracts,
            signal_price=pos.entry_price,
            entry_price=pos.entry_price,
            exit_price=exit_fill,
            stop_price=pos.trailing_stop,
            target_price=pos.target_price,
            gross_pnl=gross,
            commission=comm,
            slippage_cost=slip,
            net_pnl=net,
            exit_reason=reason,
            mae_price=pos.mae_price,
            mfe_price=pos.mfe_price,
            mae_bar=pos.mae_bar,
            mfe_bar=pos.mfe_bar,
            metadata=pos.metadata,
        )

    def _execute_signal(
        self, signal: Signal, bar: pd.Series, timestamp, session_str: str,
    ) -> Optional[Trade]:
        """Execute a signal: create a position."""
        # Calculate contracts
        stop_distance = signal.risk_points
        if stop_distance <= 0:
            return None

        contracts = self.execution.calculate_contracts(self.risk_per_trade, stop_distance)
        contracts = min(contracts, self.max_contracts - self.position_mgr.get_open_contracts())
        if contracts <= 0:
            return None

        # Apply entry slippage
        entry_fill = self.execution.fill_entry(signal.direction, signal.entry_price)

        # Create open position
        pos = OpenPosition(
            direction=signal.direction,
            entry_price=entry_fill,
            stop_price=signal.stop_price,
            target_price=signal.target_price,
            contracts=contracts,
            entry_time=timestamp,
            strategy_name=signal.strategy_name,
            setup_type=signal.setup_type,
            day_type=signal.day_type,
            trend_strength=signal.trend_strength,
            session_date=session_str,
            pyramid_level=signal.pyramid_level,
            metadata=signal.metadata.copy(),
        )

        self.position_mgr.add_position(pos)
        return None  # Trade is not complete yet -- will be closed later

    def _print_summary(self, result: BacktestResult) -> None:
        """Print backtest summary."""
        trades = result.trades
        print(f"\n{'='*70}")
        print("BACKTEST RESULTS")
        print(f"{'='*70}")
        print(f"Sessions processed: {result.sessions_processed}")
        print(f"Signals generated:  {result.signals_generated}")
        print(f"Signals filtered:   {result.signals_filtered}")
        print(f"Trades executed:    {len(trades)}")

        if not trades:
            print("  No trades to report.")
            return

        wins = [t for t in trades if t.net_pnl > 0]
        losses = [t for t in trades if t.net_pnl <= 0]

        total_pnl = sum(t.net_pnl for t in trades)
        total_gross = sum(t.gross_pnl for t in trades)
        total_comm = sum(t.commission for t in trades)
        total_slip = sum(t.slippage_cost for t in trades)

        win_rate = len(wins) / len(trades) * 100 if trades else 0
        avg_win = np.mean([t.net_pnl for t in wins]) if wins else 0
        avg_loss = np.mean([t.net_pnl for t in losses]) if losses else 0

        gross_profit = sum(t.net_pnl for t in wins)
        gross_loss = abs(sum(t.net_pnl for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        expectancy = (win_rate / 100 * avg_win) - ((1 - win_rate / 100) * abs(avg_loss))

        print(f"\n--- Performance ---")
        print(f"Win Rate:       {win_rate:.1f}% ({len(wins)}W / {len(losses)}L)")
        print(f"Profit Factor:  {profit_factor:.2f}")
        print(f"Expectancy:     ${expectancy:,.2f} per trade")
        print(f"Avg Win:        ${avg_win:,.2f}")
        print(f"Avg Loss:       ${avg_loss:,.2f}")
        if avg_loss != 0:
            print(f"R:R Actual:     {abs(avg_win/avg_loss):.2f}")

        print(f"\n--- P&L ---")
        print(f"Gross P&L:      ${total_gross:,.2f}")
        print(f"Commissions:    ${total_comm:,.2f}")
        print(f"Slippage:       ${total_slip:,.2f}")
        print(f"Net P&L:        ${total_pnl:,.2f}")

        print(f"\n--- Equity ---")
        print(f"Starting:       ${self.position_mgr.account_size:,.2f}")
        print(f"Ending:         ${self.position_mgr.equity:,.2f}")
        print(f"Max Drawdown:   ${self.position_mgr.max_drawdown_seen:,.2f}")
        if result.equity_curve:
            print(f"Max DD %:       {result.equity_curve.max_drawdown_pct:.2f}%")

        # Per-strategy breakdown
        strat_trades: Dict[str, List[Trade]] = {}
        for t in trades:
            strat_trades.setdefault(t.strategy_name, []).append(t)

        if len(strat_trades) > 1:
            print(f"\n--- By Strategy ---")
            for sname, strades in sorted(strat_trades.items()):
                s_wins = sum(1 for t in strades if t.net_pnl > 0)
                s_wr = s_wins / len(strades) * 100 if strades else 0
                s_pnl = sum(t.net_pnl for t in strades)
                print(f"  {sname:25s}: {len(strades):3d} trades, {s_wr:5.1f}% WR, ${s_pnl:>10,.2f}")
