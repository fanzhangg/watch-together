import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import Avatar, { displayName } from "../components/Avatar";
import ConfirmDialog from "../components/ConfirmDialog";
import DropdownMenu from "../components/DropdownMenu";
import InviteButton from "../components/InviteButton";
import ListNameDialog from "../components/ListNameDialog";
import MovieCard from "../components/MovieCard";
import MovieSearchDialog from "../components/MovieSearchDialog";
import type { Item, ListDetail } from "../types";

export default function ListPage() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [searchOpen, setSearchOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [renaming, setRenaming] = useState(false);

  const itemsKey = ["items", id];

  const { data: list, error: listError } = useQuery<ListDetail>({
    queryKey: ["list", id],
    queryFn: () => api.getList(id),
  });
  const { data: items, isPending } = useQuery<Item[]>({
    queryKey: itemsKey,
    queryFn: () => api.getItems(id),
  });

  const renameList = useMutation({
    mutationFn: (name: string) => api.renameList(id, name),
    onSuccess: () => {
      // Refresh both the open list and the collection it appears in.
      qc.invalidateQueries({ queryKey: ["list", id] });
      qc.invalidateQueries({ queryKey: ["lists"] });
      setRenaming(false);
    },
  });

  const deleteList = useMutation({
    mutationFn: () => api.deleteList(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lists"] });
      navigate("/");
    },
  });

  if (listError) {
    return (
      <div className="empty">
        <h3>You don’t have access to this list</h3>
        <p>Ask whoever owns it to send you an invite link.</p>
        <button style={{ marginTop: "1rem" }} onClick={() => navigate("/")}>
          Back to your lists
        </button>
      </div>
    );
  }

  const want = items?.filter((i) => i.status === "want_to_watch") ?? [];
  // Most recently watched first; within a day, most recently added first.
  const watched = (items?.filter((i) => i.status === "watched") ?? []).sort(
    (a, b) =>
      (b.watched_on ?? "").localeCompare(a.watched_on ?? "") ||
      b.created_at.localeCompare(a.created_at),
  );
  const existingTmdbIds = new Set((items ?? []).map((i) => i.tmdb_id));

  return (
    <>
      <div className="page-head">
        {/* Who's in this list sits beside its name — the faces are the whole
            point, so no names, and small enough not to compete with the title. */}
        <div className="list-title">
          <h1>{list?.name ?? "…"}</h1>
          <div className="members">
            {list?.members.map((m) => (
              <Avatar
                key={m.user.id}
                user={m.user}
                size={24}
                label={displayName(m.user)}
              />
            ))}
          </div>
        </div>
        <div className="actions">
          {/* On mobile this is replaced by the floating button (see .fab). */}
          <button
            className="primary add-movie"
            onClick={() => setSearchOpen(true)}
          >
            + Add movie
          </button>
          <InviteButton listId={id} listName={list?.name} />
          {list?.role === "owner" && (
            <DropdownMenu
              label="List options"
              triggerClassName="more-btn"
              trigger="⋯"
            >
              {(close) => (
                <>
                  <button
                    className="menu-item"
                    role="menuitem"
                    onClick={() => {
                      close();
                      setRenaming(true);
                    }}
                  >
                    Rename list
                  </button>
                  <div className="menu-sep" />
                  <button
                    className="menu-item danger"
                    role="menuitem"
                    onClick={() => {
                      close();
                      setConfirmDelete(true);
                    }}
                  >
                    Delete list
                  </button>
                </>
              )}
            </DropdownMenu>
          )}
        </div>
      </div>

      {isPending && <p className="muted">Loading movies…</p>}

      {items && items.length === 0 && (
        <div className="empty">
          <h3>No movies yet</h3>
          <p>Search TMDB and add the first one.</p>
          <button
            className="primary"
            style={{ marginTop: "1rem" }}
            onClick={() => setSearchOpen(true)}
          >
            + Add movie
          </button>
        </div>
      )}

      {want.length > 0 && (
        <>
          <h2 className="section-title">Want to watch</h2>
          <div className="movie-grid">
            {want.map((item) => (
              <MovieCard key={item.id} item={item} listId={id} />
            ))}
          </div>
        </>
      )}

      {watched.length > 0 && (
        <>
          <h2 className="section-title">Watched</h2>
          <div className="movie-grid">
            {watched.map((item) => (
              <MovieCard key={item.id} item={item} listId={id} />
            ))}
          </div>
        </>
      )}

      {renaming && list && (
        <ListNameDialog
          title="Rename list"
          initialName={list.name}
          submitLabel="Save"
          busy={renameList.isPending}
          error={renameList.error as Error | null}
          onSubmit={(name) => renameList.mutate(name)}
          onClose={() => setRenaming(false)}
        />
      )}

      {confirmDelete && list && (
        <ConfirmDialog
          title={`Delete “${list.name}”?`}
          body="This removes the list and all its movies for everyone in it. This can’t be undone."
          confirmLabel="Delete list"
          busy={deleteList.isPending}
          onConfirm={() => deleteList.mutate()}
          onCancel={() => setConfirmDelete(false)}
        />
      )}

      {/* Mobile: adding a movie is always one thumb-tap away. */}
      <button
        className="fab"
        aria-label="Add movie"
        onClick={() => setSearchOpen(true)}
      >
        +
      </button>

      {searchOpen && (
        <MovieSearchDialog
          listId={id}
          existingTmdbIds={existingTmdbIds}
          onClose={() => setSearchOpen(false)}
          onAdded={() => qc.invalidateQueries({ queryKey: itemsKey })}
        />
      )}
    </>
  );
}
