import { expect, test } from "@playwright/test";

import {
  apiDelete,
  apiPost,
  gotoShellRoute,
  useShellReadyWorkspace,
} from "./helpers/shellReady";
import { gotoWorkflowEditor, openCanvasTab, workflowUrlId } from "./helpers/workflowEditor";

test.describe.configure({ mode: "serial" });
useShellReadyWorkspace(test);

type WorkflowSummary = {
  id: string;
  name: string;
};

test.describe("Workflow editor shell", () => {
  let seededWorkflowId: string | null = null;
  const createdWorkflowIds = new Set<string>();

  test.beforeAll(async () => {
    const workflow = await apiPost<WorkflowSummary>("/workflows", {
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
    seededWorkflowId = workflow.id;
    createdWorkflowIds.add(workflow.id);
  });

  test.afterAll(async () => {
    for (const workflowId of createdWorkflowIds) {
      await apiDelete(`/workflows/${workflowId}`);
    }
  });

  test("creates a workflow from Flows and opens the shared editor route directly", async ({
    page,
  }) => {
    await gotoShellRoute(page, "/flows");

    await page.getByTestId("flows-create-workflow-button").click();

    await expect(page).toHaveURL(/\/workflows\/[^/]+\/edit(?:\?.*)?$/, { timeout: 15_000 });
    await expect(page.getByRole("dialog")).toHaveCount(0);

    const workflowId = workflowUrlId(page.url());
    createdWorkflowIds.add(workflowId);
    await expect(page.getByTestId("workflow-name-display")).toBeVisible();
  });

  test("loads the shared surface editor and lets the user switch to the canvas view", async ({
    page,
  }) => {
    await gotoWorkflowEditor(page, seededWorkflowId!);

    await expect(page.getByTestId("workflow-tab-yaml")).toBeVisible();
    await expect(page.getByTestId("workflow-yaml-editor")).toBeVisible();

    await openCanvasTab(page);
  });
});
