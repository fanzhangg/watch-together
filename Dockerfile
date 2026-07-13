# Multi-stage build: compile the React frontend with Node, then run the FastAPI
# backend (which serves the built assets) on Python. One image, one service —
# matching the single-origin design, and this is what Render builds.

# --- Stage 1: build the frontend -----------------------------------------
FROM node:20-slim AS frontend
WORKDIR /frontend

# Playwright is a devDependency used only for e2e; never fetch browsers here.
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# Copy manifests first so `npm ci` is cached until dependencies actually change.
COPY frontend/package.json frontend/package-lock.json ./
# `ci` (not `install`) so the build is reproducible from the lockfile.
RUN npm ci

COPY frontend/ ./
# vite.config.ts writes the build to ../backend/app/web
RUN mkdir -p /backend/app && npm run build

# --- Stage 2: backend runtime --------------------------------------------
FROM python:3.13-slim AS runtime
WORKDIR /backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
# Bring in the compiled SPA produced by the frontend stage.
COPY --from=frontend /backend/app/web ./app/web

ENV PORT=8000
EXPOSE 8000
# Apply migrations, then serve the API and the SPA on one origin.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
