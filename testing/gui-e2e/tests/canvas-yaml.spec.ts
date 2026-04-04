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

  test("switches between Visual and Code modes", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector('[data-testid="canvas-reactflow"]', { timeout: 15000 });

    await page.getByTestId("canvas-mode-code").click();
    await expect(page.getByTestId("canvas-yaml-editor")).toBeVisible({ timeout: 5000 });

    await page.getByTestId("canvas-mode-visual").click();
    await expect(page.locator(".react-flow")).toBeVisible({ timeout: 5000 });
  });

  test("can apply YAML from editor into visual graph", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector('[data-testid="canvas-reactflow"]', { timeout: 15000 });
    await page.getByTestId("canvas-mode-code").click();
    await expect(page.getByTestId("canvas-yaml-editor")).toBeVisible();

    const yamlText = [
      'version: "1.0"',
      "blocks:",
      "  step_a:",
      "    type: linear",
      "  step_b:",
      "    type: fanout",
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
    }, yamlText);

    await page.getByTestId("canvas-apply-yaml").click();
    await page.getByTestId("canvas-mode-visual").click();
    await expect(page.locator(".react-flow__node")).toHaveCount(2);
  });

  test("invalid YAML shows parse error without crashing", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector('[data-testid="canvas-reactflow"]', { timeout: 15000 });
    await page.getByTestId("canvas-mode-code").click();
    await expect(page.getByTestId("canvas-yaml-editor")).toBeVisible();

    await page.evaluate(() => {
      const el = document.querySelector('[data-testid="canvas-yaml-editor"]') as { __e2eSetValue?: (value: string) => void } | null;
      if (el?.__e2eSetValue) {
        el.__e2eSetValue("invalid: yaml: [[[");
      }
    });

    await page.getByTestId("canvas-apply-yaml").click();
    await expect(page.getByTestId("canvas-parse-error")).toBeVisible({ timeout: 5000 });
  });
});
