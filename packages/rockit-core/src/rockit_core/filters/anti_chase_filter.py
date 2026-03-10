"""
Anti-chase filter — blocks contrarian strategies from chasing momentum.

Config-driven: rules specify which bias values block which directions
for each strategy. Generic — works for any contrarian strategy.
"""

from typing import Dict, List, Set

import pandas as pd

from rockit_core.filters.base import FilterBase
from rockit_core.strategies.signal import Signal


class AntiChaseFilter(FilterBase):
    """Block contrarian strategies from chasing aligned momentum.

    Example: 80P LONG blocked when tape bias is Bullish (chasing overbought).

    Args:
        rules: List of dicts with 'strategy', 'block_long_when_bias', 'block_short_when_bias'.
    """

    def __init__(self, rules: List[Dict]):
        self._long_blocks: Dict[str, Set[str]] = {}
        self._short_blocks: Dict[str, Set[str]] = {}
        for rule in rules:
            strategy = rule["strategy"]
            if "block_long_when_bias" in rule:
                self._long_blocks[strategy] = set(rule["block_long_when_bias"])
            if "block_short_when_bias" in rule:
                self._short_blocks[strategy] = set(rule["block_short_when_bias"])

    @property
    def name(self) -> str:
        return "AntiChase"

    def should_trade(self, signal: Signal, bar: pd.Series, session_context: dict) -> bool:
        bias = session_context.get("session_bias", "NEUTRAL")

        if signal.direction == "LONG":
            blocked_biases = self._long_blocks.get(signal.strategy_name)
            if blocked_biases and bias in blocked_biases:
                return False

        elif signal.direction == "SHORT":
            blocked_biases = self._short_blocks.get(signal.strategy_name)
            if blocked_biases and bias in blocked_biases:
                return False

        return True
