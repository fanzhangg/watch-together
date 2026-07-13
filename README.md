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
backend/            FastAPI app, SQLAlchemy, Alembic migrations, pytest
frontend/           React + Vite SPA (built assets are served by the backend)
Dockerfile          Multi-stage build (Node build -> Python runtime); used by Render
.dockerignore       Keeps .venv / node_modules / .env out of the image
docker-compose.yml  Local stack: the image + a real Postgres
render.yaml         Render service definition
docs/               Design doc
```

## Prerequisites

- **Python 3.11+** (3.13 used here)
- **Node 20+** — for local frontend dev only. Install with
  `winget install OpenJS.NodeJS.LTS`, then reopen the terminal.
- **Docker Desktop** *(optional)* — only if you want to build/run the container
  image or test against a real Postgres. `winget install Docker.DockerDesktop`.
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

## Building and running with Docker

One `docker build` produces **both** halves of the app. The [Dockerfile](Dockerfile)
is multi-stage:

```
Stage 1  node:20-slim          Stage 2  python:3.13-slim  ← the final image
┌──────────────────────┐       ┌────────────────────────────────────┐
│ npm ci               │       │ pip install -r requirements.txt    │
│ npm run build        │  ──▶  │ COPY --from=frontend  (built SPA)  │
│  → backend/app/web   │       │ alembic upgrade head && uvicorn    │
└──────────────────────┘       └────────────────────────────────────┘
     discarded                  ~294 MB · Python + compiled SPA only
```

The Node stage is thrown away — the shipped image contains no Node and no
`node_modules`, just Python and the compiled assets. One container serves the
SPA **and** the API on a single origin, which is exactly what Render runs.

[.dockerignore](.dockerignore) keeps local state out of the image: `.venv`,
`node_modules`, `*.db`, and — importantly — **`backend/.env`, so your TMDB key is
never baked into a layer**. The container gets its config from environment
variables at run time. (Note the patterns use `**/*.db`, not `*.db`: Docker only
matches a bare `*.db` at the context root, so `backend/dev.db` would otherwise
sneak in.)

> **Docker Desktop must actually be running**, not just installed. If you see
> `failed to connect to the docker API ... dockerDesktopLinuxEngine`, start
> Docker Desktop and wait for the whale icon to settle.

### Option A — Compose: the app + a real Postgres (recommended)

The closest local mirror of production (Render + Neon). Migrations run
automatically once the database reports healthy.

```bash
docker compose up --build         # build + start  → http://localhost:8000
docker compose up -d --build      # ...in the background
docker compose logs -f app        # follow the app logs
docker compose down               # stop
docker compose down -v            # stop AND delete the database volume
```

Config: `backend/.env` is read for your `TMDB_API_KEY`; Compose supplies
`DB_URL`, `DEV_LOGIN=true`, `SESSION_SECRET` and `APP_BASE_URL` itself
(see [docker-compose.yml](docker-compose.yml)).

### Option B — build and run the image on its own

Useful for checking exactly what Render will build.

```bash
docker build -t watch-together .

docker run --rm -p 8000:8000 \
  -e DEV_LOGIN=true \
  -e TMDB_API_KEY=your_key_here \
  watch-together                  # → http://localhost:8000
```

With no `DB_URL`, the container falls back to a **SQLite file inside the
container** — fine for a quick look, but it disappears when the container does.
To point it at a real database (e.g. Neon), pass one:

```bash
docker run --rm -p 8000:8000 \
  -e DB_URL="postgresql://user:pass@host/db" \
  -e TMDB_API_KEY=your_key_here \
  watch-together
```

### Handy

```bash
docker compose exec app sh                       # shell inside the app container
docker compose exec db psql -U watch -d watchtogether   # psql into the database
docker compose build --no-cache app             # force a clean rebuild
docker images watch-together                    # check the image size
```

> **Base-image pulls can fail with `EOF`** on flaky networks — it's a transient
> Docker Hub / CDN hiccup, not a problem with the Dockerfile. Just run the build
> again.

> Day to day, prefer the two-terminal setup above — it has hot reload. Use Docker
> to verify the image, the migrations, and the Postgres path before deploying.

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
`ON DELETE CASCADE`, `UNIQUE`, etc. behave exactly as in production), start the
Compose stack and point the suite at it:

```bash
docker compose up -d db
docker compose exec -T db psql -U watch -d watchtogether -c "CREATE DATABASE watchtogether_test;"
```

```powershell
cd backend
$env:TEST_DATABASE_URL = "postgresql://watch:watch@localhost:5432/watchtogether_test"
pytest        # all 38 pass on Postgres as well as SQLite
```

(A throwaway Neon branch works the same way — just use its connection string.)
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
