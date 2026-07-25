import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { Item, Rating, RatingValue } from "./types";

/** My verdict on a movie, or null if I haven't given one. */
export function myRating(
  item: Item,
  meId: string | undefined,
): RatingValue | null {
  if (!meId) return null;
  return item.ratings.find((r) => r.user_id === meId)?.value ?? null;
}

/**
 * Set, flip, or clear my verdict on a movie.
 *
 * Shared by the detail page's control and the list view's quick buttons so the
 * two can't drift apart. Optimistic on **both** caches a verdict appears in —
 * the single item and the whole board — because either can be the screen you're
 * looking at when you tap, and the other is usually one click away.
 */
export function useRating(
  listId: string,
  itemId: string,
  meId: string | undefined,
) {
  const qc = useQueryClient();
  const itemKey = ["item", listId, itemId];
  const itemsKey = ["items", listId];

  return useMutation({
    // The response is discarded: the optimistic write below already holds the
    // new state, and onSettled refetches anyway.
    mutationFn: async (next: RatingValue | null): Promise<void> => {
      if (next === null) await api.clearRating(listId, itemId);
      else await api.setRating(listId, itemId, next);
    },

    onMutate: async (next) => {
      await qc.cancelQueries({ queryKey: itemKey });
      await qc.cancelQueries({ queryKey: itemsKey });
      const prevItem = qc.getQueryData<Item>(itemKey);
      const prevItems = qc.getQueryData<Item[]>(itemsKey);

      if (meId) {
        const mine: Rating[] =
          next === null ? [] : [{ user_id: meId, value: next }];
        // Replaces only my own entry — everyone else's is untouchable.
        const apply = (item: Item): Item =>
          item.id === itemId
            ? {
                ...item,
                ratings: [
                  ...item.ratings.filter((r) => r.user_id !== meId),
                  ...mine,
                ],
              }
            : item;

        qc.setQueryData<Item>(itemKey, (old) => (old ? apply(old) : old));
        qc.setQueryData<Item[]>(itemsKey, (old) => old?.map(apply));
      }
      return { prevItem, prevItems };
    },

    onError: (_err, _next, ctx) => {
      if (ctx?.prevItem) qc.setQueryData(itemKey, ctx.prevItem);
      if (ctx?.prevItems) qc.setQueryData(itemsKey, ctx.prevItems);
    },

    onSettled: () => {
      qc.invalidateQueries({ queryKey: itemKey });
      qc.invalidateQueries({ queryKey: itemsKey });
    },
  });
}
