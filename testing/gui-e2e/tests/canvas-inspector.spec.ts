/**
 * Canvas Inspector E2E integration tests — NO MOCKS.
 * Tests inspector panel, node selection, tabs, conditions.
 *
 * Run: pnpm -C testing/gui-e2e test -- canvas-inspector --reporter=list --retries=0
 */
import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const API = "http://localhost:8000/api";

async function apiDelete(path: string) {
  return fetch(`${API}${path}`, { method: "DELETE" });
}

test.describe("Canvas Inspector", () => {
  const testWorkflowName = `e2e-inspector-${Date.now()}`;
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
      await apiDelete(`/workflows/${createdWorkflowId}`);
    }
  });

  test("create workflow and navigate to canvas", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created in beforeAll");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await expect(page.locator(".react-flow")).toBeVisible({ timeout: 15000 });
  });

  test("drag a node from palette onto canvas", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");

    await expect(paletteNode).toBeVisible({ timeout: 5000 });
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await expect(page.locator(".react-flow__node").first()).toBeVisible({ timeout: 8000 });
  });

  test("click node → inspector panel opens", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await expect(page.locator(".react-flow__node").first()).toBeVisible({ timeout: 8000 });

    await page.locator(".react-flow__node").first().click();

    const inspector = page.locator('[aria-label="Node inspector panel"]');
    await expect(inspector).toBeVisible({ timeout: 5000 });
  });

  test("inspector Overview tab shows node name textbox and Step Type", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await page.locator(".react-flow__node").first().click();

    const inspector = page.locator('[aria-label="Node inspector panel"]');
    await expect(inspector).toBeVisible({ timeout: 5000 });

    const nameInput = inspector.getByRole("textbox", { name: "Node name" });
    await expect(nameInput).toBeVisible({ timeout: 5000 });

    await expect(inspector.getByText("Step Type")).toBeVisible({ timeout: 3000 });
    // Step Type shows a badge (e.g. Linear, Placeholder from palette)
    await expect(inspector.locator("[data-slot='badge']").first()).toBeVisible({ timeout: 3000 });
  });

  test("edit node name in Overview → name input updates", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await page.locator(".react-flow__node").first().click();

    const inspector = page.locator('[aria-label="Node inspector panel"]');
    const nameInput = inspector.getByRole("textbox", { name: "Node name" });
    await nameInput.fill("My Custom Node");
    await expect(nameInput).toHaveValue("My Custom Node");
  });

  test("switch to Prompt tab → shows editor area", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await page.locator(".react-flow__node").first().click();

    const inspector = page.locator('[aria-label="Node inspector panel"]');
    await inspector.getByRole("tab", { name: "Prompt" }).click();
    await expect(inspector.getByRole("textbox", { name: "Prompt editor" })).toBeVisible({ timeout: 5000 });
  });

  test("switch to Conditions tab → shows Simple/Expression/Python mode buttons", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await page.locator(".react-flow__node").first().click();

    const inspector = page.locator('[aria-label="Node inspector panel"]');
    await inspector.getByRole("tab", { name: "Conditions" }).click();
    await expect(inspector.getByRole("tabpanel", { name: "Conditions tab" })).toBeVisible({ timeout: 5000 });
    await expect(inspector.getByText("Simple")).toBeVisible();
    await expect(inspector.getByText("Expression")).toBeVisible();
    await expect(inspector.getByText("Python")).toBeVisible();
  });

  test("Conditions Simple mode shows IF/THEN/ELSE", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await page.locator(".react-flow__node").first().click();

    const inspector = page.locator('[aria-label="Node inspector panel"]');
    await inspector.getByRole("tab", { name: "Conditions" }).click();
    await expect(inspector.getByText("IF", { exact: true }).first()).toBeVisible({ timeout: 3000 });
    await expect(inspector.getByText("THEN").first()).toBeVisible();
    await expect(inspector.getByText("ELSE").first()).toBeVisible();
  });

  test("switch to Expression mode → shows Jinja2 textarea", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await page.locator(".react-flow__node").first().click();

    const inspector = page.locator('[aria-label="Node inspector panel"]');
    await inspector.getByRole("tab", { name: "Conditions" }).click();
    await inspector.locator("button:has-text('Expression')").click();
    await expect(inspector.getByRole("textbox", { name: "Expression (Jinja2)" })).toBeVisible({ timeout: 5000 });
  });

  test("close inspector via close button", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await page.locator(".react-flow__node").first().click();

    const inspector = page.locator('[aria-label="Node inspector panel"]');
    await expect(inspector).toBeVisible({ timeout: 5000 });

    await page.getByRole("button", { name: "Close inspector panel" }).click();
    await expect(inspector).not.toBeVisible({ timeout: 3000 });
  });

  test("click canvas background → inspector closes", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await page.locator(".react-flow__node").first().click();

    const inspector = page.locator('[aria-label="Node inspector panel"]');
    await expect(inspector).toBeVisible({ timeout: 5000 });

    await page.locator(".react-flow__pane").click({ position: { x: 50, y: 50 } });
    await expect(inspector).not.toBeVisible({ timeout: 3000 });
  });

  test("click different node → inspector updates with new node data", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const paletteNode = page.locator("aside [draggable]").first();
    const canvas = page.locator(".react-flow__pane");

    // Add first node
    await paletteNode.dragTo(canvas, { targetPosition: { x: 20, y: 20 } });
    await page.locator(".react-flow__node").first().click();
    const inspector = page.locator('[aria-label="Node inspector panel"]');
    await expect(inspector).toBeVisible({ timeout: 5000 });
    const nameInput1 = inspector.getByRole("textbox", { name: "Node name" });
    await nameInput1.fill("First Node");

    // Add second node (drag another palette item - e.g. Placeholder)
    await page.locator("aside [draggable]").nth(1).dragTo(canvas, { targetPosition: { x: 300, y: 20 } });
    await expect(page.locator(".react-flow__node")).toHaveCount(2, { timeout: 5000 });

    await page.locator(".react-flow__node").nth(1).click();
    const nameInput2 = inspector.getByRole("textbox", { name: "Node name" });
    await expect(nameInput2).toBeVisible({ timeout: 3000 });
    // Second node has different default name (from palette item)
    await expect(nameInput2).not.toHaveValue("First Node");
  });
});
