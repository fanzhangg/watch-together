import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import Modal from "./Modal";

/** Mirrors the "add a movie" flow: a button opens a dialog, rather than an
 *  inline form sitting on the page. */
export default function NewListDialog({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");

  const create = useMutation({
    mutationFn: (n: string) => api.createList(n),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lists"] });
      onClose();
    },
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    // Guard against a double submit creating two identical lists.
    if (!trimmed || create.isPending) return;
    create.mutate(trimmed);
  };

  return (
    <Modal label="New list" onClose={onClose}>
      <form className="dialog-pad" onSubmit={submit}>
        <h2>New list</h2>
        <p className="muted" style={{ marginTop: "0.4rem" }}>
          Give it a name you’ll both recognise.
        </p>

        <input
          type="text"
          autoFocus
          placeholder="e.g. Date night"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={200}
          aria-label="List name"
          style={{ marginTop: "1.25rem" }}
        />

        {create.error && (
          <div className="error" style={{ marginTop: "0.75rem" }}>
            {(create.error as Error).message}
          </div>
        )}

        <div className="dialog-actions">
          <button
            className="primary"
            type="submit"
            disabled={!name.trim() || create.isPending}
          >
            {create.isPending ? "Creating…" : "Create list"}
          </button>
          <button
            className="ghost"
            type="button"
            onClick={onClose}
            disabled={create.isPending}
          >
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}
