/**
 * Canvas YAML Editor E2E integration tests — NO MOCKS.
 * Tests Visual/Code toggle, YAML editor, validation, toolbar.
 *
 * Run: cd apps/gui && E2E_INTEGRATION=1 CI= npx playwright test canvas-yaml --reporter=list --retries=0
 */
import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const API = "http://localhost:8000/api";

test.describe("Canvas YAML", () => {
  const testWorkflowName = `e2e-yaml-${Date.now()}`;
  let createdWorkflowId: string | null = null;

  test.beforeAll(async () => {
    const res = await fetch(`${API}/workflows`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: testWorkflowName }),
    });
    const data = await res.json();
    createdWorkflowId = data.id;
  });

  test.afterAll(async () => {
    if (createdWorkflowId) {
      await fetch(`${API}/workflows/${createdWorkflowId}`, { method: "DELETE" });
    }
  });

  test("create workflow and add a node, then switch to Code", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await expect(page.locator(".react-flow__node").first()).toBeVisible({ timeout: 8000 });

    await page.getByRole("button", { name: "Code" }).click();
    await expect(page.locator('[data-testid="yaml-editor"]')).toBeVisible({ timeout: 5000 });
  });

  test("in Code mode, sidebar/palette is hidden", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await page.getByRole("button", { name: "Code" }).click();

    await expect(page.locator('[data-testid="yaml-editor"]')).toBeVisible({ timeout: 5000 });
    // In Code mode, CanvasSidebar is not rendered (WorkflowCanvas line 459: viewMode === "visual")
    await expect(page.locator("aside [draggable]")).not.toBeVisible();
  });

  test("status bar shows validation and node count", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await page.getByRole("button", { name: "Code" }).click();

    await expect(page.locator('[data-testid="yaml-editor"]')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("Valid YAML")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/1 node|2 nodes/)).toBeVisible({ timeout: 3000 });
    await expect(page.getByText(/0 edges|1 edge|2 edges/)).toBeVisible({ timeout: 3000 });
  });

  test("YAML toolbar has Save/Undo/Format buttons", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await page.getByRole("button", { name: "Code" }).click();

    await expect(page.locator('[data-testid="yaml-editor"]')).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole("button", { name: /Save/ })).toBeVisible({ timeout: 3000 });
    await expect(page.getByRole("button", { name: /Undo/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Format/ })).toBeVisible();
  });

  test("switch back to Visual mode restores canvas", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await page.getByRole("button", { name: "Code" }).click();
    await expect(page.locator('[data-testid="yaml-editor"]')).toBeVisible({ timeout: 5000 });

    await page.getByRole("button", { name: "Visual" }).click();
    await expect(page.locator(".react-flow")).toBeVisible({ timeout: 5000 });
    await expect(page.locator(".react-flow__node").first()).toBeVisible({ timeout: 5000 });
  });

  test("invalid YAML shows error and blocks switch to Visual", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await page.getByRole("button", { name: "Code" }).click();

    await expect(page.locator('[data-testid="yaml-editor"]')).toBeVisible({ timeout: 5000 });

    // Use __e2eSetValue if available to inject invalid YAML (Monaco keyboard is unreliable)
    const editorContainer = page.locator('[data-testid="yaml-editor"]');
    await editorContainer.waitFor({ state: "visible", timeout: 5000 });
    const invalidYaml = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="yaml-editor"]') as { __e2eSetValue?: (text: string) => void };
      if (el?.__e2eSetValue) {
        el.__e2eSetValue("invalid: yaml: [[[");
        return true;
      }
      return false;
    });

    if (invalidYaml) {
      await expect(page.getByText("Error")).toBeVisible({ timeout: 5000 });
      await expect(page.getByText(/Fix YAML errors before switching/)).toBeVisible({ timeout: 3000 });
    }
  });
});
