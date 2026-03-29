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

test.describe("Souls CRUD", () => {
  const testSoulName = `e2e-soul-${Date.now()}`;
  const testSoulNameEdited = `${testSoulName}-edited`;
  let createdSoulId: string | null = null;

  type NamedEntity = {
    id: string;
    name: string;
  };

  type NamedEntityListResponse = {
    total: number;
    items: NamedEntity[];
  };

  test.afterAll(async () => {
    if (createdSoulId) {
      await apiDelete(`/souls/${createdSoulId}`);
    }
  });

  test("list souls", async ({ page }) => {
    await page.goto("/souls");
    await expect(page.getByRole("main").getByRole("heading", { name: "Souls" })).toBeVisible({ timeout: 10000 });
  });

  test("create soul", async ({ page }) => {
    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    const beforeData = (await apiGet("/souls")) as NamedEntityListResponse;
    const countBefore = beforeData.total;

    await page.getByRole("button", { name: /New Soul/i }).first().click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    await modal.getByPlaceholder(/Enter soul name/i).fill(testSoulName);
    await modal.getByPlaceholder(/Enter the system prompt that defines/i).fill("E2E test soul prompt");
    await modal.getByRole("button", { name: /Create Soul/i }).click();

    await expect(modal).not.toBeVisible({ timeout: 10000 });
    await expect(page.getByText(testSoulName, { exact: true })).toBeVisible({ timeout: 10000 });

    const afterData = (await apiGet("/souls")) as NamedEntityListResponse;
    const created = afterData.items.find((s) => s.name === testSoulName);
    expect(created).toBeDefined();
    expect(afterData.total).toBeGreaterThanOrEqual(countBefore + 1);
    createdSoulId = created.id;
  });

  test("edit soul", async ({ page }) => {
    test.skip(!createdSoulId, "Soul was not created in previous test");

    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    const rowLocator = page.getByRole("row", { name: new RegExp(testSoulName) });
    await rowLocator.getByRole("button").first().click();
    await page.getByRole("menuitem", { name: /Edit/i }).click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    await modal.getByPlaceholder(/Enter soul name/i).fill(testSoulNameEdited);
    await modal.getByRole("button", { name: /Save Changes/i }).click();

    await expect(modal).not.toBeVisible({ timeout: 10000 });
    await expect(page.getByText(testSoulNameEdited, { exact: true })).toBeVisible({ timeout: 10000 });

    const afterData = (await apiGet("/souls")) as NamedEntityListResponse;
    const updated = afterData.items.find((s) => s.id === createdSoulId);
    expect(updated.name).toBe(testSoulNameEdited);
  });

  test("delete soul", async ({ page }) => {
    test.skip(!createdSoulId, "Soul was not created in previous test");

    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    const rowLocator = page.getByRole("row", { name: new RegExp(testSoulNameEdited) });
    await rowLocator.getByRole("button").first().click();
    await page.getByRole("menuitem", { name: /Delete/i }).click();

    const confirmModal = page.getByRole("dialog");
    await expect(confirmModal).toBeVisible({ timeout: 5000 });
    await confirmModal.getByRole("button", { name: "Delete" }).click();

    await expect(confirmModal).not.toBeVisible({ timeout: 10000 });
    await expect(page.getByText(testSoulNameEdited, { exact: true })).not.toBeVisible({ timeout: 10000 });

    const afterData = (await apiGet("/souls")) as NamedEntityListResponse;
    const deleted = afterData.items.find((s) => s.id === createdSoulId);
    expect(deleted).toBeUndefined();
    
    createdSoulId = null;
  });
});
