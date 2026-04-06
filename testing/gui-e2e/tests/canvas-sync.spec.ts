import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const API = "http://localhost:8000/api";

test.describe("Canvas Sync (RUN-62)", () => {
  const workflowName = `e2e-canvas-sync-${Date.now()}`;
  let workflowId: string | null = null;

  test.beforeAll(async () => {
    const response = await fetch(`${API}/workflows`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: workflowName,
        yaml: [
          'version: "1.0"',
          "blocks:",
          "  step_a:",
          "    type: linear",
          "workflow:",
          "  name: Demo",
          "  entry: step_a",
          "  transitions: []",
          "",
        ].join("\n"),
      }),
    });
    const data = await response.json();
    workflowId = data.id;
  });

  test.afterAll(async () => {
    if (!workflowId) return;
    await fetch(`${API}/workflows/${workflowId}`, { method: "DELETE" });
  });

  test("code edits can be applied to visual graph", async ({ page }) => {

    await page.goto(`/workflows/${workflowId}`);
    await page.waitForSelector('[data-testid="canvas-reactflow"]', { timeout: 15000 });

    await page.getByTestId("canvas-mode-code").click();
    await expect(page.getByTestId("canvas-yaml-editor")).toBeVisible();

    const yamlWithSecondNode = [
      'version: "1.0"',
      "blocks:",
      "  step_a:",
      "    type: linear",
      "  step_b:",
      "    type: dispatch",
      "workflow:",
      "  name: Demo",
      "  entry: step_a",
      "  transitions:",
      "    - from: step_a",
      "      to: step_b",
      "",
    ].join("\n");

    await page.evaluate((text) => {
      const el = document.querySelector('[data-testid="canvas-yaml-editor"]') as { __e2eSetValue?: (value: string) => void } | null;
      if (el?.__e2eSetValue) {
        el.__e2eSetValue(text);
      }
    }, yamlWithSecondNode);

    await page.getByTestId("canvas-apply-yaml").click();
    await page.getByTestId("canvas-mode-visual").click();
    await expect(page.locator(".react-flow__node")).toHaveCount(2);
  });

  test("save/load cycle persists visual canvas_state separate from yaml", async ({ page }) => {

    await page.goto(`/workflows/${workflowId}`);
    await page.waitForSelector('[data-testid="canvas-reactflow"]', { timeout: 15000 });

    await page.getByTestId("canvas-save").click();
    await expect(page.getByTestId("canvas-save")).toContainText("Save");

    const response = await fetch(`${API}/workflows/${workflowId}`);
    const data = await response.json();
    expect(data.canvas_state).toBeDefined();
    expect(Array.isArray(data.canvas_state.nodes)).toBeTruthy();
    expect(data.canvas_state.viewport).toBeDefined();
    expect(typeof data.yaml).toBe("string");
  });
});
