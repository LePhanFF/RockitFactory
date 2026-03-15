"""Pluggable execution framework: strategy adapter, combo runner, reporting."""

from rockit_core.execution.combo_report import combo_report
from rockit_core.execution.combo_runner import ComboRunner
from rockit_core.execution.strategy_adapter import StrategyAdapter

__all__ = [
    "ComboRunner",
    "StrategyAdapter",
    "combo_report",
]
