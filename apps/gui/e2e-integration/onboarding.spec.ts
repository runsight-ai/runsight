import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const API = "http://localhost:8000/api";

async function apiGet(path: string) {
  const res = await fetch(`${API}${path}`);
  return res.json();
}

test.describe("Onboarding", () => {
  test("check onboarding state from real API", async ({ page }) => {
    await page.goto("/");

    const appSettings = await apiGet("/settings/app");
    const providersData = await apiGet("/settings/providers");
    const hasProviders = (providersData?.total ?? providersData?.items?.length ?? 0) > 0;

    // Redirect to /landing only when BOTH no providers AND onboarding not completed
    if (!appSettings.onboarding_completed && !hasProviders) {
      await expect(page).toHaveURL(/.*landing.*/, { timeout: 10000 });
    } else {
      await expect(page).not.toHaveURL(/.*landing.*/, { timeout: 10000 });
    }
  });

  test("walk through onboarding steps if applicable", async ({ page }) => {
    const appSettings = await apiGet("/settings/app");
    test.skip(appSettings.onboarding_completed, "Onboarding already completed");

    // Go to /landing first (where unauthenticated users are redirected)
    await page.goto("/landing");
    await expect(page).toHaveURL(/.*landing.*/, { timeout: 5000 });

    // Click "Get Started" to navigate to /onboarding
    await page.getByRole("link", { name: /Get Started/i }).click();
    await expect(page).toHaveURL(/.*onboarding.*/, { timeout: 5000 });

    // Onboarding wizard shows "Welcome to Runsight"
    await expect(page.getByRole("heading", { name: /Welcome to Runsight/i })).toBeVisible({
      timeout: 10000,
    });

    // Connection test with fake keys fails, so "Complete Setup" never enables.
    // Use "Skip for now" to complete onboarding.
    await page.getByRole("button", { name: /Skip for now/i }).click();

    // Wait for redirect to /
    await expect(page).toHaveURL(/\//, { timeout: 10000 });

    // Poll API until onboarding_completed is persisted (mutation is async)
    let afterSettings: { onboarding_completed?: boolean } = {};
    for (let i = 0; i < 10; i++) {
      afterSettings = await apiGet("/settings/app");
      if (afterSettings.onboarding_completed === true) break;
      await new Promise((r) => setTimeout(r, 500));
    }
    expect(afterSettings.onboarding_completed).toBe(true);
  });

  test("verify completion state persists", async ({ page }) => {
    const appSettings = await apiGet("/settings/app");
    test.skip(!appSettings.onboarding_completed, "Onboarding not completed yet");

    // When completed, visiting / should show dashboard (no redirect to landing)
    await page.goto("/");
    await expect(page).not.toHaveURL(/.*landing.*/, { timeout: 10000 });
  });
});
