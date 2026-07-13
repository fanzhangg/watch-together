// Typed API client. Requests go through the Vite dev proxy (same origin in dev,
// same origin in prod too), so the session cookie is sent automatically.

import {
  todayISO,
  type AppConfig,
  type Invite,
  type InvitePreview,
  type Item,
  type ListDetail,
  type ListSummary,
  type MovieDetail,
  type MovieSearchResult,
  type User,
} from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    ...init,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body — keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const post = (body?: unknown): RequestInit => ({
  method: "POST",
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  // --- runtime config ---
  config: () => request<AppConfig>("/api/config"),

  // --- auth ---
  me: () => request<User>("/api/auth/me"),
  devLogin: () => request<User>("/api/auth/dev-login", post()),
  googleLogin: (credential: string) =>
    request<User>("/api/auth/google", post({ credential })),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", post()),

  // --- lists ---
  getLists: () => request<ListSummary[]>("/api/lists"),
  createList: (name: string) => request<ListSummary>("/api/lists", post({ name })),
  getList: (id: string) => request<ListDetail>(`/api/lists/${id}`),
  renameList: (id: string, name: string) =>
    request<ListSummary>(`/api/lists/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),
  deleteList: (id: string) =>
    request<void>(`/api/lists/${id}`, { method: "DELETE" }),

  // --- movies in a list ---
  getItems: (listId: string) => request<Item[]>(`/api/lists/${listId}/items`),
  getItem: (listId: string, itemId: string) =>
    request<Item>(`/api/lists/${listId}/items/${itemId}`),
  addItem: (listId: string, tmdbId: number) =>
    request<Item>(`/api/lists/${listId}/items`, post({ tmdb_id: tmdbId })),
  /** Mark watched. Sends the user's LOCAL today so the server never guesses. */
  markWatched: (listId: string, itemId: string, watchedOn: string = todayISO()) =>
    request<Item>(`/api/lists/${listId}/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "watched", watched_on: watchedOn }),
    }),
  markUnwatched: (listId: string, itemId: string) =>
    request<Item>(`/api/lists/${listId}/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "want_to_watch" }),
    }),
  /** Move the watch date of an already-watched movie. */
  setWatchedOn: (listId: string, itemId: string, watchedOn: string) =>
    request<Item>(`/api/lists/${listId}/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify({ watched_on: watchedOn }),
    }),
  deleteItem: (listId: string, itemId: string) =>
    request<void>(`/api/lists/${listId}/items/${itemId}`, { method: "DELETE" }),

  // --- tmdb ---
  searchMovies: (q: string) =>
    request<MovieSearchResult[]>(`/api/tmdb/search?q=${encodeURIComponent(q)}`),
  getMovieDetail: (tmdbId: number) =>
    request<MovieDetail>(`/api/tmdb/movie/${tmdbId}`),

  // --- invites ---
  createInvite: (listId: string) =>
    request<Invite>(`/api/lists/${listId}/invites`, post({})),
  previewInvite: (code: string) => request<InvitePreview>(`/api/invites/${code}`),
  acceptInvite: (code: string) =>
    request<ListSummary>(`/api/invites/${code}/accept`, post()),
};
