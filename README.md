# Watch Together

A minimal full-stack app for sharing movie watch-lists with another person.
Sign in with Google, create shared lists, add movies via TMDB search, and mark
them watched / want-to-watch together.

**Stack:** React + Vite · FastAPI + SQLAlchemy 2.0 (sync) + Alembic · Postgres
(Neon) · deployed on Render. Full design in [docs/design.md](docs/design.md).

Status: **M0 — scaffold** (infra only; feature milestones M1–M6 to come).

## Repo layout

```
backend/    FastAPI app, SQLAlchemy, Alembic migrations, pytest
frontend/   React + Vite SPA (built assets are served by the backend)
Dockerfile  Multi-stage build (Node build -> Python runtime) used by Render
render.yaml Render service definition
docs/       Design doc
```

## Prerequisites

- **Python 3.11+** (3.13 used here)
- **Node 20+** — for local frontend dev only. Install with
  `winget install OpenJS.NodeJS.LTS`, then reopen the terminal.
- A **Neon** Postgres database (free tier) — optional until you need the DB;
  the API's health check runs without one.

## Local development

Run the backend and frontend in two terminals. The Vite dev server proxies
`/api` to the backend, so the browser sees a single origin (needed for the
session cookie).

### Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # then fill in values as needed
uvicorn app.main:app --reload --port 8000
```

Check it: <http://localhost:8000/api/health> → `{"status":"ok"}`

Run tests:

```bash
cd backend
pytest
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173> — it shows the scaffold page and reports the
backend health via the dev proxy.

## Database migrations

```bash
cd backend
alembic upgrade head          # apply migrations
alembic revision --autogenerate -m "add users"   # create a new one
```

Set `DB_URL` (Neon pooled connection string) in `backend/.env` first.

## Deploy (Render + Neon)

1. Create a Neon project; copy the **pooled** connection string.
2. Push this repo to GitHub and create a Render **Blueprint** from `render.yaml`
   (or a Docker web service pointing at the `Dockerfile`).
3. Set env vars in Render: `DB_URL`, `GOOGLE_CLIENT_ID`, `TMDB_API_KEY`
   (`SESSION_SECRET` is auto-generated; keep `DEV_LOGIN=false`).
4. Deploy. Migrations run automatically on start; the container serves the SPA
   and the API on one origin.

## Backups

Periodically dump the database (cheap insurance):

```bash
pg_dump "$DB_URL" > backup-$(date +%F).sql
```
