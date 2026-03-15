"""Application configuration via environment variables."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"

# JWT
SECRET_KEY = os.getenv("ROCKIT_SECRET_KEY", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ROCKIT_TOKEN_EXPIRE_MINUTES", "480"))

# Database — user data separate from research DuckDB
USER_DB_URL = os.getenv(
    "ROCKIT_USER_DB_URL",
    f"sqlite+aiosqlite:///{DATA_DIR / 'users.db'}",
)

# Research DuckDB (read-only from API, never written by user actions)
RESEARCH_DB_PATH = str(DATA_DIR / "research.duckdb")

# Live data
LIVE_DATA_DIR = os.getenv(
    "ROCKIT_LIVE_DATA_DIR",
    r"G:\My Drive\future_data\1min",
)

# CORS
CORS_ORIGINS = os.getenv("ROCKIT_CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

# Demo mode — seeds a demo user + mock signals for testing
DEMO_MODE = os.getenv("ROCKIT_DEMO_MODE", "true").lower() == "true"
