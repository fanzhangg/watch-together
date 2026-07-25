export type Status = "want_to_watch" | "watched";

/** Runtime config from the backend — which sign-in methods this deployment has. */
export interface AppConfig {
  google_client_id: string | null;
  dev_login: boolean;
}

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
}

export interface Member {
  user: User;
  role: "owner" | "member";
}

export interface ListSummary {
  id: string;
  name: string;
  owner_id: string;
  created_at: string;
  role: "owner" | "member";
}

export interface ListDetail extends ListSummary {
  members: Member[];
}

/** Thumbs up or thumbs down. "No opinion" is the absence of a Rating, not a 0. */
export type RatingValue = 1 | -1;

/**
 * One member's verdict on one movie **in this list**. The same film in another
 * list carries its own, separate verdicts.
 *
 * Carries a bare `user_id`: every page that renders these has already loaded
 * the list's members, so the name and avatar come from there.
 */
export interface Rating {
  user_id: string;
  value: RatingValue;
}

/** What a write returns — no user_id, since it can only ever be mine. */
export interface MyRating {
  item_id: string;
  value: RatingValue;
}

export interface Item {
  id: string;
  tmdb_id: number;
  title: string;
  release_year: number | null;
  poster_path: string | null;
  overview: string | null;
  status: Status;
  added_by: string;
  /** "2026-07-12". Null iff status is want_to_watch — the DB guarantees it. */
  watched_on: string | null;
  created_at: string;
  /**
   * Verdicts from this list's members only. Independent of `status`: an
   * unwatched movie can carry them, and un-watching clears none.
   */
  ratings: Rating[];
}

export interface MovieSearchResult {
  tmdb_id: number;
  title: string;
  release_year: number | null;
  poster_path: string | null;
  overview: string | null;
}

/** Live TMDB metadata for the detail page — richer than the DB snapshot. */
export interface MovieDetail extends MovieSearchResult {
  backdrop_path: string | null;
  tagline: string | null;
  runtime: number | null;
  genres: string[];
  director: string | null;
  cast: string[];
}

export interface Invite {
  code: string;
  url: string;
  list_id: string;
  expires_at: string | null;
}

export interface InvitePreview {
  code: string;
  list_name: string;
  invited_by: string;
  expires_at: string | null;
}

/** Posters are public on TMDB's CDN — no API key needed client-side. */
export function posterUrl(path: string | null, size = "w342"): string | null {
  return path ? `https://image.tmdb.org/t/p/${size}${path}` : null;
}

// --- Watch dates ---------------------------------------------------------
// A watch date is a plain calendar day ("2026-07-12"), never an instant.
//
// NEVER write `new Date("2026-07-12")`: a bare date string is parsed as UTC
// midnight, which toLocaleDateString() then renders as the 11th anywhere west
// of Greenwich — i.e. wrong for every user we have. These three helpers are the
// only places that convert, so there is exactly one place to get it right.

/** "2026-07-12" -> a Date at LOCAL midnight on that day. */
export function parseLocalDate(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

/** The user's own today, as the API's date string. */
export function todayISO(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** "2026-07-12" -> "July 2026" — the sub-header the watched board groups under. */
export function formatWatchMonth(iso: string): string {
  return parseLocalDate(iso).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
}

/** "2026-07-12" -> "12 Jul 2026" — the exact day, for the detail-rich list view.
 *  The poster grid deliberately shows only the month; a row has space to say
 *  precisely when. */
export function formatWatchDate(iso: string): string {
  return parseLocalDate(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/**
 * A `created_at` timestamp from the API -> a local Date.
 *
 * Unlike a watch date, this one really IS an instant, so `new Date()` is the
 * right tool — the warning above is about bare date strings. The catch is
 * different: SQLite (local dev) round-trips these WITHOUT a timezone suffix,
 * and a bare "2026-07-25T21:30:00" is parsed as local time rather than UTC,
 * which moves an evening addition onto the wrong day. Postgres sends the
 * offset; we supply it when it's missing, exactly as the backend does when
 * reading invite expiry.
 */
export function parseTimestamp(iso: string): Date {
  const hasZone = /([Zz]|[+-]\d{2}:?\d{2})$/.test(iso);
  return new Date(hasZone ? iso : `${iso}Z`);
}

/** "2026-07-25T21:30:00Z" -> "25 Jul 2026" — the day a movie joined the list. */
export function formatAddedDate(iso: string): string {
  return parseTimestamp(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
