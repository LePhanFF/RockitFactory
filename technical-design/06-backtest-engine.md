# Technical Design: Backtest Engine

> **Package:** `rockit-core/engine/`
> **Type:** MIGRATE from BookMapOrderFlowStudies/engine/
> **Source files:** 5 files, ~1,295 LOC
> **Tests:** See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#engine)

---

## Purpose

The backtest engine is the bar-by-bar orchestrator that replays historical market data through strategies, filters, and trade models. It builds `session_context` for each session, manages positions and risk, and produces a `BacktestResult` with all trades and equity curve. The same engine code runs for research backtesting and evaluation gate checks.

---

## Source Files (Being Migrated)

| File | Class | LOC | Destination | Type |
|------|-------|-----|-------------|------|
| `engine/backtest.py` | `BacktestEngine` | ~800 | `engine/backtest.py` | MIGRATE + EXTEND |
| `engine/execution.py` | `ExecutionModel` | ~120 | `engine/execution.py` | MIGRATE |
| `engine/position.py` | `PositionManager`, `OpenPosition` | ~220 | `engine/position.py` | MIGRATE |
| `engine/trade.py` | `Trade` | ~80 | `engine/trade.py` | MIGRATE |
| `engine/equity.py` | `EquityCurve` | ~75 | `engine/equity.py` | MIGRATE |

---

## Interface: BacktestEngine

```python
# packages/rockit-core/src/rockit_core/engine/backtest.py

from pathlib import Path
from typing import Any

import pandas as pd

from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal
from rockit_core.strategies.day_type import classify_day_type, classify_trend_strength
from rockit_core.strategies.day_confidence import DayTypeConfidenceScorer
from rockit_core.filters.base import FilterBase
from rockit_core.engine.execution import ExecutionModel
from rockit_core.engine.position import PositionManager
from rockit_core.engine.trade import Trade
from rockit_core.engine.equity import EquityCurve
from rockit_core.metrics import MetricsCollector, MetricEvent, NullCollector


class BacktestResult:
    """Complete backtest output.

    Attributes:
        trades: All completed Trade objects.
        equity_curve: EquityCurve with running P&L.
        sessions: Per-session summary dicts.
        metrics: MetricsCollector with all events (if provided).
    """
    def __init__(
        self,
        trades: list[Trade],
        equity_curve: EquityCurve,
        sessions: list[dict[str, Any]],
        metrics: MetricsCollector | None = None,
    ):
        self.trades = trades
        self.equity_curve = equity_curve
        self.sessions = sessions
        self.metrics = metrics

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        winners = sum(1 for t in self.trades if t.pnl > 0)
        return winners / len(self.trades)

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss


class BacktestEngine:
    """Bar-by-bar backtest orchestrator.

    Source: BookMapOrderFlowStudies/engine/backtest.py (~800 LOC)
    Migration: MIGRATE + add metrics, YAML config integration, trade models

    The engine processes data session by session:
    1. Identify session boundaries (RTH 09:30-16:00 ET)
    2. Accumulate IB bars (first 60 minutes, 09:30-10:30)
    3. Compute IB high, IB low, IB range
    4. Build initial session_context
    5. Call strategy.on_session_start() for each strategy
    6. For each post-IB bar:
       a. Update session_context (running high/low, indicators, day type confidence)
       b. Call strategy.on_bar() for each applicable strategy
       c. If signal returned: apply filters, apply trade models, execute
       d. Check open positions for stop/target/trail
       e. Update equity curve
    7. At session end: close any open positions, compute session summary
    """

    def __init__(
        self,
        strategies: list[StrategyBase],
        filters: list[FilterBase],
        execution_model: ExecutionModel,
        position_manager: PositionManager,
        metrics: MetricsCollector | None = None,
        strategy_configs: dict[str, dict] | None = None,
    ):
        """Initialize the backtest engine.

        Args:
            strategies: List of strategy instances to evaluate.
            filters: List of filter instances (applied as AND chain).
            execution_model: Slippage and commission model.
            position_manager: Position tracking and risk limits.
            metrics: Optional metrics collector.
            strategy_configs: Per-strategy config dicts from strategies.yaml.
                              Keys are strategy names, values are config dicts.
        """
        self._strategies = strategies
        self._filters = filters
        self._execution = execution_model
        self._positions = position_manager
        self._metrics = metrics or NullCollector()
        self._strategy_configs = strategy_configs or {}

    def run(self, data: pd.DataFrame) -> BacktestResult:
        """Run backtest over historical data.

        Args:
            data: DataFrame with columns:
                - timestamp (datetime)
                - open, high, low, close (float)
                - volume (int)
                - delta (float) — buy volume - sell volume
                - cvd (float) — cumulative volume delta
                - vol_ask, vol_bid (float) — ask/bid volume
                - Plus any indicator columns (vwap, ema20, etc.)

        Returns:
            BacktestResult with all trades, equity curve, and session summaries.
        """
        all_trades: list[Trade] = []
        equity = EquityCurve()
        sessions_summary: list[dict] = []

        # Group bars by session date
        sessions = self._group_by_session(data)

        for session_date, session_bars in sessions:
            session_trades = self._run_session(session_date, session_bars, equity)
            all_trades.extend(session_trades)

            sessions_summary.append({
                "date": session_date,
                "trades": len(session_trades),
                "pnl": sum(t.pnl for t in session_trades),
                "winners": sum(1 for t in session_trades if t.pnl > 0),
                "losers": sum(1 for t in session_trades if t.pnl <= 0),
            })

            self._metrics.record(MetricEvent(
                timestamp=session_date,
                layer="engine",
                component="backtest_engine",
                metric="session_complete",
                value=len(session_trades),
                context={"session_date": session_date},
            ))

        return BacktestResult(
            trades=all_trades,
            equity_curve=equity,
            sessions=sessions_summary,
            metrics=self._metrics if not isinstance(self._metrics, NullCollector) else None,
        )

    def _group_by_session(self, data: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
        """Group bars into trading sessions by date.

        Uses RTH boundaries (09:30-16:00 ET) to split data.

        Returns:
            List of (session_date_str, session_dataframe) tuples.
        """
        ...

    def _run_session(
        self,
        session_date: str,
        bars: pd.DataFrame,
        equity: EquityCurve,
    ) -> list[Trade]:
        """Process a single trading session.

        This is the core bar-by-bar loop.
        """
        # 1. Identify IB bars (first 60 minutes)
        ib_bars, post_ib_bars = self._split_ib(bars)
        if ib_bars.empty or post_ib_bars.empty:
            return []

        # 2. Compute IB levels
        ib_high = ib_bars["high"].max()
        ib_low = ib_bars["low"].min()
        ib_range = ib_high - ib_low

        # 3. Build initial session context
        context = self._build_session_context(session_date, ib_bars, ib_high, ib_low, ib_range)

        # 4. Initialize day type confidence scorer
        confidence_scorer = DayTypeConfidenceScorer()
        confidence_scorer.on_session_start(ib_high, ib_low, ib_range, context.get("atr14", 0.0))

        # 5. Call on_session_start for each strategy
        for strategy in self._strategies:
            strategy.on_session_start(session_date, ib_high, ib_low, ib_range, context)

        # 6. Reset position manager for new session
        self._positions.on_session_start(session_date)
        session_trades: list[Trade] = []

        # 7. Bar-by-bar loop
        for bar_index, (_, bar) in enumerate(post_ib_bars.iterrows()):
            # 7a. Update running context
            context = self._update_context(context, bar, bar_index, confidence_scorer)

            # 7b. Check open positions for stop/target/trail
            closed = self._positions.check_exits(bar, context)
            for trade in closed:
                trade = self._execution.apply_exit_costs(trade)
                session_trades.append(trade)
                equity.add_trade(trade)

                self._metrics.record(MetricEvent(
                    timestamp=bar["timestamp"].isoformat() if hasattr(bar["timestamp"], "isoformat") else str(bar["timestamp"]),
                    layer="engine",
                    component="backtest_engine",
                    metric="trade_closed",
                    value=trade.pnl,
                    context={"strategy": trade.strategy_name, "exit_reason": trade.exit_reason},
                ))

            # 7c. Evaluate strategies
            for strategy in self._strategies:
                signal = strategy.on_bar(bar, bar_index, context)
                if signal is None:
                    continue

                # 7d. Apply filters
                if not self._apply_filters(signal, bar, context):
                    continue

                # 7e. Apply trade models from config
                config = self._strategy_configs.get(strategy.name, {})
                signal = self._apply_trade_models(signal, context, config)

                # 7f. Execute trade
                if self._positions.can_open(signal, context):
                    filled_signal = self._execution.apply_entry_costs(signal)
                    self._positions.open_position(filled_signal, bar)

                    self._metrics.record(MetricEvent(
                        timestamp=bar["timestamp"].isoformat() if hasattr(bar["timestamp"], "isoformat") else str(bar["timestamp"]),
                        layer="engine",
                        component="backtest_engine",
                        metric="trade_opened",
                        value=1.0,
                        context={"strategy": strategy.name, "direction": signal.direction},
                    ))

        # 8. End of session: close any open positions at market
        remaining = self._positions.close_all(bars.iloc[-1])
        for trade in remaining:
            trade = self._execution.apply_exit_costs(trade)
            trade.exit_reason = "session_end"
            session_trades.append(trade)
            equity.add_trade(trade)

        # 9. Notify strategies
        for strategy in self._strategies:
            strategy.on_session_end(session_date)

        return session_trades

    def _build_session_context(
        self,
        session_date: str,
        ib_bars: pd.DataFrame,
        ib_high: float,
        ib_low: float,
        ib_range: float,
    ) -> dict[str, Any]:
        """Build the initial session context dict from IB data.

        Context includes:
        - ib_high, ib_low, ib_range
        - atr14, vwap, ema20, ema50, ema200, rsi14 (from last IB bar)
        - prior_day: dict with prev session high/low/close/VAH/VAL/POC
        - volume_profile: dict with current POC/VAH/VAL
        - session_high, session_low (initially = IB high/low)
        """
        ...

    def _update_context(
        self,
        context: dict,
        bar: pd.Series,
        bar_index: int,
        confidence_scorer: DayTypeConfidenceScorer,
    ) -> dict:
        """Update session context with new bar data.

        Updates: session_high, session_low, day_type_confidence,
        running indicators, volume profile.
        """
        context["session_high"] = max(context["session_high"], bar["high"])
        context["session_low"] = min(context["session_low"], bar["low"])
        context["day_type_confidence"] = confidence_scorer.update(bar, bar_index)
        context["current_bar"] = bar
        context["bar_index"] = bar_index
        return context

    def _apply_filters(self, signal: Signal, bar: pd.Series, context: dict) -> bool:
        """Apply all filters to a signal. Returns True if signal passes ALL filters."""
        for f in self._filters:
            if not f.should_trade(signal, bar, context):
                self._metrics.record(MetricEvent(
                    timestamp=bar["timestamp"].isoformat() if hasattr(bar["timestamp"], "isoformat") else str(bar["timestamp"]),
                    layer="filter",
                    component=f.name,
                    metric="filter_blocked",
                    value=1.0,
                    context={"strategy": signal.strategy_name},
                ))
                return False
            self._metrics.record(MetricEvent(
                timestamp=bar["timestamp"].isoformat() if hasattr(bar["timestamp"], "isoformat") else str(bar["timestamp"]),
                layer="filter",
                component=f.name,
                metric="filter_passed",
                value=1.0,
                context={"strategy": signal.strategy_name},
            ))
        return True

    def _apply_trade_models(self, signal: Signal, context: dict, config: dict) -> Signal:
        """Apply entry/stop/target models from YAML config to a signal.

        See 05-trade-models.md for apply_trade_models() implementation.
        If no models configured, signal retains strategy-set prices.
        """
        from rockit_core.models.registry import get_entry_model, get_stop_model, get_target_model
        # (delegates to apply_trade_models from 05-trade-models.md)
        ...
        return signal
```

---

## Interface: ExecutionModel

```python
# packages/rockit-core/src/rockit_core/engine/execution.py

from rockit_core.strategies.signal import Signal
from rockit_core.engine.trade import Trade


class ExecutionModel:
    """Simulates realistic execution costs.

    Source: BookMapOrderFlowStudies/engine/execution.py (~120 LOC)
    Migration: MIGRATE — add instrument config integration

    Default costs for NQ:
    - Slippage: 1 tick per side (0.25 pts = $5 per contract)
    - Commission: $2.05 per contract per side
    """

    def __init__(
        self,
        slippage_ticks: int = 1,
        tick_size: float = 0.25,
        tick_value: float = 5.0,
        commission_per_contract: float = 2.05,
        contracts: int = 1,
    ):
        self.slippage_ticks = slippage_ticks
        self.tick_size = tick_size
        self.tick_value = tick_value
        self.commission_per_contract = commission_per_contract
        self.contracts = contracts

    @property
    def slippage_points(self) -> float:
        return self.slippage_ticks * self.tick_size

    @property
    def slippage_cost(self) -> float:
        """Dollar cost of slippage per side per contract."""
        return self.slippage_ticks * self.tick_value

    @property
    def round_trip_cost(self) -> float:
        """Total round-trip cost per contract (slippage both sides + commission both sides)."""
        return (self.slippage_cost * 2) + (self.commission_per_contract * 2)

    def apply_entry_costs(self, signal: Signal) -> Signal:
        """Adjust entry price for slippage.

        LONG: entry_price += slippage
        SHORT: entry_price -= slippage
        """
        if signal.direction == "LONG":
            signal.entry_price += self.slippage_points
        else:
            signal.entry_price -= self.slippage_points
        return signal

    def apply_exit_costs(self, trade: Trade) -> Trade:
        """Apply slippage and commission to a completed trade.

        Adjusts exit_price for slippage and deducts commission.
        """
        if trade.direction == "LONG":
            trade.exit_price -= self.slippage_points
        else:
            trade.exit_price += self.slippage_points

        trade.commission = self.commission_per_contract * 2 * trade.contracts
        trade.slippage = self.slippage_cost * 2 * trade.contracts
        trade.pnl = trade.gross_pnl - trade.commission - trade.slippage
        return trade
```

---

## Interface: PositionManager

```python
# packages/rockit-core/src/rockit_core/engine/position.py

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from rockit_core.strategies.signal import Signal
from rockit_core.engine.trade import Trade


@dataclass
class OpenPosition:
    """An open position being tracked."""
    signal: Signal
    entry_bar: pd.Series
    entry_time: datetime
    contracts: int = 1
    current_stop: float = 0.0
    current_target: float = 0.0
    trail_rules: list[dict] = field(default_factory=list)
    highest_since_entry: float = 0.0
    lowest_since_entry: float = 0.0


class PositionManager:
    """Manages open positions, risk limits, and exits.

    Source: BookMapOrderFlowStudies/engine/position.py (~220 LOC)
    Migration: MIGRATE — add trail rule evaluation, instrument config

    Risk limits (from instrument config):
    - max_contracts: Maximum total open contracts
    - max_daily_loss: Maximum dollar loss per session before stopping
    - max_risk_per_trade: Maximum risk (entry to stop) per trade in dollars
    """

    def __init__(
        self,
        max_contracts: int = 30,
        max_daily_loss: float = 2000.0,
        max_risk_per_trade: float = 400.0,
        point_value: float = 20.0,
    ):
        self.max_contracts = max_contracts
        self.max_daily_loss = max_daily_loss
        self.max_risk_per_trade = max_risk_per_trade
        self.point_value = point_value
        self._positions: list[OpenPosition] = []
        self._daily_pnl: float = 0.0
        self._session_date: str = ""

    def on_session_start(self, session_date: str) -> None:
        """Reset daily state for new session."""
        self._positions = []
        self._daily_pnl = 0.0
        self._session_date = session_date

    def can_open(self, signal: Signal, context: dict) -> bool:
        """Check if a new position can be opened.

        Returns False if:
        - Total open contracts would exceed max_contracts
        - Daily loss limit has been hit
        - Risk per trade exceeds max_risk_per_trade
        """
        total_open = sum(p.contracts for p in self._positions)
        if total_open >= self.max_contracts:
            return False
        if self._daily_pnl <= -self.max_daily_loss:
            return False
        risk_dollars = signal.risk_points * self.point_value
        if risk_dollars > self.max_risk_per_trade:
            return False
        return True

    def open_position(self, signal: Signal, bar: pd.Series) -> None:
        """Open a new position from a filled signal."""
        position = OpenPosition(
            signal=signal,
            entry_bar=bar,
            entry_time=bar["timestamp"],
            current_stop=signal.stop_price,
            current_target=signal.target_price,
            trail_rules=signal.metadata.get("trail_rules", []),
            highest_since_entry=bar["high"],
            lowest_since_entry=bar["low"],
        )
        self._positions.append(position)

    def check_exits(self, bar: pd.Series, context: dict) -> list[Trade]:
        """Check all open positions for stop, target, or trail exits.

        For each open position:
        1. Update highest/lowest since entry
        2. Evaluate trail rules (move stop to BE, trail by ATR, etc.)
        3. Check if stop was hit (bar low <= stop for LONG)
        4. Check if target was hit (bar high >= target for LONG)

        Returns:
            List of Trade objects for positions that were closed.
        """
        closed: list[Trade] = []
        remaining: list[OpenPosition] = []

        for pos in self._positions:
            pos.highest_since_entry = max(pos.highest_since_entry, bar["high"])
            pos.lowest_since_entry = min(pos.lowest_since_entry, bar["low"])

            # Evaluate trail rules
            self._evaluate_trail_rules(pos, bar, context)

            trade = self._check_exit(pos, bar)
            if trade:
                self._daily_pnl += trade.pnl
                closed.append(trade)
            else:
                remaining.append(pos)

        self._positions = remaining
        return closed

    def _evaluate_trail_rules(
        self, pos: OpenPosition, bar: pd.Series, context: dict,
    ) -> None:
        """Evaluate and apply trail rules for a position.

        Trail rules are defined in the signal metadata (from target models).
        Example: move stop to breakeven after 5m FVG forms.
        """
        ...

    def _check_exit(self, pos: OpenPosition, bar: pd.Series) -> Trade | None:
        """Check if position should be closed on this bar.

        Exit priority: stop loss > target > trail.
        """
        signal = pos.signal

        if signal.direction == "LONG":
            if bar["low"] <= pos.current_stop:
                return self._create_trade(pos, pos.current_stop, "stop_loss")
            if bar["high"] >= pos.current_target:
                return self._create_trade(pos, pos.current_target, "target_hit")
        else:
            if bar["high"] >= pos.current_stop:
                return self._create_trade(pos, pos.current_stop, "stop_loss")
            if bar["low"] <= pos.current_target:
                return self._create_trade(pos, pos.current_target, "target_hit")

        return None

    def _create_trade(
        self, pos: OpenPosition, exit_price: float, exit_reason: str,
    ) -> Trade:
        """Create a Trade from a closed position."""
        ...

    def close_all(self, last_bar: pd.Series) -> list[Trade]:
        """Close all open positions at last bar's close price."""
        trades = []
        for pos in self._positions:
            trade = self._create_trade(pos, last_bar["close"], "session_end")
            trades.append(trade)
        self._positions = []
        return trades
```

---

## Interface: Trade

```python
# packages/rockit-core/src/rockit_core/engine/trade.py

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Trade:
    """A completed trade record.

    Source: BookMapOrderFlowStudies/engine/trade.py (~80 LOC)
    Migration: MIGRATE — add entry_model/stop_model/target_model fields
    """
    # Identity
    strategy_name: str
    setup_type: str
    day_type: str

    # Direction
    direction: str                  # "LONG" or "SHORT"

    # Prices
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float

    # Timing
    entry_time: datetime
    exit_time: datetime
    session_date: str

    # Size
    contracts: int = 1

    # P&L (set by ExecutionModel)
    pnl: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0

    # Exit info
    exit_reason: str = ""           # "stop_loss" | "target_hit" | "session_end" | "trail"

    # Trade model references
    entry_model: str = ""
    stop_model: str = ""
    target_model: str = ""

    # Metadata
    confidence: str = "medium"
    metadata: dict = field(default_factory=dict)

    @property
    def gross_pnl(self) -> float:
        """P&L before costs."""
        if self.direction == "LONG":
            return (self.exit_price - self.entry_price) * self.contracts * 20.0  # point_value
        return (self.entry_price - self.exit_price) * self.contracts * 20.0

    @property
    def is_winner(self) -> bool:
        return self.pnl > 0

    @property
    def r_multiple(self) -> float:
        """Actual R-multiple achieved. risk = entry to stop distance."""
        risk = abs(self.entry_price - self.stop_price)
        if risk == 0:
            return 0.0
        actual = abs(self.exit_price - self.entry_price)
        return actual / risk if self.is_winner else -(actual / risk)
```

---

## Interface: EquityCurve

```python
# packages/rockit-core/src/rockit_core/engine/equity.py

from rockit_core.engine.trade import Trade


class EquityCurve:
    """Running equity curve tracker.

    Source: BookMapOrderFlowStudies/engine/equity.py (~75 LOC)
    Migration: MIGRATE as-is
    """

    def __init__(self, starting_equity: float = 0.0):
        self._equity: list[float] = [starting_equity]
        self._peak: float = starting_equity

    def add_trade(self, trade: Trade) -> None:
        """Add trade P&L to equity curve."""
        new_equity = self._equity[-1] + trade.pnl
        self._equity.append(new_equity)
        self._peak = max(self._peak, new_equity)

    @property
    def current(self) -> float:
        return self._equity[-1]

    @property
    def peak(self) -> float:
        return self._peak

    @property
    def drawdown(self) -> float:
        """Current drawdown from peak in dollars."""
        return self._peak - self._equity[-1]

    @property
    def max_drawdown(self) -> float:
        """Maximum drawdown observed during the backtest."""
        peak = self._equity[0]
        max_dd = 0.0
        for eq in self._equity:
            peak = max(peak, eq)
            dd = peak - eq
            max_dd = max(max_dd, dd)
        return max_dd

    @property
    def values(self) -> list[float]:
        """Full equity curve as list."""
        return list(self._equity)
```

---

## Data Flow

```
CSV Data (pd.DataFrame)
    │
    ▼
BacktestEngine.run(data)
    │
    ├──► _group_by_session(data)
    │       └──► [(session_date, session_bars), ...]
    │
    └──► For each session:
            │
            ├──► _split_ib(bars) ──► ib_bars, post_ib_bars
            │
            ├──► _build_session_context() ──► session_context dict
            │       ├── ib_high, ib_low, ib_range
            │       ├── indicators (VWAP, EMA, ATR, RSI)
            │       ├── volume_profile (POC, VAH, VAL)
            │       └── prior_day data
            │
            ├──► DayTypeConfidenceScorer.on_session_start()
            │
            ├──► For each strategy: on_session_start()
            │
            └──► For each post-IB bar:
                    │
                    ├──► _update_context() ──► updated session_context
                    │       └── DayTypeConfidenceScorer.update()
                    │
                    ├──► PositionManager.check_exits(bar) ──► [Trade, ...]
                    │
                    └──► For each strategy:
                            │
                            ├──► strategy.on_bar(bar, ctx) ──► Signal | None
                            │
                            ├──► _apply_filters(signal) ──► bool
                            │       └── FilterBase.should_trade() for each filter
                            │
                            ├──► _apply_trade_models(signal) ──► Signal (adjusted)
                            │       └── EntryModel, StopModel, TargetModel
                            │
                            └──► PositionManager.can_open() + open_position()
                                    └── ExecutionModel.apply_entry_costs()
```

---

## Dependencies

| This module | Depends on |
|-------------|-----------|
| `engine/backtest.py` | `strategies/*`, `filters/*`, `engine/execution.py`, `engine/position.py`, `engine/trade.py`, `engine/equity.py`, `models/registry.py`, `metrics/` |
| `engine/execution.py` | `strategies/signal.py`, `engine/trade.py` |
| `engine/position.py` | `strategies/signal.py`, `engine/trade.py` |
| `engine/trade.py` | None (stdlib only) |
| `engine/equity.py` | `engine/trade.py` |

---

## Metrics Emitted

| Metric | Layer | When |
|--------|-------|------|
| `engine.session_complete` | engine | Session processing finished |
| `engine.trade_opened` | engine | New position opened |
| `engine.trade_closed` | engine | Position closed (stop/target/trail/session_end) |
| `engine.daily_loss_limit` | engine | Daily loss limit hit, no more trades |
| `engine.position_limit` | engine | Max contracts reached |
| `filter.filter_passed` | filter | Signal passes a filter |
| `filter.filter_blocked` | filter | Signal blocked by a filter |

---

## Migration Notes

1. **No core logic changes.** The bar-by-bar loop, IB computation, session context building, and position management are migrated as-is from BookMapOrderFlowStudies.

2. **New: metrics injection.** The engine accepts a `MetricsCollector` and emits events at key points. This is additive, not a change to existing logic.

3. **New: trade model integration.** After a signal passes filters, the engine applies entry/stop/target models from YAML config (see `_apply_trade_models`). If no models are configured, the signal retains strategy-set prices.

4. **New: `strategy_configs` parameter.** The engine reads per-strategy config dicts from `strategies.yaml` to determine which trade models and filter overrides to apply.

5. **`point_value` in Trade.gross_pnl is hardcoded to 20.0 (NQ).** This must be parameterized from instrument config during migration. The `ExecutionModel` should pass the correct `point_value` when creating trades.

---

## Test Contract

1. **Known-output backtest** — run engine on a fixed 5-session dataset with known signals, verify exact trade count, P&L, and equity curve
2. **IB computation** — verify IB high/low/range from known bar data
3. **Session context** — verify all context fields are populated correctly
4. **Filter integration** — verify signals are blocked when filters reject
5. **Position risk limits** — verify daily loss limit stops trading
6. **Execution costs** — verify slippage and commission are applied correctly
7. **Trail rules** — verify stop moves to breakeven when trail condition met
8. **Session end close** — verify open positions close at session end
9. **Empty session** — verify engine handles sessions with no post-IB bars gracefully

See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#engine)
