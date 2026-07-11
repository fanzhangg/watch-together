// Tiny API client. Requests go through the Vite dev proxy (same origin), so the
// session cookie is sent automatically; `credentials: "include"` is belt-and-
// suspenders in case the frontend is ever served from a different origin.

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { credentials: "include", ...init });
  if (!res.ok) throw new Error(`${init?.method ?? "GET"} ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  me: () => request<User>("/api/auth/me"),
  devLogin: () => request<User>("/api/auth/dev-login", { method: "POST" }),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
};
