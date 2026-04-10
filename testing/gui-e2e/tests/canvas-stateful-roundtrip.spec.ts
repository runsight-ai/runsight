import { expect, test } from "@playwright/test";
import { parse } from "yaml";
import {
  apiDelete,
  apiGet,
  apiPost,
  apiPut,
  gotoShellRoute,
  useShellReadyWorkspace,
} from "./helpers/shellReady";
import {
  gotoWorkflowEditor,
  openCanvasTab,
  readWorkflowYaml,
  setWorkflowYaml,
} from "./helpers/workflowEditor";

test.describe.configure({ mode: "serial" });
useShellReadyWorkspace(test);

type WorkflowRecord = {
  id: string;
  yaml?: string;
};

test.describe("Surface YAML stateful round-trip", () => {
  let workflowId: string;

  test.beforeAll(async () => {
    const created = await apiPost<WorkflowRecord>("/workflows", {
      name: `e2e-stateful-${Date.now()}`,
      yaml: "",
      canvas_state: {
        nodes: [],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
        selected_node_id: null,
        canvas_mode: "dag",
      },
      commit: false,
    });
    workflowId = created.id;
  });

  test.afterAll(async () => {
    await apiDelete(`/workflows/${workflowId}`);
  });

  test("preserves stateful: true after YAML save and editor reload", async ({ page }) => {
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

    await gotoWorkflowEditor(page, workflowId);
    await setWorkflowYaml(page, yamlInput);
    await expect(page.getByTestId("workflow-save-button")).toBeEnabled();
    await apiPut<WorkflowRecord>(`/workflows/${workflowId}`, { yaml: yamlInput });

    const saved = await apiGet<WorkflowRecord>(`/workflows/${workflowId}`);
    const persistedYaml = saved.yaml ?? "";
    expect(parse(persistedYaml).blocks.step_a.stateful).toBe(true);

    await page.reload();
    await gotoWorkflowEditor(page, workflowId);
    await openCanvasTab(page);

    await expect
      .poll(async () => {
        const reloadedYaml = await readWorkflowYaml(page);
        return parse(reloadedYaml)?.blocks?.step_a?.stateful;
      })
      .toBe(true);
  });

  test("omits stateful when the block does not declare it", async ({ page }) => {
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

    await gotoWorkflowEditor(page, workflowId);
    await setWorkflowYaml(page, yamlInput);
    await expect(page.getByTestId("workflow-save-button")).toBeEnabled();
    await apiPut<WorkflowRecord>(`/workflows/${workflowId}`, { yaml: yamlInput });

    await page.reload();
    await gotoWorkflowEditor(page, workflowId);
    const reloadedYaml = await readWorkflowYaml(page);
    expect(parse(reloadedYaml).blocks.step_a.stateful).toBeUndefined();
  });

  test("keeps stateful only on the blocks that declare it", async ({ page }) => {
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

    await gotoWorkflowEditor(page, workflowId);
    await setWorkflowYaml(page, yamlInput);
    await expect(page.getByTestId("workflow-save-button")).toBeEnabled();
    await apiPut<WorkflowRecord>(`/workflows/${workflowId}`, { yaml: yamlInput });

    await gotoShellRoute(page, `/workflows/${workflowId}/edit`);
    const reloadedYaml = await readWorkflowYaml(page);
    const parsed = parse(reloadedYaml);

    expect(parsed.blocks.step_stateful.stateful).toBe(true);
    expect(parsed.blocks.step_plain.stateful).toBeUndefined();
  });
});
