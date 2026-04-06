import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const API = "http://localhost:8000/api";

async function apiGet(path: string) {
  const res = await fetch(`${API}${path}`);
  return res.json();
}

async function apiDelete(path: string) {
  return fetch(`${API}${path}`, { method: "DELETE" });
}

test.describe("Settings: Providers CRUD", () => {
  const testProviderName = `e2e-test-provider-${Date.now()}`;
  let createdProviderId: string | null = null;

  // Determine provider availability once for the whole suite
  let hasOllama = false;
  let hasOpenAI = false;

  test.beforeAll(async () => {
    hasOllama = await fetch("http://localhost:11434/api/tags")
      .then((r) => r.ok)
      .catch(() => false);
    hasOpenAI = Boolean(
      process.env.OPENAI_API_KEY && process.env.OPENAI_API_KEY.length > 10
    );
  });

  test.afterAll(async () => {
    if (createdProviderId) {
      await apiDelete(`/settings/providers/${createdProviderId}`);
    }
  });

  test("providers page lists real providers from API", async ({ page }) => {
    await page.goto("/settings");

    const data = await apiGet("/settings/providers");

    // We expect at least one provider (Anthropic) to be there.
    if (data.items && data.items.length > 0) {
      await expect(
        page.getByText(data.items[0].name, { exact: true }).first()
      ).toBeVisible({ timeout: 10000 });
    }
  });

  test("add provider via form → appears in list and API", async ({ page }) => {
    // Ollama: requires localhost:11434. OpenAI: requires real API key. Done enables only after successful connection.
    test.skip(
      !hasOllama && !hasOpenAI,
      "Ollama (localhost:11434) or OPENAI_API_KEY required"
    );

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    const beforeData = await apiGet("/settings/providers");
    const countBefore = beforeData.items ? beforeData.items.length : 0;

    await page.getByRole("button", { name: /Add Provider/i }).first().click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    if (hasOllama) {
      // Step 1: Select Ollama from "Other Provider" dropdown
      await modal.getByRole("combobox").click();
      await page.getByRole("option", { name: /Ollama/i }).click();
      await modal.getByPlaceholder(/Ollama/i).fill(testProviderName);
    } else {
      // Step 1: Select OpenAI
      await modal.getByRole("button", { name: /OpenAI/i }).click();
      await modal.getByPlaceholder(/OpenAI/i).fill(testProviderName);
      await modal.locator('input[type="password"]').fill(process.env.OPENAI_API_KEY!);
    }

    const doneButton = modal.getByRole("button", { name: /Done/i });
    await expect(doneButton).toBeEnabled({ timeout: 15000 });
    await doneButton.click();

    await expect(modal).not.toBeVisible({ timeout: 10000 });

    await expect(page.getByText(testProviderName, { exact: true }).first()).toBeVisible({ timeout: 10000 });

    const afterData = await apiGet("/settings/providers");
    const created = afterData.items?.find(
      (p: { name: string }) => p.name === testProviderName
    );
    expect(created).toBeDefined();
    expect(afterData.items.length).toBeGreaterThanOrEqual(countBefore + 1);
    createdProviderId = created.id;
  });

  test("test connection on a provider", async ({ page }) => {
    test.skip(!hasOllama && !hasOpenAI, "Ollama or OPENAI_API_KEY required — provider was not created");

    await page.goto("/settings");

    const card = page.locator(".rounded-lg").filter({
      has: page.getByRole("heading", { name: testProviderName }),
    });
    await card.getByRole("button", { name: /Test Connection/i }).click();

    await expect(page.getByText(/Connection successful|Connection failed|Connected|Failed/i)).toBeVisible({ timeout: 10000 });
  });

  test("delete provider → confirm dialog, verify removed", async ({ page }) => {
    test.skip(!hasOllama && !hasOpenAI, "Ollama or OPENAI_API_KEY required — provider was not created");

    await page.goto("/settings");

    // Use native confirm handler — ProvidersTab uses window.confirm()
    page.once("dialog", (d) => d.accept());

    const card = page.locator(".rounded-lg").filter({
      has: page.getByRole("heading", { name: testProviderName }),
    });
    await card.getByRole("button", { name: /Remove provider/i }).click();

    await expect(page.getByText(testProviderName)).not.toBeVisible({ timeout: 10000 });

    const afterData = await apiGet("/settings/providers");
    const stillExists = afterData.items?.find(
      (p: { id: string }) => p.id === createdProviderId
    );
    expect(stillExists).toBeFalsy();

    createdProviderId = null;
  });
});
