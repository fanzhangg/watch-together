import { Link } from "react-router-dom";
import { formatWatchedDate, posterUrl, type Item } from "../types";

/**
 * Just the poster — and, once watched, the date stamped across it like a
 * postmark. Nothing else: the whole card is a link to the detail page, which is
 * where every action on a movie lives.
 *
 * The title isn't rendered: the poster already carries it, far better than we
 * could. It moves to the link's aria-label so the card still has an accessible
 * name, and it's only drawn for the rare movie with no poster art.
 */
export default function MovieCard({ item, listId }: { item: Item; listId: string }) {
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
    </article>
  );
}
