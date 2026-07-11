import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type User } from "./api";

// M1 placeholder UI: shows auth state and exercises the dev-login / logout
// flow end to end. The real Google sign-in button and app routes arrive in
// later milestones per docs/design.md.
export default function App() {
  const qc = useQueryClient();

  const { data: user, isLoading } = useQuery<User | null>({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await api.me();
      } catch {
        return null; // 401 -> not logged in
      }
    },
  });

  const login = useMutation({
    mutationFn: api.devLogin,
    onSuccess: (u) => qc.setQueryData(["me"], u),
  });
  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => qc.setQueryData(["me"], null),
  });

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <h1>🎬 Watch Together</h1>
      {isLoading ? (
        <p>Loading…</p>
      ) : user ? (
        <>
          <p>
            Signed in as <strong>{user.display_name ?? user.email}</strong> (
            {user.email})
          </p>
          <button onClick={() => logout.mutate()} disabled={logout.isPending}>
            Log out
          </button>
        </>
      ) : (
        <>
          <p>You are not signed in.</p>
          <button onClick={() => login.mutate()} disabled={login.isPending}>
            Dev login
          </button>
          <p style={{ color: "#888", fontSize: "0.9rem" }}>
            (Dev login works when the backend runs with <code>DEV_LOGIN=true</code>.
            Google sign-in comes later.)
          </p>
        </>
      )}
    </main>
  );
}
