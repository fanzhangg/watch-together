import RatingButtons from "./RatingButtons";
import type { Item, Member } from "../types";

/**
 * The detail page's rating panel: a prompt, and the 👍 / 👎 buttons carrying
 * everyone's faces.
 *
 * One element rather than a control plus a read-only strip — the button *is*
 * the tally, so nothing is stated twice and your own verdict appears exactly
 * once, as the pressed button.
 *
 * A verdict is independent of the watch status (docs/design.md §12), so this
 * renders whatever state the movie is in and there is no gate to pass. What a
 * thumb *means* comes from that status instead: on something we haven't seen it
 * reads as "I'm keen", on something we have, as "I liked it". The prompt is what
 * makes that explicit, so the two of you don't quietly adopt different
 * conventions.
 */
export default function RatingControl({
  item,
  listId,
  members,
  meId,
}: {
  item: Item;
  listId: string;
  members: Member[];
  /** Undefined only while `me` is still loading. */
  meId: string | undefined;
}) {
  return (
    <section className="rating-panel">
      <span className="muted">
        {item.status === "watched" ? "How was it?" : "Keen to watch it?"}
      </span>

      <RatingButtons
        item={item}
        listId={listId}
        members={members}
        meId={meId}
        show="who"
      />
    </section>
  );
}
