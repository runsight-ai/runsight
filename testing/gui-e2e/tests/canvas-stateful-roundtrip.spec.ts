import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import { parse } from "yaml";

test.describe.configure({ mode: "serial" });

const API = "http://localhost:8000/api";

test.describe("Canvas YAML — stateful field round-trip", () => {
  const testWorkflowName = `e2e-stateful-${Date.now()}`;
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

  // ---------------------------------------------------------------------------
  // Helper: set YAML in the code editor and apply it
  // ---------------------------------------------------------------------------
  async function setYamlAndApply(page: Page, yaml: string) {
    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector('[data-testid="canvas-reactflow"]', { timeout: 15000 });

    // Switch to Code mode
    await page.getByTestId("canvas-mode-code").click();
    await expect(page.getByTestId("canvas-yaml-editor")).toBeVisible({ timeout: 5000 });

    // Inject YAML via the Monaco __e2eSetValue bridge
    await page.evaluate((text) => {
      const el = document.querySelector('[data-testid="canvas-yaml-editor"]') as
        | { __e2eSetValue?: (value: string) => void }
        | null;
      if (el?.__e2eSetValue) {
        el.__e2eSetValue(text);
      }
    }, yaml);

    // Apply the YAML
    await page.getByTestId("canvas-apply-yaml").click();
  }

  // ---------------------------------------------------------------------------
  // Helper: trigger recompilation via save, then read the recompiled YAML
  // ---------------------------------------------------------------------------
  async function triggerRecompileAndReadYaml(page: Page): Promise<string> {
    // Click canvas-save to trigger compileGraphToWorkflowYaml
    await page.getByTestId("canvas-save").click();
    await expect(page.getByTestId("canvas-save")).toContainText("Save", { timeout: 5000 });

    // Switch to Code mode to read the recompiled YAML
    await page.getByTestId("canvas-mode-code").click();
    await expect(page.getByTestId("canvas-yaml-editor")).toBeVisible({ timeout: 5000 });

    // Read value via Monaco editor API (no __e2eGetValue bridge exists)
    const yamlText = await page.evaluate(() => {
      type MonacoWindow = Window & {
        monaco?: {
          editor?: {
            getModels?: () => Array<{ getValue: () => string }>;
          };
        };
      };

      const models = (window as MonacoWindow).monaco?.editor?.getModels?.();
      if (models && models.length > 0) return models[0].getValue();
      // Fallback: read textContent from the editor element
      const el = document.querySelector('[data-testid="canvas-yaml-editor"]');
      return el?.textContent ?? "";
    });

    return yamlText;
  }

  // ---------------------------------------------------------------------------
  // 1. YAML with stateful: true → Apply → Visual → Save → Code preserves stateful
  // ---------------------------------------------------------------------------
  test("stateful: true survives Visual → Code → Apply → Code round-trip", async ({ page }) => {

    const yamlInput = [
      'version: "1.0"',
      "blocks:",
      "  step_a:",
      "    type: linear",
      "    stateful: true",
      "workflow:",
      "  name: StatefulTest",
      "  entry: step_a",
      "  transitions: []",
      "",
    ].join("\n");

    await setYamlAndApply(page, yamlInput);

    // Switch to Visual mode
    await page.getByTestId("canvas-mode-visual").click();
    await expect(page.locator(".react-flow__node")).toHaveCount(1, { timeout: 5000 });

    // Save to trigger recompilation, then read recompiled YAML
    const outputYaml = await triggerRecompileAndReadYaml(page);
    const parsed = parse(outputYaml);
    expect(parsed.blocks.step_a.stateful).toBe(true);
  });

  // ---------------------------------------------------------------------------
  // 2. Block without stateful — field is omitted from YAML output (no clutter)
  // ---------------------------------------------------------------------------
  test("stateful is omitted from YAML when not set on the block", async ({ page }) => {

    const yamlInput = [
      'version: "1.0"',
      "blocks:",
      "  step_a:",
      "    type: linear",
      "workflow:",
      "  name: NoStatefulTest",
      "  entry: step_a",
      "  transitions: []",
      "",
    ].join("\n");

    await setYamlAndApply(page, yamlInput);

    // Switch to Visual mode
    await page.getByTestId("canvas-mode-visual").click();
    await expect(page.locator(".react-flow__node")).toHaveCount(1, { timeout: 5000 });

    // Save to trigger recompilation, then read recompiled YAML
    const outputYaml = await triggerRecompileAndReadYaml(page);
    const parsed = parse(outputYaml);
    expect(parsed.blocks.step_a.stateful).toBeUndefined();
  });

  // ---------------------------------------------------------------------------
  // 3. Mixed workflow: one block with stateful: true, one without
  // ---------------------------------------------------------------------------
  test("mixed workflow preserves stateful on correct blocks only", async ({ page }) => {

    const yamlInput = [
      'version: "1.0"',
      "blocks:",
      "  step_stateful:",
      "    type: linear",
      "    stateful: true",
      "  step_plain:",
      "    type: dispatch",
      "workflow:",
      "  name: MixedStatefulTest",
      "  entry: step_stateful",
      "  transitions:",
      "    - from: step_stateful",
      "      to: step_plain",
      "",
    ].join("\n");

    await setYamlAndApply(page, yamlInput);

    // Switch to Visual mode — expect 2 nodes
    await page.getByTestId("canvas-mode-visual").click();
    await expect(page.locator(".react-flow__node")).toHaveCount(2, { timeout: 5000 });

    // Save to trigger recompilation, then read recompiled YAML
    const outputYaml = await triggerRecompileAndReadYaml(page);
    const parsed = parse(outputYaml);

    // The stateful block should retain stateful: true
    expect(parsed.blocks.step_stateful.stateful).toBe(true);

    // The step_plain block should NOT have a stateful field
    expect(parsed.blocks.step_plain.stateful).toBeUndefined();
  });
});
