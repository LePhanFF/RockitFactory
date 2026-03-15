"""Integration tests for the Rockit API.

Tests auth flow, trade logging, journal, strategy preferences, and bot API.
Uses an in-memory SQLite database (no file I/O).
"""

from __future__ import annotations

import os

# Force test config before any imports
os.environ["ROCKIT_USER_DB_URL"] = "sqlite+aiosqlite://"
os.environ["ROCKIT_DEMO_MODE"] = "false"
os.environ["ROCKIT_SECRET_KEY"] = "test-secret-key-for-testing-only"

import pytest
from httpx import ASGITransport, AsyncClient

from rockit_serve.app import app
from rockit_serve.database import Base, engine, init_db


@pytest.fixture(autouse=True)
async def setup_db():
    """Initialize fresh database for each test — drop all tables first."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await init_db()
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_client(client: AsyncClient):
    """Client with a registered + authenticated user."""
    resp = await client.post("/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123",
        "display_name": "Test Trader",
    })
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


# ─── Auth Tests ──────────────────────────────────────────────────────────────

class TestAuth:
    async def test_register(self, client: AsyncClient):
        resp = await client.post("/auth/register", json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "password123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["username"] == "newuser"

    async def test_register_duplicate(self, client: AsyncClient):
        body = {"username": "dup", "email": "dup@example.com", "password": "password123"}
        await client.post("/auth/register", json=body)
        resp = await client.post("/auth/register", json=body)
        assert resp.status_code == 409

    async def test_login(self, client: AsyncClient):
        await client.post("/auth/register", json={
            "username": "loginuser",
            "email": "login@example.com",
            "password": "password123",
        })
        resp = await client.post("/auth/login", json={
            "username": "loginuser",
            "password": "password123",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_login_wrong_password(self, client: AsyncClient):
        await client.post("/auth/register", json={
            "username": "wrongpw",
            "email": "wrong@example.com",
            "password": "password123",
        })
        resp = await client.post("/auth/login", json={
            "username": "wrongpw",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    async def test_get_profile(self, auth_client: AsyncClient):
        resp = await auth_client.get("/auth/me")
        assert resp.status_code == 200
        assert resp.json()["username"] == "testuser"

    async def test_unauthorized(self, client: AsyncClient):
        resp = await client.get("/auth/me")
        assert resp.status_code == 422  # Missing header


# ─── Strategy Preferences ────────────────────────────────────────────────────

class TestStrategyPrefs:
    async def test_default_prefs(self, auth_client: AsyncClient):
        resp = await auth_client.get("/auth/strategies")
        assert resp.status_code == 200
        prefs = resp.json()
        assert len(prefs) == 12  # All 12 strategies
        assert all(p["mastery_level"] == "learning" for p in prefs)

    async def test_update_pref(self, auth_client: AsyncClient):
        resp = await auth_client.put("/auth/strategies/or_reversal", json={
            "strategy_id": "or_reversal",
            "is_active": True,
            "mastery_level": "mastered",
            "notes": "My bread and butter strategy",
        })
        assert resp.status_code == 200
        assert resp.json()["mastery_level"] == "mastered"

    async def test_focus_on_two_strategies(self, auth_client: AsyncClient):
        """User masters 2 strategies, deactivates the rest."""
        # Activate only OR Rev and 80P
        for sid in ["or_reversal", "80p_rule"]:
            await auth_client.put(f"/auth/strategies/{sid}", json={
                "strategy_id": sid, "is_active": True, "mastery_level": "mastered",
            })
        # Deactivate others
        for sid in ["or_acceptance", "trend_bull", "trend_bear", "bday",
                     "ib_edge_fade", "pdh_pdl_reaction", "va_edge_fade",
                     "20p_ib_extension", "ndog_gap_fill", "nwog_gap_fill"]:
            await auth_client.put(f"/auth/strategies/{sid}", json={
                "strategy_id": sid, "is_active": False, "mastery_level": "learning",
            })

        resp = await auth_client.get("/auth/strategies")
        active = [p for p in resp.json() if p["is_active"]]
        assert len(active) == 2


# ─── Trade Logging ───────────────────────────────────────────────────────────

class TestTrades:
    async def test_create_trade(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/trades", json={
            "session_date": "2026-03-14",
            "strategy_id": "or_reversal",
            "direction": "LONG",
            "entry_price": 21520.0,
            "stop_price": 21490.0,
            "target_price": 21580.0,
            "entry_time": "10:30",
            "notes": "Clean Judas sweep setup",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["strategy_id"] == "or_reversal"
        assert data["result"] == "OPEN"

    async def test_update_trade_with_exit(self, auth_client: AsyncClient):
        # Create
        create = await auth_client.post("/api/v1/trades", json={
            "session_date": "2026-03-14",
            "strategy_id": "or_reversal",
            "direction": "LONG",
            "entry_price": 21520.0,
            "stop_price": 21490.0,
            "target_price": 21580.0,
        })
        trade_id = create.json()["id"]

        # Close with win
        resp = await auth_client.patch(f"/api/v1/trades/{trade_id}", json={
            "exit_price": 21575.0,
            "result": "WIN",
            "exit_time": "11:15",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "WIN"
        assert data["pnl"] > 0
        assert data["r_multiple"] > 0

    async def test_list_trades_by_date(self, auth_client: AsyncClient):
        for i in range(3):
            await auth_client.post("/api/v1/trades", json={
                "session_date": "2026-03-14",
                "strategy_id": "or_reversal",
                "direction": "LONG",
                "entry_price": 21520.0 + i,
                "stop_price": 21490.0,
                "target_price": 21580.0,
            })
        resp = await auth_client.get("/api/v1/trades?session_date=2026-03-14")
        assert len(resp.json()) == 3


# ─── Journal ─────────────────────────────────────────────────────────────────

class TestJournal:
    async def test_create_journal_entry(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/journal", json={
            "session_date": "2026-03-14",
            "entry_type": "premarket",
            "content": "Gap up 40pts into PDH. Expecting OR Rev setup if sweep occurs.",
        })
        assert resp.status_code == 201
        assert resp.json()["entry_type"] == "premarket"

    async def test_update_journal_entry(self, auth_client: AsyncClient):
        create = await auth_client.post("/api/v1/journal", json={
            "session_date": "2026-03-14",
            "entry_type": "postmarket",
            "content": "Good session",
        })
        entry_id = create.json()["id"]

        resp = await auth_client.patch(f"/api/v1/journal/{entry_id}", json={
            "content": "Good session — 2W 0L. OR Rev was textbook. Should have held longer.",
        })
        assert resp.status_code == 200
        assert "textbook" in resp.json()["content"]


# ─── Bot API Keys ────────────────────────────────────────────────────────────

class TestBotKeys:
    async def test_create_bot_key(self, auth_client: AsyncClient):
        resp = await auth_client.post("/auth/bot-keys", json={
            "name": "My NinjaTrader Bot",
            "instruments": "NQ,ES",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["api_key"]) > 20
        assert data["instruments"] == "NQ,ES"

    async def test_list_and_delete_bot_key(self, auth_client: AsyncClient):
        create = await auth_client.post("/auth/bot-keys", json={"name": "Test Bot"})
        key_id = create.json()["id"]

        # List
        resp = await auth_client.get("/auth/bot-keys")
        assert len(resp.json()) == 1

        # Delete
        resp = await auth_client.delete(f"/auth/bot-keys/{key_id}")
        assert resp.status_code == 204


# ─── Health ──────────────────────────────────────────────────────────────────

class TestHealth:
    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
