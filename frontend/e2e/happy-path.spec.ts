import { expect, test } from "@playwright/test";

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

  // --- create a list ---
  await page.getByPlaceholder("New list name").fill(listName);
  await page.getByRole("button", { name: "Create" }).click();

  const card = page.getByRole("link", { name: new RegExp(listName) });
  await expect(card).toBeVisible();
  await card.click();

  await expect(page.getByRole("heading", { name: listName })).toBeVisible();
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

  // --- clean up ---
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Delete list" }).click();
  await expect(page.getByRole("heading", { name: "Your lists" })).toBeVisible();
  await expect(page.getByRole("link", { name: new RegExp(listName) })).toHaveCount(0);
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
  await ownerPage.getByPlaceholder("New list name").fill(listName);
  await ownerPage.getByRole("button", { name: "Create" }).click();
  await ownerPage.getByRole("link", { name: new RegExp(listName) }).click();
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
  ownerPage.once("dialog", (d) => d.accept());
  await ownerPage.getByRole("button", { name: "Delete list" }).click();
  await owner.close();
  await visitor.close();
});
