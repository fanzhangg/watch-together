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
  vote_average: number | null;
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

/** "2026-07-12" -> "Sun, Jul 12, 2026" */
export function formatWatchedDate(iso: string): string {
  return parseLocalDate(iso).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
