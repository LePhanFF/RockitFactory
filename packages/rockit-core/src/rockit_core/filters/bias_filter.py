"""
Bias alignment filter — blocks trades that oppose session bias.

Config-driven: no strategy names in code. Applies universally.
Neutral/flat bias can optionally pass through.
"""

import pandas as pd

from rockit_core.filters.base import FilterBase
from rockit_core.strategies.signal import Signal

# Bias values that indicate a direction
_LONG_BIASES = {"Bullish", "BULL", "Very Bullish"}
_SHORT_BIASES = {"Bearish", "BEAR", "Very Bearish"}


class BiasAlignmentFilter(FilterBase):
    """Block trades that oppose session bias.

    Args:
        neutral_passes: If True, trades with neutral/flat/unknown bias pass through.
    """

    def __init__(self, neutral_passes: bool = True):
        self._neutral_passes = neutral_passes

    @property
    def name(self) -> str:
        return "BiasAlignment"

    def should_trade(self, signal: Signal, bar: pd.Series, session_context: dict) -> bool:
        bias = session_context.get("session_bias", "NEUTRAL")

        # Neutral bias = no filter
        if not bias or bias in ("NEUTRAL", "Neutral", "Flat", ""):
            return self._neutral_passes

        # Check alignment
        direction = signal.direction
        if direction == "LONG" and bias in _SHORT_BIASES:
            return False  # LONG trade into bearish bias
        if direction == "SHORT" and bias in _LONG_BIASES:
            return False  # SHORT trade into bullish bias

        return True
