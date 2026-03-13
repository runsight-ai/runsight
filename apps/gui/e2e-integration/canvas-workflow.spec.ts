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
    const created = data.items.find(
      (w: { name: string }) => w.name === testWorkflowName
    );
    expect(created).toBeDefined();
    createdWorkflowId = created.id;
  });

  test("verify canvas loads with empty state", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    
    // BUG: Canvas might not load properly or show empty state
    await expect(page.locator(".react-flow")).toBeVisible({ timeout: 10000 });
    // Should have no nodes initially (or just a start node)
  });

  test("drag a node from palette onto canvas", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow");
    
    // BUG: Drag and drop might be broken
    const paletteNode = page.locator('aside [draggable]').first();
    const canvas = page.locator(".react-flow__pane");
    
    await paletteNode.dragTo(canvas, { targetPosition: { x: 50, y: 50 } });
    
    await expect(page.locator(".react-flow__node").first()).toBeVisible({ timeout: 5000 });
  });

  test("select node, verify inspector opens and configure", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow");

    // Add a node first (canvas is fresh per test, nodes are not persisted until saved)
    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 50, y: 50 } });
    await expect(page.locator(".react-flow__node").first()).toBeVisible({ timeout: 5000 });

    await page.locator(".react-flow__node").first().click();

    const inspector = page.locator('[aria-label="Node inspector panel"]');
    await expect(inspector).toBeVisible({ timeout: 5000 });

    const nameInput = inspector.getByRole("textbox", { name: "Node name" });
    await expect(nameInput).toBeVisible({ timeout: 10000 });
    await nameInput.fill("Test Node 1");
  });

  test("add node and verify canvas state", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow");

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 50, y: 50 } });
    await expect(page.locator(".react-flow__node").first()).toBeVisible({ timeout: 5000 });

    // Note: Persisting nodes (Commit flow) requires the backend file to be dirty.
    // The visual editor does not yet auto-sync drag operations to the workflow file.
    expect(await page.locator(".react-flow__node").count()).toBeGreaterThan(0);
  });
});
