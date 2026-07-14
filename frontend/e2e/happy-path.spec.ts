import { expect, test } from "@playwright/test";
import { createAndOpenList, deleteOpenList } from "./helpers";

/**
 * The M5 happy path, driven through the real UI in a browser:
 * sign in -> create a list -> search TMDB -> add a movie -> mark it watched ->
 * generate an invite link. This is the flow the app exists to support.
 */
test("sign in, create a list, add a movie, mark watched, invite", async ({ page }) => {
  const listName = `E2E ${Date.now()}`;

  // --- sign in (dev login) ---
  await page.goto("/login");
  await page.getByRole("button", { name: "Dev login" }).click();
  await expect(page.getByRole("heading", { name: "Your lists" })).toBeVisible();

  // --- create a list (button -> dialog, same as adding a movie) ---
  await createAndOpenList(page, listName);
  await expect(page.getByText("No movies yet")).toBeVisible();

  // --- add a movie via TMDB search ---
  await page.getByRole("button", { name: "+ Add movie" }).first().click();
  await page.getByPlaceholder("Search movies…").fill("the matrix");

  const result = page.locator(".result").filter({ hasText: "The Matrix" }).first();
  await expect(result).toBeVisible({ timeout: 15_000 }); // real TMDB call
  await result.getByRole("button", { name: "Add" }).click();

  // Once added, the dialog marks it as already in the list.
  await expect(result.getByRole("button", { name: "Added" })).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();

  // --- it lands under "Want to watch" ---
  // The card carries no title text (the poster art does), so it's found by the
  // link's accessible name.
  await expect(page.getByRole("heading", { name: /Want to watch/ })).toBeVisible();
  const movie = page
    .locator(".movie")
    .filter({ has: page.getByRole("link", { name: "The Matrix" }) })
    .first();
  await expect(movie).toBeVisible();

  // --- one tap on the card's tick marks it watched (optimistic) ---
  await movie.getByRole("button", { name: "Mark The Matrix watched" }).click();

  await expect(page.getByRole("heading", { name: /^Watched/ })).toBeVisible();
  const watchedCard = page
    .locator(".movie.is-watched")
    .filter({ has: page.getByRole("link", { name: "The Matrix" }) });
  await expect(watchedCard).toBeVisible();

  // The card shows TODAY — as the browser itself reckons it. This is the guard
  // against parsing the API's "2026-07-12" as UTC midnight, which would render
  // as *yesterday* anywhere west of Greenwich (design.md risk #9). Computing the
  // expectation in the page keeps it honest about locale and timezone.
  const today = await page.evaluate(() =>
    new Date().toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
    }),
  );
  await expect(watchedCard.locator(".movie-watched")).toHaveText(today);

  // Once watched, the card carries no control at all — the stamp says it, and
  // unwatching lives on the detail page.
  await expect(watchedCard.getByRole("button")).toHaveCount(0);

  // Survives a reload — it was really persisted, not just optimistic UI.
  await page.reload();
  await expect(watchedCard).toBeVisible();
  await expect(watchedCard.locator(".movie-watched")).toHaveText(today);

  // --- invite link (opens in a modal) ---
  await page.getByRole("button", { name: /Invite/ }).click();
  const dialog = page.getByRole("dialog", { name: "Invite someone" });
  await expect(dialog).toBeVisible();
  const link = dialog.locator("input[readonly]");
  await expect(link).toHaveValue(/\/invite\/.+/);
  await expect(dialog.getByRole("button", { name: "Copy link" })).toBeVisible();

  await dialog.getByRole("button", { name: "Done" }).click();
  await expect(dialog).toBeHidden();

  // --- delete, via the "⋯" menu + confirm dialog ---
  // Deletion must not be reachable without opening the menu.
  await expect(page.getByRole("menuitem", { name: "Delete list" })).toHaveCount(0);
  await deleteOpenList(page);
  await expect(page.getByRole("link", { name: new RegExp(listName) })).toHaveCount(0);
});

test("open a movie, correct the date we actually watched it", async ({ page }) => {
  const listName = `Detail ${Date.now()}`;

  await page.goto("/login");
  await page.getByRole("button", { name: "Dev login" }).click();
  await createAndOpenList(page, listName);

  // Add a movie and mark it watched (which dates it "today").
  await page.getByRole("button", { name: "+ Add movie" }).first().click();
  await page.getByPlaceholder("Search movies…").fill("the matrix");
  const result = page.locator(".result").filter({ hasText: "The Matrix" }).first();
  await expect(result).toBeVisible({ timeout: 15_000 });
  await result.getByRole("button", { name: "Add" }).click();
  await page.getByRole("button", { name: "Close" }).click();

  const card = page
    .locator(".movie")
    .filter({ has: page.getByRole("link", { name: "The Matrix" }) })
    .first();

  // --- the card is a link to the detail page, where it gets marked watched ---
  await card.getByRole("link").click();
  await expect(page.getByRole("heading", { name: "The Matrix" })).toBeVisible();
  await page.getByRole("button", { name: "✓ Mark watched today" }).click();
  await expect(page.getByLabel("Watch date")).toBeVisible();
  // Live TMDB metadata the DB snapshot doesn't hold.
  await expect(page.getByText("Keanu Reeves")).toBeVisible({ timeout: 15_000 });

  // --- but we actually watched it on the 4th ---
  // The picker IS the watch date — there's no formatted copy of it to check.
  await page.getByLabel("Watch date").fill("2026-07-04");

  // It really persisted — and the list shows the corrected date, not today.
  await page.reload();
  await expect(page.getByLabel("Watch date")).toHaveValue("2026-07-04");
  await page.getByRole("link", { name: new RegExp(listName) }).click();
  await expect(card.locator(".movie-watched")).toHaveText("Sat, Jul 4, 2026");

  await deleteOpenList(page);
});

test("unwatch and remove live in the detail page's ⋯ menu", async ({ page }) => {
  const listName = `Menu ${Date.now()}`;

  await page.goto("/login");
  await page.getByRole("button", { name: "Dev login" }).click();
  await createAndOpenList(page, listName);

  await page.getByRole("button", { name: "+ Add movie" }).first().click();
  await page.getByPlaceholder("Search movies…").fill("the matrix");
  const result = page.locator(".result").filter({ hasText: "The Matrix" }).first();
  await expect(result).toBeVisible({ timeout: 15_000 });
  await result.getByRole("button", { name: "Add" }).click();
  await page.getByRole("button", { name: "Close" }).click();

  await page.getByRole("link", { name: "The Matrix" }).click();

  // Unwatched: one button, no "not watched yet" restatement of it.
  await expect(page.getByRole("button", { name: "✓ Mark watched today" })).toBeVisible();
  await expect(page.getByText("Not watched yet")).toHaveCount(0);
  // Destructive actions are never loose on the page.
  await expect(page.getByRole("button", { name: "Remove from list" })).toHaveCount(0);

  await page.getByRole("button", { name: "✓ Mark watched today" }).click();
  await expect(page.getByLabel("Watch date")).toBeVisible();

  // Unwatch, from the menu.
  await page.getByRole("button", { name: "Movie options" }).click();
  await page.getByRole("menuitem", { name: "↩ Mark unwatched" }).click();
  await expect(page.getByRole("button", { name: "✓ Mark watched today" })).toBeVisible();

  // Remove, from the menu — via a confirm, then back to the list.
  await page.getByRole("button", { name: "Movie options" }).click();
  await page.getByRole("menuitem", { name: "Remove from list" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Remove" }).click();

  await expect(page.getByText("No movies yet")).toBeVisible();

  await deleteOpenList(page);
});

test("the list action buttons line up with each other", async ({ page }) => {
  const listName = `Align ${Date.now()}`;

  await page.goto("/login");
  await page.getByRole("button", { name: "Dev login" }).click();
  await createAndOpenList(page, listName);

  const add = (await page.locator(".actions .add-movie").boundingBox())!;
  const invite = (await page.locator(".actions .invite-btn").boundingBox())!;
  const more = (await page.locator(".actions .more-btn").boundingBox())!;

  // The "⋯" trigger sits inside a positioning wrapper, so it does not stretch
  // to the row height for free — assert it really is the same size and on the
  // same baseline as its siblings.
  expect(Math.round(more.height)).toBe(Math.round(invite.height));
  expect(Math.round(add.height)).toBe(Math.round(invite.height));
  expect(Math.round(more.y)).toBe(Math.round(invite.y));

  await deleteOpenList(page);
});

test("rename a list from the ⋯ menu", async ({ page }) => {
  const before = `Rename ${Date.now()}`;
  const after = `${before} renamed`;

  await page.goto("/login");
  await page.getByRole("button", { name: "Dev login" }).click();
  await createAndOpenList(page, before);

  // Rename lives behind the same menu as delete, not loose on the page.
  await expect(page.getByRole("menuitem", { name: "Rename list" })).toHaveCount(0);
  await page.getByRole("button", { name: "List options" }).click();
  await page.getByRole("menuitem", { name: "Rename list" }).click();

  const dialog = page.getByRole("dialog", { name: "Rename list" });
  await expect(dialog).toBeVisible();
  // Prefilled with the current name, and Save is disabled until it changes.
  await expect(dialog.getByLabel("List name")).toHaveValue(before);
  await expect(dialog.getByRole("button", { name: "Save" })).toBeDisabled();

  await dialog.getByLabel("List name").fill(after);
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(dialog).toBeHidden();

  // The heading updates...
  await expect(page.getByRole("heading", { name: after })).toBeVisible();
  // ...and so does the lists page (it really persisted, not just local state).
  await page.reload();
  await expect(page.getByRole("heading", { name: after })).toBeVisible();
  await page.getByRole("link", { name: "Watch Together" }).click();
  await expect(page.getByRole("link", { name: after })).toBeVisible();
  await expect(page.getByRole("link", { name: before, exact: true })).toHaveCount(0);

  await page.getByRole("link", { name: after }).click();
  await deleteOpenList(page);
});

test("avatar opens a profile menu, which is where sign out lives", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Dev login" }).click();
  await expect(page.getByRole("heading", { name: "Your lists" })).toBeVisible();

  // Sign out is not sitting in the header any more — it's behind the avatar.
  await expect(page.getByRole("menuitem", { name: "Sign out" })).toHaveCount(0);

  const avatar = page.getByRole("button", { name: "Account menu" });
  await avatar.click();

  const menu = page.getByRole("menu");
  await expect(menu).toBeVisible();
  await expect(menu.getByText("dev@local")).toBeVisible();

  // Escape closes it.
  await page.keyboard.press("Escape");
  await expect(menu).toBeHidden();

  // Clicking outside closes it too.
  await avatar.click();
  await expect(menu).toBeVisible();
  await page.locator("main").click({ position: { x: 5, y: 5 } });
  await expect(menu).toBeHidden();

  // And signing out from the menu really signs you out.
  await avatar.click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page.getByRole("button", { name: "Dev login" })).toBeVisible();
});

test("invite page shows a preview and asks a signed-out visitor to sign in", async ({
  browser,
}) => {
  const listName = `E2E invite ${Date.now()}`;

  // Owner creates a list and an invite link.
  const owner = await browser.newContext();
  const ownerPage = await owner.newPage();
  await ownerPage.goto("/login");
  await ownerPage.getByRole("button", { name: "Dev login" }).click();
  await createAndOpenList(ownerPage, listName);
  await ownerPage.getByRole("button", { name: /Invite/ }).click();
  const inviteDialog = ownerPage.getByRole("dialog", { name: "Invite someone" });
  const url = await inviteDialog.locator("input[readonly]").inputValue();
  await inviteDialog.getByRole("button", { name: "Done" }).click();

  // A signed-out visitor opens the link: they see WHAT they're joining,
  // without having to sign in first.
  const visitor = await browser.newContext();
  const visitorPage = await visitor.newPage();
  await visitorPage.goto(new URL(url).pathname);

  await expect(visitorPage.getByText("You’re invited")).toBeVisible();
  await expect(visitorPage.getByRole("heading", { name: listName })).toBeVisible();
  await expect(visitorPage.getByRole("button", { name: "Sign in to join" })).toBeVisible();

  // cleanup
  await deleteOpenList(ownerPage);
  await owner.close();
  await visitor.close();
});
