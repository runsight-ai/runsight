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

test.describe("Workflows CRUD", () => {
  const testWorkflowName = `e2e-workflow-${Date.now()}`;
  let createdWorkflowId: string | null = null;

  test.afterAll(async () => {
    if (createdWorkflowId) {
      await apiDelete(`/workflows/${createdWorkflowId}`);
    }
  });

  test("list workflows", async ({ page }) => {
    await page.goto("/workflows");
    const heading = page.getByRole("main").getByRole("heading", { name: "Workflows" });
    const emptyState = page.getByText(/No workflows yet|Create your first workflow/i);
    await expect(heading.or(emptyState).first()).toBeVisible({ timeout: 10000 });
  });

  test("create workflow", async ({ page }) => {
    await page.goto("/workflows");
    await page.waitForLoadState("networkidle");

    const beforeData = await apiGet("/workflows");
    const countBefore = beforeData.total;

    await page.getByRole("button", { name: /New Workflow/i }).first().click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    await modal.getByPlaceholder(/Enter workflow name/i).fill(testWorkflowName);
    await modal.getByPlaceholder(/Describe what this workflow does/i).fill("E2E test workflow description");
    await modal.getByRole("button", { name: /Create/i }).click();

    // Verify navigation to canvas
    await expect(page).toHaveURL(/\/workflows\//, { timeout: 15000 });

    const afterData = await apiGet("/workflows");
    const created = afterData.items.find((w: any) => w.name === testWorkflowName);
    expect(created).toBeDefined();
    expect(afterData.total).toBe(countBefore + 1);
    createdWorkflowId = created.id;
  });

  test("delete workflow", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created in previous test");

    await page.goto("/workflows");
    await page.waitForLoadState("networkidle");

    const rowLocator = page.getByRole('row', { name: testWorkflowName });
    await rowLocator.locator('button').first().click();
    await page.getByRole('menuitem', { name: /Delete/i }).click();

    const confirmModal = page.getByRole("dialog");
    await expect(confirmModal).toBeVisible({ timeout: 5000 });
    await confirmModal.getByRole("button", { name: "Delete" }).click();

    await expect(confirmModal).not.toBeVisible({ timeout: 10000 });
    await expect(page.getByText(testWorkflowName, { exact: true })).not.toBeVisible({ timeout: 10000 });

    const afterData = await apiGet("/workflows");
    const deleted = afterData.items.find((w: any) => w.id === createdWorkflowId);
    expect(deleted).toBeUndefined();
    
    createdWorkflowId = null;
  });
});
