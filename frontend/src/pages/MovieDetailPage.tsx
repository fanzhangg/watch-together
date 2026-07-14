import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import ConfirmDialog from "../components/ConfirmDialog";
import DropdownMenu from "../components/DropdownMenu";
import {
  posterUrl,
  todayISO,
  type Item,
  type ListDetail,
  type MovieDetail,
} from "../types";

/** "142" -> "2h 22m" */
function runtimeLabel(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h ? `${h}h ${m}m` : `${m}m`;
}

export default function MovieDetailPage() {
  const { id = "", itemId = "" } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [confirmRemove, setConfirmRemove] = useState(false);

  const itemKey = ["item", id, itemId];
  const backToList = () => {
    qc.invalidateQueries({ queryKey: ["items", id] });
    navigate(`/lists/${id}`);
  };

  const { data: list } = useQuery<ListDetail>({
    queryKey: ["list", id],
    queryFn: () => api.getList(id),
  });
  const {
    data: item,
    isPending,
    error: itemError,
  } = useQuery<Item>({
    queryKey: itemKey,
    queryFn: () => api.getItem(id, itemId),
  });

  // Live TMDB metadata. Its failure is not the page's failure — everything the
  // page needs to *function* (title, status, date) is already in `item`, so a
  // TMDB outage just costs us the runtime/cast/genres.
  const { data: detail, isPending: detailPending } = useQuery<MovieDetail>({
    queryKey: ["movie", item?.tmdb_id],
    queryFn: () => api.getMovieDetail(item!.tmdb_id),
    enabled: item !== undefined,
    retry: false,
  });

  // The PATCH response is the updated item, so seed the cache with it directly
  // and let the list refetch in the background (its ordering may have changed).
  const onUpdated = (next: Item) => {
    qc.setQueryData(itemKey, next);
    qc.invalidateQueries({ queryKey: ["items", id] });
  };

  const markWatched = useMutation({
    mutationFn: () => api.markWatched(id, itemId),
    onSuccess: onUpdated,
  });
  const markUnwatched = useMutation({
    mutationFn: () => api.markUnwatched(id, itemId),
    onSuccess: onUpdated,
  });
  const setDate = useMutation({
    mutationFn: (watchedOn: string) => api.setWatchedOn(id, itemId, watchedOn),
    onSuccess: onUpdated,
  });

  const remove = useMutation({
    mutationFn: () => api.deleteItem(id, itemId),
    onSuccess: backToList,
  });

  if (itemError) {
    return (
      <div className="empty">
        <h3>This movie isn’t here</h3>
        <p>It may have been removed from the list.</p>
        <button style={{ marginTop: "1rem" }} onClick={() => navigate(`/lists/${id}`)}>
          Back to the list
        </button>
      </div>
    );
  }
  if (isPending || !item) return <p className="muted">Loading…</p>;

  const watched = item.status === "watched";
  const poster = posterUrl(item.poster_path, "w500");
  const dateError = setDate.error as Error | null;

  return (
    <>
      <Link className="back-link" to={`/lists/${id}`}>
        ← {list?.name ?? "Back to the list"}
      </Link>

      <article className="detail">
        {poster ? (
          <img className="detail-poster" src={poster} alt="" />
        ) : (
          <div className="detail-poster placeholder">🎞️</div>
        )}

        <div className="detail-body">
          <h1>{item.title}</h1>

          <div className="detail-meta">
            {item.release_year && <span>{item.release_year}</span>}
            {detail?.runtime && <span>{runtimeLabel(detail.runtime)}</span>}
          </div>

          {detail?.tagline && <p className="detail-tagline">“{detail.tagline}”</p>}

          {detail && detail.genres.length > 0 && (
            <div className="members">
              {detail.genres.map((genre) => (
                <span className="chip" key={genre}>
                  {genre}
                </span>
              ))}
            </div>
          )}

          {/* The point of the page: when did we watch it. One control says it —
              the date picker IS the watch date, so a formatted copy of it above
              would just be the same fact twice. The menu sits BESIDE that
              control, as a sibling, not wrapped around it.

              Both states of the control share one fixed footprint (.watch-control),
              so marking a movie watched swaps the button for the date picker
              without the row changing size under the cursor. */}
          <section className="watch-panel">
            {watched && item.watched_on ? (
              <label className="watch-control watch-date">
                <span>Watched on</span>
                <input
                  type="date"
                  aria-label="Watch date"
                  value={item.watched_on}
                  max={todayISO()}
                  disabled={setDate.isPending}
                  onChange={(e) => e.target.value && setDate.mutate(e.target.value)}
                />
              </label>
            ) : (
              <button
                className="primary watch-control"
                onClick={() => markWatched.mutate()}
                disabled={markWatched.isPending}
              >
                ✓ Mark watched today
              </button>
            )}

            <DropdownMenu
              label="Movie options"
              triggerClassName="more-btn watch-more"
              trigger="⋯"
            >
              {(close) => (
                <>
                  {watched && (
                    <>
                      <button
                        className="menu-item"
                        role="menuitem"
                        disabled={markUnwatched.isPending}
                        onClick={() => {
                          close();
                          markUnwatched.mutate();
                        }}
                      >
                        ↩ Mark unwatched
                      </button>
                      <div className="menu-sep" />
                    </>
                  )}
                  <button
                    className="menu-item danger"
                    role="menuitem"
                    onClick={() => {
                      close();
                      setConfirmRemove(true);
                    }}
                  >
                    Remove from list
                  </button>
                </>
              )}
            </DropdownMenu>
          </section>

          {dateError && <p className="error">{dateError.message}</p>}

          {(detail?.overview ?? item.overview) && (
            <p className="detail-overview">{detail?.overview ?? item.overview}</p>
          )}

          {detail?.director && (
            <p className="detail-credit">
              <span className="muted">Director</span> {detail.director}
            </p>
          )}
          {detail && detail.cast.length > 0 && (
            <p className="detail-credit">
              <span className="muted">Cast</span> {detail.cast.join(", ")}
            </p>
          )}

          {!detail && !detailPending && (
            <p className="muted">
              Couldn’t reach TMDB for the full details — showing what we saved when
              this movie was added.
            </p>
          )}
        </div>
      </article>

      {confirmRemove && (
        <ConfirmDialog
          title={`Remove “${item.title}”?`}
          body="This takes it off the list for everyone in it."
          confirmLabel="Remove"
          busy={remove.isPending}
          onConfirm={() => remove.mutate()}
          onCancel={() => setConfirmRemove(false)}
        />
      )}
    </>
  );
}
