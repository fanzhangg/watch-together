import { Link } from "react-router-dom";
import {
  formatAddedDate,
  formatWatchDate,
  posterUrl,
  type Item,
  type Member,
} from "../types";
import EyeIcon from "./EyeIcon";
import RatingButtons from "./RatingButtons";

/**
 * One movie as a row — the detail-rich counterpart to MovieCard.
 *
 * The poster grid is for finding a film fast: artwork, nothing else. This view
 * is for the state around it — when it was watched, and what everyone thought.
 *
 * **Every row can be rated**, watched or not: a thumb on something we haven't
 * seen reads as "I'm keen", on something we have, as "I liked it" (docs/design.md
 * §12). Only an unwatched row also carries the eye, since marking it watched is
 * the one thing left to do to it.
 *
 * The actions are **siblings** of the link, not children, so they're never tap
 * targets nested inside a tap target. Everything inside the link is inert, so
 * tapping the row opens the movie — which is what a row is expected to do.
 */
export default function MovieRow({
  item,
  listId,
  members,
  meId,
  onWatch,
  busy,
}: {
  item: Item;
  listId: string;
  members: Member[];
  meId: string | undefined;
  /** Omitted for a watched row — there's nothing left to mark. */
  onWatch?: () => void;
  busy?: boolean;
}) {
  const watched = item.status === "watched";
  const poster = posterUrl(item.poster_path, "w185");

  return (
    <article className={`movie-row${watched ? " is-watched" : ""}`}>
      <Link className="movie-row-link" to={`/lists/${listId}/items/${item.id}`}>
        {poster ? (
          <img className="row-poster" src={poster} alt="" loading="lazy" />
        ) : (
          <div className="row-poster placeholder" aria-hidden="true">
            🎞️
          </div>
        )}

        <div className="row-body">
          <h3 className="row-title">{item.title}</h3>
          {/* Both states say WHEN. "Want to watch" only repeated the section
              header above it; the day it was added is the thing you can't get
              anywhere else — and it's how you notice something has been sitting
              on the list since March. */}
          <p className="row-status muted">
            {watched && item.watched_on
              ? `Watched on ${formatWatchDate(item.watched_on)}`
              : `Wishlisted on ${formatAddedDate(item.created_at)}`}
          </p>
        </div>
      </Link>

      <div className="row-actions">
        <RatingButtons
          item={item}
          listId={listId}
          members={members}
          meId={meId}
          compact
        />
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
      </div>
    </article>
  );
}
