/**
 * Real E2E integration tests for Settings page — NO MOCKS.
 * Prerequisites: API on localhost:8000, GUI on localhost:3000
 */
import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const API = "http://localhost:8000/api";

async function apiGet(path: string) {
  const res = await fetch(`${API}${path}`);
  return res.json();
}

test.describe("Settings page", () => {
  test("Settings page renders at /settings", async ({ page }) => {
    await page.goto("/settings");
    await expect(
      page.getByRole("heading", { name: /Global Settings/i })
    ).toBeVisible({ timeout: 10000 });
  });

  test("Settings page has tabs (Providers, Models, Budgets)", async ({
    page,
  }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    await expect(
      page.getByRole("button", { name: /Providers/i })
    ).toBeVisible({ timeout: 10000 });
    await expect(
      page.getByRole("button", { name: /Models/i })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Budgets/i })
    ).toBeVisible();
  });

  test("Providers tab is active by default", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    const providersButton = page.getByRole("button", { name: /Providers/i }).first();
    await expect(providersButton).toBeVisible({ timeout: 10000 });
    await expect(providersButton).toHaveClass(/text-foreground/);
    await expect(page.getByRole("heading", { name: "Providers" })).toBeVisible();
  });

  test("Tab navigation works — click Models tab, verify content changes", async ({
    page,
  }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /Models/i }).first().click();
    await expect(
      page.getByRole("heading", { name: /Models/i })
    ).toBeVisible({ timeout: 5000 });
  });

  test("Tab navigation works — click Budgets tab, verify content changes", async ({
    page,
  }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /Budgets/i }).first().click();
    await expect(
      page.getByRole("heading", { name: "Budgets", exact: true })
    ).toBeVisible({ timeout: 5000 });
  });

  test("Provider list shows real providers from API", async ({ page }) => {
    const data = await apiGet("/settings/providers");
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    if (data.items?.length > 0) {
      await expect(
        page.getByText(data.items[0].name, { exact: true }).first()
      ).toBeVisible({ timeout: 10000 });
    } else {
      await expect(
        page.getByText(/No providers configured/i)
      ).toBeVisible({ timeout: 10000 });
    }
  });

  test("If providers exist: verify provider card shows name and status", async ({
    page,
  }) => {
    const data = await apiGet("/settings/providers");
    const hasProviders = data.items?.length > 0;

    test.skip(!hasProviders, "No providers in API");

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    const providerName = data.items[0].name;
    const card = page.locator(".rounded-lg").filter({
      has: page.getByText(providerName),
    });
    await expect(card).toBeVisible({ timeout: 10000 });
    await expect(card).toContainText(providerName);
    await expect(
      card.getByText(/Active|Error|Offline|Rate Limited/i)
    ).toBeVisible();
  });

  test("Models tab content renders", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /Models/i }).first().click();
    await expect(
      page.getByRole("heading", { name: /Models/i })
    ).toBeVisible({ timeout: 5000 });
    await expect(
      page.getByText(/Model defaults|Provider|Model/i).first()
    ).toBeVisible({ timeout: 5000 });
  });

  test("Budgets tab content renders", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /Budgets/i }).first().click();
    await expect(
      page.getByRole("heading", { name: "Budgets", exact: true })
    ).toBeVisible({ timeout: 5000 });
  });
});
