"""ComboRunner: two-pass combinatorial backtester.

Pass 1: Run original backtest with StrategyAdapter → collect detections.
Pass 2: For each (stop_model, target_model) combo, replay detections
         with recomputed signals through a fresh engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

from rockit_core.config.instruments import InstrumentSpec
from rockit_core.engine.backtest import BacktestEngine, BacktestResult
from rockit_core.engine.execution import ExecutionModel
from rockit_core.engine.position import PositionManager
from rockit_core.execution.strategy_adapter import StrategyAdapter
from rockit_core.models.base import StopModel, TargetModel
from rockit_core.models.bridge import recompute_signal
from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal


@dataclass
class ComboResult:
    """Result of a single strategy × stop × target combination."""
    strategy_name: str
    stop_model_name: str
    target_model_name: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    net_pnl: float = 0.0
    avg_r: float = 0.0
    backtest_result: Optional[BacktestResult] = field(default=None, repr=False)


class _ReplayStrategy(StrategyBase):
    """Internal strategy that replays pre-computed signals at specific bars."""

    def __init__(
        self,
        name: str,
        signals_by_session_bar: Dict[Tuple[str, int], Signal],
    ):
        self._name = name
        self._signals = signals_by_session_bar
        self._session_date = None
        self._applicable_day_types: list = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def applicable_day_types(self) -> list:
        return self._applicable_day_types

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._session_date = str(session_date)

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        key = (self._session_date, bar_index)
        return self._signals.get(key)

    def on_session_end(self, session_date):
        pass


class ComboRunner:
    """Two-pass combinatorial backtester."""

    def __init__(
        self,
        instrument: InstrumentSpec,
        strategy: StrategyBase,
        stop_models: List[StopModel],
        target_models: List[TargetModel],
        risk_per_trade: float = 500.0,
        max_contracts: int = 3,
    ):
        self.instrument = instrument
        self.strategy = strategy
        self.stop_models = stop_models
        self.target_models = target_models
        self.risk_per_trade = risk_per_trade
        self.max_contracts = max_contracts

    def run(
        self,
        df: pd.DataFrame,
        include_original: bool = True,
        verbose: bool = False,
    ) -> List[ComboResult]:
        """Run two-pass combo backtest.

        Args:
            df: Market data DataFrame.
            include_original: If True, include "original" combo (no recomputation).
            verbose: Print progress.

        Returns:
            List of ComboResult, one per combo.
        """
        # --- Pass 1: Run original backtest with adapter ---
        adapter = StrategyAdapter(self.strategy)
        pass1_engine = BacktestEngine(
            instrument=self.instrument,
            strategies=[adapter],
            execution=ExecutionModel(self.instrument),
            position_mgr=PositionManager(),
            risk_per_trade=self.risk_per_trade,
            max_contracts=self.max_contracts,
        )
        pass1_result = pass1_engine.run(df, verbose=verbose)

        results: List[ComboResult] = []

        # Include original combo (unmodified signals)
        if include_original:
            results.append(self._build_combo_result(
                strategy_name=self.strategy.name,
                stop_name="original",
                target_name="original",
                backtest_result=pass1_result,
            ))

        if verbose:
            print(f"Pass 1 complete: {len(adapter.detections)} detections captured")

        if not adapter.detections:
            return results

        # Build detection index: map (session_date, bar_index) → detection
        # We need bar_index from the detection context. Since detections are
        # captured during on_bar() which receives bar_index, we need to
        # reconstruct which bar index each detection corresponds to.
        # The session_context has 'session_date' and bar has 'timestamp'.
        detections_indexed = self._index_detections(adapter.detections, df)

        # --- Pass 2: For each combo, replay with recomputed signals ---
        for stop_model in self.stop_models:
            for target_model in self.target_models:
                combo_result = self._run_combo(
                    df=df,
                    detections_indexed=detections_indexed,
                    stop_model=stop_model,
                    target_model=target_model,
                    verbose=verbose,
                )
                results.append(combo_result)

        return results

    def _index_detections(
        self,
        detections: list,
        df: pd.DataFrame,
    ) -> Dict[Tuple[str, int], Tuple[Signal, pd.Series, dict]]:
        """Index detections by (session_date, bar_index) for replay lookup."""
        indexed = {}
        for signal, bar, ctx in detections:
            session_date = ctx.get('session_date', '')
            # Find bar_index: match by timestamp in post-IB data
            # Use a simplified approach: store the bar's timestamp and match later
            bar_ts = bar.get('timestamp')
            if bar_ts is not None:
                indexed[(session_date, bar_ts)] = (signal, bar, ctx)
            else:
                # Fallback: use signal timestamp
                indexed[(session_date, signal.timestamp)] = (signal, bar, ctx)
        return indexed

    def _run_combo(
        self,
        df: pd.DataFrame,
        detections_indexed: dict,
        stop_model: StopModel,
        target_model: TargetModel,
        verbose: bool = False,
    ) -> ComboResult:
        """Run a single combo by replaying detections with recomputed signals."""
        # Recompute all signals with this stop/target combo
        recomputed_by_session_bar: Dict[Tuple[str, int], Signal] = {}

        for key, (signal, bar, ctx) in detections_indexed.items():
            new_signal = recompute_signal(signal, stop_model, target_model, bar, ctx)
            # We need to store by (session_date, bar_index) for the replay strategy.
            # Since we don't have bar_index directly, we use a replay approach that
            # matches by timestamp.
            recomputed_by_session_bar[key] = new_signal

        # Build a replay strategy that emits recomputed signals at the right bars
        replay = _TimestampReplayStrategy(
            name=self.strategy.name,
            signals_by_session_ts=recomputed_by_session_bar,
        )

        engine = BacktestEngine(
            instrument=self.instrument,
            strategies=[replay],
            execution=ExecutionModel(self.instrument),
            position_mgr=PositionManager(),
            risk_per_trade=self.risk_per_trade,
            max_contracts=self.max_contracts,
        )
        result = engine.run(df, verbose=False)

        combo_result = self._build_combo_result(
            strategy_name=self.strategy.name,
            stop_name=stop_model.name,
            target_name=target_model.name,
            backtest_result=result,
        )

        if verbose:
            print(
                f"  {stop_model.name} × {target_model.name}: "
                f"{combo_result.trades} trades, {combo_result.win_rate:.1f}% WR, "
                f"PF {combo_result.profit_factor:.2f}, ${combo_result.net_pnl:,.0f}"
            )

        return combo_result

    @staticmethod
    def _build_combo_result(
        strategy_name: str,
        stop_name: str,
        target_name: str,
        backtest_result: BacktestResult,
    ) -> ComboResult:
        """Build a ComboResult from a BacktestResult."""
        trades = backtest_result.trades
        wins = [t for t in trades if t.net_pnl > 0]
        losses = [t for t in trades if t.net_pnl <= 0]
        win_rate = len(wins) / len(trades) * 100 if trades else 0.0

        gross_win = sum(t.net_pnl for t in wins)
        gross_loss = abs(sum(t.net_pnl for t in losses))
        pf = gross_win / gross_loss if gross_loss > 0 else float('inf') if gross_win > 0 else 0.0

        net_pnl = sum(t.net_pnl for t in trades)

        avg_r = 0.0
        r_values = [t.r_multiple for t in trades if t.risk_points > 0]
        if r_values:
            avg_r = sum(r_values) / len(r_values)

        return ComboResult(
            strategy_name=strategy_name,
            stop_model_name=stop_name,
            target_model_name=target_name,
            trades=len(trades),
            wins=len(wins),
            losses=len(losses),
            win_rate=win_rate,
            profit_factor=pf,
            net_pnl=net_pnl,
            avg_r=avg_r,
            backtest_result=backtest_result,
        )


class _TimestampReplayStrategy(StrategyBase):
    """Replay strategy that matches detections by timestamp."""

    def __init__(
        self,
        name: str,
        signals_by_session_ts: Dict[Tuple[str, object], Signal],
    ):
        self._name = name
        self._signals = signals_by_session_ts
        self._session_date = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def applicable_day_types(self) -> list:
        return []

    def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
        self._session_date = str(session_date)

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:
        bar_ts = bar.get('timestamp')
        if bar_ts is not None:
            key = (self._session_date, bar_ts)
            return self._signals.get(key)
        return None

    def on_session_end(self, session_date):
        pass
