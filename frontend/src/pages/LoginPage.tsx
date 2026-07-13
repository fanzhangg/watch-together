import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useConfig, useMe } from "../auth";
import GoogleSignInButton from "../components/GoogleSignInButton";
import type { User } from "../types";

interface LocationState {
  from?: { pathname: string };
}

export default function LoginPage() {
  const { data: user, isPending: userPending } = useMe();
  const { data: config, isPending: configPending } = useConfig();
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

  if (userPending || configPending) {
    return <p className="container muted">Loading…</p>;
  }
  if (user) return <Navigate to={next} replace />;

  const error = googleLogin.error ?? devLogin.error;
  // Only offer what this deployment actually supports: in production DEV_LOGIN
  // is off, so the dev button must not appear (it would 404).
  const showGoogle = !!config?.google_client_id;
  const showDevLogin = !!config?.dev_login;

  return (
    <div className="center-card">
      <h1>🎬 Watch Together</h1>
      <p>Keep a movie list with someone you like.</p>

      <div className="stack">
        {error && <div className="error">{(error as Error).message}</div>}

        {showGoogle && (
          <GoogleSignInButton
            clientId={config!.google_client_id}
            onCredential={(c) => googleLogin.mutate(c)}
          />
        )}

        {showGoogle && showDevLogin && <div className="divider">or</div>}

        {showDevLogin && (
          <>
            <button
              className={showGoogle ? "" : "primary"}
              onClick={() => devLogin.mutate()}
              disabled={devLogin.isPending}
            >
              {devLogin.isPending ? "Signing in…" : "Dev login"}
            </button>
            <p style={{ fontSize: "0.8rem" }} className="muted">
              Local development only.
            </p>
          </>
        )}

        {!showGoogle && !showDevLogin && (
          <div className="error">
            No sign-in method is configured. Set <code>GOOGLE_CLIENT_ID</code> on
            the server.
          </div>
        )}
      </div>
    </div>
  );
}
