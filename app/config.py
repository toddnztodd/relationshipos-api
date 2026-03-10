"""Application configuration using pydantic-settings.

All settings have sensible defaults so the app starts cleanly with no
environment variables set. Override any value via environment variable or
a .env file.

DATABASE_URL handling:
  Accepts any of these formats and auto-converts for async SQLAlchemy:
    postgres://...          -> postgresql+asyncpg://...
    postgresql://...        -> postgresql+asyncpg://...
    postgresql+asyncpg://...  (used as-is)
    sqlite:///...           -> sqlite+aiosqlite:///...
    sqlite+aiosqlite:///... (used as-is)

CORS_ORIGINS handling:
  pydantic-settings 2.x tries to JSON-decode any field typed as list[str]
  before validators run, which causes a crash when the env var is a plain
  string like "*".  We store CORS_ORIGINS as a plain str and expose it as a
  list via the `cors_origins_list` property.
"""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic_settings import BaseSettings


# Default Neon PostgreSQL connection string (persistent across deploys)
_DEFAULT_DATABASE_URL = (
    "postgresql://neondb_owner:npg_HvYka2b5nPOZ"
    "@ep-autumn-sound-a7om89h2-pooler.ap-southeast-2.aws.neon.tech"
    "/neondb?sslmode=require"
)


class Settings(BaseSettings):
    # ── Application ───────────────────────────────────────────────────────────
    APP_NAME: str = "RelationshipOS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Database ──────────────────────────────────────────────────────────────
    # Defaults to Neon PostgreSQL. Override via DATABASE_URL env var.
    DATABASE_URL: str = _DEFAULT_DATABASE_URL

    @property
    def async_database_url(self) -> str:
        """Return the DATABASE_URL converted for async SQLAlchemy."""
        url = self.DATABASE_URL.strip()

        # Strip channel_binding param (not supported by asyncpg)
        if "channel_binding=" in url:
            import re
            url = re.sub(r'[&?]channel_binding=[^&]*', '', url)
            # Clean up trailing ? or leading & after removal
            url = url.rstrip('?').rstrip('&')

        # Handle Render/Heroku-style postgres:// URLs
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        elif url.startswith("postgresql+asyncpg://"):
            pass
        # SQLite handling
        elif url.startswith("sqlite:///"):
            url = "sqlite+aiosqlite:///" + url[len("sqlite:///"):]
        elif url.startswith("sqlite+aiosqlite:///"):
            pass

        return url

    @property
    def is_postgres(self) -> bool:
        """Return True if using PostgreSQL."""
        return "postgresql" in self.DATABASE_URL or "postgres://" in self.DATABASE_URL

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
