/**
 * Real E2E tests for error states — NO MOCKS.
 *
 * Prerequisites: API on localhost:8000, GUI on localhost:3000
 * Run: pnpm -C testing/gui-e2e test -- error-states --reporter=list --retries=0
 */
import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const API = "http://localhost:8000/api";

async function apiGet(path: string) {
  const res = await fetch(`${API}${path}`);
  return res.json();
}

test.describe("Error states: validation", () => {
  test("create soul with empty name → Create button is disabled", async ({
    page,
  }) => {
    await page.goto("/souls/new");
    await page.waitForLoadState("networkidle");

    await page.getByLabel("System Prompt").fill("Test");
    const createBtn = page.getByRole("button", { name: "Create Soul" });
    await expect(createBtn).toBeDisabled();
  });

  test("create soul with whitespace-only name → Create button is disabled", async ({
    page,
  }) => {
    await page.goto("/souls/new");
    await page.waitForLoadState("networkidle");

    await page.getByLabel("Name").fill("   ");
    await page.getByLabel("System Prompt").fill("Test");
    const createBtn = page.getByRole("button", { name: "Create Soul" });
    await expect(createBtn).toBeDisabled();
  });

});

test.describe("Error states: 404 and nonexistent resources", () => {
  test("navigate to /workflows/nonexistent-id → shows not found message", async ({
    page,
  }) => {
    const fakeId = "00000000-0000-0000-0000-000000000000";
    await page.goto(`/workflows/${fakeId}/edit`);
    await page.waitForLoadState("networkidle");

    await expect(page.getByText(/not found/i)).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("link", { name: /back to workflows/i })).toBeVisible();
  });

  test("navigate to /runs/nonexistent-id → shows Run not found", async ({
    page,
  }) => {
    const fakeId = "00000000-0000-0000-0000-000000000000";
    await page.goto(`/runs/${fakeId}`);
    await page.waitForLoadState("networkidle");

    await expect(
      page.getByText(/Run not found|not found/i)
    ).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Error states: souls page when API is healthy", () => {
  test("navigate to /souls when API is healthy → no error banners shown", async ({
    page,
  }) => {
    const data = await apiGet("/souls");
    expect(data).toBeDefined();
    expect(Array.isArray(data.items)).toBe(true);

    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    // Should not show "Failed to load souls" error state
    await expect(
      page.getByText(/Failed to load souls/i)
    ).not.toBeVisible();
  });
});

test.describe("Error states: settings provider invalid key", () => {
  test("settings providers tab loads without error", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    await expect(
      page.getByRole("tab", { name: /Providers/i }).or(page.getByText(/Providers/i).first())
    ).toBeVisible({ timeout: 10000 });
  });

  // Submit provider with invalid API key: AddProviderDialog uses ProviderSetup wizard
  // Real API key validation happens on backend - we cannot easily test invalid key without mocking
  // Skip: would require creating provider then testing connection; API may reject invalid keys
  // Document: Provider Test Connection shows Failed when key is invalid (manual verification)
});
