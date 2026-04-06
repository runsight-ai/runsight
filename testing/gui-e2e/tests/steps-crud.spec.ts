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

test.describe("Steps CRUD", () => {
  const testStepName = `e2e-step-${Date.now()}`;
  const testStepNameEdited = `${testStepName}-edited`;
  let createdStepId: string | null = null;

  test.beforeAll(async () => {
    const res = await fetch(`${API}/steps`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: testStepName, description: "E2E test step description" }),
    });
    const data = await res.json();
    createdStepId = data.id ?? null;
  });

  test.afterAll(async () => {
    if (createdStepId) {
      await apiDelete(`/steps/${createdStepId}`);
    }
  });

  test("list steps", async ({ page }) => {
    await page.goto("/steps");
    await expect(
      page.getByRole("main").getByRole("heading", { name: "Steps", exact: true, level: 1 })
    ).toBeVisible({ timeout: 10000 });
  });

  test("create step via UI", async ({ page }) => {
    const createName = `${testStepName}-ui`;
    await page.goto("/steps");
    await page.waitForLoadState("networkidle");

    const beforeData = await apiGet("/steps");
    const countBefore = beforeData.total;

    await page.getByRole("button", { name: /New Step/i }).first().click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    await modal.getByPlaceholder(/Enter step name/i).fill(createName);
    await modal.getByPlaceholder(/Describe what this step does/i).fill("E2E test step description");
    await modal.getByRole("button", { name: /Create/i }).click();

    await expect(modal).not.toBeVisible({ timeout: 10000 });
    await expect(page.getByText(createName, { exact: true })).toBeVisible({ timeout: 10000 });

    const afterData = await apiGet("/steps");
    const created = afterData.items.find((s: { name: string }) => s.name === createName);
    expect(created).toBeDefined();
    expect(afterData.total).toBeGreaterThanOrEqual(countBefore + 1);

    // Clean up the UI-created step
    if (created?.id) {
      await apiDelete(`/steps/${created.id}`);
    }
  });

  test("edit step", async ({ page }) => {
    await page.goto("/steps");
    await page.waitForLoadState("networkidle");

    const rowLocator = page.getByRole("row", { name: new RegExp(testStepName) });
    await rowLocator.getByRole("button").first().click();
    await page.getByRole("menuitem", { name: /Edit/i }).click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    await modal.getByPlaceholder(/Enter step name/i).fill(testStepNameEdited);
    await modal.getByRole("button", { name: /Save Changes/i }).click();

    await expect(modal).not.toBeVisible({ timeout: 10000 });
    await expect(page.getByText(testStepNameEdited, { exact: true })).toBeVisible({ timeout: 10000 });

    const afterData = await apiGet("/steps");
    const updated = afterData.items.find((s: { id: string }) => s.id === createdStepId);
    expect(updated).toBeDefined();
    expect(updated!.name).toBe(testStepNameEdited);
  });

  test("delete step", async ({ page }) => {
    await page.goto("/steps");
    await page.waitForLoadState("networkidle");

    const rowLocator = page.getByRole("row", { name: new RegExp(testStepNameEdited) });
    await rowLocator.getByRole("button").first().click();
    await page.getByRole("menuitem", { name: /Delete/i }).click();

    const confirmModal = page.getByRole("dialog");
    await expect(confirmModal).toBeVisible({ timeout: 5000 });
    await confirmModal.getByRole("button", { name: "Delete" }).click();

    await expect(confirmModal).not.toBeVisible({ timeout: 10000 });
    await expect(page.getByText(testStepNameEdited, { exact: true })).not.toBeVisible({
      timeout: 10000,
    });

    const afterData = await apiGet("/steps");
    const deleted = afterData.items.find((s: { id: string }) => s.id === createdStepId);
    expect(deleted).toBeUndefined();

    createdStepId = null;
  });
});
