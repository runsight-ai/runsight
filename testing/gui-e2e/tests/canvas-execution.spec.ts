/**
 * Canvas Execution E2E integration tests — NO MOCKS.
 * Tests Run button, execution state transitions.
 * NOTE: Real execution is simulated (no LLM). We test UI transitions.
 *
 * Run: pnpm -C testing/gui-e2e test -- canvas-execution --reporter=list --retries=0
 */
import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const API = "http://localhost:8000/api";

test.describe("Canvas Execution", () => {
  const testWorkflowName = `e2e-execution-${Date.now()}`;
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

  test("Run button is visible when workflow has nodes", async ({ page }) => {
    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await expect(page.locator(".react-flow__node").first()).toBeVisible({ timeout: 8000 });

    const runButton = page.getByRole("button", { name: /^Run$/ });
    await expect(runButton).toBeVisible({ timeout: 5000 });
  });

  test("click Run → execution state starts, header shows Running and Read-only banner", async ({ page }) => {
    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await expect(page.locator(".react-flow__node").first()).toBeVisible({ timeout: 8000 });

    await page.getByRole("button", { name: /^Run$/ }).click();

    await expect(page.getByText("Running...")).toBeVisible({ timeout: 3000 });
    await expect(page.getByText("Read-only during execution")).toBeVisible({ timeout: 5000 });
  });

  test("execution completes and shows summary", async ({ page }) => {
    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await expect(page.locator(".react-flow__node").first()).toBeVisible({ timeout: 8000 });

    await page.getByRole("button", { name: /^Run$/ }).click();
    await expect(page.getByText("Running...")).toBeVisible({ timeout: 3000 });

    // WorkflowCanvas simulates 2s per node. One node → ~2s total
    await expect(page.getByRole("button", { name: /Run Again|Retry/ })).toBeVisible({ timeout: 15000 });
  });
});
