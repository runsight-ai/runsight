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

test.describe("Canvas Workflow", () => {
  const testWorkflowName = `e2e-canvas-test-${Date.now()}`;
  let createdWorkflowId: string | null = null;

  test.afterAll(async () => {
    if (createdWorkflowId) {
      await apiDelete(`/workflows/${createdWorkflowId}`);
    }
  });

  test("create a workflow, navigate to canvas", async ({ page }) => {
    await page.goto("/workflows");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /New Workflow/i }).first().click();
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });
    await modal.getByPlaceholder(/workflow name/i).fill(testWorkflowName);
    await modal.getByRole("button", { name: /Create/i }).click();
    await expect(page).toHaveURL(/\/workflows\//, { timeout: 15000 });

    const data = await apiGet("/workflows");
    const created = data.items.find((w: { name: string }) => w.name === testWorkflowName);
    expect(created).toBeDefined();
    createdWorkflowId = created.id;
  });

  test("verify canvas loads and can save workflow state", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await expect(page.getByTestId("canvas-reactflow")).toBeVisible({ timeout: 10000 });

    // Save without editing should still persist baseline canvas state safely.
    await page.getByTestId("canvas-save").click();
    await expect(page.getByTestId("canvas-save")).toContainText("Save");

    const saved = await apiGet(`/workflows/${createdWorkflowId}`);
    expect(saved.canvas_state).toBeDefined();
    expect(saved.yaml === null || typeof saved.yaml === "string").toBeTruthy();
  });
});
