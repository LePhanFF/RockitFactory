# Rockit Dashboard — Testing Instructions

## Prerequisites

- Python 3.11+ with pip
- Node.js 18+ with npm
- Both `rockit-core` and `rockit-serve` installed

## Quick Start (2 terminals)

### Terminal 1: Start the API server

```bash
cd RockitFactory

# Install Python deps (one time)
pip install -e packages/rockit-core
pip install -e packages/rockit-serve
pip install "sqlalchemy[asyncio]>=2.0" "aiosqlite>=0.20" "python-jose[cryptography]>=3.3" \
  "passlib[bcrypt]>=1.7" "bcrypt>=4.0,<5.0" "httpx>=0.27"

# Start server in demo mode (mock market data, no live feed needed)
ROCKIT_DEMO_MODE=true python -m uvicorn rockit_serve.app:app --reload --port 8000
```

On Windows (PowerShell):
```powershell
$env:ROCKIT_DEMO_MODE="true"
python -m uvicorn rockit_serve.app:app --reload --port 8000
```

The API starts with:
- Demo market loop (simulated NQ data cycling through all 4 phases)
- In-memory SQLite user database
- Auto-generated JWT secret key

### Terminal 2: Start the Dashboard

```bash
cd RockitFactory/packages/rockit-dashboard

# Install npm deps (one time)
npm install

# Start dev server (proxies API calls to localhost:8000)
npm run dev
```

Open **http://localhost:5173** in your browser.

## What to Test

### 1. Registration & Login
- Click "Need an account? Register"
- Create a user (e.g., `trader1` / `trader1@test.com` / `password123`)
- You'll be logged in automatically
- Log out, then log back in to verify

### 2. Strategy Board (auto-updates every 2 seconds)
- Watch the 12 strategy cards cycle through states as demo data progresses
- **Phase 0** (Pre-Market): NDOG shows as WATCHING
- **Phase 1** (First Hour): Strategies start WATCHING
- **Phase 2** (Mid-Session): OR Rev FIRES, 80P ARMS, Trend Bear BLOCKED
- Cards show entry/stop/target when ARMED or FIRED
- Cards show P&L when FIRED
- Cards show condition progress when WATCHING (e.g., ADX, timer bars)

### 3. Trade Plan Timeline
- Phase progress bar highlights current phase
- Active strategies listed per phase
- Decision tree shows IB range classification
- Risk rules show position count, daily P&L, consecutive losses

### 4. Market Context Panel
- Structure section: IB, VA, POC, DPOC, VWAP (all updating live)
- Key Levels: sorted by proximity to current price
- Indicators: EMAs, RSI, ATR, ADX
- Order Flow: CVD, TPO shape

### 5. Trade Ideas (proactive)
- When a strategy reaches ARMED state (e.g., 80P Rule), a trade idea card appears
- Shows confidence level, direction, entry/stop/target, R:R
- Shows evidence cards (for/against)
- Shows agent verdict (TAKE/SKIP)

### 6. Journal (slide-out panel)
- Click the book icon in the header to open
- **Trades tab**: Log a trade with strategy, direction, entry/stop/target
- Close trades with Win/Loss/Scratch buttons — auto-calculates P&L and R-multiple
- **Notes tab**: Write premarket/intraday/postmarket notes
- All data persists per-user in SQLite

### 7. Strategy Preferences
- Use the API directly to set which strategies you trade:
```bash
# Mark OR Reversal as mastered
curl -X PUT http://localhost:8000/auth/strategies/or_reversal \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"strategy_id": "or_reversal", "is_active": true, "mastery_level": "mastered"}'

# Deactivate a strategy you don't trade
curl -X PUT http://localhost:8000/auth/strategies/trend_bear \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"strategy_id": "trend_bear", "is_active": false, "mastery_level": "learning"}'
```
- Mastered strategies show an "M" badge on their card
- Deactivated strategies appear dimmed (40% opacity)

### 8. Bot API (NinjaTrader integration)
```bash
# Create a bot API key
curl -X POST http://localhost:8000/auth/bot-keys \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "My NinjaTrader Bot", "instruments": "NQ"}'
# Response includes api_key — save it

# Poll for active signals (what NinjaTrader would call every 30s)
curl http://localhost:8000/api/v1/signals?instrument=NQ \
  -H "X-API-Key: YOUR_BOT_KEY"

# Get signal history
curl http://localhost:8000/api/v1/signals/history?instrument=NQ&limit=20 \
  -H "X-API-Key: YOUR_BOT_KEY"

# WebSocket subscription (for lower latency)
# Connect to: ws://localhost:8000/ws/bot?api_key=YOUR_BOT_KEY
# Receives JSON SignalEvent on each ARMED/FIRED/CLOSED state change
```

### 9. Multi-User Test
- Open a second browser (or incognito window)
- Register a different user
- Each user sees their own trades and journal
- Both users see the same market data and strategy signals
- Strategy preferences are per-user (user A can master OR Rev, user B can master 80P)

### 10. Theme Switching
- Click the palette icon in the header
- Cycles: Dark (default) → Light → Metal → Dark
- All panels, cards, and text adapt to the theme

## Running Tests

### API Tests (17 tests)
```bash
cd RockitFactory
python -m pytest packages/rockit-serve/tests/test_api.py -v
```

### TypeScript Type Check
```bash
cd packages/rockit-dashboard
npx tsc --noEmit
```

### Production Build
```bash
cd packages/rockit-dashboard
npm run build
# Output in dist/ — 252 KB JS + 17 KB CSS
```

## API Endpoints Reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /auth/register | - | Create account |
| POST | /auth/login | - | Get JWT token |
| GET | /auth/me | JWT | Current user profile |
| GET | /auth/strategies | JWT | Strategy preferences |
| PUT | /auth/strategies/{id} | JWT | Update strategy preference |
| GET | /auth/bot-keys | JWT | List bot API keys |
| POST | /auth/bot-keys | JWT | Create bot API key |
| DELETE | /auth/bot-keys/{id} | JWT | Delete bot API key |
| GET | /api/v1/trades | JWT | List user's trades |
| POST | /api/v1/trades | JWT | Log a trade |
| PATCH | /api/v1/trades/{id} | JWT | Update/close a trade |
| DELETE | /api/v1/trades/{id} | JWT | Delete a trade |
| GET | /api/v1/journal | JWT | List journal entries |
| POST | /api/v1/journal | JWT | Create journal entry |
| PATCH | /api/v1/journal/{id} | JWT | Update journal entry |
| GET | /api/v1/signals | API Key | Active signals (bot polling) |
| GET | /api/v1/signals/history | API Key | Signal history |
| WS | /ws/dashboard | - | Dashboard live stream |
| WS | /ws/bot?api_key=X | API Key | Bot live stream |
| GET | /api/v1/market/context | - | Current market state |
| GET | /api/v1/market/strategies | - | All strategy states |
| GET | /health | - | Health check |

## Architecture Notes

- **User data** (accounts, trades, journal, bot keys) → SQLite (`data/users.db`)
- **Research data** (backtest trades, sessions, observations) → DuckDB (`data/research.duckdb`) — READ ONLY from API
- **Market state** → In-memory, pushed via WebSocket
- **Demo mode** → Simulated NQ data, no live feed needed
- **Strategy code** → Untouched in `rockit-core`, only consumed read-only
