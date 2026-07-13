import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../api";
import { posterUrl, type MovieSearchResult } from "../types";

/** Debounce a value so we don't fire a TMDB search on every keystroke. */
function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

export default function MovieSearchDialog({
  listId,
  existingTmdbIds,
  onClose,
  onAdded,
}: {
  listId: string;
  existingTmdbIds: Set<number>;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [query, setQuery] = useState("");
  const debounced = useDebounced(query.trim(), 300);

  // Close on Escape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Stop the page scrolling behind the sheet (very noticeable on mobile).
  useEffect(() => {
    document.body.classList.add("no-scroll");
    return () => document.body.classList.remove("no-scroll");
  }, []);

  const { data: results, isFetching, error } = useQuery<MovieSearchResult[]>({
    queryKey: ["tmdb", debounced],
    queryFn: () => api.searchMovies(debounced),
    enabled: debounced.length > 0,
  });

  const add = useMutation({
    mutationFn: (tmdbId: number) => api.addItem(listId, tmdbId),
    onSuccess: onAdded,
  });

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div
        className="dialog"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Add a movie"
      >
        <div className="dialog-head">
          <input
            type="search"
            autoFocus
            placeholder="Search movies…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button className="ghost" onClick={onClose} style={{ flex: "none" }}>
            Close
          </button>
        </div>

        <div className="dialog-body">
          {error && <div className="error">{(error as Error).message}</div>}
          {add.error && <div className="error">{(add.error as Error).message}</div>}

          {!debounced && (
            <p className="muted" style={{ padding: "1.5rem", textAlign: "center" }}>
              Type a title to search TMDB.
            </p>
          )}
          {debounced && isFetching && (
            <p className="muted" style={{ padding: "1rem" }}>
              Searching…
            </p>
          )}
          {debounced && !isFetching && results?.length === 0 && (
            <p className="muted" style={{ padding: "1rem" }}>
              No movies found for “{debounced}”.
            </p>
          )}

          {results?.map((m) => {
            const already = existingTmdbIds.has(m.tmdb_id);
            const thumb = posterUrl(m.poster_path, "w92");
            return (
              <div className="result" key={m.tmdb_id}>
                {thumb ? (
                  <img src={thumb} alt="" loading="lazy" />
                ) : (
                  <div className="thumb">🎞️</div>
                )}
                <div className="result-info">
                  <div className="t">
                    {m.title}{" "}
                    {m.release_year && <span className="muted">({m.release_year})</span>}
                  </div>
                  {m.overview && <div className="o">{m.overview}</div>}
                </div>
                <button
                  className={already ? "small" : "small primary"}
                  disabled={already || add.isPending}
                  onClick={() => add.mutate(m.tmdb_id)}
                  style={{ flex: "none" }}
                >
                  {already ? "Added" : "Add"}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
