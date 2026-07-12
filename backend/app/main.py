"""FastAPI application entrypoint.

Serves the JSON API under ``/api/*`` and, in production, the built React SPA
(everything else). Route order matters: the API router and static assets are
registered BEFORE the SPA catch-all so the fallback never shadows them
(design risk #3).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import auth, health, invites, items, lists, tmdb

# Vite builds into this directory (see frontend/vite.config.ts). It is absent
# in local backend-only dev and in tests — the app still serves /api fine.
WEB_DIR = Path(__file__).parent / "web"

app = FastAPI(title="Watch-Together API")

# --- API routes (registered first) ---------------------------------------
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(lists.router)
app.include_router(items.router)
app.include_router(tmdb.router)
app.include_router(invites.list_invites_router)
app.include_router(invites.router)


# --- Static SPA (registered last, only if a build exists) -----------------
def _mount_spa(application: FastAPI) -> None:
    index_file = WEB_DIR / "index.html"
    if not index_file.exists():
        return

    # Hashed build assets under /assets are served directly.
    application.mount(
        "/assets",
        StaticFiles(directory=WEB_DIR / "assets"),
        name="assets",
    )

    @application.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        # Any non-API, non-asset path returns index.html for client-side routing.
        candidate = WEB_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_file)


_mount_spa(app)
