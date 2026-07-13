import { Link } from "react-router-dom";
import DropdownMenu from "./DropdownMenu";
import { formatWatchedDate, posterUrl, type Item } from "../types";

/**
 * Deliberately minimal: poster, title, and — if watched — the day it was
 * watched. Nothing else. Anything richer is a click away on the detail page.
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
      <Link className="movie-link" to={`/lists/${listId}/items/${item.id}`}>
        {poster ? (
          <img className="poster" src={poster} alt="" loading="lazy" />
        ) : (
          <div className="poster placeholder">🎞️</div>
        )}
        <div className="movie-body">
          <div className="movie-title">{item.title}</div>
          {watched && item.watched_on && (
            <div className="movie-watched">{formatWatchedDate(item.watched_on)}</div>
          )}
        </div>
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
