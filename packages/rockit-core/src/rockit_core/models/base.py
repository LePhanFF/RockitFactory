"""Abstract base classes for entry, stop, and target models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

    from rockit_core.models.signals import EntrySignal, StopLevel, TargetSpec


class EntryModel(ABC):
    """Base class for all entry models.

    Entry models evaluate market conditions and emit EntrySignal when
    conditions are met. They do NOT manage positions — they only signal.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this entry model."""

    @abstractmethod
    def evaluate(self, bar: pd.Series, session_context: dict) -> EntrySignal | None:
        """Evaluate current bar and session context for entry conditions.

        Args:
            bar: Current price bar with OHLCV + order flow data.
            session_context: Session-level context (day type, IB range, VA levels, etc.).

        Returns:
            EntrySignal if conditions met, None otherwise.
        """


class StopModel(ABC):
    """Base class for all stop-loss models.

    Stop models compute appropriate stop-loss levels given an entry signal
    and current market conditions.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this stop model."""

    @abstractmethod
    def compute(self, entry_signal: EntrySignal, bar: pd.Series, session_context: dict) -> StopLevel:
        """Compute stop-loss level for a given entry signal.

        Args:
            entry_signal: The entry signal to compute a stop for.
            bar: Current price bar.
            session_context: Session-level context.

        Returns:
            StopLevel with the computed stop price.
        """


class TargetModel(ABC):
    """Base class for all target/exit models.

    Target models compute profit targets and trailing stop rules
    given an entry signal and stop level.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this target model."""

    @abstractmethod
    def compute(
        self, entry_signal: EntrySignal, stop_level: StopLevel, bar: pd.Series, session_context: dict
    ) -> TargetSpec:
        """Compute target level for a given entry and stop.

        Args:
            entry_signal: The entry signal.
            stop_level: The computed stop-loss level.
            bar: Current price bar.
            session_context: Session-level context.

        Returns:
            TargetSpec with target price and optional trail rule.
        """
