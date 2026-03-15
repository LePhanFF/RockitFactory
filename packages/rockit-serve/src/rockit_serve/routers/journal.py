"""Per-user trade logging and journal endpoints.

Trade logs and journal entries are stored in the user SQLite database,
completely separate from the research DuckDB. This means:
- Users logging trades does NOT affect backtest data
- Each user sees only their own trades/journal
- The research DuckDB remains the single source of truth for strategy performance
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rockit_serve.database import get_db
from rockit_serve.dependencies import get_current_user
from rockit_serve.models import User, UserJournal, UserTrade
from rockit_serve.schemas import (
    JournalCreate,
    JournalResponse,
    JournalUpdate,
    TradeCreate,
    TradeResponse,
    TradeUpdate,
)

router = APIRouter(tags=["journal"])


# ─── Trades ──────────────────────────────────────────────────────────────────

@router.get("/api/v1/trades", response_model=list[TradeResponse])
async def list_trades(
    session_date: str | None = Query(default=None),
    strategy_id: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(UserTrade).where(UserTrade.user_id == user.id)
    if session_date:
        q = q.where(UserTrade.session_date == session_date)
    if strategy_id:
        q = q.where(UserTrade.strategy_id == strategy_id)
    q = q.order_by(UserTrade.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return [TradeResponse.model_validate(t) for t in result.scalars()]


@router.post("/api/v1/trades", response_model=TradeResponse, status_code=status.HTTP_201_CREATED)
async def create_trade(
    body: TradeCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trade = UserTrade(
        user_id=user.id,
        session_date=body.session_date,
        strategy_id=body.strategy_id,
        instrument=body.instrument,
        direction=body.direction,
        entry_price=body.entry_price,
        stop_price=body.stop_price,
        target_price=body.target_price,
        entry_time=body.entry_time,
        notes=body.notes,
    )
    db.add(trade)
    await db.commit()
    await db.refresh(trade)
    return TradeResponse.model_validate(trade)


@router.patch("/api/v1/trades/{trade_id}", response_model=TradeResponse)
async def update_trade(
    trade_id: int,
    body: TradeUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserTrade).where(UserTrade.id == trade_id, UserTrade.user_id == user.id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(trade, field, value)

    # Auto-calculate R multiple if we have exit + entry + stop
    if trade.exit_price and trade.entry_price and trade.stop_price:
        risk = abs(trade.entry_price - trade.stop_price)
        if risk > 0:
            reward = trade.exit_price - trade.entry_price if trade.direction == "LONG" else trade.entry_price - trade.exit_price
            trade.r_multiple = round(reward / risk, 2)
            trade.pnl = round(reward * 20, 2)  # NQ = $20/point

    await db.commit()
    await db.refresh(trade)
    return TradeResponse.model_validate(trade)


@router.delete("/api/v1/trades/{trade_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trade(
    trade_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserTrade).where(UserTrade.id == trade_id, UserTrade.user_id == user.id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    await db.delete(trade)
    await db.commit()


# ─── Journal ─────────────────────────────────────────────────────────────────

@router.get("/api/v1/journal", response_model=list[JournalResponse])
async def list_journal(
    session_date: str | None = Query(default=None),
    entry_type: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(UserJournal).where(UserJournal.user_id == user.id)
    if session_date:
        q = q.where(UserJournal.session_date == session_date)
    if entry_type:
        q = q.where(UserJournal.entry_type == entry_type)
    q = q.order_by(UserJournal.created_at.desc()).limit(limit)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        JournalResponse(
            id=j.id,
            session_date=j.session_date,
            entry_type=j.entry_type,
            content=j.content,
            created_at=j.created_at.isoformat() if j.created_at else "",
            updated_at=j.updated_at.isoformat() if j.updated_at else "",
        )
        for j in rows
    ]


@router.post("/api/v1/journal", response_model=JournalResponse, status_code=status.HTTP_201_CREATED)
async def create_journal_entry(
    body: JournalCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = UserJournal(
        user_id=user.id,
        session_date=body.session_date,
        entry_type=body.entry_type,
        content=body.content,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return JournalResponse(
        id=entry.id,
        session_date=entry.session_date,
        entry_type=entry.entry_type,
        content=entry.content,
        created_at=entry.created_at.isoformat() if entry.created_at else "",
        updated_at=entry.updated_at.isoformat() if entry.updated_at else "",
    )


@router.patch("/api/v1/journal/{entry_id}", response_model=JournalResponse)
async def update_journal_entry(
    entry_id: int,
    body: JournalUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserJournal).where(UserJournal.id == entry_id, UserJournal.user_id == user.id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    entry.content = body.content
    await db.commit()
    await db.refresh(entry)
    return JournalResponse(
        id=entry.id,
        session_date=entry.session_date,
        entry_type=entry.entry_type,
        content=entry.content,
        created_at=entry.created_at.isoformat() if entry.created_at else "",
        updated_at=entry.updated_at.isoformat() if entry.updated_at else "",
    )
