"""Backtest engine: bar-by-bar simulation with execution cost modeling."""

from rockit_core.engine.backtest import BacktestEngine, BacktestResult
from rockit_core.engine.equity import EquityCurve, EquitySnapshot
from rockit_core.engine.execution import ExecutionModel
from rockit_core.engine.position import OpenPosition, PositionManager
from rockit_core.engine.trade import Trade

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "EquityCurve",
    "EquitySnapshot",
    "ExecutionModel",
    "OpenPosition",
    "PositionManager",
    "Trade",
]
