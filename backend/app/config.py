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

    # --- Auth ------------------------------------------------------------
    session_secret: str = "dev-insecure-secret-change-me"
    google_client_id: str = ""
    # Local-only login bypass so the UI can be built before OAuth is wired.
    dev_login: bool = False
    # Session cookie settings. secure=False for local http dev; set True in prod.
    session_cookie_name: str = "wt_session"
    session_cookie_secure: bool = False
    session_max_age_seconds: int = 60 * 60 * 24 * 14  # 14 days

    # --- External APIs (used from M3) ------------------------------------
    tmdb_api_key: str = ""

    # --- App ---------------------------------------------------------------
    # Public base URL used to build share links, e.g. https://host/invite/<code>.
    # In dev the SPA is on :5173 while the API is on :8000, so set
    # APP_BASE_URL=http://localhost:5173 to get clickable invite links.
    app_base_url: str = ""
    # Render injects this automatically (https://<service>.onrender.com), so
    # production gets correct https invite links with no manual configuration.
    render_external_url: str = ""

    @property
    def public_base_url(self) -> str:
        """Explicit config wins, then Render's own URL; empty means 'use the
        request's origin' (correct when the SPA and API share one)."""
        return self.app_base_url or self.render_external_url

    @property
    def database_url(self) -> str:
        """Resolve the SQLAlchemy URL.

        - Empty -> a local SQLite file so the app runs with zero config in dev.
        - Postgres schemes are normalized to the psycopg (v3) driver.
        - SQLite / other URLs pass through unchanged.

        Production sets ``DB_URL`` to the Neon pooled connection string.
        """
        url = self.db_url
        if not url:
            return "sqlite:///./dev.db"
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        elif url.startswith("postgres://"):  # some providers use this scheme
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        return url

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
