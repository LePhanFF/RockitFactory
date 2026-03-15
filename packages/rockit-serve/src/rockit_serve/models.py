"""SQLAlchemy ORM models for user data.

These models store per-user state: accounts, strategy preferences, trade logs,
journal entries, and bot API keys. Nothing here touches the research DuckDB.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rockit_serve.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(100), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # Relationships
    strategy_prefs: Mapped[list[UserStrategyPref]] = relationship(back_populates="user", cascade="all, delete-orphan")
    trades: Mapped[list[UserTrade]] = relationship(back_populates="user", cascade="all, delete-orphan")
    journal_entries: Mapped[list[UserJournal]] = relationship(back_populates="user", cascade="all, delete-orphan")
    bot_keys: Mapped[list[BotApiKey]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserStrategyPref(Base):
    """Per-user strategy preferences — which strategies this user has mastered/is trading."""

    __tablename__ = "user_strategy_prefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    strategy_id: Mapped[str] = mapped_column(String(50))  # e.g. "or_reversal"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    mastery_level: Mapped[str] = mapped_column(String(20), default="learning")  # learning | practicing | mastered
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    user: Mapped[User] = relationship(back_populates="strategy_prefs")


class UserTrade(Base):
    """Per-user trade log — separate from backtest results in DuckDB."""

    __tablename__ = "user_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    strategy_id: Mapped[str] = mapped_column(String(50))
    instrument: Mapped[str] = mapped_column(String(10), default="NQ")
    direction: Mapped[str] = mapped_column(String(5))  # LONG | SHORT
    entry_price: Mapped[float] = mapped_column(Float)
    stop_price: Mapped[float] = mapped_column(Float)
    target_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    result: Mapped[str] = mapped_column(String(10), default="OPEN")  # OPEN | WIN | LOSS | SCRATCH
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    r_multiple: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str] = mapped_column(Text, default="")
    entry_time: Mapped[str] = mapped_column(String(5), default="")  # HH:MM
    exit_time: Mapped[str] = mapped_column(String(5), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="trades")


class UserJournal(Base):
    """Per-user journal entries — premarket, intraday, postmarket notes."""

    __tablename__ = "user_journal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_date: Mapped[str] = mapped_column(String(10))
    entry_type: Mapped[str] = mapped_column(String(20))  # premarket | intraday | postmarket | review
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    user: Mapped[User] = relationship(back_populates="journal_entries")


class BotApiKey(Base):
    """API keys for bot/algo subscribers (NinjaTrader, etc)."""

    __tablename__ = "bot_api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    api_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=lambda: secrets.token_urlsafe(32))
    name: Mapped[str] = mapped_column(String(100))  # "My NinjaTrader bot"
    instruments: Mapped[str] = mapped_column(String(50), default="NQ")  # comma-separated
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="bot_keys")


class SignalLog(Base):
    """Audit log for all signals emitted — immutable, for compliance/review."""

    __tablename__ = "signal_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    instrument: Mapped[str] = mapped_column(String(10))
    strategy_id: Mapped[str] = mapped_column(String(50))
    direction: Mapped[str] = mapped_column(String(5))
    entry_price: Mapped[float] = mapped_column(Float)
    stop_price: Mapped[float] = mapped_column(Float)
    target_price: Mapped[float] = mapped_column(Float)
    state: Mapped[str] = mapped_column(String(20))  # WATCHING | ARMED | FIRED | DONE | BLOCKED
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
