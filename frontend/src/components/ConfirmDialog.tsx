import Modal from "./Modal";

/**
 * Confirmation for destructive actions. Replaces window.confirm(), which looks
 * out of place and is especially jarring on mobile.
 */
export default function ConfirmDialog({
  title,
  body,
  confirmLabel = "Delete",
  busy,
  onConfirm,
  onCancel,
}: {
  title: string;
  body: string;
  confirmLabel?: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal label={title} onClose={onCancel}>
      <div className="dialog-pad">
        <h2>{title}</h2>
        <p className="muted" style={{ marginTop: "0.4rem" }}>
          {body}
        </p>
        <div className="dialog-actions">
          <button className="destructive" onClick={onConfirm} disabled={busy}>
            {busy ? "Deleting…" : confirmLabel}
          </button>
          <button className="ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
        </div>
      </div>
    </Modal>
  );
}
