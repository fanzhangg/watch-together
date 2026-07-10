"""Application configuration.

Settings are read from environment variables (and a local ``.env`` in dev).
See ``.env.example`` for the full list.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Database ---------------------------------------------------------
    # Neon gives a `postgresql://...` URL; SQLAlchemy needs the driver in the
    # scheme. `database_url` (property) normalizes it to psycopg v3.
    # Empty by default so the app can import (and the health check can run)
    # without a database configured. The engine connects lazily.
    db_url: str = ""

    # SQLAlchemy pool tuning for serverless Postgres (Neon). Small pool +
    # pre-ping avoids stale-connection errors after autosuspend.
    db_pool_size: int = 5
    db_max_overflow: int = 2
    db_pool_recycle_seconds: int = 300

    # --- Auth (used from M1) ---------------------------------------------
    session_secret: str = "dev-insecure-secret-change-me"
    google_client_id: str = ""
    # Local-only login bypass so the UI can be built before OAuth is wired.
    dev_login: bool = False

    # --- External APIs (used from M3) ------------------------------------
    tmdb_api_key: str = ""

    @property
    def database_url(self) -> str:
        """Normalize the DB URL to the psycopg (v3) driver SQLAlchemy expects."""
        url = self.db_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        elif url.startswith("postgres://"):  # some providers use this scheme
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
