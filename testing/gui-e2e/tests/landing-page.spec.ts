/**
 * Real E2E tests for landing page — NO MOCKS.
 *
 * Prerequisites: API on localhost:8000, GUI on localhost:3000
 * Run: pnpm -C testing/gui-e2e test -- landing-page --reporter=list --retries=0
 */
import { test, expect } from "@playwright/test";

test.describe("Landing page", () => {
  test("navigate to /landing → page renders with content", async ({ page }) => {
    await page.goto("/landing");
    await expect(page).toHaveURL(/\/landing/);

    await expect(
      page.getByRole("main").getByRole("heading", { name: /Orchestrate AI Agents/i })
    ).toBeVisible({ timeout: 10000 });
  });

  test("landing page has Get Started button (CTA)", async ({ page }) => {
    await page.goto("/landing");

    await expect(
      page.getByRole("link", { name: /Get Started/i })
    ).toBeVisible({ timeout: 10000 });
  });

  test("clicking Get Started navigates to /onboarding", async ({ page }) => {
    await page.goto("/landing");

    await page.getByRole("link", { name: /Get Started/i }).click();

    await expect(page).toHaveURL(/\/onboarding/);
  });

  test("landing page shows product name RUNSIGHT", async ({ page }) => {
    await page.goto("/landing");

    await expect(page.getByText("RUNSIGHT", { exact: true })).toBeVisible({
      timeout: 10000,
    });
  });
});
