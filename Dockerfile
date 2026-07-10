# Multi-stage build: compile the React frontend with Node, then run the FastAPI
# backend (which serves the built assets) on Python. One image, one Render
# service — matches the single-origin design.

# --- Stage 1: build the frontend -----------------------------------------
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
# vite.config.ts writes the build to ../backend/app/web
RUN mkdir -p /backend/app && npm run build

# --- Stage 2: backend runtime --------------------------------------------
FROM python:3.13-slim AS runtime
WORKDIR /backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
# Bring in the compiled SPA produced by the frontend stage.
COPY --from=frontend /backend/app/web ./app/web

ENV PORT=8000
EXPOSE 8000
# Apply migrations, then serve.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
