import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useMe } from "../auth";
import GoogleSignInButton from "../components/GoogleSignInButton";
import type { User } from "../types";

interface LocationState {
  from?: { pathname: string };
}

export default function LoginPage() {
  const { data: user, isPending } = useMe();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  // Send people back where they were headed (e.g. an invite link).
  const next = (location.state as LocationState | null)?.from?.pathname ?? "/";

  const onSignedIn = (u: User) => {
    qc.setQueryData(["me"], u);
    navigate(next, { replace: true });
  };

  const devLogin = useMutation({ mutationFn: api.devLogin, onSuccess: onSignedIn });
  const googleLogin = useMutation({
    mutationFn: api.googleLogin,
    onSuccess: onSignedIn,
  });

  if (isPending) return <p className="container muted">Loading…</p>;
  if (user) return <Navigate to={next} replace />;

  const error = googleLogin.error ?? devLogin.error;

  return (
    <div className="center-card">
      <h1>🎬 Watch Together</h1>
      <p>Keep a movie list with someone you like.</p>

      <div className="stack">
        {error && <div className="error">{(error as Error).message}</div>}

        <GoogleSignInButton onCredential={(c) => googleLogin.mutate(c)} />

        {import.meta.env.VITE_GOOGLE_CLIENT_ID && <div className="divider">or</div>}

        <button
          className="primary"
          onClick={() => devLogin.mutate()}
          disabled={devLogin.isPending}
        >
          {devLogin.isPending ? "Signing in…" : "Dev login"}
        </button>
        <p style={{ fontSize: "0.8rem" }}>
          Dev login works when the backend runs with <code>DEV_LOGIN=true</code>.
        </p>
      </div>
    </div>
  );
}
