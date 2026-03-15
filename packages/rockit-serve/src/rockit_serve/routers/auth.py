"""Authentication endpoints: register, login, profile, strategy preferences, bot keys."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from rockit_serve.auth import create_access_token, hash_password, verify_password
from rockit_serve.database import get_db
from rockit_serve.dependencies import get_current_user
from rockit_serve.models import BotApiKey, User, UserStrategyPref
from rockit_serve.schemas import (
    BotKeyCreate,
    BotKeyResponse,
    StrategyPrefResponse,
    StrategyPrefUpdate,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# ─── All 12 strategies ──────────────────────────────────────────────────────

ALL_STRATEGIES = [
    "or_reversal", "or_acceptance", "80p_rule", "20p_ib_extension",
    "trend_bull", "trend_bear", "bday", "ib_edge_fade",
    "pdh_pdl_reaction", "va_edge_fade", "ndog_gap_fill", "nwog_gap_fill",
]


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check existing
    existing = await db.execute(select(User).where((User.username == body.username) | (User.email == body.email)))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already exists")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name or body.username,
    )
    db.add(user)
    await db.flush()

    # Seed default strategy prefs — all strategies visible, none mastered
    for sid in ALL_STRATEGIES:
        db.add(UserStrategyPref(user_id=user.id, strategy_id=sid, is_active=True, mastery_level="learning"))

    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.username)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    token = create_access_token(user.id, user.username)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def get_profile(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)


# ─── Strategy Preferences ────────────────────────────────────────────────────

@router.get("/strategies", response_model=list[StrategyPrefResponse])
async def get_strategy_prefs(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UserStrategyPref).where(UserStrategyPref.user_id == user.id).order_by(UserStrategyPref.strategy_id)
    )
    return [StrategyPrefResponse.model_validate(p) for p in result.scalars()]


@router.put("/strategies/{strategy_id}", response_model=StrategyPrefResponse)
async def update_strategy_pref(
    strategy_id: str,
    body: StrategyPrefUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserStrategyPref).where(
            UserStrategyPref.user_id == user.id,
            UserStrategyPref.strategy_id == strategy_id,
        )
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = UserStrategyPref(user_id=user.id, strategy_id=strategy_id)
        db.add(pref)

    pref.is_active = body.is_active
    pref.mastery_level = body.mastery_level
    pref.notes = body.notes
    await db.commit()
    await db.refresh(pref)
    return StrategyPrefResponse.model_validate(pref)


# ─── Bot API Keys ────────────────────────────────────────────────────────────

@router.get("/bot-keys", response_model=list[BotKeyResponse])
async def list_bot_keys(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BotApiKey).where(BotApiKey.user_id == user.id))
    return [BotKeyResponse.model_validate(k) for k in result.scalars()]


@router.post("/bot-keys", response_model=BotKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_bot_key(body: BotKeyCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    key = BotApiKey(user_id=user.id, name=body.name, instruments=body.instruments)
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return BotKeyResponse.model_validate(key)


@router.delete("/bot-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot_key(key_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(BotApiKey).where(BotApiKey.id == key_id, BotApiKey.user_id == user.id))
    await db.commit()
