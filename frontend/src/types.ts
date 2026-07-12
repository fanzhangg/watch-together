export type Status = "want_to_watch" | "watched";

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
  watched_at: string | null;
  created_at: string;
}

export interface MovieSearchResult {
  tmdb_id: number;
  title: string;
  release_year: number | null;
  poster_path: string | null;
  overview: string | null;
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
