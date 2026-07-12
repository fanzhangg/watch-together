import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { ListSummary } from "../types";

export default function ListsPage() {
  const qc = useQueryClient();
  const [name, setName] = useState("");

  const { data: lists, isPending, error } = useQuery<ListSummary[]>({
    queryKey: ["lists"],
    queryFn: api.getLists,
  });

  const createList = useMutation({
    mutationFn: (n: string) => api.createList(n),
    onSuccess: () => {
      setName("");
      qc.invalidateQueries({ queryKey: ["lists"] });
    },
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    // Guard against double-submits creating duplicate lists.
    if (!trimmed || createList.isPending) return;
    createList.mutate(trimmed);
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Your lists</h1>
          <div className="subtitle">Movies to watch together</div>
        </div>
      </div>

      <form onSubmit={submit} className="row" style={{ marginBottom: "1.75rem" }}>
        <input
          type="text"
          placeholder="New list name — e.g. Date night"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={200}
        />
        <button
          className="primary"
          type="submit"
          disabled={!name.trim() || createList.isPending}
          style={{ flex: "none" }}
        >
          {createList.isPending ? "Creating…" : "Create"}
        </button>
      </form>

      {createList.error && (
        <div className="error">{(createList.error as Error).message}</div>
      )}

      {isPending && <p className="muted">Loading your lists…</p>}
      {error && <div className="error">{(error as Error).message}</div>}

      {lists && lists.length === 0 && (
        <div className="empty">
          <h3>No lists yet</h3>
          <p>Create your first list above, then add movies and invite someone.</p>
        </div>
      )}

      {lists && lists.length > 0 && (
        <div className="card-grid">
          {lists.map((l) => (
            <Link key={l.id} to={`/lists/${l.id}`} className="list-card">
              <h3>{l.name}</h3>
              <span className="badge">{l.role}</span>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
