import { Link } from "react-router-dom";
import DropdownMenu from "./DropdownMenu";
import { formatWatchedDate, posterUrl, type Item } from "../types";

/**
 * Just the poster — and, once watched, the date stamped across it like a
 * postmark.
 *
 * The title isn't rendered: the poster already carries it, far better than we
 * could. It moves to the link's aria-label so the card still has an accessible
 * name, and it's only drawn for the rare movie with no poster art.
 *
 * The body is a link, so the quick actions live behind a "⋯" menu rather than
 * as buttons nested inside a tap target.
 */
export default function MovieCard({
  item,
  listId,
  onToggle,
  onRemove,
  busy,
}: {
  item: Item;
  listId: string;
  onToggle: () => void;
  onRemove: () => void;
  busy?: boolean;
}) {
  const watched = item.status === "watched";
  const poster = posterUrl(item.poster_path);

  return (
    <article className={`movie${watched ? " is-watched" : ""}`}>
      <Link
        className="movie-link"
        to={`/lists/${listId}/items/${item.id}`}
        aria-label={item.title}
      >
        {poster ? (
          <img className="poster" src={poster} alt="" loading="lazy" />
        ) : (
          <div className="poster placeholder">
            <span aria-hidden="true">🎞️</span>
            <span className="movie-title">{item.title}</span>
          </div>
        )}
        {/* A watched movie gets the date stamped onto the poster, like a
            postmark on a card you've received. */}
        {watched && item.watched_on && (
          <div className="watch-stamp">
            <span className="movie-watched">{formatWatchedDate(item.watched_on)}</span>
          </div>
        )}
      </Link>

      <DropdownMenu
        label={`Options for ${item.title}`}
        triggerClassName="card-more-btn"
        trigger="⋯"
      >
        {(close) => (
          <>
            <button
              className="menu-item"
              role="menuitem"
              disabled={busy}
              onClick={() => {
                close();
                onToggle();
              }}
            >
              {watched ? "↩ Mark unwatched" : "✓ Mark watched"}
            </button>
            <div className="menu-sep" />
            <button
              className="menu-item danger"
              role="menuitem"
              disabled={busy}
              onClick={() => {
                close();
                onRemove();
              }}
            >
              Remove from list
            </button>
          </>
        )}
      </DropdownMenu>
    </article>
  );
}
