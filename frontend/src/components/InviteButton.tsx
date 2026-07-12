import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";

export default function InviteButton({ listId }: { listId: string }) {
  const [copied, setCopied] = useState(false);

  const invite = useMutation({
    mutationFn: () => api.createInvite(listId),
    onSuccess: async (inv) => {
      try {
        await navigator.clipboard.writeText(inv.url);
        setCopied(true);
        setTimeout(() => setCopied(false), 2500);
      } catch {
        // Clipboard can be blocked (permissions, non-HTTPS); the link is still
        // shown below so it can be copied by hand.
      }
    },
  });

  return (
    <div>
      <button onClick={() => invite.mutate()} disabled={invite.isPending}>
        {invite.isPending ? "Creating…" : "🔗 Invite someone"}
      </button>

      {invite.error && (
        <div className="error" style={{ marginTop: "0.5rem" }}>
          {(invite.error as Error).message}
        </div>
      )}

      {invite.data && (
        <div style={{ marginTop: "0.6rem", maxWidth: 420 }}>
          <div className="muted" style={{ fontSize: "0.82rem", marginBottom: "0.25rem" }}>
            {copied ? "✓ Link copied — send it to them" : "Share this link:"}
          </div>
          <input
            type="text"
            readOnly
            value={invite.data.url}
            onFocus={(e) => e.currentTarget.select()}
          />
        </div>
      )}
    </div>
  );
}
