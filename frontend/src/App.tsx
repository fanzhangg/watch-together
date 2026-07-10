import { useQuery } from "@tanstack/react-query";

// M0 placeholder: proves the frontend can reach the backend through the dev
// proxy (/api -> FastAPI). Real routes (login, lists, board, invite) arrive in
// later milestones per docs/design.md.
async function fetchHealth(): Promise<{ status: string }> {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error(`health check failed: ${res.status}`);
  return res.json();
}

export default function App() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
  });

  const backend = isLoading
    ? "checking…"
    : isError
      ? "unreachable"
      : (data?.status ?? "unknown");

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <h1>🎬 Watch Together</h1>
      <p>Scaffold is running (M0).</p>
      <p>
        Backend health: <strong>{backend}</strong>
      </p>
    </main>
  );
}
