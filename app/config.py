"""Application configuration using pydantic-settings.

All settings have sensible defaults so the app starts cleanly with no
environment variables set. Override any value via environment variable or
a .env file.

IMPORTANT — CORS_ORIGINS:
  pydantic-settings 2.x tries to JSON-decode any field typed as list[str]
  before validators run, which causes a crash when the env var is a plain
  string like "*".  We store CORS_ORIGINS as a plain str and expose it as a
  list via the `cors_origins_list` property, which handles all formats:
    "*"
    "https://myapp.com"
    "https://a.com,https://b.com"
    '["https://a.com","https://b.com"]'
"""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Application ───────────────────────────────────────────────────────────
    APP_NAME: str = "RelationshipOS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Database ──────────────────────────────────────────────────────────────
    # SQLite by default (zero-config). Switch to PostgreSQL by setting:
    #   DATABASE_URL=postgresql+asyncpg://user:password@host:5432/relationshipos
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/relationshipos.db"

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "relateos-secret-key-2024-production"
    SECRET_KEY: str = "relateos-secret-key-2024-production"  # alias for compatibility
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Stored as a plain string to avoid pydantic-settings JSON-parsing issues.
    # Use the `cors_origins_list` property wherever a list is needed.
    CORS_ORIGINS: str = "*"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a list, accepting multiple formats."""
        v = self.CORS_ORIGINS.strip()
        if not v:
            return ["*"]
        # JSON array: '["https://a.com","https://b.com"]'
        if v.startswith("["):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except json.JSONDecodeError:
                pass
        # Comma-separated or single value: "https://a.com,https://b.com" or "*"
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",        # silently ignore unknown env vars
        "case_sensitive": False,  # DATABASE_URL and database_url both work
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
