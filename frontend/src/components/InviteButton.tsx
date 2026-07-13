import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import Modal from "./Modal";

export default function InviteButton({
  listId,
  listName,
}: {
  listId: string;
  listName?: string;
}) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const invite = useMutation({ mutationFn: () => api.createInvite(listId) });

  const openDialog = () => {
    setOpen(true);
    setCopied(false);
    // Links are multi-use, so reuse the one we already made rather than
    // minting a new invite row every time the dialog is opened.
    if (!invite.data && !invite.isPending) invite.mutate();
  };

  const copy = async () => {
    if (!invite.data) return;
    try {
      await navigator.clipboard.writeText(invite.data.url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // Clipboard can be blocked (permissions, insecure origin). The link is
      // still on screen and selectable, so this is not fatal.
    }
  };

  const canShare = typeof navigator !== "undefined" && !!navigator.share;
  const share = async () => {
    if (!invite.data) return;
    try {
      await navigator.share({
        title: "Watch Together",
        text: listName
          ? `Join my movie list “${listName}”`
          : "Join my movie list",
        url: invite.data.url,
      });
    } catch {
      // User dismissed the share sheet — nothing to do.
    }
  };

  return (
    <>
      <button className="invite-btn" onClick={openDialog}>
        🔗 Invite someone
      </button>

      {open && (
        <Modal label="Invite someone" onClose={() => setOpen(false)}>
          <div className="dialog-pad">
            <h2>🔗 Invite someone</h2>
            <p className="muted" style={{ marginTop: "0.4rem" }}>
              Anyone with this link can join{" "}
              {listName ? <strong>{listName}</strong> : "this list"} and edit it
              with you.
            </p>

            {invite.isPending && (
              <p className="muted" style={{ marginTop: "1.25rem" }}>
                Creating link…
              </p>
            )}

            {invite.error && (
              <div className="error" style={{ marginTop: "1rem" }}>
                {(invite.error as Error).message}
              </div>
            )}

            {invite.data && (
              <>
                <input
                  type="text"
                  readOnly
                  value={invite.data.url}
                  onFocus={(e) => e.currentTarget.select()}
                  style={{ marginTop: "1.25rem" }}
                  aria-label="Invite link"
                />
                <div className="dialog-actions">
                  <button className="primary" onClick={copy}>
                    {copied ? "✓ Copied" : "Copy link"}
                  </button>
                  {canShare && <button onClick={share}>Share…</button>}
                  <button className="ghost" onClick={() => setOpen(false)}>
                    Done
                  </button>
                </div>
              </>
            )}
          </div>
        </Modal>
      )}
    </>
  );
}
