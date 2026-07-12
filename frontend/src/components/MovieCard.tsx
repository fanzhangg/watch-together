import { posterUrl, type Item } from "../types";

export default function MovieCard({
  item,
  onToggle,
  onRemove,
  busy,
}: {
  item: Item;
  onToggle: () => void;
  onRemove: () => void;
  busy?: boolean;
}) {
  const watched = item.status === "watched";
  const poster = posterUrl(item.poster_path);

  return (
    <article className={`movie${watched ? " is-watched" : ""}`}>
      {poster ? (
        <img className="poster" src={poster} alt="" loading="lazy" />
      ) : (
        <div className="poster placeholder">🎞️</div>
      )}
      <div className="movie-body">
        <div>
          <div className="movie-title">{item.title}</div>
          {item.release_year && <div className="movie-year">{item.release_year}</div>}
        </div>
        <div className="movie-actions">
          <button className="small" onClick={onToggle} disabled={busy}>
            {watched ? "↩ Unwatch" : "✓ Watched"}
          </button>
          <button
            className="small ghost danger"
            onClick={onRemove}
            disabled={busy}
            aria-label={`Remove ${item.title}`}
            style={{ flex: "none" }}
          >
            ✕
          </button>
        </div>
      </div>
    </article>
  );
}
