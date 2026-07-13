import { expect, type Page } from "@playwright/test";

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
