import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
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
  const {
    data: config,
    isPending: configPending,
    error: configError,
  } = useConfig();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  // Send people back where they were headed (e.g. an invite link).
  const next = (location.state as LocationState | null)?.from?.pathname ?? "/";

  const onSignedIn = (u: User) => {
    qc.setQueryData(["me"], u);
    navigate(next, { replace: true });
  };

  // Naming the dev user is what makes a second browser profile a second
  // PERSON — without it every profile signs in as the same one and nothing
  // multi-user (shared lists, invites, someone else's verdict) can be seen.
  const [devName, setDevName] = useState("");
  const devLogin = useMutation({
    mutationFn: () => api.devLogin(devName.trim() || undefined),
    onSuccess: onSignedIn,
  });
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
            <input
              type="text"
              value={devName}
              maxLength={40}
              placeholder="Sign in as… (optional)"
              aria-label="Dev login name"
              onChange={(e) => setDevName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && devLogin.mutate()}
            />
            <button
              className={showGoogle ? "" : "primary"}
              onClick={() => devLogin.mutate()}
              disabled={devLogin.isPending}
            >
              {devLogin.isPending
                ? "Signing in…"
                : devName.trim()
                  ? `Dev login as ${devName.trim()}`
                  : "Dev login"}
            </button>
            <p style={{ fontSize: "0.8rem" }} className="muted">
              Local development only. Give a name to sign in as someone else —
              use a second browser profile to be two people at once.
            </p>
          </>
        )}

        {/* A failed /api/config request leaves `config` undefined, which looks
            exactly like "this deployment offers no sign-in". Say which it is:
            in dev the answer is almost always that the backend isn't running,
            and blaming GOOGLE_CLIENT_ID sends you off to fix the wrong thing. */}
        {configError && (
          <div className="error">
            Can’t reach the server.
            {import.meta.env.DEV
              ? " Is the backend running on port 8000? (cd backend && uvicorn app.main:app --reload --port 8000)"
              : " Please try again in a moment."}
          </div>
        )}

        {!configError && !showGoogle && !showDevLogin && (
          <div className="error">
            No sign-in method is configured. Set <code>GOOGLE_CLIENT_ID</code> on
            the server.
          </div>
        )}
      </div>
    </div>
  );
}
