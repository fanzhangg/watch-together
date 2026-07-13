import { devices, expect, test } from "@playwright/test";

// Emulates a real phone (viewport + touch + mobile UA), not just a narrow window.
// Pixel 5 rather than an iPhone because its default engine is Chromium — the one
// browser we install — so the emulation is genuine rather than WebKit-in-name-only.
test.use({ ...devices["Pixel 5"] });

test("mobile: add a movie via the floating button, sheet doesn't scroll the page", async ({
  page,
}) => {
  const listName = `M ${Date.now()}`;

  await page.goto("/login");
  await page.getByRole("button", { name: "Dev login" }).tap();

  await page.getByPlaceholder("New list name").fill(listName);
  await page.getByRole("button", { name: "Create" }).tap();
  await page.getByRole("link", { name: new RegExp(listName) }).tap();

  // The header "+ Add movie" is hidden on mobile; the FAB replaces it.
  await expect(page.locator(".actions .add-movie")).toBeHidden();
  // exact: otherwise this also matches the empty-state "+ Add movie" button.
  const fab = page.getByRole("button", { name: "Add movie", exact: true });
  await expect(fab).toBeVisible();

  // The FAB is a comfortable tap target and sits within the viewport.
  const box = (await fab.boundingBox())!;
  expect(box.width).toBeGreaterThanOrEqual(44);
  expect(box.height).toBeGreaterThanOrEqual(44);

  await fab.tap();

  // Search opens as a full-screen sheet.
  const dialog = page.locator(".dialog");
  await expect(dialog).toBeVisible();
  const viewport = page.viewportSize()!;
  const dialogBox = (await dialog.boundingBox())!;
  expect(dialogBox.width).toBeCloseTo(viewport.width, 0);

  // Background scroll is locked while the sheet is open.
  await expect(page.locator("body")).toHaveClass(/no-scroll/);

  await page.getByPlaceholder("Search movies…").fill("the matrix");
  const result = page.locator(".result").filter({ hasText: "The Matrix" }).first();
  await expect(result).toBeVisible({ timeout: 15_000 });
  await result.getByRole("button", { name: "Add" }).tap();
  await page.getByRole("button", { name: "Close" }).tap();

  // Sheet closed -> page scrolls again.
  await expect(page.locator("body")).not.toHaveClass(/no-scroll/);

  const movie = page.locator(".movie").filter({ hasText: "The Matrix" }).first();
  await expect(movie).toBeVisible();

  // Movie action buttons are tappable (>=40px tall).
  const watchedBtn = movie.getByRole("button", { name: "✓ Watched" });
  expect((await watchedBtn.boundingBox())!.height).toBeGreaterThanOrEqual(40);
  await watchedBtn.tap();
  await expect(
    page.locator(".movie.is-watched").filter({ hasText: "The Matrix" }),
  ).toBeVisible();

  // Nothing overflows horizontally — the classic mobile layout bug.
  const scrollW = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(scrollW).toBeLessThanOrEqual(viewport.width + 1);

  // cleanup
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Delete list" }).tap();
  await expect(page.getByRole("heading", { name: "Your lists" })).toBeVisible();
});
