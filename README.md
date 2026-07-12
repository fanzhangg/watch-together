# Watch Together

A minimal full-stack app for sharing movie watch-lists with another person.
Sign in with Google, create shared lists, add movies via TMDB search, and mark
them watched / want-to-watch together.

**Stack:** React + Vite · FastAPI + SQLAlchemy 2.0 (sync) + Alembic · Postgres
(Neon) · deployed on Render. Full design in [docs/design.md](docs/design.md).

Status: **M5 — UI complete** (sign in, create lists, search TMDB, add movies,
mark watched, invite someone). Next: deploy to Render (M6).

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
- A **Neon** Postgres database (free tier) — optional for local dev, which
  defaults to SQLite.
- A **TMDB API key** (free) — only needed for *real* movie search. Get it from
  <https://www.themoviedb.org/settings/api> and set `TMDB_API_KEY` in
  `backend/.env`. Without it, the TMDB endpoints return a clear `503`; the rest
  of the app works fine.

## Running the app locally

> **You need TWO terminals running at once** — the backend and the frontend.
> The Vite dev server proxies `/api` to the backend so the browser sees a single
> origin (needed for the session cookie). If only the frontend is running, the
> page shows **"Backend health: unreachable"** — that just means the backend
> isn't up.

### One-time setup

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate       # macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env              # fill in values as needed (optional for M0)

# Frontend (in a separate shell)
cd frontend
npm install
```

### Every time — two terminals

**Terminal 1 — backend** (leave running):

```bash
cd backend
.venv\Scripts\Activate.ps1        # Windows PowerShell
uvicorn app.main:app --reload --port 8000
```

Wait for `Uvicorn running on http://127.0.0.1:8000`. Sanity check:
<http://localhost:8000/api/health> → `{"status":"ok"}`

**Terminal 2 — frontend** (leave running):

```bash
cd frontend
npm run dev
```

Open <http://localhost:5173>. With both servers up you'll see the sign-in
state and a **Dev login** button (works when the backend runs with
`DEV_LOGIN=true`, which is the default in `.env.example`). Vite hot-reloads, so
once the backend is up just refresh the page.

> **Database:** local dev/test defaults to a **SQLite** file (`dev.db`) — zero
> setup. Run migrations once before logging in: `alembic upgrade head` (creates
> the `users` table). Production uses Postgres/Neon via `DB_URL`.

## Testing

### Backend (pytest)

```bash
cd backend
.venv\Scripts\Activate.ps1        # Windows PowerShell
pytest                            # runs everything in backend/tests/
pytest -v                         # verbose
pytest tests/test_health.py       # a single file
```

Covers the health-check smoke test, the M1 auth flow, and the M2 list
membership/403 access-control tests. Tests use an in-memory SQLite DB per test
by default.

To run the **same tests against real Postgres** (prod-accurate constraints —
recommended from M2 on), point them at a throwaway Neon branch:

```powershell
$env:TEST_DATABASE_URL = "<neon test-branch pooled connection string>"
pytest
```

See [docs/design.md](docs/design.md) section 11.

### Frontend

```bash
cd frontend
npm run typecheck                 # tsc --noEmit
npm run build                     # type-checks and builds into backend/app/web
```

### End-to-end (Playwright)

The e2e suite drives the real UI in a browser against the **built** app served
by FastAPI — i.e. exactly how production runs (one origin, no dev proxy):

```bash
cd frontend && npm run build                      # 1. build the SPA
cd ../backend && uvicorn app.main:app --port 8020 # 2. serve it (DEV_LOGIN=true,
                                                  #    TMDB_API_KEY set)
cd ../frontend && npm run e2e                     # 3. drive it
```

It covers the happy path (sign in → create list → search TMDB → add movie →
mark watched → invite link) and the signed-out invite preview. First run needs
`npx playwright install chromium`.

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
