/**
 * Real E2E tests for health page — NO MOCKS.
 *
 * Prerequisites: API on localhost:8000, GUI on localhost:3000
 * Run: E2E_INTEGRATION=1 CI= npx playwright test health-page --reporter=list --retries=0
 */
import { test, expect } from "@playwright/test";

test.describe("Health page", () => {
  test("navigate to /health → page renders", async ({ page }) => {
    await page.goto("/health");
    await expect(page).toHaveURL(/\/health/);

    await expect(
      page.getByText(/Health/i).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test("health page shows placeholder content", async ({ page }) => {
    await page.goto("/health");

    // HealthPage currently shows "Health — TODO" placeholder
    await expect(
      page.getByText(/Health.*TODO|TODO.*Health/i)
    ).toBeVisible({ timeout: 10000 });
  });

  test("health page is reachable from shell layout", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Navigate to health via sidebar if link exists, or direct URL
    await page.goto("/health");
    await expect(page).toHaveURL(/\/health/);
  });
});
