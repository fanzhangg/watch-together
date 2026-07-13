import { useState } from "react";
import Modal from "./Modal";

/**
 * Shared "name a list" dialog — used both to create a list and to rename one.
 * The caller owns the mutation; this just collects a valid, changed name.
 */
export default function ListNameDialog({
  title,
  description,
  initialName = "",
  submitLabel,
  busy = false,
  error,
  onSubmit,
  onClose,
}: {
  title: string;
  description?: string;
  initialName?: string;
  submitLabel: string;
  busy?: boolean;
  error?: Error | null;
  onSubmit: (name: string) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState(initialName);
  const trimmed = name.trim();
  // Nothing to do if it's empty, unchanged, or already in flight — this also
  // stops a double submit creating two identical lists.
  const canSubmit = !!trimmed && trimmed !== initialName.trim() && !busy;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    onSubmit(trimmed);
  };

  return (
    <Modal label={title} onClose={onClose}>
      <form className="dialog-pad" onSubmit={submit}>
        <h2>{title}</h2>
        {description && (
          <p className="muted" style={{ marginTop: "0.4rem" }}>
            {description}
          </p>
        )}

        <input
          type="text"
          autoFocus
          placeholder="e.g. Date night"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onFocus={(e) => e.currentTarget.select()}
          maxLength={200}
          aria-label="List name"
          style={{ marginTop: "1.25rem" }}
        />

        {error && (
          <div className="error" style={{ marginTop: "0.75rem" }}>
            {error.message}
          </div>
        )}

        <div className="dialog-actions">
          <button className="primary" type="submit" disabled={!canSubmit}>
            {busy ? "Saving…" : submitLabel}
          </button>
          <button className="ghost" type="button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}
