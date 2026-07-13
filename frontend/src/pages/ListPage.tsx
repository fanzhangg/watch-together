import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import ConfirmDialog from "../components/ConfirmDialog";
import DropdownMenu from "../components/DropdownMenu";
import InviteButton from "../components/InviteButton";
import ListNameDialog from "../components/ListNameDialog";
import MovieCard from "../components/MovieCard";
import MovieSearchDialog from "../components/MovieSearchDialog";
import { todayISO, type Item, type ListDetail, type Status } from "../types";

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

  // Optimistic toggle: flip it in the cache immediately, roll back on failure.
  // watched_on moves with the status — the card renders the date, so leaving it
  // for the refetch would flash a dateless "Watched" card.
  const toggle = useMutation({
    mutationFn: ({ item, status }: { item: Item; status: Status }) =>
      status === "watched"
        ? api.markWatched(id, item.id)
        : api.markUnwatched(id, item.id),
    onMutate: async ({ item, status }) => {
      await qc.cancelQueries({ queryKey: itemsKey });
      const previous = qc.getQueryData<Item[]>(itemsKey);
      const watched_on = status === "watched" ? todayISO() : null;
      qc.setQueryData<Item[]>(itemsKey, (old) =>
        old?.map((i) => (i.id === item.id ? { ...i, status, watched_on } : i)),
      );
      return { previous };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(itemsKey, ctx.previous);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: itemsKey }),
  });

  const remove = useMutation({
    mutationFn: (item: Item) => api.deleteItem(id, item.id),
    onMutate: async (item) => {
      await qc.cancelQueries({ queryKey: itemsKey });
      const previous = qc.getQueryData<Item[]>(itemsKey);
      qc.setQueryData<Item[]>(itemsKey, (old) => old?.filter((i) => i.id !== item.id));
      return { previous };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(itemsKey, ctx.previous);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: itemsKey }),
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
        <div>
          <h1>{list?.name ?? "…"}</h1>
          <div className="members" style={{ marginTop: "0.5rem" }}>
            {list?.members.map((m) => (
              <span className="chip" key={m.user.id}>
                {m.user.display_name ?? m.user.email}
                <span className="role">{m.role}</span>
              </span>
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
          <h2 className="section-title">
            Want to watch <span className="count">{want.length}</span>
          </h2>
          <div className="movie-grid">
            {want.map((item) => (
              <MovieCard
                key={item.id}
                item={item}
                listId={id}
                onToggle={() => toggle.mutate({ item, status: "watched" })}
                onRemove={() => remove.mutate(item)}
              />
            ))}
          </div>
        </>
      )}

      {watched.length > 0 && (
        <>
          <h2 className="section-title">
            Watched <span className="count">{watched.length}</span>
          </h2>
          <div className="movie-grid">
            {watched.map((item) => (
              <MovieCard
                key={item.id}
                item={item}
                listId={id}
                onToggle={() => toggle.mutate({ item, status: "want_to_watch" })}
                onRemove={() => remove.mutate(item)}
              />
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
