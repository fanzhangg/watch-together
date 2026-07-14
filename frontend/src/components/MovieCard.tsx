import { Link } from "react-router-dom";
import { formatWatchedDate, posterUrl, type Item } from "../types";

/** Drawn rather than an 👁 emoji: emoji rendering varies wildly per platform and
 *  can't take the button's colour. This inherits currentColor. */
function EyeIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M1.5 12S5 5.5 12 5.5 22.5 12 22.5 12 19 18.5 12 18.5 1.5 12 1.5 12Z" />
      <circle cx="12" cy="12" r="3.2" />
    </svg>
  );
}

/**
 * The poster — and, once watched, the date stamped across it like a postmark.
 *
 * An unwatched card carries one control: a tick that marks it watched, today.
 * It's a button, not a menu, deliberately — a popover hung off a ~160px poster
 * is what produced the clipping and off-screen bugs this card used to have.
 * Everything else, including anything destructive, lives on the detail page.
 * A watched card has no control at all: its stamp says what it needs to.
 *
 * The title isn't rendered: the poster already carries it, far better than we
 * could. It moves to the link's aria-label so the card still has an accessible
 * name, and it's only drawn for the rare movie with no poster art.
 */
export default function MovieCard({
  item,
  listId,
  onWatch,
  busy,
}: {
  item: Item;
  listId: string;
  /** Omitted for a watched card, which carries no control. */
  onWatch?: () => void;
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
        {watched && item.watched_on && (
          <div className="watch-stamp">
            <span className="movie-watched">{formatWatchedDate(item.watched_on)}</span>
          </div>
        )}
      </Link>

      {!watched && onWatch && (
        <button
          className="watch-btn"
          aria-label={`Mark ${item.title} watched`}
          title="Mark watched today"
          disabled={busy}
          onClick={onWatch}
        >
          <EyeIcon />
        </button>
      )}
    </article>
  );
}
