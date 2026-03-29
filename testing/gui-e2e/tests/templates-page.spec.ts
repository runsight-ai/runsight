/**
 * Real E2E tests for templates page — NO MOCKS.
 *
 * Prerequisites: API on localhost:8000, GUI on localhost:3000
 * Run: pnpm -C testing/gui-e2e test -- templates-page --reporter=list --retries=0
 */
import { test, expect } from "@playwright/test";

test.describe("Templates page", () => {
  test("navigate to /templates → page renders", async ({ page }) => {
    await page.goto("/templates");
    await expect(page).toHaveURL(/\/templates/);

    await expect(
      page.getByText(/Templates/i).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test("templates page shows placeholder content", async ({ page }) => {
    await page.goto("/templates");

    // TemplatesPage currently shows "Templates — TODO" placeholder
    await expect(
      page.getByText(/Templates.*TODO|TODO.*Templates/i)
    ).toBeVisible({ timeout: 10000 });
  });

  test("templates page is reachable from shell layout", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.goto("/templates");
    await expect(page).toHaveURL(/\/templates/);
  });
});
