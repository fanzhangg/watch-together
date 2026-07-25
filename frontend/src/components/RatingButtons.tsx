import Avatar, { displayName } from "./Avatar";
import ThumbIcon from "./ThumbIcon";
import { myRating, useRating } from "../ratings";
import type { Item, Member, RatingValue } from "../types";

const ORDER: RatingValue[] = [1, -1];

/**
 * 👍 / 👎 on a movie — **one element that both shows the verdict and casts it**.
 *
 * A separate read-only widget beside the buttons said the same thing twice: the
 * tally, and then the control that changes it. Here the button carries its own
 * count (or, where there's room, the faces behind it), which also means your own
 * verdict appears exactly once — as the pressed button — instead of in a strip
 * as well.
 *
 * Three states, and **tapping the thumb you already hold takes it back**, which
 * is the only way to undo a mis-tap.
 *
 * `show`:
 * - `count` — "👍 2". For list rows, where space is tight.
 * - `who` — the voters' avatars, overlapped. For the detail page, where the
 *   question is *who* thought that, not how many.
 */
export default function RatingButtons({
  item,
  listId,
  members,
  meId,
  show = "count",
  compact = false,
}: {
  item: Item;
  listId: string;
  members: Member[];
  /** Undefined only while `me` is still loading. */
  meId: string | undefined;
  show?: "count" | "who";
  /** Tighter, for a list row rather than the detail page. */
  compact?: boolean;
}) {
  const rate = useRating(listId, item.id, meId);
  const mine = myRating(item, meId);

  return (
    <div className={`rating-control${compact ? " is-compact" : ""}`}>
      {ORDER.map((value) => {
        // Member order decides face order, so it matches the avatars beside
        // the list name rather than whatever order the votes arrived in.
        const voters = members
          .map((m) => m.user)
          .filter((u) =>
            item.ratings.some((r) => r.user_id === u.id && r.value === value),
          );
        const label = value === 1 ? "Thumbs up" : "Thumbs down";

        return (
          <button
            key={value}
            className={`rating-btn${mine === value ? " is-mine" : ""}`}
            aria-pressed={mine === value}
            aria-label={
              voters.length
                ? `${label} — ${voters.map(displayName).join(", ")}`
                : label
            }
            title={
              voters.length
                ? `${label}: ${voters.map(displayName).join(", ")}`
                : label
            }
            disabled={rate.isPending || !meId}
            onClick={() => rate.mutate(mine === value ? null : value)}
          >
            <span className="rating-thumb">
              <ThumbIcon up={value === 1} size={compact ? 16 : 18} />
            </span>

            {voters.length > 0 &&
              (show === "count" ? (
                <span aria-hidden="true" className="rating-count">
                  {voters.length}
                </span>
              ) : (
                <span aria-hidden="true" className="avatar-stack">
                  {voters.map((user) => (
                    <Avatar key={user.id} user={user} size={18} />
                  ))}
                </span>
              ))}
          </button>
        );
      })}
    </div>
  );
}
