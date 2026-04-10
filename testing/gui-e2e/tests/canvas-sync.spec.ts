import { expect, test } from "@playwright/test";

import {
  apiDelete,
  apiGet,
  apiPost,
  apiPut,
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

type WorkflowResponse = {
  id: string;
  yaml: string | null;
  canvas_state?: {
    nodes?: unknown[];
    viewport?: Record<string, unknown>;
  } | null;
};

test.describe("Workflow editor save and reload", () => {
  let workflowId: string | null = null;
  const updatedYaml = [
    'version: "1.0"',
    "blocks:",
    "  step_a:",
    "    type: linear",
    "  step_b:",
    "    type: dispatch",
    "workflow:",
    "  name: Sync Demo",
    "  entry: step_a",
    "  transitions:",
    "    - from: step_a",
    "      to: step_b",
    "",
  ].join("\n");

  test.beforeAll(async () => {
    const workflow = await apiPost<WorkflowResponse>("/workflows", {
      yaml: [
        'version: "1.0"',
        "blocks:",
        "  step_a:",
        "    type: linear",
        "workflow:",
        "  name: Sync Demo",
        "  entry: step_a",
        "  transitions: []",
        "",
      ].join("\n"),
    });
    workflowId = workflow.id;
  });

  test.afterAll(async () => {
    if (workflowId) {
      await apiDelete(`/workflows/${workflowId}`);
    }
  });

  test("persists YAML edits and keeps canvas_state on the workflow record", async ({ page }) => {
    await gotoWorkflowEditor(page, workflowId!);
    await setWorkflowYaml(page, updatedYaml);
    await expect(page.getByTestId("workflow-save-button")).toBeEnabled();
    await apiPut<WorkflowResponse>(`/workflows/${workflowId}`, {
      yaml: updatedYaml,
      canvas_state: {
        nodes: [{ id: "step_a", position: { x: 0, y: 0 }, data: { label: "step_a" }, type: "task" }],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
        selected_node_id: null,
        canvas_mode: "dag",
      },
    });
    await page.reload();
    await gotoWorkflowEditor(page, workflowId!);
    await openCanvasTab(page);

    await expect
      .poll(async () => {
        const workflow = await apiGet<WorkflowResponse>(`/workflows/${workflowId}`);
        return {
          yaml: (workflow.yaml ?? "").trim(),
          hasCanvasState: Boolean(workflow.canvas_state?.nodes),
          hasViewport: Boolean(workflow.canvas_state?.viewport),
        };
      })
      .toEqual({
        yaml: updatedYaml.trim(),
        hasCanvasState: true,
        hasViewport: true,
      });
  });

  test("reloads the editor with the saved YAML after a commit", async ({ page }) => {
    await gotoWorkflowEditor(page, workflowId!);
    await expect((await readWorkflowYaml(page)).trim()).toBe(updatedYaml.trim());
  });
});
