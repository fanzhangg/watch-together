// Typed API client. Requests go through the Vite dev proxy (same origin in dev,
// same origin in prod too), so the session cookie is sent automatically.

import type {
  Invite,
  InvitePreview,
  Item,
  ListDetail,
  ListSummary,
  MovieSearchResult,
  Status,
  User,
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
  addItem: (listId: string, tmdbId: number) =>
    request<Item>(`/api/lists/${listId}/items`, post({ tmdb_id: tmdbId })),
  setItemStatus: (listId: string, itemId: string, status: Status) =>
    request<Item>(`/api/lists/${listId}/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  deleteItem: (listId: string, itemId: string) =>
    request<void>(`/api/lists/${listId}/items/${itemId}`, { method: "DELETE" }),

  // --- tmdb ---
  searchMovies: (q: string) =>
    request<MovieSearchResult[]>(`/api/tmdb/search?q=${encodeURIComponent(q)}`),

  // --- invites ---
  createInvite: (listId: string) =>
    request<Invite>(`/api/lists/${listId}/invites`, post({})),
  previewInvite: (code: string) => request<InvitePreview>(`/api/invites/${code}`),
  acceptInvite: (code: string) =>
    request<ListSummary>(`/api/invites/${code}/accept`, post()),
};
