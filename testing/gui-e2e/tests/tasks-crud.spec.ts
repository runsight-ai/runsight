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

test.describe("Tasks CRUD", () => {
  const testTaskName = `e2e-task-${Date.now()}`;
  const testTaskNameEdited = `${testTaskName}-edited`;
  let createdTaskId: string | null = null;

  test.beforeAll(async () => {
    const res = await fetch(`${API}/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: testTaskName, description: "E2E test task description" }),
    });
    const data = await res.json();
    createdTaskId = data.id ?? null;
  });

  test.afterAll(async () => {
    if (createdTaskId) {
      await apiDelete(`/tasks/${createdTaskId}`);
    }
  });

  test("list tasks", async ({ page }) => {
    await page.goto("/tasks");
    await expect(
      page.getByRole("main").getByRole("heading", { name: "Tasks", exact: true, level: 1 })
    ).toBeVisible({ timeout: 10000 });
  });

  test("create task via UI", async ({ page }) => {
    const createName = `${testTaskName}-ui`;
    await page.goto("/tasks");
    await page.waitForLoadState("networkidle");

    const beforeData = await apiGet("/tasks");
    const countBefore = beforeData.total;

    await page.getByRole("button", { name: /New Task/i }).first().click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    await modal.getByPlaceholder(/Enter task name/i).fill(createName);
    await modal.getByPlaceholder(/Describe what this task does/i).fill("E2E test task description");
    await modal.getByRole("button", { name: /Create/i }).click();

    await expect(modal).not.toBeVisible({ timeout: 10000 });
    await expect(page.getByText(createName, { exact: true })).toBeVisible({ timeout: 10000 });

    const afterData = await apiGet("/tasks");
    const created = afterData.items.find((t: { name: string }) => t.name === createName);
    expect(created).toBeDefined();
    expect(afterData.total).toBeGreaterThanOrEqual(countBefore + 1);

    // Clean up the UI-created task
    if (created?.id) {
      await apiDelete(`/tasks/${created.id}`);
    }
  });

  test("edit task", async ({ page }) => {
    await page.goto("/tasks");
    await page.waitForLoadState("networkidle");

    const rowLocator = page.getByRole("row", { name: new RegExp(testTaskName) });
    await rowLocator.getByRole("button").first().click();
    await page.getByRole("menuitem", { name: /Edit/i }).click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    await modal.getByPlaceholder(/Enter task name/i).fill(testTaskNameEdited);
    await modal.getByRole("button", { name: /Save Changes/i }).click();

    await expect(modal).not.toBeVisible({ timeout: 10000 });
    await expect(page.getByText(testTaskNameEdited, { exact: true })).toBeVisible({ timeout: 10000 });

    const afterData = await apiGet("/tasks");
    const updated = afterData.items.find((t: { id: string }) => t.id === createdTaskId);
    expect(updated).toBeDefined();
    expect(updated!.name).toBe(testTaskNameEdited);
  });

  test("delete task", async ({ page }) => {
    await page.goto("/tasks");
    await page.waitForLoadState("networkidle");

    const rowLocator = page.getByRole("row", { name: new RegExp(testTaskNameEdited) });
    await rowLocator.getByRole("button").first().click();
    await page.getByRole("menuitem", { name: /Delete/i }).click();

    const confirmModal = page.getByRole("dialog");
    await expect(confirmModal).toBeVisible({ timeout: 5000 });
    await confirmModal.getByRole("button", { name: "Delete" }).click();

    await expect(confirmModal).not.toBeVisible({ timeout: 10000 });
    await expect(page.getByText(testTaskNameEdited, { exact: true })).not.toBeVisible({
      timeout: 10000,
    });

    const afterData = await apiGet("/tasks");
    const deleted = afterData.items.find((t: { id: string }) => t.id === createdTaskId);
    expect(deleted).toBeUndefined();

    createdTaskId = null;
  });
});
