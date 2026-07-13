import { expect, type Page } from "@playwright/test";

/**
 * Create a list from the lists page. Mirrors "add a movie": a button opens a
 * dialog, rather than an inline form on the page.
 */
export async function createList(page: Page, name: string) {
  // Whichever opener is showing: the header button (desktop), the empty-state
  // button, or the floating button (mobile, where the header one is hidden).
  await page
    .locator(".lists-actions button:visible, .empty button:visible, .fab:visible")
    .first()
    .click();

  const dialog = page.getByRole("dialog", { name: "New list" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("List name").fill(name);
  await dialog.getByRole("button", { name: "Create list" }).click();

  await expect(dialog).toBeHidden();
  await expect(page.getByRole("link", { name: new RegExp(name) })).toBeVisible();
}

/** Create a list and open it. */
export async function createAndOpenList(page: Page, name: string) {
  await createList(page, name);
  await page.getByRole("link", { name: new RegExp(name) }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
}

/**
 * Delete the list currently open. Deletion lives behind the "⋯" menu and is
 * confirmed in a dialog (no native confirm()).
 */
export async function deleteOpenList(page: Page) {
  await page.getByRole("button", { name: "List options" }).click();
  await page.getByRole("menuitem", { name: "Delete list" }).click();

  const confirm = page.getByRole("dialog");
  await expect(confirm).toBeVisible();
  await confirm.getByRole("button", { name: "Delete list" }).click();

  await expect(page.getByRole("heading", { name: "Your lists" })).toBeVisible();
}
