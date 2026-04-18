import { expect, test } from "@playwright/test";

import { setupShellReadyWorkspace } from "./helpers/shellReady";

test.describe.configure({ mode: "serial" });
setupShellReadyWorkspace(test);

const API = "http://localhost:8000/api";

type SoulSummary = {
  id: string;
  role: string;
};

type SoulListResponse = {
  total: number;
  items: SoulSummary[];
};

async function apiGet(path: string) {
  const res = await fetch(`${API}${path}`);
  return res.json();
}

async function apiDelete(path: string) {
  return fetch(`${API}${path}`, { method: "DELETE" });
}

async function createSoulViaApi(role: string) {
  const res = await fetch(`${API}/souls`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      id: role,
      kind: "soul",
      name: role,
      role,
      system_prompt: "E2E test soul prompt",
    }),
  });
  return res.json();
}

test.describe("Souls CRUD", () => {
  const testSoulName = `e2e-soul-${Date.now()}`;
  const testSoulNameEdited = `${testSoulName}-edited`;
  let createdSoulId: string | null = null;

  test.beforeAll(async () => {
    const data = await createSoulViaApi(testSoulName);
    createdSoulId = data.id ?? null;
  });

  test.afterAll(async () => {
    if (createdSoulId) {
      await apiDelete(`/souls/${createdSoulId}`);
    }
  });

  test("list souls", async ({ page }) => {
    await page.goto("/souls");
    await expect(page.getByRole("main").getByRole("heading", { name: "Souls" })).toBeVisible({
      timeout: 10000,
    });
  });

  test("create soul via the current form route", async ({ page }) => {
    const createName = `${testSoulName}-ui`;
    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    const beforeData = (await apiGet("/souls")) as SoulListResponse;
    const countBefore = beforeData.total;

    await page.getByRole("button", { name: /New Soul/i }).click();
    await expect(page).toHaveURL(/\/souls\/new$/, { timeout: 10000 });

    await page.getByLabel("Name").fill(createName);
    await page.getByLabel("System Prompt").fill("E2E test soul prompt");
    await page.getByRole("button", { name: "Create Soul" }).click();

    await expect(page).toHaveURL(/\/souls$/, { timeout: 10000 });
    await expect(page.getByText(createName, { exact: true }).first()).toBeVisible({
      timeout: 10000,
    });

    const afterData = (await apiGet("/souls")) as SoulListResponse;
    const created = afterData.items.find((soul) => soul.role === createName);
    expect(created).toBeDefined();
    expect(afterData.total).toBeGreaterThanOrEqual(countBefore + 1);

    if (created?.id) {
      await apiDelete(`/souls/${created.id}`);
    }
  });

  test("edit soul via the current form route", async ({ page }) => {
    expect(createdSoulId).not.toBeNull();

    await page.goto(`/souls/${createdSoulId}/edit`);
    await expect(page.getByRole("heading", { name: "Edit Soul" })).toBeVisible({
      timeout: 10000,
    });

    await page.getByLabel("Name").fill(testSoulNameEdited);
    await page.getByRole("button", { name: "Save Changes" }).click();

    await expect(page).toHaveURL(/\/souls$/, { timeout: 10000 });
    await expect(page.getByText(testSoulNameEdited, { exact: true }).first()).toBeVisible({
      timeout: 10000,
    });

    const afterData = (await apiGet("/souls")) as SoulListResponse;
    const updated = afterData.items.find((soul) => soul.id === createdSoulId);
    expect(updated?.role).toBe(testSoulNameEdited);
  });

  test("clicking a soul row opens the edit route", async ({ page }) => {
    expect(createdSoulId).not.toBeNull();

    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    await expect(page.getByText(testSoulNameEdited, { exact: true }).first()).toBeVisible({
      timeout: 10000,
    });
    await page.getByRole("row", { name: new RegExp(testSoulNameEdited) }).click();
    await expect(page).toHaveURL(new RegExp(`/souls/${createdSoulId}/edit$`), {
      timeout: 10000,
    });
    await expect(page.getByRole("heading", { name: "Edit Soul" })).toBeVisible();
  });
});
