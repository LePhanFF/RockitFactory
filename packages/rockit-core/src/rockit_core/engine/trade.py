"""
Unified Trade dataclass.
Replaces the separate Trade definitions scattered across the codebase.
All P&L fields are in DOLLARS (not points).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Trade:
    """A completed trade with full cost accounting."""

    # Identification
    strategy_name: str = ""
    setup_type: str = ""
    day_type: str = ""
    trend_strength: str = ""
    session_date: str = ""

    # Timing
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    bars_held: int = 0

    # Direction and size
    direction: str = ""         # 'LONG' or 'SHORT'
    contracts: int = 0

    # Prices
    signal_price: float = 0.0   # Price at signal generation
    entry_price: float = 0.0    # Actual fill price after slippage
    exit_price: float = 0.0     # Actual exit fill price after slippage
    stop_price: float = 0.0
    target_price: float = 0.0

    # P&L (all in dollars)
    gross_pnl: float = 0.0      # Before costs
    commission: float = 0.0     # Round-trip commission
    slippage_cost: float = 0.0  # Round-trip slippage cost
    net_pnl: float = 0.0       # gross_pnl - commission - slippage_cost

    # Exit
    exit_reason: str = ""       # 'STOP', 'TARGET', 'TIME', 'EOD', 'DAILY_LOSS', 'VWAP_BREACH_PM'

    # MAE/MFE (Maximum Adverse/Favorable Excursion)
    mae_price: float = 0.0     # Worst price during trade (LONG: lowest low, SHORT: highest high)
    mfe_price: float = 0.0     # Best price during trade (LONG: highest high, SHORT: lowest low)
    mae_bar: int = 0           # Bar number when MAE occurred
    mfe_bar: int = 0           # Bar number when MFE occurred

    # Metadata
    metadata: dict = field(default_factory=dict)

    @property
    def is_winner(self) -> bool:
        return self.net_pnl > 0

    @property
    def risk_points(self) -> float:
        """Distance from entry to stop in points."""
        if self.direction == 'LONG':
            return abs(self.entry_price - self.stop_price)
        else:
            return abs(self.stop_price - self.entry_price)

    @property
    def reward_points(self) -> float:
        """Distance from entry to target in points."""
        if self.direction == 'LONG':
            return abs(self.target_price - self.entry_price)
        else:
            return abs(self.entry_price - self.target_price)

    @property
    def r_multiple(self) -> float:
        """Actual R-multiple achieved (net P&L / risk)."""
        risk = self.risk_points
        if risk == 0:
            return 0.0
        if self.direction == 'LONG':
            actual_points = self.exit_price - self.entry_price
        else:
            actual_points = self.entry_price - self.exit_price
        return actual_points / risk

    @property
    def mae_points(self) -> float:
        """MAE distance from entry in points (always positive)."""
        if self.direction == 'LONG':
            return max(0.0, self.entry_price - self.mae_price)
        else:
            return max(0.0, self.mae_price - self.entry_price)

    @property
    def mfe_points(self) -> float:
        """MFE distance from entry in points (always positive)."""
        if self.direction == 'LONG':
            return max(0.0, self.mfe_price - self.entry_price)
        else:
            return max(0.0, self.entry_price - self.mfe_price)

    @property
    def mae_pct_of_stop(self) -> float:
        """MAE as percentage of stop distance. 0.8 = touched 80% of stop."""
        risk = self.risk_points
        return self.mae_points / risk if risk > 0 else 0.0

    @property
    def mfe_pct_of_target(self) -> float:
        """MFE as percentage of target distance. 1.2 = went 20% past target."""
        reward = self.reward_points
        return self.mfe_points / reward if reward > 0 else 0.0

    @property
    def entry_efficiency(self) -> float:
        """Entry quality: (MFE - MAE) / (MFE + MAE). 1.0 = perfect, 0.0 = terrible."""
        total = self.mfe_points + self.mae_points
        if total == 0:
            return 0.0
        return (self.mfe_points - self.mae_points) / total

    @property
    def heat(self) -> float:
        """Heat: MAE / risk. >1.0 = price went past stop level without fill."""
        risk = self.risk_points
        return self.mae_points / risk if risk > 0 else 0.0

    @property
    def entry_hour(self) -> Optional[int]:
        """Hour of entry for time-of-day analysis."""
        if self.entry_time is not None and hasattr(self.entry_time, 'hour'):
            return self.entry_time.hour
        return None
