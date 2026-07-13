# Watch-Together — Design Doc

A minimal full-stack app for sharing movie watch-lists with another person. Both
members of a list can add movies (via TMDB search), mark them watched/unwatched,
and edit the list together.

Status: **approved design, pre-implementation.**

---

## 1. Requirements

- Users sign in with **Google**. First sign-in auto-creates an account.
- A user can create **multiple named lists** (e.g. "Date night", "Horror marathon").
- Each list has **members**. Any member can view and edit the list (add/remove
  movies, change status). The list creator is the owner.
- **Adding a movie**: search TMDB by title → pick a result → backend fetches
  metadata → movie is saved to the list with a **status**
  (`want_to_watch` / `watched`).
- **Inviting**: a member generates a **shareable invite link/code**; whoever
  opens it while logged in joins the list.
- The **TMDB API key lives only on the backend** — the browser never sees it.

### Out of scope (v1)
- Ratings / reviews / notes on movies — **future scope**.
- Real-time collaboration — refresh-on-action is fine (last-write-wins).
- Conflict resolution, WebSockets, caching layers, tests/CI beyond a smoke test.

---

## 2. Stack (final)

| Layer     | Choice                                             | Notes |
|-----------|----------------------------------------------------|-------|
| Frontend  | React + Vite, TanStack Query                       | Built static assets served by the backend |
| Backend   | FastAPI + **sync** SQLAlchemy 2.0 + Alembic        | Sync (not async) — right call for ~2 users |
| Database  | **Neon** Postgres                                  | Pooled connection string, small pool size |
| Auth      | Google OAuth → own signed-cookie session           | + dev-login bypass for local work |
| External  | TMDB API, server-side proxy                        | Key never reaches the browser |
| Hosting   | **Render** web service, paid warm instance (~$7/mo)| Single service serves static + API |
| Repo      | Monorepo, single deployed service                  | `render.yaml` infra-as-code |
| Ops       | `pg_dump` backup habit                             | Cheap insurance against data loss |

**Rough cost:** ~$7/mo (Render Starter, always-on) + Neon free tier.

### Key stack decisions & rationale
- **Sync, not async, SQLAlchemy.** Async buys concurrency we'll never need at two
  users, and charges us in complexity (greenlet issues, harder stack traces).
  Sync is simpler and strictly better here.
- **Single Render service serves both static frontend and `/api/*`.** Same origin
  avoids cross-site cookie / CORS complexity entirely. Don't split it.
- **Snapshot TMDB metadata into the DB.** The list renders with zero external
  calls and survives TMDB outages / rate limits. `tmdb_id` allows a later refresh.
- **Decoupled DB (Neon).** Compute host is now a swappable decision; we can move
  off Render later without touching data. Neon's free tier persists (unlike
  Render's free Postgres, which is deleted ~90 days).

---

## 3. Architecture

```
┌────────────┐   HTTPS/JSON    ┌─────────────┐   SQLAlchemy  ┌──────────────┐
│  React SPA │ ───────────────▶│   FastAPI   │ ─────────────▶│  Postgres    │
│ (Vite)     │◀─────────────── │  (uvicorn)  │   (sync)      │  (Neon)      │
└────────────┘   httpOnly       └─────────────┘               └──────────────┘
     │           cookie              │  server-side key
     │ Google Identity Services      ▼
     └──────────────────────▶  TMDB API (proxied)
```

Both the built React static files and the `/api/*` routes are served by the same
FastAPI process on one Render web service.

---

## 4. Data model

```
users
  id            uuid pk
  google_sub    text unique         -- Google's stable user id
  email         text unique
  display_name  text
  avatar_url    text
  created_at    timestamptz

lists
  id            uuid pk
  name          text
  owner_id      uuid -> users.id
  created_at    timestamptz

list_members                        -- who can access a list
  list_id       uuid -> lists.id
  user_id       uuid -> users.id
  role          text   -- 'owner' | 'member'
  joined_at     timestamptz
  PRIMARY KEY (list_id, user_id)

list_items                          -- a movie in a list (with TMDB snapshot)
  id            uuid pk
  list_id       uuid -> lists.id
  tmdb_id       int
  title         text
  release_year  int
  poster_path   text                -- TMDB relative path
  overview      text
  status        text   -- 'want_to_watch' | 'watched'
  added_by      uuid -> users.id
  watched_on    date null           -- M7: the day it was watched, user-owned
  created_at    timestamptz
  UNIQUE (list_id, tmdb_id)         -- prevent dupes in a list
  CHECK ((status = 'watched') = (watched_on IS NOT NULL))

invites
  id            uuid pk
  list_id       uuid -> lists.id
  code          text unique         -- random, in the share URL
  created_by    uuid -> users.id
  expires_at    timestamptz null
  created_at    timestamptz
```

### Indexes (up front)
- `list_members(user_id)` — "my lists" lookup
- `list_items(list_id)` — board loads
- `list_items(list_id, watched_on)` — chronological watched ordering (M7)
- `UNIQUE(list_id, tmdb_id)` and `invites.code` uniques cover the rest

### Notes
- TMDB fields are **snapshotted** into `list_items`; rendering needs no TMDB call.
- **`watched_on` is a `DATE`, not a timestamp** (M7). "We watched it on the 12th"
  is the same fact in every timezone; a timestamp forces every reader to pick one
  and gets the day wrong for evening viewings. The **CHECK constraint makes
  "watched" and "has a date" the same thing** — there is no watched-but-undated
  state to branch on anywhere in the code.
- Invite is **multi-use until expiry** (simplest); a `used_at` column can make it
  single-use later.
- Access control is one rule: for any `/api/lists/{id}/*` route, require a row in
  `list_members` for `(id, current_user)`.

---

## 5. API surface

### Auth
- `POST /api/auth/google` — body: Google ID token → verify → upsert user → set httpOnly session cookie
- `POST /api/auth/logout`
- `GET  /api/auth/me` — current user or 401

### Lists
- `GET  /api/lists` — lists I'm a member of
- `POST /api/lists` — create (I become owner + member)
- `GET  /api/lists/{id}` — list + members
- `PATCH /api/lists/{id}` — rename (owner)
- `DELETE /api/lists/{id}` — (owner)

### Items
- `GET  /api/lists/{id}/items`
- `GET  /api/lists/{id}/items/{itemId}` — one item (the detail page's own load, M7)
- `POST /api/lists/{id}/items` — body: `{ tmdb_id, status }` → backend fetches TMDB metadata, inserts snapshot
- `PATCH /api/lists/{id}/items/{itemId}` — body: `{ status?, watched_on? }` (M7)
- `DELETE /api/lists/{id}/items/{itemId}`

#### PATCH item semantics (M7)
Both fields are optional, but the request must contain at least one, and it must
leave the row consistent with the CHECK constraint. Contradictions are **422s,
not silent fixes** — they can only come from a client bug.

| Body | Result |
|------|--------|
| `{status: "watched", watched_on: "2026-07-12"}` | watched on that day (what the UI sends) |
| `{status: "watched"}` | watched; date defaults to the **server's** UTC today |
| `{watched_on: "2026-07-01"}` on a watched item | moves the date |
| `{status: "want_to_watch"}` | unwatched; `watched_on` cleared |
| `{status: "want_to_watch", watched_on: <date>}` | **422** — contradictory |
| `{watched_on: <date>}` on an unwatched item | **422** — would break the invariant |
| `{watched_on: null}` on a watched item | **422** — unwatch it instead |
| any `watched_on` more than 1 day in the future | **422** — you can't have watched it yet |

The **client sends its own local today** when marking watched, so the server
never has to guess the user's timezone. The +1 day tolerance on the future check
exists precisely to absorb the gap between the client's today and the server's.

### Invites
- `POST /api/lists/{id}/invites` — create → returns `{ code, url }`
- `GET  /api/invites/{code}` — preview (list name, who invited) before accepting
- `POST /api/invites/{code}/accept` — join list (must be logged in)

### TMDB proxy
- `GET /api/tmdb/search?q=...` — returns trimmed results (id, title, year, poster_path)
- `GET /api/tmdb/movie/{tmdbId}` — full metadata for the detail page (M7): runtime,
  genres, tagline, rating, backdrop, director, top cast. **Fetched live, not
  snapshotted** — the board still renders from the DB snapshot with zero TMDB
  calls, so a TMDB outage degrades one page instead of the whole app.

### Access-control dependency (the query that matters)
```python
# "Is current_user a member of this list?" — gate on every /lists/{id}/* route
stmt = select(ListMember).where(
    ListMember.list_id == list_id,
    ListMember.user_id == current_user.id,
)
member = session.execute(stmt).scalar_one_or_none()
if member is None:
    raise HTTPException(403)
```

---

## 6. Auth flow (Google → own session)

1. React renders the Google Identity Services button → user signs in → browser
   gets a Google **ID token**.
2. React POSTs it to `/api/auth/google`.
3. FastAPI verifies the token against Google's public keys (`google-auth`),
   reads `sub` / `email` / `name` / `picture`, upserts the `users` row.
4. FastAPI issues its **own** signed session in an **httpOnly, Secure,
   SameSite=Lax** cookie. Browser JS never touches the token.
5. Subsequent requests carry the cookie automatically; a dependency validates it
   and loads `current_user`.

### Dev-login bypass
A `DEV_LOGIN=1` env flag enables a local-only route that logs in a fixed fake
user, so the list/movie UI can be built before the Google OAuth client and TMDB
key are configured. Never enabled in production.

---

## 7. Frontend (React + Vite)

- **Routes**: `/login`, `/` (my lists), `/lists/:id` (movie board),
  `/lists/:id/items/:itemId` (movie detail, M7), `/invite/:code` (accept).
- **Server state**: TanStack Query — caching + optimistic updates on status toggle.
- **Key components**: `ListBoard` (items grouped by status),
  `MovieSearchDialog` (debounced TMDB search → add), `InviteButton`
  (create + copy link), `MemberList`.
- **Posters**: build TMDB image URL from `poster_path` on the client
  (`https://image.tmdb.org/t/p/w200{poster_path}`) — public, no key needed.

### Cards vs. the detail page (M7)
The card is **deliberately minimal** — poster, title, and (if watched) the watch
date. Nothing else. The card body is a link to the detail page; the quick actions
(mark watched / unwatch / remove) live behind a `⋯` menu on the card, reusing the
same `DropdownMenu` as the list header. Everything richer — full TMDB metadata,
changing the watch date — is on the detail page.

**Dates must never be parsed with `new Date("2026-07-12")`.** That parses as UTC
midnight, so `toLocaleDateString()` renders it as the *11th* anywhere west of
Greenwich — the exact off-by-one-day bug we moved to a `DATE` column to avoid.
All conversion goes through the helpers in `types.ts` (`parseLocalDate`,
`todayISO`, `formatWatchedDate`); nothing else touches the raw string.

---

## 8. Deployment (Render + Neon)

- **Neon Postgres**: pooled connection string → `DATABASE_URL`; keep SQLAlchemy
  pool small (serverless Postgres punishes many direct connections). Handle the
  `postgresql://` → `postgresql+psycopg://` scheme rewrite in config.
- **Render Web Service** (single, paid warm instance ~$7/mo): build runs
  `vite build` then starts `uvicorn`; FastAPI mounts the static build and serves
  the API. Env: `DATABASE_URL`, `TMDB_API_KEY`, `GOOGLE_CLIENT_ID`,
  `SESSION_SECRET`.
- **Migrations**: Alembic, run on deploy.
- **`render.yaml`**: declares the service + env as infra-as-code.
- **Backups**: periodic `pg_dump` (scheduled or manual monthly) — the one thing
  that actually protects the data.

---

## 9. Implementation plan (milestones)

- **M0 — Scaffold & infra.** Monorepo (`/frontend`, `/backend`), FastAPI serving
  the Vite build, **Vite dev proxy** (`/api` → backend, so dev is single-origin),
  `render.yaml`, Neon connection + scheme handling (`pool_pre_ping`, small pool,
  pooled endpoint), Alembic baseline, health check, and the **test harness**
  (pytest + FastAPI `TestClient` against a throwaway Neon branch; Playwright
  installed). *Done when:* deploys to Render and returns `/api/health`.
- **M1 — Auth.** Google verify → upsert → signed-cookie session; `me` / `logout`;
  `DEV_LOGIN=1` bypass. *Done when:* login (real + dev) works and an authed route
  is reachable.
- **M2 — Lists + membership.** `lists` CRUD, `list_members`, access-control
  dependency, indexes. *Done when:* create/rename/delete owned lists; only see
  lists you're a member of.
- **M3 — Movies (TMDB).** Search proxy; add item (snapshot), toggle `status`
  (sets/clears `watched_at`), delete. *Done when:* search → add → toggle → remove,
  end to end.
- **M4 — Invites.** Create link, preview, accept-to-join. *Done when:* a second
  Google account opens the link and can edit.
- **M5 — Frontend polish.** Board grouped by status, optimistic toggle, search
  dialog, invite/copy button, member list, empty states, mobile layout.
- **M6 — Ship.** Real Google OAuth client + TMDB key in Render env, migrations on
  deploy, warm instance, first `pg_dump`. *Done when:* both users are on the real URL.
- **M7 — Watch dates & movie detail.** `watched_at timestamptz` → `watched_on date`
  (+ CHECK, + backfill of existing rows); PATCH accepts a date; watched section
  sorted newest-first; minimal cards with a `⋯` menu; a movie detail page with
  live TMDB metadata where the date is edited. *Done when:* you can mark a movie
  watched, open it, correct the date to the day you actually watched it, and see
  the watched list reorder.

### Out of scope for M7 (deliberately)
- **Calendar view.** Cut for implementation simplicity. The `DATE` column and the
  newest-first ordering are exactly what it would need, so it stays cheap to add.
- **Rewatches.** One watch date per movie. When this chafes it becomes a
  `watch_events` table — a real migration, not a tweak.
- **Backfilling old films you never added** (add → mark watched → fix date is the
  3-step path). Expect this to come back as a request.

---

## 10. Implementation risks

Almost all risk is in the *integration seams*, not the (thin) business logic.

| # | Risk | Likelihood | Mitigation |
|---|------|-----------|------------|
| 1 | **Auth cookies don't flow in dev** — prod is single-origin, but locally Vite (`:5173`) and FastAPI (`:8000`) are two origins, so the session cookie silently isn't sent. | High | Vite **dev proxy** (`/api` → `:8000`) so the browser sees one origin in dev too. Test the cookie path early. |
| 2 | **Neon connection staleness** — serverless Postgres closes idle connections / autosuspends; pooled connections go stale → intermittent "server closed the connection unexpectedly." | High | `pool_pre_ping=True`, small `pool_size`, Neon **pooled** endpoint, modest `pool_recycle`. |
| 3 | **SPA catch-all shadows the API** — the `index.html` fallback can swallow `/api/*` or `/assets` if route ordering is wrong. | Medium | Mount `/api` and `/assets` **before** the catch-all; test that both an API route and a deep client route resolve. |
| 4 | **Google OAuth config friction** — authorized origins, client-ID mismatch, ID-token audience/issuer verification. | Medium | The **`DEV_LOGIN` bypass** de-risks downstream milestones; verify real Google only at M1 close and M6. |
| 5 | **TMDB specifics** — v3 key vs v4 bearer token, rate limits, junk results without year disambiguation. | Medium | Pin auth style in config; return `release_year` for disambiguation; map non-200s to a clean 502. |
| 6 | **Concurrent add of same movie** — `UNIQUE(list_id, tmdb_id)` throws `IntegrityError`. | Low | Catch it, treat as idempotent (return existing item), not a 500. |
| 7 | **Migration fails on deploy** → app won't boot. | Low | Alembic as a pre-deploy step; test `upgrade head` on a fresh DB before shipping. |
| 8 | **Scope creep** (the "SaaS for two" over-build) — the biggest *schedule* risk. | Medium | Milestones are vertical slices; ship M1–M4 usable before M5 polish. |
| 9 | **(M7) `new Date("2026-07-12")` parses as UTC midnight** → `toLocaleDateString()` renders the *previous day* in any US timezone. Would put a wrong date on every card. | High | One `parseLocalDate` helper in `types.ts`; nothing else touches the raw date string. Asserted in the e2e (the card must show *today*). |
| 10 | **(M7) The data migration is the one thing the test suite can't see** — tests build the schema with `create_all`, not Alembic, so the `timestamptz → date` backfill SQL first runs against *production data*. The cast is lossy and irreversible: a wrong timezone silently shifts real watch dates back a day. | High | `pg_dump` **before** the deploy; run `alembic upgrade head` against the docker-compose Postgres with seeded watched rows first. Cast at `America/Los_Angeles`, not UTC (9pm PDT is stored as 04:00 UTC *the next day*). |

Risks **1, 2, and 3** are the ones that eat an afternoon if found late — all three are cheap to prove out in M0/M1.

## 11. Testing & success criteria

**Philosophy:** the logic is thin glue, so test at the **API boundary**
(integration tests) where the real risk lives — not a pyramid of unit tests.

- **Backend:** `pytest` + FastAPI `TestClient` against a **real Postgres**
  (throwaway **Neon branch** or local Docker PG — *not* SQLite, so `UNIQUE` /
  constraints behave like prod). Transactional fixture rolls back per test.
  - **Interim (M1–M5):** to keep momentum before a Postgres was provisioned, the
    suite ran on in-memory **SQLite** (portable model types, `create_all`).
  - **Resolved:** `docker compose` now provides a real Postgres, and the full
    suite passes against it (`TEST_DATABASE_URL=...`, see README). SQLite stays
    the fast default for the inner loop; Postgres is the prod-accurate check.
    This matters — SQLite silently ignored `ON DELETE CASCADE` and hid a real
    bug in M2 until the pragma was enabled.
- **Frontend:** minimal — **Playwright** for 2–3 critical end-to-end flows.
- **Manual / `/verify`:** drive the flow in a browser for UI-polish items not
  worth automating.

**Minimum viable suite** (what actually gets written): the M2 membership/403
tests + the M3 item-lifecycle tests + one M5 Playwright happy path. That trio
covers the only real logic (access control), the only stateful transition
(`watched_at`), and end-to-end wiring.

| Milestone | Success criteria (measurable "done") | How verified |
|-----------|--------------------------------------|--------------|
| **M0 Scaffold** | App boots; `GET /api/health` → 200; a deep client route serves the SPA; migrations apply to a fresh DB. | Smoke test on `/api/health` **and** a client route (risk #3); `alembic upgrade head` on a clean branch (risks #2, #7). |
| **M1 Auth** | Dev-login sets a cookie; `me` returns the user with the cookie and **401 without it**; logout clears it; real Google verifies once manually. | Integration: me-with-cookie=200, me-no-cookie=401, logout→401 (risk #1). One manual real-Google login. |
| **M2 Lists + membership** | Owner can CRUD lists; a **non-member gets 403** on every `/lists/{id}/*`; `GET /lists` returns only my lists. | Integration with **two seeded users**: member=200, stranger=403 across item/rename/delete/invite routes. Highest-value test. |
| **M3 Movies** | Search returns trimmed results with year; add snapshots metadata; toggling status sets/clears `watched_at`; duplicate add is idempotent. | Integration (TMDB mocked): add→GET shows snapshot; PATCH want→watched sets `watched_at` & reverse clears it; second add returns existing, not 500 (risk #6). |
| **M4 Invites** | Creating returns code+URL; preview shows list name; accepting adds caller to `list_members`; **logged-out** accept rejected. | Integration: A creates invite → B accepts → B passes the M2 membership check. One Playwright pass with a second account. |
| **M5 Frontend polish** | Board groups by status; status toggle is optimistic and reconciles; search→add works; invite link copies; usable on mobile. | **Playwright** e2e: dev-login → create list → search+add → toggle watched → open invite. Manual `/verify` for layout/empty states. |
| **M6 Ship** | Prod URL loads; real Google login works E2E; TMDB search works with the prod key; first `pg_dump` is restorable. | Manual prod smoke of the full happy path (both users) + confirm the backup restores into a scratch Neon branch. |
| **M7 Watch dates** | Marking watched stores **today** and shows it on the card; the date is editable on the detail page; watched sorts newest-first; a watched row can never have a null date (CHECK); contradictory/future dates are 422s; existing watched rows keep the right day through the migration. | Integration: PATCH matrix from §5 (each 422 case asserted); the CHECK rejects an inconsistent row. **Playwright**: mark watched → card shows today's date (guards risk #9) → detail page → change the date → list reorders. Migration: `alembic upgrade head` on seeded Postgres, assert an evening-UTC timestamp lands on the *previous* local day (risk #10). |
