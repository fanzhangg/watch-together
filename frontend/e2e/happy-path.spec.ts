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
  await expect(page.getByRole("heading", { name: /Want to watch/ })).toBeVisible();
  const movie = page.locator(".movie").filter({ hasText: "The Matrix" }).first();
  await expect(movie).toBeVisible();

  // --- mark watched (optimistic) -> moves to the Watched section ---
  await movie.getByRole("button", { name: "✓ Watched" }).click();
  await expect(page.getByRole("heading", { name: /^Watched/ })).toBeVisible();
  await expect(
    page.locator(".movie.is-watched").filter({ hasText: "The Matrix" }),
  ).toBeVisible();

  // Survives a reload — it was really persisted, not just optimistic UI.
  await page.reload();
  await expect(
    page.locator(".movie.is-watched").filter({ hasText: "The Matrix" }),
  ).toBeVisible();

  // --- invite link (opens in a modal) ---
  await page.getByRole("button", { name: /Invite someone/ }).click();
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
  await ownerPage.getByRole("button", { name: /Invite someone/ }).click();
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
