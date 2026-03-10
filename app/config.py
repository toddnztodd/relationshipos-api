"""Application configuration using pydantic-settings.

All settings have sensible defaults so the app starts cleanly with no
environment variables set. Override any value via environment variable or
a .env file.

DATABASE_URL handling:
  The Neon PostgreSQL connection string is hardcoded as the production
  database. If a DATABASE_URL env var is set AND it points to PostgreSQL,
  that value is used instead. SQLite env vars are ignored to prevent
  accidental data loss on ephemeral platforms like Render.

CORS_ORIGINS handling:
  pydantic-settings 2.x tries to JSON-decode any field typed as list[str]
  before validators run, which causes a crash when the env var is a plain
  string like "*".  We store CORS_ORIGINS as a plain str and expose it as a
  list via the `cors_origins_list` property.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache

from pydantic_settings import BaseSettings


# ── Neon PostgreSQL (production) ─────────────────────────────────────────────
# This is the permanent database. Data persists across all deploys.
_NEON_DATABASE_URL = (
    "postgresql://neondb_owner:npg_HvYka2b5nPOZ"
    "@ep-autumn-sound-a7om89h2-pooler.ap-southeast-2.aws.neon.tech"
    "/neondb?sslmode=require"
)


def _resolve_database_url() -> str:
    """Determine the correct DATABASE_URL.

    Priority:
      1. If DATABASE_URL env var is set AND contains 'postgresql' or 'postgres://',
         use it (allows overriding with a different PostgreSQL instance).
      2. Otherwise, always use the hardcoded Neon PostgreSQL URL.
         This prevents Render's SQLite env var from overriding the production DB.
    """
    env_url = os.environ.get("DATABASE_URL", "").strip()
    if env_url and ("postgresql" in env_url or "postgres://" in env_url):
        return env_url
    # Ignore SQLite or empty — always fall back to Neon
    return _NEON_DATABASE_URL


class Settings(BaseSettings):
    # ── Application ───────────────────────────────────────────────────────────
    APP_NAME: str = "RelationshipOS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Database ──────────────────────────────────────────────────────────────
    # Resolved at import time — see _resolve_database_url() above.
    DATABASE_URL: str = _resolve_database_url()

    @property
    def async_database_url(self) -> str:
        """Return the DATABASE_URL converted for async SQLAlchemy."""
        # Always re-resolve to ensure Neon is used even if pydantic loaded SQLite
        url = _resolve_database_url()

        # Strip channel_binding param (not supported by asyncpg)
        if "channel_binding=" in url:
            url = re.sub(r'[&?]channel_binding=[^&]*', '', url)
            url = url.rstrip('?').rstrip('&')

        # Handle Render/Heroku-style postgres:// URLs
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        elif url.startswith("postgresql+asyncpg://"):
            pass
        # SQLite handling (only for local dev when explicitly forced)
        elif url.startswith("sqlite:///"):
            url = "sqlite+aiosqlite:///" + url[len("sqlite:///"):]
        elif url.startswith("sqlite+aiosqlite:///"):
            pass

        return url

    @property
    def is_postgres(self) -> bool:
        """Return True if using PostgreSQL."""
        url = _resolve_database_url()
        return "postgresql" in url or "postgres://" in url

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "relateos-secret-key-2024-production"
    SECRET_KEY: str = "relateos-secret-key-2024-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "*"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a list, accepting multiple formats."""
        v = self.CORS_ORIGINS.strip()
        if not v:
            return ["*"]
        if v.startswith("["):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except json.JSONDecodeError:
                pass
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
