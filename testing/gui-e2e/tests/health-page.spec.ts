/**
 * Real E2E tests for retired health route behavior — NO MOCKS.
 *
 * Prerequisites: API on localhost:8000, GUI on localhost:3000
 * Run: pnpm -C testing/gui-e2e test -- health-page --reporter=list --retries=0
 */
import { test, expect } from "@playwright/test";

test.describe("Retired health route", () => {
  test("direct visits to /health redirect to the supported shell", async ({ page }) => {
    await page.goto("/health");

    await expect(page).not.toHaveURL(/\/health/);
    await expect(page).toHaveURL(/\/$/);
  });

  test("retired /health bookmarks no longer render placeholder content", async ({
    page,
  }) => {
    await page.goto("/health");

    await expect(page.getByText(/Health.*TODO|TODO.*Health/i)).toHaveCount(0);
    await expect(page.getByText(/^Health$/i)).toHaveCount(0);
  });

  test("shell navigation no longer exposes a Health route", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await expect(
      page.getByRole("navigation").getByRole("link", { name: "Health" })
    ).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Health" })).toHaveCount(0);
  });
});
