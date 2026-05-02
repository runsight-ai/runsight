import { expect, test } from "@playwright/test";

import {
  apiDelete,
  apiGet,
  apiPost,
  apiPut,
  buildBlankWorkflowYaml,
  setupShellReadyWorkspace,
} from "./helpers/shellReady";
import {
  gotoWorkflowEditor,
  openCanvasTab,
  openYamlTab,
  readWorkflowYaml,
  setWorkflowYaml,
} from "./helpers/workflowEditor";

test.describe.configure({ mode: "serial" });
setupShellReadyWorkspace(test);

type WorkflowResponse = {
  id: string;
  yaml: string | null;
  canvas_state?: {
    nodes?: unknown[];
    viewport?: Record<string, unknown>;
  } | null;
};

test.describe("Workflow YAML editor", () => {
  let workflowId: string | null = null;

  test.beforeAll(async () => {
    const id = `e2e-yaml-${Date.now()}`;
    const workflow = await apiPost<WorkflowResponse>("/workflows", {
      name: "Demo",
      yaml: buildBlankWorkflowYaml(id, "Demo"),
      canvas_state: {
        nodes: [],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
        selected_node_id: null,
        canvas_mode: "dag",
      },
      commit: false,
    });
    workflowId = workflow.id;
  });

  test.afterAll(async () => {
    if (workflowId) {
      await apiDelete(`/workflows/${workflowId}`);
    }
  });

  test("switches between YAML and Canvas using the shared surface tabs", async ({ page }) => {
    await gotoWorkflowEditor(page, workflowId!);

    await openYamlTab(page);
    await openCanvasTab(page);
    await openYamlTab(page);
  });

  test("loads the current workflow YAML and persists edits through the commit dialog", async ({
    page,
  }) => {
    const updatedYaml = buildBlankWorkflowYaml(workflowId!, "Demo Updated");

    await gotoWorkflowEditor(page, workflowId!);

    expect(await readWorkflowYaml(page)).toContain("kind: workflow");

    await setWorkflowYaml(page, updatedYaml);
    await expect(page.getByTestId("workflow-save-button")).toBeEnabled();
    await page.getByTestId("workflow-save-button").click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).not.toBeVisible();

    await apiPut<WorkflowResponse>(`/workflows/${workflowId}`, {
      yaml: updatedYaml,
      canvas_state: {
        nodes: [
          {
            id: "step_a",
            position: { x: 0, y: 0 },
            data: { label: "step_a" },
            type: "task",
          },
        ],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
        selected_node_id: null,
        canvas_mode: "dag",
      },
    });
    await page.reload();
    await gotoWorkflowEditor(page, workflowId!);

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
});
