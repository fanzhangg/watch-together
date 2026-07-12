import { useEffect, useRef } from "react";

// Minimal shape of the Google Identity Services API we use.
interface GoogleIdentity {
  accounts: {
    id: {
      initialize(opts: {
        client_id: string;
        callback: (res: { credential: string }) => void;
      }): void;
      renderButton(el: HTMLElement, opts: Record<string, unknown>): void;
    };
  };
}
declare global {
  interface Window {
    google?: GoogleIdentity;
  }
}

const GSI_SRC = "https://accounts.google.com/gsi/client";

function loadGsi(): Promise<void> {
  if (window.google) return Promise.resolve();
  const existing = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SRC}"]`);
  if (existing) {
    return new Promise((resolve) => existing.addEventListener("load", () => resolve()));
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = GSI_SRC;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Google sign-in"));
    document.head.appendChild(script);
  });
}

/**
 * Renders the official "Sign in with Google" button.
 *
 * Only shown when VITE_GOOGLE_CLIENT_ID is configured — until then the app is
 * fully usable via dev login, so an unconfigured OAuth client never blocks work.
 */
export default function GoogleSignInButton({
  onCredential,
}: {
  onCredential: (credential: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

  useEffect(() => {
    if (!clientId || !ref.current) return;
    let cancelled = false;

    loadGsi()
      .then(() => {
        if (cancelled || !window.google || !ref.current) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: (res) => onCredential(res.credential),
        });
        window.google.accounts.id.renderButton(ref.current, {
          theme: "outline",
          size: "large",
          width: 260,
        });
      })
      .catch(() => {
        /* button just won't render; dev login still works */
      });

    return () => {
      cancelled = true;
    };
  }, [clientId, onCredential]);

  if (!clientId) return null;
  return <div ref={ref} style={{ display: "flex", justifyContent: "center" }} />;
}
