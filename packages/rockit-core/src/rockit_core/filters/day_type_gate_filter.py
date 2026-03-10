"""
Day type gate filter — blocks specific strategies on incompatible day types.

Config-driven: rules come from YAML, not code.
Adding a new gate = add a YAML rule, zero code changes.
"""

from typing import Dict, List, Set

import pandas as pd

from rockit_core.filters.base import FilterBase
from rockit_core.strategies.signal import Signal


class DayTypeGateFilter(FilterBase):
    """Block strategies on incompatible session day types.

    Args:
        rules: List of dicts with 'strategy' and 'blocked_day_types' keys.
    """

    def __init__(self, rules: List[Dict]):
        self._blocked: Dict[str, Set[str]] = {}
        for rule in rules:
            strategy = rule["strategy"]
            blocked = {dt.lower() for dt in rule.get("blocked_day_types", [])}
            self._blocked[strategy] = blocked

    @property
    def name(self) -> str:
        return "DayTypeGate"

    def should_trade(self, signal: Signal, bar: pd.Series, session_context: dict) -> bool:
        blocked_types = self._blocked.get(signal.strategy_name)
        if blocked_types is None:
            return True  # Strategy not in rules = pass through

        day_type = session_context.get("day_type", "").lower()
        return day_type not in blocked_types
