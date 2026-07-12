import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useMe } from "../auth";
import type { InvitePreview } from "../types";

export default function InvitePage() {
  const { code = "" } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: user, isPending: userPending } = useMe();

  // Public preview — you can see what you're joining before signing in.
  const { data: preview, isPending, error } = useQuery<InvitePreview>({
    queryKey: ["invite", code],
    queryFn: () => api.previewInvite(code),
    retry: false,
  });

  const accept = useMutation({
    mutationFn: () => api.acceptInvite(code),
    onSuccess: (list) => {
      qc.invalidateQueries({ queryKey: ["lists"] });
      navigate(`/lists/${list.id}`, { replace: true });
    },
  });

  if (isPending || userPending) {
    return <p className="center-card muted">Loading invite…</p>;
  }

  if (error) {
    return (
      <div className="center-card">
        <h1>Invite not available</h1>
        <p>{(error as Error).message}</p>
        <div className="stack">
          <Link to="/">
            <button style={{ width: "100%" }}>Go to your lists</button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="center-card">
      <h1>🎬 You’re invited</h1>
      <p>
        <strong>{preview!.invited_by}</strong> invited you to share the list
      </p>
      <h2 style={{ marginTop: "0.75rem" }}>{preview!.list_name}</h2>

      <div className="stack">
        {accept.error && <div className="error">{(accept.error as Error).message}</div>}

        {user ? (
          <button
            className="primary"
            onClick={() => accept.mutate()}
            disabled={accept.isPending}
          >
            {accept.isPending ? "Joining…" : "Join this list"}
          </button>
        ) : (
          <>
            <p>Sign in to join — you’ll come straight back here.</p>
            <Link to="/login" state={{ from: { pathname: `/invite/${code}` } }}>
              <button className="primary" style={{ width: "100%" }}>
                Sign in to join
              </button>
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
