import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import ConfirmDialog from "../components/ConfirmDialog";
import DropdownMenu from "../components/DropdownMenu";
import InviteButton from "../components/InviteButton";
import MovieCard from "../components/MovieCard";
import MovieSearchDialog from "../components/MovieSearchDialog";
import type { Item, ListDetail, Status } from "../types";

export default function ListPage() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [searchOpen, setSearchOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

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
  const toggle = useMutation({
    mutationFn: ({ item, status }: { item: Item; status: Status }) =>
      api.setItemStatus(id, item.id, status),
    onMutate: async ({ item, status }) => {
      await qc.cancelQueries({ queryKey: itemsKey });
      const previous = qc.getQueryData<Item[]>(itemsKey);
      qc.setQueryData<Item[]>(itemsKey, (old) =>
        old?.map((i) => (i.id === item.id ? { ...i, status } : i)),
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
  const watched = items?.filter((i) => i.status === "watched") ?? [];
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
                onToggle={() => toggle.mutate({ item, status: "want_to_watch" })}
                onRemove={() => remove.mutate(item)}
              />
            ))}
          </div>
        </>
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
