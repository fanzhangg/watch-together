import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useMe } from "../auth";
import ConfirmDialog from "../components/ConfirmDialog";
import DropdownMenu from "../components/DropdownMenu";
import DotsIcon from "../components/DotsIcon";
import EyeIcon from "../components/EyeIcon";
import RatingControl from "../components/RatingControl";
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
  // Verdicts carry a bare user_id; `list.members` is what turns those into
  // faces, and `me` is how the control knows which one is mine to change.
  const { data: me } = useMe();
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

        {/* What identifies the film, kept separate from what's said about it —
            on a phone this is the part that sits BESIDE the poster, while the
            synopsis and the action panel run full width underneath. */}
        <div className="detail-headline">
          <h1>{item.title}</h1>

          {/* Year, runtime and genres are all the same kind of fact — a label on
              the film — so they share one wrapping row instead of three stacked
              blocks. The metadata is here to be glanced at, not read. */}
          <div className="detail-meta">
            {item.release_year && (
              <span className="detail-fact">{item.release_year}</span>
            )}
            {detail?.runtime && (
              <span className="detail-fact">{runtimeLabel(detail.runtime)}</span>
            )}
            {/* Wrapped so the phone can drop the whole set onto its own line.
                On a wide screen it's `display: contents`, so the chips stay
                direct children of the meta row and nothing changes. */}
            {detail && detail.genres.length > 0 && (
              <span className="detail-genres">
                {detail.genres.map((genre) => (
                  <span className="chip" key={genre}>
                    {genre}
                  </span>
                ))}
              </span>
            )}
          </div>

          {detail?.tagline && <p className="detail-tagline">“{detail.tagline}”</p>}
        </div>

        <div className="detail-body">

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

          {/* The point of the page: when did we watch it. One control says it —
              the date picker IS the watch date, so a formatted copy of it above
              would just be the same fact twice. The menu sits BESIDE that
              control, as a sibling, not wrapped around it.

              Both states of the control share one fixed footprint (.watch-control),
              so marking a movie watched swaps the button for the date picker
              without the row changing size under the cursor.

              Everything you can DO to this movie comes LAST: the metadata above
              is reference material you skim, so the page reads title -> what it
              is -> what we do about it. A labelled rule marks the change of
              subject — the same one the watched board puts between months. */}
          <h2 className="section-label actions-label">Watch &amp; rate</h2>
          <section className="detail-actions">
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
                <EyeIcon />
                Mark watched today
              </button>
            )}

            <DropdownMenu
              label="Movie options"
              triggerClassName="more-btn watch-more"
              trigger={<DotsIcon />}
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

            {/* Grouped with the watch control because both are things you DO
                here — not because the two facts are related. They stay
                independent (docs/design.md §12); only the affordances are
                neighbours. */}
            <RatingControl
              item={item}
              listId={id}
              members={list?.members ?? []}
              meId={me?.id}
            />
          </section>
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
