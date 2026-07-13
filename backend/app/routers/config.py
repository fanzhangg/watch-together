"""Public runtime configuration for the frontend.

The SPA is compiled once (in the Docker image) and then runs in every
environment, so anything environment-specific must be fetched at run time rather
than baked in at build time with VITE_* variables. That keeps one image
deployable anywhere and means changing the Google client id is a restart, not a
rebuild.

Nothing secret is exposed: the Google client id is public by design (it ships to
the browser in the sign-in button), and dev_login only reports whether the
local-only bypass is enabled.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas import ConfigOut

router = APIRouter(prefix="/api", tags=["config"])


@router.get(
    "/config",
    response_model=ConfigOut,
    summary="Which sign-in methods this deployment offers",
)
def get_config(settings: Settings = Depends(get_settings)) -> ConfigOut:
    return ConfigOut(
        google_client_id=settings.google_client_id or None,
        dev_login=settings.dev_login,
    )
