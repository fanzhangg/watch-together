import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import NewListDialog from "../components/NewListDialog";
import type { ListSummary } from "../types";

export default function ListsPage() {
  const [newOpen, setNewOpen] = useState(false);

  const {
    data: lists,
    isPending,
    error,
  } = useQuery<ListSummary[]>({
    queryKey: ["lists"],
    queryFn: api.getLists,
  });

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Your lists</h1>
          <div className="subtitle">Movies to watch together</div>
        </div>
        {/* On mobile this row is replaced by the floating button (see .fab),
            the same as "+ Add movie" on a list. */}
        <div className="actions lists-actions">
          <button className="primary" onClick={() => setNewOpen(true)}>
            + New list
          </button>
        </div>
      </div>

      {isPending && <p className="muted">Loading your lists…</p>}
      {error && <div className="error">{(error as Error).message}</div>}

      {lists && lists.length === 0 && (
        <div className="empty">
          <h3>No lists yet</h3>
          <p>Create your first list, then add movies and invite someone.</p>
          <button
            className="primary"
            style={{ marginTop: "1rem" }}
            onClick={() => setNewOpen(true)}
          >
            + New list
          </button>
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

      {/* Mobile: creating a list is always one thumb-tap away. */}
      <button
        className="fab"
        aria-label="New list"
        onClick={() => setNewOpen(true)}
      >
        +
      </button>

      {newOpen && <NewListDialog onClose={() => setNewOpen(false)} />}
    </>
  );
}
