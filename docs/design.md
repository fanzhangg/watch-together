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
- Ratings / reviews / notes on movies — **future scope** (thumbs up/down arrives
  in **M8**, see §12; written reviews and notes remain out of scope).
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

item_ratings                        -- M8: one member's thumb on one movie
  list_item_id  uuid -> list_items.id  on delete cascade
  user_id       uuid -> users.id       on delete cascade
  value         smallint            -- +1 up | -1 down
  rated_at      timestamptz
  PRIMARY KEY (list_item_id, user_id)
  CHECK (value IN (-1, 1))
```

### Indexes (up front)
- `list_members(user_id)` — "my lists" lookup
- `list_items(list_id)` — board loads
- `list_items(list_id, watched_on)` — chronological watched ordering (M7)
- `UNIQUE(list_id, tmdb_id)` and `invites.code` uniques cover the rest
- `item_ratings` needs none of its own (M8): reads are item-first, and
  `list_item_id` leads the primary key

### Notes
- TMDB fields are **snapshotted** into `list_items`; rendering needs no TMDB call.
- **`watched_on` is a `DATE`, not a timestamp** (M7). "We watched it on the 12th"
  is the same fact in every timezone; a timestamp forces every reader to pick one
  and gets the day wrong for evening viewings. The **CHECK constraint makes
  "watched" and "has a date" the same thing** — there is no watched-but-undated
  state to branch on anywhere in the code.
- **A verdict is scoped to the list item** (M8), so it belongs to the list it was
  given in — the same film in another list carries its own. That FK is what makes
  the privacy property structural rather than a filter someone has to remember,
  and it means removing a movie takes the opinions about it along. Nothing ties
  a verdict to `status`; see §12.
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
- `PUT /api/lists/{id}/items/{itemId}/rating` — body: `{ value: 1 | -1 }` → my
  thumb on this movie (M8). Upsert; sets only the caller's.
- `DELETE /api/lists/{id}/items/{itemId}/rating` — take my thumb back;
  `204` even if I hadn't rated it

Item responses carry a `ratings: [{user_id, value}]` array (M8) — this list's
members only, and independent of `status`. Full spec in §12.

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
`todayISO`, `formatWatchMonth`); nothing else touches the raw string.

The watched board carries no per-card date at all. It is split into month runs
under `.month-title` sub-headers ("July 2026"), newest first — the month is how
you actually look something up, and it says once what a stamp on every poster
was saying twenty times over the artwork. The exact day stays on the detail
page, where it's editable. Grouping keys off `watched_on.slice(0, 7)` rather
than a `Date`: `"2026-07"` sorts as a string and can't drift across a timezone.

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
- **M8 — Ratings (👍 / 👎).** An `item_ratings` table keyed on `(list_item_id,
  user_id)` — a verdict belongs to a *member, within one list*, and is **fully
  decoupled from the shared watch status**, so nothing spans the two tables and
  no existing table changes. `PUT`/`DELETE /api/lists/{id}/items/{itemId}/rating`;
  items carry a `ratings` array; the control lives on the detail page. *Done
  when:* both members can thumb any movie in their shared list, each sees the
  other's verdict attributed, tapping your own verdict again clears it, watching
  or un-watching changes no verdict, and a verdict given in one list appears in
  no other. Full spec in **§12**.

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
| **M8 Ratings** | A member can thumb any movie in a shared list and take it back; a verdict stays in the list it was given in; watching/un-watching changes no verdict; removing the movie removes them. | Integration: upsert/flip/clear leaves exactly one row; the **isolation test** (the same film in two lists rates separately, and a verdict never reaches someone outside the list); the decoupling asserted directly (PATCH status → verdicts unchanged); both cascades on real Postgres. **Playwright**: open a movie → 👍 → reopen → 👍 again → cleared. |

---

## 12. M8 — Ratings (thumbs up / thumbs down)

Each member gives a movie one of two verdicts — 👍 or 👎 — and sees what the
others said. Deliberately two values: the question is "would you watch it again
with me", which a 5-star scale answers worse, not better.

**This is a social feature for a small group, not a rating system.** The unit of
value is *"Fang gave this a 👎"* — a person, a gesture, someone you'll talk to
about it — not a score. Everything downstream follows from that: verdicts are
**attributed by avatar rather than aggregated into a number**, no average is ever
computed or displayed, and the design optimises for reading someone else's
reaction at a glance, not for measuring a film. When a choice comes up, the
social reading wins.

### The shape: two independent facts, both local to the list

| Fact | Belongs to | Key | Who can write it |
|---|---|---|---|
| **Watch status** (M3/M7) | the **list** — "*we* watched it on the 12th" | `list_items.id` | any member |
| **Verdict** (M8) | a **member, within this list** — "*I* liked it" | `(list_item_id, user_id)` | that member, nobody else |

Two independence claims, and the milestone rests on both:

**Nothing ties a verdict to the watch status.** You may rate a movie nobody has
marked watched; un-watching one leaves every verdict untouched. There is no
invariant spanning the two tables — earlier drafts tried to couple them ("rate
only what you've watched") and every version produced either a state the schema
couldn't express or a case where one member's toggle destroyed another
member's data.

**Nothing ties a verdict to the same film in another list.** A thumb is aimed at
the people in *this* list, so it stays in it. Rate the same movie in two lists
and those are two separate remarks — the same thing said in two rooms, not one
statement contradicting itself.

Three consequences fall out, all wanted:

- **Every fact has exactly one writer**, so a member's action can never
  invalidate another member's data.
- **Privacy is structural, not a convention.** The FK points into `list_items`,
  which carries `list_id`, which every route already gates on membership. A
  verdict cannot physically reach outside its list, whatever a future query gets
  wrong.
- **M8 modifies no existing table.** One new table, one migration, no change to
  `list_items`, the PATCH semantics in §5, or M7's CHECK constraint.

### What a thumb means

A thumb is a **social gesture** before it's a data point, and people give it
whether or not they've seen the film. So the verdict carries two readings, and
**the item's watch status picks which one**:

| Status | 👍 means |
|---|---|
| `want_to_watch` | *"I'm keen — let's pick this one."* An anticipation signal. |
| `watched` | *"I liked it."* A genuine verdict. |

This is deliberate, and it's why the control appears everywhere. The context a
thumb is given in already says which kind it is, so the app stores one value and
lets the surrounding status disambiguate — rather than splitting one gesture
into two controls nobody asked for. The control's prompt changes with the status
(*"Keen to watch it?"* / *"How was it?"*) so the convention is visible in the
product, not just in this document.

**The wrinkle: the reading flips underneath a stored row.** 👍 a film you're keen
on, watch it together, hate it — the row hasn't changed, but it now reads as
"liked it", a verdict you never gave. Nothing is corrupt; the *interpretation*
moved when the status did.

Two cheap answers, neither required for M8:

- Expect people to re-tap after watching. In a two-person list, they will.
- Or **infer which side of the watch a verdict came from** — `rated_at` against
  the item's `watched_on`, both already stored, no schema change — and label it
  ("Fang 👍 *before watching*"). That reads honestly and prompts the re-tap.
  Approximate at the day boundary, since `watched_on` is a DATE by design (§4):
  good enough for a UI hint, not for a rule.

### 12.1 Data model

```
item_ratings
  list_item_id  uuid -> list_items.id  ON DELETE CASCADE
  user_id       uuid -> users.id       ON DELETE CASCADE
  value         smallint               -- +1 up | -1 down; no 0, no null
  rated_at      timestamptz            -- set on insert, bumped on flip
  PRIMARY KEY (list_item_id, user_id)
  CHECK (value IN (-1, 1))
```

**No secondary index.** Every read is item-first ("verdicts on these 40
movies"), so `list_item_id` leads the primary key and its index already serves
them.

- **The verdict dies with the movie.** Remove a film from the list and the
  opinions about it go too; re-adding it later is a clean slate rather than an
  ambush by a thumb you'd forgotten giving. Delete the list, same. Delete a
  *user*, same.
- **`value` is `smallint`, not a boolean.** A boolean cannot grow a third state
  and reads worse at the call site (`value == 1` vs `is_up == True`); ±1 also
  sums directly if an aggregate is ever wanted.
- **Un-rating deletes the row.** Three states — up, down, none — with "none" as
  absence rather than a null `value`, so the CHECK stays total.
- **`rated_at` earns its place by being unbackfillable.** Nothing reads it in
  M8; if it isn't written now, "what did we think of this last year" is
  unanswerable forever. It's also what the *before/after watching* label above
  would need.

### 12.2 Who sees whose verdict

Members of the list the verdict was given in, and nobody else. That isn't a
filter anyone has to remember — **it's the foreign key**. `item_ratings` points
at a `list_item`, which carries a `list_id`, which every `/api/lists/{id}/*`
route already gates through `require_list_member`. A verdict recorded in one
list is not reachable from another even if every `WHERE` clause in the codebase
were wrong.

Reads still go through one place, `crud.ratings_for_list(db, list_id,
item_ids=None)`, for two lesser reasons: it orders verdicts by the raters'
`joined_at` so they appear in a stable order every render rather than whatever
the database returns, and it drops anyone no longer in the list. One query for a
whole board, never one per item; `item_ids` narrows it for the single-item
route.

The residual, small and worth naming: **a new member sees verdicts recorded
before they joined.** That's consistent with how lists already work — joining
shows you the items and the watch dates too — and unlike the global-key design
it cannot reach back into lists they'll never be part of.

### 12.3 API surface

| Route | Body | Result |
|---|---|---|
| `PUT /api/lists/{listId}/items/{itemId}/rating` | `{"value": 1}` or `{"value": -1}` | Upsert my verdict on that item → `200` with `{item_id, value}`. Idempotent; flipping 👍→👎 updates the row, never inserts a second. |
| `DELETE /api/lists/{listId}/items/{itemId}/rating` | — | `204`. Clears my verdict. **Also `204` when I hadn't rated it** — the client can't always know, and "it isn't rated" is the requested end state either way. |
| bad value (`0`, `2`, `"up"`) | | `422` — the CHECK expressed in Pydantic as `Literal[1, -1]`. The only rating-specific 422 in the milestone. |
| not a member / no session | | `403` / `401`, from the existing dependency. |

Both routes clear or set **only the caller's** verdict; there is no path by
which one member writes another's.

`ItemOut` gains one field, so both `GET /lists/{id}/items` and
`GET /lists/{id}/items/{itemId}` carry verdicts:

```jsonc
{ "id": "...", "tmdb_id": 693134, "title": "Dune: Part Two", "status": "watched",
  "watched_on": "2026-07-12",
  "ratings": [ {"user_id": "…fang", "value": 1}, {"user_id": "…you", "value": -1} ] }
```

- **`user_id` only — no nested user objects.** Both `ListPage` and
  `MovieDetailPage` already fetch `getList(id)` for `members` and already render
  avatars, so the client has the map. Embedding names per item would repeat
  every member across every card for nothing.
- **No separate `my_rating` field.** The caller is always a member of the list,
  so their own verdict is already in the array; a second copy is a second thing
  to keep in sync.
- `ratings` is **not** a lazy relationship — that would issue a query per card
  on the board. One `ratings_for_list` call is stitched onto the items in the
  router.

**Upsert has no portable form.** SQLAlchemy offers no dialect-neutral
`ON CONFLICT`, and this suite runs on both Postgres and SQLite. Use
SELECT-then-INSERT/UPDATE with an `IntegrityError` catch — the same shape as the
M3 duplicate-add path (risk #6) — not dialect branching. Re-sending the verdict
you already hold is a no-op that does **not** move `rated_at`: the opinion
didn't change, so neither did when you formed it.

### 12.4 Frontend

Verdicts surface at **two levels**, and the split is what keeps the poster card
intact:

- **The detail page** — where you form and change your own opinion, so the
  buttons carry the voters' **faces**: 👍 followed by everyone who liked it.
- **The board's list view** — a row per movie carrying the state the grid has no
  room for: the exact watch date, and the same buttons carrying a **count**
  instead. This is how you *find out* someone reacted without opening 40 movies.

**The control and the tally are one element**, not a widget beside a widget. An
earlier build had a read-only verdict strip next to the buttons that changed it,
which stated the same fact twice and put your own thumb on screen in two places
at once. Folding the count into the button removed both problems, and every row
is rateable — watched or not, since a thumb means something either way.

The **poster grid is deliberately untouched**. It stays a visual index — artwork
and nothing else — which is what it's good at, and the earlier idea of squeezing
a verdict strip onto a 150px poster is dropped rather than deferred. A toggle in
the list header switches between the two; the choice is a viewing preference, so
it lives in `localStorage`, not on the server.

**The list view is the default.** It's the one that answers questions — when did
we watch this, what did we think, has the other person weighed in — while the
grid mostly shows you what's there. Only an explicit switch to `grid` opts out,
so a member who has never touched the toggle lands on the richer view.

| File | Change |
|---|---|
| `types.ts` | `RatingValue = 1 \| -1`; `Rating {user_id, value}`; `MyRating {item_id, value}`; `Item.ratings: Rating[]`; `formatWatchDate` (the exact day, vs the grid's month) |
| `api.ts` | `setRating(listId, itemId, value)`, `clearRating(listId, itemId)` |
| `ratings.ts` | **new** — `useRating` (optimistic on both the item *and* board caches) + `myRating`, so every place you can rate behaves identically |
| `components/RatingButtons.tsx` | **new** — the 👍 / 👎 pair. **The button is also the tally**: `show="count"` for rows ("👍 2"), `show="who"` for the detail page (the voters' avatars, overlapped). |
| `components/MovieRow.tsx` | **new** — the list view's row: poster thumb, title, watch date, the rating pills, and the eye button while it's still unwatched |
| `MovieDetailPage.tsx` | Renders `RatingControl`. **Always available** — no status condition. |
| `ListPage.tsx` | Grid/list toggle, persisted; rows replace the month-grouped grids in list view. |
| `MovieCard.tsx` | **Unchanged.** The poster stays a poster. |

- **Tapping your current verdict clears it** (👍 → 👍 = none); tapping the other
  one flips it. Three states, one control.
- **Optimistic, matching the existing watched toggle** — mutate the react-query
  cache, revert on error. The optimistic write replaces only your own entry;
  everyone else's is left exactly as fetched. Both `["items", listId]` and
  `["item", listId, itemId]` are invalidated on settle.
- Because a verdict is local to its list, **no other cached board can go stale**
  from a write here.

### 12.5 Migration

`0007_item_ratings.py` — create table with both cascades and the CHECK. **No
backfill, no data migration, nothing touched that already exists.** Unlike M7
(risk #10) this is additive and reversible: `downgrade()` is a single
`drop_table`.

### 12.6 Tests

Backend (`tests/test_ratings.py`):

| Assertion | Why it exists |
|---|---|
| `PUT` creates; `PUT` the other value flips it — still exactly one row | The upsert is the whole write path |
| `DELETE` clears; `DELETE` again → `204` | Idempotence is a promise, not an accident |
| `0`, `2`, `-2`, `"up"`, `null` → `422`; non-member → `403`; no session → `401` | The value domain and the auth boundary |
| **Alice+Bob share a list; Carol has the same film in her own. Carol sees only her own verdict, and Alice sees only hers and Bob's** | The isolation rule, end to end |
| **The same film in two of your own lists is rated separately** — two rows, and rating it in one shows nothing in the other | The scoping stated as behaviour, not just as a schema shape |
| The board carries every item's verdicts in one response | Guards the per-card N+1 |
| Rating an unwatched item is allowed; watching, then un-watching, changes nobody's verdict | The decoupling, asserted rather than assumed |
| Removing the movie deletes its verdicts; re-adding it is a clean slate | The cascade, and the ambush that can no longer happen |
| Deleting the list, or the user, removes their verdicts | Both cascades — SQLite silently ignored `ON DELETE CASCADE` in M2, so this is worth stating |

Run against **Postgres**, not just SQLite — the CHECK and the cascades are the
point (see §11).

Playwright — extend the happy path: open a movie → 👍 → reopen → 👍 again →
cleared; then switch the board to list view and assert the verdict shows there.

### 12.7 Done when

Both members can thumb any movie in their shared list from its detail page, each
sees the other's verdict attributed by avatar, tapping your own verdict again
clears it, marking a movie watched or un-watched changes no verdict, and a
verdict given in one list appears in no other.

### 12.8 Open UI questions (deferred, by decision)

The data model is settled and the prototype is built; these are pixel-level.
Recorded so they get chosen rather than defaulted.

1. **Where the control sits on the detail page.** Currently below the watch
   control because there was room — not because they belong together.
2. **Prompt a re-rate when a keen film becomes a watched one?** Marking watched
   flips how existing verdicts read (see *What a thumb means*). The transition is
   the natural moment to nudge, if it's worth the interruption.
3. **Whether a verdict arriving deserves an actual signal.** The list view means
   you can *see* everyone's thumbs by switching views instead of opening 40
   movies — but nothing tells you a new one landed. A notification, an unread
   dot, or an activity feed are all still absent, and for two people who talk
   daily that may stay the right answer.
4. **Whose silence it is, is invisible.** A count tells you *how many* voted, not
   who hasn't — "Fang hasn't rated this yet" and "Fang had no opinion" read the
   same. The detail page's avatars answer it; a row doesn't. A held slot per
   member was tried and rejected: it put an empty widget on every unrated movie,
   and most movies are unrated.
5. **Naming** — "rating" vs "verdict" in the copy, plus the collision with
   TMDB's own audience score if that's ever surfaced (§5 says the M7 fetch
   includes it).
6. **Accessibility beyond the basics.** The buttons carry `aria-pressed` and
   `aria-label`, and every verdict is stated in words for screen readers
   ("Fang: thumbs up" / "Fang hasn't rated this"), but emoji-vs-icon and
   distinguishability without colour are unresolved.
7. **The list view's own polish** — row density, whether the watched section
   should still carry month headers there (it doesn't; each row states its exact
   date), and how the toggle behaves on a narrow screen.

**Resolved by the two-level design:** where a verdict goes on the poster card.
It doesn't. The card is a bare poster — no title, no date, no text region, ~150px
wide with the eye button already in the corner — so a strip would have meant
overlaying artwork or bolting on chrome, and a read-only thumb inside the card's
`<Link>` would navigate when tapped. The list view carries that weight instead,
and the grid keeps doing the one thing it's good at.

### Out of scope for M8 (deliberately)

- **Sorting or filtering the board by verdict** ("show the ones we both liked").
  Cheap later — the data is there — but it's a new UI surface.
- **Agreement stats** ("you two agree 71% of the time") and **any aggregate
  score**. Not merely deferred — this is the rating-site framing the opening
  paragraph rules out. A number replaces the person, and the person is the point.
- **Verdicts in the search dialog** ("you rated this 👎 in 2024 — still adding
  it?"). Scoping verdicts to a list puts this out of reach structurally, not
  just out of scope: there is no per-user film history to query. That is the
  price of the isolation, and it was paid knowingly.
- **Written notes or reviews.** Still out of scope, as in §1.
